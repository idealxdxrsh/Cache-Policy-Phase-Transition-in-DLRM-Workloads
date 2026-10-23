#!/bin/bash
# P3 driver (run locally; NOT yet run): sync repo, then for 2M and then 10M rows
# submit dump -> 26-task table array -> merge, chained with afterok (the 10M
# chain starts only after the 2M merge succeeds). Blocks on the last job with
# sbatch --wait (no polling), then copies results back to results/P3/.
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
    d=\$(\$s \$dep p3_dump.sbatch)
    a=\$(\$s --dependency=afterok:\$d p3_table.sbatch)
    m=\$(\$s --dependency=afterok:\$a p3_merge.sbatch)
    echo "rows=\$N dump=\$d array=\$a merge=\$m" >> $W/results/P3/jobs.txt
    dep="--dependency=afterok:\$m"
done
sbatch --parsable --wait --kill-on-invalid-dep=yes -p compute -c 4 -t 00:05:00 -J p3_wait \
    -o $W/logs/p3_wait_%j.out \$dep --wrap true \
    || echo "chain failed or was cancelled (rc=\$?)" >> $W/results/P3/jobs.txt
sacct -S today -n -X --name=p3_dump,p3_table,p3_merge -o JobID,JobName,State,ExitCode,Elapsed \
    >> $W/results/P3/jobs.txt
REMOTE
mkdir -p "$ROOT/results/P3"
rsync -a "$H:$W/results/P3/" "$ROOT/results/P3/"
