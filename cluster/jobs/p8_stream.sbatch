#!/bin/bash
#SBATCH -J p8_stream
#SBATCH -p compute
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/p8/slurm/%x_%j.out
# -c 4: the compute QOS rejects -c 1 (QOSMinCpuNotSatisfied); the script uses one CPU.
# P8: Criteo request slices (tools/p8_stream.py): first 2,000,000 rows, P3b shared-cache order and keys; slices from
# row 0 and from row 1,000,000, 200,000 requests each, keys numbered inside each slice.
set -euo pipefail
P=/scratch/rahulkmr/Adarsh/p8
E=/home/rahulkmr/.conda/envs/rtl_sim/bin
"$E/python3" -I "$P/code/tools/timev.py" "$E/python3" -I "$P/code/tools/p8_stream.py" \
    /scratch/rahulkmr/Adarsh/data/criteo/extracted/train.txt "$P/stimulus" 200000 \
    > "$P/results/stream_log.txt" 2> "$P/results/stream_time.txt"
