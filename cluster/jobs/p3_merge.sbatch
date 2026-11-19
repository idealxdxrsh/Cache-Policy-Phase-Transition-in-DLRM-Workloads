#!/bin/bash -l
#SBATCH -J p3_merge
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH --mem=4G
#SBATCH -t 00:30:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# Merge the 26 per-table parts, then write figures + CSV tables.
# Submit with: sbatch --export=ALL,N_ROWS=2000000 p3_merge.sbatch
set -euo pipefail
# Env check: fail at once if the env lost files (scratch purge 2026-11-17 broke jobs 456795-7; rebuild:
# cluster/jobs/env_rebuild.sbatch).
/scratch/rahulkmr/Adarsh/envs/dlrm_cache/bin/python -I -c 'import enum, numpy' || { echo "ENV CHECK FAILED: /scratch/rahulkmr/Adarsh/envs/dlrm_cache/bin/python cannot import enum, numpy (env damaged or purged)" >&2; exit 3; }
W=/scratch/rahulkmr/Adarsh
: "${N_ROWS:?set N_ROWS}"
OUT=$W/results/P3/rows_$N_ROWS
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
python -I "$W/repo/trace_sim/merge_results.py" --expect_tables 26 \
    --output "$OUT/trace_sim_results.json" "$OUT"/parts/table_*.json
python -I "$W/repo/trace_sim/plot_trace_results.py" \
    --results "$OUT/trace_sim_results.json" --output "$OUT/figs" > "$OUT/plot_log.txt"
