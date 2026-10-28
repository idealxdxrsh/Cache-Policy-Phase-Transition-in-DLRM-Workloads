#!/bin/bash
# P11: Yosys equivalence of rtl-v2-final (gold) vs rtl/v3 (gate) in COUNTER_MODE 1, on the RTL (not the netlists).
#   bash synthesis/p11/equiv_v2_v3_m1.sh [depths...]   default: 64
# Same commands as synthesis/p5d/equiv_packed_vs_array.sh. gold = rtl/v2/lfu_cache_controller.v at tag rtl-v2-final,
# gate = rtl/v3/lfu_cache_controller.v of the working tree. equiv_status -assert fails (non-zero exit) if any $equiv
# cell is unproven. Each run is capped at ${CAP:-10800} s. Output: results/P11/equiv/equiv_d<D>_m1.txt.
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
R=$ROOT/results/P11/equiv; mkdir -p "$R"
W=$(mktemp -d); trap 'rm -r "$W"' EXIT
git -C "$ROOT" show rtl-v2-final:rtl/v2/lfu_cache_controller.v | sed 's/^module lfu_cache_controller /module gold /' > "$W/gold.v"
sed 's/^module lfu_cache_controller /module gate /' "$ROOT/rtl/v3/lfu_cache_controller.v" > "$W/gate.v"
for d in ${*:-64}; do
    o=$R/equiv_d${d}_m1.txt
    {
    echo "# gold: rtl-v2-final:rtl/v2/lfu_cache_controller.v sha256 $(git -C "$ROOT" show rtl-v2-final:rtl/v2/lfu_cache_controller.v | sha256sum | cut -c1-64)"
    echo "# gate: rtl/v3/lfu_cache_controller.v sha256 $(sha256sum "$ROOT/rtl/v3/lfu_cache_controller.v" | cut -c1-64)"
    echo "# $(yosys -V); CACHE_DEPTH=$d COUNTER_MODE=1; started $(date -Is)"
    } > "$o"
    /usr/bin/time -f "wall %e s, max RSS %M KB" timeout "${CAP:-10800}" yosys -q -p "read_verilog -sv $W/gold.v $W/gate.v; chparam -set CACHE_DEPTH $d -set COUNTER_MODE 1 gold gate; proc; opt_clean; memory; flatten; async2sync; equiv_make gold gate eq; hierarchy -top eq; equiv_simple; equiv_induct; tee -o $W/status.txt equiv_status; equiv_status -assert" >> "$o" 2>&1
    rc=$?
    [ -f "$W/status.txt" ] && cat "$W/status.txt" >> "$o"
    echo "depth=$d mode=1 exit=$rc (0 = all proven, 124 = timeout); ended $(date -Is)" | tee -a "$o"
    rm -f "$W/status.txt"
done
