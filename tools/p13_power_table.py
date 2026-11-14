"""P13: gate-level simulation and power of the merge-off netlists on C2 as Markdown tables. Technology: a commercial
28nm FD-SOI standard-cell library, typical corner.

Usage: python -I tools/p13_power_table.py [dir]   (dir defaults to ~/c2_results, outside the repo)
Run folders <dir>/p13/<netlist run>_<slice>_<zero|sdf_tcf>/ written by cadence/run_gls.csh: summary.txt (mismatching
and X cycles, compared cycles, netlist hit log against the P9 (v2) / P10 (v3) RTL log, SDF annotation statistics).
The SDF folders also hold power_tcf.rpt (Genus report_power with the run's TCF, read_tcf -tcf_instance gl: Subtotal
and category rows, in its Power Unit) and sdb_annotation.rpt (report_sdb_annotation: Asserted% of driver nets, flop
outputs and primary ports). SDF-variant smoke runs: <run>_row0_sdf_n10000_delays_<a|b|c>/summary.txt. P12
vectorless power: Subtotal Total of <dir>/<netlist run>/power.rpt.
Energy per request = total power x cycles x 0.8 ns / 200,000; where the driver-net coverage is below 90% it carries
the LABEL below.
"""
import re
import sys
from pathlib import Path

DIR = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / 'c2_results'
SHOW = str(DIR).replace(str(Path.home()), '~')
RUNS = [(v, s) for v in ('v2', 'v3') for s in ('row0', 'row1M')]
NET = '{}_m0_d256_p0.8_nomerge'
MIN_COVERAGE = 90.0
LABEL = ('path delays annotated, timing checks not annotated; flip-flop outputs and ports 100% annotated, '
         'combinational driver nets 42% annotated; combinational logic is 1.5 to 2.2% of total power, so its '
         'uncertainty bounds total power by about +/-2.2%')


def find(pattern, text, where):
    m = re.search(pattern, text, re.M)
    if not m:
        sys.exit(f'{where}: no match for {pattern!r}')
    return m.groups()


def lockstep(path):
    s = path.read_text()
    return dict(cycles=int(find(r'^gls_c2 .*\bcycles=(\d+)', s, path)[0]),
                mism=find(r'mismatching_cycles=(\d+)', s, path)[0],
                x='/'.join(find(r'x_cycles_netlist=(\d+) x_cycles_rtl=(\d+)', s, path)),
                passed='PASSED' if 'GLS SLICE LOCKSTEP PASSED' in s else 'FAILED',
                hits=' of '.join(find(r'hits_gl lines (\d+) differing (\d+)', s, path)[::-1]),
                wall=find(r'xrun exit=\d+ wall_s=(\d+)', s, path)[0],
                paths=re.search(r'No\. of Pathdelays = \d+.*Annotated = ([\d.]+%) \((\d+/\d+)\)', s),
                checks=re.search(r'No\. of Tchecks += \d+.*Annotated = ([\d.]+%) \((\d+/\d+)\)', s))


def rows(path):
    t = path.read_text()
    unit, = find(r'^Power Unit:\s*(\S+)', t, path)
    get = lambda name: find(rf'^\s*{name}\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', t, path)
    return get('Subtotal'), get('register'), get('logic'), unit


def ann(a, name, where):
    return find(rf'^\s*{name}\s.*?\s([\d.]+)%\s*$', a, where)[0]


def main():
    P = DIR / 'p13'
    print('# P13 gate-level simulation and power of v2/v3_m0_d256_p0.8_nomerge (C2). Technology: a commercial 28nm '
          'FD-SOI standard-cell library, typical corner.')
    print(f'Source: {SHOW}/p13/<run>/{{summary.txt,power_tcf.rpt,sdb_annotation.rpt}} (raw reports, kept off the repo); '
          f'P12 vectorless: {SHOW}/<netlist run>/power.rpt. Clock 0.8 ns; 200,000 requests per slice; lockstep with the '
          'RTL, every cycle.\n')
    print('## Lockstep (zero-delay and SDF; SDF inputs 160 ps after the clock edge)\n')
    print('| netlist | slice | cycles | zero-delay: mismatching; X (netlist/RTL) cycles | SDF: mismatching; X (netlist/RTL) cycles | netlist hit log '
          'vs RTL log (zero / SDF) | SDF path delays annotated | SDF timing checks annotated | wall s (zero / SDF) |')
    print('|---|---|---|---|---|---|---|---|---|')
    L = {}
    for v, s in RUNS:
        z, d = lockstep(P / f'{NET.format(v)}_{s}_zero/summary.txt'), lockstep(P / f'{NET.format(v)}_{s}_sdf_tcf/summary.txt')
        if z['cycles'] != d['cycles']:
            sys.exit(f'{v} {s}: zero-delay and SDF cycle counts differ')
        L[v, s] = d
        print(f"| {v} | {s} | {d['cycles']} | {z['mism']}; {z['x']} ({z['passed']}) | {d['mism']}; {d['x']} "
              f"({d['passed']}) | {z['hits']} / {d['hits']} differ | {d['paths'].group(2)} ({d['paths'].group(1)}) "
              f"| {d['checks'].group(2)} ({d['checks'].group(1)}) | {z['wall']} / {d['wall']} |")
    print('\nTiming checks are not annotated: the cell models\' checks are conditional and the SDF has no COND entries.')
    print('\n## SDF variants tried for timing-check annotation (v3, row0, first 10,000 requests)\n')
    print('| write_sdf variant | path delays annotated | timing checks annotated | mismatching cycles |')
    print('|---|---|---|---|')
    for k, opts in (('a', 'Genus defaults'), ('b', '-setuphold/-recrem merge_when_paired -edges check_edge'),
                    ('c', 'b + -nosplit_timing_check')):
        r = lockstep(P / f'{NET.format("v3")}_row0_sdf_n10000_delays_{k}/summary.txt')
        print(f"| {k}: {opts} | {r['paths'].group(2)} ({r['paths'].group(1)}) | {r['checks'].group(2)} "
              f"({r['checks'].group(1)}) | {r['mism']} |")
    print('\n## Power (report_power with each SDF run\'s TCF) and energy per request = total x cycles x 0.8 ns / 200,000\n')
    print('| netlist | slice | total | internal | switching | leakage | register share | logic share | driver nets '
          'annotated | flop outputs; ports in/out annotated | energy per request | P12 vectorless total |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|')
    E, T, low = {}, {}, False
    for v, s in RUNS:
        d = P / f'{NET.format(v)}_{s}_sdf_tcf'
        (leak, internal, switching, total), reg, logic, unit = rows(d / 'power_tcf.rpt')
        a = (d / 'sdb_annotation.rpt').read_text()
        nets, flops = ann(a, 'Driver nets', d), ann(a, 'Flop', d)
        ports = '%/'.join((ann(a, 'Inputs', d), ann(a, 'Outputs', d))) + '%'
        vt, vu = rows(DIR / NET.format(v) / 'power.rpt')[0][3], rows(DIR / NET.format(v) / 'power.rpt')[3]
        scale = {'W': 1.0, 'mW': 1e-3, 'uW': 1e-6, 'nW': 1e-9}[unit]
        E[v, s] = float(total) * scale * L[v, s]['cycles'] * 0.8e-9 / 200000 * 1e12
        T[v, s] = float(total) * scale
        mark = '' if float(nets) >= MIN_COVERAGE else ' *'
        low |= bool(mark)
        print(f"| {v} | {s} | {total} {unit} | {internal} | {switching} | {leak} | {float(reg[3]) / float(total) * 100:.2f}% "
              f"| {float(logic[3]) / float(total) * 100:.2f}% | {nets}% | {flops}%; {ports} | {E[v, s]:.2f} pJ{mark} "
              f"| {vt} {vu} |")
    if low:
        print(f'\n\\* Driver-net coverage below {MIN_COVERAGE:.0f}%: {LABEL}.')
    print('\n## v3 against v2 per slice\n')
    print('| slice | energy per request v2 -> v3 | change | total power change | cycles change |')
    print('|---|---|---|---|---|')
    for s in ('row0', 'row1M'):
        e2, e3, c2, c3 = E['v2', s], E['v3', s], L['v2', s]['cycles'], L['v3', s]['cycles']
        print(f"| {s} | {e2:.2f} -> {e3:.2f} pJ | {e3 - e2:+.2f} pJ ({(e3 - e2) / e2 * 100:+.2f}%) "
              f"| {(T['v3', s] - T['v2', s]) / T['v2', s] * 100:+.2f}% | {(c3 - c2) / c2 * 100:+.2f}% |")


if __name__ == '__main__':
    main()
