#!/bin/bash -l
#SBATCH -J p3_dump
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH --mem=8G
#SBATCH -t 01:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# Parse the first N_ROWS rows of Criteo train.txt once and write the 26
# categorical columns as per-table uint32 traces for the p3_table array.
# Submit with: sbatch --export=ALL,N_ROWS=2000000 p3_dump.sbatch
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
: "${N_ROWS:?set N_ROWS}"
EXT=$W/data/criteo/extracted
TR=$W/data/p3/traces_$N_ROWS
OUT=$W/results/P3/rows_$N_ROWS; mkdir -p "$OUT"
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
TRAIN=$(find "$EXT" -type f \( -name 'train.txt' -o -name 'train.csv' \) | head -n 1)
[ -n "$TRAIN" ] || { echo "no train.txt/train.csv under $EXT" | tee "$OUT/dump_error.txt"; exit 1; }
/usr/bin/time -v python -I "$W/repo/trace_sim/run_trace_sim.py" \
    --criteo_path "$TRAIN" --n_rows "$N_ROWS" --dump_traces "$TR" \
    > "$OUT/dump_log.txt" 2> "$OUT/dump_time.txt"
