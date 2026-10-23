#!/bin/bash
#SBATCH --job-name=trace_cache_sim
#SBATCH --partition=compute
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/trace_sim_%j.out
#SBATCH --error=logs/trace_sim_%j.err
#
# Trace-driven LRU / LFU / LFU-reset / TinyLFU sweep on Criteo.
# Run from the trace_sim/ directory:   mkdir -p logs && sbatch submit_trace_sim.sh
# Override the dataset path with:      CRITEO_PATH=/path/train.txt sbatch submit_trace_sim.sh
set -e
cd "$SLURM_SUBMIT_DIR"
CRITEO_PATH="${CRITEO_PATH:-/scratch/$USER/Adarsh/dlrm/criteo/raw/dac/train.txt}"
N_ROWS="${N_ROWS:-2000000}"

[ -f "$CRITEO_PATH" ] || { echo "Criteo file not found: $CRITEO_PATH"; exit 1; }
mkdir -p results figs logs

echo "node=$(hostname) cpus=$SLURM_CPUS_PER_TASK rows=$N_ROWS file=$CRITEO_PATH"
python3 run_trace_sim.py \
    --criteo_path "$CRITEO_PATH" \
    --n_rows "$N_ROWS" \
    --output results \
    --capacities 100 500 1000 2000 5000 10000 20000 50000 100000 \
    --workers "$SLURM_CPUS_PER_TASK"

python3 plot_trace_results.py --results results/trace_sim_results.json --output figs
echo "done: $(date)"
