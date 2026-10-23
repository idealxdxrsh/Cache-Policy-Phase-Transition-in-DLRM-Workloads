#!/bin/bash
# P3 driver (run locally): sync repo, then for 2M and then 10M rows submit
# dump -> 26-task table array (max 6 running) -> merge, chained with afterok
# (the 10M chain starts only after the 2M merge succeeds). The 10M dump gets a
# 2 h limit. Submits and returns; it does not wait. When the jobs are done,
# copy results back with:
#   rsync -a rahulkmr@hpc.bits-hyderabad.ac.in:/scratch/rahulkmr/Adarsh/results/P3/ results/P3/
set -euo pipefail
H=rahulkmr@hpc.bits-hyderabad.ac.in
W=/scratch/rahulkmr/Adarsh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ssh -o BatchMode=yes "$H" "mkdir -p $W/repo $W/logs $W/results/P3"
rsync -a --delete --exclude .git --exclude .venv --exclude results "$ROOT/" "$H:$W/repo/"
ssh -o BatchMode=yes "$H" bash -l -s <<REMOTE
set -e
cd $W/repo/cluster/jobs
dep=""
: > $W/results/P3/jobs.txt
for N in 2000000 10000000; do
    s="sbatch --parsable --kill-on-invalid-dep=yes --export=ALL,N_ROWS=\$N"
    if [ \$N = 10000000 ]; then dt="-t 02:00:00"; else dt=""; fi
    d=\$(\$s \$dt \$dep p3_dump.sbatch)
    a=\$(\$s --array=0-25%6 --dependency=afterok:\$d p3_table.sbatch)
    m=\$(\$s --dependency=afterok:\$a p3_merge.sbatch)
    echo "rows=\$N dump=\$d array=\$a merge=\$m" | tee -a $W/results/P3/jobs.txt
    dep="--dependency=afterok:\$m"
done
squeue -u rahulkmr -o "%.10i %.10P %.10j %.3t %.10l %.20E %r" | head -n 20
REMOTE
