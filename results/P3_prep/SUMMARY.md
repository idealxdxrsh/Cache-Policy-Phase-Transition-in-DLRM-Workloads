# P3 prep (offline, no cluster job submitted): summary (2026-10-23)

All data here is SYNTHETIC (tools/gen_synthetic_criteo.py). Its hit rates are smoke tests only, not results.
Local machine: 12 cores, Python 3.12.3. Venv `.venv/` (gitignored), numpy 1.26.4, matplotlib 3.8.4 (`venv_freeze.txt`).

## Code (trace_sim/, tools/, tests/)
- Policies: LRU, LFU per-address history, LFU reset-on-eviction, TinyLFU-exact, W-TinyLFU with a
  Count-Min sketch, ARC, plus optional Belady MIN (`--belady`; offline, demand-fetch, no bypass).
- Capacities: 64..100k vectors (1k = 1000), one cache per table. Results JSON now has a `per_table`
  list per policy and capacity, plus `tables` with the Zipf alpha per table
  (log-log OLS of count on rank, ranks with count >= 5).
- Array path: `--dump_traces` (per-table uint32 files), `--trace_dir --tables N`, `merge_results.py`.
- plot_trace_results.py: draws every policy present, including ARC, TinyLFU-exact and Belady.
  Adds per-table small multiples, a Zipf bar chart, and hit_rates.csv / zipf_per_table.csv.
- Tests: 40 run, OK (`unittest.txt`). Mutation check: 16/16 mutants caught (`mutation.txt`).
  One test checks that merging the array parts gives exactly the single-run result.
- Plot run: `timing_200k/figs/`, `timing_2M/merged/figs/` (merge + plot of all 26 parts, rc 0).

## Timing: per-table tasks, 7 policies x 11 capacities, 4 workers, one task at a time
| rows | tables timed | wall per task (s) | sum of walls (s) | peak RSS per task | source |
|---|---|---|---|---|---|
| 200k (1 process, all tables) | 26 | 98.16 sweep | n/a | 237760 kB | `timing_200k/` |
| 2M | 26 | 21.66 to 40.67 | 916.97 | 212984 kB | `timing_2M/table_*_time.txt` |
| 10M | 3 (tables 0, 12, 25) | 116.38 / 194.98 / 189.14 | 500.5 | 812976 kB | `timing_10M/` |
- Measured 10M/2M ratio for the same table: 5.37x (t0), 5.02x (t12), 5.13x (t25).
- Dump (parse TSV, write traces): 2M 15.54 s, 10M 77.97 s, peak 980084 kB (`timing_*/dump_time.txt`).
- PROJECTION, not measured: all 26 tables at 10M run one after another would take 26 x (116.38..194.98 s)
  = 3025.88..5069.48 s. Real Criteo has far more unique ids per table than this synthetic data
  (table 25 at 10M: 96,023 unique), so real-data time and memory are unknown until the 2M job runs.

## Decision: sbatch array (one task per table)
- Pure Python is fine per table. One all-tables process at 10M would need every trace as Python
  ints at once (peak 812976 kB for one table here), so the work is split per table.
- `cluster/jobs/p3_dump.sbatch` (8G, 1h) -> `p3_table.sbatch` (`--array=0-25`, 4 CPUs, 16G, 2h)
  -> `p3_merge.sbatch` (merge with --expect_tables 26, then plot). `cluster/p3_driver.sh` chains 2M and
  then 10M with afterok and blocks with `sbatch --wait`. Limits are a margin over synthetic data.
  The driver is NOT run yet: it needs P2 (Criteo on scratch) first. It uses CPU only, no GPU.

## Still open
- Per-table numbers on real Criteo, and whether LFU beats LRU at 256 vectors: needs the cluster run.
