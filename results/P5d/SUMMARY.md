# P5d: hit_idx priority loop -> balanced priority tree — NanGate45, not TSMC; pre-layout; no power numbers
Before = P5c (commit 73016e0, `results/P5c/tree_copies`). Same Yosys 0.33 + NanGate45 + OpenSTA flow, local; driver `synthesis/p5d/run_p5d.sh`. Files: `COMPARE.md`, `RESULTS.md`, `NOISE.md`, `CRITICAL_PATH.md`. Final RTL tagged `rtl-v2-final`.
## Structure: priority tree, not one-hot AND-OR (lowest matching slot wins, 0 if none, as the loop did; RTL lines 120-147)
- It does not rely on at most one match, but the invariant holds and is checked. Tags are written only at reset (line 267)
  and in FILL (line 294). Valid bits are cleared at reset (line 265) and for the victim in EVICT (line 286), and set only in
  FILL (line 296). FILL follows only a LOOKUP miss (lines 247-249) on an address held since IDLE (lines 232, 240); there is no flush.
  Lockstep checks at most one match every cycle in both designs: 0 multi-match cycles in all runs (`lockstep_vs_*.txt`).
## Behaviour checks (unit testbench unmodified; no cycle-timing or latency change)
- 7 tests pass at depths 16/64/256 x modes 0/1 (`sim/`). Lockstep, 200,000 random cycles per run, vs rtl-v2-baseline,
  P5b (fac3366) and P5c (73016e0): 18/18 runs with 0 port, 0 victim-slot and 0 hit_idx mismatches (lockstep testbench now also compares hit_idx).
- Mutation (`mutation.txt`, all depths/modes, `--lockstep`): RESULT OK; 113 killed by testbench, 10 by lockstep, 33
  equivalent. 5 new hit-tree mutants; `hit_tree_prefer_right` is equivalent (it needs two matches, which never happen).
- Attempt 1 wrote the tree as flat vectors; it took Icarus 5791 s per depth-256 lockstep run (mutation timed out). It was moved to
  `attempt1_packed_vectors/` and rewritten with unpacked arrays (same logic). Yosys equiv proves both equal at depth 16, modes 0 and 1
  (`equiv/`); depth 64 timed out after 1500 s, so it is not proven there.
## Before (P5c) -> after (P5d final) — Fmax = 1/(period - WNS), 1 GHz netlists unless noted
| depth | mode | Fmax MHz | WNS @1 GHz ns | WNS @500 MHz ns | cells | area um^2 (1 GHz) |
|---|---|---|---|---|---|---|
| 16 | 0 | 626.1 -> 571.3 | -0.5973 -> -0.7505 | met -> met | 10,834 -> 11,529 | 26363.792 -> 26733.266 |
| 16 | 1 | 611.6 -> 586.9 | -0.6351 -> -0.7040 | met -> met | 11,242 -> 11,661 | 26634.048 -> 26875.310 |
| 64 | 0 | 486.4 -> 528.4 | -1.0561 -> -0.8925 | -0.3076 -> -0.1794 | 41,192 -> 37,720 | 96531.400 -> 92969.660 |
| 64 | 1 | 439.3 -> 470.9 | -1.2762 -> -1.1236 | -0.3492 -> -0.3400 | 40,434 -> 37,901 | 96895.820 -> 93294.180 |
| 256 | 0 | 213.9 -> 451.2 | -3.6744 -> -1.2161 | -2.6744 -> -0.3432 | 144,237 -> 143,761 | 359696.904 -> 359441.544 |
| 256 | 1 | 199.4 -> 435.3 | -4.0142 -> -1.2972 | -3.0142 -> -0.3366 | 146,419 -> 145,730 | 361999.400 -> 362935.454 |
## Noise floor (`NOISE.md`, 1 GHz): 8 same-logic designs (final, flat-vector form, 3 one-line rewrites of each); the flow alone moves Fmax 1.96-16.62%, far above the ~2% P5c estimated from one depth-16 pair
| depth | mode 0 min-max MHz (spread) | mode 1 min-max MHz (spread) |
|---|---|---|
| 16 | 560.7-623.0 (11.12%) | 563.1-620.5 (10.20%) |
| 64 | 528.4-538.8 (1.96%) | 470.9-549.1 (16.62%) |
| 256 | 397.9-451.8 (13.54%) | 409.0-435.3 (6.42%) |
## Where it did not help or made things worse (plain statement)
- Depth 16 got worse: 626.1 -> 571.3 / 611.6 -> 586.9 MHz. All 8 mode-0 variants are below P5c's 626.1, so the hit tree
  did not help at depth 16. The depth-64 and depth-256 gains are above every noise range (all 8 variants beat P5c).
- 500 MHz is still met only at depth 16. The depth-64 mode-0 1 GHz netlist has Fmax 528.4, but the netlist synthesized for 500 MHz misses.
- Max-cap/slew violators besides rst_n (1 GHz): depth 256 rose 118 -> 120 (mode 0) and 48 -> 108 (mode 1); depth 64 fell 8 -> 2 and 9 -> 3.
- P5c kept the address copies on a +7.44% / +5.84% margin at depth 256. That margin is inside this noise floor, so the
  decision is not supported above noise. The copies were not re-evaluated, because the RTL is now frozen.
## New critical paths (1 GHz; `CRITICAL_PATH.md`)
- Depths 64 and 256: from `stageA_min` through Stage B (EVICT) to `valid_bits`/`data_store` D pins, 38-43 cells, 1.8499-2.2562 ns; hit path no longer worst. Depth 16: `freq_cnt[10]` -> `valid_bits[0]`, 34 cells, 1.7072 ns.
