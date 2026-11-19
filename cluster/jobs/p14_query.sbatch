#!/bin/bash -l
#SBATCH -J p14_query
#SBATCH -p gpu_h100_4
#SBATCH -w gpunode6
#SBATCH -N 1 -n 1 -c 1
#SBATCH --mem=1G
#SBATCH -t 00:03:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# P14: list the GH100 L2 (lts__) metric names that this node's ncu knows (no GPU needed:
# --query-metrics --chip gh100). Used to pick raw hit/miss sector counters for the main run.
set -eo pipefail
# Env check: fail at once if the env lost files (scratch purge 2026-11-17 broke jobs 456795-7; rebuild:
# cluster/jobs/env_rebuild.sbatch).
/scratch/rahulkmr/Adarsh/envs/p4_torch/bin/python -I -c 'import enum, numpy, torch' || { echo "ENV CHECK FAILED: /scratch/rahulkmr/Adarsh/envs/p4_torch/bin/python cannot import enum, numpy, torch (env damaged or purged)" >&2; exit 3; }
OUT=/scratch/rahulkmr/Adarsh/results/P14/query_$SLURM_JOB_ID; mkdir -p "$OUT"
NCU=/usr/local/cuda/bin/ncu
"$NCU" --version > "$OUT/ncu_version.txt" 2>&1
"$NCU" --query-metrics --chip gh100 > "$OUT/query_metrics_gh100.txt" 2>&1
"$NCU" --query-metrics --chip gh100 --query-metrics-mode suffix --metrics lts__t_sectors_op_read_lookup_hit,lts__t_sectors_lookup_hit,lts__t_sector_hit_rate > "$OUT/query_suffix.txt" 2>&1 || true
