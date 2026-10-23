# P3 prep (offline, no cluster job): summary (2026-10-23)

Local only: Python 3.12.3, numpy 1.26.4. No pytest or matplotlib installed locally (none installed).
Reproduce: `python3 -m unittest discover -s tests -v` and `python3 tools/mutate_policies.py`.

## Changes
- `trace_sim/run_trace_sim.py`
  - `CountMinSketch`: 4 rows, width = next power of two >= capacity (min 16), 4-bit
    saturating counters, all counters halved every 10 x capacity increments. No doorkeeper.
  - `WTinyLFUCache` ("W-TinyLFU (Count-Min, window=1%)"): LRU window, SLRU main
    (80% protected), admits only if sketch(candidate) > sketch(victim); ties rejected.
    Not modelled: doorkeeper, Caffeine's random admission, adaptive window.
  - `ARCCache`: Megiddo & Modha 2003 pseudocode (T1/T2/B1/B2, adaptive p).
  - Exact-counter TinyLFU renamed "TinyLFU-exact (window=1%)" so it is not mistaken for the sketch version.
  - `DEFAULT_CAPACITIES` = 64, 128, 256, 512, 1000, 2000, 5000, 10k, 20k, 50k, 100k vectors,
    one cache per embedding table. "1k/2k" taken as 1000/2000 (not 1024/2048).
- `trace_sim/submit_trace_sim.sh`: same capacity list (not submitted).
- `trace_sim/plot_trace_results.py`: TinyLFU curve now uses the Count-Min policy. Removed
  "our RTL" labels from the per-address-history LFU, because the RTL keeps no per-address history.
- `tests/test_policies.py` (new, unittest; pytest can also run it), 29 tests.
- `tools/gen_synthetic_criteo.py` (new): synthetic file in train.txt layout.
- `tools/mutate_policies.py` (new): 11 broken copies, and each one must fail the tests.

## Verification
- Tests: 29 run, OK (`results/P3_prep/unittest.txt`).
- Mutation: 11/11 mutants caught (`results/P3_prep/mutation.txt`). Two W-TinyLFU mutants
  (admit on tie, no SLRU promotion) at first slipped through; I added tests for both.
- End-to-end sweep, 6 policies x 11 capacities, on 20,000 SYNTHETIC rows (seed 0): ran OK
  (`results/P3_prep/synthetic/run_log.txt`, `trace_sim_results.json`; timing in `time.txt`).
  These hit rates come from synthetic Zipf data. They are only a smoke test and must not be reported.
- Plot script not run: no matplotlib locally (`results/P3_prep/synthetic/plot_log.txt`).
  `cluster/environment.yml` lists matplotlib.

## Still open before the P3 cluster run
- Per-table hit rates (run_one currently sums over the 26 tables) and per-table Zipf fit.
- Optional Belady. The plot shows only LRU, the two LFUs and W-TinyLFU (not ARC or TinyLFU-exact).
- Runtime at 2M/10M rows is not measured. The simulator is pure Python.
- The question "does LFU beat LRU at 256 vectors?" is unanswered. That needs real Criteo data.
