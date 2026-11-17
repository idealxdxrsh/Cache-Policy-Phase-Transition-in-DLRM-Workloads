"""P15: aggregate table of the Innovus place-and-route runs copied from C2 to ~/c2_results/p15/<run>_pnr<period>/.

Usage: python3 -I tools/p15_collect.py [root]        (root default ~/c2_results/p15; prints Markdown to stdout)

Reads, per run folder: rpt/setup/*_postRoute.summary.gz and rpt/hold/*_postRoute_hold.summary.gz (timeDesign
'all' column), rpt/drc.rpt (verify_drc), rpt/conn.rpt (verifyConnectivity, all nets) and rpt/conn_pg.rpt (the four
power nets), rpt/power.rpt (report_power, Innovus default activity: 0.2 for primary inputs and sequential outputs),
rpt/conn_pg_metal.rpt (the same with -noSoftPGConnect: metal only), rpt/welltap.rpt and rpt/welltap_inner.rpt
(verifyWellTap, full core and without the bottom and top end-cap rows) with the rule value in rpt/welltap_rule.txt
(written when the run is copied, from the run's command record), rpt/metrics.txt (written by cadence/pnr/stageB.tcl).
Second table: verify_drc violations split into PG special-wire shorts with cell pins and the rest, and the number of
distinct instances with an unconnected power/ground terminal in rpt/conn_pg.rpt.
Prints numbers only, never cell, instance or library names.
"""
import gzip
import re
import sys
from pathlib import Path


def text(p):
    p = Path(p)
    return (gzip.open(p, 'rt', errors='replace') if p.suffix == '.gz' else open(p, errors='replace')).read()


def one(folder, pattern):
    m = sorted(folder.glob(pattern))
    if len(m) != 1:
        raise SystemExit(f'{folder}: expected one {pattern}, found {len(m)}')
    return m[0]


def timing(path):
    t = text(path)
    row = {}
    for key in ('WNS', 'TNS', 'Violating Paths', 'All Paths'):
        m = re.search(rf'{key}(?: \(ns\))?:\|\s*(\S+)\s*\|', t)
        row[key] = m.group(1) if m else 'n/a'
    return row


def problems(path):
    t = text(path)
    if re.search(r'Found no problems or warnings', t):
        return 0, ''
    codes = re.findall(r'^\s*(\d+) Problem\(s\) \((IMPVFC-\d+)\)', t, re.M)
    if not codes:
        raise SystemExit(f'{path}: no summary found')
    return sum(int(n) for n, _ in codes), ' '.join(f'{c}:{n}' for n, c in codes)


def drc(path):
    t = text(path)
    if 'No DRC violations were found' in t:
        return 0
    m = re.search(r'Total Violations\s*:\s*(\d+)', t)
    if not m:
        raise SystemExit(f'{path}: no DRC total found')
    return int(m.group(1))


def drc_split(path):
    """(PG special-wire metal shorts, other DRC) from verify_drc; counts only."""
    t = text(path)
    shorts = len(re.findall(r'^SHORT: .*Special Wire of Net \S+ & Pin of Cell', t, re.M))
    viols = len(re.findall(r'^\S+: \(', t, re.M))
    return shorts, viols - shorts


def pre_extra(rp):
    """Setup / hold WNS before the extra optDesign -postRoute -setup (rpt/pre_extra/, target-slack flow only)."""
    d = rp / 'pre_extra'
    if not d.exists():
        return '-'
    return (f"{timing(one(d / 'setup', '*_postRoute.summary.gz'))['WNS']} / "
            f"{timing(one(d / 'hold', '*_postRoute_hold.summary.gz'))['WNS']}")


def other_drc_types(path):
    """verify_drc violations other than PG special-wire shorts, as 'type layer: count' (no net or cell names)."""
    out = {}
    for kind, rule, what, layer in re.findall(r'^(\w+): \( ([^)]+?) \) (.*?) of Net .*?\(\s*(M\d+)\s*\)\s*$', text(path), re.M):
        if kind == 'SHORT' and what.startswith('Special Wire'):
            continue
        k = f'{rule} {layer}'
        out[k] = out.get(k, 0) + 1
    return '; '.join(f'{k}: {v}' for k, v in sorted(out.items())) or '-'


def pg_open_insts(path):
    """Distinct instances with an unconnected power/ground terminal (IMPVFC-96); used for counts only."""
    return set(re.findall(r'Pin Pin: ([^/\s]+)/\S+; Direction: INOUT; Use: (?:GROUND|POWER);: has an unconnected', text(path)))


def short_insts(path):
    """Distinct instances whose pins short a PG special wire in verify_drc; used for counts only."""
    return set(re.findall(r'^SHORT: .*Special Wire of Net \S+ & Pin of Cell (\S+)', text(path), re.M))


def welltap(path):
    m = re.search(r'Found (\d+) violations? in total', text(path))
    if not m:
        raise SystemExit(f'{path}: no verifyWellTap total found')
    return int(m.group(1))


def power(path):
    t = text(path)
    unit = re.search(r'Power Units = (\S+)', t).group(1)
    vals = {k: float(re.search(rf'^Total {k} Power:\s+(\S+)', t, re.M).group(1))
            for k in ('Internal', 'Switching', 'Leakage')}
    vals['Total'] = float(re.search(r'^Total Power:\s+(\S+)', t, re.M).group(1))
    seq = re.search(r'Sequential Element Activity: (\S+)', t).group(1)
    pi = re.search(r'Primary Input Activity: (\S+)', t).group(1)
    return unit, vals, f'default (seq {seq}, PI {pi})'


def flow(m):
    """Folder suffix -> flow label: none = first P15 flow (multi-row cells allowed); nodv = multi-row cells dont_use."""
    return {None: 'multi-row allowed', 'nodv': 'multi-row dont_use',
            'nodveco2': 'multi-row dont_use + 2nd ecoRoute',
            'nodvts': 'multi-row dont_use + 2nd ecoRoute + setup target slack 0.03 + extra postRoute setup opt'
            }.get(m.group(3), m.group(3))


def multirow(rp, mt):
    """Multi-row logic instances in the routed design: metrics.txt (new flow) or rpt/diag_census.txt (diagnosis)."""
    if 'insts_multirow' in mt:
        return mt['insts_multirow']
    census = rp / 'diag_census.txt'
    if census.exists():
        return str(sum(int(n) for n in re.findall(r'^count (\d+) rows=', census.read_text(), re.M)))
    return 'n/a'


def metrics(path):
    out = {}
    for line in text(path).splitlines():
        k, _, v = line.partition(' ')
        out[k] = v.strip()
    return out


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '~/c2_results/p15').expanduser()
    runs = sorted(p.parent.parent for p in root.glob('*/rpt/metrics.txt'))
    if not runs:
        raise SystemExit(f'no runs under {root}')
    print('| run | flow | period ns | multi-row insts | setup WNS ns | setup TNS ns | setup viol. paths | hold WNS ns | hold TNS ns | '
          'hold viol. paths | DRC | conn. problems all nets | conn. problems 4 PG nets | 4 PG nets metal only | '
          'well-tap rule um | well-tap viol. full core | well-tap viol. inner rows | core area | '
          'logic cell area | logic insts | phys.-only insts | power total | internal | switching | leakage | '
          'activity |')
    print('|' + '---|' * 26)
    for r in runs:
        m = re.match(r'(.+)_pnr([\d.]+)(?:_([A-Za-z0-9]+))?$', r.name)
        if not m:
            continue
        rp = r / 'rpt'
        s = timing(one(rp / 'setup', '*_postRoute.summary.gz'))
        h = timing(one(rp / 'hold', '*_postRoute_hold.summary.gz'))
        ca, cad = problems(rp / 'conn.rpt')
        cp, cpd = problems(rp / 'conn_pg.rpt')
        cm, cmd = problems(rp / 'conn_pg_metal.rpt')
        rule = (rp / 'welltap_rule.txt').read_text().split()[0]
        unit, pw, act = power(rp / 'power.rpt')
        mt = metrics(rp / 'metrics.txt')
        print(f"| {m.group(1)} | {flow(m)} | {m.group(2)} | {multirow(rp, mt)} | {s['WNS']} | {s['TNS']} | {s['Violating Paths']} | {h['WNS']} | "
              f"{h['TNS']} | {h['Violating Paths']} | {drc(rp / 'drc.rpt')} | {ca}{' (' + cad + ')' if ca else ''} | "
              f"{cp}{' (' + cpd + ')' if cp else ''} | {cm}{' (' + cmd + ')' if cm else ''} | {rule} | "
              f"{welltap(rp / 'welltap.rpt')} | {welltap(rp / 'welltap_inner.rpt')} | {float(mt['core_area_um2']):.1f} | "
              f"{float(mt['logic_cell_area_um2']):.1f} | {mt['insts_logic']} | {mt['insts_physical_only']} | "
              f"{pw['Total']:.4f} {re.sub(r'^1(?=[a-zA-Z])', '', unit)} | {pw['Internal']:.4f} | {pw['Switching']:.4f} | {pw['Leakage']:.5f} | "
              f"{act} |")
    print()
    print('## DRC and PG-connectivity breakdown')
    print('| run | flow | period ns | DRC total | metal shorts PG special wire vs cell pin | other DRC | '
          'instances with unconnected PG terminals | instances in shorts | instances in both | other DRC types | '
          'DRC before the 2nd ecoRoute | setup / hold WNS ns before the extra postRoute setup opt |')
    print('|' + '---|' * 12)
    for r in runs:
        m = re.match(r'(.+)_pnr([\d.]+)(?:_([A-Za-z0-9]+))?$', r.name)
        if not m:
            continue
        rp = r / 'rpt'
        sh, other = drc_split(rp / 'drc.rpt')
        total = drc(rp / 'drc.rpt')
        if sh + other != total:
            raise SystemExit(f'{rp}/drc.rpt: {sh}+{other} != total {total}')
        po, si = pg_open_insts(rp / 'conn_pg.rpt'), short_insts(rp / 'drc.rpt')
        print(f"| {m.group(1)} | {flow(m)} | {m.group(2)} | {total} | {sh} | {other} | {len(po)} | {len(si)} | {len(po & si)} | "
              f"{other_drc_types(rp / 'drc.rpt')} | "
              f"{drc(rp / 'drc_pass1.rpt') if (rp / 'drc_pass1.rpt').exists() else '-'} | {pre_extra(rp)} |")

    diagnosis(runs)
    fix_table(runs)
    bracket(runs)


def bracket(runs):
    """Met = setup WNS >= 0 and hold WNS >= 0 (timeDesign 'all'); fixed-flow runs only (no multi-row cells)."""
    res = {}
    for r in runs:
        m = re.match(r'(.+)_pnr([\d.]+)(?:_([A-Za-z0-9]+))?$', r.name)
        if not m or m.group(3) not in ('nodv', 'nodveco2', 'nodvts') or '_d256_' not in m.group(1):
            continue
        rp = r / 'rpt'
        s = timing(one(rp / 'setup', '*_postRoute.summary.gz'))
        h = timing(one(rp / 'hold', '*_postRoute_hold.summary.gz'))
        met = float(s['WNS']) >= 0 and float(h['WNS']) >= 0
        res.setdefault(m.group(1), []).append((float(m.group(2)), met, s['WNS'], h['WNS'], m.group(3)))
    if not res:
        return
    print()
    print('## Met/failed bracket per version (fixed flows; met = setup and hold WNS >= 0)')
    print('| run | flows | periods run ns (setup WNS / hold WNS ns) | tightest met ns | loosest failed ns | monotonic |')
    print('|' + '---|' * 6)
    groups = {}
    for run, rows in res.items():
        groups.setdefault((run, 'all fixed flows'), []).extend(rows)
        groups.setdefault((run, 'target-slack flow (nodvts) only'), []).extend(x for x in rows if x[4] == 'nodvts')
    for (run, fl), rows in sorted(groups.items()):
        if not rows:
            continue
        rows.sort()
        met = [p for p, ok, *_ in rows if ok]
        failed = [p for p, ok, *_ in rows if not ok]
        tm = min(met) if met else None
        lf = max(failed) if failed else None
        mono = 'yes' if tm is None or lf is None or lf < tm else 'no'
        runs_s = '; '.join(f"{p} {t or ''} {'met' if ok else 'failed'} ({sw} / {hw})" for p, ok, sw, hw, t in rows)
        print(f"| {run} | {fl} | {runs_s} | {tm if tm is not None else 'none'} | {lf if lf is not None else 'none'} | {mono} |")


def fix_table(runs):
    """rpt/multirow.txt of the fixed flow (stageA.tcl): multi-row library cells set dont_use, netlist instances resized."""
    rows = []
    for r in runs:
        f = r / 'rpt' / 'multirow.txt'
        if not f.exists():
            continue
        m = re.match(r'(.+)_pnr([\d.]+)(?:_([A-Za-z0-9]+))?$', r.name)
        kv = dict(l.split() for l in f.read_text().splitlines() if l.strip())
        rows.append(f"| {m.group(1)} | {m.group(2)} | {kv['multirow_libcells']} | {kv['multirow_insts_netlist']} | "
                    f"{kv['multirow_insts_swapped']} | {kv['multirow_insts_left']} | "
                    f"{metrics(r / 'rpt' / 'metrics.txt').get('insts_multirow', 'n/a')} |")
    if rows:
        print()
        print('## Fix: multi-row cells dont_use, netlist multi-row instances resized (rpt/multirow.txt, metrics.txt)')
        print('| run | period ns | multi-row library cells set dont_use | multi-row insts in netlist | resized to single-row | '
              'left | multi-row insts after route |')
        print('|' + '---|' * 7)
        for row in rows:
            print(row)


def diagnosis(runs):
    """Names-free counts from cadence/pnr/diag_shorts.tcl + run_diag.csh (rpt/diag_*.txt) of the first-flow runs."""
    rows = []
    for r in runs:
        rp = r / 'rpt'
        if not (rp / 'diag_census.txt').exists():
            continue
        m = re.match(r'(.+)_pnr([\d.]+)(?:_([A-Za-z0-9]+))?$', r.name)
        census = (rp / 'diag_census.txt').read_text()
        kv = dict(re.findall(r'^(\w+) (\d+)$', census, re.M))
        classes = re.findall(r'^count (\d+) rows=(\S+) master_site_is_row_site=(\d) bottom_row_orient=(\S+) '
                             r'inst_orient=(\S+) in_shorts=(\d)$', census, re.M)
        n_multi = sum(int(c[0]) for c in classes)
        n_multi_short = sum(int(c[0]) for c in classes if c[5] == '1')
        heights = sorted({c[1] for c in classes}) or ['-']
        on_own_site = sum(int(c[0]) for c in classes if c[2] == '1')
        orients = {}
        for c in classes:
            orients[f'{c[3]} row/{c[4]}'] = orients.get(f'{c[3]} row/{c[4]}', 0) + int(c[0])
        insts = [l.split()[0] for l in (rp / 'diag_insts.txt').read_text().splitlines() if l.strip()]
        pres = {}
        for db in ('place', 'cts', 'route'):
            pres[db] = {a: b == '1' for a, b in (l.split() for l in (rp / f'diag_present_{db}.txt').read_text().splitlines() if l.strip())}
        in_nl = set((rp / 'diag_in_netlist.txt').read_text().split())
        first = {'netlist name': 0, 'place_opt': 0, 'CTS + postCTS opt': 0, 'postRoute opt': 0}
        for n in insts:
            if n in in_nl:
                first['netlist name'] += 1
            elif pres['place'].get(n):
                first['place_opt'] += 1
            elif pres['cts'].get(n):
                first['CTS + postCTS opt'] += 1
            else:
                first['postRoute opt'] += 1
        prefixes = {}
        for n in insts:
            k = re.sub(r'_?\d+(_\d+)?$', '', n)
            prefixes[k] = prefixes.get(k, 0) + 1
        rows.append(f"| {m.group(1)} | {m.group(2)} | {len(insts)} | {kv.get('multirow_masters_used')} | "
                    f"{kv.get('single_row_other_site_masters_used')} | {kv.get('row_sites')} | {n_multi} | {n_multi_short} | "
                    f"{', '.join(heights)} | {on_own_site} of {n_multi} | "
                    f"{'; '.join(f'{k} {v}' for k, v in sorted(orients.items())) or '-'} | "
                    f"{'; '.join(f'{k} {v}' for k, v in first.items())} | "
                    f"{'; '.join(f'{k} {v}' for k, v in sorted(prefixes.items())) or '-'} |")
    if not rows:
        return
    print()
    print('## Diagnosis of the PG-rail shorts (first flow; route.enc, place.enc, cts.enc and the Genus netlist)')
    print('| run | period ns | shorting insts | multi-row masters used | single-row other-site masters used | row sites | '
          'multi-row insts | of which shorting | height rows | on a row of their own site | row orient/inst orient | '
          'first present (netlist name = in the Genus netlist by name) | name prefix |')
    print('|' + '---|' * 13)
    for row in rows:
        print(row)


if __name__ == '__main__':
    main()
