"""Fig. (a): one cache shared by all 26 tables, total hit rate vs capacity, every policy; 10M rows solid, 2M dashed.

Reads results/P3b/rows_{2000000,10000000}/parts/*.csv (P3b, jobs 413067 and 413106).
"""
from collections import defaultdict

from style import POLICY, SINGLE, files, plt, rows, save

fig, ax = plt.subplots(figsize=(SINGLE, 2.3))
for n, dashed in ((10000000, False), (2000000, True)):
    tot = defaultdict(lambda: [0, 0])
    for p in files(f'results/P3b/rows_{n}/parts/'):
        for r in rows(p):
            if r['table'] == 'all':                   # the 'all' row repeats the per-table sums
                continue
            k = (r['policy'], int(r['capacity']))
            tot[k][0] += int(r['hits'])
            tot[k][1] += int(r['misses'])
    for pol in POLICY:
        caps = sorted(c for q, c in tot if q == pol)
        if not caps:
            continue
        lab, col, mk, _, _ = POLICY[pol]
        y = [tot[pol, c][0] / sum(tot[pol, c]) * 100 for c in caps]
        ax.plot(caps, y, color=col, marker=mk, ls='--' if dashed else '-', lw=0.8 if dashed else 1.0,
                mfc='white' if dashed else col, label=None if dashed else lab, zorder=2 if dashed else 3)
ax.set_xscale('log')
ax.set_xlabel('Shared cache capacity (vectors, all 26 tables)')
ax.set_ylabel('Hit rate (%)')
ax.set_xticks([256, 1000, 10000, 100000], ['256', '1,000', '10,000', '100,000'])
ax.minorticks_off()
h, lab = ax.get_legend_handles_labels()
h.append(plt.Line2D([], [], color='0.3', ls='-'))
lab.append('10M rows (solid)')
h.append(plt.Line2D([], [], color='0.3', ls='--', marker='o', mfc='white'))
lab.append('2M rows (dashed, open)')
ax.legend(h, lab, loc='lower right', ncol=1, handlelength=2.2)
save(fig, 'fig_shared')
