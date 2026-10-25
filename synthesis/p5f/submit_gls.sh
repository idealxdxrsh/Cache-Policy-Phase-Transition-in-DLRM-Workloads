#!/bin/bash
# P5f: submit the gate-level simulations on the cluster (run on the login node from /scratch/rahulkmr/Adarsh/gls).
# One --mem per array is all Slurm allows, so the depth-256 tasks (32 GB) and the others (8 GB) are two arrays;
# the second starts only after the first has ended (afterany), so at most 4 tasks run at any time.
# compute partition: MaxTime UNLIMITED (sinfo/scontrol); each task asks 2:30:00 = 2 h vvp limit + compile margin.
set -euo pipefail
G=/scratch/rahulkmr/Adarsh/gls
cd "$G"
mkdir -p slurm
A=$(sbatch --parsable -p compute -c 4 --mem=32G --time=02:30:00 --array=1-8%4 -J gls256 \
    -o slurm/%x_%A_%a.out "$G/scripts/gls_task.sh" "$G/scripts/tasks_32g.txt")
B=$(sbatch --parsable -p compute -c 4 --mem=8G --time=02:30:00 --array=1-12%4 -J gls_small \
    --dependency=afterany:$A -o slurm/%x_%A_%a.out "$G/scripts/gls_task.sh" "$G/scripts/tasks_8g.txt")
echo "$A $B"
