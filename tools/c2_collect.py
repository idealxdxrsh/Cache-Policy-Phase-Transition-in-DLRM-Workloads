"""P12: Genus runs on C2 as one Markdown table. Library, corner and tool version are not named in the repo.

Usage: python -I tools/c2_collect.py [dir]   (dir defaults to ~/c2_results, outside the repo)
One folder per run, named <ver>_m<mode>_d<depth>_p<period_ns> as written by cadence/run_genus.csh, holding
timing.rpt, area.rpt, gates.rpt, power.rpt and constraints.sdc copied from C2. Other folders are skipped (stderr).
Every number is read from a file of that run: WNS = slack of Path 1 in timing.rpt (ps); period = create_clock -period
in constraints.sdc (must equal the folder name); Fmax = 1 / (period - WNS); area = Total Area of the top instance in
area.rpt (library area unit, which the report does not state); cells = the 'total' row of gates.rpt (must equal
Cell Count in area.rpt); power = Total of the Subtotal row in power.rpt, in its Power Unit. Depth and mode must equal
the elaborated module name in area.rpt, so a run whose parameters were not applied stops the script.
"""
import re
import sys
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
    unit = find(r'^Power Unit:\s*(\S+)', p, f'{d}/power.rpt')
    power = find(r'^\s*Subtotal\s+\S+\s+\S+\s+\S+\s+(\S+)', p, f'{d}/power.rpt')
    fmax = 1e6 / (float(period) * 1e3 - float(wns))  # MHz, from ns and ps
    return (ver, int(mode), int(depth), float(period)), [ver, mode, depth, period, f'{wns} ({status})', f'{fmax:.1f}',
                                                         area, cells, f'{power} {unit}']


def main():
    rows = []
    for d in sorted(x for x in DIR.iterdir() if x.is_dir()):
        if NAME.match(d.name):
            rows.append(row(d))
        else:
            print(f'skipped {d.name}', file=sys.stderr)
    print('# P12 Genus synthesis on C2 (v2 = tag rtl-v2-final, v3 = branch rtl-v3). '
          'Library, corner and tool version are not named in the repo.')
    print('Pre-layout: no LEF, library default wireload; power is vectorless (default switching activity); '
          'I/O delay 0.2 x period, clock uncertainty 0. Fmax = 1 / (period - WNS).')
    print(f'Source: {DIR}/<run>/{{timing,area,gates,power}}.rpt, constraints.sdc\n')
    print('| version | mode | depth | period (ns) | WNS (ps) | Fmax (MHz) | area (lib unit) | cells | total power |')
    print('|---|---|---|---|---|---|---|---|---|')
    for _, r in sorted(rows):
        print('| ' + ' | '.join(r) + ' |')


if __name__ == '__main__':
    main()
