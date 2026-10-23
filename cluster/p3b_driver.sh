#!/bin/bash
# P3b driver (run locally): sync repo, submit ONE shared-cache job for 2M rows.
# Submits and returns; it does not wait. When the job is done, copy back with:
#   rsync -a rahulkmr@hpc.bits-hyderabad.ac.in:/scratch/rahulkmr/Adarsh/results/P3b/ results/P3b/
set -euo pipefail
H=rahulkmr@hpc.bits-hyderabad.ac.in
W=/scratch/rahulkmr/Adarsh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ssh -o BatchMode=yes "$H" "mkdir -p $W/repo $W/logs $W/results/P3b"
rsync -a --delete --exclude .git --exclude .venv --exclude results "$ROOT/" "$H:$W/repo/"
ssh -o BatchMode=yes "$H" bash -l -s <<REMOTE
set -e
cd $W/repo/cluster/jobs
j=\$(sbatch --parsable --export=ALL,N_ROWS=2000000 p3b_shared.sbatch)
echo "rows=2000000 shared=\$j" | tee -a $W/results/P3b/jobs.txt
squeue -u rahulkmr -o "%.10i %.10P %.12j %.3t %.10l %.6C %.8m %r" | head -n 5
REMOTE
