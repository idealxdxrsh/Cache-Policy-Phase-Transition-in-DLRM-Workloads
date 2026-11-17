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
    print('| run | period ns | setup WNS ns | setup TNS ns | setup viol. paths | hold WNS ns | hold TNS ns | '
          'hold viol. paths | DRC | conn. problems all nets | conn. problems 4 PG nets | 4 PG nets metal only | '
          'well-tap rule um | well-tap viol. full core | well-tap viol. inner rows | core area | '
          'logic cell area | logic insts | phys.-only insts | power total | internal | switching | leakage | '
          'activity |')
    print('|' + '---|' * 24)
    for r in runs:
        m = re.match(r'(.+)_pnr([\d.]+)$', r.name)
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
        print(f"| {m.group(1)} | {m.group(2)} | {s['WNS']} | {s['TNS']} | {s['Violating Paths']} | {h['WNS']} | "
              f"{h['TNS']} | {h['Violating Paths']} | {drc(rp / 'drc.rpt')} | {ca}{' (' + cad + ')' if ca else ''} | "
              f"{cp}{' (' + cpd + ')' if cp else ''} | {cm}{' (' + cmd + ')' if cm else ''} | {rule} | "
              f"{welltap(rp / 'welltap.rpt')} | {welltap(rp / 'welltap_inner.rpt')} | {float(mt['core_area_um2']):.1f} | "
              f"{float(mt['logic_cell_area_um2']):.1f} | {mt['insts_logic']} | {mt['insts_physical_only']} | "
              f"{pw['Total']:.4f} {re.sub(r'^1(?=[a-zA-Z])', '', unit)} | {pw['Internal']:.4f} | {pw['Switching']:.4f} | {pw['Leakage']:.5f} | "
              f"{act} |")
    print()
    print('## DRC and PG-connectivity breakdown')
    print('| run | period ns | DRC total | metal shorts PG special wire vs cell pin | other DRC | '
          'instances with unconnected PG terminals | instances in shorts | instances in both |')
    print('|' + '---|' * 8)
    for r in runs:
        m = re.match(r'(.+)_pnr([\d.]+)$', r.name)
        if not m:
            continue
        rp = r / 'rpt'
        sh, other = drc_split(rp / 'drc.rpt')
        total = drc(rp / 'drc.rpt')
        if sh + other != total:
            raise SystemExit(f'{rp}/drc.rpt: {sh}+{other} != total {total}')
        po, si = pg_open_insts(rp / 'conn_pg.rpt'), short_insts(rp / 'drc.rpt')
        print(f"| {m.group(1)} | {m.group(2)} | {total} | {sh} | {other} | {len(po)} | {len(si)} | {len(po & si)} |")


if __name__ == '__main__':
    main()
