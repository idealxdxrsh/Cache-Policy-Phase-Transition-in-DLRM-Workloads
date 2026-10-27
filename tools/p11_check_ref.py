"""P11 part A: exact reproduction check at 256 entries before the new 16- and 64-entry numbers are used.

Usage: python -I tools/p11_check_ref.py <P11 shared_cache_results.json> <ref dir>
<ref dir> holds the committed files of the same row count: p3b.json (results/P3b/rows_<N>/), p9A.json and p9B.json
(results/P9/cluster/rows_<N>_set<A|B>/). At capacity 256 the P11 run must equal, in total and per-table hits and
misses: LRU and LFU-reset (oldest) of P3b, RTL-exact mode 0 of P9 set A, Rotate-victim mode 0 of P9 set B. The stream
totals (rows, accesses, unique keys, accesses per table) must equal P3b's. Exit 0 if all equal, 1 otherwise (the
2M job then fails, so its afterok 10M job does not run).
"""
import json
import sys
from pathlib import Path

REFS = {'LRU': 'p3b', 'LFU (gem5 LFURP — reset on eviction)': 'p3b',
        'RTL-exact mode 0': 'p9A', 'Rotate-victim mode 0': 'p9B'}


def main():
    new = json.load(open(sys.argv[1]))
    ref = {k: json.load(open(Path(sys.argv[2]) / f'{k}.json')) for k in ('p3b', 'p9A', 'p9B')}
    ok = True
    for k in ('n_rows', 'accesses', 'unique_keys', 'accesses_per_table'):
        same = new['meta'][k] == ref['p3b']['meta'][k]
        ok &= same
        print(f"meta {k}: {'equal' if same else 'DIFFERENT'}")
    for pol, r in REFS.items():
        a = new['results'].get('256', {}).get(pol)
        b = ref[r]['results']['256'][pol]
        if a is None:
            ok = False
            print(f'{pol} 256: MISSING in the P11 run')
            continue
        same = (a['hits'], a['misses']) == (b['hits'], b['misses']) and \
            [(t['hits'], t['misses']) for t in a['per_table']] == [(t['hits'], t['misses']) for t in b['per_table']]
        ok &= same
        print(f"{pol} 256: P11 {a['hits']} hits / {a['misses']} misses vs {r} {b['hits']} / {b['misses']}; "
              f"per table {'equal' if same else 'DIFFERENT'}: {'MATCH' if same else 'MISMATCH'}")
    print('P11_REF_CHECK ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
