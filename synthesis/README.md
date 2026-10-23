# Synthesis evidence

Flow (synth.tcl): `read_verilog; synth -top lfu_cache_controller; abc -g cmos2; clean; stat`.
`abc -g cmos2` maps to generic NAND/NOR/NOT gates. **No technology library is used, so this flow reports gate
counts only: no area in um2, no power, no timing.**

| Run | Flip-flops | Combinational gates | Total cells |
|-----|-----------:|--------------------:|------------:|
| `LFU.v` as simulated (ADDR 32, DATA 512), your log, Yosys 0.62 | 9,449 | 24,704 | 34,153 |
| same, my rerun, Yosys 0.33 (gate mix differs by version) | 9,449 | 23,268 | 32,717 |
| paper configuration (ADDR 20, DATA 128), my rerun, Yosys 0.33 | 2,705 | 8,626 | 11,331 |

Longest topological path (`ltp`): 243 gate levels (32/512) and 245 gate levels (20/128).

The paper's 2,730 flip-flops is consistent with the 20/128 run. The paper's 4,048 total cells is not (11,331 here),
and no file in this project contains the 6,791 um2, 2.45 mW, 1,070 ps or 935 MHz figures as tool output.
Getting real numbers needs a liberty file (for example NanGate45, ASAP7 or SKY130) plus OpenSTA.
