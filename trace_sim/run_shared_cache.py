#!/usr/bin/env python3
"""
Shared-cache variant of run_trace_sim.py: ONE cache over all 26 tables.

Access order: Criteo rows in file order; within a row, tables 0..25 (columns
14..39). Empty or non-hex fields produce no access, exactly as in
run_trace_sim.load_criteo_traces, so per-table access counts match P3.
Keys are table-qualified: key = table << 32 | id, i.e. (table, id) packed
into one int (Criteo ids are 32-bit), so equal ids in two tables are
different embedding rows. The policy classes are imported unchanged.

Usage:
    python3 run_shared_cache.py --criteo_path train.txt --n_rows 2000000 \
        --workers 4 --output results/P3b --tag shared_2M
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from array import array

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_trace_sim import (LRUCache, LFUResetCache, LFUCache,  # noqa: E402
                           ARCCache, WTinyLFUCache)
from rtl_exact import P9_POLICIES  # noqa: E402

POLICIES = [LRUCache, LFUResetCache, LFUCache, ARCCache, WTinyLFUCache]
# P9 (trace_sim/rtl_exact.py): selectable with --policies, not part of the default run
SELECTABLE = POLICIES + P9_POLICIES
DEFAULT_CAPACITIES = [256, 1000, 10000, 100000]
N_TABLES = 26
ID_BITS = 32

_KEYS = array('q')     # set before forking so workers share the trace


def make_key(table, fid):
    return table << ID_BITS | fid


def key_table(key):
    return key >> ID_BITS


def load_shared_trace(path, n_rows=None):
    """Returns (keys, rows_loaded, accesses_per_table); keys in row order."""
    cat_cols = list(range(14, 14 + N_TABLES))
    keys = array('q')
    per_table = [0] * N_TABLES
    delimiter = ',' if path.endswith('.csv') else '\t'
    rows_loaded = 0
    with open(path, 'r', buffering=1 << 20) as f:
        for row in csv.reader(f, delimiter=delimiter):
            if not row:
                continue
            for t, col in enumerate(cat_cols):
                if col < len(row) and row[col].strip():
                    try:
                        fid = int(row[col], 16)
                    except ValueError:
                        continue
                    if fid >> ID_BITS:
                        raise ValueError(f"id {row[col]!r} in table {t} exceeds {ID_BITS} bits")
                    keys.append(make_key(t, fid))
                    per_table[t] += 1
            rows_loaded += 1
            if n_rows and rows_loaded >= n_rows:
                break
    return keys, rows_loaded, per_table


def run_one(job):
    """Simulate one (policy, capacity) pair over the whole shared trace."""
    policy_cls, capacity = job
    t0 = time.process_time()
    cache = policy_cls(capacity)
    hits = [0] * N_TABLES
    for key in _KEYS:
        if cache.access(key):
            hits[key_table(key)] += 1
    return policy_cls.name, capacity, hits, cache.hits, cache.misses, time.process_time() - t0


def write_part(part_dir, name, cap, hits, per_table):
    """One CSV per (policy, capacity), written atomically as soon as it finishes."""
    slug = re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')
    path = os.path.join(part_dir, f'cap{cap}_{slug}.csv')
    with open(path + '.tmp', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['policy', 'capacity', 'table', 'hits', 'misses'])
        for t in range(N_TABLES):
            w.writerow([name, cap, t, hits[t], per_table[t] - hits[t]])
        w.writerow([name, cap, 'all', sum(hits), sum(per_table) - sum(hits)])
    os.replace(path + '.tmp', path)


def run_shared(keys, per_table, capacities, workers, policies=None, part_dir=None):
    """Returns results[cap][policy] with totals and a per_table breakdown.
    With part_dir, each (policy, capacity) is also saved to its own CSV on arrival."""
    global _KEYS
    policies = POLICIES if policies is None else policies
    _KEYS = keys
    jobs = [(p, c) for c in capacities for p in policies]
    results = {c: {} for c in capacities}

    def collect(out):
        name, cap, hits, h, m, sec = out
        assert sum(hits) == h and h + m == len(keys), f"{name}@{cap}: counts do not add up"
        if part_dir:
            write_part(part_dir, name, cap, hits, per_table)
        results[cap][name] = {
            'hits': h, 'misses': m, 'hit_rate': h / (h + m) * 100 if h + m else 0.0,
            'cpu_seconds': sec,
            'per_table': [{'table': t, 'hits': hits[t], 'misses': per_table[t] - hits[t],
                           'hit_rate': hits[t] / per_table[t] * 100 if per_table[t] else None}
                          for t in range(N_TABLES)]}

    if workers > 1:
        from multiprocessing import get_context
        with get_context('fork').Pool(processes=workers) as pool:
            for out in pool.imap_unordered(run_one, jobs, chunksize=1):
                collect(out)
    else:
        for job in jobs:
            collect(run_one(job))
    return results


def main():
    ap = argparse.ArgumentParser(description="Shared-cache trace simulator (one cache, all tables)")
    ap.add_argument('--criteo_path', required=True)
    ap.add_argument('--n_rows', type=int, default=2_000_000)
    ap.add_argument('--capacities', nargs='+', type=int, default=DEFAULT_CAPACITIES,
                    help='total cache size in vectors, shared by all tables')
    ap.add_argument('--policies', nargs='+', default=None,
                    help='policy names (default: the five of POLICIES; P9 names: see rtl_exact.P9_POLICIES)')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--output', default='results')
    ap.add_argument('--tag', default='shared_cache_results')
    args = ap.parse_args()

    by_name = {p.name: p for p in SELECTABLE}
    policies = [by_name[n] for n in args.policies] if args.policies else POLICIES

    t0 = time.time()
    keys, n_rows, per_table = load_shared_trace(args.criteo_path, args.n_rows)
    t_load = time.time() - t0
    unique = len(set(keys))
    print(f"Loaded {n_rows:,} rows, {len(keys):,} accesses, {unique:,} unique (table, id) keys "
          f"in {t_load:.1f}s", flush=True)

    part_dir = os.path.join(args.output, 'parts')
    os.makedirs(part_dir, exist_ok=True)
    t0 = time.time()
    results = run_shared(keys, per_table, args.capacities, args.workers, policies, part_dir)
    t_sweep = time.time() - t0
    print(f"Sweep finished in {t_sweep:.1f}s\n")
    names = [p.name for p in policies]
    print(f"{'capacity':>10} | " + ' | '.join(f'{n:>14.14}' for n in names))
    for c in args.capacities:
        print(f"{c:>10,} | " + ' | '.join(f"{results[c][n]['hit_rate']:13.4f}%" for n in names))

    os.makedirs(args.output, exist_ok=True)
    out = os.path.join(args.output, args.tag + '.json')
    with open(out, 'w') as f:
        json.dump({'meta': {'source': args.criteo_path, 'n_rows': n_rows,
                            'accesses': len(keys), 'unique_keys': unique,
                            'accesses_per_table': per_table,
                            'capacities': args.capacities, 'policies': names,
                            'capacity_unit': 'vectors, ONE cache shared by all 26 tables',
                            'order': 'file row order; within a row tables 0..25; '
                                     'empty/non-hex fields skipped',
                            'key': 'table << 32 | id',
                            'workers': args.workers,
                            'wall_seconds': {'load': t_load, 'sweep': t_sweep}},
                   'results': {str(k): v for k, v in results.items()}}, f, indent=2)
    print(f"\nSaved: {out}")


if __name__ == '__main__':
    main()
