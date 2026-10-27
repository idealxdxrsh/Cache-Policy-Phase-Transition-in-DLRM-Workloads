"""P9: request-by-request check of the RTL-exact models against the RTL's hit_flag.

Usage: python -I tools/p9_validate.py [workers, default 4]
For every run in results/P9/rtl/ (synthesis/p9/run_p9.sh: depths 16/64/256, modes 0/1, slices row0/row1M; kind
p8budget = P8's cycle budget, kind full = all 200,000 requests), the hit log `<index> <address> <hit_flag>` is
checked line by line against the slice file (results/P8/stimulus/<slice>.hex: index i must be request i with
the same address) and against two models run from a cold start on the same requests:
trace_sim/rtl_exact.RTLExactCache (fast) and RTLStructuralModel (literal, 16 groups as the RTL default).
Any mismatch is reported with its first request index. For p8budget runs the summary line `p8_power ...` must
equal the one in results/P8/sim/d<D>_m<M>_criteo_<slice>_rtl_w<warm>_n10000.txt character for character.
Writes results/P9/validate/validate.json and prints one line per run.
"""
import gzip
import json
import re
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'trace_sim'))
from rtl_exact import RTLExactCache, RTLStructuralModel  # noqa: E402

P9, P8 = ROOT / 'results' / 'P9', ROOT / 'results' / 'P8'


def p8_line(path):
    return next((l for l in Path(path).read_text().splitlines() if l.startswith('p8_power')), None)


def check(run_txt):
    run_txt = Path(run_txt)
    run = run_txt.name[:-4]
    d, m, sl, kind = re.fullmatch(r'd(\d+)_m(\d)_(row0|row1M)_(p8budget|full)', run).groups()
    d, m = int(d), int(m)
    hex_addrs = [int(x, 16) for x in (P8 / 'stimulus' / f'{sl}.hex').read_text().split()]
    log = [l.split() for l in gzip.open(P9 / 'rtl' / f'{run}.hits.gz', 'rt').read().splitlines()]
    idx = [int(a) for a, _, _ in log]
    addrs = [int(b, 16) for _, b, _ in log]
    rtl = [c == '1' for _, _, c in log]
    out = {'run': run, 'depth': d, 'mode': m, 'slice': sl, 'kind': kind, 'requests': len(log),
           'rtl_hits': sum(rtl),
           'indices_consecutive': idx == list(range(len(log))),
           'addresses_equal_slice': addrs == hex_addrs[:len(log)]}
    for name, model in (('fast', RTLExactCache(d, m)), ('structural', RTLStructuralModel(d, m))):
        sim = [model.access(a) for a in addrs]
        diff = [i for i in range(len(sim)) if sim[i] != rtl[i]]
        out[f'{name}_hits'] = sum(sim)
        out[f'{name}_mismatches'] = len(diff)
        out[f'{name}_first_mismatch'] = diff[0] if diff else None
    line = p8_line(run_txt)
    out['summary_line'] = line
    if kind == 'p8budget':
        warm = 100000 if d == 256 else 20000
        ref = p8_line(P8 / 'sim' / f'd{d}_m{m}_criteo_{sl}_rtl_w{warm}_n10000.txt')
        out['p8_line_identical'] = line == ref
    else:
        out['all_slice_requests'] = len(log) == len(hex_addrs)
    out['pass'] = (out['indices_consecutive'] and out['addresses_equal_slice'] and out['fast_mismatches'] == 0
                   and out['structural_mismatches'] == 0
                   and out.get('p8_line_identical', out.get('all_slice_requests')) is True)
    return out


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    runs = sorted((P9 / 'rtl').glob('d*_m*_row*_*.txt'))
    with Pool(workers) as pool:
        res = pool.map(check, runs, chunksize=1)
    res.sort(key=lambda r: (r['kind'] != 'p8budget', r['depth'], r['mode'], r['slice']))
    (P9 / 'validate').mkdir(parents=True, exist_ok=True)
    (P9 / 'validate' / 'validate.json').write_text(json.dumps(res, indent=1) + '\n')
    for r in res:
        print(f"{r['run']:24s} requests={r['requests']:>6} rtl_hits={r['rtl_hits']:>6} fast={r['fast_hits']:>6} "
              f"structural={r['structural_hits']:>6} mismatches fast/structural={r['fast_mismatches']}/"
              f"{r['structural_mismatches']} addresses_ok={r['addresses_equal_slice']} "
              f"{'p8_line_identical' if r['kind'] == 'p8budget' else 'all_slice_requests'}="
              f"{r.get('p8_line_identical', r.get('all_slice_requests'))} pass={r['pass']}")
    print(f"{sum(r['pass'] for r in res)}/{len(res)} runs pass")
    return 0 if all(r['pass'] for r in res) else 1


if __name__ == '__main__':
    sys.exit(main())
