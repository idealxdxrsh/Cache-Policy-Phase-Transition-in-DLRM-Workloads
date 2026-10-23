#!/usr/bin/env python3
"""
Trace-driven cache policy simulator — Adarsh (2023B1A31167G)
BITS Pilani Goa / Sharanga HPC

Compares LRU, LFU (per-address history), LFU (reset on eviction),
TinyLFU (exact counters), W-TinyLFU (Count-Min sketch) and ARC on Criteo
embedding access traces across cache capacities given in vectors.

Usage (one process, all tables):
    python3 run_trace_sim.py --criteo_path /path/to/train.txt \
                             --n_rows 2000000 --belady --workers 4 \
                             --output results/

Usage (sbatch array: dump once, one task per table, then merge):
    python3 run_trace_sim.py --criteo_path train.txt --n_rows 10000000 --dump_traces traces/
    python3 run_trace_sim.py --trace_dir traces/ --tables 7 --belady --workers 4 \
                             --output parts/ --tag table_07
    python3 merge_results.py --output results/trace_sim_results.json parts/table_*.json

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
import math
from array import array
from collections import Counter, OrderedDict, defaultdict


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


class CountMinSketch:
    """
    Count-Min sketch with 4-bit saturating counters and periodic aging,
    as used by TinyLFU (Einziger, Friedman & Manes, 2017).

    depth rows of `width` counters (width rounded up to a power of two).
    Each row uses a fixed multiply-shift hash, so runs are deterministic.
    After `sample_size` increments every counter is halved (the "reset"
    aging step) and the increment count is halved too.
    No doorkeeper Bloom filter is modelled.
    """
    MASK64 = (1 << 64) - 1
    SEEDS = (0x9E3779B97F4A7C15, 0xC2B2AE3D27D4EB4F,
             0x165667B19E3779F9, 0xD6E8FEB86659FD93)

    def __init__(self, width, sample_size, depth=4, max_count=15):
        assert 1 <= depth <= len(self.SEEDS)
        bits = max(4, (max(1, width) - 1).bit_length())
        self.width = 1 << bits
        self.shift = 64 - bits
        self.depth = depth
        self.max_count = max_count
        self.sample_size = sample_size
        self.additions = 0
        self.rows = [bytearray(self.width) for _ in range(depth)]

    def _indexes(self, key):
        if not isinstance(key, int):
            key = hash(key)
        key &= self.MASK64
        return [(((key ^ (key >> 29)) * a) & self.MASK64) >> self.shift
                for a in self.SEEDS[:self.depth]]

    def increment(self, key):
        mc = self.max_count
        for row, i in zip(self.rows, self._indexes(key)):
            if row[i] < mc:
                row[i] += 1
        self.additions += 1
        if self.additions >= self.sample_size:
            self.age()

    def age(self):
        for r in range(self.depth):
            self.rows[r] = bytearray(c >> 1 for c in self.rows[r])
        self.additions //= 2

    def estimate(self, key):
        return min(row[i] for row, i in zip(self.rows, self._indexes(key)))


class WTinyLFUCache:
    """
    Window-TinyLFU with a real Count-Min sketch (Einziger et al., 2017;
    the layout used by Caffeine):
      - window: LRU, window_pct of capacity (at least 1 line);
      - main:   segmented LRU, protected = 80% of main, rest probation;
      - admission: a line evicted from the window replaces the probation
        LRU victim only if sketch(candidate) > sketch(victim);
      - sketch: CountMinSketch, width ~ capacity, 4 rows, 4-bit counters,
        halved every 10 x capacity accesses.
    Not modelled: doorkeeper, Caffeine's random admission of warm
    candidates, adaptive window sizing.
    """
    name = "W-TinyLFU (Count-Min, window=1%)"

    def __init__(self, capacity, window_pct=0.01, protected_pct=0.80):
        self.total_cap = capacity
        self.win_cap   = max(1, int(capacity * window_pct))
        self.main_cap  = capacity - self.win_cap
        self.prot_cap  = int(self.main_cap * protected_pct)
        self.window    = OrderedDict()
        self.probation = OrderedDict()
        self.protected = OrderedDict()
        self.sketch    = CountMinSketch(width=capacity, sample_size=10 * capacity)
        self.hits = self.misses = 0

    def __len__(self):
        return len(self.window) + len(self.probation) + len(self.protected)

    def access(self, key):
        self.sketch.increment(key)

        if key in self.window:
            self.window.move_to_end(key)
            self.hits += 1
            return True
        if key in self.protected:
            self.protected.move_to_end(key)
            self.hits += 1
            return True
        if key in self.probation:
            del self.probation[key]
            self.protected[key] = 1
            if len(self.protected) > self.prot_cap:
                demoted, _ = self.protected.popitem(last=False)
                self.probation[demoted] = 1
            self.hits += 1
            return True

        self.misses += 1
        self.window[key] = 1
        if len(self.window) > self.win_cap:
            candidate, _ = self.window.popitem(last=False)
            self._offer(candidate)
        return False

    def _offer(self, candidate):
        if self.main_cap == 0:
            return
        if len(self.probation) + len(self.protected) < self.main_cap:
            self.probation[candidate] = 1
            return
        victims = self.probation if self.probation else self.protected
        victim = next(iter(victims))
        if self.sketch.estimate(candidate) > self.sketch.estimate(victim):
            del victims[victim]
            self.probation[candidate] = 1

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total * 100 if total > 0 else 0.0

    @property
    def dram_reads(self):
        return self.misses


class ARCCache:
    """
    Adaptive Replacement Cache (Megiddo & Modha, FAST 2003), following the
    paper's pseudocode. T1/T2 hold resident lines (seen once / at least
    twice), B1/B2 are ghost lists of evicted keys (no data), and p is the
    adaptive target size of T1. A hit in a ghost list counts as a miss.
    """
    name = "ARC"

    def __init__(self, capacity):
        self.cap = capacity
        self.p = 0.0
        self.t1, self.t2 = OrderedDict(), OrderedDict()
        self.b1, self.b2 = OrderedDict(), OrderedDict()
        self.hits = self.misses = 0

    def __len__(self):
        return len(self.t1) + len(self.t2)

    def _replace(self, in_b2):
        t1 = len(self.t1)
        if self.t1 and (t1 > self.p or (in_b2 and t1 == self.p) or not self.t2):
            k, _ = self.t1.popitem(last=False)
            self.b1[k] = 1
        else:
            k, _ = self.t2.popitem(last=False)
            self.b2[k] = 1

    def access(self, key):
        c = self.cap
        if key in self.t1:
            del self.t1[key]
            self.t2[key] = 1
            self.hits += 1
            return True
        if key in self.t2:
            self.t2.move_to_end(key)
            self.hits += 1
            return True

        self.misses += 1
        if key in self.b1:
            self.p = min(c, self.p + max(len(self.b2) / len(self.b1), 1))
            if len(self) >= c:
                self._replace(False)
            del self.b1[key]
            self.t2[key] = 1
            return False
        if key in self.b2:
            self.p = max(0, self.p - max(len(self.b1) / len(self.b2), 1))
            if len(self) >= c:
                self._replace(True)
            del self.b2[key]
            self.t2[key] = 1
            return False

        l1 = len(self.t1) + len(self.b1)
        if l1 >= c:
            if len(self.t1) < c:
                self.b1.popitem(last=False)
                self._replace(False)
            else:
                self.t1.popitem(last=False)
        else:
            total = l1 + len(self.t2) + len(self.b2)
            if total >= c:
                if total >= 2 * c:
                    self.b2.popitem(last=False)
                if len(self) >= c:
                    self._replace(False)
        self.t1[key] = 1
        return False

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total * 100 if total > 0 else 0.0

    @property
    def dram_reads(self):
        return self.misses


class BeladyCache:
    """
    Belady's MIN: on a miss, evict the resident key whose next use is
    farthest in the future. Offline (needs the whole trace), demand-fetch,
    no bypass, so on the same trace no policy in this file can have more
    hits. Call prepare(trace) before replaying exactly that trace.
    """
    name = "Belady (MIN, offline)"
    offline = True

    def __init__(self, capacity):
        self.cap = capacity
        self.cache = {}            # key -> position of its next use
        self.heap = []             # lazy max-heap of (-next_use, key)
        self.next_use = None
        self.pos = 0
        self.hits = self.misses = 0

    def prepare(self, trace):
        n = len(trace)
        nxt = [n] * n              # n = never used again
        last = {}
        for i in range(n - 1, -1, -1):
            k = trace[i]
            nxt[i] = last.get(k, n)
            last[k] = i
        self.next_use = nxt
        self.pos = 0

    def access(self, key):
        nu = self.next_use[self.pos]
        self.pos += 1
        if key in self.cache:
            self.cache[key] = nu
            heapq.heappush(self.heap, (-nu, key))
            self.hits += 1
            hit = True
        else:
            self.misses += 1
            if len(self.cache) >= self.cap:
                h = self.heap
                while True:
                    neg, k = heapq.heappop(h)
                    if self.cache.get(k) == -neg:
                        break
                del self.cache[k]
            self.cache[key] = nu
            heapq.heappush(self.heap, (-nu, key))
            hit = False
        if len(self.heap) > 4 * self.cap + 10000:
            self.heap = [(-v, k) for k, v in self.cache.items()]
            heapq.heapify(self.heap)
        return hit

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

def load_criteo_traces(path, n_rows=None, col_indices=None, as_array=False):
    """
    Load Criteo Train TSV/CSV and extract embedding access traces.

    Criteo format (tab-separated):
      Col 0:    label (0/1)
      Cols 1-13: 13 dense integer features
      Cols 14-39: 26 categorical hex features (C1-C26) — these are our embedding IDs

    Returns: list of lists — traces[col_idx] = [feature_id, feature_id, ...]
    With as_array=True each trace is an array('I') (4 bytes per id instead of
    a Python int object), used when dumping large row counts.
    """
    # Categorical columns are 14..39 (0-indexed)
    cat_cols = list(range(14, 40)) if col_indices is None else col_indices
    n_cat = len(cat_cols)
    traces = [array('I') if as_array else [] for _ in range(n_cat)]

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
# TRACE STATISTICS
# ══════════════════════════════════════════════════════════════

def zipf_exponent(trace, min_count=5, min_points=10):
    """
    Rank-frequency Zipf exponent: alpha = -slope of an ordinary least-squares
    fit of log(count) on log(rank), over the ranks whose count >= min_count
    (the noisy singleton tail is excluded). Returns (alpha, n_points), or
    (None, n_points) if fewer than min_points ranks qualify.
    """
    counts = sorted(Counter(trace).values(), reverse=True)
    pts = [(math.log(r), math.log(c))
           for r, c in enumerate(counts, 1) if c >= min_count]
    n = len(pts)
    if n < min_points:
        return None, n
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    return -sxy / sxx, n


def table_stats(traces, table_ids):
    stats = []
    for t, trace in zip(table_ids, traces):
        alpha, npts = zipf_exponent(trace)
        stats.append({'table': t, 'column': 14 + t, 'accesses': len(trace),
                      'unique': len(set(trace)), 'zipf_alpha': alpha,
                      'zipf_fit_points': npts})
    return stats


# ══════════════════════════════════════════════════════════════
# PER-TABLE TRACE FILES (for sbatch array tasks)
# ══════════════════════════════════════════════════════════════

def dump_traces(traces, n_rows, out_dir, source):
    """Write each table as raw native uint32 (table_XX.u32) + meta.json."""
    os.makedirs(out_dir, exist_ok=True)
    for t, trace in enumerate(traces):
        if not isinstance(trace, array):
            trace = array('I', trace)        # raises if an id is >= 2**32
        with open(os.path.join(out_dir, f'table_{t:02d}.u32'), 'wb') as f:
            trace.tofile(f)
    meta = {'source': source, 'n_rows': n_rows, 'n_tables': len(traces),
            'accesses': [len(t) for t in traces], 'itemsize': array('I').itemsize}
    with open(os.path.join(out_dir, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=2)


def load_dumped_traces(trace_dir, tables):
    with open(os.path.join(trace_dir, 'meta.json')) as f:
        meta = json.load(f)
    traces = []
    for t in tables:
        a = array('I')
        with open(os.path.join(trace_dir, f'table_{t:02d}.u32'), 'rb') as f:
            a.frombytes(f.read())
        assert len(a) == meta['accesses'][t], f"table {t}: length mismatch"
        traces.append(a.tolist())
    return traces, meta


# ══════════════════════════════════════════════════════════════
# SIMULATION
# ══════════════════════════════════════════════════════════════


class TinyLFUPolicy(TinyLFUCache):
    """TinyLFUCache with a fixed window fraction and a stable display name."""
    name = "TinyLFU-exact (window=1%)"

    def __init__(self, capacity):
        super().__init__(capacity, window_pct=0.01)


POLICIES = [LRUCache, LFUCache, LFUResetCache, TinyLFUPolicy, WTinyLFUCache, ARCCache]
OFFLINE_POLICIES = [BeladyCache]

# Cache capacity in embedding VECTORS, one cache per table (PLAN.md P3).
# "1k", "2k" are taken as 1000 and 2000, like 5k..100k.
DEFAULT_CAPACITIES = [64, 128, 256, 512, 1000, 2000, 5000,
                      10000, 20000, 50000, 100000]

# Set before the worker pool is created, so forked workers inherit the
# traces instead of receiving a pickled copy with every job.
_TRACES = []


def run_one(job):
    """Simulate one (policy, capacity, table) triple."""
    policy_cls, capacity, idx, table = job
    trace = _TRACES[idx]
    t0 = time.process_time()
    cache = policy_cls(capacity)
    if getattr(cache, 'offline', False):
        cache.prepare(trace)
    for key in trace:
        cache.access(key)
    return (policy_cls.name, capacity, table, cache.hits, cache.misses,
            time.process_time() - t0)


def _rate(h, m):
    return h / (h + m) * 100 if h + m else 0.0


def aggregate(per_table):
    """per_table[cap][policy][table] = (hits, misses) -> results dict."""
    results = {}
    for cap, pols in per_table.items():
        results[cap] = {}
        for name, tabs in pols.items():
            h = sum(v[0] for v in tabs.values())
            m = sum(v[1] for v in tabs.values())
            results[cap][name] = {
                'hits': h, 'misses': m, 'dram_reads': m, 'hit_rate': _rate(h, m),
                'per_table': [{'table': t, 'hits': th, 'misses': tm,
                               'hit_rate': _rate(th, tm)}
                              for t, (th, tm) in sorted(tabs.items())]}
    return results


def run_sweep(traces, capacities, workers, policies=None, table_ids=None):
    """Returns (results, cpu_seconds_per_policy). Empty tables are skipped."""
    global _TRACES
    policies = POLICIES if policies is None else policies
    table_ids = list(range(len(traces))) if table_ids is None else table_ids
    _TRACES = traces
    jobs = [(p, c, i, t) for c in capacities for p in policies
            for i, t in enumerate(table_ids) if traces[i]]
    per_table = {c: {p.name: {} for p in policies} for c in capacities}
    cpu = defaultdict(float)

    def collect(out):
        name, cap, table, h, m, sec = out
        per_table[cap][name][table] = (h, m)
        cpu[name] += sec

    if workers > 1:
        from multiprocessing import get_context
        with get_context('fork').Pool(processes=workers) as pool:
            for out in pool.imap_unordered(run_one, jobs, chunksize=1):
                collect(out)
    else:
        for job in jobs:
            collect(run_one(job))
    return aggregate(per_table), dict(cpu)


def print_table(results, capacities, names):
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
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--criteo_path', help='Path to Criteo train.txt (tab-separated)')
    src.add_argument('--trace_dir', help='directory written by --dump_traces')
    parser.add_argument('--n_rows', type=int, default=2_000_000)
    parser.add_argument('--output', default='results')
    parser.add_argument('--capacities', nargs='+', type=int,
                        default=DEFAULT_CAPACITIES,
                        help='cache size in vectors, per embedding table')
    parser.add_argument('--tables', nargs='+', type=int, default=None,
                        help='table indices 0..25 to simulate (default: all)')
    parser.add_argument('--belady', action='store_true',
                        help='also run offline Belady MIN')
    parser.add_argument('--dump_traces', metavar='DIR',
                        help='write per-table uint32 traces to DIR and exit')
    parser.add_argument('--tag', default='trace_sim_results',
                        help='output file name (without .json)')
    parser.add_argument('--workers', type=int, default=1,
                        help='parallel processes (use the number of cores you requested)')
    args = parser.parse_args()

    t_load = time.time()
    if args.criteo_path:
        traces, n_rows = load_criteo_traces(args.criteo_path, args.n_rows,
                                            as_array=bool(args.dump_traces))
        source = args.criteo_path
        if args.dump_traces:
            dump_traces(traces, n_rows, args.dump_traces, source)
            print(f"Wrote {len(traces)} tables to {args.dump_traces}")
            return
        table_ids = args.tables or list(range(len(traces)))
        traces = [traces[t] for t in table_ids]
    else:
        meta = json.load(open(os.path.join(args.trace_dir, 'meta.json')))
        table_ids = args.tables or list(range(meta['n_tables']))
        traces, meta = load_dumped_traces(args.trace_dir, table_ids)
        n_rows, source = meta['n_rows'], meta['source']
    t_load = time.time() - t_load

    policies = POLICIES + (OFFLINE_POLICIES if args.belady else [])
    os.makedirs(args.output, exist_ok=True)
    total = sum(len(t) for t in traces)
    print(f"\nTrace: {n_rows:,} rows, tables {table_ids}, {total:,} accesses")
    t0 = time.time()
    stats = table_stats(traces, table_ids)
    t_stats = time.time() - t0
    for s in stats:
        a = 'n/a' if s['zipf_alpha'] is None else f"{s['zipf_alpha']:.3f}"
        print(f"  table {s['table']:>2}: {s['accesses']:>10,} accesses "
              f"{s['unique']:>10,} unique  zipf alpha {a} ({s['zipf_fit_points']} ranks)")

    n_jobs = len(policies) * len(args.capacities) * sum(1 for t in traces if t)
    print(f"Running {n_jobs} jobs on {args.workers} worker(s)\n")
    t0 = time.time()
    results, cpu = run_sweep(traces, args.capacities, args.workers, policies, table_ids)
    t_sweep = time.time() - t0
    print(f"\nSweep finished in {t_sweep:.1f}s")
    names = [p.name for p in policies]
    print_table(results, args.capacities, names)

    out = os.path.join(args.output, args.tag + '.json')
    with open(out, 'w') as f:
        json.dump({'meta': {'source': source, 'n_rows': n_rows, 'tables': table_ids,
                            'capacities': args.capacities, 'policies': names,
                            'capacity_unit': 'vectors, one cache per table',
                            'workers': args.workers,
                            'wall_seconds': {'load': t_load, 'stats': t_stats,
                                             'sweep': t_sweep},
                            'cpu_seconds_per_policy': cpu},
                   'tables': stats,
                   'results': {str(k): v for k, v in results.items()}}, f, indent=2)
    print(f"\nSaved: {out}")

    print("\nLFU (history) minus LRU, in percentage points:")
    for cap in args.capacities:
        d = results[cap][LFUCache.name]['hit_rate'] - results[cap]['LRU']['hit_rate']
        print(f"  cap={cap:>8,}: {d:+6.2f} pp")


if __name__ == '__main__':
    main()
