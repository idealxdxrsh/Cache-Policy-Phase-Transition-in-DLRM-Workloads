# P0 Setup: summary (2026-10-23)

Raw outputs: `results/P0/sinfo.txt`, `results/P0/sinfo_gpu.txt`, `results/P0/env.txt`, `results/P0/env2.txt`.

## Access
- `ssh -O check sharanga` fails: no `sharanga` alias or ControlPath in local ssh config.
- `ssh -o BatchMode=yes rahulkmr@hpc.bits-hyderabad.ac.in` works with keys, no password/OTP prompt.
  Login node: `hpc01.sharanga.local`. Later phases should use this host string (or add an alias).

## GPU partitions (`sinfo_gpu.txt`)
- H200: **`gpu_h200_8`**, node `gpunode7`, `nvidia_h200_nvl` x8, time limit 1-00:00:00.
- H100: `gpu_h100_4`, nodes `gpunode[5-6]`, `nvidia_h100_80gb_hbm3` x4, time limit 3-00:00:00.
- Also present: gpu_v100_1, gpu_v100_2, gpu_a100_8, gpu_rtx_pro_6000_6_csis_hyd (`sinfo.txt`).
- CPU: `compute`, `big_compute` (default), `big_compute_amd_9655`, `big_compute_suryoday`.

## Storage (`env.txt`, `env2.txt`)
- `/scratch/rahulkmr/Adarsh` did not exist; created it in P0 (empty).
- /scratch: 228T size, 164T avail. User usage 74.73G, no block quota (0k), file limit 20000000 (148967 used).

## Software (`env.txt`, `env2.txt`)
- Login-shell default: anaconda3-2023.09, conda 23.7.4, Python 3.11.5, git 2.43.5.
- No `nvcc` or `ncu` on default PATH; must load a module.
- CUDA modules: 9.2.88, 11.6.2, 11.7.1, 11.8.0, 12.1.0 (newest: `cuda-12.1.0-gcc-11.2.0-s5o57xp`).
- nvhpc modules: 22.3, 22.5, 22.9, 23.1. No separate nsight module found by name.
- Existing conda envs include `dlrm1`, `dlrm_h100`, `rtl_sim` (contents not inspected).

## Open items for later phases
- Whether `ncu` ships inside a CUDA/nvhpc module (or a PyTorch-bundled CUDA) is unverified: check in P4.
- CUDA 12.1 module may be too old for H200 driver/ncu support; check `nvidia-smi` on gpunode7 in P4.
- PLAN.md's `sharanga` alias should be updated to the real host string.
