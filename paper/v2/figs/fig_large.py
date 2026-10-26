"""Fig. (b): per-table caches, the five large tables combined (unique ids >= 150,000 at both row counts, as in
tools/p3_analysis.py), hit rate by policy at 64 / 256 / 1,000 / 10,000 vectors per table, 10M rows.

Reads results/P3/rows_10000000/figs/hit_rates.csv and results/P3/rows_{2000000,10000000}/figs/zipf_per_table.csv.
"""
import numpy as np

from style import POLICY, SINGLE, plt, rows, save

LARGE_MIN, N, CAPS = 150000, 10000000, (64, 256, 1000, 10000)
uniq = {n: {r['table']: int(r['unique']) for r in rows(f'results/P3/rows_{n}/figs/zipf_per_table.csv')}
        for n in (2000000, 10000000)}
large = sorted((t for t in uniq[N] if all(u[t] >= LARGE_MIN for u in uniq.values())), key=int)
hm = {}
for r in rows(f'results/P3/rows_{N}/figs/hit_rates.csv'):
    if r['table'] in large:
        k = (r['policy'], int(r['capacity']))
        h, m = hm.get(k, (0, 0))
        hm[k] = (h + int(r['hits']), m + int(r['misses']))

fig, ax = plt.subplots(figsize=(SINGLE, 2.2))
pols = list(POLICY)
w = 0.8 / len(pols)
x = np.arange(len(CAPS))
for i, pol in enumerate(pols):
    lab, col, _, _, hatch = POLICY[pol]
    y = [hm[pol, c][0] / sum(hm[pol, c]) * 100 for c in CAPS]
    ax.bar(x - 0.4 + w * (i + 0.5), y, w, color=col if hatch or pol == 'LRU' else 'white',
           edgecolor='black' if pol != 'LRU' else 'black', hatch=hatch, lw=0.4, label=lab)
ax.set_xticks(x, [f'{c:,}' for c in CAPS])
ax.set_xlabel('Cache capacity per table (vectors)')
ax.set_ylabel('Hit rate, large tables (%)')
ax.legend(ncol=2, loc='upper left', handlelength=1.6, columnspacing=0.8)
ax.set_ylim(0, 100)
save(fig, 'fig_large')
print('large tables:', ', '.join(large))
