#!/bin/bash
# P7: did the P5f lockstep stimulus drive any frequency counter to saturation (63)? Local, RTL only (Icarus).
# synthesis/p7/tb_counter_sat.sv reuses the stimulus of synthesis/p5f/tb_gls_lockstep.sv (seed 1, 200,000 cycles);
# its response/hit/miss/fill counts are compared with results/P5f_gls/cluster/lockstep/d<D>_m<M>_1000MHz.txt
# (the clock target does not change the RTL, so one run per depth/mode covers both netlists).
#   bash synthesis/p7/run_counter_sat.sh      -> results/P7/counter_sat/d<D>_m<M>.txt
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
R=$ROOT/results/P7/counter_sat; W=$ROOT/results/P7/counter_sat/work
mkdir -p "$R" "$W"
one() {
    d=$1 m=$2; o=$R/d${d}_m${m}.txt
    { echo "# RTL-only counter-saturation run, depth $d mode $m (rtl/v2 at $(git -C "$ROOT" describe --tags --always HEAD), $(iverilog -V 2>&1 | head -n 1))"
      iverilog -g2012 -Ptb_counter_sat.CACHE_DEPTH=$d -Ptb_counter_sat.COUNTER_MODE=$m -o "$W/d${d}_m${m}.vvp" \
          "$ROOT/rtl/v2/lfu_cache_controller.v" "$ROOT/synthesis/p7/tb_counter_sat.sv" || { echo "compile failed"; return; }
      t0=$(date +%s)
      timeout 7200 vvp -n "$W/d${d}_m${m}.vvp" | grep '^counter_sat'
      echo "vvp exit=${PIPESTATUS[0]} wall_s=$(( $(date +%s) - t0 ))"
      g=$(grep '^gls_lockstep' "$ROOT/results/P5f_gls/cluster/lockstep/d${d}_m${m}_1000MHz.txt")
      echo "P5f lockstep (cluster, Icarus 11): $g"
    } > "$o" 2>&1
}
export -f one; export R W ROOT
printf '%s\n' "16 0" "16 1" "64 0" "64 1" "256 0" "256 1" | xargs -P 6 -L 1 bash -c 'one "$0" "$1"'
rm -rf "$W"
