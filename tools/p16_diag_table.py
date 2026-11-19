"""P16 I/O hold diagnosis table (numbers only) from the report_timing -early -path_type full_clock reports of
cadence/pnr/p16_diag_io.tcl, copied to ~/c2_results/p16/<run>_diag/rpt/diag/.

Usage: python3 -I tools/p16_diag_table.py [diag folder]   (Markdown to stdout)

Per corner (tt, ss), worst input-to-register and worst register-to-output hold path:
  in2reg : input delay (SDC, ideal clock edge 0), data arrival at the register, capture clock: source insertion delay
           (per-view clock source latency, 0 if the report has none), clock arrival at the register, tree insertion
           delay = arrival - source latency; hold time; required; slack.
  reg2out: launch clock source latency, clock arrival at the launching register's clock pin (arrival just before the
           row of that register), data arrival at the output, output (external) delay, required, slack.
Prints no instance, pin, cell or library names.
"""
import re
import sys
from pathlib import Path


def num(pat, t, default=None):
    m = re.search(pat, t, re.M)
    if not m:
        if default is not None:
            return default
        raise SystemExit(f'no match for {pat}')
    return float(m.group(1))


def rows(block):
    """Table rows of one path table: (instance, arrival)."""
    out = []
    for ln in block.splitlines():
        c = [x.strip() for x in ln.split('|')]
        if len(c) >= 7 and re.fullmatch(r'-?\d+\.\d+', c[5] or ''):
            out.append((c[1], float(c[5])))
    return out


def in2reg(t):
    head, other = t.split('Other End Path:', 1) if 'Other End Path:' in t else (t, '')
    # the capture-clock header lines sit just before "Other End Path:" (after the data path table)
    cap_hdr = head.rsplit('Clock Rise Edge', 1)[1]
    other_rows = rows(other)
    return {
        'input delay': num(r'\+ Input Delay\s+(-?\d+\.\d+)', t),
        'data arrival': num(r'^\s*Arrival Time\s+(-?\d+\.\d+)', t),
        'source latency': num(r'\+ Source Insertion Delay\s+(-?\d+\.\d+)', cap_hdr, 0.0),
        'clock arrival': num(r'Other End Arrival Time\s+(-?\d+\.\d+)', t),
        'last row': other_rows[-1][1] if other_rows else None,
        'hold': num(r'^\+ Hold\s+(-?\d+\.\d+)', t),
        'required': num(r'= Required Time\s+(-?\d+\.\d+)', t),
        'slack': num(r'Slack Time\s+(-?\d+\.\d+)', t),
    }


def reg2out(t):
    beg = re.search(r'^Beginpoint:\s+(\S+)', t, re.M).group(1)
    inst = beg.rsplit('/', 1)[0]
    r = rows(t)
    idx = next(i for i, (n, _) in enumerate(r) if n == inst)
    return {
        'source latency': num(r'\+ Source Insertion Delay\s+(-?\d+\.\d+)', t.split('Instance', 1)[0], 0.0),
        'clock arrival': r[idx - 1][1],
        'data arrival': num(r'^\s*Arrival Time\s+(-?\d+\.\d+)', t),
        'output delay': num(r'- External Delay\s+(-?\d+\.\d+)', t),
        'required': num(r'= Required Time\s+(-?\d+\.\d+)', t),
        'slack': num(r'Slack Time\s+(-?\d+\.\d+)', t),
    }


def main():
    d = Path(sys.argv[1] if len(sys.argv) > 1 else
             Path.home() / 'c2_results/p16/v3_m0_d256_p0.8_nomerge_pnr1.0_nodvtsh2_diag/rpt/diag')
    out = ['| corner | worst in2reg hold path: input delay | data arrival | capture clock source latency | '
           'clock arrival at register | tree insertion delay (arrival - source latency) | hold | required | slack |',
           '|---|---|---|---|---|---|---|---|---|']
    out2 = ['| corner | worst reg2out hold path: launch clock source latency | clock arrival at launching register | '
            'data arrival at output | output delay | required | slack |', '|---|---|---|---|---|---|---|']
    cnt = ['| corner | violating hold paths in2reg | violating hold paths reg2out |', '|---|---|---|']
    for tag in ('tt', 'ss'):
        a = in2reg((d / f'{tag}_in2reg.rpt').read_text(errors='replace'))
        if a['last row'] is not None and abs(a['last row'] - a['clock arrival']) > 0.0015:
            raise SystemExit(f'{tag}: capture table end {a["last row"]} != Other End Arrival {a["clock arrival"]}')
        out.append(f'| {tag} | {a["input delay"]:.3f} | {a["data arrival"]:.3f} | {a["source latency"]:.3f} | '
                   f'{a["clock arrival"]:.3f} | {a["clock arrival"] - a["source latency"]:.3f} | {a["hold"]:.3f} | '
                   f'{a["required"]:.3f} | {a["slack"]:.3f} |')
        b = reg2out((d / f'{tag}_reg2out.rpt').read_text(errors='replace'))
        out2.append(f'| {tag} | {b["source latency"]:.3f} | {b["clock arrival"]:.3f} | {b["data arrival"]:.3f} | '
                    f'{b["output delay"]:.3f} | {b["required"]:.3f} | {b["slack"]:.3f} |')
        c = dict(re.findall(r'^(\w+) violating_hold_paths (\d+)', (d / f'{tag}_counts.txt').read_text(), re.M))
        cnt.append(f'| {tag} | {c.get("in2reg", "n/a")} | {c.get("reg2out", "n/a")} |')
    print('\n'.join(out + [''] + out2 + [''] + cnt))


if __name__ == '__main__':
    main()
