#!/bin/bash
# P8: submit on the login node from /scratch/rahulkmr/Adarsh/p8 (after rsync of the code tree to $P/code).
# p8_stream first; p8_gls256 (10 tasks, at most 4 at a time) starts only if p8_stream succeeds (afterok).
set -euo pipefail
P=/scratch/rahulkmr/Adarsh/p8
cd "$P"; mkdir -p slurm results stimulus
A=$(sbatch --parsable "$P/code/cluster/jobs/p8_stream.sbatch")
B=$(sbatch --parsable -J p8_gls256 -p compute -c 4 --mem=8G --time=04:00:00 --array=1-10%4 \
    --dependency=afterok:$A -o "$P/slurm/%x_%A_%a.out" "$P/code/synthesis/p8/gls_task.sh" "$P/code/synthesis/p8/tasks_256.txt")
echo "$A $B"
