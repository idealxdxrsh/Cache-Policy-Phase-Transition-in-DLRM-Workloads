# P5e: measurement flow only (no RTL change; rtl-v2-final) — NanGate45, not TSMC; pre-layout; no power numbers
Local only, driver `synthesis/p5e/run_p5e.sh`. Tables: `COMPARE.md` (sections 1-5), `new/RESULTS.md`, `CRITICAL_PATH.md`. Old flow = `results/P5d`.
## (1) Does the clock target reach ABC? Yes. Why the 1 GHz and 500 MHz netlists were often identical (`COMPARE.md` s.1)
- `run_p5d.sh` calls `synthesis/p5/run_p5.sh`, which fills `synthesis/p5/synth.ys.in` line 14: `abc -liberty <NanGate45 lib>
  -D <period ps> -constr synthesis/p5/abc.constr` (BUF_X1 drive, 3.795620 fF load). Yosys expands it to (`d16_m0_1000MHz/yosys.log.gz`):
  `strash; &get -n; &fraig -x; &put; scorr; dc2; dretime; retime -o -D 1000; strash; &get -n; &dch -f; &nf -D 1000; &put; buffer; upsize -D 1000; dnsize -D 1000; stime -p`.
- The netlists are identical exactly where ABC's own delay estimate is above both targets (P5, all depths; P5b and P5c, depth 256:
  4153.14-5447.77 ps). Then -D cannot bind, and both runs map for minimum delay. Below 2000 ps they differ.
- ABC's timer was optimistic: `buffer`/`upsize`/`dnsize`/`stime` ran without `-c`, so with no wire load ("none"), while OpenSTA uses
  5K_hvratio_1_1, and ABC does not see flip-flop clk->Q or setup. Example, P5d depth 64 mode 0 at 500 MHz: ABC 1861.80 ps (thinks met), STA arrival 2.1358 ns (WNS -0.1794).
## (2) New flow: `synthesis/p5e/synth_td.ys.in` + `abc_td.script.in` (same Yosys steps; only the abc call changes)
3 delay-oriented passes `&st; &syn2; &if -g -K 6; &synch2; &nf -D`, then `buffer -c -p` (also buffers flip-flop outputs), `upsize -c`, `dnsize -c`, all
with the liberty wire load 5K_hvratio_1_1. ABC target = period - 141.5 ps; 141.5 = clk->Q 0.0983 + setup 0.0432 ns (`results/P5d/d16_m0_1000MHz/sta.txt`).
| depth | mode | Fmax MHz old -> new (1 GHz netlist) | 500 MHz netlist old -> new | area um^2 old -> new | other slew/cap violators | yosys wall |
|---|---|---|---|---|---|---|
| 16 | 0 | 571.3 -> 636.1 (+11.35%) | met -> met | 26733.266 -> 26744.438 | 0 -> 1 | 0:16.84 -> 0:32.55 |
| 16 | 1 | 586.9 -> 659.5 (+12.39%) | met -> met | 26875.310 -> 26626.866 | 1 -> 1 | 0:21.11 -> 0:26.74 |
| 64 | 0 | 528.4 -> 603.0 (+14.11%) | 458.8 -> met | 92969.660 -> 94385.578 | 2 -> 7 | 1:51.19 -> 3:10.95 |
| 64 | 1 | 470.9 -> 611.2 (+29.80%) | 427.4 -> met | 93294.180 -> 95100.852 | 3 -> 6 | 1:36.30 -> 3:31.80 |
| 256 | 0 | 451.2 -> 556.6 (+23.34%) | 426.8 -> 491.2 (WNS -0.0357) | 359441.544 -> 369529.860 | 120 -> 61 | 16:51.35 -> 31:06.89 |
| 256 | 1 | 435.3 -> 542.3 (+24.58%) | 428.0 -> 499.6 (WNS -0.0015) | 362935.454 -> 370226.514 | 108 -> 19 | 12:00.22 -> 34:41.70 |
## (3) Noise floor, same 8 same-logic designs as `results/P5d/NOISE.md`, 1 GHz netlists (`COMPARE.md` s.3), Fmax min-max MHz (spread)
| depth | mode | old flow | new flow |
|---|---|---|---|
| 16 | 0 / 1 | 560.7-623.0 (11.12%) / 563.1-620.5 (10.20%) | 636.1-739.4 (16.23%) / 642.2-691.8 (7.71%) |
| 64 | 0 / 1 | 528.4-538.8 (1.96%) / 470.9-549.1 (16.62%) | 603.0-640.6 (6.24%) / 591.4-620.5 (4.92%) |
| 256 | 0 / 1 | 397.9-451.8 (13.54%) / 409.0-435.3 (6.42%) | 512.8-556.6 (8.53%) / 520.4-556.9 (7.02%) |
- The new flow is better above noise: in every depth/mode its lowest variant beats the old flow's highest. The noise floor is still large (4.92-16.23%).
## 500 MHz: met at depths 16 and 64 (both modes); not met at depth 256 — stopped here as asked
- Short by 0.0357 ns (mode 0) and 0.0015 ns (mode 1), i.e. 1.79% and 0.07% of the 2 ns period (`COMPARE.md` s.4), well inside the new-flow spread at depth 256 (8.53% / 7.02%, measured on 1 GHz netlists). So whether depth 256 meets 500 MHz cannot be told from this flow.
## (4) Can a cycle exercise the reported worst paths? (rtl/v2/lfu_cache_controller.v at rtl-v2-final)
- stageA_min -> valid_bits: YES. stageA_min loads only on the LOOKUP-miss edge (lines 191-193, 247); the next cycle is EVICT, which clears valid_bits[victim_comb] (line 286). Same for -> victim_reg (line 285).
- stageA_min -> data_store (old flow, depth 64 m1, depth 256 m1): NO as a one-cycle path. data_store loads only in FILL (lines 292, 295) from victim_reg, at least 2 cycles after stageA_min changes (line 248).
- freq_cnt -> valid_bits (old depth 16; new depth 64 m0 1 GHz, depth 256 m1 500 MHz), -> victim_reg (new depths 16, 64 m1), -> stageA_min (new depth 256 m0): NO. freq_cnt loads only on edges into IDLE (lines 281, 298-300; 247, 249), so EVICT is >= 3 cycles later and the end of LOOKUP >= 2 cycles later.
- Check (`tools/p5e_mcp.py`, `COMPARE.md` s.5): these pairs as multicycle exceptions (2 or 3) change WNS by at most 0.0628 ns old and 0.0259 ns new; depth-256 500 MHz stays at -0.0357 / -0.0001 ns.
  The first pass had only 2 pairs (`COMPARE_pass1.md`, `mcp_pass1/`); I added stageA_min -> tag_store, freq_cnt -> stageA_min/victim_reg after seeing its worst paths.
- Not excepted but also NO: valid_bits -> victim_reg (new, depth 16; valid_bits changes only on edges out of EVICT/FILL, lines 286, 296, so the next EVICT is >= 3 cycles later) and freq_cnt -> data_store (old, depth 64 m1; FILL >= 4 cycles later). UNKNOWN: valid_bits -> valid_bits (old, depth 16; FILL writes valid_bits by victim_reg, so it depends on gate-level sensitization).
## Limits (plain statement)
- No ablation of which part of the new script helps; it was picked on one pilot (depth 16 mode 0, rtl-v2-final) before the full run. Yosys time up to 34:41.70 at depth 256. Violators rose at depth 64 (2 -> 7, 3 -> 6). No equivalence check or gate-level simulation of the new netlists. Headline numbers use no exceptions.
