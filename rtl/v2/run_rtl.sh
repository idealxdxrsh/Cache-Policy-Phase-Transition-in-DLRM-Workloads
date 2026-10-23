#!/bin/bash
# Compile and simulate the v2 controller for every COUNTER_MODE,
# then (optionally) run generic Yosys synthesis.
#   bash run_rtl.sh            # modes 0 and 1
#   bash run_rtl.sh 1          # one mode
# Runs locally (small); on the cluster use sbatch, never srun --pty.
set -e
cd "$(dirname "$0")"
mkdir -p logs
MODES=${*:-"0 1"}
for m in $MODES; do
    iverilog -g2012 -P tb_lfu_cache.COUNTER_MODE=$m -o lfu_sim_m$m lfu_cache_controller.v tb_lfu_cache.sv
    vvp -n lfu_sim_m$m | tee logs/sim_mode$m.txt
    rm -f lfu_sim_m$m
    grep -q "ALL TESTS PASSED" logs/sim_mode$m.txt || { echo "SIMULATION FAILED (COUNTER_MODE=$m)"; exit 1; }
done
if command -v yosys >/dev/null; then
    yosys -q -l logs/synth.log synth.ys && grep -E "Number of cells" logs/synth.log | tail -1
else
    echo "yosys not found, skipping synthesis"
fi
