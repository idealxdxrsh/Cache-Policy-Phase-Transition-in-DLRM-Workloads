# P5 summary: rtl/v2 LFU controller on NanGate45 — NanGate45, not TSMC; pre-layout; no power numbers
Every number below is NanGate45 (typical, 1.1V, 25C), not TSMC, pre-layout (wire-load 5K_hvratio_1_1, ideal clock, no
placement/routing). No power step was run, so there are no power numbers. Full table: `RESULTS.md` (`tools/p5_results.py`).
Tools and sources (commits, sizes, sha256, liberty licence header): `SOURCES.md`. Driver: `synthesis/p5/run_p5.sh`.

## Checks before the RTL runs
- OpenSTA on one INV_X1 at liberty table points matches the tables exactly: rise 0.0142069 ns, fall 0.0076343 ns,
  slack 0.9857931 ns at 1.0 ns (`sta_check_inv1.txt`).
- Icarus: `ALL TESTS PASSED` for depth 16, 64, 256 x COUNTER_MODE 0, 1 (`sim/sim_d<D>_m<M>.txt`; the testbench depth is
  now a parameter, default 256). COUNTER_MODE 2 stops at elaboration as designed (`sim/mode2_elab.txt`), not synthesized.

## Results (12 runs, all exit 0; `d<D>_m<M>_<F>MHz/`) — NanGate45, not TSMC, pre-layout
| depth | mode | cells | flip-flops | area um^2 (sum of cell areas) | FF area share | WNS @1 GHz ns | WNS @500 MHz ns | Fmax MHz (pre-layout) |
|---|---|---|---|---|---|---|---|---|
| 16 | 0 | 9,399 | 2,657 | 23688.630 | 0.5967 | -3.9226 | -2.9226 | 203.1 |
| 16 | 1 | 10,467 | 2,657 | 24643.038 | 0.5736 | -3.6487 | -2.6487 | 215.1 |
| 64 | 0 | 36,605 | 10,131 | 90869.324 | 0.5928 | -4.1363 | -3.1363 | 194.7 |
| 64 | 1 | 37,204 | 10,131 | 91623.168 | 0.5880 | -4.2487 | -3.2487 | 190.5 |
| 256 | 0 | 143,139 | 39,925 | 358573.054 | 0.5922 | -4.9752 | -3.9752 | 167.4 |
| 256 | 1 | 144,521 | 39,925 | 364404.838 | 0.5827 | -5.0483 | -4.0483 | 165.3 |
- No configuration meets 1 GHz or 500 MHz. Fmax = 1 / (period - WNS), from the worst setup path (flip-flop to flip-flop
  in every run), pre-layout only. Worst hold slack is 0.0317 ns in all 12 runs.
- The 1 GHz and 500 MHz netlists are byte-identical for every depth/mode (`netlists.sha256`): the abc delay target did
  not change the mapping, so cells/area are per depth/mode and the two WNS values differ by exactly the 1 ns period gap.
- Flip-flops (the tag/data/counter/valid arrays; no SRAM macro) are 0.5736-0.5967 of the cell area in every run.
- Mode 1 vs mode 0: more cells at every depth; Fmax higher at depth 16, lower at 64 and 256 (table above).

## Caveats (read before quoting any number)
- Pre-layout DRC is not clean. rst_n drives every DFFR directly (2,657 DFFR_X1 at depth 16, `stat.txt`) and violates max slew/cap in all
  runs; its recovery/removal paths are excluded (`set_false_path -from rst_n`). Other max-cap/slew violators (distinct
  pins, `RESULTS.md`): depth 16: 0 (mode 0) / 2 (mode 1); 64: 0 / 2; 256: 18 / 130. A layout flow would buffer these and
  the timing would change.
- Changes from PLAN.md: abc gets `-constr synthesis/p5/abc.constr` (BUF_X1 driver, 3.795620 fF output load) because
  without it abc inserted no buffers (first depth-16 try showed internal max-slew violations; its output was
  overwritten, so no number is quoted); STA uses the same driver/load.
  Yosys loads the liberty with `read_liberty -lib` so `check -assert` sees cell pin directions.
- Area is the sum of liberty cell areas, not a placed area. Gate-level netlists were not simulated.
- Netlists (93M) are not committed; rerun `bash synthesis/p5/run_p5.sh` (depth 256 Yosys: 5:44.02-9:16.78 wall per run).
