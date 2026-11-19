#!/bin/bash -l
#SBATCH -J p14_smoke
#SBATCH -N 1 -n 1 -c 4
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH -t 00:10:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# P14 prep: are nsys / ncu present on the GPU node, and do ncu hardware counters work?
#   sbatch -p gpu_h100_4 --export=ALL,GPU_LABEL=h100 p14_smoke.sbatch
# Exit 0 only if ncu returned counter values (COUNTERS=OK); otherwise exit 5, so a job chained
# with afterok (and --kill-on-invalid-dep=yes) is cancelled.
set -eo pipefail
# Env check: fail at once if the env lost files (scratch purge 2026-11-17 broke jobs 456795-7; rebuild:
# cluster/jobs/env_rebuild.sbatch).
/scratch/rahulkmr/Adarsh/envs/p4_torch/bin/python -I -c 'import enum, numpy, torch' || { echo "ENV CHECK FAILED: /scratch/rahulkmr/Adarsh/envs/p4_torch/bin/python cannot import enum, numpy, torch (env damaged or purged)" >&2; exit 3; }
W=/scratch/rahulkmr/Adarsh
: "${GPU_LABEL:?set GPU_LABEL}"
OUT=$W/results/P14/${GPU_LABEL}_$SLURM_JOB_ID; mkdir -p "$OUT"
PY=$W/envs/p4_torch/bin/python
METRICS=lts__t_sector_hit_rate.pct,dram__bytes_read.sum
T="$OUT/tools.txt"
{
  echo "node $(hostname) job $SLURM_JOB_ID partition $SLURM_JOB_PARTITION"
  echo "lmod: $(type -t module || echo none)"
  echo "RmProfilingAdminOnly: $(grep -h RmProfilingAdminOnly /proc/driver/nvidia/params 2>&1 || true)"
} > "$T"
nvidia-smi > "$OUT/nvidia_smi.txt" 2>&1 || true
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$OUT/nvidia_smi_query.csv" 2>&1 || true

# Candidate ncu / nsys: PATH before any module, system CUDA installs, then the cuda-12.1.0 module.
cands_ncu=(); cands_nsys=()
p=$(command -v ncu 2>/dev/null) && cands_ncu+=("$p")
p=$(command -v nsys 2>/dev/null) && cands_nsys+=("$p")
for f in /usr/local/cuda*/bin/ncu /opt/nvidia/nsight-compute/*/ncu; do [ -x "$f" ] && cands_ncu+=("$f"); done
for f in /usr/local/cuda*/bin/nsys /opt/nvidia/nsight-systems/*/bin/nsys; do [ -x "$f" ] && cands_nsys+=("$f"); done
if [ "$(type -t module)" = function ]; then
  module load cuda-12.1.0-gcc-11.2.0-s5o57xp >> "$T" 2>&1 && echo "module load cuda-12.1.0 returned 0 (see lines above for lmod errors)" >> "$T" || echo "module load failed" >> "$T"
  p=$(command -v ncu 2>/dev/null) && cands_ncu+=("$p")
  p=$(command -v nsys 2>/dev/null) && cands_nsys+=("$p")
fi
best=""; bestv=""
for c in $(printf '%s\n' "${cands_ncu[@]}" | sort -u); do
  v=$("$c" --version 2>&1 | grep -o 'Version [0-9.]*' | head -n 1 | cut -d' ' -f2)
  echo "ncu candidate: $c version ${v:-unknown}" >> "$T"
  if [ -n "$v" ] && { [ -z "$bestv" ] || [ "$(printf '%s\n%s\n' "$bestv" "$v" | sort -V | tail -n 1)" = "$v" ]; }; then best=$c; bestv=$v; fi
done
for c in $(printf '%s\n' "${cands_nsys[@]}" | sort -u); do
  echo "nsys candidate: $c $("$c" --version 2>&1 | tail -n 1)" >> "$T"
done
echo "ncu chosen: ${best:-none} ${bestv}" >> "$T"

S="$OUT/status.txt"
if [ -z "$best" ]; then echo "COUNTERS=NO_NCU" > "$S"; cat "$T" "$S"; exit 5; fi
# The workload alone (no profiler), for the checksum.
"$PY" -I "$W/repo/profiling/p14_smoke.py" > "$OUT/plain.txt" 2>&1 || true
rc=0
"$best" --profile-from-start off --target-processes all --metrics "$METRICS" --csv \
    --log-file "$OUT/ncu_log.txt" "$PY" -I "$W/repo/profiling/p14_smoke.py" \
    > "$OUT/ncu.csv" 2> "$OUT/ncu_stderr.txt" || rc=$?
echo "ncu rc=$rc" >> "$T"
if grep -q ERR_NVGPUCTRPERM "$OUT/ncu.csv" "$OUT/ncu_log.txt" "$OUT/ncu_stderr.txt" 2>/dev/null; then
  echo "COUNTERS=ERR_NVGPUCTRPERM" > "$S"
elif cat "$OUT/ncu.csv" "$OUT/ncu_log.txt" | grep -q '"lts__t_sector_hit_rate.pct"' \
  && cat "$OUT/ncu.csv" "$OUT/ncu_log.txt" | grep -q '"dram__bytes_read.sum"'; then
  # with --log-file, ncu writes its CSV metric rows to ncu_log.txt; ncu.csv holds the program's stdout
  echo "COUNTERS=OK" > "$S"
else
  echo "COUNTERS=OTHER_FAILURE" > "$S"
fi
cat "$T" "$S"
grep -q '^COUNTERS=OK$' "$S" || exit 5
