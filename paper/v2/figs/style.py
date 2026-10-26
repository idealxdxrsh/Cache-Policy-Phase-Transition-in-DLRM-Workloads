"""Shared style and input helpers for the paper/v2 figures.

Inputs are read with `git show HEAD:<path>`, so a figure can only be drawn from committed result files.
Fonts: Liberation Serif (metric-compatible with Times, which IEEEtran uses) and STIX math, embedded as TrueType
(pdf.fonttype 42). Colours: Okabe-Ito (colour-blind safe); every series also has its own marker and line style so the
figures read in grayscale.
"""
import csv
import io
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use('pdf')
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True,
                           check=True).stdout.strip())
OUT = Path(__file__).resolve().parent
SINGLE, DOUBLE = 3.48, 7.14                   # IEEEtran \columnwidth 252pt, \textwidth 516pt (1 in = 72.27 pt)

plt.rcParams.update({
    'pdf.fonttype': 42, 'ps.fonttype': 42,
    'font.family': 'serif', 'font.serif': ['Liberation Serif'], 'mathtext.fontset': 'stix',
    'font.size': 8, 'axes.labelsize': 8, 'xtick.labelsize': 7, 'ytick.labelsize': 7, 'legend.fontsize': 7,
    'axes.linewidth': 0.6, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
    'xtick.minor.width': 0.4, 'ytick.minor.width': 0.4, 'lines.linewidth': 1.0, 'lines.markersize': 4,
    'axes.spines.top': False, 'axes.spines.right': False, 'legend.frameon': False,
    'figure.constrained_layout.use': True, 'figure.constrained_layout.h_pad': 0.02,
    'figure.constrained_layout.w_pad': 0.02,
})

# policy name in the result CSVs -> (label, colour, marker, line style, hatch)
POLICY = {
    'LRU': ('LRU', '#000000', 'o', '-', ''),
    'LFU (gem5 LFURP — reset on eviction)': ('LFU, reset on eviction', '#0072B2', 's', '-', '//'),
    'LFU (persistent counters)': ('LFU, persistent counters', '#D55E00', '^', '-.', '\\\\'),
    'TinyLFU-exact (window=1%)': ('TinyLFU, exact counters', '#E69F00', 'P', ':', '..'),
    'W-TinyLFU (Count-Min, window=1%)': ('W-TinyLFU (Count-Min)', '#CC79A7', 'v', '--', 'xx'),
    'ARC': ('ARC', '#009E73', 'D', (0, (5, 1, 1, 1)), '++'),
    'Belady (MIN, offline)': ('Belady (offline bound)', '#777777', '*', (0, (1, 1)), ''),
}


def read(path):
    """Committed content of a repository file (fails if the file is not committed)."""
    tracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--error-unmatch', path], capture_output=True)
    if tracked.returncode:
        raise SystemExit(f'not committed: {path}')
    return subprocess.run(['git', '-C', str(ROOT), 'show', f'HEAD:{path}'], capture_output=True, text=True,
                          check=True).stdout


def rows(path):
    return list(csv.DictReader(io.StringIO(read(path))))


def files(prefix):
    return sorted(f for f in subprocess.run(['git', '-C', str(ROOT), 'ls-files', prefix], capture_output=True,
                                            text=True, check=True).stdout.splitlines())


def save(fig, name):
    fig.savefig(OUT / f'{name}.pdf')
    print(f'wrote {(OUT / name).relative_to(ROOT)}.pdf')
