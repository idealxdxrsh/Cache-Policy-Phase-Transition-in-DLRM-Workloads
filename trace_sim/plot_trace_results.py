#!/usr/bin/env python3
"""
Plot trace-driven simulation results.
Run after run_trace_sim.py (or merge_results.py) has produced a results JSON.

Usage:
    python3 plot_trace_results.py --results results/trace_sim_results.json \
                                  --output figs/

Figures (every policy present in the JSON is drawn; Belady, if present, is a
dashed gray bound):
  trace_hit_rate_sweep.png     aggregate hit rate vs capacity
  trace_dram_reads.png         aggregate misses (= DRAM reads) vs capacity
  trace_phase_transition.png   each policy minus LRU, percentage points
  trace_per_table.png          per-table hit rate vs capacity, 26 small multiples
  trace_zipf_alpha.png         fitted Zipf exponent per table
Tables (text view of the same data):
  hit_rates.csv                policy, capacity, table ('all' = aggregate), hits, misses, hit rate
  zipf_per_table.csv           table, column, accesses, unique, alpha, fit points
"""

import argparse
import csv
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

RC = {
    'figure.facecolor': '#fcfcfb', 'axes.facecolor': '#fcfcfb',
    'savefig.facecolor': '#fcfcfb',
    'axes.edgecolor': '#52514e', 'axes.linewidth': 0.6,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'axes.grid.axis': 'y',
    'grid.color': '#e4e3df', 'grid.linewidth': 0.5,
    'xtick.color': '#52514e', 'ytick.color': '#52514e',
    'axes.labelcolor': '#0b0b0b', 'text.color': '#0b0b0b',
    'xtick.direction': 'out', 'ytick.direction': 'out',
    'font.family': 'DejaVu Sans', 'font.size': 9,
    'axes.titlesize': 10, 'axes.titleweight': 'bold', 'axes.labelsize': 9,
    'legend.frameon': False, 'legend.fontsize': 8,
    'figure.dpi': 200, 'savefig.dpi': 200,
    'savefig.bbox': 'tight', 'savefig.pad_inches': 0.08,
    'lines.linewidth': 1.6, 'lines.markersize': 4,
}
plt.rcParams.update(RC)

# Categorical slots 1-6 of the dataviz reference palette, in fixed order
# (validated: adjacent CVD dE >= 9.1, normal-vision dE >= 19.6 on #fcfcfb).
# Three slots are below 3:1 contrast, so every series also has its own marker
# and line style, and hit_rates.csv is the table view.
SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300']
MARKERS = ['o', 's', '^', 'D', 'v', 'P']
STYLES = ['-', '-', '--', '-.', ':', '--']
BOUND = '#8a8985'           # Belady: neutral gray, dashed, no marker

# Policy names in run_trace_sim.py -> short legend labels. Unknown names
# (e.g. from an older JSON) fall back to the full name.
SHORT = {
    'LRU': 'LRU',
    'LFU (persistent counters)': 'LFU, per-address history (idealised)',
    'LFU (gem5 LFURP — reset on eviction)': 'LFU, reset on eviction',
    'TinyLFU-exact (window=1%)': 'TinyLFU, exact counters',
    'W-TinyLFU (Count-Min, window=1%)': 'W-TinyLFU, Count-Min sketch',
    'ARC': 'ARC',
    'Belady (MIN, offline)': 'Belady MIN (offline bound)',
}


def load(path):
    """Return (capacities, results, tables). Accepts the old flat format too."""
    with open(path) as f:
        raw = json.load(f)
    if 'results' in raw:
        res, tables = raw['results'], raw.get('tables', [])
    else:
        res, tables = raw, []
    caps = sorted(int(k) for k in res)
    return caps, {int(k): v for k, v in res.items()}, tables


def styles(names):
    """Fixed style per policy name, by its position among online policies."""
    out, i = {}, 0
    for n in names:
        if n.startswith('Belady'):
            out[n] = dict(color=BOUND, ls=(0, (4, 2)), marker=None, lw=1.2, zorder=1)
        else:
            out[n] = dict(color=SERIES[i % len(SERIES)], ls=STYLES[i % len(STYLES)],
                          marker=MARKERS[i % len(MARKERS)], lw=1.6, zorder=3)
            i += 1
    return out


def log_x(ax, caps):
    ax.set_xscale('log')
    ax.set_xticks(caps)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(
        lambda v, _: f'{v/1000:g}k' if v >= 1000 else f'{v:g}'))
    ax.xaxis.set_minor_locator(ticker.NullLocator())
    ax.set_xlabel('cache capacity (vectors per table)')


def line_plot(caps, names, sty, ys, ylabel, title, out, zero_line=False):
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for n in names:
        s = sty[n]
        ax.plot(caps, ys[n], color=s['color'], ls=s['ls'], marker=s['marker'],
                lw=s['lw'], zorder=s['zorder'], label=SHORT.get(n, n))
    if zero_line:
        ax.axhline(0, color='#52514e', lw=0.6, zorder=0)
    log_x(ax, caps)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc='left')
    ax.legend(loc='center left', bbox_to_anchor=(1.01, 0.5))
    fig.savefig(out)
    plt.close(fig)
    print(f"Saved: {out}")


def write_csvs(caps, res, tables, names, outdir):
    p = os.path.join(outdir, 'hit_rates.csv')
    with open(p, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['policy', 'capacity', 'table', 'hits', 'misses', 'hit_rate_pct'])
        for n in names:
            for c in caps:
                r = res[c][n]
                w.writerow([n, c, 'all', r['hits'], r['misses'], f"{r['hit_rate']:.4f}"])
                for t in r.get('per_table', []):
                    w.writerow([n, c, t['table'], t['hits'], t['misses'],
                                f"{t['hit_rate']:.4f}"])
    print(f"Saved: {p}")
    if tables:
        p = os.path.join(outdir, 'zipf_per_table.csv')
        with open(p, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['table', 'column', 'accesses', 'unique',
                        'zipf_alpha', 'zipf_fit_points'])
            for t in tables:
                a = '' if t['zipf_alpha'] is None else f"{t['zipf_alpha']:.4f}"
                w.writerow([t['table'], t['column'], t['accesses'], t['unique'],
                            a, t['zipf_fit_points']])
        print(f"Saved: {p}")


def per_table_plot(caps, res, names, sty, out):
    tabs = [t['table'] for t in res[caps[0]][names[0]].get('per_table', [])]
    if not tabs:
        return
    ncol = 7
    nrow = -(-len(tabs) // ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(13, 2.0 * nrow),
                             sharex=True, sharey=True, squeeze=False)
    for ax, (i, t) in zip(axes.flat, enumerate(tabs)):
        for n in names:
            s = sty[n]
            y = [res[c][n]['per_table'][i]['hit_rate'] for c in caps]
            ax.plot(caps, y, color=s['color'], ls=s['ls'], lw=1.0, zorder=s['zorder'],
                    label=SHORT.get(n, n))
        ax.set_title(f'table {t} (C{t + 1})', fontsize=8, loc='left')
        ax.set_xscale('log')
        ax.xaxis.set_minor_locator(ticker.NullLocator())
        ax.set_xticks([caps[0], caps[-1]])
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(
            lambda v, _: f'{v/1000:g}k' if v >= 1000 else f'{v:g}'))
    for ax in axes.flat[len(tabs):]:
        ax.axis('off')
    for ax in axes[:, 0]:
        ax.set_ylabel('hit rate (%)')
    h, l = axes.flat[0].get_legend_handles_labels()
    fig.suptitle('Per-table hit rate vs capacity (vectors)', x=0.01, ha='left',
                 fontweight='bold')
    fig.tight_layout()
    spare = list(axes.flat[len(tabs):])
    if spare:                                   # legend over the empty grid slots
        pos = spare[0].get_position()
        fig.legend(h, l, loc='center left', fontsize=7.5,
                   bbox_to_anchor=(pos.x0, pos.y0 + pos.height / 2))
    else:
        fig.legend(h, l, loc='upper center', ncol=4, bbox_to_anchor=(0.5, 0.0))
    fig.savefig(out)
    plt.close(fig)
    print(f"Saved: {out}")


def zipf_plot(tables, out):
    tabs = [t for t in tables if t['zipf_alpha'] is not None]
    if not tabs:
        return
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    x = [t['table'] for t in tabs]
    ax.bar(x, [t['zipf_alpha'] for t in tabs], width=0.7, color=SERIES[0])
    ax.set_xticks(x)
    ax.set_xticklabels([str(i) for i in x], fontsize=7)
    ax.set_xlabel('table index (C1 = 0)')
    ax.set_ylabel('fitted Zipf alpha')
    ax.set_title('Zipf exponent per table (log-log OLS, ranks with count >= 5)',
                 loc='left')
    fig.savefig(out)
    plt.close(fig)
    print(f"Saved: {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', default='results/trace_sim_results.json')
    parser.add_argument('--output', default='figs')
    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)

    caps, res, tables = load(args.results)
    names = list(res[caps[0]])
    names.sort(key=lambda n: n.startswith('Belady'))   # bound drawn/listed last
    sty = styles(names)
    write_csvs(caps, res, tables, names, args.output)

    hr = {n: [res[c][n]['hit_rate'] for c in caps] for n in names}
    dr = {n: [res[c][n]['dram_reads'] / 1e6 for c in caps] for n in names}
    line_plot(caps, names, sty, hr, 'hit rate (%)',
              'Hit rate vs capacity, all tables',
              os.path.join(args.output, 'trace_hit_rate_sweep.png'))
    line_plot(caps, names, sty, dr, 'misses = DRAM reads (millions)',
              'Misses vs capacity, all tables',
              os.path.join(args.output, 'trace_dram_reads.png'))
    others = [n for n in names if n != 'LRU']
    diff = {n: [a - b for a, b in zip(hr[n], hr['LRU'])] for n in others}
    line_plot(caps, others, sty, diff, 'hit rate minus LRU (pp)',
              'Each policy minus LRU, all tables',
              os.path.join(args.output, 'trace_phase_transition.png'), zero_line=True)
    per_table_plot(caps, res, names, sty, os.path.join(args.output, 'trace_per_table.png'))
    zipf_plot(tables, os.path.join(args.output, 'trace_zipf_alpha.png'))

    print(f"\n{'capacity':>9} | " + " | ".join(f"{SHORT.get(n, n)[:14]:>14}" for n in names))
    for i, c in enumerate(caps):
        print(f"{c:>9,} | " + " | ".join(f"{hr[n][i]:>13.2f}%" for n in names))


if __name__ == '__main__':
    main()
