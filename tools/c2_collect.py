"""P12: Genus runs on C2 as Markdown tables. Technology: a commercial 28nm FD-SOI standard-cell library, typical corner.

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
Table 3 = per version, mode and depth: the tightest period with WNS >= 0, the loosest period with WNS < 0, and
Fmax = 1 / (period - WNS) of every run with WNS < 0. "non-monotonic" marks a depth where a period met timing although
a looser one failed.
Table 4 = v3 against v2 Fmax at each mode, depth and period where at least one of them has WNS < 0; differences are
computed from the unrounded Fmax.
Tables 1-4 use the normal runs only. Folders ending in _nomerge are merge-off runs (cadence/genus_lfu_nomerge.tcl);
table 5 puts each next to the normal run with the same parameters, with req_addr_grp flops and is_320 read from
<dir>/sweep_nomerge.log (written by cadence/run_nomerge.sh from each netlist.v on C2).
"""
import re
import sys
from decimal import Decimal
from pathlib import Path

DIR = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / 'c2_results'
SHOW = str(DIR).replace(str(Path.home()), '~')   # printed source path, without the home directory
NAME = re.compile(r'^(v\d+)_m(\d+)_d(\d+)_p(\d+(?:\.\d+)?)(_nomerge)?$')


def find(pattern, text, where, last=False):
    m = re.findall(pattern, text, re.M)
    if not m:
        sys.exit(f'{where}: no match for {pattern!r}')
    return m[-1] if last else m[0]


def row(d):
    ver, mode, depth, period, nomerge = NAME.match(d.name).groups()
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
    mhz = None
    if Decimal(wns) > 0:
        fmax = 'relaxed, Fmax not meaningful'
    elif Decimal(wns) == 0:
        fmax = 'met at target, Fmax not measured'
    else:
        mhz = 1e6 / (float(period) * 1e3 - float(wns))  # MHz, from ns and ps
        fmax = f'{mhz:.1f}'
    return dict(ver=ver, mode=int(mode), depth=int(depth), period=period, wns=wns, status=status, fmax=fmax, mhz=mhz,
                area=area, cells=cells, ffs=ffs, power=f'{power} {unit}', flow='merge-off' if nomerge else 'normal')


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
    nomerge = [r for r in rows if r['flow'] == 'merge-off']
    rows = [r for r in rows if r['flow'] == 'normal']
    print('# P12 Genus synthesis on C2 (v2 = tag rtl-v2-final, v3 = branch rtl-v3). '
          'Technology: a commercial 28nm FD-SOI standard-cell library, typical corner; area in library units.')
    print('Pre-layout: no LEF, library default wireload; power is vectorless (default switching activity); '
          'I/O delay 0.2 x period, clock uncertainty 0. Fmax = 1 / (period - WNS), only for WNS < 0.')
    print('Limitation: Genus ignored (* keep *) on req_addr_grp (VLOGPT-506) and merged the per-group address copies '
          'into one register, so these netlists lack the per-group fan-out split the RTL was written for.')
    print(f'Source: {SHOW}/<run>/{{timing,area,gates,power}}.rpt, constraints.sdc (raw reports, kept off the repo)\n')
    print('| version | mode | depth | period (ns) | WNS (ps) | Fmax (MHz) | area (library units) | cells | flip-flops '
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
    print('| mode | depth | period (ns) | area v2 (library units) | area v3 | area v3 - v2 | area change | WNS v2 (ps) | WNS v3 (ps) '
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

    groups = {}
    for r in rows:
        groups.setdefault((r['ver'], r['mode'], r['depth']), []).append(r)
    print('\n## Timing limit per version, mode and depth')
    print('Tightest met = smallest period with WNS >= 0; loosest failed = largest period with WNS < 0; '
          'Fmax = 1 / (period - WNS) of each failing run. Only the periods listed were run.\n')
    print('| version | mode | depth | periods run (ns) | tightest met (ns) | loosest failed (ns) '
          '| Fmax of failing runs (period ns: MHz) | note |')
    print('|---|---|---|---|---|---|---|---|')
    for (ver, mode, depth), rs in sorted(groups.items()):
        rs = sorted(rs, key=lambda r: -Decimal(r['period']))
        met = [r['period'] for r in rs if Decimal(r['wns']) >= 0]
        fail = [r for r in rs if Decimal(r['wns']) < 0]
        tight = met[-1] if met else 'none'
        loose = fail[0]['period'] if fail else 'none'
        fmaxes = '; '.join(f"{r['period']}: {r['fmax']}" for r in fail) or '-'
        note = 'non-monotonic' if met and fail and Decimal(tight) < Decimal(loose) else ''
        print(f"| {ver} | {mode} | {depth} | {', '.join(r['period'] for r in rs)} | {tight} | {loose} | {fmaxes} "
              f"| {note} |")

    print('\n## v3 against v2 Fmax at the same mode, depth and period (periods where at least one fails)')
    print('Fmax = 1 / (period - WNS) for WNS < 0; difference and change from the unrounded values. Mode 1 is the same '
          'logic in both versions, so its difference is the observed noise reference.\n')
    print('| mode | depth | period (ns) | WNS v2 (ps) | WNS v3 (ps) | Fmax v2 (MHz) | Fmax v3 (MHz) | Fmax v3 - v2 (MHz) '
          '| change | difference is |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for (ver, mode, depth, period), r3 in sorted(by.items(), key=lambda kv: kv[0][1:]):
        r2 = by.get(('v2', mode, depth, period))
        if ver != 'v3' or r2 is None or (r2['mhz'] is None and r3['mhz'] is None):
            continue
        both = r2['mhz'] is not None and r3['mhz'] is not None
        dif = f"{r3['mhz'] - r2['mhz']:+.1f}" if both else '-'
        pct = f"{(r3['mhz'] - r2['mhz']) / r2['mhz'] * 100:+.2f}%" if both else '-'
        role = 'observed noise reference (same logic)' if mode == 1 else 'logic change (Rotate-victim)'
        print(f"| {mode} | {depth} | {r3['period']} | {r2['wns']} | {r3['wns']} | {r2['fmax']} | {r3['fmax']} | {dif} "
              f"| {pct} | {role} |")

    log = DIR / 'sweep_nomerge.log'
    grp = {m[0]: (m[1], m[2]) for m in re.findall(r'(\S+_nomerge) .*?req_addr_grp_flops=(\d+) is_320=(yes|no)',
                                                  log.read_text())} if log.exists() else {}
    print('\n## Merge-off (optimize_merge_seq false on req_addr_grp_reg) next to the normal run')
    print(f'req_addr_grp flops and is_320: {SHOW}/{log.name} (req_addr_grp_reg instances in each netlist.v on C2); flip-flops: '
          'gates.rpt. Change = (merge-off - normal) / normal; Fmax change only when both have WNS < 0.\n')
    print('| version | mode | depth | period (ns) | flow | req_addr_grp flops | is_320 | WNS (ps) | Fmax (MHz) '
          '| Fmax change | area (library units) | area change | flip-flops |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in nomerge:
        n = by.get(key(r))
        if n:
            print(f"| {n['ver']} | {n['mode']} | {n['depth']} | {n['period']} | normal | - | - | {n['wns']} ({n['status']}) "
                  f"| {n['fmax']} | | {n['area']} | | {n['ffs']} |")
        g, ok = grp.get(f"{r['ver']}_m{r['mode']}_d{r['depth']}_p{r['period']}_nomerge", ('not in log', 'not in log'))
        fc = f"{(r['mhz'] - n['mhz']) / n['mhz'] * 100:+.2f}%" if n and r['mhz'] and n['mhz'] else '-'
        ac = f"{(Decimal(r['area']) - Decimal(n['area'])) / Decimal(n['area']) * 100:+.2f}%" if n else '-'
        print(f"| {r['ver']} | {r['mode']} | {r['depth']} | {r['period']} | merge-off | {g} | {ok} | {r['wns']} "
              f"({r['status']}) | {r['fmax']} | {fc} | {r['area']} | {ac} | {r['ffs']} |")


if __name__ == '__main__':
    main()
