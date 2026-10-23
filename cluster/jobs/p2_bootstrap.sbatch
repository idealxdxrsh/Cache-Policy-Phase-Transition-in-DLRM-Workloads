#!/bin/bash -l
#SBATCH -J p2_boot
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH -t 01:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
OUT=$W/results/P2; mkdir -p "$OUT"
{ echo "host $(hostname)"; date -Is; } > "$OUT/bootstrap.txt"
# Compute-node internet check (bootstrap and download both need it)
curl -sS -o /dev/null -w "kaggle.com HTTP %{http_code}\n" --max-time 20 https://www.kaggle.com >> "$OUT/bootstrap.txt"
# Full log kept separately (conda prints its traceback first); summary gets the tail
rc=0
bash "$W/repo/cluster/bootstrap.sh" > "$OUT/bootstrap_full.log" 2>&1 || rc=$?
tail -n 15 "$OUT/bootstrap_full.log" >> "$OUT/bootstrap.txt"
echo "bootstrap.sh rc=$rc" >> "$OUT/bootstrap.txt"
exit $rc
