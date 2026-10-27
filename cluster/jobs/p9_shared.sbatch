#!/bin/bash -l
#SBATCH -J p9_shared
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# P9: shared-cache trace simulator (P3b stream and order: run_shared_cache.py, unchanged loader) with the P9
# policies of trace_sim/rtl_exact.py at 256/1000/10000/100000 entries. Memory and time limits are given at
# submission (cluster/p9_driver.sh; basis in results/P9/jobs/sizing.json).
#   SET=A: RTL-exact modes 0/1, LFU-reset lowest-slot, 6-bit, lowest-slot 6-bit, and LFU reset-on-eviction
#          (LFUResetCache, already in P3b: reproduction check).
#   SET=B: candidate tie-break rules (not in the RTL): Rotate-victim, Rotate-step, Young-bit, modes 0/1.
# Submit with: sbatch --export=ALL,N_ROWS=2000000,SET=A p9_shared.sbatch
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
: "${N_ROWS:?set N_ROWS}"; : "${SET:?set SET (A or B)}"
case $SET in
    A) POL=("LFU (gem5 LFURP — reset on eviction)" "RTL-exact mode 0" "RTL-exact mode 1" "LFU-reset lowest-slot"
            "LFU-reset 6-bit" "LFU-reset lowest-slot 6-bit") ;;
    B) POL=("Rotate-victim mode 0" "Rotate-victim mode 1" "Rotate-step mode 0" "Rotate-step mode 1"
            "Young-bit mode 0" "Young-bit mode 1") ;;
    *) echo "SET must be A or B" >&2; exit 2 ;;
esac
EXT=$W/data/criteo/extracted
OUT=$W/results/P9/rows_${N_ROWS}_set$SET; mkdir -p "$OUT"
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
TRAIN=$(find "$EXT" -type f \( -name 'train.txt' -o -name 'train.csv' \) | head -n 1)
[ -n "$TRAIN" ] || { echo "no train.txt/train.csv under $EXT" | tee "$OUT/error.txt"; exit 1; }
python -I "$W/repo/tools/timev.py" python -I "$W/repo/trace_sim/run_shared_cache.py" \
    --criteo_path "$TRAIN" --n_rows "$N_ROWS" --workers "$SLURM_CPUS_PER_TASK" \
    --output "$OUT" --tag shared_cache_results --policies "${POL[@]}" \
    > "$OUT/log.txt" 2> "$OUT/time.txt"
# Set A: LFUResetCache must reproduce P3b exactly (tools/p9_check_p3b.py); on a mismatch this job fails, so the
# afterok 10M job is cancelled (--kill-on-invalid-dep=yes in cluster/p9_driver.sh).
if [ "$SET" = A ]; then
    python -I "$W/repo/tools/p9_check_p3b.py" "$OUT/shared_cache_results.json" \
        "$W/repo/p3b_ref/rows_$N_ROWS/shared_cache_results.json" > "$OUT/p3b_check.txt"
fi
