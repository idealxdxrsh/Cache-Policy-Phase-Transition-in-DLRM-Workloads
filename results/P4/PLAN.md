# P4 plan: EmbeddingBag vs MLP timing on H100 and H200 (nothing submitted yet)

## Cluster facts (checked 2026-10-24, login node, read-only)
- `sinfo`: `gpu_h100_4` = gpunode[5-6], 4x `nvidia_h100_80gb_hbm3` each, MaxTime 3 days.
  `gpu_h200_8` = gpunode7, 8x `nvidia_h200_nvl`, MaxTime 1 day. Both were "mixed" (partly in use).
- ncu: not on PATH, but module `cuda-11.8.0-gcc-8.5.0-o55wffj` provides it: `ncu --version` = 2022.3.0.0
  (Nsight Compute 2022.3.0). `/opt/nvidia/nsight-compute` is empty. Whether this ncu can read counters on
  H100/H200 with the nodes' driver is unknown; the GPU jobs only record `ncu --version` and `--query-metrics`.
  No counters are collected in this plan, so no claim about why the embedding kernels take the time they do.
- Driver version on the GPU nodes: unknown from the login node; each GPU job records `nvidia-smi -q`.
- Criteo traces for the `criteo` pattern: `/scratch/rahulkmr/Adarsh/data/p3/traces_10000000/table_XX.u32` (635M).
- No torch in `envs/dlrm_cache` (ModuleNotFoundError). /scratch has 163T free (`df -h`).

## Environment (needs approval: this is the install)
- New venv `/scratch/rahulkmr/Adarsh/envs/p4_torch` from the dlrm_cache Python 3.11.17;
  `pip install torch==2.14.1+cu126 numpy==1.26.4` from https://download.pytorch.org/whl/cu126.
  The default PyPI torch 2.14.1 wheel is built for CUDA 13 (`cuda-toolkit==13.0.3`), so the cu126 index is used.
- Download size: torch wheel 869,136,951 bytes (HTTP content-length). With its CUDA 12.6 dependencies
  (cuDNN 674.0 MiB, cuBLAS 374.9 MiB, NCCL 276.3 MiB, cuSPARSELt 273.9 MiB, Triton 236.5 MiB, ...),
  summed from PyPI metadata: about 3.41 GiB. Installed size is not known until installed (`du -sh` is logged).
- Installed in a CPU job (`p4_env`), refuses to run if the env dir already exists. Nothing system-wide.
  `du -sh` of the installed env goes to `results/P4/env_du.txt`.
- GPU job preflight (first step, `preflight.txt`): prints the nvidia-smi driver version, torch.version.cuda and
  torch.cuda.is_available(); exits with PREFLIGHT FAIL (rc 2/3/4) if the driver cannot be read, is older than
  525.60.13 (CUDA 12.x minor-version compatibility minimum), or CUDA is unavailable / a tiny CUDA op fails.
  Tested locally with stub nvidia-smi/python for all of these cases.

## Script `tools/profile_embedding.py`
- Model: 26 x `nn.EmbeddingBag(rows, dim, mode='sum')` -> concat -> MLP 26*dim-512-256-1 (ReLU). fp32,
  inference only (`torch.no_grad`), 1 index per table per sample (Criteo has one id per field).
- Sweep: rows 1e6, 1e7; dim 64, 128; batch 64, 128, ..., 8192 (8 values); patterns uniform, zipf0.6,
  zipf0.85, zipf1.1, criteo = 2 x 2 x 8 x 5 = 160 configs per GPU. 20 warmup + 100 timed iterations,
  a fresh index batch for every iteration.
- Zipf: ranks from the continuous inverse CDF of r^-alpha on 1..rows, mapped to ids by a bijection
  (r-1)*1000003 + 7919*table mod rows. Criteo: consecutive ids from the 10M per-table dumps, id mod rows
  (hashing many raw ids onto one row); per-table traces skip empty fields, so table t batch k is not the
  same Criteo rows as table t' batch k.
- Timing: 3 CUDA events per iteration (before embeddings, between, after MLP). Reported per config:
  p10/median/p90 of embedding ms and MLP ms, median embedding share = emb/(emb+mlp), CPU wall ms per
  iteration (if it is close to the GPU time, the run is launch-bound: 26 separate EmbeddingBag kernels),
  and `emb_lookup_GBps` = 26*batch*dim*4 bytes / median embedding time. That is useful bytes per second,
  NOT measured DRAM traffic. The embedding share is a measured time share, not a proof of memory-boundedness.
- Memory: a (rows, dim) model is skipped, and logged as `skipped`, when weights + indices + 2 GiB exceed
  `torch.cuda.mem_get_info` free memory. 1e7 x 128 weights are 26*1e7*128*4 = 133,120,000,000 bytes, more
  than an 80 GB H100, so expect it to run on H200 only; the decision is made at run time.
- Recorded: `env.json` (torch, torch CUDA, cuDNN, GPU name/capability/memory, driver via nvidia-smi query),
  `nvidia_smi_q.txt`, `nvidia_smi.txt`, `ncu_query_metrics.txt`, `results.csv` (flushed after every config),
  `time.txt` (wall, peak RSS via tools/timev.py).

## Tests (CPU, tiny sizes; scratch venv with torch 2.14.1+cpu, numpy 1.26.4)
- `tests/test_profile_embedding.py`: 9 tests OK (`results/P4/cpu_test.txt`): index ranges, Zipf slope within
  0.1 of alpha (0.6, 0.85, 1.1), bijection, Criteo order/modulo/wrap, pooled sum equals manual sum,
  end-to-end CLI on CPU for all 5 patterns. Main suite in `.venv` (no torch): 65 run OK, 9 skipped.
- CPU smoke run: `results/P4/cpu_smoke/` (CPU perf_counter times, not GPU results).
- Index generation at full size on the local CPU: 12.38 s for all synthetic configs (`index_gen_timing.txt`).

## Job list (driver `cluster/p4_driver.sh`, afterok chain, no waiting)
| # | job | partition | GPUs | CPUs | mem | time limit | depends on |
|---|---|---|---|---|---|---|---|
| 1 | p4_env (`cluster/jobs/p4_env.sbatch`) | compute | 0 | 4 | 8G | 01:00:00 | none |
| 2 | p4_profile, GPU_LABEL=h100 | gpu_h100_4 | 1 | 8 | 32G | 01:00:00 | afterok 1 |
| 3 | p4_profile, GPU_LABEL=h200 | gpu_h200_8 | 1 | 8 | 32G | 01:00:00 | afterok 2 |
- At most 1 GPU at a time and at most 2 GPU-hours in total (two 1 h limits).
- Outputs: `/scratch/rahulkmr/Adarsh/results/P4/{h100,h200}_<jobid>/`; job ids in `results/P4/jobs.txt`.
