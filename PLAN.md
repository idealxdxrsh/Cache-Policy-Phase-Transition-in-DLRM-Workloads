# PLAN.md: phases for Claude Code

Rules: see CLAUDE.md. One phase per session. Each phase ends with results/<phase>/SUMMARY.md (<40 lines), a git commit, then STOP.

## P0 Setup (about 10 min)
- `ssh -O check sharanga`; `sinfo -o "%P %G %D %t"` to list partitions and GPU types (find the H200 one).
- Check scratch path, quota, modules/conda availability.
- Output: results/P0/SUMMARY.md.

## P1 RTL fix (local, no cluster)
- Add parameter `COUNTER_MODE` to rtl/v2: 0 = count set to 1 on install (default); 1 = current v2 (slot keeps count); 2 = address-indexed history, only if Prof. Mane decides.
- Run all tests for each mode.
- Add a mutation script proving the testbench FAILS on broken copies (stale victim, double increment).

## P2 Bootstrap (cluster)
- Idempotent `cluster/bootstrap.sh` using `cluster/environment.yml`.
- Criteo download as a batch job, only after the user places the Kaggle token by hand (never read it).
- Verify row count and that columns 14..39 are hex.

## P3 Trace sim at RTL scale (cluster, CPU)
- Capacities (vectors): 64, 128, 256, 512, 1k, 2k, 5k, 10k, 20k, 50k, 100k.
- Policies: LRU, LFU per-address history, LFU reset-on-eviction, real Count-Min TinyLFU, ARC, optional Belady.
- Add tests/test_policies.py first.
- Run 2M rows, then 10M. Report per-table results and the Zipf exponent per table.
- State plainly whether LFU beats LRU at 256 vectors (about 4 KB), far below the gem5 crossover.

## P4 GPU profiling (H100 and H200)
- Write profile_embedding.py with nn.EmbeddingBag: uniform and Zipf (alpha 0.6, 0.85, 1.1) and Criteo-hashed indices; table rows 1e6 and 1e7; dim 64 and 128; batch 64..8192; about 26 tables.
- CUDA events, 20 warmup, 100 timed. Nsight Compute counters after `ncu --query-metrics`.
- Record `nvidia-smi -q` and library versions.
- Do not use the word "stall" without counter support.

## P5 Synthesis with an open PDK (local)
- NanGate45 liberty + OpenSTA; depths 16, 64, 256; every COUNTER_MODE; targets 1 GHz and 500 MHz.
- Label as "NanGate45, not TSMC". No power numbers unless a power step is run.

## P6 gem5 (optional)
- Write bench/zipf_embedding.cpp (static binary, validated first).
- L2 256 kB..2 MB array job; record the gem5 commit hash.

## P7 Consolidate
- tools/make_tables.py -> TABLES.md. CLAIMS.md maps every claim to a source file or "unsupported".
- README edits as a diff. Do not touch paper/ and do not push without asking.
