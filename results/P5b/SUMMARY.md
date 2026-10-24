# P5b: Stage-B reduction tree + per-group address copies — NanGate45, not TSMC; pre-layout; no power numbers
Baseline = tag `rtl-v2-baseline` (1483717, `results/P5`); same Yosys 0.33 + NanGate45 + OpenSTA flow, local. Files: `COMPARE.md` (full before/after, incl. a tree-only column), `RESULTS.md`, `CRITICAL_PATH.md`, `lockstep.txt`, `mutation.txt`.

## Behaviour checks (testbench unchanged, no test loosened)
- All 7 tests pass, modes 0 and 1, depths 16/64/256 (`sim/sim_d<D>_m<M>.txt`).
- No cycle-timing or latency change (copies load with `req_addr_reg`; the tree is in the same EVICT cycle): lockstep vs the
  baseline tag, 200,000 random cycles per depth/mode, 0 port and 0 victim-slot mismatches in all 6 (`lockstep.txt`).
- Mutation (`mutation.txt`, all depths/modes, `--lockstep`): RESULT OK. 69 runs killed by the testbench, 6 by lockstep, 15 equivalent.
  New mutants: 6 tree, 3 address copy. `tree_tie_right` passes the testbench (any fixed slot order looks the same at the
  ports) and is killed only by the lockstep victim check. `tree_leaf_ignores_valid` is equivalent (in EVICT an invalid slot
  always has count 0), so it is documented, and `tree_leaf_wrong_index` replaces it.

## Before -> after (1 GHz netlists unless noted; Fmax = 1/(period - WNS), pre-layout) — NanGate45, not TSMC
| depth | mode | Fmax MHz | WNS @1 GHz ns | WNS @500 MHz ns | cells | area um^2 (1 GHz / 500 MHz netlist) |
|---|---|---|---|---|---|---|
| 16 | 0 | 203.1 -> 629.2 | -3.9226 -> -0.5892 | -2.9226 -> 0.0000 (met) | 9,399 -> 10,381 | 23688.630 -> 25879.140 / 25813.970 |
| 16 | 1 | 215.1 -> 624.4 | -3.6487 -> -0.6015 | -2.6487 -> 0.0000 (met) | 10,467 -> 10,690 | 24643.038 -> 26137.160 / 26071.458 |
| 64 | 0 | 194.7 -> 476.1 | -4.1363 -> -1.1004 | -3.1363 -> -0.2720 | 36,605 -> 40,818 | 90869.324 -> 96163.256 / 96071.486 |
| 64 | 1 | 190.5 -> 472.6 | -4.2487 -> -1.1159 | -3.2487 -> -0.2950 | 37,204 -> 41,303 | 91623.168 -> 97302.268 / 97024.298 |
| 256 | 0 | 167.4 -> 188.4 | -4.9752 -> -4.3074 | -3.9752 -> -3.3074 | 143,139 -> 143,583 | 358573.054 -> 359159.584 |
| 256 | 1 | 165.3 -> 185.2 | -5.0483 -> -4.3997 | -4.0483 -> -3.3997 | 144,521 -> 147,232 | 364404.838 -> 362078.136 |
- Nothing meets 1 GHz; 500 MHz is met only at depth 16. Flip-flops +300 at every depth (16 x 20-bit copies; `req_addr_reg` merged into one).

## Where it did not help or made things worse (plain statement)
- Depth 256: only +21.0 / +19.9 MHz (mode 0 / 1). The tree alone gave 173.3 / 176.2 MHz (`COMPARE.md`, tree-only column).
- Address copies at depth 16 mode 0: WNS -0.5850 (tree only) -> -0.5892 (tree + copies), slightly worse, and +793 cells.
- Area went up in every configuration except depth 256 mode 1 (`COMPARE.md`).
- More max-cap/slew violators besides rst_n, at 1 GHz (`RESULTS.md` vs `results/P5/RESULTS.md`): depth 64 mode 0 went
  0 -> 17, and depth 256 mode 0 went 18 -> 64. Fewer at depth 256 mode 1 (130 -> 83) and depth 16 mode 1 (2 -> 1).

## New critical paths (mode 0, 1 GHz; `CRITICAL_PATH.md`)
- Depth 16: `freq_cnt[1][0]` -> `valid_bits[9]`, 36 cells, arrival 1.5455 ns (was 114 cells, 4.8791 ns): still Stage B, now the tree.
- Depth 64: `req_addr_grp[15][9]` -> `freq_cnt[0][0]`, 48 cells, 2.0594 ns: the hit path from an address copy, 3 buffers 0.1785 ns.
- Depth 256: `freq_cnt[208][0]` -> `stageA_min[13][2]`, 144 cells, 5.2667 ns: the Stage A serial minimum over a 16-slot group
  (RTL lines 137-144). This experiment did not change Stage A. The 52-buffer address chain is gone (10 buffers, 0.5075 ns).
## Flow notes
- First run: Yosys merged the 16 identical copies back into one register despite `(* keep *)` on the reg. Kept as
  `attempt1_copies_merged/` (effectively tree only). Fix: copy keep onto the driving flip-flop cells (`synthesis/p5/synth.ys.in`).
  Baseline RTL, depth 16: cell stats and WNS/TNS identical to P5 (`noop_check_baseline/`). Netlists not committed; RTL header STATUS updated (comment only).
