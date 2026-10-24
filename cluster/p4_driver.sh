#!/bin/bash
# P4 driver (run locally): sync repo, then submit env install (CPU) -> H100 -> H200,
# chained with afterok, one GPU per job. Submits and returns; it does not wait.
# Copy back with: rsync -a rahulkmr@hpc.bits-hyderabad.ac.in:/scratch/rahulkmr/Adarsh/results/P4/ results/P4/
set -euo pipefail
H=rahulkmr@hpc.bits-hyderabad.ac.in
W=/scratch/rahulkmr/Adarsh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ssh -o BatchMode=yes "$H" "mkdir -p $W/repo $W/logs $W/results/P4"
rsync -a --delete --exclude .git --exclude .venv --exclude results "$ROOT/" "$H:$W/repo/"
ssh -o BatchMode=yes "$H" bash -l -s <<REMOTE
set -e
cd $W/repo/cluster/jobs
s="sbatch --parsable --kill-on-invalid-dep=yes"
e=\$(\$s p4_env.sbatch)
a=\$(\$s -p gpu_h100_4 --dependency=afterok:\$e --export=ALL,GPU_LABEL=h100 p4_profile.sbatch)
b=\$(\$s -p gpu_h200_8 --dependency=afterok:\$a --export=ALL,GPU_LABEL=h200 p4_profile.sbatch)
echo "env=\$e h100=\$a h200=\$b" | tee -a $W/results/P4/jobs.txt
squeue -u rahulkmr -o "%.10i %.12P %.12j %.3t %.10l %.6C %.8m %.14b %.20E" | head -n 6
REMOTE
