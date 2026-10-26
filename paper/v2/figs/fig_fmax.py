"""Fig. (e): pre-layout Fmax (NanGate45, 1 GHz netlists) vs cache depth across the design iterations, COUNTER_MODE 0
and 1, with the flow noise band (min-max Fmax of 8 same-logic designs) for the old flow (P5d) and the P5e flow.

Reads results/{P5,P5b,P5c/tree_copies,P5d,P5e/new}/d*_m*_1000MHz/sta.txt and the noise-floor designs listed in
NOISE (same directories as tools/make_tables.py).
"""
import re

from style import DOUBLE, plt, read, save

DEPTHS = (16, 64, 256)
ITER = [('Baseline (P5)', 'results/P5', '#000000', 'o', '-'),
        ('Stage-B tree + copies (P5b)', 'results/P5b', '#E69F00', 'v', ':'),
        ('Stage-A tree (P5c)', 'results/P5c/tree_copies', '#56B4E9', 'P', (0, (5, 1, 1, 1))),
        ('Hit tree, old flow (P5d)', 'results/P5d', '#0072B2', 's', '--'),
        ('Hit tree, timing-driven flow (P5e)', 'results/P5e/new', '#D55E00', '^', '-')]
NOISE = {'results/P5d': ['results/P5d', 'results/P5d/noise/null_tagcmp_swap', 'results/P5d/noise/null_hitor_swap',
                         'results/P5d/noise/null_stageB_gt', 'results/P5d/attempt1_packed_vectors'] +
         [f'results/P5d/attempt1_packed_vectors/noise/{v}' for v in ('null_tagcmp_swap', 'null_hitor_swap', 'null_stageB_gt')],
         'results/P5e/new': ['results/P5e/new'] + [f'results/P5e/noise/{a}{v}' for a in ('final_', 'packed_')
                                                   for v in ('null_tagcmp_swap', 'null_hitor_swap', 'null_stageB_gt')]
         + ['results/P5e/noise/packed']}


def fmax(d, depth, mode):
    sta = read(f'{d}/d{depth}_m{mode}_1000MHz/sta.txt')
    period = float(re.search(r'^PERIOD_NS (\S+)', sta, re.M).group(1))
    wns = float(re.search(r'^wns max (\S+)', sta, re.M).group(1))
    assert wns < 0, (d, depth, mode)
    return 1e3 / (period - wns)


fig, axes = plt.subplots(1, 2, figsize=(DOUBLE, 2.5), sharey=True)
for ax, mode in zip(axes, (0, 1)):
    for d, col in (('results/P5d', '#0072B2'), ('results/P5e/new', '#D55E00')):
        lo = [min(fmax(v, n, mode) for v in NOISE[d]) for n in DEPTHS]
        hi = [max(fmax(v, n, mode) for v in NOISE[d]) for n in DEPTHS]
        ax.fill_between(DEPTHS, lo, hi, color=col, alpha=0.15, lw=0,
                        hatch='////' if d == 'results/P5d' else '\\\\\\\\', edgecolor=col)
    for lab, d, col, mk, ls in ITER:
        ax.plot(DEPTHS, [fmax(d, n, mode) for n in DEPTHS], color=col, marker=mk, ls=ls, label=lab)
    ax.axhline(500, color='0.4', lw=0.6, ls=(0, (2, 2)))
    ax.text(1.01, 500, '500\nMHz', fontsize=6.5, color='0.35', va='center', ha='left',
            transform=ax.get_yaxis_transform())
    ax.set_xscale('log', base=2)
    ax.set_xticks(DEPTHS, [str(n) for n in DEPTHS])
    ax.minorticks_off()
    ax.set_xlabel(f'Cache depth (lines), COUNTER_MODE {mode}')
    ax.set_ylim(0, 800)
axes[0].set_ylabel('Fmax, pre-layout (MHz)')
h, lab = axes[0].get_legend_handles_labels()
h += [plt.Rectangle((0, 0), 1, 1, fc='#0072B2', alpha=0.15, hatch='////', ec='#0072B2', lw=0),
      plt.Rectangle((0, 0), 1, 1, fc='#D55E00', alpha=0.15, hatch='\\\\\\\\', ec='#D55E00', lw=0)]
lab += ['noise band, old flow (8 same-logic designs)', 'noise band, timing-driven flow (8 designs)']
fig.legend(h, lab, loc='outside upper center', ncol=4, columnspacing=1.0)
save(fig, 'fig_fmax')
