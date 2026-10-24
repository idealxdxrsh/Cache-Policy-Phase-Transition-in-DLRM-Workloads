"""Before/after tables for P5b. NanGate45, not TSMC. Pre-layout. No power numbers.

Usage: python -I tools/p5b_compare.py <liberty>
Columns: P5 = rtl-v2-baseline (results/P5); tree only = results/P5b/attempt1_copies_merged (the address
copies were merged back into one register by Yosys, so only the Stage-B tree is in those netlists);
tree + copies = results/P5b. Reads the same files as tools/p5_results.py.
Fmax = 1 / (period - WNS) of that netlist; "met" when WNS >= 0 (then Fmax >= the target, not measured).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p5_results import row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEPTHS, MODES, FREQS = [16, 64, 256], [0, 1], [1000, 500]
RUNS = [('P5 baseline', 'results/P5'), ('tree only', 'results/P5b/attempt1_copies_merged'),
        ('tree + copies', 'results/P5b')]


def fmax(r, f):
    return f'{1e3 / r["minp"]:.1f}' if r['minp'] else f'met (>= {f})'


def main():
    lib = sys.argv[1]
    names = [n for n, _ in RUNS]
    out = []
    for f in FREQS:
        out += [f'### Netlists synthesized for {f} MHz (abc -D {1000000 // f} ps), STA at {f} MHz', '',
                '| depth | mode | ' + ' | '.join(f'WNS ns {n}' for n in names) + ' | '
                + ' | '.join(f'Fmax MHz {n}' for n in names) + ' | '
                + ' | '.join(f'cells {n}' for n in names) + ' | '
                + ' | '.join(f'area um^2 {n}' for n in names) + ' | '
                + ' | '.join(f'flip-flops {n}' for n in names) + ' |',
                '|' + '---|' * (2 + 5 * len(RUNS))]
        for d in DEPTHS:
            for m in MODES:
                rs = [row(ROOT / p / f'd{d}_m{m}_{f}MHz', lib) for _, p in RUNS]
                out.append(f'| {d} | {m} | ' + ' | '.join(f'{r["wns"]:.4f}' for r in rs) + ' | '
                           + ' | '.join(fmax(r, f) for r in rs) + ' | '
                           + ' | '.join(f'{r["cells"]:,}' for r in rs) + ' | '
                           + ' | '.join(f'{r["area"]:.3f}' for r in rs) + ' | '
                           + ' | '.join(f'{r["ffs"]:,}' for r in rs) + ' |')
        out.append('')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
