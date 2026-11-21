"""Generate paper/v2/macros.tex: one \\defnum{key}{shown} per number in the paper, each extracted from a committed
results file (read with `git show HEAD:<path>`, so only committed results can reach the paper).

Usage (from the repository root):
  python3 -I tools/make_paper_macros.py            write paper/v2/macros.tex
  python3 -I tools/make_paper_macros.py --check    exit 1 if macros.tex is stale, or main.tex uses an undefined key
  add --target report to do the same for docs/sem_report/report.tex and docs/sem_report/macros.tex (semester report)
  add --target synth for docs/synthesis_report (implementation report; its gen_*.tex tables, written by
  docs/synthesis_report/gen_tables.py, are scanned for keys together with synthesis_report.tex)
Every spec below is extracted on every run; the output holds only the keys that the target's .tex uses.

Every definition line ends with a comment naming the source: file:line, the table row and column (or the regex),
and the full source value. Display rules (agreed with the authors, 2026-11-19):
  hit   hit rates: rounded half-up to 2 decimals; the comment keeps the full value
  raw   every other value exactly as written in the file (sign shown with a math minus)
  abs   as raw, without the sign (used where the text says "lower", "fewer", "more")
  sci   as raw, with the e-notation typeset as x 10^n (same digits)
  sub   a difference computed from the full source values, then rounded half-up to the given decimals
  min / max   the smallest / largest of several source values, shown exactly as written
  mW    a power in W written in e-notation, shown in mW by moving the decimal point three places (same digits)
  div   an exact quotient by a unit constant (e.g. bytes / 1,048,576 = MiB); fails unless the quotient is exact
A spec may list `same` cells: the generator fails unless they all equal the chosen value (used where the text says
"at every size" or "in every run").
"""
import re
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {'paper': ('paper/v2/main.tex', 'paper/v2/macros.tex'),          # --target paper (default)
           'report': ('docs/sem_report/report.tex', 'docs/sem_report/macros.tex'),
           'synth': ('docs/synthesis_report/synthesis_report.tex', 'docs/synthesis_report/macros.tex')}
_t = sys.argv[sys.argv.index('--target') + 1] if '--target' in sys.argv else 'paper'
if _t not in TARGETS:
    raise SystemExit(f'unknown --target {_t}; one of {sorted(TARGETS)}')
TEX, OUT = (ROOT / x for x in TARGETS[_t])
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
    if fmt == 'mW':
        return str(Decimal(t).scaleb(3))
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


def DIV(key, a, const, what):
    q, r = divmod(_num(a), Decimal(const))
    if r:
        raise SystemExit(f'{key}: {a.tok} / {const} is not exact')
    SPECS.append((key, str(q), f'div ({a.note()}) / {const} ({what}), exact'))


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


# added for the readability revision (2026-11-20): tables carry the detail, prose keeps 2-3 numbers per paragraph
DIV('p14.l2mib', grep(P14S, r'H100 L2 = ([\d,]+) B'), 1048576, '1 MiB = 1,048,576 bytes')
for n, s in NS:
    N(f'p13.mW.{n}.{s}', tab(P13T, PW, {'netlist': n, 'slice': s}, 'total'), 'mW')
    N(f'p15.mW.{n}.{s}', tab(P15T, PP, {'netlist': n, 'slice': s}, 'total'), 'mW')
for n in ('v2', 'v3'):
    for k, c in (('reg', 'register share'), ('clk', 'clock (clock tree) share'),
                 ('logic', 'logic (combinational) share = uncertainty bound')):
        N(f'p15.{k}.{n}.row0', tab(P15T, PP, {'netlist': n, 'slice': 'row0'}, c))
for s in ('row0', 'row1M'):
    N(f'p13.dC.{s}', tab(P13T, VV, {'slice': s}, 'cycles change'))
    N(f'p15.dC.{s}', tab(P15T, VV, {'slice': s}, 'cycles change'))
    N(f'p13.dE.{s}.abs', tab(P13T, VV, {'slice': s}, 'change', 1), 'abs')
for v in ('v2', 'v3'):
    for c, cn in (('ss', 'ss'), ('ff', 'ff')):
        r = {'design': f'd256 {v}', 'PnR period ns': '1.0', 'corner': cn}
        N(f'p16.{c}.hio.{v}', tab(P16T, PGR, r, 'hold default', 1))
        N(f'p16.{c}.hrr.{v}', tab(P16T, PGR, r, 'hold reg2reg', 1))
SUB('d.in2reg.other', grep(P16T, r'Failing hold paths at ss in timeDesign: (\d+)'),
    tab(P16T, '| corner | violating hold paths in2reg', {'corner': 'ss'}, 'violating hold paths in2reg'), 0)
N('p13.fill.max', grep(P13S, r'(\d)-(\d) random cycles', 2))
N('p9.rvdiff.hi.abs', grep(P9S, r'Rotate-victim differs by (-?\d+) to (\+[\d,]+) hits', 2), 'abs')
N('p12.a.16.m0.abs', tab(P12T, DA, {'mode': '0', 'depth': '16', 'period (ns)': '2.0'}, 'area change'), 'abs')
N('p12.mo.a.v3.abs', tab(P12T, MO, {'version': 'v3', 'period (ns)': '0.65', 'flow': 'merge-off'}, 'area change'), 'abs')
N('p12.mo.a08.v3.abs', tab(P12T, MO, {'version': 'v3', 'period (ns)': '0.8', 'flow': 'merge-off'}, 'area change'), 'abs')
N('p12.a.256.m1.abs', tab(P12T, DA, {'mode': '1', 'depth': '256', 'period (ns)': '2.0'}, 'area change'), 'abs')


# ================================================================ semester report (docs/sem_report), 2026-11-20
P0S, P1S, P2S, P3S, P4S = (f'results/{x}/SUMMARY.md' for x in ('P0', 'P1', 'P2', 'P3', 'P4'))
P5bS, P5cS, P5dS, P5eS, P5fS = (f'results/{x}/SUMMARY.md' for x in ('P5b', 'P5c', 'P5d', 'P5e', 'P5f_gls'))
P7S, P8R = 'results/P7/SUMMARY.md', 'results/P8/RESULTS.md'

# P1
N('p1.mutants', grep(P1S, r'(\d+) mutants x (\d+) modes = (\d+) runs', 1))
N('p1.runs', grep(P1S, r'(\d+) mutants x (\d+) modes = (\d+) runs', 3))
N('p1.survive', grep(P1S, r'(\d+) runs survive as expected'))
# P2
N('p2.archive', grep(P2S, r'Archive size (\d+) bytes'))
N('p2.train', tab(P2S, '| File | Bytes |', {'File': 'train.txt'}, 'Bytes'))
N('p2.cols', grep(P2S, r'Rows without (\d+) tab-separated columns'))
N('p2.bad', grep(P2S, r'Rows without \d+ tab-separated columns: (\d+)'))
N('p2.c.lo', grep(P2S, r'Categorical columns (\d+)-(\d+):', 1))
N('p2.c.hi', grep(P2S, r'Categorical columns (\d+)-(\d+):', 2))
N('p2.hexlen', grep(P2S, r'fields are (\d+)-char lowercase hex'))
N('p2.hex', grep(P2S, r': (\d+) fields are \d+-char lowercase hex'))
N('p2.empty', grep(P2S, r'hex, (\d+) empty'))
N('p2.fields', grep(P2S, r'= (\d+) = \d+ rows'))
# P3
PT = r'2M: persistent LFU > LRU on (\d+) tables, tie on (\d+), worse on (\d+); LFURP > LRU on (\d+), tie (\d+), worse on (\d+)'
for i, k in enumerate(('p3.t2M.p.win', 'p3.t2M.p.tie', 'p3.t2M.p.lose', 'p3.t2M.r.win', 'p3.t2M.r.tie', 'p3.t2M.r.lose'), 1):
    N(k, grep(P3S, PT, i))
PT10 = r'10M: persistent LFU > LRU on (\d+), tie (\d+), worse on (\d+)'
for i, k in enumerate(('p3.t10M.p.win', 'p3.t10M.p.tie', 'p3.t10M.p.lose'), 1):
    N(k, grep(P3S, PT10, i))
PT10r = r'LFURP > LRU on (\d+), tie (\d+), worse on (\d+) \(tables 1, 4\)'
for i, k in enumerate(('p3.t10M.r.win', 'p3.t10M.r.tie', 'p3.t10M.r.lose'), 1):
    N(k, grep(P3S, PT10r, i))
N('p3.zipf.n', grep(P3S, r'(\d+) of (\d+) tables fitted at both sizes', 1))
N('p3.zipf.lo', grep(P3S, r'10M: ([\d.]+) \(table 2\) to ([\d.]+) \(table 5\)', 1))
N('p3.zipf.hi', grep(P3S, r'10M: ([\d.]+) \(table 2\) to ([\d.]+) \(table 5\)', 2))
N('p3.large.thr', grep(T7, r'unique ids >= ([\d,]+) at both row counts'))
for L in ROWS:
    for cap in ('64', '1,000', '10,000', '100,000'):
        for k, c in P3COL.items():
            N(f'p3.{L}.{cap.replace(",", "")}.{k}', tab(T7, f'### P3 combined (all 26 tables), {ROWS[L]} rows, hit %',
                                                       {'capacity (vectors per table)': cap}, c), 'hit')
    for k in ('LRU', 'LFUr', 'LFUp', 'WTLFU', 'ARC'):
        N(f'p3b.{L}.10000.{k}', tab(T7, f'### P3b total hit %, {ROWS[L]} rows', {'capacity (vectors, total)': '10,000'},
                                   P3COL[k]), 'hit')
N('p3b.tests', grep(P3BS, r'test_shared_cache.py` (\d+) tests'))
N('p3b.mut', grep(P3BS, r'mutation (\d+)/(\d+) \(`mutation.txt`\)', 1))
N('p3b.mut.n', grep(P3BS, r'mutation (\d+)/(\d+) \(`mutation.txt`\)', 2))
N('p5f.mism', tab(T7, '### P5f lockstep RTL vs netlist', {'run': 'd256_m0_1000MHz'}, 'mismatching cycles'),
  same=[tab(T7, '### P5f lockstep RTL vs netlist', {'run': f'd{d}_m{m}_{f}MHz'}, 'mismatching cycles')
        for d in ('16', '64', '256') for m in '01' for f in ('1000', '500')])
N('p3b.large.acc', grep(T7, r'2,000,000 rows: large tables = ([\d.]+)% of all accesses'))
N('p3b.large.hit.lo', tab(T7, '#### 2,000,000 rows: large tables', {'capacity': '256', 'policy': 'LRU'}, 'share of all hits %'))
N('p3b.large.hit.hi', tab(T7, '#### 2,000,000 rows: large tables', {'capacity': '256', 'policy': 'ARC'}, 'share of all hits %'))
# P4
N('p4.cfg', grep(P4S, r'## Ran vs skipped \((\d+) configs per GPU'))
N('p4.h100.ok', grep(P4S, r'H100: (\d+) ok, (\d+) skipped', 1))
N('p4.h100.skip', grep(P4S, r'H100: (\d+) ok, (\d+) skipped', 2))
N('p4.lb.pct', grep(P4S, r'CPU wall/iter within (\d+)% of the batch-64 wall'))
N('p4.lb.h100.lo', grep(P4S, r'\(H100 ([\d.]+)-([\d.]+), H200 ([\d.]+)-([\d.]+)\)', 1))
N('p4.lb.h100.hi', grep(P4S, r'\(H100 ([\d.]+)-([\d.]+), H200 ([\d.]+)-([\d.]+)\)', 2))
N('p4.lb.h200.lo', grep(P4S, r'\(H100 ([\d.]+)-([\d.]+), H200 ([\d.]+)-([\d.]+)\)', 3))
N('p4.lb.h200.hi', grep(P4S, r'\(H100 ([\d.]+)-([\d.]+), H200 ([\d.]+)-([\d.]+)\)', 4))
N('p4.b8k.h100.lo', grep(P4S, r'H100 B=8192: ([\d.]+)-([\d.]+)\.', 1))
N('p4.b8k.h100.hi', grep(P4S, r'H100 B=8192: ([\d.]+)-([\d.]+)\.', 2))
N('p4.b8k.h200.lo', grep(P4S, r'; B=8192: ([\d.]+)-([\d.]+)\.', 1))
N('p4.b8k.h200.hi', grep(P4S, r'; B=8192: ([\d.]+)-([\d.]+)\.', 2))
N('p4.b.min', grep(P4S, r'batch-(\d+) wall'))
N('p4.b.max', grep(P4S, r'H100 B=(\d+):'))
N('p4.iters', grep(P4S, r'launch loop over (\d+) iterations'))
N('p4.dim.hi', grep(P4S, r'Dim: (\d+) leaves the launch-bound region at a smaller batch than (\d+)', 1))
N('p4.dim.lo', grep(P4S, r'Dim: (\d+) leaves the launch-bound region at a smaller batch than (\d+)', 2))
# P14 table
for B in ('64', '1,024', '16,384'):
    b = B.replace(',', '')
    for lay, lk in (('per_table', 'pt'), ('concat', 'cc')):
        r = {'B': B, 'layout': lay}
        N(f'p14.all.{b}.{lk}', tab(P14S, '| B | layout', r, 'L2 hit % (all)'), 'hit')
        N(f'p14.dram.{b}.{lk}', tab(P14S, '| B | layout', r, 'DRAM B/lookup'))
        N(f'p14.us.{b}.{lk}', tab(P14S, '| B | layout', r, 'GPU us/batch'))
    N(f'p14.look.{b}', tab(P14S, '| B | layout', {'B': B, 'layout': 'per_table'}, 'lookups'))
N('p14.acc', grep(P14S, r'True; ([\d,]+) accesses, ([\d,]+) unique', 1))
N('p14.uniq', grep(P14S, r'True; ([\d,]+) accesses, ([\d,]+) unique', 2))
N('p14.bad.pct', grep(P14S, r'wrong denominator, gave ([\d.]+) %'))
N('p14.ncu', grep(P14S, r'ncu Version ([\d.]+)'))
N('p14.sectors', grep(P14S, r'A vector is \d+ B = (\d+) sectors'))
# P5 iterations, mode 0, 1 GHz netlists
P5SEC = {'p5': '### P5: rtl-v2-baseline', 'p5b': '### P5b: Stage-B tree', 'p5c': '### P5c tree + copies',
         'p5d': '### P5d: hit_idx priority tree', 'p5e': '### P5e: rtl-v2-final, timing-driven'}
for ph, sec in P5SEC.items():
    for d in ('16', '64', '256'):
        N(f'{ph}.f.{d}', tab(T7, sec, {'depth': d, 'mode': '0', 'clock target': '1000 MHz'}, 'Fmax MHz (pre-layout)'))
for d in ('16', '64', '256'):
    for m in '01':
        r = {'depth': d, 'mode': m, 'clock target': '1000 MHz'}
        for k, c in (('cells', 'cells'), ('ff', 'flip-flops'), ('area', 'area um^2'), ('fmax', 'Fmax MHz (pre-layout)')):
            N(f'p5e.{d}.{m}.{k}', tab(T7, P5SEC['p5e'], r, c))
        N(f'p5e.{d}.{m}.wns500', tab(T7, P5SEC['p5e'], dict(r, **{'clock target': '500 MHz'}), 'WNS ns'))
        N(f'p5d.noise.{d}.{m}', tab(T7, '#### old flow (P5d)', {'depth': d, 'mode': m}, 'spread'))
        N(f'p5e.noise.{d}.{m}', tab(T7, '#### P5e flow', {'depth': d, 'mode': m}, 'spread'))
N('clk.1000', tab(T7, P5SEC['p5e'], {'depth': '16', 'mode': '0', 'clock target': '1000 MHz'}, 'clock target'))
N('clk.500', tab(T7, P5SEC['p5e'], {'depth': '16', 'mode': '0', 'clock target': '500 MHz'}, 'clock target'))
N('p5e.budget', tab(T7, '### Flow settings and toolchain', {'item': 'timing-driven flow ABC budget, ps (ABC target = period - budget)'}, 'value'))
N('p5c.rule', grep(P5cS, r'Fmax\(tree \+ copies\) >= ([\d.]+) x Fmax'))
N('p5c.copy.m0', grep(P5cS, r'Rule met \(([+\d.]+)%, ([+\d.]+)%\)', 1))
N('p5c.copy.m1', grep(P5cS, r'Rule met \(([+\d.]+)%, ([+\d.]+)%\)', 2))
N('p5d.icarus', grep(P5dS, r'took Icarus (\d+) s per depth-256 lockstep run'))
N('p5f.cells', grep(P5fS, r'(\d+) cells against the liberty functions, (\d+) PASS', 1))
N('p5f.pass', grep(P5fS, r'(\d+) cells against the liberty functions, (\d+) PASS', 2))
N('p5f.netlists', grep(P5fS, r'- Netlists: (\d+) \(depth'))
N('p5f.cycles', tab(T7, '### P5f lockstep RTL vs netlist', {'run': 'd256_m0_1000MHz'}, 'cycles compared'))
N('p5f.eq', tab(T7, '### P5f equivalence RTL vs netlist', {'run': 'd16_m0_1000MHz'}, '$equiv cells proven / unproven'))
N('p5.mut.tb', grep(T7, r'All depths and modes: (\d+) mutant runs killed by the unit testbench, (\d+) by the lockstep check, (\d+) survived', 1))
N('p5.mut.ls', grep(T7, r'All depths and modes: (\d+) mutant runs killed by the unit testbench, (\d+) by the lockstep check, (\d+) survived', 2))
N('p5.mut.eq', grep(T7, r'All depths and modes: (\d+) mutant runs killed by the unit testbench, (\d+) by the lockstep check, (\d+) survived', 3))
CS = '### Counter saturation in the lockstep stimulus'
EXT('p7.sat.cyc.lo', [tab(T7, CS, {'depth': d, 'mode': m}, 'cycles with a line at max') for d in ('16', '64', '256') for m in '01'], 'min')
EXT('p7.sat.cyc.hi', [tab(T7, CS, {'depth': d, 'mode': m}, 'cycles with a line at max') for d in ('16', '64', '256') for m in '01'], 'max')
EXT('p7.sat.sup.lo', [tab(T7, CS, {'depth': d, 'mode': m}, 'hit increments suppressed at max') for d in ('16', '64', '256') for m in '01'], 'min')
EXT('p7.sat.sup.hi', [tab(T7, CS, {'depth': d, 'mode': m}, 'hit increments suppressed at max') for d in ('16', '64', '256') for m in '01'], 'max')
# P8 power components (NanGate45, 500 MHz netlists, Criteo slice row0, mode 0)
for d in ('16', '64', '256'):
    r = {'depth': d, 'mode': '0', 'activity source': 'Criteo slice row0'}
    for k, c in (('ck', '(b) CK all flip-flops'), ('ffo', '(d) flip-flop other internal'), ('comb', '(e) combinational internal'),
                 ('sw', '(f) switching'), ('leak', '(g) leakage mW')):
        N(f'p8.{d}.{k}', tab(P8R, '## 1. Power components', r, c))
N('p8.ckff', tab(P8R, '## 1. Power components', {'depth': '256', 'mode': '0', 'activity source': 'Criteo slice row0'},
                 '(a) CK fJ per flip-flop per cycle'))
N('p8.bias', grep(P8R, r'per-event recomputation [\d.]+ mW vs OpenSTA [\d.]+ mW \(\+([\d.]+)%\)'))
N('p8.cycles', tab(P8R, '## 1. Power components', {'depth': '256', 'mode': '0', 'activity source': 'Criteo slice row0'}, 'recorded cycles'))
# P9 full traces, 10M rows, and the candidate rules
for e, lab in (('16', '16 (P11)'), ('64', '64 (P11)'), ('256', '256'), ('1000', '1,000'), ('10000', '10,000'), ('100000', '100,000')):
    for k, c in (('LRU', 'LRU'), ('LFUr', 'LFU-reset (oldest)'), ('v2', 'RTL-exact mode 0')):
        N(f'p9t.{e}.{k}', tab(T7, '#### 10,000,000 rows: total hit %', {'entries': lab}, c), 'hit')
    N(f'p9t.{e}.v3', tab(T7, '#### 10,000,000 rows: candidate tie-break', {'entries': lab}, 'Rotate-victim mode 0'), 'hit')
    if e not in ('16', '64'):
        N(f'p9t.{e}.m1', tab(T7, '#### 10,000,000 rows: total hit %', {'entries': lab}, 'RTL-exact mode 1'), 'hit')
        N(f'p9t.{e}.vslru', tab(T7, '#### 10,000,000 rows: RTL-exact vs LRU', {'entries': lab}, 'RTL-exact m0 vs LRU'))
        N(f'p9t.{e}.gap', tab(T7, '#### 10,000,000 rows: RTL-exact vs LRU', {'entries': lab}, 'gap'))
        for k, c in (('rv', 'recovered % Rotate-victim mode 0'), ('rs', 'recovered % Rotate-step mode 0'),
                     ('yb', 'recovered % Young-bit mode 0'), ('rv1', 'recovered % Rotate-victim mode 1')):
            N(f'p9c.{e}.{k}', tab(T7, '#### 10,000,000 rows: candidate tie-break', {'entries': lab}, c))
N('p9.ff.rv', tab(CT, '| rule |', {'rule': 'R1 Rotate-victim'}, SC))
# P10, all six mode-0 runs
for d in ('16', '64', '256'):
    for sl in ('row0', 'row1M'):
        if f'p10.{d}.{sl}.v3' not in {k for k, _, _ in SPECS}:
            N(f'p10.{d}.{sl}.v3', tab(T7, LK, {'depth': d, 'mode': '0', 'slice': sl}, 'RTL hits'))
            N(f'p10.{d}.{sl}.v2', tab(T7, LK, {'depth': d, 'mode': '0', 'slice': sl}, V2C))
# P12 brackets for every version, mode and depth
for v in ('v2', 'v3'):
    for m in '01':
        for d in ('16', '64', '256'):
            for k, c in (('met', 'tightest met (ns)'), ('fail', 'loosest failed (ns)')):
                N(f'p12.b.{v}.{m}.{d}.{k}', tab(P12T, TL, {'version': v, 'mode': m, 'depth': d}, c))
N('p12.fmo.a.v2', tab(P12T, MO, {'version': 'v2', 'period (ns)': '0.65', 'flow': 'merge-off'}, 'area change'))
# P13 per run
for n, sl in NS:
    for k, c in (('logic', 'logic share'), ('cov', 'driver nets annotated'), ('reg', 'register share')):
        N(f'p13.{k}.{n}.{sl}', tab(P13T, PW, {'netlist': n, 'slice': sl}, c))
N('p13.variants', grep(P13S, r'timing checks 0% annotated \(conditional checks in the cell models; (\d+) write_sdf variants tried'))
# P15 final runs per version and period
TSF = 'multi-row dont_use + 2nd ecoRoute + setup target slack 0.03 + extra postRoute setup opt'
for v in ('v2', 'v3'):
    for per, fl in (('0.9', H2), ('1.0', H2), ('1.1', TSF)):
        pk = per.replace('.', '')
        for k, c in (('s', 'setup WNS ns'), ('sn', 'setup viol. paths'), ('h', 'hold WNS ns'), ('hn', 'hold viol. paths'),
                     ('drc', 'DRC'), ('la', 'logic cell area'), ('core', 'core area')):
            N(f'p15f.{v}.{pk}.{k}', pr(v, per, c, flow=fl))
    for sl in ('row1M',):
        for k, c in (('reg', 'register share'), ('clk', 'clock (clock tree) share'),
                     ('logic', 'logic (combinational) share = uncertainty bound')):
            N(f'p15.{k}.{v}.{sl}', tab(P15T, PP, {'netlist': v, 'slice': sl}, c))
SH = r'd256 PG-rail shorts \((\d+)/(\d+)/(\d+)/(\d+)\)'
for i, k in enumerate(('p15.sh.v2.08', 'p15.sh.v2.09', 'p15.sh.v3.08', 'p15.sh.v3.09'), 1):
    N(k, grep(P15S, SH, i))
N('p15.dontuse', tab(P15T, '## Fix: multi-row', {'run': 'v2_m0_d256_p0.8_nomerge', 'period ns': '1.0'},
                     'multi-row library cells set dont_use', first=True))


def _secs(t):
    h, m, s_ = (int(x) for x in t.split(':'))
    return h * 3600 + m * 60 + s_


_rt = []
for j, ln in enumerate(lines(P15T), 1):
    c = [x.strip() for x in ln.strip().strip('|').split('|')] if ln.startswith('| v') else []
    if len(c) == 4 and '_d256_' in c[0] and re.fullmatch(r'\d+:\d\d:\d\d', c[3]) and 'export' not in c[1] \
            and 'holdfix' not in c[1]:
        _rt.append(Src(c[3], P15T, j, f'[{c[0]}, {c[1]}, {c[2]} | real]'))
_rt.sort(key=lambda x: _secs(x.tok))
SPECS.append(('p15.rt.min', _rt[0].tok, f'min of {len(_rt)} depth-256 place-and-route run times: ' + _rt[0].note()))
SPECS.append(('p15.rt.max', _rt[-1].tok, f'max of {len(_rt)} depth-256 place-and-route run times: ' + _rt[-1].note()))
# P16 per design and corner
for dk, des, per in (('d16v3', 'd16 v3', '0.8'), ('d256v2', 'd256 v2', '1.0'), ('d256v3', 'd256 v3', '1.0'),
                     ('d256v2', 'd256 v2', '1.1'), ('d256v3', 'd256 v3', '1.1')):
    for cn in ('tt', 'ss', 'ff'):
        r = {'design': des, 'PnR period ns': per, 'corner': cn}
        N(f'p16t.{dk}.{per.replace(".", "")}.{cn}.s', tab(P16T, TC, r, 'setup WNS ns'))
        N(f'p16t.{dk}.{per.replace(".", "")}.{cn}.h', tab(P16T, TC, r, 'hold WNS ns'))
N('p16.dp.d16', tab(P16T, DER, {'design': 'd16 v3', 'PnR period ns': '0.8'}, 'derived slow-corner period ns'))
# environment rebuild and the claims audit
ER = 'results/P14/env_rebuild/result_460012.txt'
N('env.pkgs', grep(ER, r'conda-meta packages (\d+), files listed (\d+), missing (\d+)', 1))
N('env.files', grep(ER, r'conda-meta packages (\d+), files listed (\d+), missing (\d+)', 2))
N('env.missing', grep(ER, r'conda-meta packages (\d+), files listed (\d+), missing (\d+)', 3))
CA = r'Section A: (\d+) earlier claims\. (\d+) CONTRADICTED, (\d+) UNSUPPORTED, (\d+) NOT RE-RUN, (\d+) SUPPORTED'
for i, k in enumerate(('p7.a.n', 'p7.a.contra', 'p7.a.unsup', 'p7.a.notrerun', 'p7.a.sup'), 1):
    N(k, grep(P7S, CA, i))
CB = r'Section B: (\d+) new claims, .* (\d+) SUPPORTED, (\d+) NOT RE-RUN'
for i, k in enumerate(('p7.b.n', 'p7.b.sup', 'p7.b.notrerun'), 1):
    N(k, grep(P7S, CB, i))
N('p7.rerun.cells', grep(P7S, r'contradicted by the Yosys rerun \(([\d,]+) cells, ([\d,]+) flip-flops\)', 1))
N('p7.rerun.ff', grep(P7S, r'contradicted by the Yosys rerun \(([\d,]+) cells, ([\d,]+) flip-flops\)', 2))
N('old.kshare', grep(T7, r'Kernel share: .* = ([\d.]+)%'))


# ================================================================ implementation report (docs/synthesis_report), 2026-11-21
P12MAIN = '| version | mode | depth | period (ns) | WNS (ps)'
for v in ('v2', 'v3'):
    for m in '01':
        for d in ('16', '64', '256'):
            r = {'version': v, 'mode': m, 'depth': d, 'period (ns)': '2.0'}
            N(f'sr.ff.{v}.{m}.{d}', tab(P12T, P12MAIN, r, 'flip-flops'))
            N(f'sr.area.{v}.{m}.{d}', tab(P12T, P12MAIN, r, 'area (library units)'))
            N(f'sr.cells.{v}.{m}.{d}', tab(P12T, P12MAIN, r, 'cells'))
for v, d, per in (('v2', '64', '0.65'), ('v2', '64', '0.5'), ('v2', '256', '0.65'), ('v2', '256', '0.5'),
                  ('v3', '256', '0.65'), ('v3', '256', '0.5')):
    r = {'version': v, 'mode': '0', 'depth': d, 'period (ns)': per}
    N(f'sr.fx.{v}.{d}.{per.replace(".", "")}', tab(P12T, P12MAIN, r, 'Fmax (MHz)'))
    N(f'sr.wns.{v}.{d}.{per.replace(".", "")}', tab(P12T, P12MAIN, r, 'WNS (ps)'))
N('sr.per.065', tab(P12T, P12MAIN, {'version': 'v2', 'mode': '0', 'depth': '64', 'period (ns)': '0.65'}, 'period (ns)'))
N('sr.per.10', tab(P12T, P12MAIN, {'version': 'v2', 'mode': '0', 'depth': '64', 'period (ns)': '1.0'}, 'period (ns)'))
N('sr.per.13', tab(P12T, P12MAIN, {'version': 'v2', 'mode': '0', 'depth': '64', 'period (ns)': '1.3'}, 'period (ns)'))
for v in ('v2', 'v3'):
    for per in ('0.65', '0.8'):
        for fl in ('normal', 'merge-off'):
            r = {'version': v, 'period (ns)': per, 'flow': fl}
            k = f'sr.mo.{v}.{per.replace(".", "")}.{"mo" if fl == "merge-off" else "n"}'
            N(f'{k}.ff', tab(P12T, MO, r, 'flip-flops'))
            N(f'{k}.area', tab(P12T, MO, r, 'area (library units)'))
N('sr.p12.mo.a08.v2', tab(P12T, MO, {'version': 'v2', 'period (ns)': '0.8', 'flow': 'merge-off'}, 'area change'))
N('sr.p12.mo.a08.v3', tab(P12T, MO, {'version': 'v3', 'period (ns)': '0.8', 'flow': 'merge-off'}, 'area change'))
# P13
N('sr.p13.indelay', grep(P13T, r'SDF inputs (\d+) ps after the clock edge'))
for n, s in NS:
    N(f'sr.p13.cyc.{n}.{s}', tab(P13T, GL, {'netlist': n, 'slice': s}, 'cycles'))
    for k, c in (('sw', 'switching'), ('int', 'internal')):
        N(f'sr.p13.{k}.{n}.{s}', tab(P13T, PW, {'netlist': n, 'slice': s}, c), 'mW')
for n in ('v2', 'v3'):
    r = {'netlist': n, 'slice': 'row0'}
    N(f'sr.p13.pd.{n}', tab(P13T, GL, r, 'SDF path delays annotated', 0))
    N(f'sr.p13.pdn.{n}', tab(P13T, GL, r, 'SDF path delays annotated', 1))
    N(f'sr.p13.tc.{n}', tab(P13T, GL, r, 'SDF timing checks annotated', 0))
    N(f'sr.p13.tcn.{n}', tab(P13T, GL, r, 'SDF timing checks annotated', 1))
# P15
D16 = dict(v=None, period='0.8', flow='multi-row dont_use', run='v3_m0_d16_p0.8')
for k, c in (('h', 'hold WNS ns'), ('hn', 'hold viol. paths'), ('core', 'core area'), ('la', 'logic cell area'),
             ('conn', 'conn. problems all nets')):
    N(f'sr.d16.{k}', pr(col=c, **D16))
N('sr.d16.s', pr(col='setup WNS ns', **D16))
N('sr.p15.metal', pr('v2', '1.0', '4 PG nets metal only'),
  same=[pr(v, p, '4 PG nets metal only') for v in ('v2', 'v3') for p in ('1.0', '0.9')])
TS0 = 'multi-row dont_use + 2nd ecoRoute + setup target slack 0.03 + extra postRoute setup opt'
H1 = 'nodvts database + one extra optDesign -postRoute -hold and ecoRoute -fix_drc'
for v in ('v2', 'v3'):
    for k, fl in (('ts', TS0), ('h1', H1)):
        N(f'sr.hold.{v}.{k}', pr(v, '1.0', 'hold WNS ns', flow=fl))
        N(f'sr.hold.{v}.{k}.n', pr(v, '1.0', 'hold viol. paths', flow=fl))
    N(f'sr.first.{v}.s', pr(v, '0.8', 'setup WNS ns', flow='multi-row allowed'))
    N(f'sr.first.{v}.drc', pr(v, '0.8', 'DRC', flow='multi-row allowed'))
N('sr.htarget', grep(P15T, r'HOLDFIX_HOLD_TARGET ([\d.]+)'))
N('sr.cpus', grep(P15T, r'(\d+) CPUs each, up to (\d+) runs in parallel'))
for n in ('v2', 'v3'):
    r = {'netlist': n, 'slice': 'row0', 'mode': 'sdf'}
    N(f'sr.p15.pd.{n}', tab(P15T, PG, r, 'SDF path delays annotated', 0))
    N(f'sr.p15.tcn.{n}', tab(P15T, PG, r, 'SDF timing checks annotated', 1))
    N(f'sr.p15.spef.{n}', tab(P15T, PP, {'netlist': n, 'slice': 'row0'}, 'SPEF read (read_spef statistics)', 0))
    N(f'sr.p15.spef0.{n}', tab(P15T, PP, {'netlist': n, 'slice': 'row0'}, 'SPEF read (read_spef statistics)', 1))
N('sr.p15.indelay', tab(P15T, PG, {'netlist': 'v2', 'slice': 'row0', 'mode': 'sdf'}, 'clock / input delay ps', 1))
for n, s in NS:
    N(f'sr.p15.cyc.{n}.{s}', tab(P15T, PP, {'netlist': n, 'slice': s}, 'cycles'))
    for k, c in (('sw', 'switching'), ('int', 'internal')):
        N(f'sr.p15.{k}.{n}.{s}', tab(P15T, PP, {'netlist': n, 'slice': s}, c), 'mW')
# P16: derived 1.1 ns periods and the d16 derived period exist above; fast-corner setup WNS range
EXT('sr.ff.s.lo', [tab(P16T, TC, {'design': d, 'PnR period ns': p, 'corner': 'ff'}, 'setup WNS ns')
                   for d, p in (('d16 v3', '0.8'), ('d256 v2', '1.0'), ('d256 v3', '1.0'), ('d256 v2', '1.1'),
                                ('d256 v3', '1.1'))], 'min')


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
    srcs = [TEX] + sorted(TEX.parent.glob('gen_*.tex')) if _t == 'synth' else [TEX]
    tex = re.sub(r'(?<!\\)%.*', '', '\n'.join(s.read_text() for s in srcs))
    return set(re.findall(r'\\R\{([^{}]+)\}', tex))


def main():
    text = render()
    defined = {k for k, _, _ in SPECS}
    missing = sorted(used_keys() - defined)
    unused = sorted(defined - used_keys())
    if '--check' in sys.argv:
        bad = False
        if not OUT.exists() or OUT.read_text() != text:
            print(f'FAIL: {OUT.relative_to(ROOT)} is stale; run python3 -I tools/make_paper_macros.py --target {_t}')
            bad = True
        if missing:
            print(f'FAIL: keys used in {TEX.name} but not defined: {missing}')
            bad = True
        print(f'{len(SPECS)} macros; {len(unused)} defined but unused: {unused}')
        sys.exit(1 if bad else 0)
    OUT.write_text(text)
    print(f'wrote {OUT.relative_to(ROOT)}: {len(SPECS) - len(unused)} macros used by {TEX.name} '
          f'({len(SPECS)} extracted; extracted but unused: {unused})')
    if missing:
        print(f'FAIL: keys used in {TEX.name} but not defined: {missing}')
        sys.exit(1)


if __name__ == '__main__':
    main()
