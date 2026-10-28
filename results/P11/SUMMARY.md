# P11: rtl/v3 (Rotate-victim in mode 0) full-trace hit rates, synthesis, gate-level lockstep, mutation, equivalence
Driver `cluster/p11_driver.sh`. Cluster jobs (`jobs.txt`, `sacct.txt`): 419663, 419664 (part A), 419703 / 419704 / 419705 (GLS arrays, depths 16 / 64 / 256), all COMPLETED 0:0. NanGate45 is an open PDK, not TSMC. All synthesis numbers are pre-layout. No RTL was changed in P11 (rtl/v3 is the P10 file, sha256 13a7a7a9… in `equiv/`).
## Part A: full traces, one cache shared by 26 tables, P9 stream and order (`PARTA.md`, from `cluster/rows_<N>/shared_cache_results.json`)
| rows | entries | LRU | LFU-reset (oldest) | v2: RTL-exact m0 | v3: Rotate-victim m0 | v3 - v2 hits | tables with v3 < v2 (hits lost) |
|---|---|---:|---:|---:|---:|---:|---|
| 2M | 16 | 0.0792% | 14.2361% | 9.4309% | 14.2361% | +2,216,578 | 10 of 26 (890,527) |
| 2M | 64 | 24.9119% | 38.9979% | 28.3291% | 38.9979% | +4,921,393 | 4 of 26 (14,305) |
| 10M | 16 | 0.0796% | 14.8318% | 9.5573% | 14.8318% | +12,210,235 | 10 of 26 (4,726,864) |
| 10M | 64 | 25.0508% | 39.2538% | 28.4614% | 39.2538% | +24,983,685 | 4 of 26 (95,475) |
- 256 entries was rerun as a check: totals and per-table counts equal P3b (LRU, LFU-reset) and P9 sets A/B (`cluster/rows_{2000000,10000000}/ref_check.txt`: P11_REF_CHECK PASS). Rows were added to `results/P7/TABLES.md` by `tools/make_tables.py`.
- v3 equals LFU-reset exactly, in total and per table, at 16, 64 and 256 entries on both traces (`PARTA.md`).
- Where v3 loses to v2: never in total hits on the full traces. Inside the shared cache, 10 of 26 tables at 16 entries, 4 at 64 and 2 at 256 have fewer hits under v3 (`PARTA.md`). On P10's cold-start 200,000-request slices at depth 16, v3 has fewer hits than the v2 rule (row0 17,035 vs 19,946; row1M 5,217 vs 18,254; `results/P10/SUMMARY.md`).
## Part B: synthesis, P5e flow unchanged, run LOCALLY (`SYNTH.md`, `synth/*`, `run_synth.txt`)
Synthesis ran on the local machine, not through sbatch: Yosys 0.33, OpenSTA 3.1.0 and the liberty (local only, `results/P5/SOURCES.md`) are local, and the cluster has Yosys 0.62 and no OpenSTA. v2 = rtl-v2-final (`results/P5e/new`).
| depth | mode | flip-flops v2 -> v3 | area 1 GHz v2 -> v3 um^2 | Fmax 1 GHz v2 -> v3 MHz | 500 MHz WNS v2 -> v3 ns |
|---|---|---|---|---|---|
| 16 | 0 | 2,957 -> 2,961 | 26744.438 -> 27196.638 (+1.69%) | 636.1 -> 662.5 (+4.14%) | met -> met |
| 16 | 1 | 2,957 -> 2,957 | 26626.866 -> 26599.202 (-0.10%) | 659.5 -> 691.4 (+4.83%) | met -> met |
| 64 | 0 | 10,431 -> 10,437 | 94385.578 -> 95559.170 (+1.24%) | 603.0 -> 599.4 (-0.59%) | met -> met |
| 64 | 1 | 10,431 -> 10,431 | 95100.852 -> 95064.676 (-0.04%) | 611.2 -> 571.9 (-6.44%) | met -> met |
| 256 | 0 | 40,225 -> 40,233 | 369529.860 -> 369396.594 (-0.04%) | 556.6 -> 528.3 (-5.08%) | -0.0357 -> -0.0130 (not met) |
| 256 | 1 | 40,225 -> 40,225 | 370226.514 -> 370835.654 (+0.16%) | 542.3 -> 533.1 (-1.69%) | -0.0015 -> -0.0377 (not met) |
- Flow variation: v3 mode 1 is the same logic as v2 mode 1 (Yosys-proven equivalent at depth 64, below), yet its Fmax moved by -6.44% at depth 64, 1 GHz. This 6.44% is the observed flow variation. Every v3 mode-0 Fmax change (+4.14%, -0.59%, -5.08% at 1 GHz; 491.2 -> 496.8 MHz, +1.13%, at depth 256, 500 MHz) is within it, so no Fmax cost (or gain) of Rotate-victim is claimed. The P5d / P5e noise floors are also in `SYNTH.md`; P5d's floor is larger than every change.
- Area: the same-logic mode-1 pairs vary by -0.31% to +0.16% (all 6 netlists, `SYNTH.md`). Mode 0 is +1.69% / +1.24% at depths 16 / 64 (1 GHz), above that range; at depth 256 it is -0.04%, inside it. Flip-flops in mode 0 grow by exactly the ptr width (+4 / +6 / +8); mode 1 adds 0.
## Equivalence, v2 mode 1 vs v3 mode 1, RTL, Yosys 0.33, LOCAL (`synthesis/p11/equiv_v2_v3_m1.sh`, `equiv/`)
PROVEN at depth 64: all 12,578 $equiv cells proven, 0 unproven, exit 0, in 4066.31 s (`equiv/equiv_d64_m1.txt`). Also proven at depth 16: 3,520 of 3,520 cells (`equiv/equiv_d16_m1.txt`). The commands are those of `synthesis/p5d/equiv_packed_vs_array.sh` (proc, memory, flatten, async2sync, equiv_make, equiv_simple, equiv_induct, equiv_status -assert). gold = tag rtl-v2-final, gate = rtl/v3. This proves the RTL equivalent, not the netlists.
## Gate-level lockstep, functional, zero delay (`gls.json`, `gls_check.txt`, `cluster/gls/results/*.txt`)
Each array task = one netlist (1000 or 500 MHz) x one slice (row0, row1M); task order in `gls_tasks_d<D>.txt`. Run on the cluster with Icarus 11.
| array (depth) | mode | tasks | hits RTL = netlist, row0 / row1M | mismatching cycles | X cycles netlist / RTL |
|---|---|---|---|---|---|
| 419703 (16) | 0 / 1 | _1-_4 / _5-_8 | 17,035 / 5,217 ; 30,018 / 26,350 | 0 in every task | 0 / 0 in every task |
| 419704 (64) | 0 / 1 | _1-_4 / _5-_8 | 80,697 / 77,528 ; 61,252 / 59,978 | 0 in every task | 0 / 0 in every task |
| 419705 (256) | 0 / 1 | _1-_4 / _5-_8 | 103,382 / 101,867 ; 91,192 / 86,439 | 0 in every task | 0 / 0 in every task |
- 24/24 pass: all 200,000 requests replayed. The netlist, RTL and trace sha256 match the local files, and the RTL hit log sha256 equals P10's for the same depth, mode and slice (`tools/p11_gls_check.py`).
## Mutation suite on v3, LOCAL, Icarus 12 (`mutation.txt`, `tools/mutate_rtl.py --v3 --lockstep`)
RESULT: OK. Out of 210 mutant cells: 140 were killed by the testbench, 5 by lockstep against rtl-v2-baseline (mode 1), 0 non-equivalent mutants survived, and 62 equivalent cells survived as expected. 3 equivalent cells were killed: TEST 8 checks the internal ptr in mode 1.
## Not measured
Power; timing-annotated (SDF) gate-level simulation; layout and placed area; a noise floor at 500 MHz; TSMC; part A on any other stream or order; equivalence at depth 256, and of the netlists.
