#!/usr/bin/env python3
"""
Trace-driven cache policy simulator — Adarsh (2023B1A31167G)
BITS Pilani Goa / Sharanga HPC

Compares LRU, LFU (persistent counters), and TinyLFU on real Criteo
embedding access traces across multiple cache capacities.

Usage:
    python3 run_trace_sim.py --criteo_path /path/to/criteo_train.csv \
                             --n_rows 5000000 \
                             --output results/

Criteo dataset: kaggle competitions download -c criteo-display-ad-challenge
File: train.txt (TSV) or train.csv
Columns 14–39 are the 26 categorical embedding features (C1–C26).
"""

import argparse
import csv
import os
import sys
import time
import json
import heapq
from collections import OrderedDict, defaultdict


# ══════════════════════════════════════════════════════════════
# CACHE IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════

class LRUCache:
    """Standard LRU — evicts least recently used line."""
    name = "LRU"

    def __init__(self, capacity):
        self.cap = capacity
        self.cache = OrderedDict()
        self.hits = self.misses = 0

    def access(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            self.hits += 1
            return True
        self.misses += 1
        if len(self.cache) >= self.cap:
            self.cache.popitem(last=False)
        self.cache[key] = 1
        return False

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total * 100 if total > 0 else 0.0

    @property
    def dram_reads(self):
        return self.misses


class _MinFreqIndex:
    """
    Lazy min-heap over (frequency, entry_sequence, key).

    Gives the same victim as scanning a dict in insertion order for the
    smallest frequency (ties -> the key that entered the cache earliest),
    but in O(log n) instead of O(n) per eviction.
    """
    def __init__(self):
        self.heap = []

    def push(self, freq, seq, key):
        heapq.heappush(self.heap, (freq, seq, key))

    def peek_valid(self, is_valid):
        h = self.heap
        while h and not is_valid(h[0]):
            heapq.heappop(h)
        return h[0] if h else None

    def pop(self):
        return heapq.heappop(self.heap)

    def rebuild(self, entries):
        self.heap = list(entries)
        heapq.heapify(self.heap)


class LFUCache:
    """
    LFU with per-ADDRESS frequency history that survives eviction.

    This is an idealised history model: the counter for an address is
    kept in an unbounded dictionary, so a line that is evicted and later
    re-fetched resumes from its old count. The hardware in rtl/ keeps
    counters per cache SLOT, which is a different (cheaper) mechanism,
    so results from this class bound what a history-keeping LFU could
    achieve; they are not a cycle-accurate model of the RTL.

    Counters saturate at 255.
    """
    name = "LFU (persistent counters)"

    def __init__(self, capacity):
        self.cap = capacity
        self.cache = {}            # key -> entry sequence number
        self.freq = {}             # key -> count (kept after eviction)
        self.index = _MinFreqIndex()
        self.seq = 0
        self.hits = self.misses = 0

    def _valid(self, entry):
        f, s, k = entry
        return self.cache.get(k) == s and self.freq[k] == f

    def access(self, key):
        if key in self.cache:
            f = self.freq[key]
            if f < 255:
                f += 1
                self.freq[key] = f
                self.index.push(f, self.cache[key], key)
                if len(self.index.heap) > 4 * self.cap + 10000:
                    self.index.rebuild((self.freq[k], s, k) for k, s in self.cache.items())
            self.hits += 1
            return True

        self.misses += 1
        if len(self.cache) >= self.cap:
            self.index.peek_valid(self._valid)
            _, _, victim = self.index.pop()
            del self.cache[victim]          # freq[victim] is kept
        self.seq += 1
        self.cache[key] = self.seq
        f = min(255, self.freq.get(key, 0) + 1)
        self.freq[key] = f
        self.index.push(f, self.seq, key)
        return False

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total * 100 if total > 0 else 0.0

    @property
    def dram_reads(self):
        return self.misses


class LFUResetCache:
    """
    LFU where an address's count is discarded on eviction and restarts
    at 1 when re-fetched (the behaviour hypothesised for gem5 LFURP).
    Compare against LFUCache to isolate the effect of keeping history.
    """
    name = "LFU (gem5 LFURP \u2014 reset on eviction)"

    def __init__(self, capacity):
        self.cap = capacity
        self.cache = {}
        self.freq = {}
        self.index = _MinFreqIndex()
        self.seq = 0
        self.hits = self.misses = 0

    def _valid(self, entry):
        f, s, k = entry
        return self.cache.get(k) == s and self.freq.get(k) == f

    def access(self, key):
        if key in self.cache:
            f = self.freq[key]
            if f < 255:
                f += 1
                self.freq[key] = f
                self.index.push(f, self.cache[key], key)
                if len(self.index.heap) > 4 * self.cap + 10000:
                    self.index.rebuild((self.freq[k], s, k) for k, s in self.cache.items())
            self.hits += 1
            return True

        self.misses += 1
        if len(self.cache) >= self.cap:
            self.index.peek_valid(self._valid)
            _, _, victim = self.index.pop()
            del self.cache[victim]
            del self.freq[victim]           # RESET on eviction
        self.seq += 1
        self.cache[key] = self.seq
        self.freq[key] = 1
        self.index.push(1, self.seq, key)
        return False

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total * 100 if total > 0 else 0.0

    @property
    def dram_reads(self):
        return self.misses


class TinyLFUCache:
    """
    Idealised Window-TinyLFU: a small LRU admission window in front of an
    LFU main cache. Frequencies come from an EXACT unbounded counter table
    (no Count-Min sketch, no aging, no doorkeeper), so this is an upper
    bound on what the real TinyLFU admission filter achieves.
    window_pct: fraction of capacity used as the LRU window.
    """
    name = "TinyLFU (Window-LRU + LFU main)"

    def __init__(self, capacity, window_pct=0.01):
        self.total_cap = capacity
        self.win_cap   = max(1, int(capacity * window_pct))
        self.main_cap  = capacity - self.win_cap
        self.window    = OrderedDict()
        self.main      = {}                # key -> entry sequence number
        self.main_freq = {}
        self.index     = _MinFreqIndex()
        self.seq       = 0
        self.sketch    = defaultdict(int)
        self.hits = self.misses = 0

    def _valid(self, entry):
        f, s, k = entry
        return self.main.get(k) == s and self.main_freq[k] == f

    def _admit(self, key, freq):
        self.seq += 1
        self.main[key] = self.seq
        self.main_freq[key] = freq
        self.index.push(freq, self.seq, key)
        if len(self.index.heap) > 4 * self.main_cap + 10000:
            self.index.rebuild((self.main_freq[k], s, k) for k, s in self.main.items())

    def access(self, key):
        self.sketch[key] += 1

        if key in self.main:
            new = min(255, self.main_freq[key] + 1)
            if new != self.main_freq[key]:
                self.main_freq[key] = new
                self.index.push(new, self.main[key], key)
            self.hits += 1
            return True

        if key in self.window:
            self.window.move_to_end(key)
            self.hits += 1
            return True

        self.misses += 1

        if len(self.window) >= self.win_cap:
            candidate, _ = self.window.popitem(last=False)
            if len(self.main) >= self.main_cap:
                top = self.index.peek_valid(self._valid)
                if top is not None and self.sketch[candidate] > top[0]:
                    self.index.pop()
                    victim = top[2]
                    del self.main[victim]
                    del self.main_freq[victim]
                    self._admit(candidate, self.sketch[candidate])
            else:
                self._admit(candidate, self.sketch[candidate])

        self.window[key] = 1
        return False

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total * 100 if total > 0 else 0.0

    @property
    def dram_reads(self):
        return self.misses


# ══════════════════════════════════════════════════════════════
# TRACE LOADING
# ══════════════════════════════════════════════════════════════

def load_criteo_traces(path, n_rows=None, col_indices=None):
    """
    Load Criteo Train TSV/CSV and extract embedding access traces.

    Criteo format (tab-separated):
      Col 0:    label (0/1)
      Cols 1-13: 13 dense integer features
      Cols 14-39: 26 categorical hex features (C1-C26) — these are our embedding IDs

    Returns: list of lists — traces[col_idx] = [feature_id, feature_id, ...]
    """
    # Categorical columns are 14..39 (0-indexed)
    cat_cols = list(range(14, 40)) if col_indices is None else col_indices
    n_cat = len(cat_cols)
    traces = [[] for _ in range(n_cat)]

    delimiter = '\t'
    # Auto-detect delimiter from file extension
    if path.endswith('.csv'):
        delimiter = ','

    print(f"Loading Criteo traces from: {path}")
    print(f"  Categorical columns: {cat_cols[0]}..{cat_cols[-1]} ({n_cat} embedding tables)")
    if n_rows:
        print(f"  Max rows: {n_rows:,}")

    t0 = time.time()
    rows_loaded = 0
    with open(path, 'r', buffering=1 << 20) as f:
        reader = csv.reader(f, delimiter=delimiter)
        for row in reader:
            if not row:
                continue
            for i, col in enumerate(cat_cols):
                if col < len(row) and row[col].strip():
                    # Criteo uses hex strings — convert to int for cache key
                    try:
                        fid = int(row[col], 16)
                        traces[i].append(fid)
                    except ValueError:
                        pass
            rows_loaded += 1
            if n_rows and rows_loaded >= n_rows:
                break
            if rows_loaded % 500_000 == 0:
                elapsed = time.time() - t0
                print(f"  Loaded {rows_loaded:,} rows in {elapsed:.1f}s")

    elapsed = time.time() - t0
    total_accesses = sum(len(t) for t in traces)
    print(f"  Done: {rows_loaded:,} rows, {total_accesses:,} total accesses in {elapsed:.1f}s")
    return traces, rows_loaded


# ══════════════════════════════════════════════════════════════
# SIMULATION
# ══════════════════════════════════════════════════════════════


class TinyLFUPolicy(TinyLFUCache):
    """TinyLFUCache with a fixed window fraction and a stable display name."""
    name = "TinyLFU (window=1%)"

    def __init__(self, capacity):
        super().__init__(capacity, window_pct=0.01)


POLICIES = [LRUCache, LFUCache, LFUResetCache, TinyLFUPolicy]


def run_one(job):
    """Simulate one (policy, capacity) pair over every embedding table."""
    policy_cls, capacity, traces = job
    hits = misses = 0
    for trace in traces:
        if not trace:
            continue
        cache = policy_cls(capacity)
        for key in trace:
            cache.access(key)
        hits += cache.hits
        misses += cache.misses
    total = hits + misses
    return (policy_cls.name, capacity, hits, misses,
            hits / total * 100 if total else 0.0)


def run_sweep(traces, capacities, workers):
    jobs = [(p, c, traces) for c in capacities for p in POLICIES]
    results = {c: {} for c in capacities}
    if workers > 1:
        from multiprocessing import Pool
        with Pool(processes=workers) as pool:
            outputs = pool.imap_unordered(run_one, jobs)
            for name, cap, h, m, hr in outputs:
                results[cap][name] = {'hits': h, 'misses': m,
                                      'dram_reads': m, 'hit_rate': hr}
                print(f"  cap={cap:>8,}  {name:<22} hit-rate={hr:6.2f}%", flush=True)
    else:
        for job in jobs:
            name, cap, h, m, hr = run_one(job)
            results[cap][name] = {'hits': h, 'misses': m,
                                  'dram_reads': m, 'hit_rate': hr}
            print(f"  cap={cap:>8,}  {name:<22} hit-rate={hr:6.2f}%", flush=True)
    return results


def print_table(results, capacities):
    names = [p.name for p in POLICIES]
    print("\n" + "=" * 100)
    print(f"{'capacity':>10} | " + " | ".join(f"{n[:22]:>22}" for n in names) + " | best")
    print("=" * 100)
    for cap in capacities:
        r = results[cap]
        best = max(names, key=lambda n: r[n]['hit_rate'])
        print(f"{cap:>10,} | " +
              " | ".join(f"{r[n]['hit_rate']:>21.2f}%" for n in names) +
              f" | {best[:18]}")


def main():
    parser = argparse.ArgumentParser(description="Trace-driven cache policy simulator")
    parser.add_argument('--criteo_path', required=True,
                        help='Path to Criteo train.txt (tab-separated)')
    parser.add_argument('--n_rows', type=int, default=2_000_000)
    parser.add_argument('--output', default='results')
    parser.add_argument('--capacities', nargs='+', type=int,
                        default=[100, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000])
    parser.add_argument('--workers', type=int, default=1,
                        help='parallel processes (use the number of cores you requested)')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    traces, n_rows = load_criteo_traces(args.criteo_path, args.n_rows)
    total = sum(len(t) for t in traces)
    print(f"\nTrace: {n_rows:,} rows, {total:,} accesses, "
          f"{len(set(k for t in traces for k in t)):,} unique ids")
    print(f"Running {len(POLICIES) * len(args.capacities)} jobs on {args.workers} worker(s)\n")

    t0 = time.time()
    results = run_sweep(traces, args.capacities, args.workers)
    print(f"\nSweep finished in {time.time() - t0:.1f}s")
    print_table(results, args.capacities)

    out = os.path.join(args.output, 'trace_sim_results.json')
    with open(out, 'w') as f:
        json.dump({str(k): v for k, v in results.items()}, f, indent=2)
    print(f"\nSaved: {out}")

    print("\nLFU (history) minus LRU, in percentage points:")
    for cap in args.capacities:
        d = results[cap][LFUCache.name]['hit_rate'] - results[cap]['LRU']['hit_rate']
        print(f"  cap={cap:>8,}: {d:+6.2f} pp")


if __name__ == '__main__':
    main()
