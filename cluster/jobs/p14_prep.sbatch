#!/bin/bash -l
#SBATCH -J p14_prep
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH --mem=16G        # raw ids 2M x 26 int64 = 416 MB, plus one table's dump at a time
#SBATCH -t 01:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# Row-aligned Criteo stream (first 2M rows) for P14, checked against the P3 dumps (tools/p14_prep_stream.py).
set -euo pipefail
# Env check: fail at once if the env lost files (scratch purge 2026-11-17 broke jobs 456795-7; rebuild:
# cluster/jobs/env_rebuild.sbatch).
/scratch/rahulkmr/Adarsh/envs/dlrm_cache/bin/python -I -c 'import enum, numpy' || { echo "ENV CHECK FAILED: /scratch/rahulkmr/Adarsh/envs/dlrm_cache/bin/python cannot import enum, numpy (env damaged or purged)" >&2; exit 3; }
W=/scratch/rahulkmr/Adarsh
OUT=$W/data/p14/rows_2000000; mkdir -p "$OUT" "$W/results/P14/prep"
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
TRAIN=$(find "$W/data/criteo/extracted" -type f \( -name 'train.txt' -o -name 'train.csv' \) | head -n 1)
[ -n "$TRAIN" ] || { echo "no train.txt/train.csv" | tee "$W/results/P14/prep/error.txt"; exit 1; }
python -I "$W/repo/tools/timev.py" python -I "$W/repo/tools/p14_prep_stream.py" \
    --criteo_path "$TRAIN" --dump_dir "$W/data/p3/traces_2000000" --n_rows 2000000 --out "$OUT" \
    > "$W/results/P14/prep/log.txt" 2> "$W/results/P14/prep/time.txt"
cp "$OUT/check.json" "$W/results/P14/prep/check.json"
