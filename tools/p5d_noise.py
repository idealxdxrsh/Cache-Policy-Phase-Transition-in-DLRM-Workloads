"""P5d noise floor: Fmax spread over logically identical designs. NanGate45, not TSMC. Pre-layout.

Usage: python -I tools/p5d_noise.py <liberty>   (prints Markdown)
Designs, all the same logic (1 GHz netlists, abc -D 1000):
  final            = results/P5d (rtl/v2, hit tree as unpacked arrays)
  final null_*     = results/P5d/noise/null_*   (tools/p5d_null_variants.py rewrites of rtl/v2)
  packed           = results/P5d/attempt1_packed_vectors (same tree as flat vectors; equal by Yosys equiv at depth 16)
  packed null_*    = results/P5d/attempt1_packed_vectors/noise/null_*
Spread = (max - min) / min of Fmax = 1 / (period - WNS). Netlist hashes are not compared: the netlist text
embeds the source file path. Distinct (cells, area) pairs show how many different mappings there were.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p5_results import row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NULLS = ['null_tagcmp_swap', 'null_hitor_swap', 'null_stageB_gt']
DESIGNS = ([('final', 'results/P5d')] + [(f'final {n}', f'results/P5d/noise/{n}') for n in NULLS]
           + [('packed', 'results/P5d/attempt1_packed_vectors')]
           + [(f'packed {n}', f'results/P5d/attempt1_packed_vectors/noise/{n}') for n in NULLS])


def main():
    lib = sys.argv[1]
    out = ['| depth | mode | ' + ' | '.join(n for n, _ in DESIGNS) + ' | min | max | spread | distinct (cells, area) |',
           '|' + '---|' * (len(DESIGNS) + 6)]
    for d in (16, 64, 256):
        for m in (0, 1):
            fs, maps = [], set()
            for _, p in DESIGNS:
                r = row(ROOT / p / f'd{d}_m{m}_1000MHz', lib)
                fs.append(1e3 / r['minp'])
                maps.add((r['cells'], r['area']))
            lo, hi = min(fs), max(fs)
            out.append(f'| {d} | {m} | ' + ' | '.join(f'{f:.1f}' for f in fs)
                       + f' | {lo:.1f} | {hi:.1f} | {100 * (hi - lo) / lo:.2f}% | {len(maps)} of {len(fs)} |')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
