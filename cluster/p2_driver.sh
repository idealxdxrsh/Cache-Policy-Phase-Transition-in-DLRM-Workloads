#!/bin/bash
# P2 driver (run locally): sync repo, submit bootstrap -> download -> verify chain,
# block on the last job (sbatch --wait, no polling), copy results back.
set -euo pipefail
H=rahulkmr@hpc.bits-hyderabad.ac.in
W=/scratch/rahulkmr/Adarsh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ssh -o BatchMode=yes "$H" "mkdir -p $W/repo $W/logs $W/results/P2"
rsync -a --delete --exclude .git --exclude results "$ROOT/" "$H:$W/repo/"
ssh -o BatchMode=yes "$H" bash -l -s <<REMOTE
set -e
cd $W/repo/cluster/jobs
j1=\$(sbatch --parsable p2_bootstrap.sbatch)
j2=\$(sbatch --parsable --kill-on-invalid-dep=yes --dependency=afterok:\$j1 p2_download.sbatch)
echo "jobs: \$j1 \$j2" > $W/results/P2/jobs.txt
sbatch --wait --kill-on-invalid-dep=yes --dependency=afterok:\$j2 p2_verify.sbatch \
    >> $W/results/P2/jobs.txt 2>&1 || echo "verify job failed or rejected (rc=\$?)" >> $W/results/P2/jobs.txt
sacct -S today -n -X --name=p2_boot,p2_dl,p2_verify -o JobID,JobName,State,ExitCode,Elapsed >> $W/results/P2/jobs.txt
REMOTE
mkdir -p "$ROOT/results/P2"
rsync -a "$H:$W/results/P2/" "$ROOT/results/P2/"
