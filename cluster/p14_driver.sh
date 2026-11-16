#!/bin/bash
# P14 prep driver (run locally): sync repo, submit the counter smoke test on one H100 GPU, then the
# same job on one H200 GPU chained with afterok (the H100 job exits non-zero unless ncu returned
# counter values, and --kill-on-invalid-dep cancels the H200 job then). Each job: 1 GPU, 4 CPUs, 10 min.
# H200 partition from `sinfo` on 2026-11-16: gpu_h200_8 (nvidia_h200_nvl).
# The final sbatch uses --wait, so this script blocks until the H200 job ends or is cancelled; no polling.
# Copy back with: rsync -a rahulkmr@hpc.bits-hyderabad.ac.in:/scratch/rahulkmr/Adarsh/results/P14/ results/P14/
# ONLY=h200 ./cluster/p14_driver.sh submits only the H200 job (used after job 453624, whose script misread the ncu log).
set -euo pipefail
ONLY=${ONLY:-}
H=rahulkmr@hpc.bits-hyderabad.ac.in
W=/scratch/rahulkmr/Adarsh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ssh -o BatchMode=yes "$H" "mkdir -p $W/repo $W/logs $W/results/P14"
rsync -a --delete --exclude .git --exclude .venv --exclude results "$ROOT/" "$H:$W/repo/"
ssh -o BatchMode=yes "$H" bash -l -s <<REMOTE
set -e
cd $W/repo/cluster/jobs
s="sbatch --parsable --kill-on-invalid-dep=yes"
if [ "$ONLY" = h200 ]; then
  a=\$(\$s -p gpu_h200_8 --export=ALL,GPU_LABEL=h200 p14_smoke.sbatch); b=\$a
  echo "h200=\$a (alone)" | tee -a $W/results/P14/jobs.txt
else
  a=\$(\$s -p gpu_h100_4 --export=ALL,GPU_LABEL=h100 p14_smoke.sbatch)
  echo "h100=\$a" | tee -a $W/results/P14/jobs.txt
  b=\$(\$s -p gpu_h200_8 --dependency=afterok:\$a --export=ALL,GPU_LABEL=h200 p14_smoke.sbatch)
  echo "h200=\$b (afterok:\$a)" | tee -a $W/results/P14/jobs.txt
fi
sbatch --wait --parsable -p compute -c 4 --mem=100M -t 00:01:00 -J p14_wait \
    -o $W/logs/%x_%j.out --dependency=afterany:\$a:\$b --wrap true || true
sacct -j \$a,\$b -X -o JobID,Partition,NodeList,State,ExitCode,Elapsed | tee -a $W/results/P14/sacct.txt
REMOTE
