# P4 summary: 26 x EmbeddingBag vs MLP on one H100 and one H200 (fp32 inference, pooling 1)
Jobs (`sacct.txt`): env 413620 (00:45:21), H100 413621 gpunode5 (00:01:26), H200 413622 gpunode7 (00:00:59), all COMPLETED 0:0.
Full tables: `RESULTS.md` (from `tools/p4_results.py`); raw: `h100_413621/results.csv`, `h200_413622/results.csv`.

## Ran vs skipped (160 configs per GPU)
- H100: 120 ok, 40 skipped. All 40 skips are rows=1e7, dim=128 (5 patterns x 8 batches): one memory check,
  "needs 135471955968 bytes incl. margin, free 84260356096" (weights 26*1e7*128*4 B do not fit in 80 GB). Expected in PLAN.md.
- H200: 160 ok, 0 skipped.
- Run time vs work: profile wall 0:29.39 (H100) and 0:19.45 (H200) (`<gpu>/time.txt`). Timed iterations alone sum to
  7.0062 s and 6.4461 s (`RESULTS.md`); the rest is warmup, index generation and model init. Each iteration is short
  (median embedding <= 0.5063 ms), so the short total is consistent with the work, not a sign of missing configs.

## Versions and env (`env_install.txt`, `env_du.txt`, `<gpu>/env.json`, `<gpu>/nvidia_smi_q.txt`)
- Both nodes: driver 580.126.20 (nvidia-smi "CUDA Version 13.0"); torch 2.14.1+cu126, torch.version.cuda 12.6,
  cuDNN 91002, Python 3.11.17, numpy 1.26.4. GPUs: NVIDIA H100 80GB HBM3, NVIDIA H200 NVL (both capability 9.0).
- Env size: 4.6G `/scratch/rahulkmr/Adarsh/envs/p4_torch`; wheel cache 3.5G `/scratch/rahulkmr/Adarsh/wheels/p4_cu126`.
- ncu (`<gpu>/ncu_query_metrics.txt`): gpunode5 has no lmod ("ncu: command not found", rc 127). gpunode7: ncu 2025.1.1.0,
  `--query-metrics` failed with ERR_NVGPUCTRPERM (no permission for GPU performance counters). No counters exist for P4.

## Launch-bound configs (criterion: CPU wall/iter within 5% of the batch-64 wall, same rows/dim/pattern)
- H100: dim 128 at B <= 2048 (all cells); dim 64 at B <= 512 (all cells), and most cells at 1024-4096, where the wall
  (0.5438-0.5865 ms) sits near the 5% cut. Not launch-bound: dim 128 at 4096/8192, dim 64 at 8192. L cells: wall 0.5223-0.5709 ms.
- H200: dim 64 at B <= 1024, dim 128 at B <= 512 (all cells). L cells: wall 0.2586-0.2771 ms.
- In these cells, the embedding ms is about the same for rows 1e6 and 1e7, and for every index pattern (spread tables in
  `RESULTS.md`, e.g. H100 dim 64 B=64: 0.4134-0.4256 ms over both row counts and 5 patterns). The time is set by the CPU
  issuing the ops (26 separate EmbeddingBag calls, a cat, the MLP layers), not by the lookups. So the embedding share there
  (H100 0.5261-0.8112, H200 0.4434-0.7888) is the share of launch time, not lookup cost. Consistent with the CLAUDE.md note on the earlier run.
- "CPU wall" is the launch loop over 100 iterations plus one final synchronize, divided by 100. It is not a pure launch
  time: no per-op CPU timing was recorded.

## Embedding share outside the launch-bound cells (median emb/(emb+mlp))
- H100 B=8192: 0.4224-0.4553. H200 non-L cells: 0.4024-0.4970; B=8192: 0.4024-0.4358. At the largest batches the MLP
  takes longer than the 26 embeddings on both GPUs (e.g. H200 1e7/128/uniform B=8192: emb 0.5063 ms, MLP 0.6843 ms).
- Rows 1e6 vs 1e7: no visible change at any batch (both GPUs, `RESULTS.md` tables).
- Dim: 128 leaves the launch-bound region at a smaller batch than 64 (H200: 1024 vs 2048; H100: 4096 vs 8192, dim 64 borderline from 1024).
- Index pattern: the effect is small and shows only at large batches. At B=8192, criteo is lowest and uniform/zipf0.6
  highest, e.g. H200 1e7/128: 0.4616-0.5063 ms; H100 1e6/128: 0.4542-0.5004 ms. Zipf 1.1 sits between them.
- No conclusion here about memory-boundedness, cache behaviour or DRAM traffic: there are no counters, and
  `emb_lookup_GBps` counts useful bytes only.
