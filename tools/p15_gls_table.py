"""P15: post-route gate-level simulation tables (Markdown) from the runs copied to ~/c2_results/p15/gls/.

Usage: python3 -I tools/p15_gls_table.py [dir]      (dir default ~/c2_results/p15/gls)

Run folders <run>_<slice>_<zero|sdf>[_n<nreq>]_pnr<period>[_<variant>]/summary.txt, written by cadence/run_gls.csh with
the P15 overrides (netlist and SDF exported from the routed design by cadence/pnr/export_gls.tcl, clock period of the
place-and-route run). Export files <run>_pnr<period>_export/check.txt (physical-only instances left in the netlist, SDF
variants written) and sdf_counts.txt (number of each SDF construct in the SDF used). Power: <run>_<slice>_sdf_pnr<p>_tcf/
power_tcf.rpt and sdb_annotation.rpt (cadence/run_power.csh: Genus report_power with the routed netlist, the run's SDC,
the Innovus SPEF and the TCF of that SDF run; report_sdb_annotation for activity coverage). Energy per request =
total power x cycles x clock period / 200,000. Prints numbers only.
"""
import re
import sys
from pathlib import Path


def get(pat, s, where, cast=str):
    m = re.search(pat, s, re.M)
    if not m:
        raise SystemExit(f'{where}: no match for {pat!r}')
    return cast(m.group(1)) if m.lastindex == 1 else tuple(cast(g) for g in m.groups())


def annot(s, kind, where):
    """'annotated/total (pct%)' from the xrun SDF statistics line of kind Pathdelays or Tchecks."""
    m = re.search(rf'No\. of {kind}\s*=\s*(\d+).*?Annotated = ([\d.]+)% \((\d+)/(\d+)\)', s)
    if not m:
        raise SystemExit(f'{where}: no SDF statistics for {kind}')
    return f'{m.group(3)}/{m.group(4)} ({m.group(2)}%)'


def prows(path):
    t = path.read_text()
    unit = get(r'^Power Unit:\s*(\S+)', t, path)
    g = lambda name: get(rf'^\s*{name}\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', t, path)
    return g('Subtotal'), g('register'), g('logic'), g('clock'), unit


def ann(a, name, where):
    return get(rf'^\s*{name}\s.*?\s([\d.]+)%\s*$', a, where)


def power(root):
    E, T, C, out = {}, {}, {}, []
    for v in ('v2', 'v3'):
        for sl in ('row0', 'row1M'):
            d = next(iter(sorted(root.glob(f'{v}_m0_d256_p0.8_nomerge_{sl}_sdf_pnr*_tcf'))), None)
            if d is None or not (d / 'power_tcf.rpt').exists():
                return
            per = float(re.search(r'_pnr([\d.]+)_tcf$', d.name).group(1))
            sm = (d / 'summary.txt').read_text()
            cyc = get(r'period_ps=\d+ in_ps=\d+ cycles=(\d+)', sm, d, int)
            ok = 'passed' if 'GLS SLICE LOCKSTEP PASSED' in sm else 'FAILED'
            (leak, internal, switching, total), reg, logic, clk, unit = prows(d / 'power_tcf.rpt')
            a = (d / 'sdb_annotation.rpt').read_text()
            nets, flops = ann(a, 'Driver nets', d), ann(a, 'Flop', d)
            ports = f"{ann(a, 'Inputs', d)}% / {ann(a, 'Outputs', d)}%"
            scale = {'W': 1.0, 'mW': 1e-3, 'uW': 1e-6, 'nW': 1e-9}[unit]
            E[v, sl] = float(total) * scale * cyc * per * 1e-9 / 200000 * 1e12
            T[v, sl], C[v, sl] = float(total) * scale, cyc
            sp = (d / 'spef_stats.txt').read_text()
            spef = (f"{get(r'Total number of nets: (\d+)', sp, d)} nets, "
                    f"{get(r'Number of nets cannot be annotated: (\d+)', sp, d)} not annotated")
            out.append(f"| {v} | {sl} | {per} | {spef} | {total} {unit} | {internal} | {switching} | {leak} | "
                       f"{float(reg[3]) / float(total) * 100:.2f}% | {float(clk[3]) / float(total) * 100:.2f}% | "
                       f"{float(logic[3]) / float(total) * 100:.2f}% | "
                       f"{nets}% | {flops}% | {ports} | {cyc} | {ok} | {E[v, sl]:.2f} pJ |")
    print()
    print('## Post-route power (typical corner; path delays annotated, timing checks not annotated): report_power with '
          'the routed netlist, SDC, Innovus SPEF and the TCF of the SDF run')
    print('| netlist | slice | period ns | SPEF read (read_spef statistics) | total | internal | switching | leakage | register share | '
          'clock (clock tree) share | logic '
          '(combinational) share = uncertainty bound | driver nets annotated | flop outputs annotated | '
          'ports in / out annotated | cycles | lockstep (SDF+TCF run) | energy per request |')
    print('|' + '---|' * 17)
    print('\n'.join(out))
    print()
    print('## v3 against v2 per slice (1.1 ns, both meet setup and hold)')
    print('| slice | energy per request v2 -> v3 | change | total power change | cycles change |')
    print('|---|---|---|---|---|')
    for sl in ('row0', 'row1M'):
        e2, e3 = E['v2', sl], E['v3', sl]
        print(f"| {sl} | {e2:.2f} -> {e3:.2f} pJ | {e3 - e2:+.2f} pJ ({(e3 - e2) / e2 * 100:+.2f}%) | "
              f"{(T['v3', sl] - T['v2', sl]) / T['v2', sl] * 100:+.2f}% | "
              f"{(C['v3', sl] - C['v2', sl]) / C['v2', sl] * 100:+.2f}% |")


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '~/c2_results/p15/gls').expanduser()
    rows, smoke = [], []
    for f in sorted(root.glob('*/summary.txt')):
        name = f.parent.name
        m = re.match(r'(v\d)_m0_d256_p0\.8_nomerge_(row0|row1M)_(zero|sdf)(?:_n(\d+))?_pnr([\d.]+)(?:_(\w+))?$', name)
        # the _tcf runs (SDF + activity dump for power) are listed in their own rows, mode 'sdf tcf'
        if not m:
            continue
        ver, sl, mode, nreq, per, var = m.groups()
        s = f.read_text()
        period, in_ps, cyc, req = get(r'period_ps=(\d+) in_ps=(\d+) cycles=(\d+) requests=(\d+)', s, f)
        mism = get(r'mismatching_cycles=(\d+)', s, f)
        xg, xr = get(r'x_cycles_netlist=(\d+) x_cycles_rtl=(\d+)', s, f)
        ok = 'passed' if 'GLS SLICE LOCKSTEP PASSED' in s else 'FAILED'
        hl = get(r'hits_gl lines (\d+) differing (\d+)', s, f)
        wall = get(r'wall_s=(\d+)', s, f)
        if mode == 'sdf':
            pd, tc = annot(s, 'Pathdelays', f), annot(s, 'Tchecks', f)
            tv = get(r'^timing violations: (\d+)', s, f)
        else:
            pd = tc = tv = '-'
        row = (f'| {ver} | {sl} | {mode}{" " + var if var else ""} | {per} | {period} / {in_ps} | {req} | {cyc} | '
               f'{mism} | {xg} / {xr} | {hl[1]} of {hl[0]} | {ok} | {pd} | {tc} | {tv} | {wall} |')
        (smoke if nreq else rows).append(row)
    head = ('| netlist | slice | mode | PnR period ns | clock / input delay ps | requests | cycles | mismatching cycles | '
            'X cycles netlist / RTL | netlist hit log lines differing from P9/P10 RTL log | lockstep | '
            'SDF path delays annotated | SDF timing checks annotated | timing violations | wall s |')
    sep = '|' + '---|' * 15
    print('## Post-route GLS: lockstep with the RTL, both 200,000-request slices')
    print(head)
    print(sep)
    print('\n'.join(rows))
    if smoke:
        print()
        print('## SDF variant check (v3, row0, first 10,000 requests; a = write_sdf defaults, b = SETUPHOLD/RECREM merged '
              'when paired, library check edges)')
        print(head)
        print(sep)
        print('\n'.join(smoke))
    ex = sorted(root.glob('*_export'))
    if ex:
        print()
        print('## Export from the routed design (cadence/pnr/export_gls.tcl) and constructs in the SDF used (delays_a.sdf)')
        keys = ['netlist_insts_FILL', 'netlist_insts_ENDCAP', 'netlist_insts_WT']
        ckeys = ['IOPATH', 'INTERCONNECT', 'TIMINGCHECK', 'SETUPHOLD', 'RECREM', 'WIDTH', 'COND']
        print('| run | ' + ' | '.join(k.replace('netlist_insts_', 'netlist insts ') for k in keys) + ' | SDF variants written | '
              + ' | '.join(f'SDF {k}' for k in ckeys) + ' |')
        print('|' + '---|' * (2 + len(keys) + len(ckeys)))
        for d in ex:
            c = (d / 'check.txt').read_text()
            kv = dict(re.findall(r'^(\w+) (\d+)$', c, re.M))
            var = ', '.join(re.findall(r'SDF VARIANT (\w+) OK', c)) or '-'
            sc = dict((b, a) for a, b in re.findall(r'^\s*(\d+) \((\w+)$', (d / 'sdf_counts.txt').read_text(), re.M))
            print(f'| {d.name[:-len("_export")]} | ' + ' | '.join(kv.get(k, 'n/a') for k in keys) + f' | {var} | '
                  + ' | '.join(sc.get(k, '0') for k in ckeys) + ' |')
    power(root)


if __name__ == '__main__':
    main()
