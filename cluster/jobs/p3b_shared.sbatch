#!/bin/bash -l
#SBATCH -J p3b_shared
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH --mem=16G   # 200k synthetic peak 142032 kB x 9.34 (accesses) x 5 processes = ~6.6 GB upper estimate
#SBATCH -t 01:00:00 # estimate: ~1159 s CPU total, longest single job ~221 s, ~5 min wall on 4 workers
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# One cache SHARED by all 26 tables: LRU, both LFUs, ARC, W-TinyLFU at
# 256/1000/10000/100000 vectors, parsed straight from Criteo train.txt in row order.
# Submit with: sbatch --export=ALL,N_ROWS=2000000 p3b_shared.sbatch
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
: "${N_ROWS:?set N_ROWS}"
EXT=$W/data/criteo/extracted
OUT=$W/results/P3b/rows_$N_ROWS; mkdir -p "$OUT"
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
TRAIN=$(find "$EXT" -type f \( -name 'train.txt' -o -name 'train.csv' \) | head -n 1)
[ -n "$TRAIN" ] || { echo "no train.txt/train.csv under $EXT" | tee "$OUT/error.txt"; exit 1; }
# GNU time is missing on some compute nodes (node6, job 412923: exit 127)
python -I "$W/repo/tools/timev.py" python -I "$W/repo/trace_sim/run_shared_cache.py" \
    --criteo_path "$TRAIN" --n_rows "$N_ROWS" --workers "$SLURM_CPUS_PER_TASK" \
    --output "$OUT" --tag shared_cache_results \
    > "$OUT/log.txt" 2> "$OUT/time.txt"
