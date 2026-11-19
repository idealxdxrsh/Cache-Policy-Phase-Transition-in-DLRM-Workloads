"""Fig.: one cache shared by all 26 tables, total hit rate vs size for LRU, LFU-reset (oldest-first ties), the v2 rule
(RTL-exact mode 0, lowest-slot ties) and the v3 rule (Rotate-victim mode 0); 10M rows solid, 2M rows dashed.

Reads (committed files only):
  16 and 64 entries:        results/P11/cluster/rows_<N>/parts/cap{16,64}_*.csv            (P11 part A)
  256 .. 100,000 entries:   results/P3b/rows_<N>/parts/*.csv (LRU, LFU-reset)                (P3b)
                            results/P9/cluster/rows_<N>_setA/parts/*RTL_exact_mode_0.csv      (P9 set A, v2 rule)
                            results/P9/cluster/rows_<N>_setB/parts/*Rotate_victim_mode_0.csv  (P9 set B, v3 rule)
P11 reran 256 entries and its ref_check.txt says the counts equal P3b / P9 exactly, so 256 is taken from P3b / P9.
"""
from collections import defaultdict

from style import SINGLE, files, plt, rows, save

SERIES = {   # policy name in the CSVs -> (label, colour, marker)
    'LRU': ('LRU', '#000000', 'o'),
    'LFU (gem5 LFURP — reset on eviction)': ('LFU-reset, oldest-first ties', '#0072B2', 's'),
    'RTL-exact mode 0': ('v2 rule (lowest slot)', '#D55E00', '^'),
    'Rotate-victim mode 0': ('v3 rule (Rotate-victim)', '#009E73', 'D'),
}


def totals(n):
    srcs = [p for p in files(f'results/P11/cluster/rows_{n}/parts/') if p.split('/')[-1].split('_')[0] in ('cap16', 'cap64')]
    srcs += files(f'results/P3b/rows_{n}/parts/')
    srcs += [p for p in files(f'results/P9/cluster/rows_{n}_setA/parts/') if p.endswith('RTL_exact_mode_0.csv')]
    srcs += [p for p in files(f'results/P9/cluster/rows_{n}_setB/parts/') if p.endswith('Rotate_victim_mode_0.csv')]
    tot = defaultdict(lambda: [0, 0])
    for p in srcs:
        for r in rows(p):
            if not r['table'].isdigit():
                continue
            k = (r['policy'], int(r['capacity']))
            tot[k][0] += int(r['hits'])
            tot[k][1] += int(r['misses'])
    return tot


fig, ax = plt.subplots(figsize=(SINGLE, 2.25))
for n, dashed in ((10000000, False), (2000000, True)):
    tot = totals(n)
    for pol, (lab, col, mk) in SERIES.items():
        caps = sorted(c for q, c in tot if q == pol)
        if caps != [16, 64, 256, 1000, 10000, 100000]:
            raise SystemExit(f'{pol} {n}: capacities {caps}')
        y = [tot[pol, c][0] / sum(tot[pol, c]) * 100 for c in caps]
        wide = pol.startswith('LFU')     # drawn wide and underneath: the v3 rule lies on it (equal at 16-256 entries)
        ax.plot(caps, y, color='#9ecae1' if wide else col, marker=mk, ls='--' if dashed else '-',
                lw=(2.6 if wide else 0.8 if dashed else 1.0), ms=7 if wide else 4,
                mfc='white' if dashed else ('#9ecae1' if wide else col), label=None if dashed else lab,
                zorder=1 if wide else (2 if dashed else 3))
ax.set_xscale('log')
ax.set_xlabel('Shared cache size (entries, all 26 tables)')
ax.set_ylabel('Hit rate (%)')
ax.set_xticks([16, 64, 256, 1000, 10000, 100000], ['16', '64', '256', '1,000', '10,000', '100,000'])
ax.minorticks_off()
ax.set_ylim(0, 100)
h, lab = ax.get_legend_handles_labels()
h.append(plt.Line2D([], [], color='0.3', ls='-'))
lab.append('10M rows (solid)')
h.append(plt.Line2D([], [], color='0.3', ls='--', marker='o', mfc='white'))
lab.append('2M rows (dashed, open)')
ax.legend(h, lab, loc='upper left', ncol=1, handlelength=2.2)
save(fig, 'fig_tiebreak')
