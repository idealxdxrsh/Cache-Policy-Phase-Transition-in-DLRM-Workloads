# P9: why the RTL's hit counts differ from the trace simulator's; RTL-exact policy on slices and full traces
RTL unchanged (rtl/v2, tag rtl-v2-final). Tables: `results/P7/TABLES.md` section P9 (`tools/make_tables.py`). Slice counts are cold-start, not steady state. Tests: `tests/test_rtl_exact.py` 24 tests; suite 98 OK, 9 skipped (torch) (`unittest.txt`); mutation 19/19 caught (`mutation.txt`).
## (1) Model `trace_sim/rtl_exact.py`; (2) validation: 24/24 RTL runs, 0 mismatches in 2,560,448 requests (`validate/validate.json`)
- RTL-exact m0/m1: slots, invalid filled first (lowest index), eff = 0 if invalid else count+1, victim = lowest slot among min eff, install count 1 (m0) or slot count+1 (m1), saturation 63; checked against a literal Stage A/B tree model. Ablations of `LFUResetCache`: lowest-slot (255), 6-bit (oldest), both (written separately; equals RTL-exact m0).
- `synthesis/p9/tb_hitlog.sv` = P8's tb_power.sv + a per-request hit_flag log; zero-delay RTL, Icarus 12, depths 16/64/256, modes 0/1, row0/row1M. On P8's exact requests the summary line equals P8's in 12/12; whole 200,000-request slices 12/12. Hit logs not committed (sha256 `rtl/hits_gz.sha256`; `bash synthesis/p9/run_p9.sh all`).
## (4) Slices: the gap is the tie-break (`slices/slices.json`). In all 6 whole-slice and 12 P8-prefix runs, lowest-slot alone gives the whole gap; 6-bit 0 hits; interaction 0
- Mode 0 evicts the line installed by the previous miss in 118,522 of 118,523 evictions (row0, 256; oldest 0). At 16 entries the order reverses (row0: oldest 17,035 < RTL m0 19,946; LRU 151).
## (5) Full traces: jobs 419424-419427 COMPLETED, exit 0 (`jobs.txt`; `cluster/rows_<N>_set<A|B>/`; wall 3:34.60 / 17:52.49 A 2M/10M, 5:26.53 / 24:32.24 B; peak RSS <= 2,380,696 kB, `time.txt`)
- **LFU-reset reproduced P3b exactly:** `cluster/rows_{2000000,10000000}_setA/p3b_check.txt` = `P3B_CHECK PASS`, equal hits and misses in total and in all 26 tables at all 4 sizes, and equal stream totals (e.g. 47.6719% at 256/2M). LRU, ARC, LFU persistent, W-TinyLFU are P3b's files (not rerun).
- Total hit % (P3b parts + `cluster/rows_<N>_setA/parts/*.csv`). Lowest-slot and lowest-slot 6-bit give exactly the RTL-exact m0 hits and 6-bit exactly the oldest hits at all 8 points, so they are not repeated as columns:

| rows, entries | LRU | ARC | LFU-reset (oldest) = 6-bit | LFU persistent | W-TinyLFU | RTL-exact m0 = lowest-slot = lowest-slot 6-bit | RTL-exact m1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2M, 256 | 41.4010 | 50.9225 | 47.6719 | 41.0006 | 50.9749 | 39.3685 | 43.0680 |
| 2M, 1,000 | 53.6803 | 61.7905 | 58.4477 | 56.1060 | 62.0342 | 50.5128 | 53.1589 |
| 2M, 10,000 | 75.4015 | 80.7592 | 77.9677 | 81.9279 | 80.8618 | 72.6211 | 74.2149 |
| 2M, 100,000 | 90.4240 | 92.3695 | 91.6117 | 92.5839 | 91.9523 | 88.6136 | 91.2062 |
| 10M, 256 | 41.2640 | 50.8773 | 48.1592 | 38.4896 | 50.9101 | 39.8162 | 43.1205 |
| 10M, 1,000 | 53.4740 | 61.6774 | 59.1030 | 52.9099 | 61.9160 | 51.4595 | 53.4319 |
| 10M, 10,000 | 75.0711 | 80.5750 | 78.0735 | 78.3167 | 80.6457 | 72.8623 | 74.2280 |
| 10M, 100,000 | 90.0219 | 92.1847 | 90.9315 | 92.3924 | 91.9623 | 88.3256 | 89.7660 |
- **6-bit saturation changes 0 hits** on the full traces at all 4 sizes, 2M and 10M (sat = 0, interaction = 0). **The lowest-slot gap holds at 10M:** the tie-break is the whole gap at every size: 19,313,343 / 17,694,103 / 12,063,431 / 6,032,359 hits at 256 / 1,000 / 10,000 / 100,000 (2M: 3,830,254 / 3,660,286 / 2,466,281 / 1,382,947).
- **RTL-exact m0 loses to LRU at every size**, on both traces (2M: -937,559 / -1,461,135 / -1,282,536 / -835,082 hits; 10M: -3,351,497 / -4,663,509 / -5,113,301 / -3,926,788).
- **RTL-exact m1 beats LRU** at 256 (2M +768,969; 10M +4,297,538) and at 100,000 on 2M only (+360,815). **It loses to LRU** at 1,000 (2M -240,485; 10M -97,654), at 10,000 (-547,354; -1,951,805) and at 100,000 on 10M (-592,310).
## (6) Tie-break candidates, proposed only (`CANDIDATES.md`; 8 / 8 / 256 flip-flops; logic, timing not synthesized). Full traces, hit % (recovered % of the gap from RTL-exact of the same mode up to LFU-reset (oldest), from hits; `cluster/rows_<N>_setB/parts/*.csv`)

| rows, entries | Rotate-victim m0 | Rotate-step m0 | Young-bit m0 | Rotate-victim m1 | Rotate-step m1 | Young-bit m1 |
|---|---:|---:|---:|---:|---:|---:|
| 2M, 256 | 47.6719 (100.0) | 47.6670 (99.9) | 47.6719 (100.0) | 35.5568 (-163.1) | 35.5567 (-163.2) | 35.5568 (-163.1) |
| 2M, 1,000 | 58.4477 (100.0) | 58.8394 (104.9) | 58.4476 (100.0) | 49.4707 (-69.7) | 49.4706 (-69.7) | 49.4706 (-69.7) |
| 2M, 10,000 | 77.9677 (100.0) | 78.3310 (106.8) | 77.9630 (99.9) | 71.8884 (-62.0) | 71.8852 (-62.1) | 71.8865 (-62.0) |
| 2M, 100,000 | 91.6117 (100.0) | 91.7569 (104.8) | 91.6117 (100.0) | 90.8820 (-79.9) | 90.8455 (-88.9) | 90.8670 (-83.6) |
| 10M, 256 | 48.1592 (100.0) | 48.2054 (100.6) | 48.1592 (100.0) | 35.4649 (-151.9) | 35.4648 (-151.9) | 35.4648 (-151.9) |
| 10M, 1,000 | 59.1030 (100.0) | 59.3134 (102.8) | 59.1019 (100.0) | 49.2686 (-73.4) | 49.2686 (-73.4) | 49.2686 (-73.4) |
| 10M, 10,000 | 78.0739 (100.0) | 78.4469 (107.2) | 78.0673 (99.9) | 71.3895 (-73.8) | 71.3888 (-73.8) | 71.3891 (-73.8) |
| 10M, 100,000 | 90.9315 (100.0) | 91.2094 (110.7) | 90.9313 (100.0) | 88.2631 (-129.0) | 88.2558 (-129.6) | 88.2602 (-129.2) |
- Mode 0: Rotate-victim and Young-bit recover the whole gap to one decimal (99.9-100.0%) at every size, but are not identical to LFU-reset (oldest): Rotate-victim differs by -2 to +918 hits, Young-bit by -14,150 to 0. Rotate-step beats LFU-reset (oldest) at 7 of 8 points (up to +864,464 hits, 10M/10,000), not at 2M/256 (-2,248). Every mode-0 rule beats LRU at every size.
- Mode 1: all three rules give fewer hits than RTL-exact m1 at every size (negative recovered %); not worth synthesizing.
Limits: full traces are trace-simulator results, validated against the RTL on the slices (sections 2, 4). Candidate costs are flip-flop cell counts only.
