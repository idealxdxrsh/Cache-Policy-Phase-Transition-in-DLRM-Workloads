"""P9: projected CPU time of the full-trace jobs from measured run times (not a measurement of the jobs).

Usage: python -I tools/p9_sizing.py
Basis: per (policy, capacity), the CPU seconds measured locally on the 200,000-row synthetic trace
(results/P9/timing_200k/shared_200k_synthetic.json, trace_sim/run_shared_cache.py, 4 workers) divided by the
local CPU seconds of LFU reset-on-eviction (run_trace_sim.LFUResetCache) in the same run, times the CPU seconds
P3b measured for LFUResetCache on the real 2M / 10M traces at that capacity (results/P3b/rows_*/...json).
Set A: RTL-exact modes 0/1, the three ablations, LFUResetCache again (reproduction check against P3b).
Set B: the six candidate tie-break rules. Writes results/P9/jobs/sizing.json.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
L = 'LFU (gem5 LFURP — reset on eviction)'
SET_A = [L, 'RTL-exact mode 0', 'RTL-exact mode 1', 'LFU-reset lowest-slot', 'LFU-reset 6-bit',
         'LFU-reset lowest-slot 6-bit']
SET_B = [f'{r} mode {m}' for r in ('Rotate-victim', 'Rotate-step', 'Young-bit') for m in (0, 1)]


def main():
    t = json.loads((ROOT / 'results/P9/timing_200k/shared_200k_synthetic.json').read_text())['results']
    out = {}
    for rows in ('2000000', '10000000'):
        p3 = json.loads((ROOT / f'results/P3b/rows_{rows}/shared_cache_results.json').read_text())
        for name, pols in (('A', SET_A), ('B', SET_B)):
            proj = {f'{p}@{c}': t[c][p]['cpu_seconds'] / t[c][L]['cpu_seconds'] * p3['results'][c][L]['cpu_seconds']
                    for c in t for p in pols}
            out[f'{name}_{rows}'] = {'tasks': len(proj), 'cpu_seconds_total': sum(proj.values()),
                                     'cpu_seconds_longest_task': max(proj.values()),
                                     'p3b_load_seconds': p3['meta']['wall_seconds']['load'],
                                     'per_task': proj}
            o = out[f'{name}_{rows}']
            print(f"set {name} rows {rows}: {o['tasks']} tasks, projected CPU {o['cpu_seconds_total']:.0f} s total, "
                  f"longest task {o['cpu_seconds_longest_task']:.0f} s; on 4 workers >= "
                  f"{max(o['cpu_seconds_total'] / 4, o['cpu_seconds_longest_task']) / 60:.1f} min + load "
                  f"{o['p3b_load_seconds']:.0f} s (P3b)")
    (ROOT / 'results/P9/jobs/sizing.json').write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
