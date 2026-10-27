# P10: Rotate-victim tie-break in rtl/v3 (COUNTER_MODE 0 only); Icarus simulation only, not synthesized
RTL: `rtl/v3/lfu_cache_controller.v` = `rtl/v2` (tag rtl-v2-final, untouched) + rule R1 of `results/P9/HW_COST.md`. Driver: `bash rtl/v3/run_p10.sh all` (log `run_all.txt`, exit 0). No timing, area or power for v3.
## (1) Rule: identical to `trace_sim/rtl_exact.py` RotatingTieCache, advance 'victim' (no barrel shifter, no new stage)
- Key {eff, wrap}, wrap = (slot < ptr), KW = EW+1 = 8 bits, in Stage A leaves (constant slot vs `ptr`) and Stage B leaves (`stageA_min[g] < ptr`, no registered wrap bits; the optional 16 flip-flops are not used). Strict `<` keeps the lowest index on key ties, so the victim is the first min-eff slot at or after `ptr`, wrapping: the simulator's smallest (A - P) mod N.
- `ptr` (IDX_WIDTH bits, reset 0) loads `victim_reg + 1` in FILL with fill_valid; the IDX_WIDTH-bit add wraps N-1 to 0, as `P = a + 1` mod N. `ptr` is constant from LOOKUP to EVICT, so both stages see the same pointer.
- Unchanged: Stage A / Stage B depth, the 6-bit counter, the FSM, `eff()`. Mode 1: wrap is constant 0 (v2 rule). Mode 2: still a fatal elaboration error.
- No difference found between the RTL rule and the simulator definition (sections 2 and 3).
## (2) Testbench `rtl/v3/tb_lfu_cache.sv`: TESTS 1-7 copied unchanged from rtl/v2, plus TEST 8 (tie order, mode 0)
- ALL TESTS PASSED at depths 16 / 64 / 256, modes 0 and 1 (6 runs; `tb/sim_d<D>_mode<M>.txt`).
- TEST 8: all lines filled (ptr = victim + 1 checked after every fill), every line except slots 2, 3, 5, N-1 hit once. Six new tags give victims 2, 3, 5, N-1, 2, 3 with ptr 3, 4, 6, 0, 3, 4. This covers ptr below a candidate, ptr equal to a candidate, ptr past every group-0 candidate (Stage B picks the last group), and the N-1 to 0 wrap. Count-2 lines are untouched. The v2 rule would pick slot 2 every time. In mode 1, TEST 8 only checks that ptr stays 0.
- The same TEST 8 sequence through the simulator gives victims [2, 3, 5, N-1, 2, 3] at N = 16, 64, 256 (`lockstep.json`, `tb8_model_equals_tb`: true).
- Mutants (`mutants.txt`, depth 256, mode 0): v2 rule (ROTATE = 0), `ptr <= victim_reg`, Stage B wrap = 0: all 3 caught (10 / 12 / 7 failed TEST 8 checks).
## (3) Lockstep, RTL (Icarus 12, zero-delay, `synthesis/p9/tb_hitlog.sv` unchanged) vs simulator, cold start, all 200,000 requests of each P8 slice of the P3b stream (`results/P8/stimulus/stream.json`: matches_p3b true)
- `lockstep.json`; per-run logs `rtl/<run>.txt` (hit-log sha256; the logs themselves are not committed). Each run is compared request by request. Mismatches = 0 in all 12 runs, and the addresses equal the slice in all 12.

| depth | slice | v3 m0 RTL hits / misses | Rotate-victim m0 sim hits / misses | mismatches | v2-rule m0 hits (RTL-exact sim) |
|---|---|---:|---:|---:|---:|
| 16 | row0 | 17,035 / 182,965 | 17,035 / 182,965 | 0 | 19,946 |
| 16 | row1M | 5,217 / 194,783 | 5,217 / 194,783 | 0 | 18,254 |
| 64 | row0 | 80,697 / 119,303 | 80,697 / 119,303 | 0 | 54,737 |
| 64 | row1M | 77,528 / 122,472 | 77,528 / 122,472 | 0 | 53,788 |
| 256 | row0 | 103,382 / 96,618 | 103,382 / 96,618 | 0 | 81,221 |
| 256 | row1M | 101,867 / 98,133 | 101,867 / 98,133 | 0 | 83,219 |

- Mode 1 (unchanged logic): at all 6 points, the v3 hit log equals P9's rtl-v2-final log (`results/P9/rtl/<run>.hits.gz`) line for line, and the RTL-exact m1 simulator shows 0 mismatches (e.g. d256 row0: 91,192 hits).
- On these cold-start slices, Rotate-victim gives more mode-0 hits than the v2 rule at 64 and 256, and fewer at 16 (row1M: 5,217 vs 18,254).
Limits: simulation only; slices are cold-start, not steady state; no synthesis, STA or gate-level simulation of v3.
