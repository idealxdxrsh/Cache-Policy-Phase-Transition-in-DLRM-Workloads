#!/bin/bash
# P3b driver (run locally): sync repo, submit ONE shared-cache job.
#   bash cluster/p3b_driver.sh            # 2M rows (job 413067), sbatch defaults 16G / 2 h
#   bash cluster/p3b_driver.sh 10000000   # 10M rows, --mem=32G, 2 h: 2M peak 633444 kB x 5.02 (accesses)
#     x 5 processes = ~15.2 GB worst case; 2M wall 5:54 x 5.05 (P3 10M/2M) = ~30 min
# Submits and returns; it does not wait. When the job is done, copy back with:
#   rsync -a rahulkmr@hpc.bits-hyderabad.ac.in:/scratch/rahulkmr/Adarsh/results/P3b/ results/P3b/
set -euo pipefail
H=rahulkmr@hpc.bits-hyderabad.ac.in
W=/scratch/rahulkmr/Adarsh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
N=${1:-2000000}
case $N in
    2000000) EXTRA="" ;;
    10000000) EXTRA="--mem=32G" ;;
    *) echo "unsupported row count $N" >&2; exit 1 ;;
esac
ssh -o BatchMode=yes "$H" "mkdir -p $W/repo $W/logs $W/results/P3b"
rsync -a --delete --exclude .git --exclude .venv --exclude results "$ROOT/" "$H:$W/repo/"
ssh -o BatchMode=yes "$H" bash -l -s <<REMOTE
set -e
cd $W/repo/cluster/jobs
j=\$(sbatch --parsable $EXTRA --export=ALL,N_ROWS=$N p3b_shared.sbatch)
echo "rows=$N shared=\$j" | tee -a $W/results/P3b/jobs.txt
squeue -u rahulkmr -o "%.10i %.10P %.12j %.3t %.10l %.6C %.8m %r" | head -n 5
REMOTE
