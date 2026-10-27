"""P8: dynamic power of one gate-level run broken down by register class.

Usage: python -I tools/p8_breakdown.py <netlist.v> <inst.txt.gz> <act.vcd.gz> <vvp.txt> <out.json>
<inst.txt.gz>: OpenSTA report_power -instances for every cell (synthesis/p8/run_p8.sh inst), same VCD window as the
run's power report. Flip-flops are classed by the register their Q output drives (netlist net names):
  counter = freq_cnt, tag = tag_store, data = data_store, valid = valid_bits,
  control = everything else (state, req_addr_reg, req_addr_grp, stageA_min, victim_reg and the output registers
  resp_valid, resp_data, hit_flag, fill_req, fill_addr); each register's own figures are also kept.
A combinational cell is given a class if every flip-flop D input it reaches (backwards cone from the D pins, stopping
at flip-flop outputs and ports) belongs to that class; otherwise it is 'shared' (or 'none' if it reaches no D pin).
Toggles: 0<->1 transitions of each flip-flop's D and Q nets in the VCD between t_begin_ps and t_end_ps - 1 (the same
window as the power report), summed per class.
Clock-pin model (optional 6th argument: the liberty file): the flip-flops' CK-pin internal energy per clock cycle is
rise + fall of the CK internal_power tables (liberty units fJ) for the cell's state (when: D, Q, QN, RN), at clock slew 0
(ideal clock; linear extrapolation through the first two table points, as OpenSTA's Table1 lookup does), times 500 MHz:
  ck_opensta_model: state probability = product of the pins' own duties, Q and QN treated as independent (what OpenSTA's
                    evalBddDuty does with when conditions; power/Power.cc); duties from the VCD window.
  check_untoggled_*: for flip-flops whose D and Q never toggle in the window, OpenSTA's per-instance internal power vs
                    ck_opensta_model (maximum relative difference).
  ck_exact_state:   state probability = fraction of the window each flip-flop actually spent in that (D, Q) state
                    (QN = !Q, RN = 1).
"""
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

OUT_PINS = {'Z', 'ZN', 'Q', 'QN', 'CO', 'S'}
CLASS_OF = {'freq_cnt': 'counter', 'tag_store': 'tag', 'data_store': 'data', 'valid_bits': 'valid'}


def norm(net):
    return net.replace(' ', '').strip()


def base(net):
    return re.sub(r'\[\d+\]$', '', net).lstrip('\\')


def register(net):
    return re.match(r'[^\[]+', net.lstrip('\\')).group(0)


def ck_tables(lib):
    """CK-pin internal energy per clock cycle (rise + fall, fJ) per when-state, at slew 0, for DFFR_X1 and DFF_X1."""
    t = Path(lib).read_text()
    out = {}
    for cell in ('DFFR_X1', 'DFF_X1'):
        i = t.index(f'cell ({cell})')
        body = t[i:t.index('cell (', i + 10)]
        ckb = body[body.index('pin (CK)'):]
        ckb = ckb[:ckb.index('pin (', 10)]
        rows = []
        for blk in re.split(r'internal_power\s*\(\)', ckb)[1:]:
            w = re.search(r'when\s*:\s*"([^"]*)"', blk)
            if not w:
                continue
            e = 0.0
            for kind in ('rise_power', 'fall_power'):
                m = re.search(kind + r'\((\w+)\)\s*\{(.*?)\}', blk, re.S)
                v = [float(x) for x in re.search(r'values\s*\("([^"]*)"', m.group(2)).group(1).split(',')]
                ix = re.search(r'index_1\s*\("([^"]*)"', m.group(2))
                if not ix:
                    e += v[0]
                else:   # slew 0 is below index_1[0]: linear extrapolation through the first two points
                    x = [float(a) for a in ix.group(1).split(',')]
                    e += v[0] - (v[1] - v[0]) * x[0] / (x[1] - x[0])
            lits = [(x.strip().lstrip('!'), not x.strip().startswith('!')) for x in w.group(1).split('&')]
            rows.append((lits, e))
        out[cell] = rows
    return out


def parse_netlist(path):
    t = Path(path).read_text()
    cells = {}
    for typ, name, body in re.findall(r'^\s*([A-Z][A-Z0-9_]+)\s+(\S+)\s*\((.*?)\);', t, re.S | re.M):
        pins = {p: norm(n) for p, n in re.findall(r'\.(\w+)\(([^()]*)\)', body)}
        cells[name] = (typ, pins)
    alias = {}
    for lhs, rhs in re.findall(r'^\s*assign\s+(.+?)\s*=\s*(.+?);', t, re.M):
        lhs, rhs = norm(lhs), norm(rhs)
        if not re.match(r"\d+'", rhs) and ':' not in lhs and ':' not in rhs:
            alias[lhs] = rhs
    return cells, alias


def main():
    netlist, inst, vcd, vvp, out = sys.argv[1:6]
    ck = ck_tables(sys.argv[6]) if len(sys.argv) > 6 else None
    cells, alias = parse_netlist(netlist)
    driver = {}
    for name, (typ, pins) in cells.items():
        for p, n in pins.items():
            if p in OUT_PINS and n:
                driver[n] = name
    ff = {n: c for n, c in cells.items() if c[0].startswith('DFF')}
    ff_reg = {n: register(c[1]['Q']) for n, c in ff.items()}
    ff_cls = {n: CLASS_OF.get(r, 'control') for n, r in ff_reg.items()}
    # backward cones from the D pins
    reach = defaultdict(set)
    for f, (typ, pins) in ff.items():
        cls, stack, seen = ff_cls[f], [pins['D']], set()
        while stack:
            net = stack.pop()
            while net in alias and net not in driver:
                net = alias[net]
            d = driver.get(net)
            if d is None or d in ff or d in seen:
                continue
            seen.add(d)
            reach[d].add(cls)
            stack.extend(n for p, n in cells[d][1].items() if p not in OUT_PINS)
    comb_cls = {c: (next(iter(reach[c])) if len(reach[c]) == 1 else 'shared') if reach[c] else 'none'
                for c in cells if c not in ff}
    # per-instance power
    pw = {}
    with gzip.open(inst, 'rt') as fh:
        for line in fh:
            m = re.match(r'\s*(-?[\d.e+-]+)\s+(-?[\d.e+-]+)\s+(-?[\d.e+-]+)\s+(-?[\d.e+-]+)\s+(\S+)\s*$', line)
            if m:
                pw[m.group(5)] = [float(x) for x in m.groups()[:4]]
    missing = [c for c in cells if c not in pw]
    agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0])
    for c, v in pw.items():
        if c in ff:
            keys = ('ff:' + ff_cls[c], 'ffreg:' + ff_reg[c], 'ff:all')
        else:
            keys = ('comb:' + comb_cls.get(c, 'none'), 'comb:all')
        for k in keys:
            a = agg[k]
            for i in range(4):
                a[i] += v[i]
            a[4] += 1
    # VCD toggles of D and Q nets in the window
    kv = {k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)', next(l for l in Path(vvp).read_text().splitlines()
                                                                  if l.startswith('p8_power')))}
    t0, t1 = kv['t_begin_ps'], kv['t_end_ps'] - 1
    ids = {}    # vcd id -> (var name, lsb, width)
    names = {}  # (var name, bit or None) -> (code, offset from the right of the value string)
    tog = defaultdict(int)
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
                lsb = min(int(rng.group(1)), int(rng.group(2))) if rng else None
                ids[code] = (name, lsb, w)
                if rng is None:
                    names[(name, None)] = (code, 0)
                else:
                    for i in range(w):
                        names[(name, lsb + i)] = (code, i)
            elif line.startswith('$enddefinitions'):
                break
        # flip-flop D/Q nets -> vcd (code, bit offset)
        watch = defaultdict(list)   # (code, offset) -> [(flop, 'D'|'Q')]
        unmapped = 0
        for f, (typ, pins) in ff.items():
            for p in ('D', 'Q'):
                n = pins[p]
                m = re.match(r'(.*?)\[(\d+)\]$', n)
                key = (n, None) if (n, None) in names else ((m.group(1), int(m.group(2))) if m else (n, None))
                if key in names:
                    watch[names[key]].append((f, p))
                else:
                    unmapped += 1
        watched_codes = {c for c, _ in watch}
        toggled = set()
        cur = {}                    # flop -> [d, q] current values ('0', '1' or other)
        last = {f: t0 for f in ff}  # time of the last state change seen for the flop
        occ = {f: defaultdict(int) for f in ff}   # (d, q) -> ps in the window

        def advance(f, now):
            a = max(last[f], t0)
            if now > a:
                occ[f][tuple(cur.get(f, ['x', 'x']))] += now - a
            last[f] = now
        val, t = {}, 0
        for line in fh:
            c = line[0]
            if c == '#':
                t = int(line[1:])
                if t > t1:
                    break
                continue
            if c == 'b':
                bits, code = line[1:].split()
            elif c in '01xz':
                bits, code = c, line[1:].strip()
            else:
                continue
            if code not in watched_codes:
                continue
            w = ids[code][2]
            bits = bits.rjust(w, '0' if bits[0] in '01' else bits[0])
            old = val.get(code)
            val[code] = bits
            for i in range(w):
                n = bits[w - 1 - i]
                o = old[w - 1 - i] if old is not None else None
                if o == n:
                    continue
                for f, p in watch.get((code, i), ()):
                    advance(f, t)
                    cur.setdefault(f, ['x', 'x'])[0 if p == 'D' else 1] = n
                    if t >= t0 and o in ('0', '1') and n in ('0', '1'):
                        toggled.add(f)
                        tog[f'{p}:{ff_cls[f]}'] += 1
                        tog[f'{p}reg:{ff_reg[f]}'] += 1
        for f in ff:
            advance(f, t1 + 1)
    T = t1 + 1 - t0
    ckres = {}
    slots = defaultdict(set)    # register -> slot indices with at least one Q bit changed in the window
    if ck:
        fclk = 1e12 / 2000.0    # 500 MHz, period 2000 ps
        for f, (typ, pins) in ff.items():
            o = occ[f]
            known = sum(v for (d, q), v in o.items() if d in '01' and q in '01')
            dD = sum(v for (d, q), v in o.items() if d == '1') / T
            dQ = sum(v for (d, q), v in o.items() if q == '1') / T
            duty = {'D': dD, 'Q': dQ, 'QN': 1 - dQ, 'RN': 1.0}
            e_ind = e_ex = 0.0
            for lits, energy in ck[typ]:
                pr = 1.0
                for pin, pos in lits:
                    pr *= duty[pin] if pos else 1 - duty[pin]
                e_ind += pr * energy
                st = dict(lits)
                if st.get('RN', True) and st.get('QN', not st['Q']) == (not st['Q']):
                    e_ex += o.get(('1' if st['D'] else '0', '1' if st['Q'] else '0'), 0) / T * energy
            if f not in toggled and f in pw:   # no D/Q pin power: OpenSTA's internal power is the CK-pin part alone
                err = abs(pw[f][0] - e_ind * 1e-15 * fclk) / pw[f][0]
                ckres['check_untoggled_flops'] = ckres.get('check_untoggled_flops', 0) + 1
                ckres['check_untoggled_max_rel_err'] = max(ckres.get('check_untoggled_max_rel_err', 0.0), err)
            for k, v in (('ck_opensta_model', e_ind), ('ck_exact_state', e_ex)):
                for key in (f'{k}:{ff_cls[f]}', f'{k}:all'):
                    ckres[key] = ckres.get(key, 0.0) + v * 1e-15 * fclk
            for key in (f'ck_known_state_fraction_min:{ff_cls[f]}',):
                ckres[key] = min(ckres.get(key, 1.0), known / T)
            changed = 0 < dQ < 1
            if changed and ff_reg[f] in ('data_store', 'tag_store', 'freq_cnt'):
                slots[ff_reg[f]].add(re.match(r'\\?\w+\[(\d+)\]', pins['Q']).group(1))
            for key in (f'flops_q_changed_in_window:{ff_cls[f]}', 'flops_q_changed_in_window:all'):
                ckres[key] = ckres.get(key, 0) + (1 if changed else 0)
            for key in (f'q_mix_factor_sum:{ff_cls[f]}', 'q_mix_factor_sum:all'):
                ckres[key] = ckres.get(key, 0.0) + (dQ * dQ + (1 - dQ) * (1 - dQ))
    cnt = defaultdict(int)
    for f in ff:
        cnt[ff_cls[f]] += 1
    res = {'netlist': netlist, 'window_ps': [t0, t1], 'cells': len(cells), 'flip_flops': len(ff),
           'cells_without_power_line': len(missing),
           'power_W': {k: dict(zip(('internal', 'switching', 'leakage', 'total', 'cells'), v)) for k, v in
                       sorted(agg.items())},
           'toggles_in_window': dict(sorted(tog.items())), 'flip_flops_per_class': dict(sorted(cnt.items())),
           'vcd_unmapped_flop_pins': unmapped, 'clock_pin_model_W': dict(sorted(ckres.items())),
           'slots_with_q_change_in_window': {k: len(v) for k, v in sorted(slots.items())}}
    Path(out).write_text(json.dumps(res, indent=1) + '\n')
    print(f'wrote {out}: {len(cells)} cells, {len(ff)} flip-flops, {len(missing)} without a power line')


if __name__ == '__main__':
    main()
