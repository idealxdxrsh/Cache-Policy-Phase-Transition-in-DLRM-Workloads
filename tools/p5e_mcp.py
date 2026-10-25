"""Write OpenSTA multicycle exceptions for register pairs that P5e shows cannot form single-cycle paths.

Usage: python -I tools/p5e_mcp.py <netlist.v> <out.tcl>
NanGate45, not TSMC. Pre-layout. Reasoning (rtl/v2/lfu_cache_controller.v, tag rtl-v2-final):
- stageA_min -> data_store, tag_store: stageA_min loads only on the LOOKUP-miss edge (lines 191-193), after
  which the state is EVICT (line 247); data_store and tag_store load only in FILL (lines 292, 294, 295), which
  starts one edge later (line 248). So they capture a new stageA_min value 2 cycles after launch at the
  earliest: setup 2.
- freq_cnt -> stageA_min, valid_bits, victim_reg: freq_cnt loads only on edges after which the state is IDLE
  (line 281 in LOOKUP hit, line 247; lines 298-300 in FILL with fill_valid, line 249). stageA_min loads only at
  the end of LOOKUP (line 191), at least 2 cycles later (IDLE, LOOKUP; line 246): setup 2. valid_bits loads only
  in EVICT (line 286) and FILL (line 296), victim_reg only in EVICT (line 285), at least 3 cycles later (IDLE,
  LOOKUP, EVICT; lines 246-247): setup 3.
P5e first ran with only stageA_min -> data_store and freq_cnt -> valid_bits; the other pairs were added after
that run showed worst paths of these kinds (results/P5e/SUMMARY.md).
Hold multipliers are setup - 1, so the hold check stays at the launch edge.
Registers are found by the Q net name of each flip-flop instance in the netlist.
"""
import re
import sys
from pathlib import Path

INST = re.compile(r'^\s+(S?DFF\w*)\s+(\S+)\s+\((.*?)\);', re.S | re.M)
PAIRS = [('stageA_min', 'data_store', 2), ('stageA_min', 'tag_store', 2), ('freq_cnt', 'stageA_min', 2),
         ('freq_cnt', 'valid_bits', 3), ('freq_cnt', 'victim_reg', 3)]


def main():
    text = Path(sys.argv[1]).read_text()
    regs = {}
    for _, inst, body in INST.findall(text):
        q = re.search(r'\.Q\(\\?([A-Za-z_]\w*)', body)
        if q:
            regs.setdefault(q.group(1), []).append(inst)
    out = []
    for frm, to, n in PAIRS:
        a, b = regs.get(frm, []), regs.get(to, [])
        out.append(f'# {frm} ({len(a)} flip-flops) -> {to} ({len(b)} flip-flops): setup {n}')
        if a and b:
            out.append(f'set mcp_from [get_cells {{{" ".join(a)}}}]')
            out.append(f'set mcp_to [get_cells {{{" ".join(b)}}}]')
            out.append(f'set_multicycle_path -setup {n} -from $mcp_from -to $mcp_to')
            out.append(f'set_multicycle_path -hold {n - 1} -from $mcp_from -to $mcp_to')
    Path(sys.argv[2]).write_text('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
