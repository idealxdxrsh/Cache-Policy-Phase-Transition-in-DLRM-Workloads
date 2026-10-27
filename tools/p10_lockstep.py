"""P10: request-by-request lockstep check of rtl/v3 against the trace simulator.

Usage: python -I tools/p10_lockstep.py [workers, default 4]
For every run in results/P10/rtl/ (rtl/v3/run_p10.sh: depths 16/64/256, modes 0/1, slices row0/row1M, all
200,000 requests), the hit log `<index> <address> <hit_flag>` is checked against the slice file
(results/P8/stimulus/<slice>.hex) and against a cold-start model on the same requests:
  mode 0: trace_sim/rtl_exact.Rotate_victim_mode_0 (RotatingTieCache, advance 'victim'; the class used for the
          P9 set-B results). RTLExactCache mode 0 (the v2 rule) is run too, for its hit count only.
  mode 1: RTLExactCache mode 1, and the hit log must equal P9's rtl-v2-final log of the same run
          (results/P9/rtl/<run>.hits.gz) line for line.
Also replays TEST 8 of rtl/v3/tb_lfu_cache.sv through Rotate_victim_mode_0 and checks the victim slots.
Writes results/P10/lockstep.json and prints one line per run.
"""
import gzip
import json
import re
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'trace_sim'))
from rtl_exact import RTLExactCache, Rotate_victim_mode_0  # noqa: E402

P10, P9, P8 = ROOT / 'results' / 'P10', ROOT / 'results' / 'P9', ROOT / 'results' / 'P8'


def read_log(path):
    return [l.split() for l in gzip.open(path, 'rt').read().splitlines()]


def run_model(model, addrs, rtl):
    sim = [model.access(a) for a in addrs]
    diff = [i for i in range(len(sim)) if sim[i] != rtl[i]]
    return {'hits': sum(sim), 'misses': len(sim) - sum(sim), 'mismatches': len(diff),
            'first_mismatch': diff[0] if diff else None}


def check(run_txt):
    run = Path(run_txt).name[:-4]
    d, m, sl = re.fullmatch(r'd(\d+)_m(\d)_(row0|row1M)_full', run).groups()
    d, m = int(d), int(m)
    hex_addrs = [int(x, 16) for x in (P8 / 'stimulus' / f'{sl}.hex').read_text().split()]
    log = read_log(P10 / 'rtl' / f'{run}.hits.gz')
    addrs = [int(b, 16) for _, b, _ in log]
    rtl = [c == '1' for _, _, c in log]
    out = {'run': run, 'depth': d, 'mode': m, 'slice': sl, 'requests': len(log),
           'rtl_hits': sum(rtl), 'rtl_misses': len(rtl) - sum(rtl),
           'indices_consecutive': [int(a) for a, _, _ in log] == list(range(len(log))),
           'addresses_equal_slice': addrs == hex_addrs,
           'summary_line': next((l for l in Path(run_txt).read_text().splitlines()
                                 if l.startswith('p8_power')), None)}
    if m == 0:
        out['model'] = 'Rotate-victim mode 0'
        out['sim'] = run_model(Rotate_victim_mode_0(d), addrs, rtl)
        out['v2_rule_hits'] = run_model(RTLExactCache(d, 0), addrs, rtl)['hits']
        ok = True
    else:
        out['model'] = 'RTL-exact mode 1'
        out['sim'] = run_model(RTLExactCache(d, 1), addrs, rtl)
        out['equals_p9_v2_log'] = log == read_log(P9 / 'rtl' / f'{run}.hits.gz')
        ok = out['equals_p9_v2_log']
    out['pass'] = bool(ok and out['indices_consecutive'] and out['addresses_equal_slice']
                       and out['sim']['mismatches'] == 0 and out['summary_line'] is not None)
    return out


def tb8_victims(n):
    """TEST 8 of rtl/v3/tb_lfu_cache.sv through the simulator; returns the slot of each new tag."""
    c = Rotate_victim_mode_0(n)
    cand = {2, 3, 5, n - 1}
    for i in range(n):
        c.access(0xD0000 + i)
    for i in range(n):
        if i not in cand:
            c.access(0xD0000 + i)
    victims = []
    for j in range(6):
        c.access(0xE0000 + j)
        victims.append(c.slot_of[0xE0000 + j])
    return victims


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    runs = sorted((P10 / 'rtl').glob('d*_m*_row*_full.txt'))
    with Pool(workers) as pool:
        res = pool.map(check, runs, chunksize=1)
    res.sort(key=lambda r: (r['mode'], r['depth'], r['slice']))
    tb8 = {n: tb8_victims(n) for n in (16, 64, 256)}
    tb8_ok = all(v == [2, 3, 5, n - 1, 2, 3] for n, v in tb8.items())
    (P10 / 'lockstep.json').write_text(json.dumps({'runs': res, 'tb8_model_victims': tb8,
                                                   'tb8_model_equals_tb': tb8_ok}, indent=1) + '\n')
    for r in res:
        s = r['sim']
        extra = (f"v2_rule_hits={r['v2_rule_hits']}" if r['mode'] == 0
                 else f"equals_p9_v2_log={r['equals_p9_v2_log']}")
        print(f"{r['run']:20s} requests={r['requests']} rtl hits/misses={r['rtl_hits']}/{r['rtl_misses']} "
              f"{r['model']} hits/misses={s['hits']}/{s['misses']} mismatches={s['mismatches']} "
              f"first={s['first_mismatch']} addresses_ok={r['addresses_equal_slice']} {extra} pass={r['pass']}")
    print(f"TEST 8 through the simulator: {tb8} equals tb expectation: {tb8_ok}")
    print(f"{sum(r['pass'] for r in res)}/{len(res)} runs pass")
    return 0 if all(r['pass'] for r in res) and tb8_ok and len(res) == 12 else 1


if __name__ == '__main__':
    sys.exit(main())
