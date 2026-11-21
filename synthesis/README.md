# Synthesis

## Folders
- `p5` to `p5f`: open-library flow on rtl/v2 (Yosys 0.33, OpenSTA 3.1.0, NanGate45 typical liberty; pre-layout) and the
  gate-level and lockstep testbenches. Results: `results/P5*/SUMMARY.md`.
- `p7`, `p8`, `p9`, `p11`, `p13`: testbenches and scripts of those phases (power activity, hit logs, v3 equivalence,
  the 28nm gate-level testbench). Results: `results/<phase>/SUMMARY.md`.
- The 28nm flow (Genus, Xcelium, Innovus) is in `cadence/`; its aggregate results are in `results/P12` to `results/P16`.

## Generic gate counts of the first design (old evidence)
Flow (`synth.tcl`): `read_verilog; synth -top lfu_cache_controller; abc -g cmos2; clean; stat`.
`abc -g cmos2` maps to generic NAND/NOR/NOT gates. **No technology library is used, so this flow reports gate
counts only: no area, no power, no timing.**

| Run | Flip-flops | Combinational gates | Total cells |
|-----|-----------:|--------------------:|------------:|
| `LFU.v` as simulated (ADDR 32, DATA 512), original log `yosys_output_LFU_v_32bit_512bit.txt`, Yosys 0.62 | 9,449 | 24,704 | 34,153 |
| same, rerun `rerun_32bit_512bit_yosys0.33.txt`, Yosys 0.33 (gate mix differs by version) | 9,449 | 23,268 | 32,717 |
| earlier manuscript's configuration (ADDR 20, DATA 128), rerun `rerun_20bit_128bit_yosys0.33.txt`, Yosys 0.33 | 2,705 | 8,626 | 11,331 |

Longest topological path (`ltp`): 243 gate levels (32/512) and 245 gate levels (20/128).

The withdrawn manuscript's cell and flip-flop counts do not match the 20/128 rerun (`results/P7/CLAIMS.md`, rows
22 and 23), and no file in this project contains its area, power or timing figures as tool output.
