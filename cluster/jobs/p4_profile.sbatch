#!/bin/bash -l
#SBATCH -J p4_profile
#SBATCH -N 1 -n 1 -c 8
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
nvidia-smi -q > "$OUT/nvidia_smi_q.txt" 2>&1
nvidia-smi > "$OUT/nvidia_smi.txt" 2>&1
# ncu from the CUDA 11.8 module (Nsight Compute 2022.3.0): version + metric list only, no profiling.
{ module load cuda-11.8.0-gcc-8.5.0-o55wffj && ncu --version && ncu --query-metrics; } \
    > "$OUT/ncu_query_metrics.txt" 2>&1 || echo "ncu query failed rc=$?" >> "$OUT/ncu_query_metrics.txt"
# GNU time is missing on some compute nodes (node6, job 412923: exit 127)
"$W/envs/p4_torch/bin/python" -I "$W/repo/tools/timev.py" \
    "$W/envs/p4_torch/bin/python" -I "$W/repo/tools/profile_embedding.py" --device cuda --out "$OUT" \
    --criteo_dir "$W/data/p3/traces_10000000" > "$OUT/log.txt" 2> "$OUT/time.txt"
