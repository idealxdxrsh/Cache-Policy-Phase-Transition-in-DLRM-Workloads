"""P8: does OpenSTA's state-probability model (pin duties multiplied as if independent) bias each power component?

Usage: python -I tools/p8_bias_check.py <netlist.v> <power_debug.txt.gz> <inst.txt.gz> <act.vcd.gz> <vvp.txt> <out.json>
<power_debug.txt.gz>: OpenSTA report_power with `sta::set_debug power 2` on the run's VCD window
(synthesis/p8/run_p8.sh debug); <inst.txt.gz>: report_power -instances of the same run (6-digit per-instance values).
OpenSTA's per-arc energies (the debug `energy` column: rise/fall average in J, 3 significant digits) are kept; only the
probability weights are replaced by counts from the VCD window [t_begin_ps, t_end_ps - 1]:
  input internal  (per pin and `when`): OpenSTA energy x duty(when, independent pins) x density;
                  recomputed: energy x (transitions of the pin at which `when` holds) / T.
  output internal (per output, arcs from input pins): OpenSTA density(out) x sum(energy x weight), weight from
                  independent-pin sensitization duties; recomputed: each output transition is assigned to the arc(s)
                  whose input pin changed in the same time step (shared equally if several; arcs with a `when` only if
                  it holds); output transitions with no input change in the same step keep OpenSTA's weights (counted).
  switching:      0.5 C V^2 x density, no duty term; checked by comparing OpenSTA's density (debug, 3 significant
                  digits) with the VCD transition count / T for every output pin.
  leakage:        OpenSTA: sum(leakage(when) x duty(when, independent pins)) + cell leakage x (1 - sum of duties);
                  recomputed: sum(leakage(when) x fraction of the window the cell's pins were in a state where `when`
                  holds); states no `when` covers keep OpenSTA's per-instance leakage (counted).
`when` conditions and simultaneous changes are evaluated on the pin values after all changes of the time step (zero-delay
simulation: a flip-flop's D, Q and CK change in the same step). Flip-flop CK-pin lines are reported separately; the
time-weighted CK recalculation is in tools/p8_breakdown.py.
"""
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

OUT_PINS = {'Z', 'ZN', 'Q', 'QN', 'CO', 'S'}


def norm(net):
    return net.replace(' ', '').strip()


def when_fn(expr):
    if expr is None:
        return None
    py = re.sub(r'([A-Za-z_]\w*)', r"v.get('\1')", expr)
    py = py.replace('!', ' not ').replace('*', ' and ').replace('+', ' or ').replace('^', ' != ')
    return eval('lambda v: bool(' + py + ')')   # noqa: S307 (expression from the OpenSTA debug log of a liberty file)


def parse_debug(path):
    inst = {}
    cur = mode = None
    with gzip.open(path, 'rt') as fh:
        for line in fh:
            if not line.startswith('power:'):
                continue
            tk = line.split()[1:]
            if not tk:
                continue
            if tk[0] == 'find' and tk[1] == 'power':
                cur = inst.setdefault(tk[2], {'in': [], 'out': [], 'sw': [], 'leak': [], 'leak_final': None,
                                              'leak_true': None, 'cell': None})
                mode = None
            elif cur is None:
                continue
            elif tk[0] == 'internal' and tk[1] in ('input', 'output'):
                mode = (tk[1], tk[2].rsplit('/', 1)[1])
            elif tk[0] in ('when',):
                continue
            elif tk[0] == 'switching':
                cur['cell'], pin = tk[1].rsplit('/', 1)
                cur['sw'].append((pin, float(tk[4]), float(tk[8])))
            elif tk[0] == 'leakage':
                if '/' in tk[1]:
                    cur['cell'] = tk[1].split('/')[0]
                    if len(tk) == 3:
                        cur['leak_final'] = float(tk[2])
                    else:
                        cur['leak_true'] = (tk[2].rsplit('=', 1)[0], float(tk[3]))
                elif tk[3] == '--':
                    cur['leak'].append((None, float(tk[4])))
                else:
                    cur['leak'].append((tk[3], float(tk[4])))
            elif mode:
                if tk[-2:] == ['no', 'pg_pin']:
                    tk = tk[:-2]
                else:
                    tk = tk[:-1]
                if mode[0] == 'input':
                    pin, rest = tk[0], tk[1:]
                    when = rest[0] if len(rest) == 5 else None
                    cur['in'].append({'pin': pin, 'when': when, 'energy': float(rest[-2]), 'power': float(rest[-1])})
                else:
                    frm, to, rest = tk[0], tk[2], tk[3:]
                    when = rest[0] if len(rest) == 6 else None
                    cur['out'].append({'from': frm, 'pin': to, 'when': when, 'density': float(rest[-5]) * 1e9,
                                       'weight': float(rest[-3]), 'energy': float(rest[-2]),
                                       'power': float(rest[-1])})
    return inst


def main():
    netlist, dbg, inst_rep, vcd, vvp, out = sys.argv[1:7]
    t = Path(netlist).read_text()
    cells = {}
    for typ, name, body in re.findall(r'^\s*([A-Z][A-Z0-9_]+)\s+(\S+)\s*\((.*?)\);', t, re.S | re.M):
        cells[name] = (typ, {p: norm(n) for p, n in re.findall(r'\.(\w+)\(([^()]*)\)', body)})
    D = parse_debug(dbg)
    osta = {}
    with gzip.open(inst_rep, 'rt') as fh:
        for line in fh:
            m = re.match(r'\s*(-?[\d.e+-]+)\s+(-?[\d.e+-]+)\s+(-?[\d.e+-]+)\s+(-?[\d.e+-]+)\s+(\S+)\s*$', line)
            if m:
                osta[m.group(5)] = [float(x) for x in m.groups()[:4]]
    kv = {k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)', next(l for l in Path(vvp).read_text().splitlines()
                                                                  if l.startswith('p8_power')))}
    t0, t1 = kv['t_begin_ps'], kv['t_end_ps'] - 1
    T = (t1 + 1 - t0) * 1e-12
    # compile when conditions
    for name, d in D.items():
        for x in d['in'] + d['out']:
            x['fn'] = when_fn(x['when'])
            x['count'] = 0.0
        d['leakfn'] = [(when_fn(w), v) for w, v in d['leak']]
    # VCD
    names, ids = {}, {}
    vals = {}           # inst -> {pin: '0'/'1'/None}
    const = {"1'h0": '0', "1'h1": '1', "1'b0": '0', "1'b1": '1'}
    with gzip.open(vcd, 'rt') as fh:
        scope = []
        for line in fh:
            if line.startswith('$scope'):
                scope.append(line.split()[2])
            elif line.startswith('$upscope'):
                scope.pop()
            elif line.startswith('$var'):
                tk = line.split()
                if scope[-2:] != ['tb_power', 'gl']:
                    continue
                w, code, name = int(tk[2]), tk[3], tk[4]
                rng = re.match(r'\[(\d+):(\d+)\]', tk[5]) if tk[5] != '$end' else None
                ids[code] = w
                if rng is None:
                    names[(name, None)] = (code, 0)
                else:
                    lsb = min(int(rng.group(1)), int(rng.group(2)))
                    for i in range(w):
                        names[(name, lsb + i)] = (code, i)
            elif line.startswith('$enddefinitions'):
                break
        watch = defaultdict(list)
        unmapped = 0
        for c, (typ, pins) in cells.items():
            vals[c] = {}
            for p, n in pins.items():
                if n in const:
                    vals[c][p] = const[n]
                    continue
                m = re.match(r'(.*?)\[(\d+)\]$', n)
                key = (n, None) if (n, None) in names else ((m.group(1), int(m.group(2))) if m else (n, None))
                if key in names:
                    watch[names[key]].append((c, p))
                elif n:
                    unmapped += 1
        occ = defaultdict(lambda: defaultdict(float))
        last = {}
        out_unattrib = 0
        out_toggles = defaultdict(int)
        cur_t = None
        pending = []    # (code, new bits) of the current time step

        def flush(tnow):
            nonlocal out_unattrib
            changed = defaultdict(list)    # inst -> [(pin, old, new)]
            for code, bits in pending:
                w = ids[code]
                old = vcdval.get(code)
                vcdval[code] = bits
                for i in range(w):
                    n = bits[w - 1 - i]
                    o = old[w - 1 - i] if old is not None else None
                    if o == n:
                        continue
                    for c, p in watch.get((code, i), ()):
                        changed[c].append((p, o, n))
            for c, ch in changed.items():
                v = vals[c]
                if c in last and tnow > t0:
                    a = max(last[c], t0)
                    if tnow > a:
                        occ[c][tuple(sorted(v.items()))] += tnow - a
                last[c] = tnow
                for p, o, n in ch:
                    v[p] = n if n in '01' else None
                if tnow < t0 or c not in D:
                    continue
                d = D[c]
                tr = {p for p, o, n in ch if o in ('0', '1') and n in ('0', '1')}
                if not tr:
                    continue
                vb = {k: (x == '1') for k, x in v.items() if x is not None}
                for x in d['in']:
                    if x['pin'] in tr and (x['fn'] is None or x['fn'](vb)):
                        x['count'] += 1
                for op in {x['pin'] for x in d['out']} & tr:
                    out_toggles[c, op] += 1
                    arcs = [x for x in d['out'] if x['pin'] == op and x['from'] in tr
                            and (x['fn'] is None or x['fn'](vb))]
                    if not arcs:
                        out_unattrib += 1
                        for x in d['out']:
                            if x['pin'] == op:
                                x['count'] += x['weight']
                    else:
                        for x in arcs:
                            x['count'] += 1.0 / len(arcs)
            pending.clear()
        vcdval = {}
        for line in fh:
            ch = line[0]
            if ch == '#':
                tt = int(line[1:])
                if cur_t is not None:
                    flush(cur_t)
                cur_t = tt
                if tt > t1:
                    break
                continue
            if ch == 'b':
                bits, code = line[1:].split()
            elif ch in '01xz':
                bits, code = ch, line[1:].strip()
            else:
                continue
            if code in ids:
                w = ids[code]
                pending.append((code, bits.rjust(w, '0' if bits[0] in '01' else bits[0])))
        if cur_t is not None and cur_t <= t1:
            flush(cur_t)
        for c in cells:
            if c in last:
                a = max(last[c], t0)
                if t1 + 1 > a:
                    occ[c][tuple(sorted(vals[c].items()))] += t1 + 1 - a
    # aggregate
    R = defaultdict(float)
    sw_dev = []
    leak_uncovered = 0
    for c, d in D.items():
        typ = cells[c][0] if c in cells else d['cell']
        kind = 'ff' if typ.startswith('DFF') else 'comb'
        for x in d['in']:
            part = f'{kind}_ck' if (kind == 'ff' and x['pin'] == 'CK') else f'{kind}_in'
            R[f'{part}_osta_debug'] += x['power']
            R[f'{part}_recomputed'] += x['energy'] * x['count'] / T
        for x in d['out']:
            R[f'{kind}_out_osta_debug'] += x['power']
            R[f'{kind}_out_recomputed'] += x['energy'] * x['count'] / T
        for pin, dens, p in d['sw']:
            R[f'{kind}_sw_osta_debug'] += p
            n = out_toggles.get((c, pin), 0)
            if dens > 0:
                sw_dev.append(abs(n / T - dens) / dens)
            elif n:
                sw_dev.append(float('inf'))
        if c in osta:
            R[f'{kind}_internal_osta'] += osta[c][0]
            R[f'{kind}_switching_osta'] += osta[c][1]
            R[f'{kind}_leakage_osta'] += osta[c][2]
        # leakage recomputation
        tot = sum(occ[c].values())
        if d['leak_true'] is not None or not d['leakfn'] or tot == 0:
            R[f'{kind}_leakage_recomputed'] += osta.get(c, [0, 0, 0])[2]
            continue
        lk = 0.0
        for st, dt in occ[c].items():
            vb = {k: (x == '1') for k, x in st if x is not None}
            vals_true = [v for fn, v in d['leakfn'] if fn is not None and fn(vb)]
            if vals_true:
                lk += vals_true[0] * dt / tot
            else:
                leak_uncovered += 1
                lk += osta.get(c, [0, 0, 0])[2] * dt / tot
        R[f'{kind}_leakage_recomputed'] += lk
    res = {'netlist': netlist, 'window_ps': [t0, t1], 'instances_in_debug': len(D), 'cells': len(cells),
           'vcd_unmapped_pins': unmapped, 'output_toggles_without_input_change_same_step': out_unattrib,
           'leakage_states_not_covered_by_a_when': leak_uncovered,
           'switching_density_vs_vcd_max_rel_dev': max(sw_dev) if sw_dev else None,
           'switching_density_vs_vcd_pins': len(sw_dev),
           'switching_density_vs_vcd_pins_over_1pct': sum(1 for x in sw_dev if x > 0.01),
           'power_W': dict(sorted(R.items()))}
    Path(out).write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
