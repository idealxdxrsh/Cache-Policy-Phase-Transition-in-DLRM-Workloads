"""P13: power from the SDF gate-level runs on C2 as one Markdown table. Library, corner and tool version are not named.

Usage: python -I tools/p13_power_table.py [dir]   (dir defaults to ~/c2_results, outside the repo)
Reads, per run folder <dir>/p13/<netlist run>_<slice>_sdf_tcf/: summary.txt (run_gls.csh: mismatching cycles, X
cycles, compared cycles), power_tcf.rpt (Genus report_power with the run's TCF read by read_tcf -tcf_instance gl:
Subtotal row, in its Power Unit) and sdb_annotation.rpt (report_sdb_annotation: Asserted% of driver nets, flop
outputs and primary ports). The P12 vectorless power of the same netlist is the Subtotal Total of
<dir>/<netlist run>/power.rpt (Genus report_power at synthesis, default switching activity).
Energy per request = total power x cycles x 0.8 ns / 200,000, given only when the driver-net coverage is >= 90%.
Every result: path delays annotated, timing checks not annotated (conditional checks in the cell models).
"""
import re
import sys
from pathlib import Path

DIR = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / 'c2_results'
NAME = re.compile(r'^(v\d+_m\d+_d\d+_p[\d.]+_nomerge)_(row0|row1M)_sdf_tcf$')
MIN_COVERAGE = 90.0


def find(pattern, text, where):
    m = re.search(pattern, text, re.M)
    if not m:
        sys.exit(f'{where}: no match for {pattern!r}')
    return m.groups()


def subtotal(path):
    t = path.read_text()
    unit, = find(r'^Power Unit:\s*(\S+)', t, path)
    return find(r'^\s*Subtotal\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', t, path), unit


def main():
    rows = []
    for d in sorted((DIR / 'p13').iterdir()):
        m = NAME.match(d.name)
        if not m:
            continue
        run, sl = m.groups()
        s = (d / 'summary.txt').read_text()
        mism, cyc = find(r'mismatching_cycles=(\d+)', s, d)[0], find(r'^gls_c2 .*\bcycles=(\d+)', s, d)[0]
        xg, xr = find(r'x_cycles_netlist=(\d+) x_cycles_rtl=(\d+)', s, d)
        (leak, internal, switching, total), unit = subtotal(d / 'power_tcf.rpt')
        a = (d / 'sdb_annotation.rpt').read_text()
        nets, = find(r'^\s*Driver nets\s.*?\s([\d.]+)%\s*$', a, d / 'sdb_annotation.rpt')
        flops, = find(r'^\s*Flop\s.*?\s([\d.]+)%\s*$', a, d / 'sdb_annotation.rpt')
        ports = '/'.join(find(r'^\s*Inputs\s.*?\s([\d.]+)%\s*$', a, d) + find(r'^\s*Outputs\s.*?\s([\d.]+)%\s*$', a, d))
        (_, _, _, vtotal), vunit = subtotal(DIR / run / 'power.rpt')
        if float(nets) >= MIN_COVERAGE:
            scale = {'W': 1.0, 'mW': 1e-3, 'uW': 1e-6, 'nW': 1e-9}[unit]
            energy = f'{float(total) * scale * int(cyc) * 0.8e-9 / 200000 * 1e12:.3f} pJ'
        else:
            energy = f'not computed (driver-net coverage {nets}% < {MIN_COVERAGE:.0f}%)'
        rows.append(f'| {run} | {sl} | {mism} | {xg}/{xr} | {cyc} | {total} {unit} | {internal} | {switching} | {leak} '
                    f'| {nets}% | {flops}% | {ports}% | {energy} | {vtotal} {vunit} |')
    print('# P13 power from SDF gate-level activity (C2). Library, corner and tool version are not named in the repo.')
    print('Path delays annotated, timing checks not annotated (conditional checks in the cell models). Clock 0.8 ns, '
          'activity: TCF of the netlist instance (xmsim dumptcf -eot), read with read_tcf; power: report_power.')
    print(f'Source: {DIR}/p13/<run>_<slice>_sdf_tcf/{{summary.txt,power_tcf.rpt,sdb_annotation.rpt}}; '
          f'P12 vectorless: {DIR}/<run>/power.rpt\n')
    print('| netlist run | slice | mismatching cycles | X cycles (netlist/RTL) | cycles | total power | internal | switching '
          '| leakage | driver nets annotated | flop outputs annotated | ports in/out annotated | energy per request '
          '| P12 vectorless total |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    print('\n'.join(rows))


if __name__ == '__main__':
    main()
