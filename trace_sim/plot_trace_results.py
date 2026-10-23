#!/usr/bin/env python3
"""
Plot trace-driven simulation results — publication-quality figures.
Run after run_trace_sim.py has produced results/trace_sim_results.json

Usage:
    python3 plot_trace_results.py --results results/trace_sim_results.json \
                                  --output figs/
"""

import argparse
import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# Academic style — matches paper figures
RC = {
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'axes.edgecolor': '#222222', 'axes.linewidth': 0.8,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'axes.grid.axis': 'y',
    'grid.color': '#DDDDDD', 'grid.linewidth': 0.5, 'grid.linestyle': '--',
    'xtick.direction': 'out', 'ytick.direction': 'out',
    'xtick.major.width': 0.8, 'ytick.major.width': 0.8,
    'xtick.major.size': 4, 'ytick.major.size': 4,
    'font.family': 'DejaVu Sans', 'font.size': 9,
    'axes.titlesize': 10, 'axes.titleweight': 'bold',
    'axes.labelsize': 9, 'legend.frameon': True,
    'legend.framealpha': 1.0, 'legend.edgecolor': '#AAAAAA',
    'legend.fontsize': 8, 'figure.dpi': 200,
    'savefig.dpi': 200, 'savefig.bbox': 'tight', 'savefig.pad_inches': 0.08,
    'lines.linewidth': 1.2,
}
plt.rcParams.update(RC)

C_LRU    = '#888888'   # gray dashed  — LRU
C_LFU    = '#1a1a1a'   # black solid  — LFU persistent (our RTL)
C_LFURES = '#555555'   # dark gray    — LFU reset (gem5 LFURP)
C_TLFU   = '#333333'   # near-black hatch — TinyLFU


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', default='results/trace_sim_results.json')
    parser.add_argument('--output',  default='figs')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    with open(args.results) as f:
        raw = json.load(f)

    # Parse
    capacities = sorted(int(k) for k in raw.keys())
    data = {int(k): v for k,v in raw.items()}

    # Identify policy names
    sample = data[capacities[0]]
    lru_key   = "LRU"
    lfu_key   = next(k for k in sample if 'persistent' in k)
    reset_key = next(k for k in sample if 'gem5' in k or 'reset' in k.lower())
    tlfu_key  = next(k for k in sample if 'TinyLFU' in k or 'Tiny' in k)

    lru_hr   = [data[c][lru_key]['hit_rate']   for c in capacities]
    lfu_hr   = [data[c][lfu_key]['hit_rate']   for c in capacities]
    reset_hr = [data[c][reset_key]['hit_rate'] for c in capacities]
    tlfu_hr  = [data[c][tlfu_key]['hit_rate']  for c in capacities]

    lru_dr   = [data[c][lru_key]['dram_reads']   for c in capacities]
    lfu_dr   = [data[c][lfu_key]['dram_reads']   for c in capacities]
    reset_dr = [data[c][reset_key]['dram_reads'] for c in capacities]
    tlfu_dr  = [data[c][tlfu_key]['dram_reads']  for c in capacities]

    cap_k = [c/1000 for c in capacities]   # in thousands for x-axis label

    # ── FIG A: Hit rate sweep — all 4 policies ────────────────
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    ax.plot(cap_k, lru_hr,   color=C_LRU,    ls='--', marker='o', ms=4,
            markerfacecolor='white', markeredgewidth=1.2, label='LRU (baseline)')
    ax.plot(cap_k, lfu_hr,   color=C_LFU,    ls='-',  marker='s', ms=4,
            label='LFU — persistent counters (our RTL)')
    ax.plot(cap_k, reset_hr, color=C_LFURES, ls=':',  marker='^', ms=4,
            markerfacecolor='white', markeredgewidth=1.0, label='LFU — gem5 LFURP (reset on evict)')
    ax.plot(cap_k, tlfu_hr,  color=C_TLFU,   ls='-.', marker='D', ms=4,
            markerfacecolor='white', markeredgewidth=1.0, label='TinyLFU (Window-LRU + LFU)')

    # Find crossover between LRU and LFU persistent
    crossover = None
    for i in range(len(capacities)-1):
        if lfu_hr[i] <= lru_hr[i] and lfu_hr[i+1] > lru_hr[i+1]:
            crossover = (cap_k[i] + cap_k[i+1]) / 2
            break
    if crossover:
        ax.axvline(crossover, color='#666666', lw=0.8, ls=':', alpha=0.7)
        ax.text(crossover+0.1, ax.get_ylim()[0]+2, f'Crossover\n~{crossover:.0f}k vectors',
                fontsize=7, color='#555555', style='italic')

    ax.set_xscale('log')
    ax.set_xlabel('Cache capacity (thousands of embedding vectors, log scale)')
    ax.set_ylabel('L2 Hit Rate (%)')
    ax.set_title('Hit Rate vs Cache Capacity — Criteo Trace (Real Data)')
    ax.legend(loc='upper left', fontsize=7.5)
    ax.set_axisbelow(True)
    ax.grid(which='both', color='#DDDDDD', linewidth=0.4)
    plt.tight_layout()
    out = os.path.join(args.output, 'trace_hitrate_sweep.png')
    plt.savefig(out); plt.close()
    print(f"Saved: {out}")

    # ── FIG B: DRAM reads — all 4 policies ───────────────────
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    ax.plot(cap_k, [v/1e6 for v in lru_dr],   color=C_LRU,    ls='--', marker='o', ms=4,
            markerfacecolor='white', markeredgewidth=1.2, label='LRU')
    ax.plot(cap_k, [v/1e6 for v in lfu_dr],   color=C_LFU,    ls='-',  marker='s', ms=4,
            label='LFU — persistent')
    ax.plot(cap_k, [v/1e6 for v in reset_dr], color=C_LFURES, ls=':',  marker='^', ms=4,
            markerfacecolor='white', markeredgewidth=1.0, label='LFU — gem5 reset')
    ax.plot(cap_k, [v/1e6 for v in tlfu_dr],  color=C_TLFU,   ls='-.', marker='D', ms=4,
            markerfacecolor='white', markeredgewidth=1.0, label='TinyLFU')

    ax.set_xscale('log')
    ax.set_xlabel('Cache capacity (thousands of embedding vectors, log scale)')
    ax.set_ylabel('DRAM Read Requests (millions)')
    ax.set_title('DRAM Traffic vs Cache Capacity — Criteo Trace (Real Data)')
    ax.legend(loc='upper right', fontsize=7.5)
    ax.set_axisbelow(True)
    ax.grid(which='both', color='#DDDDDD', linewidth=0.4)
    plt.tight_layout()
    out = os.path.join(args.output, 'trace_dram_sweep.png')
    plt.savefig(out); plt.close()
    print(f"Saved: {out}")

    # ── FIG C: Phase transition — persistent LFU vs gem5 LFURP
    # Shows clearly WHY the cold-start penalty exists
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    diff_persist = [lfu_hr[i] - lru_hr[i]   for i in range(len(capacities))]
    diff_reset   = [reset_hr[i] - lru_hr[i] for i in range(len(capacities))]
    diff_tlfu    = [tlfu_hr[i] - lru_hr[i]  for i in range(len(capacities))]

    ax.axhline(0, color='#888888', lw=0.8, ls='--', alpha=0.6, label='LRU baseline (0 pp)')
    ax.plot(cap_k, diff_persist, color=C_LFU,    ls='-',  marker='s', ms=4,
            label='LFU persistent − LRU (our RTL)')
    ax.plot(cap_k, diff_reset,   color=C_LFURES, ls=':',  marker='^', ms=4,
            markerfacecolor='white', markeredgewidth=1.0, label='LFU gem5-reset − LRU')
    ax.plot(cap_k, diff_tlfu,    color=C_TLFU,   ls='-.', marker='D', ms=4,
            markerfacecolor='white', markeredgewidth=1.0, label='TinyLFU − LRU')

    # Shade regions
    ax.axhspan(-15, 0, alpha=0.04, color='#AA0000')   # LFU worse
    ax.axhspan(0,   20, alpha=0.04, color='#006600')   # LFU better

    ax.set_xscale('log')
    ax.set_xlabel('Cache capacity (thousands of embedding vectors, log scale)')
    ax.set_ylabel('Hit rate gain vs LRU (percentage points)')
    ax.set_title('Cache-Policy Phase Transition — Gain over LRU Baseline')
    ax.legend(loc='upper left', fontsize=7.5)
    ax.set_axisbelow(True)
    ax.grid(which='both', color='#DDDDDD', linewidth=0.4)
    plt.tight_layout()
    out = os.path.join(args.output, 'trace_phase_transition.png')
    plt.savefig(out); plt.close()
    print(f"Saved: {out}")

    # ── Print summary table ───────────────────────────────────
    print("\n" + "="*85)
    print(f"{'Cap (k)':>8} | {'LRU':>8} | {'LFU-pers':>10} | "
          f"{'LFU-reset':>11} | {'TinyLFU':>9} | {'Winner':>12}")
    print("="*85)
    for i, cap in enumerate(capacities):
        best = max(lru_hr[i], lfu_hr[i], reset_hr[i], tlfu_hr[i])
        if   best == tlfu_hr[i]:  winner = "TinyLFU"
        elif best == lfu_hr[i]:   winner = "LFU-persistent"
        elif best == lru_hr[i]:   winner = "LRU"
        else:                     winner = "LFU-reset"
        print(f"{cap/1000:>8.1f} | {lru_hr[i]:>7.2f}% | {lfu_hr[i]:>9.2f}% | "
              f"{reset_hr[i]:>10.2f}% | {tlfu_hr[i]:>8.2f}% | {winner:>12}")


if __name__ == '__main__':
    main()
