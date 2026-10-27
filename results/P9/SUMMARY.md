# P9: why the RTL's hit counts differ from the trace simulator's; RTL-exact policy (local; no cluster job submitted)
RTL unchanged (rtl/v2, tag rtl-v2-final). Tables: `results/P7/TABLES.md` section P9 (`tools/make_tables.py`). Hit counts are slice counts from a cold start, not steady state.
## (1) Model: `trace_sim/rtl_exact.py`
- RTL-exact (modes 0/1) has slots, invalid slots filled first (lowest index), eff = 0 if invalid else count+1, victim = lowest slot among min eff, install count 1 (m0) or slot count+1 (m1), saturation at 63. A literal Stage A/B tree model is used to check it.
- Ablations of `LFUResetCache`: lowest-slot (255), 6-bit (oldest), both. "Both" is written separately from RTL-exact and equals it (tests, all slices).
- Selectable by name in `run_shared_cache.py --policies`; default policies unchanged.
## (2) Validation: 24/24 runs, 0 mismatches, 2,560,448 requests compared one by one (`validate/validate.json`)
- `synthesis/p9/tb_hitlog.sv` = P8's tb_power.sv + a per-request hit_flag log (diff: header). Zero-delay RTL, Icarus 12, depths 16/64/256, modes 0/1, row0/row1M.
- P8's exact requests (P8 cycle budget, R = 5,798-28,493): the summary line equals P8's in 12/12. Whole slices (200,000 each): 12/12.
- Hit logs: not committed (12 MB); sha256 in `rtl/hits_gz.sha256`; regenerate with `bash synthesis/p9/run_p9.sh all` (5:53.67 locally).
## (3) Tests: `tests/test_rtl_exact.py` 24 tests; full suite 98 OK, 9 skipped (torch) (`unittest.txt`); mutation 19/19 caught (`mutation.txt`)
## (4) The gap is the tie-break (`slices/slices.json`; hits, 200,000 requests)
| slice, entries | LRU | LFU-reset (oldest) | lowest-slot | 6-bit | RTL-exact m0 (= lowest-slot 6-bit) | RTL-exact m1 |
|---|---:|---:|---:|---:|---:|---:|
| row0, 64 | 51,543 | 80,697 | 54,737 | 80,697 | 54,737 | 61,252 |
| row0, 256 | 85,437 | 103,382 | 81,221 | 103,382 | 81,221 | 91,192 |
| row1M, 256 | 83,029 | 101,867 | 83,219 | 101,867 | 83,219 | 86,439 |
- In all 6 whole-slice runs and all 12 P8-prefix runs, the lowest-slot tie-break alone gives the whole gap. 6-bit saturation changes 0 hits and the interaction is 0. Example, P8 d64 m0 row0: RTL 1,762 vs 2,532, gap 770 = tie 770.
- Mechanism: in mode 0 a new line (count 1) sits in the lowest minimum slot and is evicted by the next miss, in 118,522 of 118,523 evictions (row0, 256; oldest: 0).
- Mode 1 partly avoids this: m1 - m0 = +3,220 to +10,072 hits. At 16 entries the order reverses (row0: oldest 17,035 < RTL m0 19,946; LRU 151), because a row's 26 tables cycle through 16 lines.
## (5) Full traces: NOT RUN. Job list in `jobs.txt` waits for your OK (4 jobs, compute, 4 CPUs each)
- A: RTL-exact m0/m1, 3 ablations, LFUResetCache (check vs P3b). B: the candidate rules. 2M 16G/1 h; 10M 32G/2 h, afterok on the 2M job.
- Projected CPU (`jobs/sizing.json`, from measured times): A 700 s / 3,392 s, B 1,092 s / 5,335 s (2M / 10M).
## (6) Tie-break candidates, proposed only (`CANDIDATES.md`)
- Rotate-victim (8 flip-flops), Rotate-step (8), Young-bit (256 = 1361.92 um^2 flip-flop cells, 0.3694% of the d256 m0 500 MHz area). Logic not synthesized. Timing unknown, but every rule widens the victim-selection comparators, which are on the reported critical paths.
- Mode 0, 64/256 entries: Rotate-victim and Young-bit recover 100.0% of the gap on all 4 runs, Rotate-step 97.0-111.8%. On synthetic traces these rules are not equivalent to the oldest-first rule (9, 54 and 14 of 60 traces differ). With mode 1 all three are worse than RTL-exact m1.
## Limits
- Slices are 200,000 accesses with a cold start. RTL-level check only (P8 showed netlist = RTL on counts). Candidate costs are flip-flop cell counts, not synthesis.
