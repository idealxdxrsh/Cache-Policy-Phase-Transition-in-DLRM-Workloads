"""P5f: check the Yosys-generated NanGate45 cell models against the liberty function attributes.

Usage: python -I tools/p5f_cellcheck.py <liberty> <models.v> <workdir> <cell>...   (prints Markdown, exit 1 on any failure)
Combinational cells: every input combination (exhaustive truth table), every output, compared with the liberty
`function` evaluated here in Python. Flip-flops (cells with an `ff` group): 400 steps, one input toggled per step
(seeded random, reset/clock/data), plus fixed steps for async clear/preset with and without a clock edge; the
reference is a Python model built from `next_state`, `clocked_on`, `clear`, `preset`, `clear_preset_var1/2`
(IQ/IQN while both are active; L = 0, H = 1) and the output functions.
Before the first clear (or clock edge) the reference state is unknown and outputs are not compared.
The models are run in Icarus Verilog (4-state); an X or Z output where the reference is 0/1 is a failure.
NanGate45, not TSMC. Functional only, zero delay.
"""
import random
import re
import subprocess
import sys
from pathlib import Path


def cells_of(lib_text):
    """{name: body} for every top-level cell group, by brace matching."""
    out = {}
    for m in re.finditer(r'\bcell\s*\(\s*"?([\w]+)"?\s*\)\s*\{', lib_text):
        i, depth = m.end(), 1
        while depth:
            c = lib_text[i]
            depth += (c == '{') - (c == '}')
            i += 1
        out[m.group(1)] = lib_text[m.end():i - 1]
    return out


def groups(body, kind):
    """[(args, body)] for sub-groups `kind (args) { ... }` (one nesting level is enough here)."""
    res = []
    for m in re.finditer(r'\b' + kind + r'\s*\(([^)]*)\)\s*\{', body):
        i, depth = m.end(), 1
        while depth:
            c = body[i]
            depth += (c == '{') - (c == '}')
            i += 1
        res.append((m.group(1).replace('"', '').strip(), body[m.end():i - 1]))
    return res


def attr(body, name):
    m = re.search(r'\b' + name + r'\s*:\s*"?([^";]*)"?\s*;', body)
    return m.group(1).strip() if m else None


def parse_fn(s):
    """Liberty boolean expression -> Python callable(env). Ops: ! ' & * space | + ^ ( ), constants 0/1."""
    toks = re.findall(r"[A-Za-z_]\w*|[01]|[!'&*|+^()]", s)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take():
        pos[0] += 1
        return toks[pos[0] - 1]

    def p_or():
        a = p_xor()
        while peek() in ('|', '+'):
            take()
            b = p_xor()
            a = (lambda x, y: lambda e: x(e) | y(e))(a, b)
        return a

    def p_xor():
        a = p_and()
        while peek() == '^':
            take()
            b = p_and()
            a = (lambda x, y: lambda e: x(e) ^ y(e))(a, b)
        return a

    def p_and():
        a = p_un()
        while peek() in ('&', '*') or (peek() is not None and peek() not in ('|', '+', '^', ')')):
            if peek() in ('&', '*'):
                take()
            b = p_un()
            a = (lambda x, y: lambda e: x(e) & y(e))(a, b)
        return a

    def p_un():
        if peek() == '!':
            take()
            a = p_un()
            return lambda e: 1 - a(e)
        t = take()
        if t == '(':
            a = p_or()
            assert take() == ')'
        elif t in ('0', '1'):
            a = (lambda v: lambda e: v)(int(t))
        else:
            a = (lambda n: lambda e: e[n])(t)
        while peek() == "'":
            take()
            a = (lambda x: lambda e: 1 - x(e))(a)
        return a

    f = p_or()
    assert pos[0] == len(toks), s
    return f


def pins(body):
    ins, outs = [], {}
    for name, pb in groups(body, 'pin'):
        d = attr(pb, 'direction')
        if d == 'input':
            ins.append(name)
        elif d == 'output':
            outs[name] = attr(pb, 'function')
    return ins, outs


def tb_comb(cell, ins, outs, vecs):
    lines = ['module tb;', f'reg [{len(ins) - 1}:0] v;'] + [f'wire o_{o};' for o in outs]
    conn = [f'.{p}(v[{i}])' for i, p in enumerate(ins)] + [f'.{o}(o_{o})' for o in outs]
    lines += [f'{cell} u({", ".join(conn)});', 'integer k;', 'initial begin']
    for k in range(vecs):
        lines.append(f'  v = {len(ins)}\'d{k}; #1; $display("R {k}' + ''.join(f' %b' for _ in outs) + '"'
                     + ''.join(f', o_{o}' for o in outs) + ');')
    lines += ['  $finish;', 'end', 'endmodule']
    return '\n'.join(lines)


def run_iv(work, name, models, tb):
    work.mkdir(parents=True, exist_ok=True)
    (work / f'{name}.sv').write_text(tb)
    subprocess.run(['iverilog', '-g2012', '-o', str(work / name), str(models), str(work / f'{name}.sv')], check=True)
    out = subprocess.run(['vvp', '-n', str(work / name)], capture_output=True, text=True, check=True).stdout
    return [ln.split()[1:] for ln in out.splitlines() if ln.startswith('R ')]


def check_comb(cell, body, models, work):
    ins, outs = pins(body)
    fns = {o: parse_fn(f) for o, f in outs.items()}
    rows = run_iv(work, cell, models, tb_comb(cell, ins, outs, 2 ** len(ins)))
    bad = 0
    for k, r in enumerate(rows):
        env = {p: (k >> i) & 1 for i, p in enumerate(ins)}
        exp = [str(fns[o](env)) for o in outs]
        bad += exp != r[1:]
    ok = len(rows) == 2 ** len(ins) and bad == 0
    return ok, (f'{len(ins)} inputs, {2 ** len(ins)} rows x {len(outs)} output(s) '
                f'({", ".join(f"{o} = {f}" for o, f in outs.items())}); {bad} mismatching rows')


def check_ff(cell, body, models, work, steps=400, seed=1):
    ins, outs = pins(body)
    (ffargs, fb), = groups(body, 'ff')
    iq, iqn = [a.strip() for a in ffargs.split(',')]
    nxt, clk = parse_fn(attr(fb, 'next_state')), parse_fn(attr(fb, 'clocked_on'))
    clr = parse_fn(attr(fb, 'clear')) if attr(fb, 'clear') else (lambda e: 0)
    pre = parse_fn(attr(fb, 'preset')) if attr(fb, 'preset') else (lambda e: 0)
    lh = {'L': 0, 'H': 1}
    both = (lh.get(attr(fb, 'clear_preset_var1')), lh.get(attr(fb, 'clear_preset_var2')))
    fns = {o: parse_fn(f) for o, f in outs.items()}
    rng = random.Random(seed)
    clkpin = attr(fb, 'clocked_on').strip('!()')
    async_pins = [p for p in ins if p in (attr(fb, 'clear') or '') + (attr(fb, 'preset') or '')]
    # fixed prologue: assert/deassert each async pin (no clock), then a clock edge under clear, then random toggles
    seq, cur = [], {p: 0 for p in ins}
    for p in ins:
        cur[p] = 1 if p in async_pins else 0
    seq.append(dict(cur))
    for p in async_pins:
        for v in (0, 1):
            cur[p] = v
            seq.append(dict(cur))
    if async_pins:
        cur[async_pins[0]] = 0
        seq.append(dict(cur))
        for v in (1, 0):  # clock edge while clear/preset is active
            cur[clkpin] = v
            seq.append(dict(cur))
        cur[async_pins[0]] = 1
        seq.append(dict(cur))
    for _ in range(steps):
        p = rng.choice(ins + [clkpin] * 2)                  # clock toggles more often
        if p in async_pins and rng.random() < 0.7:
            continue
        cur[p] ^= 1
        seq.append(dict(cur))
    lines = ['module tb;'] + [f'reg {p};' for p in ins] + [f'wire o_{o};' for o in outs]
    lines += [f'{cell} u({", ".join([f".{p}({p})" for p in ins] + [f".{o}(o_{o})" for o in outs])});', 'initial begin']
    for k, s in enumerate(seq):
        lines.append('  ' + ' '.join(f'{p} = {s[p]};' for p in ins) + ' #1; $display("R %0d' + ' %b' * len(outs)
                     + f'", {k}' + ''.join(f', o_{o}' for o in outs) + ');')
    lines += ['  $finish;', 'end', 'endmodule']
    rows = run_iv(work, cell, models, '\n'.join(lines))
    state, prev, bad, compared = None, None, 0, 0
    for s, r in zip(seq, rows):
        e = dict(s)
        if clr(e) and pre(e):
            state = 'both'
        elif clr(e):
            state = 0
        elif pre(e):
            state = 1
        elif prev is not None and clk(prev) == 0 and clk(e) == 1:
            state = nxt(e)                                  # only one input changes per step: D is stable at the edge
        elif state == 'both':
            state = None                                    # liberty leaves the state after both release undefined here
        prev = e
        if state is None:
            continue
        e[iq], e[iqn] = both if state == 'both' else (state, 1 - state)
        compared += 1
        bad += [str(fns[o](e)) for o in outs] != r[1:]
    ok = len(rows) == len(seq) and bad == 0 and compared > 0
    return ok, (f'ff({ffargs}) next_state "{attr(fb, "next_state")}", clocked_on "{attr(fb, "clocked_on")}", '
                f'clear "{attr(fb, "clear")}", preset "{attr(fb, "preset")}"; {len(seq)} steps, {compared} compared, '
                f'{bad} mismatching steps')


def main():
    lib, models, work = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    cells = cells_of(Path(lib).read_text())
    out = ['| cell | kind | check | result |', '|---|---|---|---|']
    fail = 0
    for c in sys.argv[4:]:
        body = cells[c]
        if groups(body, 'ff'):
            ok, msg = check_ff(c, body, models, work)
            kind = 'flip-flop'
        else:
            ok, msg = check_comb(c, body, models, work)
            kind = 'combinational'
        fail += not ok
        out.append(f'| {c} | {kind} | {msg.replace("|", chr(92) + "|")} | {"PASS" if ok else "FAIL"} |')
    out.append(f'\n{len(sys.argv) - 4} cells checked, {fail} failed.')
    print('\n'.join(out))
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
