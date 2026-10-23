#!/bin/bash -l
#SBATCH -J p2_verify
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH -t 02:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
OUT=$W/results/P2
EXT=$W/data/criteo/extracted
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
# Labelled training file only (test file has no label column)
TRAIN=$(find "$EXT" -type f \( -name 'train.txt' -o -name 'train.csv' \) | head -n 1)
[ -n "$TRAIN" ] || { echo "no train.txt/train.csv under $EXT" | tee "$OUT/verify_error.txt"; exit 1; }
{ echo "file $TRAIN"; echo "wc -l: $(wc -l < "$TRAIN")"; head -c 300 "$TRAIN" | head -n 2 | cut -c1-200; } > "$OUT/verify_head.txt"
python -I "$W/repo/cluster/verify_criteo.py" "$TRAIN" "$OUT/verify.json"
