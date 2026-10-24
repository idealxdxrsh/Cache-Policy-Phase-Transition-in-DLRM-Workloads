# P5c: Stage-A reduction tree; tree only vs tree + address copies — NanGate45, not TSMC; pre-layout; no power numbers
Before = P5b (commit 2a9f4ae, `results/P5b`); P5 baseline = tag rtl-v2-baseline. Same Yosys 0.33 + NanGate45 + OpenSTA flow, local; driver `synthesis/p5c/run_p5c.sh`.
Files: `COMPARE.md` (all 4 designs, both clocks), `tree_copies/RESULTS.md`, `tree_only/RESULTS.md`, `CRITICAL_PATH.md`.
## Behaviour checks (testbench unmodified; no cycle-timing or latency change, so no test was edited)
- 7 tests pass at depths 16/64/256 x modes 0/1 for both variants (`sim/`) and for the final rtl/v2 (`sim_final/`).
- Lockstep, 200,000 random cycles per depth/mode: both variants vs rtl-v2-baseline and vs P5b, 24/24 runs with 0 port and 0 victim-slot mismatches (`lockstep_<variant>_vs_<ref>.txt`).
- Mutation (`mutation.txt`, final RTL, all depths/modes, `--lockstep`): RESULT OK; 89 killed by testbench, 10 by lockstep,
  27 equivalent. 6 new Stage A mutants; `a_tree_tie_right` is killed only by the lockstep victim check (depths 64, 256). At depth 16 GSIZE = 1, so the Stage A tree has no nodes and all 6 are equivalent there (tool now takes per-depth equivalence).
## Tree only vs tree + copies. Rule, fixed in `run_p5c.sh` before any P5c synthesis: keep the copies only if at depth 256
Fmax(tree + copies) >= 1.05 x Fmax(tree only) in both modes, in both the 1 GHz and 500 MHz netlists.
| depth | mode | Fmax MHz tree only / tree + copies (1 GHz netlist) | change | 500 MHz netlist | cells | area um^2 (1 GHz) |
|---|---|---|---|---|---|---|
| 16 | 0 | 606.4 / 626.1 | +3.24% | both met | 10,102 / 10,834 | 24265.584 / 26363.792 |
| 16 | 1 | 622.1 / 611.6 | -1.69% | both met | 10,275 / 11,242 | 24446.198 / 26634.048 |
| 64 | 0 | 432.1 / 486.4 | +12.55% | 416.8 / 433.4 (+3.97%) | 36,603 / 41,192 | 91540.176 / 96531.400 |
| 64 | 1 | 440.6 / 439.3 | -0.28% | 419.4 / 425.7 (+1.50%) | 37,140 / 40,434 | 91323.918 / 96895.820 |
| 256 | 0 | 199.1 / 213.9 | +7.44% | identical netlists | 143,428 / 144,237 | 357541.772 / 359696.904 |
| 256 | 1 | 188.4 / 199.4 | +5.84% | identical netlists | 145,630 / 146,419 | 360794.952 / 361999.400 |
- Rule met (+7.44%, +5.84%): copies KEPT; rtl/v2 = `rtl/tree_copies.v` + header comment (tree only: `rtl/tree_only.v`). Why: tree-only depth-256 paths start at `req_addr_reg` with 56/59 buffers, 3.5229/3.9664 ns (`CRITICAL_PATH.md`).
## Before (P5b) -> after (P5c, kept) — Fmax = 1/(period - WNS), 1 GHz netlists unless noted
| depth | mode | Fmax MHz | WNS @1 GHz ns | WNS @500 MHz ns | cells | area um^2 (1 GHz) |
|---|---|---|---|---|---|---|
| 16 | 0 | 629.2 -> 626.1 | -0.5892 -> -0.5973 | met -> met | 10,381 -> 10,834 | 25879.140 -> 26363.792 |
| 16 | 1 | 624.4 -> 611.6 | -0.6015 -> -0.6351 | met -> met | 10,690 -> 11,242 | 26137.160 -> 26634.048 |
| 64 | 0 | 476.1 -> 486.4 | -1.1004 -> -1.0561 | -0.2720 -> -0.3076 | 40,818 -> 41,192 | 96163.256 -> 96531.400 |
| 64 | 1 | 472.6 -> 439.3 | -1.1159 -> -1.2762 | -0.2950 -> -0.3492 | 41,303 -> 40,434 | 97302.268 -> 96895.820 |
| 256 | 0 | 188.4 -> 213.9 | -4.3074 -> -3.6744 | -3.3074 -> -2.6744 | 143,583 -> 144,237 | 359159.584 -> 359696.904 |
| 256 | 1 | 185.2 -> 199.4 | -4.3997 -> -4.0142 | -3.3997 -> -3.0142 | 147,232 -> 146,419 | 362078.136 -> 361999.400 |
## Where it did not help or made things worse (plain statement)
- Depth 64 mode 1 is worse than P5b: 472.6 -> 439.3 MHz; WNS at 500 MHz is worse at depth 64 in both modes.
- Depth 16 is slightly worse (-0.51% / -2.05%) though its logic is unchanged (GSIZE = 1). That is flow variation on
  the same logic, so differences of a few % here are not evidence of a design effect. The copies' -1.69% (d16 m1) and
  -0.28% (d64 m1) vs tree only are inside that range; their +5.84% at depth 256 mode 1 is not far above it.
- Depth 256 gained only +25.5 / +14.2 MHz over P5b; nothing meets 1 GHz, 500 MHz is met only at depth 16.
- Max-cap/slew violators besides rst_n (1 GHz, `RESULTS.md`): depth 256 mode 0 rose 64 -> 118, depth 64 mode 1 2 -> 9; fell at depth 256 mode 1 (83 -> 48) and depth 64 mode 0 (17 -> 8). The copies cost +300 flip-flops at every depth.
## New critical paths (kept design, 1 GHz; `CRITICAL_PATH.md`)
- Depth 256: Stage A is off the path. Both modes `req_addr_grp[15]` -> `freq_cnt`, 149 cells (mode 0: 4.6335 ns, 61 OAI21
  + 61 AOI21, 2.9785 ns). A reading, not a tool output: the hit path, i.e. tag compare, `hit_idx` loop (lines 116-120), increment.
- Depth 64: `stageA_min[12]` -> `valid_bits[34]` (Stage B/EVICT), 48 cells. Depth 16: `freq_cnt[2]` -> `valid_bits[15]`, 34 cells.
