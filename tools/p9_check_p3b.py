"""P9: exact reproduction check of P3b's LFU reset-on-eviction numbers by a P9 set-A run.

Usage: python -I tools/p9_check_p3b.py <P9 shared_cache_results.json> <P3b shared_cache_results.json>
Compares, for run_trace_sim.LFUResetCache ("LFU (gem5 LFURP - reset on eviction)"), at every capacity in the P3b
file: total hits and misses and the per-table hits and misses, plus the stream totals (rows, accesses, unique keys,
accesses per table). Everything must be equal. Prints one line per capacity with both hit rates (4 decimals).
Exit 0 if all equal, 1 otherwise (the set-A job then fails, so its afterok dependants do not run).
"""
import json
import sys

POLICY = 'LFU (gem5 LFURP — reset on eviction)'


def main():
    new, ref = (json.load(open(p)) for p in sys.argv[1:3])
    ok = True
    for k in ('n_rows', 'accesses', 'unique_keys', 'accesses_per_table'):
        same = new['meta'][k] == ref['meta'][k]
        ok &= same
        print(f"meta {k}: {'equal' if same else 'DIFFERENT'}"
              + ('' if k == 'accesses_per_table' else f" ({new['meta'][k]} vs P3b {ref['meta'][k]})"))
    for cap in ref['results']:
        a = new['results'].get(cap, {}).get(POLICY)
        b = ref['results'][cap][POLICY]
        if a is None:
            ok = False
            print(f"capacity {cap}: MISSING in the P9 run")
            continue
        same = (a['hits'], a['misses']) == (b['hits'], b['misses']) and \
            [(t['hits'], t['misses']) for t in a['per_table']] == [(t['hits'], t['misses']) for t in b['per_table']]
        ok &= same
        print(f"capacity {cap}: P9 {a['hit_rate']:.4f}% ({a['hits']} hits) vs P3b {b['hit_rate']:.4f}% "
              f"({b['hits']} hits); per table {'equal' if same else 'DIFFERENT'}: {'MATCH' if same else 'MISMATCH'}")
    print('P3B_CHECK ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
