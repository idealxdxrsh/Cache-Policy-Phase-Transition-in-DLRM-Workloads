#!/bin/bash
# P14 driver (run locally). H100 only, 1 GPU, 4 CPUs. Two stages, each ends with a waiter job
# (sbatch --wait) that blocks until its jobs end; no polling.
#   STAGE=test ./cluster/p14_driver.sh   prep (compute, CPU: row-aligned stream, checked against the P3 dumps)
#                                        -> test (H100, 15 min: 2 batches, per_table:64 and concat:16384), afterok
#   STAGE=main ./cluster/p14_driver.sh   main: 20 batches, per_table and concat at B = 64, 1024, 16384, as three
#                                        H100 jobs in sequence (afterany, one GPU at a time):
#                                        main1 per_table:64 (35 min), main2 per_table:1024 (30 min),
#                                        main3 per_table:16384 + concat x3 (35 min).
# Limits from test job 454182 (status.txt): per ncu run ~3 application-replay passes; per_table B=64 warmup
# ~75 s per pass; ~0.9 s per profiled kernel per pass; so per_table ~23-28 min, concat ~1-2 min per config.
# GPU time limits: test 15 min + main 100 min (prep smoke 453624/453629 used 4 min).
# P14 prep (counter smoke test, jobs 453624/453629) used the earlier version of this script: git history,
# results/P14/PREP.md.
# Options: AFTER=<jobid> makes every main job also wait for that job to succeed (afterok; with
# --kill-on-invalid-dep=yes they are cancelled if it fails), e.g. the env rebuild (cluster/jobs/env_rebuild.sbatch).
# NOWAIT=1 submits and returns without the waiter job and the sacct record (run sacct later).
# Copy back with: rsync -a rahulkmr@hpc.bits-hyderabad.ac.in:/scratch/rahulkmr/Adarsh/results/P14/ results/P14/
set -euo pipefail
STAGE=${STAGE:?set STAGE=test or STAGE=main}
case $STAGE in test|main) ;; *) echo "STAGE must be test or main" >&2; exit 1 ;; esac
AFTER=${AFTER:-}; NOWAIT=${NOWAIT:-0}
D1=""; DA=""; [ -n "$AFTER" ] && { D1="--dependency=afterok:$AFTER"; DA="afterok:$AFTER,"; }
H=rahulkmr@hpc.bits-hyderabad.ac.in
W=/scratch/rahulkmr/Adarsh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ssh -o BatchMode=yes "$H" "mkdir -p $W/repo $W/logs $W/results/P14"
# No --delete (user decision 2026-11-19): the sync only adds and updates files in the scratch copy of the repo.
rsync -a --exclude .git --exclude .venv --exclude results "$ROOT/" "$H:$W/repo/"
ssh -o BatchMode=yes "$H" bash -l -s <<REMOTE
set -e
cd $W/repo/cluster/jobs
s="sbatch --parsable --kill-on-invalid-dep=yes"
if [ "$STAGE" = test ]; then
  p=\$(\$s p14_prep.sbatch)
  t=\$(\$s -t 00:15:00 --dependency=afterok:\$p --export=ALL,LABEL=test,BATCHES=2,CONFIGS="per_table:64 concat:16384" p14_ncu.sbatch)
  echo "p14 prep=\$p test=\$t (afterok:\$p)" | tee -a $W/results/P14/jobs.txt; ids=\$p:\$t
else
  m1=\$(\$s -t 00:35:00 $D1 --export=ALL,LABEL=main1,BATCHES=20,CONFIGS="per_table:64" p14_ncu.sbatch)
  m2=\$(\$s -t 00:30:00 --dependency=${DA}afterany:\$m1 --export=ALL,LABEL=main2,BATCHES=20,CONFIGS="per_table:1024" p14_ncu.sbatch)
  m3=\$(\$s -t 00:35:00 --dependency=${DA}afterany:\$m2 --export=ALL,LABEL=main3,BATCHES=20,CONFIGS="per_table:16384 concat:64 concat:1024 concat:16384" p14_ncu.sbatch)
  echo "p14 main1=\$m1${AFTER:+ (afterok:$AFTER)} main2=\$m2 (${DA}afterany:\$m1) main3=\$m3 (${DA}afterany:\$m2)" | tee -a $W/results/P14/jobs.txt; ids=\$m1:\$m2:\$m3
fi
[ "$NOWAIT" = 1 ] && exit 0
sbatch --wait --parsable -p compute -c 4 --mem=100M -t 00:01:00 -J p14_wait \
    -o $W/logs/%x_%j.out --dependency=afterany:\$ids --wrap true || true
sleep 30  # accounting lag: right after the waiter, sacct showed a finished job as PENDING (job 456792)
sacct -j \${ids//:/,} -X -o JobID,JobName,Partition,NodeList,State,ExitCode,Elapsed | tee -a $W/results/P14/sacct.txt
REMOTE
