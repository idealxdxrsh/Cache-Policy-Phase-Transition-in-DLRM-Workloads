#!/usr/bin/env python3
"""
Merge per-table result files written by run_trace_sim.py --tables ... into
one results JSON with the same layout as a single all-tables run.

Usage:
    python3 merge_results.py --output results/trace_sim_results.json parts/table_*.json

Refuses to merge if the parts disagree on source, row count, capacities or
policies, or if a table appears twice.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_trace_sim import aggregate          # noqa: E402


def merge(parts):
    keys = ('source', 'n_rows', 'capacities', 'policies')
    ref = parts[0]['meta']
    per_table, tables, seen = {}, [], set()
    cpu, wall = {}, []
    for p in parts:
        m = p['meta']
        for k in keys:
            if m[k] != ref[k]:
                raise ValueError(f"parts disagree on {k}: {m[k]!r} vs {ref[k]!r}")
        dup = seen & set(m['tables'])
        if dup:
            raise ValueError(f"table(s) {sorted(dup)} appear in more than one part")
        seen |= set(m['tables'])
        tables += p['tables']
        for name, sec in m['cpu_seconds_per_policy'].items():
            cpu[name] = cpu.get(name, 0.0) + sec
        wall.append({'tables': m['tables'], 'workers': m['workers'], **m['wall_seconds']})
        for cap, pols in p['results'].items():
            for name, r in pols.items():
                d = per_table.setdefault(int(cap), {}).setdefault(name, {})
                for t in r['per_table']:
                    d[t['table']] = (t['hits'], t['misses'])
    results = aggregate(per_table)
    tables.sort(key=lambda t: t['table'])
    meta = {k: ref[k] for k in keys}
    meta.update({'tables': sorted(seen), 'capacity_unit': ref['capacity_unit'],
                 'cpu_seconds_per_policy': cpu, 'parts_wall_seconds': wall,
                 'merged_from': len(parts)})
    return {'meta': meta, 'tables': tables,
            'results': {str(c): v for c, v in sorted(results.items())}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--output', required=True)
    ap.add_argument('--expect_tables', type=int, default=None,
                    help='fail unless exactly this many tables were merged')
    ap.add_argument('parts', nargs='+')
    args = ap.parse_args()
    parts = []
    for path in args.parts:
        with open(path) as f:
            parts.append(json.load(f))
    out = merge(parts)
    n = len(out['meta']['tables'])
    if args.expect_tables is not None and n != args.expect_tables:
        sys.exit(f"merged {n} tables, expected {args.expect_tables}")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"merged {len(parts)} parts, {n} tables -> {args.output}")


if __name__ == '__main__':
    main()
