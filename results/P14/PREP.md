# P14 prep: nsys / ncu on Sharanga, and whether GPU hardware counters work (2026-11-16)
Driver `cluster/p14_driver.sh`, job `cluster/jobs/p14_smoke.sbatch` (1 GPU, 4 CPUs, 16G, 10 min), workload
`profiling/p14_smoke.py`: one EmbeddingBag(1,000,000 x 128, fp32, sum), 1,000 bags of 1 uniform lookup (seed 0),
one warmup call, one profiled call (`ncu --profile-from-start off --metrics lts__t_sector_hit_rate.pct,dram__bytes_read.sum`).
Env p4_torch (venv on the dlrm_cache interpreter), torch 2.14.1+cu126 (`<job>/plain.txt`). H200 partition from `sinfo`: gpu_h200_8.

## Jobs (`jobs.txt`, `sacct.txt`); GPU time used 00:04:04 in total
| job | partition / node | GPU (`nvidia_smi_query.csv`) | sacct | `status.txt` |
|---|---|---|---|---|
| 453624 | gpu_h100_4 / gpunode6 | NVIDIA H100 80GB HBM3, driver 580.126.20 | FAILED 5:0, 00:01:57 | COUNTERS=OTHER_FAILURE (wrong, see below) |
| 453625 | gpu_h200_8 | - | CANCELLED (afterok on 453624 never met) | - |
| 453629 | gpu_h200_8 / gpunode7 | NVIDIA H200 NVL, driver 580.126.20 | FAILED 5:0, 00:02:07 | COUNTERS=ERR_NVGPUCTRPERM |

## Counters
- H100 (gpunode6): counters WORK. `h100_453624/ncu_log.txt`, kernel `EmbeddingBag_updateOutputKernel_sum_mean<float, long>`,
  grid (1024,1,1), block (32,8,1): `dram__bytes_read.sum` 556,544 byte; `lts__t_sector_hit_rate.pct` 74.27 %.
  Its status.txt says OTHER_FAILURE because that job's script looked for the metric rows only in `ncu.csv`; with
  `--log-file`, ncu writes them to `ncu_log.txt`. Fixed in the script before 453629; 453624 was not rerun.
- H200 (gpunode7): counters DO NOT WORK. `h200_453629/ncu_log.txt`: "==ERROR== ERR_NVGPUCTRPERM - The user does not
  have permission to access NVIDIA GPU Performance Counters on the target device 0"; ncu rc=1.
- Driver parameter `RmProfilingAdminOnly` (`<job>/tools.txt`, /proc/driver/nvidia/params): 0 on gpunode6, 1 on gpunode7.
  Consistent with P4 (`results/P4/SUMMARY.md`: ERR_NVGPUCTRPERM on gpunode7). Enabling counters on gpunode7 needs the cluster admins.
- Checksums: 453624 seeded only the indices, so plain and ncu runs differ (354.449299 vs -318.510983); the seed for
  the weights was added before 453629, whose plain and ncu runs agree (-282.260395).

## Tools found
| where | ncu | nsys |
|---|---|---|
| login node, PATH | not found | not found |
| login, module cuda-11.8.0-gcc-8.5.0 | 2022.3.0.0 | 2022.4.2.1 |
| login, module cuda-12.1.0-gcc-11.2.0 | 2023.1.0.0 | 2023.1.2.43 |
| login, module nvhpc-23.1-gcc-11.2.0 | 2022.4.0.0 | 2022.5.1.82 |
| gpunode6 (H100), system installs | 2025.1.1.0 (/usr/local/cuda[-12.8], /opt/nvidia/nsight-compute) | 2024.6.2.225 (/usr/local/bin, /usr/local/cuda[-12.8], /opt) |
| gpunode7 (H200), system installs | 2025.1.1.0 (same paths) | 2025.6.3.343 (/usr/local/bin, /opt); /usr/local/cuda/bin/nsys errors "Nsight Systems 2024.6.2 hasn't been installed" |
- gpunode6: `module` is defined but /usr/share/lmod/lmod/libexec/lmod is missing, so module load does nothing there.
- gpunode7: the cuda-12.1.0 module's ncu reported version 2025.1.1.0 on that node (2023.1.0.0 on the login node); not explained.
- Both jobs used /usr/local/cuda/bin/ncu 2025.1.1.0 (newest found).

## For P14
Counter-based runs (L2 hit rate, DRAM bytes) are possible on the H100 node gpunode6 only; H200 counters need an admin change.
nsys was found but not run. Not measured: anything beyond this one 1,000-lookup kernel.
