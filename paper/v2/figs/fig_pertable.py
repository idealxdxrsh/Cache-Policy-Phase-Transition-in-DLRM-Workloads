"""Fig. (c): per-table caches of 256 vectors; hit-rate difference to LRU (percentage points) for both LFU
variants, per table, 2M rows (open markers) and 10M rows (filled).

Reads results/P3/rows_{2000000,10000000}/figs/hit_rates.csv.
"""
from style import POLICY, SINGLE, plt, rows, save

PERS, RESET = 'LFU (persistent counters)', 'LFU (gem5 LFURP — reset on eviction)'
fig, ax = plt.subplots(figsize=(SINGLE, 2.45))
ax.axhline(0, color='black', lw=0.5)
for n, filled, dx in ((2000000, False, -0.17), (10000000, True, 0.17)):
    hr = {}
    for r in rows(f'results/P3/rows_{n}/figs/hit_rates.csv'):
        if r['capacity'] == '256' and r['table'] != 'all':
            hr[r['policy'], int(r['table'])] = float(r['hit_rate_pct'])
    tables = sorted({t for _, t in hr})
    for pol, off in ((PERS, 0), (RESET, 0.0)):
        lab, col, mk, _, _ = POLICY[pol]
        d = [hr[pol, t] - hr['LRU', t] for t in tables]
        ax.plot([t + dx for t in tables], d, ls='none', marker=mk, color=col, mfc=col if filled else 'white',
                mew=0.7, ms=3.5, label=f'{lab}, {n // 1000000}M rows')
ax.set_xlabel('Table index (categorical feature, 0-25)')
ax.set_ylabel('Hit rate minus LRU (pp)')
ax.set_xticks(range(0, 26, 5))
ax.set_xlim(-0.8, 25.8)
fig.legend(ncol=2, loc='outside upper center', handletextpad=0.2, columnspacing=0.8)
save(fig, 'fig_pertable')
