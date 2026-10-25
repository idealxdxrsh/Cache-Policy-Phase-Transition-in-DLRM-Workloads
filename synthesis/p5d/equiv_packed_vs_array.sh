#!/bin/bash
# P5d: Yosys equivalence of the hit tree as flat vectors (attempt 1) vs as unpacked arrays (rtl/v2).
#   bash synthesis/p5d/equiv_packed_vs_array.sh [depths...]   default: 16
# equiv_status -assert fails (non-zero exit) if any $equiv cell is unproven. Each run is capped at 1500 s.
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
R=$ROOT/results/P5d/equiv; mkdir -p "$R"
W=$(mktemp -d); trap 'rm -r "$W"' EXIT
sed 's/^module lfu_cache_controller /module gold /' "$ROOT/results/P5d/attempt1_packed_vectors/lfu_cache_controller_packed.v" > "$W/gold.v"
sed 's/^module lfu_cache_controller /module gate /' "$ROOT/rtl/v2/lfu_cache_controller.v" > "$W/gate.v"
for d in ${*:-16}; do for m in 0 1; do
    timeout 1500 yosys -q -p "read_verilog -sv $W/gold.v $W/gate.v; chparam -set CACHE_DEPTH $d -set COUNTER_MODE $m gold gate; proc; opt_clean; memory; flatten; async2sync; equiv_make gold gate eq; hierarchy -top eq; equiv_simple; equiv_induct; equiv_status -assert" > "$R/equiv_d${d}_m$m.txt" 2>&1
    echo "depth=$d mode=$m exit=$? (0 = all proven, 124 = timeout)" | tee -a "$R/equiv_d${d}_m$m.txt"
done; done
