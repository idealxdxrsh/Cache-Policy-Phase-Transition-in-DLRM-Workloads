"""Fig. (d): median embedding share emb / (emb + MLP) vs batch size on one H100 and one H200, Criteo-hashed
indices, for each (rows, dim). Launch-bound cells (CPU wall per iteration within LB_TOL of the batch-64 CPU wall
of the same rows/dim/pattern, criterion from tools/p4_results.py) are drawn as open markers and shaded per panel
where every series is launch-bound.

Reads results/P4/h100_413621/results.csv, results/P4/h200_413622/results.csv, tools/p4_results.py (LB_TOL).
"""
import re

from style import DOUBLE, plt, read, rows, save

LB_TOL = float(re.search(r'^LB_TOL = ([\d.]+)', read('tools/p4_results.py'), re.M).group(1))
PATTERN = 'criteo'
SERIES = {('1000000', '64'): ('#0072B2', 'o', '-'), ('1000000', '128'): ('#D55E00', 's', '--'),
          ('10000000', '64'): ('#009E73', '^', '-.'), ('10000000', '128'): ('#CC79A7', 'D', ':')}
fig, axes = plt.subplots(1, 2, figsize=(DOUBLE, 2.45), sharey=True)
h100 = {(r['rows'], r['dim']) + (int(r['batch']),) for r in rows('results/P4/h100_413621/results.csv')
        if r['pattern'] == PATTERN and r['status'] == 'ok'}
for ax, (gpu, path) in zip(axes, (('H100', 'results/P4/h100_413621/results.csv'),
                                  ('H200', 'results/P4/h200_413622/results.csv'))):
    data = {(r['rows'], r['dim'], int(r['batch'])): r for r in rows(path)
            if r['pattern'] == PATTERN and r['status'] == 'ok'}
    batches = sorted({b for _, _, b in data})
    lb_all = {b: True for b in batches}
    for (nr, dim), (col, mk, ls) in SERIES.items():
        pts = [(b, data[nr, dim, b]) for b in batches if (nr, dim, b) in data]
        if not pts:
            continue
        base = float(data[nr, dim, 64]['cpu_wall_ms_per_iter'])
        xs = [b for b, _ in pts]
        ys = [float(r['emb_share_median']) for _, r in pts]
        lb = [float(r['cpu_wall_ms_per_iter']) <= LB_TOL * base for _, r in pts]
        for b, l in zip(xs, lb):
            lb_all[b] &= l
        ax.plot(xs, ys, color=col, ls=ls, lw=0.9, label=f'$10^{{{len(nr) - 1}}}$ rows, dim {dim}' + ('' if gpu == 'H100' else ' (H200 only)' if
                                                             not any(k[:2] == (nr, dim) for k in h100) else ''))
        ax.plot([x for x, l in zip(xs, lb) if l], [y for y, l in zip(ys, lb) if l], ls='none', marker=mk,
                color=col, mfc='white', mew=0.8)
        ax.plot([x for x, l in zip(xs, lb) if not l], [y for y, l in zip(ys, lb) if not l], ls='none', marker=mk,
                color=col)
    lbx = [b for b in batches if lb_all[b]]
    if lbx:
        ax.axvspan(min(lbx) / 1.3, max(lbx) * 1.3, color='0.9', zorder=0, lw=0)
        ax.text((min(lbx) * max(lbx)) ** 0.5, 0.03, 'all series launch-bound', ha='center', va='bottom',
                fontsize=6.5, color='0.35', transform=ax.get_xaxis_transform())
    ax.set_xscale('log', base=2)
    ax.set_xticks(batches, [str(b) for b in batches])
    ax.minorticks_off()
    ax.set_xlabel(f'Batch size (samples), {gpu}')
    ax.set_ylim(0, 1)
axes[0].set_ylabel('Embedding share of\nembedding + MLP time')
h, lab = axes[0].get_legend_handles_labels()
h2, lab2 = axes[1].get_legend_handles_labels()
h += [x for x, l in zip(h2, lab2) if l not in lab]
lab += [l for l in lab2 if l not in lab]
h += [plt.Line2D([], [], color='0.3', marker='o', mfc='white', ls='none'),
      plt.Line2D([], [], color='0.3', marker='o', ls='none')]
lab += [f'launch-bound (CPU wall within {round((LB_TOL - 1) * 100)}% of batch 64)', 'not launch-bound']
fig.legend(h, lab, loc='outside upper center', ncol=3, columnspacing=1.2)
save(fig, 'fig_profile')
