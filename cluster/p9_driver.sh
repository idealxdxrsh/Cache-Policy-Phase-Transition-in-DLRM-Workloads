#!/bin/bash
# P9 driver (run locally, only after the user's OK): sync the repo, submit the four P9 shared-cache jobs.
#   bash cluster/p9_driver.sh        # set A 2M; set A 10M afterok; set B 2M; set B 10M afterok
# Limits (basis: results/P9/jobs/sizing.json, projected from measured times; P3b memory at the same row counts):
#   2M : --mem=16G -t 01:00:00   (projected CPU total A 700 s, B 1092 s; P3b 2M peak RSS 633444 kB)
#   10M: --mem=32G -t 02:00:00   (projected CPU total A 3392 s, B 5335 s; P3b 10M peak RSS 2577964 kB)
# Submits and returns; it does not wait. Copy back afterwards with:
#   rsync -a rahulkmr@hpc.bits-hyderabad.ac.in:/scratch/rahulkmr/Adarsh/results/P9/ results/P9/cluster/
set -euo pipefail
H=rahulkmr@hpc.bits-hyderabad.ac.in
W=/scratch/rahulkmr/Adarsh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ssh -o BatchMode=yes "$H" "mkdir -p $W/repo $W/logs $W/results/P9"
rsync -a --delete --exclude .git --exclude .venv --exclude results "$ROOT/" "$H:$W/repo/"
ssh -o BatchMode=yes "$H" bash -l -s <<REMOTE
set -e
cd $W/repo/cluster/jobs
for s in A B; do
    j2=\$(sbatch --parsable --mem=16G -t 01:00:00 --export=ALL,N_ROWS=2000000,SET=\$s p9_shared.sbatch)
    j10=\$(sbatch --parsable --mem=32G -t 02:00:00 --dependency=afterok:\$j2 --export=ALL,N_ROWS=10000000,SET=\$s p9_shared.sbatch)
    echo "set=\$s rows=2000000 job=\$j2; rows=10000000 job=\$j10 (afterok:\$j2)" | tee -a $W/results/P9/jobs.txt
done
squeue -u rahulkmr -o "%.10i %.10P %.12j %.3t %.10l %.6C %.8m %r" | head -n 8
REMOTE
