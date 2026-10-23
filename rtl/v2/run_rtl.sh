#!/bin/bash
# Compile, simulate and (optionally) synthesize the v2 controller.
#   bash run_rtl.sh
# On Sharanga: srun --partition=compute --cpus-per-task=4 --mem=16G --pty bash   then   bash run_rtl.sh
set -e
cd "$(dirname "$0")"
mkdir -p logs
iverilog -g2012 -o lfu_sim lfu_cache_controller.v tb_lfu_cache.sv
vvp lfu_sim | tee logs/sim_output.txt
grep -q "ALL TESTS PASSED" logs/sim_output.txt || { echo "SIMULATION FAILED"; exit 1; }
if command -v yosys >/dev/null; then
    yosys -q -l logs/synth.log synth.ys && grep -E "Number of cells" logs/synth.log | tail -1
else
    echo "yosys not found, skipping synthesis (conda install -c conda-forge yosys)"
fi
