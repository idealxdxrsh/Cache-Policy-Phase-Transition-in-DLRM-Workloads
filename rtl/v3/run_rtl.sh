#!/bin/bash
# Compile and simulate the v3 controller (tb_lfu_cache.sv, TESTS 1-8)
# for each COUNTER_MODE and CACHE_DEPTH. No synthesis for v3 (P10).
#   bash run_rtl.sh [logdir]       # modes 0 1 x depths 16 64 256
# Runs locally (small); on the cluster use sbatch, never srun --pty.
set -e
cd "$(dirname "$0")"
LOG=${1:-logs}
mkdir -p "$LOG"
for d in 16 64 256; do for m in 0 1; do
    iverilog -g2012 -P tb_lfu_cache.COUNTER_MODE=$m -P tb_lfu_cache.CACHE_DEPTH=$d -o lfu_sim_d${d}_m$m \
        lfu_cache_controller.v tb_lfu_cache.sv
    vvp -n lfu_sim_d${d}_m$m > "$LOG/sim_d${d}_mode$m.txt"
    rm -f lfu_sim_d${d}_m$m
    grep -q "ALL TESTS PASSED" "$LOG/sim_d${d}_mode$m.txt" || { echo "SIMULATION FAILED (DEPTH=$d COUNTER_MODE=$m)"; exit 1; }
    echo "DEPTH=$d COUNTER_MODE=$m: ALL TESTS PASSED"
done; done
