"""P12: Genus runs on C2 as two Markdown tables. Library, corner and tool version are not named in the repo.

Usage: python -I tools/c2_collect.py [dir]   (dir defaults to ~/c2_results, outside the repo)
One folder per run, named <ver>_m<mode>_d<depth>_p<period_ns> as written by cadence/run_genus.csh, holding
timing.rpt, area.rpt, gates.rpt, power.rpt and constraints.sdc copied from C2. Other folders are skipped (stderr).
Every number is read from a file of that run: WNS = slack of Path 1 in timing.rpt (ps); period = create_clock -period
in constraints.sdc (must equal the folder name); Fmax = 1 / (period - WNS), reported only when WNS < 0 (WNS = 0 is
"met at target, Fmax not measured", WNS > 0 is "relaxed, Fmax not meaningful"); area = Total Area of the top
instance in area.rpt (library area unit, which the report does not state); cells = the 'total' row of gates.rpt
(must equal Cell Count in area.rpt); flip-flops = the 'sequential' row of gates.rpt, which counts flip-flops and
latches, so the script stops unless the 'latch' row of power.rpt is all zero; power = Total of the Subtotal row in
power.rpt, in its Power Unit. Depth and mode must equal the elaborated module name in area.rpt, so a run whose
parameters were not applied stops the script.
Table 2 = v3 - v2 at each mode, depth and period, in Decimal arithmetic on the report strings. Mode 1 is the same
logic in both versions (RTL equivalence proven by Yosys at depth 16 and 64: results/P11/equiv/equiv_d16_m1.txt,
equiv_d64_m1.txt), so its difference is the observed noise reference of this flow; mode 0 differs in logic (v3 adds
the Rotate-victim tie-break).
"""
import re
import sys
from decimal import Decimal
from pathlib import Path

DIR = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / 'c2_results'
NAME = re.compile(r'^(v\d+)_m(\d+)_d(\d+)_p(\d+(?:\.\d+)?)$')


def find(pattern, text, where, last=False):
    m = re.findall(pattern, text, re.M)
    if not m:
        sys.exit(f'{where}: no match for {pattern!r}')
    return m[-1] if last else m[0]


def row(d):
    ver, mode, depth, period = NAME.match(d.name).groups()
    t, a, g, p, sdc = ((d / f).read_text() for f in ('timing.rpt', 'area.rpt', 'gates.rpt', 'power.rpt', 'constraints.sdc'))
    sdc_period = find(r'^create_clock\b.*-period\s+(\S+)', sdc, f'{d}/constraints.sdc')
    if float(sdc_period) != float(period):
        sys.exit(f'{d}: constraints.sdc period {sdc_period} != folder name {period}')
    status, wns = find(r'^Path 1: (MET|VIOLATED) \((-?\d+(?:\.\d+)?) ps\)', t, f'{d}/timing.rpt')
    if float(find(r'^\s*Slack:=\s*(-?\d+(?:\.\d+)?)', t, f'{d}/timing.rpt')) != float(wns):
        sys.exit(f'{d}/timing.rpt: Path 1 slack and Slack:= differ')
    a_depth, a_mode, a_cells, area, wl = find(
        r'^\S+_CACHE_DEPTH(\d+)_COUNTER_MODE(\d+)\s+(\d+)\s+\S+\s+\S+\s+(\S+)(.*)$', a, f'{d}/area.rpt')
    if (a_depth, a_mode) != (depth, mode):
        sys.exit(f'{d}/area.rpt: elaborated CACHE_DEPTH={a_depth} COUNTER_MODE={a_mode}, folder says d{depth} m{mode}')
    if '(D)' not in wl:
        print(f'{d.name}: area.rpt does not mark the wireload as the library default', file=sys.stderr)
    cells = find(r'^\s*total\s+(\d+)\s+\S+\s+100\.0\s*$', g, f'{d}/gates.rpt', last=True)
    if cells != a_cells:
        sys.exit(f'{d}: gates.rpt total {cells} != area.rpt Cell Count {a_cells}')
    ffs = find(r'^\s*sequential\s+(\d+)\s', g, f'{d}/gates.rpt')
    if any(float(x) for x in find(r'^\s*latch\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', p, f'{d}/power.rpt')):
        sys.exit(f'{d}/power.rpt: latch power is not zero, so gates.rpt sequential is not a flip-flop count')
    unit = find(r'^Power Unit:\s*(\S+)', p, f'{d}/power.rpt')
    power = find(r'^\s*Subtotal\s+\S+\s+\S+\s+\S+\s+(\S+)', p, f'{d}/power.rpt')
    if Decimal(wns) > 0:
        fmax = 'relaxed, Fmax not meaningful'
    elif Decimal(wns) == 0:
        fmax = 'met at target, Fmax not measured'
    else:
        fmax = f'{1e6 / (float(period) * 1e3 - float(wns)):.1f}'  # MHz, from ns and ps
    return dict(ver=ver, mode=int(mode), depth=int(depth), period=period, wns=wns, status=status, fmax=fmax,
                area=area, cells=cells, ffs=ffs, power=f'{power} {unit}')


def key(r):
    return r['ver'], r['mode'], r['depth'], float(r['period'])


def main():
    rows = []
    for d in sorted(x for x in DIR.iterdir() if x.is_dir()):
        if NAME.match(d.name):
            rows.append(row(d))
        else:
            print(f'skipped {d.name}', file=sys.stderr)
    rows.sort(key=key)
    print('# P12 Genus synthesis on C2 (v2 = tag rtl-v2-final, v3 = branch rtl-v3). '
          'Library, corner and tool version are not named in the repo.')
    print('Pre-layout: no LEF, library default wireload; power is vectorless (default switching activity); '
          'I/O delay 0.2 x period, clock uncertainty 0. Fmax = 1 / (period - WNS), only for WNS < 0.')
    print('Limitation: Genus ignored (* keep *) on req_addr_grp (VLOGPT-506) and merged the per-group address copies '
          'into one register, so these netlists lack the per-group fan-out split the RTL was written for.')
    print(f'Source: {DIR}/<run>/{{timing,area,gates,power}}.rpt, constraints.sdc\n')
    print('| version | mode | depth | period (ns) | WNS (ps) | Fmax (MHz) | area (lib unit) | cells | flip-flops '
          '| total power |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for r in rows:
        print(f"| {r['ver']} | {r['mode']} | {r['depth']} | {r['period']} | {r['wns']} ({r['status']}) | {r['fmax']} "
              f"| {r['area']} | {r['cells']} | {r['ffs']} | {r['power']} |")

    by = {key(r): r for r in rows}
    print('\n## v3 - v2 at the same mode, depth and period')
    print('Mode 1 is the same logic in both versions (RTL equivalence proven by Yosys at depth 16 and 64, '
          'results/P11/equiv/equiv_d16_m1.txt and equiv_d64_m1.txt; not run at 256), so its difference is the observed '
          'noise reference of this flow. Mode 0 differs in logic (v3 adds the Rotate-victim tie-break). '
          'Where both WNS >= 0 the constraint was met, so the WNS difference is not a speed difference.\n')
    print('| mode | depth | period (ns) | area v2 | area v3 | area v3 - v2 | area change | WNS v2 (ps) | WNS v3 (ps) '
          '| WNS v3 - v2 (ps) | difference is |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    for (ver, mode, depth, period), r3 in sorted(by.items(), key=lambda kv: kv[0][1:]):
        r2 = by.get(('v2', mode, depth, period))
        if ver != 'v3' or r2 is None:
            continue
        da = Decimal(r3['area']) - Decimal(r2['area'])
        role = 'observed noise reference (same logic)' if mode == 1 else 'logic change (Rotate-victim)'
        print(f"| {mode} | {depth} | {r3['period']} | {r2['area']} | {r3['area']} | {da:+} "
              f"| {da / Decimal(r2['area']) * 100:+.2f}% | {r2['wns']} | {r3['wns']} "
              f"| {Decimal(r3['wns']) - Decimal(r2['wns']):+} | {role} |")


if __name__ == '__main__':
    main()
