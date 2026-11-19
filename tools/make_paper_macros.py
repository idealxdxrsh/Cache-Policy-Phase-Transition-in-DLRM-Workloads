"""Generate paper/v2/macros.tex: one \\defnum{key}{shown} per number in the paper, each extracted from a committed
results file (read with `git show HEAD:<path>`, so only committed results can reach the paper).

Usage (from the repository root):
  python3 -I tools/make_paper_macros.py            write paper/v2/macros.tex
  python3 -I tools/make_paper_macros.py --check    exit 1 if macros.tex is stale, or main.tex uses an undefined key

Every definition line ends with a comment naming the source: file:line, the table row and column (or the regex),
and the full source value. Display rules (agreed with the authors, 2026-11-19):
  hit   hit rates: rounded half-up to 2 decimals; the comment keeps the full value
  raw   every other value exactly as written in the file (sign shown with a math minus)
  abs   as raw, without the sign (used where the text says "lower", "fewer", "more")
  sci   as raw, with the e-notation typeset as x 10^n (same digits)
  sub   a difference computed from the full source values, then rounded half-up to the given decimals
  min / max   the smallest / largest of several source values, shown exactly as written
A spec may list `same` cells: the generator fails unless they all equal the chosen value (used where the text says
"at every size" or "in every run").
"""
import re
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'paper/v2/macros.tex'
TEX = ROOT / 'paper/v2/main.tex'
TOK = re.compile(r'[+\-\u2212]?\d[\d,]*(?:\.\d+)?(?:e[+-]?\d+)?')
_cache = {}


def lines(path):
    if path not in _cache:
        p = subprocess.run(['git', '-C', str(ROOT), 'show', f'HEAD:{path}'], capture_output=True, text=True)
        if p.returncode:
            raise SystemExit(f'not committed: {path}')
        _cache[path] = p.stdout.splitlines()
    return _cache[path]


class Src:
    """One extracted value: token (as written), where it came from."""
    def __init__(self, tok, path, line, how):
        self.tok, self.path, self.line, self.how = tok, path, line, how

    def note(self):
        return f'{self.path}:{self.line} {self.how} = {self.tok}'


def _start(path, after):
    ls = lines(path)
    i = 0
    for a in ([after] if isinstance(after, str) else after):
        for j in range(i, len(ls)):
            if a in ls[j]:
                i = j
                break
        else:
            raise SystemExit(f'{path}: anchor not found: {a!r}')
    return ls, i


def _cells(ln):
    return [c.strip() for c in ln.strip().strip('|').split('|')]


def _token(cell, pick, where):
    toks = TOK.findall(cell)
    if not toks or pick >= len(toks) or pick < -len(toks):
        raise SystemExit(f'{where}: no number #{pick} in cell {cell!r}')
    return toks[pick].replace('\u2212', '-')


def tab(path, after, match, col, pick=0, first=False):
    """Cell `col` of the row matching `match` in the first markdown table at or after the anchor(s) `after`."""
    ls, i = _start(path, after)
    while not ls[i].lstrip().startswith('|'):
        i += 1
    hdr, hl = _cells(ls[i]), i
    for k in list(match) + [col]:
        if k not in hdr:
            raise SystemExit(f'{path}:{hl + 1}: no column {k!r} in {hdr}')
    hits = []
    for j in range(i + 2, len(ls)):
        if not ls[j].lstrip().startswith('|'):
            break
        r = dict(zip(hdr, _cells(ls[j])))
        if all(r.get(k) == v for k, v in match.items()):
            hits.append((j, r))
    if not hits or (len(hits) > 1 and not first):
        raise SystemExit(f'{path}: {len(hits)} rows match {match} under {after!r}')
    j, r = hits[0]
    key = ', '.join(f'{v}' for v in match.values())
    return Src(_token(r[col], pick, f'{path}:{j + 1}'), path, j + 1, f'[{key} | {col}]')


def grep(path, rx, group=1, after=None):
    ls, i = _start(path, after) if after else (lines(path), 0)
    for j in range(i, len(ls)):
        m = re.search(rx, ls[j])
        if m:
            return Src(m.group(group).replace('\u2212', '-'), path, j + 1, f'/{rx}/ group {group}')
    raise SystemExit(f'{path}: no match for {rx!r}')


def _num(s):
    return Decimal(s.tok.replace(',', '').replace('+', ''))


def _q(d, k):
    return d.quantize(Decimal(1).scaleb(-k), rounding=ROUND_HALF_UP)


def _signed(t):
    return ('\\ensuremath{-}' + t[1:]) if t.startswith('-') else t


def show(fmt, src, k=2):
    t = src.tok
    if fmt == 'raw':
        return _signed(t)
    if fmt == 'abs':
        return t.lstrip('+-')
    if fmt == 'hit':
        return str(_q(_num(src), 2))
    if fmt == 'sci':
        m = re.fullmatch(r'([+-]?[\d.]+)e([+-]?\d+)', t)
        if not m:
            raise SystemExit(f'not e-notation: {t}')
        return f'\\ensuremath{{{m.group(1)}\\times10^{{{int(m.group(2))}}}}}'
    raise SystemExit(f'unknown format {fmt}')


SPECS = []          # (key, shown, comment)


def N(key, src, fmt='raw', same=()):
    for s in same:
        if s.tok != src.tok:
            raise SystemExit(f'{key}: {s.note()} differs from {src.note()}')
    extra = f'; same value in {len(same)} more cells' if same else ''
    SPECS.append((key, show(fmt, src), f'{fmt}: {src.note()}{extra}'))


def SUB(key, a, b, k):
    d = _q(_num(a) - _num(b), k)
    SPECS.append((key, _signed(str(d)), f'sub ({a.note()}) - ({b.note()}), {k} decimals'))


def RATIO(key, a, b, k):
    d = _q((_num(a) / _num(b) - 1) * 100, k)
    SPECS.append((key, _signed(str(d)), f'ratio 100 x (({a.note()}) / ({b.note()}) - 1), {k} decimals'))


def EXT(key, srcs, which):
    vals = sorted(srcs, key=_num)
    s = vals[0] if which == 'min' else vals[-1]
    show_ = show('sci', s) if 'e' in s.tok else show('raw', s)
    SPECS.append((key, show_, f'{which} of {len(srcs)}: ' + '; '.join(x.note() for x in srcs)))


# ------------------------------------------------------------------------------------------------ sources
T7 = 'results/P7/TABLES.md'
P3BS, P9S, P10S, P11S = (f'results/{p}/SUMMARY.md' for p in ('P3b', 'P9', 'P10', 'P11'))
PARTA, P14S = 'results/P11/PARTA.md', 'results/P14/SUMMARY.md'
P12T, P13S, P13T = 'results/P12/TABLES.md', 'results/P13/SUMMARY.md', 'results/P13/TABLES.md'
P12S = 'results/P12/SUMMARY.md'
P15S, P15T, P16S, P16T = 'results/P15/SUMMARY.md', 'results/P15/TABLES.md', 'results/P16/SUMMARY.md', 'results/P16/TABLES.md'
LFUR, LFUP = 'LFU (gem5 LFURP \u2014 reset on eviction)', 'LFU (persistent counters)'
ROWS = {'2M': '2,000,000', '10M': '10,000,000'}

# dataset and sizes
N('ds.rows', grep(T7, r'Rows in the file: ([\d,]+)'))
N('ds.tables', grep(T7, r'; (\d+) categorical columns = \d+ tables'))
N('ds.r2M', grep(T7, r'use the first ([\d,]+) and'))
N('ds.r10M', grep(T7, r'and the first ([\d,]+) of them'))
N('lab.2M', grep(P9S, r'\| (2M), 256 \|'))
N('lab.10M', grep(P9S, r'\| (10M), 256 \|'))
for e in ('16', '64', '256'):
    N(f'sz.{e}', tab(PARTA, '| rows |', {'rows': '2,000,000', 'entries': e}, 'entries'))
for e, s in (('1000', '1,000'), ('10000', '10,000'), ('100000', '100,000')):
    N(f'sz.{e}', tab(T7, '### P3b total hit %, 2,000,000 rows', {'capacity (vectors, total)': s},
                     'capacity (vectors, total)'))
N('sz.p3min', tab(T7, '### P3 combined (all 26 tables), 2,000,000 rows', {'capacity (vectors per table)': '64'},
                  'capacity (vectors per table)'))
for L in ROWS:
    N(f'p11.acc.{L}', tab(PARTA, '| rows |', {'rows': ROWS[L], 'entries': '256'}, 'accesses'))
N('p3.window', grep(T7, r'W-TinyLFU \(Count-Min, window=(\d+)%\)'))

# RTL parameters
RP = '## RTL and simulator parameters'
for k, item in (('rtl.vecw', 'RTL parameter VECTOR_WIDTH (default)'), ('rtl.addrw', 'RTL parameter ADDR_WIDTH (default)'),
                ('rtl.cntw', 'RTL parameter COUNTER_WIDTH (default)'), ('rtl.groups', 'RTL parameter GROUPS (default)'),
                ('rtl.sat', 'RTL counter saturation value, 2^COUNTER_WIDTH - 1'), ('rtl.tests', 'unit testbench tests'),
                ('rtl.simcap', 'trace simulator LFU counter cap (`min(N, ...)` in trace_sim/run_trace_sim.py)')):
    N(k, tab(T7, RP, {'item': item}, 'value'))
N('p10.kw', grep(P10S, r'KW = EW\+1 = (\d+) bits'))
for g, d in ((1, '16'), (2, '64'), (3, '256')):
    N(f'p11.ff.{d}', grep(P11S, r'ptr width \(\+(\d+) / \+(\d+) / \+(\d+)\)', g))
N('tool.yosys', tab(T7, '### Flow settings and toolchain', {'item': 'Yosys'}, 'value'))
N('tool.opensta', grep(T7, r'OpenSTA commit / version \| \w+ / ([\d.]+)'))

# P9 validation
N('p9.runs', grep(T7, r'Runs with zero mismatches in both models: (\d+) of \d+'))
N('p9.req', grep(T7, r'requests compared: ([\d,]+)'))
V9 = '### P9 RTL hit_flag vs RTL-exact'
N('p9.mism', tab(T7, V9, {'depth': '256', 'mode': '0', 'slice': 'row0', 'run': 'full'}, 'mismatches (RTL-exact / structural)'),
  same=[tab(T7, V9, {'depth': d, 'mode': m, 'slice': s, 'run': r}, 'mismatches (RTL-exact / structural)', pick=p)
        for d in ('16', '64', '256') for m in '01' for s in ('row0', 'row1M') for r in ('p8budget', 'full')
        for p in (0, 1)])
N('p9.slicereq', tab(T7, V9, {'depth': '256', 'mode': '0', 'slice': 'row0', 'run': 'full'}, 'requests'))

# P14
for B in ('64', '1,024', '16,384'):
    b = B.replace(',', '')
    N(f'p14.B.{b}', tab(P14S, '| B | layout', {'B': B, 'layout': 'per_table'}, 'B'))
    N(f'p14.pt.{b}', tab(P14S, '| B | layout', {'B': B, 'layout': 'per_table'}, 'L2 read hit %'), 'hit')
    N(f'p14.cc.{b}', tab(P14S, '| B | layout', {'B': B, 'layout': 'concat'}, 'L2 read hit %'), 'hit')
N('p14.rows', grep(P14S, r'first (2M) rows'))
N('p14.batches', grep(P14S, r'Profiled: (\d+) batches'))
N('p14.dim', grep(P14S, r'dim (\d+) float32'))
N('p14.cap', grep(P14S, r'closest P3b capacity: ([\d,]+)'))
N('p14.l2bytes', grep(P14S, r'H100 L2 = ([\d,]+) B'))
N('p14.vecbytes', grep(P14S, r'A vector is (\d+) B'))
N('p14.sectorbytes', grep(P14S, r'sectors of (\d+) B'))

# P3 per-table and P3b shared, hit rates
P3COL = {'LRU': 'LRU', 'LFUr': LFUR, 'LFUp': LFUP, 'TLFU': 'TinyLFU-exact (window=1%)',
         'WTLFU': 'W-TinyLFU (Count-Min, window=1%)', 'ARC': 'ARC', 'BEL': 'Belady (MIN, offline)'}
for L in ROWS:
    for k, c in P3COL.items():
        N(f'p3.{L}.256.{k}', tab(T7, f'### P3 combined (all 26 tables), {ROWS[L]} rows, hit %',
                                 {'capacity (vectors per table)': '256'}, c), 'hit')
    for k in ('LRU', 'LFUr', 'LFUp', 'WTLFU', 'ARC'):
        for cap in ('256', '1,000', '100,000'):
            N(f'p3b.{L}.{cap.replace(",", "")}.{k}',
              tab(T7, f'### P3b total hit %, {ROWS[L]} rows', {'capacity (vectors, total)': cap}, P3COL[k]), 'hit')
N('p3b.drop.lo', grep(P3BS, r'\((-[\d.]+) to (-[\d.]+) pp'), 'abs')
N('p3b.drop.hi', grep(P3BS, r'\((-[\d.]+) to (-[\d.]+) pp', 2), 'abs')

# P9 / P11 shared-cache full traces
for L in ROWS:
    for e, s in (('256', '256'), ('100000', '100,000')):
        N(f'p9.{L}.{e}.v2', tab(T7, f'#### {ROWS[L]} rows: total hit %', {'entries': s}, 'RTL-exact mode 0'), 'hit')
    for e in ('16', '64', '256'):
        a = ['### P11 full traces', f'#### {ROWS[L]} rows']
        N(f'p11.{L}.{e}.v3', tab(T7, a, {'entries': e}, 'Rotate-victim m0 (v3 rule)'), 'hit')
        N(f'p11.{L}.{e}.v2', tab(T7, a, {'entries': e}, 'RTL-exact m0 (v2 rule)'), 'hit')
        N(f'p11.{L}.{e}.LRU', tab(T7, a, {'entries': e}, 'LRU'), 'hit')
        N(f'p11.{L}.{e}.LFUr', tab(T7, a, {'entries': e}, 'LFU-reset (oldest)'), 'hit')
SUB('d.v3lru', tab(T7, ['### P11 full traces', '#### 10,000,000 rows'], {'entries': '256'}, 'Rotate-victim m0 (v3 rule)'),
    tab(T7, '#### 10,000,000 rows: total hit %', {'entries': '256'}, 'LRU'), 2)
SUB('d.v3v2', tab(T7, ['### P11 full traces', '#### 10,000,000 rows'], {'entries': '256'}, 'Rotate-victim m0 (v3 rule)'),
    tab(T7, '#### 10,000,000 rows: total hit %', {'entries': '256'}, 'RTL-exact mode 0'), 2)
EV = '### P9 evictions of the line installed'
N('p9.prev.v2', tab(T7, EV, {'slice': 'row0', 'depth': '256'}, 'RTL-exact mode 0', 0))
N('p9.prev.v2.n', tab(T7, EV, {'slice': 'row0', 'depth': '256'}, 'RTL-exact mode 0', 1))
N('p9.prev.old', tab(T7, EV, {'slice': 'row0', 'depth': '256'}, 'LFU-reset (oldest)', 0))
N('p9.prev.old.n', tab(T7, EV, {'slice': 'row0', 'depth': '256'}, 'LFU-reset (oldest)', 1))
GAP = '#### {} rows: RTL-exact vs LRU'
BIG = ('256', '1,000', '10,000', '100,000')
N('p9.gap.10M.256', tab(T7, GAP.format(ROWS['10M']), {'entries': '256'}, 'gap'),
  same=[tab(T7, GAP.format(ROWS['10M']), {'entries': '256'}, 'tie')])
for k, c in (('p9.sat', 'sat'), ('p9.int', 'interaction')):
    N(k, tab(T7, GAP.format(ROWS['2M']), {'entries': '256'}, c),
      same=[tab(T7, GAP.format(ROWS[L]), {'entries': e}, c) for L in ROWS for e in BIG])
CAND = '#### {} rows: candidate tie-break'
N('p9.rec', tab(T7, CAND.format(ROWS['2M']), {'entries': '256'}, 'recovered % Rotate-victim mode 0'),
  same=[tab(T7, CAND.format(ROWS[L]), {'entries': e}, 'recovered % Rotate-victim mode 0') for L in ROWS for e in BIG])
N('p9.rvdiff.lo', grep(P9S, r'Rotate-victim differs by (-?\d+) to (\+[\d,]+) hits'))
N('p9.rvdiff.hi', grep(P9S, r'Rotate-victim differs by (-?\d+) to (\+[\d,]+) hits', 2))
for e in ('16', '64', '256'):
    N(f'p11.tl.{e}', tab(PARTA, '| rows |', {'rows': '2,000,000', 'entries': e}, 'tables with v3 < v2 (of 26)'),
      same=[tab(PARTA, '| rows |', {'rows': '10,000,000', 'entries': e}, 'tables with v3 < v2 (of 26)')])
N('p11.lost.2M.16', tab(PARTA, '| rows |', {'rows': '2,000,000', 'entries': '16'}, 'v3 hits lost on those tables'))
N('p11.gain.2M.16', tab(PARTA, '| rows |', {'rows': '2,000,000', 'entries': '16'}, 'v3 - v2 hits'), 'abs')

# P10 lockstep and verification
LK = '### P10 lockstep'
V2C = 'v2-rule hits (m0) / equals P9 v2 log (m1)'
for d, s in (('16', 'row0'), ('16', 'row1M'), ('256', 'row0')):
    N(f'p10.{d}.{s}.v3', tab(T7, LK, {'depth': d, 'mode': '0', 'slice': s}, 'RTL hits'))
    N(f'p10.{d}.{s}.v2', tab(T7, LK, {'depth': d, 'mode': '0', 'slice': s}, V2C))
N('p10.runs', grep(P10S, r'Mismatches = 0 in all (\d+) runs'))
N('p10.mism', grep(P10S, r'Mismatches = (\d+) in all \d+ runs'))
N('p10.mut', grep(P10S, r'all (\d+) caught'))
N('p11.mut.tb', grep(P11S, r'(\d+) were killed by the testbench'))
N('p11.mut.ls', grep(P11S, r', (\d+) by lockstep against'))
N('p11.eq.16', grep(P11S, r'Also proven at depth 16: ([\d,]+) of'))
N('p11.eq.64', grep(P11S, r'all ([\d,]+) \$equiv cells proven'))
N('p11.gls.n', grep(P11S, r'- (\d+)/\d+ pass: all'))
N('p11.gls.mism', grep(P11S, r'\| (0) in every task \|'))
GL = '## Lockstep'
N('p13.mism', tab(P13T, GL, {'netlist': 'v3', 'slice': 'row0'}, 'SDF: mismatching; X (netlist/RTL) cycles'),
  same=[tab(P13T, GL, {'netlist': n, 'slice': s}, c) for n in ('v2', 'v3') for s in ('row0', 'row1M')
        for c in ('SDF: mismatching; X (netlist/RTL) cycles', 'zero-delay: mismatching; X (netlist/RTL) cycles')])
PG = '## Post-route GLS'
N('p15.mism', tab(P15T, PG, {'netlist': 'v3', 'slice': 'row0', 'mode': 'sdf'}, 'mismatching cycles'),
  same=[tab(P15T, PG, {'netlist': n, 'slice': s, 'mode': m}, 'mismatching cycles') for n in ('v2', 'v3')
        for s in ('row0', 'row1M') for m in ('sdf', 'sdf tcf', 'zero')])
N('p15.sdf.path', tab(P15T, PG, {'netlist': 'v3', 'slice': 'row0', 'mode': 'sdf'}, 'SDF path delays annotated', 2),
  same=[tab(P15T, PG, {'netlist': 'v2', 'slice': 'row0', 'mode': 'sdf'}, 'SDF path delays annotated', 2)])
N('p15.sdf.check', tab(P15T, PG, {'netlist': 'v3', 'slice': 'row0', 'mode': 'sdf'}, 'SDF timing checks annotated', 2),
  same=[tab(P15T, PG, {'netlist': 'v2', 'slice': 'row0', 'mode': 'sdf'}, 'SDF timing checks annotated', 2)])

# open-flow synthesis (P11)
FM = r'Every v3 mode-0 Fmax change \((\+[\d.]+)%, (-[\d.]+)%, (-[\d.]+)% at 1 GHz'
N('p11.nfmax.lo', grep(P11S, FM, 3))
N('p11.nfmax.hi', grep(P11S, FM, 1))
N('p11.nnoise', grep(P11S, r'This ([\d.]+)% is the observed flow variation'))

# P12 Genus
TL = '## Timing limit per version'
VM = [(v, m) for v in ('v2', 'v3') for m in '01']
for d, pairs in (('16', VM), ('64', VM[:3]), ('256', VM)):
    for k, c in (('met', 'tightest met (ns)'), ('fail', 'loosest failed (ns)')):
        N(f'p12.br.{d}.{k}', tab(P12T, TL, {'version': 'v2', 'mode': '0', 'depth': d}, c),
          same=[tab(P12T, TL, {'version': v, 'mode': m, 'depth': d}, c) for v, m in pairs])
N('p12.per.min', tab(P12T, TL, {'version': 'v2', 'mode': '0', 'depth': '16'}, 'periods run (ns)', -1))
N('p12.per.max', tab(P12T, TL, {'version': 'v2', 'mode': '0', 'depth': '16'}, 'periods run (ns)', 0))
N('p12.io', grep(P12T, r'I/O delay ([\d.]+) x period'))
DA = '## v3 - v2 at the same'
N('p12.relax', tab(P12T, DA, {'mode': '0', 'depth': '16', 'period (ns)': '2.0'}, 'period (ns)'))
for m in '01':
    for d in ('16', '64', '256'):
        N(f'p12.a.{d}.m{m}', tab(P12T, DA, {'mode': m, 'depth': d, 'period (ns)': '2.0'}, 'area change'))
N('p12.area.v2', tab(P12T, DA, {'mode': '0', 'depth': '256', 'period (ns)': '2.0'}, 'area v2 (library units)'))
N('p12.area.v3', tab(P12T, DA, {'mode': '0', 'depth': '256', 'period (ns)': '2.0'}, 'area v3'))
MO = '## Merge-off'
for v in ('v2', 'v3'):
    row = {'version': v, 'period (ns)': '0.65', 'flow': 'merge-off'}
    N(f'p12.mo.{v}', tab(P12T, MO, row, 'Fmax change'), 'abs')
    N(f'p12.mo.a.{v}', tab(P12T, MO, row, 'area change'))
    N(f'p12.fmo.{v}', tab(P12T, MO, row, 'Fmax (MHz)'))
    N(f'p12.f.{v}', tab(P12T, MO, {'version': v, 'period (ns)': '0.65', 'flow': 'normal'}, 'Fmax (MHz)'))
N('p12.copies', tab(P12T, MO, {'version': 'v2', 'period (ns)': '0.65', 'flow': 'merge-off'}, 'req_addr_grp flops'),
  same=[tab(P12T, MO, {'version': v, 'period (ns)': p, 'flow': 'merge-off'}, 'req_addr_grp flops')
        for v in ('v2', 'v3') for p in ('0.65', '0.8')])

# P13 pre-layout GLS power
N('p13.period', grep(P13S, r'clock ([\d.]+) ns;'))
N('p13.req', grep(P13S, r'([\d,]+) requests per slice'))
N('p13.fill.lo', grep(P13S, r'(\d)-(\d) random cycles'))
N('p13.fill.hi', grep(P13S, r'(\d)-(\d) random cycles', 2))
PW = '## Power'
NS = [(n, s) for n in ('v2', 'v3') for s in ('row0', 'row1M')]
EXT('p13.P.lo', [tab(P13T, PW, {'netlist': n, 'slice': s}, 'total') for n, s in NS], 'min')
EXT('p13.P.hi', [tab(P13T, PW, {'netlist': n, 'slice': s}, 'total') for n, s in NS], 'max')
for n, s in NS:
    N(f'p13.E.{n}.{s}', tab(P13T, PW, {'netlist': n, 'slice': s}, 'energy per request'))
for k, c in (('cov', 'driver nets annotated'), ('logic', 'logic share'), ('reg', 'register share')):
    EXT(f'p13.{k}.lo', [tab(P13T, PW, {'netlist': n, 'slice': s}, c) for n, s in NS], 'min')
    EXT(f'p13.{k}.hi', [tab(P13T, PW, {'netlist': n, 'slice': s}, c) for n, s in NS], 'max')
N('p13.bound', grep(P13T, r'about \+/-([\d.]+)%'))
VV = '## v3 against v2 per slice'
for s in ('row0', 'row1M'):
    N(f'p13.dE.{s}', tab(P13T, VV, {'slice': s}, 'change', 1))
    N(f'p13.dP.{s}', tab(P13T, VV, {'slice': s}, 'total power change'), 'abs')
    N(f'p13.dC.{s}.abs', tab(P13T, VV, {'slice': s}, 'cycles change'), 'abs')

# P15 place and route
BR = '## Met/failed bracket'
for k, c in (('met', 'tightest met ns'), ('fail', 'loosest failed ns')):
    q = 'target-slack flow, latest hold pass at each period'
    N(f'p15.{k}', tab(P15T, BR, {'run': 'v2_m0_d256_p0.8_nomerge', 'flows': q}, c),
      same=[tab(P15T, BR, {'run': 'v3_m0_d256_p0.8_nomerge', 'flows': q}, c)])
N('p15.oldfail', grep(P15S, r'Earlier flows failed ([\d.]+)-([\d.]+) ns', 2))
N('p15.tslack', grep(P15S, r'setup target slack ([\d.]+) ns'))
N('p15.tt.v', grep(P15S, r'typical ([\d.]+) V (\d+) C'))
N('p15.tt.t', grep(P15S, r'typical ([\d.]+) V (\d+) C', 2))
PR = '## Post-route results'
H2 = ('nodvtsh database + hold target slack 0.01, optDesign -postRoute -hold, ecoRoute -fix_drc '
      '(+1 if verify_drc found a violation)')


def pr(v, period, col, flow=H2, run=None):
    return tab(P15T, PR, {'run': run or f'{v}_m0_d256_p0.8_nomerge', 'flow': flow, 'period ns': period}, col)


for v in ('v2', 'v3'):
    N(f'p15.s.{v}.10', pr(v, '1.0', 'setup WNS ns'))
    N(f'p15.h.{v}.10', pr(v, '1.0', 'hold WNS ns'))
    N(f'p15.la.{v}', pr(v, '1.0', 'logic cell area'))
    N(f'p15.core.{v}', pr(v, '1.0', 'core area'))
    N(f'p15.s.{v}.09', pr(v, '0.9', 'setup WNS ns'))
    N(f'p15.n.{v}.09', pr(v, '0.9', 'setup viol. paths'))
    N(f'p15.s.{v}.09dv', pr(v, '0.9', 'setup WNS ns', flow='multi-row dont_use'))
    N(f'p15.rs.{v}', tab(P15T, '## Fix: multi-row', {'run': f'{v}_m0_d256_p0.8_nomerge', 'period ns': '1.0'},
                         'resized to single-row', first=True))
FIN = [pr(v, p, c) for v in ('v2', 'v3') for p in ('1.0', '0.9') for c in ('DRC', 'conn. problems all nets',
                                                                          'conn. problems 4 PG nets')]
N('p15.drc', pr('v2', '1.0', 'DRC'), same=FIN)
N('p15.conn', pr('v2', '1.0', 'conn. problems all nets'), same=FIN)
N('p15.wt', pr('v2', '1.0', 'well-tap rule um'))
N('p15.wtv', pr('v2', '1.0', 'well-tap viol. full core'), same=[pr('v3', '1.0', 'well-tap viol. full core')])
D16 = dict(v=None, period='0.8', flow='multi-row dont_use', run='v3_m0_d16_p0.8')
N('p15.d16.period', pr(col='period ns', **D16))
N('p15.d16.wns', pr(col='setup WNS ns', **D16), 'abs')
N('p15.d16.n', pr(col='setup viol. paths', **D16))
N('p15.d16.drc', pr(col='DRC', **D16))
N('p15.gls.period', grep(P15T, r'## v3 against v2 per slice \(([\d.]+) ns'))
PP = '## Post-route power'
for n, s in NS:
    N(f'p15.E.{n}.{s}', tab(P15T, PP, {'netlist': n, 'slice': s}, 'energy per request'))
for k, c in (('reg', 'register share'), ('clk', 'clock (clock tree) share'),
             ('logic', 'logic (combinational) share = uncertainty bound')):
    EXT(f'p15.{k}.lo', [tab(P15T, PP, {'netlist': n, 'slice': s}, c) for n, s in NS], 'min')
    EXT(f'p15.{k}.hi', [tab(P15T, PP, {'netlist': n, 'slice': s}, c) for n, s in NS], 'max')
for n in ('v2', 'v3'):
    N(f'p15.cov.{n}', tab(P15T, PP, {'netlist': n, 'slice': 'row0'}, 'driver nets annotated'),
      same=[tab(P15T, PP, {'netlist': n, 'slice': 'row1M'}, 'driver nets annotated')])
for s in ('row0', 'row1M'):
    N(f'p15.dE.{s}', tab(P15T, VV, {'slice': s}, 'change', 1))
    N(f'p15.dE.{s}.abs', tab(P15T, VV, {'slice': s}, 'change', 1), 'abs')
    N(f'p15.dP.{s}', tab(P15T, VV, {'slice': s}, 'total power change'), 'abs')
    N(f'p15.dC.{s}.abs', tab(P15T, VV, {'slice': s}, 'cycles change'), 'abs')

# P16 corners
N('p16.ss.v', grep(P16S, r'ss = slow ([\d.]+) V (\d+) C'))
N('p16.ss.t', grep(P16S, r'ss = slow ([\d.]+) V (\d+) C', 2))
N('p16.ff.v', grep(P16S, r'ff = fast ([\d.]+) V (-\d+) C'))
N('p16.ff.t', grep(P16S, r'ff = fast ([\d.]+) V (-\d+) C', 2))
TC, PGR, DER = '## Timing per design and corner', '## Path groups', '## Derived'
for v in ('v2', 'v3'):
    r = {'design': f'd256 {v}', 'PnR period ns': '1.0', 'corner': 'ss'}
    N(f'p16.ss.s.{v}.10', tab(P16T, TC, r, 'setup WNS ns'))
    N(f'p16.ss.hn.{v}.10', tab(P16T, TC, r, 'hold viol. paths'))
    N(f'p16.ss.hr.{v}.10', tab(P16T, PGR, r, 'hold reg2reg'))
    N(f'p16.ff.hrn.{v}', tab(P16T, PGR, dict(r, corner='ff'), 'hold reg2reg', 1))
    for p in ('1.0', '1.1'):
        N(f'p16.dp.{v}.{p.replace(".", "")}', tab(P16T, DER, {'design': f'd256 {v}', 'PnR period ns': p},
                                                  'derived slow-corner period ns'))
SUB('d.dp10', tab(P16T, DER, {'design': 'd256 v2', 'PnR period ns': '1.0'}, 'derived slow-corner period ns'),
    tab(P16T, DER, {'design': 'd256 v3', 'PnR period ns': '1.0'}, 'derived slow-corner period ns'), 3)
IO = '## I/O hold diagnosis'
N('p16.io.indelay', tab(P16T, IO, {'corner': 'ss'}, 'worst in2reg hold path: input delay'))
N('p16.io.arr', tab(P16T, IO, {'corner': 'ss'}, 'data arrival'))
N('p16.io.clk', tab(P16T, IO, {'corner': 'ss'}, 'clock arrival at register'))
N('p16.io.slack', tab(P16T, IO, {'corner': 'ss'}, 'slack'))
N('p16.io.lat', tab(P16T, IO, {'corner': 'tt'}, 'capture clock source latency'))
N('p16.io.tree', tab(P16T, IO, {'corner': 'tt'}, 'tree insertion delay (arrival - source latency)'))
N('p16.io.ttslack', tab(P16T, IO, {'corner': 'tt'}, 'slack'))
N('p16.io.in2reg', tab(P16T, '| corner | violating hold paths in2reg', {'corner': 'ss'}, 'violating hold paths in2reg'))
N('p16.io.all', grep(P16T, r'Failing hold paths at ss in timeDesign: (\d+)'))


# added after the independent review (2026-11-19)
CT = 'results/P9/CANDIDATES.md'
SC = 'added state (by construction, depth 256, 16 groups)'
N('p9.ff.rs', tab(CT, '| rule |', {'rule': 'R2 Rotate-step'}, SC), same=[tab(CT, '| rule |', {'rule': 'R1 Rotate-victim'}, SC)])
N('p9.ff.yb', tab(CT, '| rule |', {'rule': 'R3 Young-bit'}, SC))
N('p9.rs.beats', grep(P9S, r'Rotate-step beats LFU-reset \(oldest\) at (\d+) of (\d+) points'))
N('p9.rs.pts', grep(P9S, r'Rotate-step beats LFU-reset \(oldest\) at (\d+) of (\d+) points', 2))
PRB = r'Synthetic probe \(not Criteo; (\d+) random Zipf traces.*Rotate-victim mode 0 (\d+), Rotate-step mode 0 (\d+)'
N('p9.probe.n', grep(T7, PRB, 1))
N('p9.probe.rv', grep(T7, PRB, 2))
N('p9.probe.rs', grep(T7, PRB, 3))
N('p14.start', grep(P14S, r'Profiled: \d+ batches from row ([\d,]+)'))
RATIO('p15.ladiff', pr('v3', '1.0', 'logic cell area'), pr('v2', '1.0', 'logic cell area'), 2)
N('p12.noise', grep(P12S, r'the same-logic mode-1 difference reaches (-[\d.]+)%'), 'abs')
N('p16.io.r2o', tab(P16T, '| corner | violating hold paths in2reg', {'corner': 'ss'}, 'violating hold paths reg2out'))
FFIO = [tab(P16T, PGR, {'design': f'd256 {v}', 'PnR period ns': p, 'corner': 'ff'}, 'hold default', 1)
        for v in ('v2', 'v3') for p in ('1.0', '1.1')]
EXT('p16.ff.hdn.lo', FFIO, 'min')
EXT('p16.ff.hdn.hi', FFIO, 'max')


# ------------------------------------------------------------------------------------------------ output
def render():
    keys = [k for k, _, _ in SPECS]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        raise SystemExit(f'duplicate keys: {sorted(dup)}')
    out = ['% Generated by tools/make_paper_macros.py from committed results files. Do not edit by hand.',
           '% Each line: \\defnum{key}{shown}% format: source file:line [row | column] = full source value']
    used = used_keys()
    out += [f'\\defnum{{{k}}}{{{v}}}% {c}' for k, v, c in SPECS if k in used]   # every spec is still extracted
    return '\n'.join(out) + '\n'


def used_keys():
    tex = re.sub(r'(?<!\\)%.*', '', TEX.read_text())
    return set(re.findall(r'\\R\{([^{}]+)\}', tex))


def main():
    text = render()
    defined = {k for k, _, _ in SPECS}
    missing = sorted(used_keys() - defined)
    unused = sorted(defined - used_keys())
    if '--check' in sys.argv:
        bad = False
        if not OUT.exists() or OUT.read_text() != text:
            print('FAIL: paper/v2/macros.tex is stale; run python3 -I tools/make_paper_macros.py')
            bad = True
        if missing:
            print(f'FAIL: keys used in main.tex but not defined: {missing}')
            bad = True
        print(f'{len(SPECS)} macros; {len(unused)} defined but unused: {unused}')
        sys.exit(1 if bad else 0)
    OUT.write_text(text)
    print(f'wrote {OUT.relative_to(ROOT)}: {len(SPECS) - len(unused)} macros used by main.tex '
          f'({len(SPECS)} extracted; extracted but unused: {unused})')
    if missing:
        print(f'FAIL: keys used in main.tex but not defined: {missing}')
        sys.exit(1)


if __name__ == '__main__':
    main()
