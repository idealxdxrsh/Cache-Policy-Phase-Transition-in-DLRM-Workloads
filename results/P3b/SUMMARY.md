# P3b: shared-cache trace simulator (prep only, no cluster job submitted)

All hit rates in this folder are from SYNTHETIC data (tools/gen_synthetic_criteo.py): smoke tests, not results.
Local: Python 3.12.3, numpy 1.26.4 (`.venv`), 12 cores.

## Model (`trace_sim/run_shared_cache.py`)
- ONE cache shared by all 26 tables (P3 used 26 private caches, see `results/P3/ANALYSIS.md`).
- Order: Criteo rows in file order; within a row, tables 0..25. Empty/non-hex fields give no access,
  same rule as the P3 loader, so per-table access counts equal P3's (tested).
- Key = table << 32 | id, i.e. (table, id); ids wider than 32 bits are rejected.
- Policies (classes imported unchanged from run_trace_sim.py): LRU, LFU reset-on-eviction (gem5 LFURP),
  LFU persistent counters, ARC, W-TinyLFU (Count-Min). Capacities 256, 1000, 10000, 100000 vectors total.
- Output JSON: totals plus per-table hits/misses for every (policy, capacity).

## Tests
- `tests/test_shared_cache.py`: 16 tests (row order, table qualification, empty fields, row limit, LRU vs an
  independent reference incl. per-table hits, compulsory-miss-only at huge capacity, single-table run equals the
  per-table simulator for all 5 policies, parallel == serial, per-result CSV parts). Full suite: 56 tests OK (`unittest.txt`).
- Mutation: `tools/mutate_shared.py` 10/10 caught (`mutation.txt`); existing `tools/mutate_policies.py` still 16/16.

## Timing: 200k synthetic rows, 1 worker (`timing_200k/`)
- 4,940,119 accesses, 178,120 unique keys. Sweep 124.3 s wall, 124.12 s CPU summed over 20 jobs; peak RSS 142032 kB.
- Slowest jobs: W-TinyLFU 23.70 s (256), 21.14 s (1000); LRU 1.52..1.94 s (`shared_200k_synthetic.json`).

## ESTIMATE for real Criteo 2M (not measured)
- Real 2M has 46,128,690 accesses (`results/P3/rows_2000000/dump_log.txt`): 9.34x the synthetic run.
- Linear scaling: ~1159 s CPU total, longest single job ~221 s; with 4 workers about 5 min wall plus parsing
  (P3 dump parsed 2M rows in 16.9 s). Real data has 2,293,344 unique (table, id) keys (sum of `unique` in
  `results/P3/rows_2000000/figs/zipf_per_table.csv`), 12.9x the synthetic count, so bigger dicts may run slower than linear.
- Memory: 142032 kB x 9.34 x 5 processes = ~6.6 GB upper estimate.

## Job (approved with 2 h limit; each policy/capacity saved to parts/*.csv on completion)
| job | rows | tasks | CPUs | mem | time limit | depends on |
|---|---|---|---|---|---|---|
| p3b_shared (`cluster/jobs/p3b_shared.sbatch`) | 2M | 1 | 4 | 16G | 02:00:00 | none |
Submit with `cluster/p3b_driver.sh` (rsync, one sbatch, no wait). No dump step: it parses train.txt itself.
