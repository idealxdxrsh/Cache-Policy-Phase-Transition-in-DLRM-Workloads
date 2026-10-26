"""P7: build results/P7/TABLES.md from committed result files only.

Usage: python3 -I tools/make_tables.py [out, default results/P7/TABLES.md]   (run from anywhere inside the repo)
Every input is read with `git show HEAD:<path>`, so a file that is not committed cannot feed a table, and a file
with uncommitted edits is reported (its committed version is used). Each table names its source files and the
commit that last changed them (plus any git tag on that commit). No number is typed in by hand: every value
below is parsed from a file or computed from parsed values, and the formula is printed next to it.
"""
import csv
import gzip
import io
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True,
                           check=True).stdout.strip())


def git(*a, binary=False):
    r = subprocess.run(['git', '-C', str(ROOT), *a], capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode()


HEAD = git('rev-parse', '--short', 'HEAD').strip()
FILES = set(git('ls-files').splitlines())
DIRTY = {ln[3:] for ln in git('status', '--porcelain').splitlines()}
LAST = {}                                     # file -> last commit (short) that touched it
_c = None
for ln in git('log', '--format=C %h', '--name-only', 'HEAD').splitlines():
    if ln.startswith('C '):
        _c = ln[2:]
    elif ln and ln not in LAST:
        LAST[ln] = _c
TAGS = defaultdict(list)                      # commit (short) -> tags
for ln in git('show-ref', '--tags', '-d').splitlines():
    sha, ref = ln.split()
    if ref.endswith('^{}') or not git('cat-file', '-t', ref).strip() == 'tag':
        TAGS[sha[:len(HEAD)]].append(ref.split('/')[-1].replace('^{}', ''))
USED = []


def read(path):
    if path not in FILES:
        sys.exit(f'not committed: {path}')
    USED.append(path)
    b = git('show', f'HEAD:{path}', binary=True)
    return (gzip.decompress(b) if path.endswith('.gz') else b).decode()


def files(pattern):
    rx = re.compile('^' + re.escape(pattern).replace(r'\*', '[^/]*') + '$')
    return sorted(f for f in FILES if rx.match(f))


def prov(paths):
    commits = sorted({LAST[p] for p in paths})
    c = ', '.join(c + (f' (tag {", ".join(TAGS[c])})' if TAGS[c] else '') for c in commits)
    dirty = [p for p in paths if p in DIRTY]
    return f'commit {c}' + (f'; UNCOMMITTED EDITS in {len(dirty)} file(s), committed version used' if dirty else '')


def src(pattern, paths=None):
    paths = paths or files(pattern)
    return f'Source: `{pattern}` ({len(paths)} file{"s" if len(paths) > 1 else ""}), {prov(paths)}.'


def grab(pat, text, cast=float):
    m = re.search(pat, text, re.M)
    return cast(m.group(1)) if m else None


def pct(h, m):
    return f'{h / (h + m) * 100:.4f}'


out = []
W = out.append

# ---------------------------------------------------------------- P3
P3_CAPS_SHOWN = (64, 256, 1000, 10000, 100000)
LARGE_MIN = 150000                            # tools/p3_analysis.py UNIQUE_MIN


def p3_load(n):
    hm, pol, caps = {}, [], []
    for r in csv.DictReader(io.StringIO(read(f'results/P3/rows_{n}/figs/hit_rates.csv'))):
        hm[r['policy'], int(r['capacity']), r['table']] = (int(r['hits']), int(r['misses']))
        pol.count(r['policy']) or pol.append(r['policy'])
        caps.count(int(r['capacity'])) or caps.append(int(r['capacity']))
    z = {r['table']: r for r in csv.DictReader(io.StringIO(read(f'results/P3/rows_{n}/figs/zipf_per_table.csv')))}
    return hm, pol, sorted(caps), z


P3 = {n: p3_load(n) for n in (2000000, 10000000)}
W('## Dataset (P2): Criteo Display Advertising Challenge `train.txt`')
W(src('results/P2/SUMMARY.md', ['results/P2/SUMMARY.md']))
W(f'\nRows in the file: {grab(r"^- Rows: (\d+)", read("results/P2/SUMMARY.md"), int):,}. P3 and P3b use the first '
  '2,000,000 and the first 10,000,000 of them; 26 categorical columns = 26 tables.\n')
W('## P3: trace simulation, one private cache per table (26 caches), Criteo DAC first 2M and first 10M rows')
W('Limits: first 2,000,000 / 10,000,000 rows of Criteo DAC `train.txt` only; one private cache per table, capacity in '
  'vectors per table; CPU trace simulation (not gem5, not a GPU). Hit % = hits / (hits + misses) x 100.')
for n, (hm, pol, caps, z) in P3.items():
    W(f'\n### P3 combined (all 26 tables), {n:,} rows, hit %')
    W(src(f'results/P3/rows_{n}/figs/hit_rates.csv'))
    W('\n| capacity (vectors per table) | ' + ' | '.join(pol) + ' |')
    W('|---|' + '---|' * len(pol))
    for c in caps:
        W(f'| {c:,} | ' + ' | '.join(pct(*hm[p, c, 'all']) for p in pol) + ' |')
for n, (hm, pol, caps, z) in P3.items():
    W(f'\n### P3 per table at 256 vectors, {n:,} rows, hit % (Zipf alpha: rank-frequency fit, see P3 SUMMARY)')
    W(src(f'results/P3/rows_{n}/figs/*.csv'))
    W('\n| table | column | accesses | unique ids | Zipf alpha | ' + ' | '.join(pol) + ' |')
    W('|---|---|---|---|---|' + '---|' * len(pol))
    for t in sorted(z, key=int):
        r = z[t]
        W(f'| {t} | {r["column"]} | {int(r["accesses"]):,} | {int(r["unique"]):,} | {r["zipf_alpha"] or "no fit"} | '
          + ' | '.join(pct(*hm[p, 256, t]) for p in pol) + ' |')
large = sorted((t for t in P3[2000000][3] if all(int(P3[n][3][t]['unique']) >= LARGE_MIN for n in P3)), key=int)
W(f'\n### P3 large tables (unique ids >= {LARGE_MIN:,} at both row counts: tables {", ".join(large)}), hit %')
W(src('results/P3/rows_*/figs/*.csv') + ' Definition as in `tools/p3_analysis.py`. "combined" = sum of hits / sum of '
  'accesses over these tables.')
pol = P3[2000000][1]
W('\n| rows | capacity | table | ' + ' | '.join(pol) + ' |')
W('|---|---|---|' + '---|' * len(pol))
for n, (hm, _, _, z) in P3.items():
    for c in P3_CAPS_SHOWN:
        for t in large + ['combined']:
            ts = large if t == 'combined' else [t]
            W(f'| {n:,} | {c:,} | {t} | ' + ' | '.join(
                pct(sum(hm[p, c, x][0] for x in ts), sum(hm[p, c, x][1] for x in ts)) for p in pol) + ' |')

# ---------------------------------------------------------------- P3b
W('\n## P3b: ONE cache shared by all 26 tables, Criteo DAC first 2M and first 10M rows')
W('Limits: first 2M / 10M rows only; one shared cache (capacity = total vectors), not comparable 1:1 with P3\'s 26 '
  'private caches; access order = file order, tables 0..25 within a row (a modelling choice); CPU trace simulation.')
for n in (2000000, 10000000):
    parts = files(f'results/P3b/rows_{n}/parts/*.csv')
    tot, grp = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for p in parts:
        for r in csv.DictReader(io.StringIO(read(p))):
            k = (r['policy'], int(r['capacity']))
            tot[k][0] += int(r['hits']); tot[k][1] += int(r['misses'])
            if r['table'] in large:
                grp[k][0] += int(r['hits']); grp[k][1] += int(r['misses'])
    pols = list(dict.fromkeys(k[0] for k in sorted(tot, key=lambda k: k[1])))
    caps = sorted({k[1] for k in tot})
    W(f'\n### P3b total hit %, {n:,} rows (in brackets: hit % of the large tables {", ".join(large)} inside the shared cache)')
    W(src(f'results/P3b/rows_{n}/parts/*.csv', parts))
    W('\n| capacity (vectors, total) | ' + ' | '.join(pols) + ' |')
    W('|---|' + '---|' * len(pols))
    for c in caps:
        W(f'| {c:,} | ' + ' | '.join(f'{pct(*tot[p, c])} ({pct(*grp[p, c])})' for p in pols) + ' |')

# ---------------------------------------------------------------- P4
W('\n## P4: 26 x EmbeddingBag + MLP, fp32 inference, one H100 (job 413621) and one H200 (job 413622)')
W('Limits: CUDA-event timings only; NO hardware counters (ncu missing / ERR_NVGPUCTRPERM), so nothing here shows '
  'memory-boundedness, stalls or DRAM traffic. Many small-batch cells are launch-bound (see `results/P4/SUMMARY.md`), '
  'where the embedding share is a share of launch time. Synthetic index patterns plus Criteo-hashed ids; bag size 1.')
LB_TOL = grab(r'^LB_TOL = ([\d.]+)', read('tools/p4_results.py'))
for gpu in ('h100_413621', 'h200_413622'):
    path = f'results/P4/{gpu}/results.csv'
    rows = list(csv.DictReader(io.StringIO(read(path))))
    batches = sorted({int(r['batch']) for r in rows})
    st = defaultdict(int)
    for r in rows:
        st[r['status']] += 1
    W(f'\n{gpu.split("_")[0].upper()} ({src(path)[8:-1]}): {len(rows)} configurations, ' +
      ', '.join(f'{v} {k}' for k, v in sorted(st.items())) + '; skip reasons: ' +
      ('; '.join(sorted({r["note"] for r in rows if r["status"] != "ok"})) or 'none') + '.')
    for col, lab, fmt in (('emb_ms_median', 'embedding median ms (26 tables)', '{:.4f}'),
                          ('mlp_ms_median', 'MLP median ms', '{:.4f}'),
                          ('emb_share_median', 'embedding share, median emb / (emb + MLP)', '{:.4f}')):
        W(f'\n### P4 {gpu.split("_")[0].upper()}: {lab}')
        W(src(path))
        W('\n| rows | dim | pattern | ' + ' | '.join(f'B={b}' for b in batches) + ' |')
        W('|---|---|---|' + '---|' * len(batches))
        cell = {(r['rows'], r['dim'], r['pattern'], int(r['batch'])): r for r in rows}
        if col == 'emb_share_median':
            W(f'"L" = launch-bound: CPU wall per iteration <= {LB_TOL} x the batch-64 CPU wall of the same rows/dim/pattern '
              f'(criterion `LB_TOL = {LB_TOL}` in `tools/p4_results.py`, i.e. within {(LB_TOL - 1) * 100:.0f}%).')
        for key in sorted({(r['rows'], r['dim'], r['pattern']) for r in rows},
                          key=lambda k: (int(k[0]), int(k[1]), k[2])):
            vals = []
            for b in batches:
                r = cell.get((*key, b))
                if r is None or r['status'] != 'ok':
                    vals.append('-' if r is None else r['status'])
                    continue
                v = fmt.format(float(r[col]))
                b64 = cell.get((*key, 64))
                if col == 'emb_share_median' and b64 and b64['status'] == 'ok' and \
                        float(r['cpu_wall_ms_per_iter']) <= LB_TOL * float(b64['cpu_wall_ms_per_iter']):
                    v += ' L'
                vals.append(v)
            W(f'| {int(key[0]):.0e} | {key[1]} | {key[2]} | ' + ' | '.join(vals) + ' |')

# ---------------------------------------------------------------- RTL and simulator parameters
RTL, TB, SIM = 'rtl/v2/lfu_cache_controller.v', 'rtl/v2/tb_lfu_cache.sv', 'trace_sim/run_trace_sim.py'
rtl = read(RTL)
if git('show', f'rtl-v2-final:{RTL}') != rtl:
    sys.exit(f'{RTL} differs from tag rtl-v2-final')
par = dict(re.findall(r'^\s+parameter (\w+)\s*=\s*(\d+)', rtl, re.M))
tests = sorted({int(n) for n in re.findall(r'"\[(\d+)\] ', read(TB))})
sim_cap = sorted({int(n) for n in re.findall(r'min\((\d+), self\.', read(SIM))})
W('\n## RTL and simulator parameters')
W(src(f'{RTL}, {TB}, {SIM}', [RTL, TB, SIM]) + f' `{RTL}` is identical to tag rtl-v2-final.')
W('\n| item | value |')
W('|---|---|')
for k, v in par.items():
    W(f'| RTL parameter {k} (default) | {v} |')
W(f'| RTL counter saturation value, 2^COUNTER_WIDTH - 1 | {2 ** int(par["COUNTER_WIDTH"]) - 1} |')
W(f'| unit testbench tests | {len(tests)} ([{tests[0]}]..[{tests[-1]}]) |')
W(f'| trace simulator LFU counter cap (`min(N, ...)` in {SIM}) | {", ".join(map(str, sim_cap))} |')

# ---------------------------------------------------------------- P5 .. P5e
W('\n## P5-P5e: rtl/v2 on NanGate45 (Yosys 0.33 + OpenSTA 3.1.0), timing and area')
W('Limits: NanGate45 typical liberty (open PDK), NOT TSMC; pre-layout (wire-load 5K_hvratio_1_1, ideal clock, no '
  'placement or routing); area = sum of liberty cell areas, not a placed area; no power step was run, so no power '
  'numbers. Fmax = 1 / (period - WNS) from the worst setup path of that netlist; "met" = WNS >= 0. The flow alone '
  'moves Fmax by 1.96-16.62% (old flow) and 4.92-16.23% (P5e flow) on identical logic (`results/P5d/NOISE.md`, '
  '`results/P5e/COMPARE.md` s.3).')
PHASES = [('P5', 'results/P5', 'rtl-v2-baseline, first flow'),
          ('P5b', 'results/P5b', 'Stage-B tree + address copies'),
          ('P5c tree only', 'results/P5c/tree_only', 'Stage-A tree, no copies (not kept)'),
          ('P5c tree + copies', 'results/P5c/tree_copies', 'Stage-A tree + copies (kept)'),
          ('P5d', 'results/P5d', 'hit_idx priority tree = rtl-v2-final, old flow'),
          ('P5e', 'results/P5e/new', 'rtl-v2-final, timing-driven ABC flow (current numbers)')]


def violators(sta):                           # distinct pins/nets with max slew/cap/fanout VIOLATED, rst_n excluded
    return {ln.split()[0] for ln in sta.splitlines()
            if ln.rstrip().endswith('(VIOLATED)') and 'slack' not in ln and ln.split()[0] != 'rst_n'}


def fmax_of(path):                            # Fmax MHz of one sta.txt (None if met)
    sta = read(path)
    period, wns = grab(r'^PERIOD_NS (\S+)', sta), grab(r'^wns max (\S+)', sta)
    return 1e3 / (period - wns) if wns < 0 else None


for name, d, what in PHASES:
    stas = files(f'{d}/d*_m*_*MHz/sta.txt')
    W(f'\n### {name}: {what}')
    W(src(f'{d}/d*_m*_*MHz/{{sta,stat}}.txt', stas + files(f'{d}/d*_m*_*MHz/stat.txt')))
    W('\n| depth | mode | clock target | cells | flip-flops | area um^2 | WNS ns | worst hold slack ns | Fmax MHz (pre-layout) | other slew/cap violators |')
    W('|---|---|---|---|---|---|---|---|---|---|')
    key = lambda p: tuple(int(x) for x in re.search(r'd(\d+)_m(\d)_(\d+)MHz', p).groups())
    for s in sorted(stas, key=lambda p: (key(p)[0], key(p)[1], -key(p)[2])):
        dd, m, f = key(s)
        sta, stat = read(s), read(s.replace('sta.txt', 'stat.txt'))
        period, wns, hold = grab(r'^PERIOD_NS (\S+)', sta), grab(r'^wns max (\S+)', sta), grab(r'^worst slack min (\S+)', sta)
        ffs = sum(int(n) for n in re.findall(r'^\s+S?DFF\w*\s+(\d+)', stat, re.M))
        fmax = f'{1e3 / (period - wns):.1f}' if wns < 0 else f'met ({f} MHz)'
        W(f'| {dd} | {m} | {f} MHz | {grab(r"Number of cells:\s+(\d+)", stat, int):,} | {ffs:,} | '
          f'{grab(r"Chip area for module .*: ([\d.]+)", stat):.3f} | {wns:.4f} | {hold:.4f} | {fmax} | {len(violators(sta))} |')

W('\n### P5d (old flow) -> P5e (timing-driven flow), same RTL rtl-v2-final, 1 GHz netlists')
W(src('results/P5{d,e/new}/d*_m*_1000MHz/{sta,stat}.txt', files('results/P5d/d*_m*_1000MHz/sta.txt') +
      files('results/P5e/new/d*_m*_1000MHz/sta.txt')))
W('\n| depth | mode | Fmax MHz P5d -> P5e | area um^2 P5d -> P5e | area change | other slew/cap violators P5d -> P5e |')
W('|---|---|---|---|---|---|')
for dd in (16, 64, 256):
    for m in (0, 1):
        a, b = (f'{x}/d{dd}_m{m}_1000MHz' for x in ('results/P5d', 'results/P5e/new'))
        ar = [grab(r"Chip area for module .*: ([\d.]+)", read(f'{x}/stat.txt')) for x in (a, b)]
        vi = [len(violators(read(f'{x}/sta.txt'))) for x in (a, b)]
        W(f'| {dd} | {m} | {fmax_of(a + "/sta.txt"):.1f} -> {fmax_of(b + "/sta.txt"):.1f} | {ar[0]:.3f} -> {ar[1]:.3f} | '
          f'{(ar[1] / ar[0] - 1) * 100:+.2f}% | {vi[0]} -> {vi[1]} |')
ref = read('results/P5d/d16_m0_1000MHz/sta.txt')
clkq = float(next(ln.split()[3] for ln in ref[ref.index('Path Type: max'):].splitlines() if '/Q (' in ln))
setup = grab(r'^\s+-([\d.]+)\s+\S+\s+library setup time', ref)
W(f'\nP5e ABC target margin (`results/P5d/d16_m0_1000MHz/sta.txt`, worst path of the P5d depth-16 mode-0 1 GHz run): '
  f'clk->Q {clkq} ns + setup {setup} ns = {(clkq + setup) * 1e3:.1f} ps; ABC target = period - {(clkq + setup) * 1e3:.1f} ps. '
  'The P5e script was chosen on one pilot (depth 16, mode 0) with no ablation (`results/P5e/SUMMARY.md`).')

W('\n### Flow noise floor: Fmax MHz of 8 same-logic designs, 1 GHz netlists')
W('Designs: final RTL, the flat-vector ("packed") form of the same hit tree, and 3 one-line rewrites of each '
  '(`tools/p5d_null_variants.py`). Spread = max / min - 1. Any spread is flow variation, not a design effect.')
NOISE = {'old flow (P5d)': [('final', 'results/P5d'), ('final null_tagcmp_swap', 'results/P5d/noise/null_tagcmp_swap'),
                            ('final null_hitor_swap', 'results/P5d/noise/null_hitor_swap'),
                            ('final null_stageB_gt', 'results/P5d/noise/null_stageB_gt'),
                            ('packed', 'results/P5d/attempt1_packed_vectors')] +
         [(f'packed {v}', f'results/P5d/attempt1_packed_vectors/noise/{v}') for v in
          ('null_tagcmp_swap', 'null_hitor_swap', 'null_stageB_gt')],
         'P5e flow': [('final', 'results/P5e/new')] +
         [(f'final {v}', f'results/P5e/noise/final_{v}') for v in ('null_tagcmp_swap', 'null_hitor_swap', 'null_stageB_gt')] +
         [('packed', 'results/P5e/noise/packed')] +
         [(f'packed {v}', f'results/P5e/noise/packed_{v}') for v in ('null_tagcmp_swap', 'null_hitor_swap', 'null_stageB_gt')]}
for flow, var in NOISE.items():
    paths = [f'{d}/d{dd}_m{m}_1000MHz/sta.txt' for _, d in var for dd in (16, 64, 256) for m in (0, 1)]
    W(f'\n#### {flow}')
    W(src(f'{len(var)} design directories, d*_m*_1000MHz/sta.txt', paths))
    W('\n| depth | mode | ' + ' | '.join(n for n, _ in var) + ' | min | max | spread |')
    W('|---|---|' + '---|' * (len(var) + 3))
    for dd in (16, 64, 256):
        for m in (0, 1):
            v = [fmax_of(f'{d}/d{dd}_m{m}_1000MHz/sta.txt') for _, d in var]
            W(f'| {dd} | {m} | ' + ' | '.join(f'{x:.1f}' for x in v) +
              f' | {min(v):.1f} | {max(v):.1f} | {(max(v) / min(v) - 1) * 100:.2f}% |')

mut = read('results/P5d/mutation.txt')
W(f'\n### Mutation check of the final RTL (`results/P5d/mutation.txt`, {prov(["results/P5d/mutation.txt"])})')
W(f'\nAll depths and modes: {len(re.findall(r": KILLED by testbench", mut))} mutant runs killed by the unit testbench, '
  f'{len(re.findall(r"; KILLED by lockstep", mut))} by the lockstep check, '
  f'{len(re.findall(r": survived \(equivalent", mut))} survived as equivalent; '
  f'"{re.search(r"^RESULT: .*", mut, re.M).group(0)}".')

# ---------------------------------------------------------------- P5f
G = 'results/P5f_gls'
W('\n## P5f: functional gate-level simulation, zero delay, cell models generated by Yosys from the liberty file')
W('Limits: P5e-flow netlists of rtl-v2-final (NanGate45, not TSMC, pre-layout); zero delay, no SDF, so no timing is '
  'checked; cell models from Yosys `read_liberty` (checked against the liberty functions, `CELLCHECK.md`); lockstep = '
  '200,000 random cycles, one seed; equivalence proven only at depth 16 (with async2sync, induction from matched '
  'registers equal).')
runkey = lambda p: tuple(-int(x) if i == 2 else int(x) for i, x in enumerate(re.search(r'd(\d+)_m(\d)_(\d+)MHz', p).groups()))
lk = sorted(files(f'{G}/cluster/lockstep/*.txt'), key=runkey)
W('\n### P5f lockstep RTL vs netlist (cluster, Icarus 11.0)')
W(src(f'{G}/cluster/lockstep/*.txt', lk))
W('\n| run | cycles compared | responses | hits | misses | mismatching cycles | X cycles netlist / RTL | verdict | vvp wall | vvp peak RSS kB |')
W('|---|---|---|---|---|---|---|---|---|---|')
for p in lk:
    t = read(p)
    kv = dict(re.findall(r'(\w+)=(\d+)', t[t.index('gls_lockstep'):].splitlines()[0]))
    el = re.findall(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (\S+)', t)
    rss = re.findall(r'Maximum resident set size \(kbytes\): (\d+)', t)
    verdict = 'PASSED' if 'GLS LOCKSTEP PASSED' in t else 'FAILED'
    W(f'| {Path(p).stem} | {kv["cycles"]} | {kv["responses"]} | {kv["hits"]} | {kv["misses"]} | {kv["mismatching_cycles"]} | '
      f'{kv["x_cycles_netlist"]} / {kv["x_cycles_rtl"]} | {verdict} | {el[-1]} | {rss[-1]} |')
W('\n### P5f unit testbench (unmodified rtl/v2/tb_lfu_cache.sv) on the netlists')
loc, clu = sorted(files(f'{G}/sim/*.txt'), key=runkey), sorted(files(f'{G}/cluster/sim/*.txt'), key=runkey)
W(src(f'{G}/sim/*.txt (local, Icarus 12.0)', loc) + ' ' + src(f'{G}/cluster/sim/*.txt (cluster, Icarus 11.0)', clu))
W('\n| run | where | result | compile | run |')
W('|---|---|---|---|---|')
for p in loc + clu:
    t = read(p)
    res = 'ALL TESTS PASSED' if 'ALL TESTS PASSED' in t else 'NOT PASSED'
    if '/cluster/' in p:
        el = re.findall(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (\S+)', t)
        W(f'| {Path(p).stem} | cluster | {res} | {el[0]} | {el[-1]} |')
    else:
        W(f'| {Path(p).stem} | local | {res} | {grab(r"compile_s=([\d.]+)", t):.2f} s | {grab(r"run_s=([\d.]+)", t):.2f} s |')
W('\n### P5f equivalence RTL vs netlist, depth 16 only (local, Yosys 0.33)')
eq = files(f'{G}/equiv/*.txt')
W(src(f'{G}/equiv/*.txt + .log.gz', eq + files(f'{G}/equiv/*.log.gz')))
W('\n| run | exit (0 = all proven) | $equiv cells proven / unproven | wall s |')
W('|---|---|---|---|')
for p in eq:
    t, lg = read(p), read(p.replace('.txt', '.log.gz'))
    pr = re.findall(r'Of those cells (\d+) are proven and (\d+) are unproven', lg)[-1]
    W(f'| {Path(p).stem} | {grab(r"exit=(\d+)", t, int)} | {pr[0]} / {pr[1]} | {grab(r"wall_s=(\d+)", t, int)} |')
cc, cov = read(f'{G}/CELLCHECK.md'), read(f'{G}/COVERAGE.md')
W(f'\nCell models (`{G}/CELLCHECK.md`, `{G}/COVERAGE.md`, {prov([f"{G}/CELLCHECK.md", f"{G}/COVERAGE.md"])}): '
  f'{len(re.findall(r"\| PASS \|$", cc, re.M))} cells PASS, {len(re.findall(r"\| FAIL \|$", cc, re.M))} FAIL '
  f'({", ".join(re.findall(r"^\| (\w+) \|.*\| FAIL \|$", cc, re.M))}); '
  f'{grab(r"(\d+) distinct cell types", cov, int)} distinct cell types in the netlists, '
  f'"{re.search(r"Cell types without full coverage: \d+", cov).group(0)}", "{re.search(r"Scan flip-flops.*", cov).group(0)}"')

# ---------------------------------------------------------------- older evidence
W('\n## Older evidence, not reproduced in P0-P5f (values parsed from the committed files)')
W('\n### gem5 2 MB L2, LRU vs LFU (gem5 = CPU (X86TimingSimpleCPU) + DDR4, not a GPU)')
lru, lfu = read('gem5/results/lru_2mb/stats.txt'), read('gem5/results/lfu_2mb/stats.txt')
W(src('gem5/results/l*_2mb/stats.txt', ['gem5/results/lru_2mb/stats.txt', 'gem5/results/lfu_2mb/stats.txt']) +
  ' No 256 kB or 512 kB stats file is committed (see `gem5/results/README.md`).')
W('\n| stat | LRU | LFU |')
W('|---|---|---|')
S = {}
for k in ('system.l2cache.overallHits::total', 'system.l2cache.overallMisses::total', 'system.mem_ctrl.dram.numReads::total',
          'system.cpu.ipc', 'simTicks'):
    a, b = (grab(rf'^{re.escape(k)}\s+(\S+)', x, str) for x in (lru, lfu))
    S[k] = (a, b)
    W(f'| {k} | {a or "not in file"} | {b or "not in file"} |')
h, m = 'system.l2cache.overallHits::total', 'system.l2cache.overallMisses::total'
hr = [int(S[h][i]) / (int(S[h][i]) + int(S[m][i])) * 100 for i in (0, 1)]
W(f'\nDerived: L2 hit % = hits / (hits + misses): LRU {hr[0]:.2f}, LFU {hr[1]:.2f} ({hr[1] - hr[0]:+.2f} pp); '
  f'L2 misses LRU - LFU = {int(S[m][0]) - int(S[m][1]):,} ({(int(S[m][1]) / int(S[m][0]) - 1) * 100:+.2f}%); '
  f'S = misses LRU / LFU = {int(S[m][0]) / int(S[m][1]):.4f}.')
W('\n### H100 profiler output, job 149046 (old benchmark, small batch, launch-bound; not P4)')
prof = read('profiling/gpu_profile_149046_out.txt')


def self_cuda_us(name):                       # "Self CUDA" column (6th after the name) of the first row with that name
    for ln in prof.splitlines():
        f = ln.split()
        if f and f[0] == name:
            v = f[6]
            return float(v[:-2]) * (1e3 if v.endswith('ms') else 1)
    sys.exit(f'{name} not in profiler output')


emb, sp_us, dn = self_cuda_us('aten::_embedding_bag'), self_cuda_us('2_sparse_memory_lookups'), self_cuda_us('1_dense_compute_mlp')
tot = grab(r'Self CUDA time total: ([\d.]+)us', prof)
sp = sp_us / 1e3
W(src('profiling/gpu_profile_149046_out.txt', ['profiling/gpu_profile_149046_out.txt']) +
  ' Values from the "Self CUDA" column.')
f_k, f_r, s = emb / tot, sp / (sp + dn / 1e3), int(S[m][0]) / int(S[m][1])
amd = lambda f: (1 / ((1 - f) + f / s) - 1) * 100
W(f'\n- Kernel share: aten::_embedding_bag self CUDA {emb} us / Self CUDA time total {tot} us = {f_k * 100:.2f}%.')
W(f'- Annotated-range ratio: {sp} ms / ({sp} ms + {dn} us) = {f_r * 100:.2f}%; {sp} ms / {dn} us = {sp * 1e3 / dn:.2f}x. '
  'The ranges include launch gaps and idle time; they are not stall measurements.')
W(f'- Amdahl 1 / ((1 - f) + f / S) - 1 with S = {s:.4f}: f = kernel share -> {amd(f_k):+.2f}%; f = range ratio -> '
  f'{amd(f_r):+.2f}%. Both assume the gem5 CPU/DDR4 miss reduction carries over fully to GPU embedding time (untested).')
W('\n### v1 waveform `rtl/v1_verified/lfu_cache_waves.vcd` (v1 LFU.v; testbench prints, checks nothing)')
vcd = read('rtl/v1_verified/lfu_cache_waves.vcd')
ids = dict((i, n) for i, n in re.findall(r'^\$var reg 8 (\S+) \\(freq_count\[\d+\]) ', vcd, re.M))
last, peak, t_end = {}, defaultdict(int), 0
for ln in vcd[vcd.index('$enddefinitions'):].splitlines():
    if ln.startswith('#'):
        t_end = int(ln[1:])
    elif ln.startswith('b'):
        v, i = ln[1:].split()
        if i in ids and 'x' not in v:
            last[ids[i]] = int(v, 2); peak[ids[i]] = max(peak[ids[i]], int(v, 2))
W(src('rtl/v1_verified/lfu_cache_waves.vcd', ['rtl/v1_verified/lfu_cache_waves.vcd']) + f' Timescale 1 ps, last time stamp {t_end:,} ps.')
W('\n| counter | final value | max value |')
W('|---|---|---|')
for n in sorted(last, key=lambda n: -last[n]):
    if last[n] != 1 or peak[n] != 1:
        W(f'| {n} | {last[n]} | {peak[n]} |')
W(f'| all other freq_count[i] ({sum(1 for n in last if last[n] == 1 and peak[n] == 1)}) | 1 | 1 |')

head = ['# TABLES: all results tables, generated from committed files only',
        f'Generated by `tools/make_tables.py` at HEAD {HEAD}; {len(set(USED))} committed files read with `git show HEAD:<path>`.',
        'Each table states its limits and its source files with the commit that last changed them. Do not edit by hand.', '']
dst = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'results/P7/TABLES.md')
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text('\n'.join(head + out) + '\n')
print(f'wrote {dst.relative_to(ROOT)} ({len(set(USED))} source files)')
