#!/bin/bash -l
#SBATCH -J p4_profile
#SBATCH -N 1 -n 1 -c 4   # gpu_h200_8 allows at most 4 CPUs per H200 GPU; same on H100 for comparability
#SBATCH --gres=gpu:1     # one GPU per job
#SBATCH --mem=32G        # host RAM: index tensors <= 205 MB per config, weights live on the GPU
#SBATCH -t 01:00:00      # CPU index generation measured at 12.38 s for all configs (results/P4/index_gen_timing.txt)
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# EmbeddingBag vs MLP timing on one GPU. Partition and label come from the submit line:
#   sbatch -p gpu_h100_4 --export=ALL,GPU_LABEL=h100 p4_profile.sbatch
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
: "${GPU_LABEL:?set GPU_LABEL}"
OUT=$W/results/P4/${GPU_LABEL}_$SLURM_JOB_ID; mkdir -p "$OUT"
PY=$W/envs/p4_torch/bin/python
# Preflight, before any heavy work: driver version, torch CUDA, CUDA available + one tiny op.
# CUDA 12.x minor-version compatibility needs driver >= 525.60.13 (NVIDIA CUDA compatibility guide).
MIN_DRIVER=525.60.13
DRV=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader -i 0 2>&1 | head -n 1) || true
echo "nvidia-smi driver_version: $DRV" | tee "$OUT/preflight.txt"
"$PY" -I -c "import torch; print('torch', torch.__version__, 'torch.version.cuda', torch.version.cuda, 'cuda_available', torch.cuda.is_available())" \
    2>&1 | tee -a "$OUT/preflight.txt" || true
if ! [[ $DRV =~ ^[0-9]+(\.[0-9]+)+$ ]]; then
    echo "PREFLIGHT FAIL: could not read the driver version from nvidia-smi ($DRV)" | tee -a "$OUT/preflight.txt"; exit 2
fi
if [ "$(printf '%s\n%s\n' "$MIN_DRIVER" "$DRV" | sort -V | head -n 1)" != "$MIN_DRIVER" ]; then
    echo "PREFLIGHT FAIL: driver $DRV is older than $MIN_DRIVER, too old for the CUDA 12.6 wheel" | tee -a "$OUT/preflight.txt"; exit 3
fi
if ! "$PY" -I -c "import sys, torch; sys.exit(0 if torch.cuda.is_available() and (torch.ones(1, device='cuda') + 1).item() == 2 else 1)" \
        >> "$OUT/preflight.txt" 2>&1; then
    echo "PREFLIGHT FAIL: torch.cuda.is_available() is False or a tiny CUDA op failed" | tee -a "$OUT/preflight.txt"; exit 4
fi
echo "PREFLIGHT OK" | tee -a "$OUT/preflight.txt"
nvidia-smi -q > "$OUT/nvidia_smi_q.txt" 2>&1
nvidia-smi > "$OUT/nvidia_smi.txt" 2>&1
# ncu from the CUDA 11.8 module (Nsight Compute 2022.3.0): version + metric list only, no profiling.
{ module load cuda-11.8.0-gcc-8.5.0-o55wffj && ncu --version && ncu --query-metrics; } \
    > "$OUT/ncu_query_metrics.txt" 2>&1 || echo "ncu query failed rc=$?" >> "$OUT/ncu_query_metrics.txt"
# GNU time is missing on some compute nodes (node6, job 412923: exit 127)
"$PY" -I "$W/repo/tools/timev.py" \
    "$PY" -I "$W/repo/tools/profile_embedding.py" --device cuda --out "$OUT" \
    --criteo_dir "$W/data/p3/traces_10000000" > "$OUT/log.txt" 2> "$OUT/time.txt"
