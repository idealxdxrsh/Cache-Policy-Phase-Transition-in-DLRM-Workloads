"""P9: hit counts of the LFU-reset ablations, RTL-exact and the candidate tie-break rules on the P8 Criteo slices.

Usage: python -I tools/p9_slices.py            (after tools/p9_validate.py)
Request sets, all from a cold start, slices results/P8/stimulus/{row0,row1M}.hex (P8's exact files):
  full : all 200,000 requests of each slice, at 16, 64 and 256 entries (the RTL depths);
  p8   : the first R requests of each P8 RTL run (R from results/P9/validate/validate.json, p8budget runs, whose
         summary lines equal P8's), at that run's depth; the RTL's hits on them are in validate.json.
Policies: LRU and LFU-reset (oldest) are run_trace_sim.LRUCache and LFUResetCache, unchanged; the rest are
trace_sim/rtl_exact.py. Gap decomposition (hits): G = LFU-reset (oldest) - RTL-exact mode 0;
tie = LFU-reset (oldest) - lowest-slot; sat = LFU-reset (oldest) - 6-bit; interaction = G - tie - sat.
Also, per policy on the full slices: evictions, and how many of them evict the line installed by the previous
miss (the line has had no other miss in between in which to be evicted).
Synthetic probe (not Criteo): 60 random Zipf traces (seeds 0..59, 20,000 requests, capacity 4/8/16/64, 2/10/50 keys
per line, alpha 0.6/0.9/1.2), mode-0 candidates vs LFU-reset (oldest): whether their hit counts are equal.
Writes results/P9/slices/slices.json.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'trace_sim'))
from run_trace_sim import LRUCache, LFUResetCache  # noqa: E402
import rtl_exact as rx  # noqa: E402

P9, P8 = ROOT / 'results' / 'P9', ROOT / 'results' / 'P8'
SLICES = ('row0', 'row1M')
DEPTHS = (16, 64, 256)
POLICIES = [('LRU', LRUCache), ('LFU-reset (oldest)', LFUResetCache)] + \
           [(p.name, p) for p in rx.ABLATIONS + rx.RTL_EXACT + rx.CANDIDATES]


def resident(c, key):
    return key in (c.slot_of if hasattr(c, 'slot_of') else c.cache)


def run(cls, cap, addrs, newest_evicted=False):
    c = cls(cap)
    prev, ev_newest = None, 0
    for a in addrs:
        if not c.access(a):
            if newest_evicted and prev is not None and c.misses > cap and not resident(c, prev):
                ev_newest += 1
            prev = a
    out = {'hits': c.hits, 'misses': c.misses}
    if newest_evicted:
        out['evictions'] = max(0, c.misses - cap)
        out['evicted_previous_install'] = ev_newest
    return out


def decompose(h):
    g = h['LFU-reset (oldest)'] - h['RTL-exact mode 0']
    tie = h['LFU-reset (oldest)'] - h['LFU-reset lowest-slot']
    sat = h['LFU-reset (oldest)'] - h['LFU-reset 6-bit']
    return {'gap_oldest_minus_rtl_m0': g, 'tie_alone': tie, 'saturation_alone': sat,
            'interaction': g - tie - sat, 'mode1_minus_mode0': h['RTL-exact mode 1'] - h['RTL-exact mode 0']}


def main():
    val = {r['run']: r for r in json.loads((P9 / 'validate' / 'validate.json').read_text())}
    addrs = {s: [int(x, 16) for x in (P8 / 'stimulus' / f'{s}.hex').read_text().split()] for s in SLICES}
    out = {'full': [], 'p8': []}
    for s in SLICES:
        for d in DEPTHS:
            res = {name: run(cls, d, addrs[s], newest_evicted=True) for name, cls in POLICIES}
            h = {k: v['hits'] for k, v in res.items()}
            rtl = {m: val[f'd{d}_m{m}_{s}_full']['rtl_hits'] for m in (0, 1)}
            assert rtl[0] == h['RTL-exact mode 0'] and rtl[1] == h['RTL-exact mode 1'], (s, d)
            assert h['LFU-reset lowest-slot 6-bit'] == h['RTL-exact mode 0'], (s, d)
            out['full'].append({'slice': s, 'depth': d, 'requests': len(addrs[s]), 'rtl_hits': rtl,
                                'policies': res, 'decomposition': decompose(h)})
            print(s, d, json.dumps(h), json.dumps(out['full'][-1]['decomposition']), flush=True)
    for s in SLICES:
        for d in DEPTHS:
            for m in (0, 1):
                v = val[f'd{d}_m{m}_{s}_p8budget']
                assert v['p8_line_identical'], v['run']
                req = addrs[s][:v['requests']]
                h = {name: run(cls, d, req)['hits'] for name, cls in POLICIES}
                assert h[f'RTL-exact mode {m}'] == v['rtl_hits'], v['run']
                out['p8'].append({'slice': s, 'depth': d, 'mode': m, 'requests': v['requests'],
                                  'rtl_hits': v['rtl_hits'], 'hits': h, 'decomposition': decompose(h)})
    probe = []
    for seed in range(60):
        rng = random.Random(seed)
        cap = rng.choice([4, 8, 16, 64])
        nk = cap * rng.choice([2, 10, 50])
        alpha = rng.choice([0.6, 0.9, 1.2])
        keys = rng.choices(range(nk), weights=[1 / r ** alpha for r in range(1, nk + 1)], k=20000)
        h = {name: run(cls, cap, keys)['hits'] for name, cls in POLICIES
             if name == 'LFU-reset (oldest)' or name.endswith('mode 0') and not name.startswith('RTL')}
        probe.append({'seed': seed, 'capacity': cap, 'keys': nk, 'alpha': alpha, 'hits': h})
    out['synthetic_probe'] = {
        'traces': len(probe),
        'differ_from_oldest': {n: sum(r['hits'][n] != r['hits']['LFU-reset (oldest)'] for r in probe)
                               for n in probe[0]['hits'] if n != 'LFU-reset (oldest)'},
        'runs': probe}
    print('synthetic probe, traces differing from LFU-reset (oldest):', out['synthetic_probe']['differ_from_oldest'])
    (P9 / 'slices').mkdir(parents=True, exist_ok=True)
    (P9 / 'slices' / 'slices.json').write_text(json.dumps(out, indent=1) + '\n')
    print('written', P9 / 'slices' / 'slices.json')


if __name__ == '__main__':
    main()
