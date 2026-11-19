#!/bin/bash -l
#SBATCH -J p14_ncu
#SBATCH -p gpu_h100_4
#SBATCH -w gpunode6      # the H100 node where counters worked (P14 prep, job 453624); see results/P14/PREP.md
#SBATCH -N 1 -n 1 -c 4
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# P14: ncu on nn.EmbeddingBag over the real Criteo stream (tools/p14_profile.py), one ncu run per config.
#   sbatch -t 00:15:00 --export=ALL,LABEL=test,BATCHES=2,CONFIGS="per_table:64 concat:16384" p14_ncu.sbatch
# ncu: application replay (each metric pass reruns the whole program, so every pass sees the same cache
# state) and --cache-control none (no L2 flush before kernels: L2 keeps what warmup and earlier kernels left).
# Clocks: ncu default --clock-control base. Exit 0 only if every config produced all metric rows.
set -eo pipefail
# Env check: fail at once if the env lost files (scratch purge 2026-11-17 broke jobs 456795-7; rebuild:
# cluster/jobs/env_rebuild.sbatch).
/scratch/rahulkmr/Adarsh/envs/p4_torch/bin/python -I -c 'import enum, numpy, torch' || { echo "ENV CHECK FAILED: /scratch/rahulkmr/Adarsh/envs/p4_torch/bin/python cannot import enum, numpy, torch (env damaged or purged)" >&2; exit 3; }
W=/scratch/rahulkmr/Adarsh
: "${LABEL:?}" "${BATCHES:?}" "${CONFIGS:?}"
OUT=$W/results/P14/${LABEL}_$SLURM_JOB_ID; mkdir -p "$OUT"
PY=$W/envs/p4_torch/bin/python
STREAM=$W/data/p14/rows_2000000/stream.npz
# Raw L2 lookup counts (names checked with ncu --query-metrics --chip gh100, job 456792): hit rate =
# hit / (hit + miss). Test job 454182 used lts__t_sector*_hit_rate.pct weighted by lts__t_sectors*.sum,
# which is wrong (the rate's denominator is sector lookups, not lts__t_sectors; it gave 100.6 %).
METRICS=lts__t_sectors_lookup_hit.sum,lts__t_sectors_lookup_miss.sum,lts__t_sectors_op_read_lookup_hit.sum,lts__t_sectors_op_read_lookup_miss.sum,dram__bytes_read.sum,gpu__time_duration.sum,sm__warps_active.avg.pct_of_peak_sustained_active
NCU=/usr/local/cuda/bin/ncu
{ echo "node $(hostname) job $SLURM_JOB_ID"; grep -h RmProfilingAdminOnly /proc/driver/nvidia/params || true
  echo "ncu $NCU: $($NCU --version 2>&1 | tail -n 1)"; echo "metrics $METRICS"; echo "batches $BATCHES configs $CONFIGS"; } > "$OUT/env.txt"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$OUT/nvidia_smi_query.csv" 2>&1 || true
fail=0
for cfg in $CONFIGS; do
  mode=${cfg%%:*}; b=${cfg##*:}; D="$OUT/${mode}_b$b"; mkdir -p "$D"
  t0=$(date +%s); rc=0
  "$NCU" --profile-from-start off --replay-mode application --cache-control none --print-units base \
      --metrics "$METRICS" --csv --log-file "$D/ncu.csv" \
      "$PY" -I "$W/repo/tools/p14_profile.py" --stream "$STREAM" --mode "$mode" --batch "$b" \
      --batches "$BATCHES" --out "$D" > "$D/stdout.txt" 2>&1 || rc=$?
  n=$(grep -c '"gpu__time_duration.sum"' "$D/ncu.csv" || true)
  st=OK; grep -q ERR_NVGPUCTRPERM "$D/ncu.csv" && st=ERR_NVGPUCTRPERM
  [ "$rc" = 0 ] && [ "${n:-0}" -gt 0 ] || { [ $st = OK ] && st=FAIL; }
  [ $st = OK ] || fail=1
  echo "$mode b=$b ncu_rc=$rc kernels_with_metrics=$n wall_s=$(( $(date +%s) - t0 )) status=$st" | tee -a "$OUT/status.txt"
done
exit $fail
