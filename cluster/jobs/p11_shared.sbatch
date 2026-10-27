#!/bin/bash -l
#SBATCH -J p11_shared
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# P11 part A: shared-cache trace simulator (P3b stream and order: run_shared_cache.py, unchanged loader, as P9) with
# LRU, LFU-reset (oldest) = LFUResetCache, RTL-exact mode 0 (v2 rule) and Rotate-victim mode 0 (v3 rule) at 16, 64
# and 256 entries. 256 is a reproduction check only (tools/p11_check_ref.py: must equal P3b / P9 exactly); a
# mismatch fails this job, so the afterok 10M job is cancelled (--kill-on-invalid-dep=yes in cluster/p11_driver.sh).
# Submit with: sbatch --export=ALL,N_ROWS=2000000 p11_shared.sbatch
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
: "${N_ROWS:?set N_ROWS}"
POL=("LRU" "LFU (gem5 LFURP — reset on eviction)" "RTL-exact mode 0" "Rotate-victim mode 0")
EXT=$W/data/criteo/extracted
OUT=$W/results/P11/rows_${N_ROWS}; mkdir -p "$OUT"
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
TRAIN=$(find "$EXT" -type f \( -name 'train.txt' -o -name 'train.csv' \) | head -n 1)
[ -n "$TRAIN" ] || { echo "no train.txt/train.csv under $EXT" | tee "$OUT/error.txt"; exit 1; }
python -I "$W/repo/tools/timev.py" python -I "$W/repo/trace_sim/run_shared_cache.py" \
    --criteo_path "$TRAIN" --n_rows "$N_ROWS" --workers "$SLURM_CPUS_PER_TASK" --capacities 16 64 256 \
    --output "$OUT" --tag shared_cache_results --policies "${POL[@]}" \
    > "$OUT/log.txt" 2> "$OUT/time.txt"
python -I "$W/repo/tools/p11_check_ref.py" "$OUT/shared_cache_results.json" "$W/repo/p11_ref/rows_$N_ROWS" \
    > "$OUT/ref_check.txt"
