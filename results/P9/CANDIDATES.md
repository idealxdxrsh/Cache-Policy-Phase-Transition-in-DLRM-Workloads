# P9 (6): hardware-friendly tie-break rules, proposed only (not implemented in the RTL)

The RTL picks the lowest slot among the minimum effective count. In mode 0, a newly installed line has count 1, the
minimum. Its slot was the lowest slot at the minimum, so it is again the lowest at the minimum and is evicted by the
next miss unless it is hit first. On the full slices, RTL-exact mode 0 evicts the line installed by the previous miss
in 118,522 of 118,523 evictions (row0, 256 entries); LFU-reset (oldest) does so in 0 (`slices/slices.json`, field
`evicted_previous_install`). The rules below change only which slot wins among equal effective counts.

| rule | what changes | added state (by construction, depth 256, 16 groups) | added logic (not synthesized) |
|---|---|---|---|
| R1 Rotate-victim | circular priority: among equal eff, the first slot at or after `ptr`; `ptr <= victim + 1` in FILL | 8 flip-flops (`ptr`) | per-slot bit `slot < ptr` (thermometer decode of `ptr`, shared); tree key 7 -> 8 bits in Stage A (16 trees x 15 nodes) and Stage B (15 nodes); Stage B needs `stageA_min[g] < ptr` (16 x 8-bit compares, or 16 more Stage A flip-flops); 8-bit incrementer |
| R2 Rotate-step | as R1, but `ptr` is a counter, +1 per miss | 8 flip-flops | as R1, without the load from `victim_reg` |
| R3 Young-bit | one bit per slot, set in FILL; key (eff, young, slot); if the chosen victim is young, clear all young bits | 256 flip-flops (one per slot) | tree key 7 -> 8 bits as R1; Stage B reads `young[stageA_min[g]]` like `freq_cnt`; one clear signal to 256 flip-flops |

Cell area of the added flip-flops only, from the NanGate45 liberty already used in P5 (`DFFR_X1` area 5.320000 um^2;
`~/eda/pdk/nangate45/NangateOpenCellLibrary_typical.lib`, sha256 8d540a4d...e9b1 as `results/P5/SOURCES.md`):
R1 and R2, 8 x 5.32 = 42.56 um^2; R3, 256 x 5.32 = 1361.92 um^2. That is 0.0115% and 0.3694% of the depth-256 mode-0
500 MHz netlist area of 368641.154 um^2 (`results/P5e/new/RESULTS.md`). These figures cover only the flip-flop cells.
They include none of the logic in the last column, which was not synthesized, so they do not give the total area cost.

Timing: none of the rules was synthesized, so I have no number. Every worst path reported for the current RTL starts or
ends in victim selection (`freq_cnt` -> `stageA_min` / `victim_reg` / `valid_bits`, `stageA_min` -> `valid_bits`;
`results/P5e/CRITICAL_PATH.md`). All three rules widen the comparators on those paths by one key bit, so they add
delay on the critical path. At depth 256, the 500 MHz netlists already miss timing by 0.0357 ns (mode 0) and 0.0015 ns
(mode 1) (`results/P5e/SUMMARY.md`). The per-slot inputs of R1/R2 (`slot < ptr`) and R3 (`young`) come from flip-flops
that are stable during LOOKUP, as `freq_cnt` is. Measuring the cost needs a synthesis run of each variant, which was
not done (no RTL change in P9).

What they recover on the slices (trace simulator, 200,000 requests, cold start; `slices/slices.json`, also in
TABLES.md): with mode 0 at 64 and 256 entries, R1 and R3 give exactly the hits of LFU-reset (oldest) on all four
slice/depth runs, i.e. 100.0% of the gap. R2 gives 98.6%, 99.6%, 111.8% and 97.0%. That equality is not a general
equivalence: on synthetic Zipf traces, R1 differs from LFU-reset (oldest) on 9 of 60, R2 on 54 and R3 on 14
(`synthetic_probe`).
With mode 1 every rule is worse than RTL-exact mode 1 (row0 at 256: R1 75,502, R2 75,454, R3 75,483 vs 91,192).
Under mode 1 a fair tie-break raises the counts of all slots together, so frequent lines are no longer kept. Only the
mode-0 combinations are worth a synthesis run. At 16 entries every rule except R2 gives fewer hits than RTL-exact
mode 0 (17,035 vs 19,946 on row0), and so does LFU-reset (oldest). There a row's 26 tables cycle through 16 entries:
LRU gets 151 hits, and the RTL's habit of re-evicting the newest line keeps older lines resident.
Full-trace numbers for the rules come from cluster job set B (`results/P9/jobs/sizing.json`), not yet submitted.
