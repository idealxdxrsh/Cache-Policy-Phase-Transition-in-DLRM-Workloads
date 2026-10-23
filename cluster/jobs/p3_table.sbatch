#!/bin/bash -l
#SBATCH -J p3_table
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH --mem=16G   # synthetic 10M task peaked at 812976 kB; real Criteo has more unique ids
#SBATCH -t 02:00:00 # synthetic 10M task: 116-195 s on 4 workers (results/P3_prep/timing_10M)
#SBATCH --array=0-25
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%A_%a.out
# One array task per embedding table: all policies + Belady, all capacities.
# Submit with: sbatch --export=ALL,N_ROWS=2000000 p3_table.sbatch
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
: "${N_ROWS:?set N_ROWS}"
T=$SLURM_ARRAY_TASK_ID
TAG=$(printf 'table_%02d' "$T")
TR=$W/data/p3/traces_$N_ROWS
PARTS=$W/results/P3/rows_$N_ROWS/parts; mkdir -p "$PARTS"
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
# GNU time is missing on some compute nodes (node6, job 412923: exit 127)
python -I "$W/repo/tools/timev.py" python -I "$W/repo/trace_sim/run_trace_sim.py" \
    --trace_dir "$TR" --tables "$T" --belady --workers "$SLURM_CPUS_PER_TASK" \
    --output "$PARTS" --tag "$TAG" \
    > "$PARTS/${TAG}_log.txt" 2> "$PARTS/${TAG}_time.txt"
