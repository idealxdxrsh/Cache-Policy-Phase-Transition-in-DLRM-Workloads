#!/usr/bin/env python3
"""P14 prep (CPU): row-aligned Criteo index stream for GPU EmbeddingBag profiling.

The P3 dumps (data/p3/traces_<N>/table_XX.u32) hold each table's ids in row order but skip
empty fields, so the row of each lookup is lost. This script parses the first N rows of
train.txt with the same rule as P3 / P3b (trace_sim/run_trace_sim.py, run_shared_cache.py:
field stripped and non-empty, int(x, 16), ValueError -> no access), keeps the row position
(-1 = no access), and CHECKS that every table's non-missing sequence equals the P3 dump
exactly. Ids are then mapped per table to dense rows 0..n_t-1 (np.unique order).

Output (--out): stream.npz with dense [N, 26] int32 (-1 = no access) and card [26] int64;
check.json with per-table accesses, unique ids, dump equality, totals.
"""
import argparse
import csv
import json
import os
import sys

import numpy as np

N_TABLES = 26


def parse(path, n_rows):
    raw = np.full((n_rows, N_TABLES), -1, dtype=np.int64)
    cat_cols = list(range(14, 14 + N_TABLES))
    delimiter = ',' if path.endswith('.csv') else '\t'
    r = 0
    with open(path, 'r', buffering=1 << 20) as f:
        for row in csv.reader(f, delimiter=delimiter):
            if not row:
                continue
            for t, col in enumerate(cat_cols):
                if col < len(row) and row[col].strip():
                    try:
                        raw[r, t] = int(row[col], 16)
                    except ValueError:
                        pass
            r += 1
            if r >= n_rows:
                break
    if r != n_rows:
        raise SystemExit(f'only {r} rows in {path}')
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--criteo_path', required=True)
    ap.add_argument('--dump_dir', required=True, help='P3 traces_<N> directory')
    ap.add_argument('--n_rows', type=int, default=2_000_000)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    raw = parse(a.criteo_path, a.n_rows)
    with open(os.path.join(a.dump_dir, 'meta.json')) as f:
        meta = json.load(f)
    dense = np.full(raw.shape, -1, dtype=np.int32)
    card = np.zeros(N_TABLES, dtype=np.int64)
    tables, ok = [], True
    for t in range(N_TABLES):
        m = raw[:, t] >= 0
        ids = raw[m, t]
        dump = np.fromfile(os.path.join(a.dump_dir, f'table_{t:02d}.u32'), dtype=np.uint32).astype(np.int64)
        eq = bool(len(dump) == len(ids) and np.array_equal(dump, ids))
        ok &= eq and len(ids) == meta['accesses'][t]
        uniq, inv = np.unique(ids, return_inverse=True)
        dense[m, t] = inv.astype(np.int32)
        card[t] = len(uniq)
        tables.append({'table': t, 'accesses': int(m.sum()), 'unique': int(len(uniq)), 'equals_p3_dump': eq})
    res = {'criteo_path': a.criteo_path, 'dump_dir': a.dump_dir, 'n_rows': a.n_rows,
           'total_accesses': int(sum(x['accesses'] for x in tables)),
           'total_unique_table_id': int(card.sum()), 'all_tables_equal_p3_dump': ok, 'tables': tables}
    np.savez(os.path.join(a.out, 'stream.npz'), dense=dense, card=card)
    with open(os.path.join(a.out, 'check.json'), 'w') as f:
        json.dump(res, f, indent=1)
    print(f"P14_PREP rows={a.n_rows} accesses={res['total_accesses']} unique={res['total_unique_table_id']} "
          f"all_tables_equal_p3_dump={ok}")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
