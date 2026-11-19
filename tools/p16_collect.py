"""P16: aggregate tables of the multi-corner timing runs copied from C2 to ~/c2_results/p16/<source run>/.

Usage: python3 -I tools/p16_collect.py [root] [p15_root]   (defaults ~/c2_results/p16, ~/c2_results/p15; Markdown to stdout)

Reads, per run folder and corner (tt, ss, ff): rpt/<corner>/setup/*_postRoute.summary.gz and
rpt/<corner>/hold/*_postRoute_hold.summary.gz (timeDesign 'all' column), rpt/p16_settings.txt. Checks the tt corner
against the P15 reports of the same routed database (~/c2_results/p15/<source run>/rpt/{setup,hold}/).
Derived figure (not a measurement): slow-corner period = PnR period - ss setup WNS.
Prints numbers only, never cell, instance or library names.
"""
import gzip
import re
import sys
from pathlib import Path

CORNERS = [('tt', 'typical 1.00 V 25 C, nominal RC'), ('ss', 'slow 0.90 V 125 C, SigRCmax RC'),
           ('ff', 'fast 1.10 V -40 C, SigCmin RC')]


def text(p):
    p = Path(p)
    return (gzip.open(p, 'rt', errors='replace') if p.suffix == '.gz' else open(p, errors='replace')).read()


def one(folder, pattern):
    m = sorted(Path(folder).glob(pattern))
    if len(m) != 1:
        raise SystemExit(f'{folder}: expected one {pattern}, found {len(m)}')
    return m[0]


def timing(path):
    t = text(path)
    row = {}
    for key in ('WNS', 'TNS', 'Violating Paths', 'All Paths'):
        m = re.search(rf'{key}(?: \(ns\))?:\|\s*(\S+)\s*\|', t)
        if not m:
            raise SystemExit(f'{path}: no {key}')
        row[key] = m.group(1)
    return row


def groups(path):
    """{group: {'WNS':..., 'Violating Paths':...}} for every column of the summary (all, reg2reg, default)."""
    t = text(path)
    hdr = re.search(r'\|\s*(?:Setup|Hold) mode\s*\|(.*)\|', t)
    if not hdr:
        raise SystemExit(f'{path}: no mode header')
    names = [c.strip() for c in hdr.group(1).split('|')]
    out = {n: {} for n in names}
    for key in ('WNS', 'Violating Paths'):
        m = re.search(rf'{key}(?: \(ns\))?:\|(.*)\|', t)
        for n, v in zip(names, m.group(1).split('|')):
            out[n][key] = v.strip()
    return out


def met(s, h):
    """Met = setup and hold WNS not negative (a reported -0.000 is negative) and 0 violating paths (as P15)."""
    return all(not r['WNS'].startswith('-') and r['Violating Paths'] == '0' for r in (s, h))


def design(name):
    m = re.match(r'(v\d+)_m\d+_d(\d+)_.*_pnr([0-9.]+)(?:_(\w+))?$', name)
    return m.group(1), int(m.group(2)), m.group(3), m.group(4) or ''


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / 'c2_results/p16')
    p15 = Path(sys.argv[2] if len(sys.argv) > 2 else Path.home() / 'c2_results/p15')
    runs = sorted((d for d in root.iterdir() if (d / 'rpt/p16_settings.txt').exists()),
                  key=lambda d: (design(d.name)[1], design(d.name)[2], design(d.name)[0]))
    rows, checks, derived, grp = [], [], [], []
    for d in runs:
        ver, depth, period, flow = design(d.name)
        st = text(d / 'rpt/p16_settings.txt')
        if not all(f'{c} view' in st and 'done' in st for c, _ in CORNERS):
            raise SystemExit(f'{d}: not every corner finished ({d}/rpt/p16_settings.txt)')
        at = re.search(r'analysisType (\S+)', st).group(1)
        cp = re.search(r'cppr (\S+)', st).group(1)
        res = {}
        for c, _ in CORNERS:
            s = timing(one(d / f'rpt/{c}/setup', '*_postRoute.summary.gz'))
            h = timing(one(d / f'rpt/{c}/hold', '*_postRoute_hold.summary.gz'))
            res[c] = (s, h)
            gs = groups(one(d / f'rpt/{c}/setup', '*_postRoute.summary.gz'))
            gh = groups(one(d / f'rpt/{c}/hold', '*_postRoute_hold.summary.gz'))
            cell = lambda g, n: f'{g[n]["WNS"]} ({g[n]["Violating Paths"]})' if n in g else 'n/a'
            grp.append(f'| d{depth} {ver} | {period} | {c} | {cell(gs, "reg2reg")} | {cell(gs, "default")} | '
                       f'{cell(gh, "reg2reg")} | {cell(gh, "default")} |')
            rows.append(f'| d{depth} {ver} | {period} | {flow} | {c} | {s["WNS"]} | {s["TNS"]} | {s["Violating Paths"]} | '
                        f'{h["WNS"]} | {h["TNS"]} | {h["Violating Paths"]} | {"met" if met(s, h) else "failed"} | '
                        f'{at} / {cp} |')
        ps = timing(one(p15 / d.name / 'rpt/setup', '*_postRoute.summary.gz'))
        ph = timing(one(p15 / d.name / 'rpt/hold', '*_postRoute_hold.summary.gz'))
        same = all(ps[k] == res['tt'][0][k] and ph[k] == res['tt'][1][k] for k in ('WNS', 'TNS', 'Violating Paths'))
        checks.append(f'| d{depth} {ver} | {period} | {ps["WNS"]} / {ph["WNS"]} | {res["tt"][0]["WNS"]} / '
                      f'{res["tt"][1]["WNS"]} | {"yes" if same else "no"} |')
        w = float(res['ss'][0]['WNS'])
        derived.append(f'| d{depth} {ver} | {period} | {res["ss"][0]["WNS"]} | {float(period) - w:.3f} |')
    out = ['## Timing per design and corner (timeDesign -postRoute, \'all\' path group; no re-optimisation)',
           'Corners: ' + '; '.join(f'{c} = {t}' for c, t in CORNERS) + '.',
           '| design | PnR period ns | P15 flow | corner | setup WNS ns | setup TNS ns | setup viol. paths | '
           'hold WNS ns | hold TNS ns | hold viol. paths | met (setup and hold) | analysis type / CPPR |',
           '|---|---|---|---|---|---|---|---|---|---|---|---|', *rows, '',
           '## Path groups (WNS ns, violating paths in brackets): reg2reg = register to register; default = all other',
           'paths (inputs to registers and registers to outputs, against the SDC input/output delay of 0.2 x period)',
           '| design | PnR period ns | corner | setup reg2reg | setup default | hold reg2reg | hold default |',
           '|---|---|---|---|---|---|---|', *grp, '',
           '## Typical corner against the P15 reports of the same database (setup / hold WNS ns)',
           '| design | PnR period ns | P15 | P16 tt | WNS, TNS and violating paths identical |', '|---|---|---|---|---|',
           *checks, '',
           '## Derived (not measured): period the slow corner would need = PnR period - ss setup WNS',
           'Same layout, no re-optimisation at the new period; ignores hold and any change of the clock tree.',
           '| design | PnR period ns | ss setup WNS ns | derived slow-corner period ns |', '|---|---|---|---|',
           *derived]
    print('\n'.join(out))


if __name__ == '__main__':
    main()
