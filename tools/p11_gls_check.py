"""P11 part B: check the gate-level slice lockstep runs (cluster/jobs/p11_gls.sbatch, synthesis/p11/tb_gls_slice.sv).

Usage: python -I tools/p11_gls_check.py   (writes results/P11/gls.json, prints one line per run)
For each of the 12 netlists (results/P11/synth/netlists.sha256) x slices row0, row1M, reads
results/P11/cluster/gls/results/<run>_<slice>.txt and checks: GLS SLICE LOCKSTEP PASSED, 0 mismatching cycles on
all 5 outputs, 0 X cycles on both designs, all 200,000 requests replayed, the netlist sha256 equal to the local one,
and the RTL hit log sha256 equal to P10's v3 RTL hit log of the same depth, mode and slice
(results/P10/rtl/d<D>_m<M>_<slice>_full.txt), so the RTL side replays exactly P10's lockstep run.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P11 = ROOT / 'results' / 'P11'


def grab(pat, text, cast=str):
    m = re.search(pat, text, re.M)
    return cast(m.group(1)) if m else None


def main():
    sha = dict(ln.split()[::-1] for ln in (P11 / 'synth' / 'netlists.sha256').read_text().splitlines())
    res = []
    for d in (16, 64, 256):
        for m in (0, 1):
            for f in (1000, 500):
                run = f'd{d}_m{m}_{f}MHz'
                for sl in ('row0', 'row1M'):
                    p = P11 / 'cluster' / 'gls' / 'results' / f'{run}_{sl}.txt'
                    r = {'run': run, 'slice': sl, 'file': str(p.relative_to(ROOT)), 'exists': p.exists()}
                    if p.exists():
                        t = p.read_text()
                        s = grab(r'^(gls_slice .*)$', t)
                        kv = dict(x.split('=') for x in s.split()[1:]) if s else {}
                        p10 = (ROOT / 'results' / 'P10' / 'rtl' / f'd{d}_m{m}_{sl}_full.txt').read_text()
                        r.update({k: int(v) for k, v in kv.items()})
                        r['passed_line'] = 'GLS SLICE LOCKSTEP PASSED' in t
                        r['netlist_sha_ok'] = grab(r'^netlist sha256: (\w+)', t) == sha[f'{run}/netlist.v']
                        r['hitlog_equals_p10'] = grab(r'^hitlog: lines \d+ sha256 (\w+)', t) == \
                            grab(r'^hitlog: lines \d+ sha256 (\w+)', p10)
                        r['vvp_wall'] = grab(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (\S+)', t.split('== run')[-1])
                        r['job'] = grab(r'^job (\S+)', t)
                        r['host'] = grab(r'^job \S+ host (\S+)', t)
                    r['pass'] = bool(r['exists'] and r.get('passed_line') and r.get('mismatching_cycles') == 0
                                     and r.get('x_cycles_netlist') == 0 and r.get('x_cycles_rtl') == 0
                                     and r.get('requests') == 200000 and r.get('netlist_sha_ok')
                                     and r.get('hitlog_equals_p10'))
                    res.append(r)
                    print(f"{run:16s} {sl:6s} " + (f"cycles={r.get('cycles')} requests={r.get('requests')} hits={r.get('hits')} "
                          f"gl_hits={r.get('gl_hits')} mismatching_cycles={r.get('mismatching_cycles')} "
                          f"x={r.get('x_cycles_netlist')}/{r.get('x_cycles_rtl')} netlist_sha_ok={r.get('netlist_sha_ok')} "
                          f"hitlog_equals_p10={r.get('hitlog_equals_p10')} vvp={r.get('vvp_wall')}" if r['exists'] else 'MISSING')
                          + f" pass={r['pass']}")
    (P11 / 'gls.json').write_text(json.dumps(res, indent=1) + '\n')
    print(f"{sum(r['pass'] for r in res)}/{len(res)} runs pass")
    return 0 if all(r['pass'] for r in res) else 1


if __name__ == '__main__':
    sys.exit(main())
