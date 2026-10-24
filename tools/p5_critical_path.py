"""Per-cell tables of the worst setup path from the saved P5 OpenSTA reports (CRITICAL_PATH.md).

Usage: python -I tools/p5_critical_path.py results/P5 d16_m0_1000MHz d256_m0_1000MHz
Reads <run>/sta.txt (report_checks -path_delay max -fields {slew cap fanout}) and, when present,
<run>/netlist.v (not committed) for the register names on the start/end flip-flops' Q pins.
Prints Markdown to stdout. NanGate45, not TSMC. Pre-layout.
"""
import re
import sys
from collections import Counter
from pathlib import Path

ROW = re.compile(r'^\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([v^])\s+(\S+)/(\w+)\s+\((\w+)\)')
CK = re.compile(r'^\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[v^]\s+(\S+)/CK\s+\((\w+)\)')
BUFS = ('BUF_', 'CLKBUF_')


def q_name(netlist, inst):
    if not netlist.exists():
        return 'netlist not present'
    pat = re.compile(r'^\s+\w+ ' + re.escape(inst) + r' \((.*?)\);', re.S | re.M)
    m = pat.search(netlist.read_text())
    q = re.search(r'\.Q\(([^)]*)\)', m.group(1)) if m else None
    return q.group(1).strip() if q else 'not found'


def parse(run):
    sta = (run / 'sta.txt').read_text()
    i = sta.index('Path Type: max')
    head, body = sta[:i], sta[i:sta.index('slack (', i)]
    start = re.findall(r'^Startpoint: (\S+) \((.*)\)$', head, re.M)[-1]
    end = re.findall(r'^Endpoint: (\S+) \((.*)\)$', head, re.M)[-1]
    rows = [ROW.match(ln).groups() for ln in body.splitlines() if ROW.match(ln)]
    arrival = float(re.search(r'^\s+([\d.]+)\s+data arrival time', body, re.M).group(1))
    setup = float(re.search(r'^\s+-([\d.]+)\s+[\d.]+\s+library setup time', body, re.M).group(1))
    slack = float(re.search(r'^\s+(-?[\d.]+)\s+slack', sta[i:], re.M).group(1))
    period = float(re.search(r'^PERIOD_NS (\S+)', sta, re.M).group(1))
    return start, end, rows, arrival, setup, slack, period


def main():
    root = Path(sys.argv[1])
    out = []
    for name in sys.argv[2:]:
        run = root / name
        start, end, rows, arrival, setup, slack, period = parse(run)
        nl = run / 'netlist.v'
        out += [f'## {name} (`{run}/sta.txt`)', '',
                f'- Start point: `{start[0]}` ({start[1]}), Q = `{q_name(nl, start[0])}`',
                f'- End point: `{end[0]}` ({end[1]}), Q = `{q_name(nl, end[0])}`, path ends at its D pin',
                f'- Cells on the path: {len(rows)} (including the start flip-flop clock-to-Q); data arrival '
                f'{arrival:.4f} ns; library setup time {setup:.4f} ns; period {period:.4f} ns; slack {slack:.4f} ns', '']
        cnt, dsum = Counter(), Counter()
        for r in rows:
            cnt[r[8]] += 1
            dsum[r[8]] += float(r[3])
        buf = [r for r in rows if r[8].startswith(BUFS)]
        bdel = sum(float(r[3]) for r in buf)
        # longest run of consecutive buffers
        best = cur = 0
        best_end = 0
        cur_sum = best_sum = 0.0
        for k, r in enumerate(rows):
            if r[8].startswith(BUFS):
                cur += 1
                cur_sum += float(r[3])
                if cur > best:
                    best, best_sum, best_end = cur, cur_sum, k
            else:
                cur, cur_sum = 0, 0.0
        out += [f'- Buffers (BUF_*/CLKBUF_*) on the path: {len(buf)}, sum of their delays {bdel:.4f} ns '
                f'({bdel / arrival:.4f} of the arrival time).',
                f'- Longest run of consecutive buffers: {best} cells, {best_sum:.4f} ns '
                f'(rows {best_end - best + 2}-{best_end + 1} of the table below).',
                f'- Sum of the non-buffer cell delays: {arrival - bdel:.4f} ns.', '',
                '| cell type | count | sum of delays ns |', '|---|---|---|']
        for c, n in sorted(cnt.items(), key=lambda t: -dsum[t[0]]):
            out.append(f'| {c} | {n} | {dsum[c]:.4f} |')
        out += ['', '| # | instance/pin | cell | edge | fanout | cap fF | slew ns | delay ns | arrival ns |',
                '|---|---|---|---|---|---|---|---|---|']
        for k, r in enumerate(rows, 1):
            out.append(f'| {k} | {r[6]}/{r[7]} | {r[8]} | {r[5]} | {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |')
        out.append('')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
