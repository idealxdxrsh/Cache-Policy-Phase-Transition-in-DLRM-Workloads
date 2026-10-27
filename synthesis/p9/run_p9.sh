#!/bin/bash
# P9 driver (local): zero-delay RTL simulations of rtl-v2-final (rtl/v2/lfu_cache_controller.v, unchanged) on the
# P8 Criteo slices, logging hit_flag per request (synthesis/p9/tb_hitlog.sv = P8's tb_power.sv + a hit log).
#   bash synthesis/p9/run_p9.sh rtl D M SLICE KIND    # KIND p8budget: P8's cycle budget (warm-up + window cycles,
#                                                     #   same seed), so the requests replayed are P8's exactly;
#                                                     # KIND full: all 200,000 requests of the slice
#   bash synthesis/p9/run_p9.sh all                   # the 24 runs (depths 16/64/256, modes 0/1, row0/row1M, both
#                                                     #   kinds), 4 at a time
# Output: results/P9/rtl/<run>.txt (summary line, compile/run time) and results/P9/rtl/<run>.hits.gz
# (`<request index> <address hex> <hit_flag>` per request). Work files in results/P9/work/ (not committed).
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
R=$ROOT/results/P9; S=$ROOT/results/P8/stimulus
PY=${PY:-python3}
TV="$PY -I $ROOT/tools/timev.py"

rtl() {     # rtl D M SLICE KIND
    local d=$1 m=$2 slice=$3 kind=$4 warm win full
    if [ "$d" = 256 ]; then warm=100000; else warm=20000; fi    # P8: results/P8/sim/*_rtl_w<warm>_n10000.txt
    win=10000
    full=$([ "$kind" = full ] && echo 1 || echo 0)
    local run=d${d}_m${m}_${slice}_${kind}
    local w=$R/work/$run o=$R/rtl/$run.txt tf=$S/$slice.hex; mkdir -p "$w" "$R/rtl"
    {
    echo "# P9 $run: zero-delay RTL simulation (rtl/v2, rtl-v2-final), tb_hitlog FULL=$full WARM=$warm WIN=$win SEED=1"
    echo "trace: $tf sha256 $(sha256sum "$tf" | cut -c1-64)"
    echo "iverilog: $(iverilog -V 2>&1 | head -n 1)"
    $TV iverilog -g2012 -DUSE_RTL -Ptb_hitlog.CACHE_DEPTH=$d -Ptb_hitlog.COUNTER_MODE=$m -Ptb_hitlog.STIM=1 \
        -Ptb_hitlog.WARM=$warm -Ptb_hitlog.WIN=$win -Ptb_hitlog.SEED=1 -Ptb_hitlog.FULL=$full \
        -o "$w/sim.vvp" "$ROOT/rtl/v2/lfu_cache_controller.v" "$ROOT/synthesis/p9/tb_hitlog.sv" \
        > "$w/iverilog.txt" 2> "$w/compile_time.txt"
    echo "compile: $(grep -E 'Elapsed|Maximum resident' "$w/compile_time.txt" | awk -F': ' '{printf "%s ", $2}')"
    $TV vvp -n "$w/sim.vvp" "+trace=$tf" "+nreq=$(grep -c . "$tf")" "+hitlog=$w/hits.txt" \
        > "$w/vvp.txt" 2> "$w/run_time.txt"
    echo "run: $(grep -E 'Elapsed|Maximum resident' "$w/run_time.txt" | awk -F': ' '{printf "%s ", $2}')"
    grep '^p8_power' "$w/vvp.txt" || { echo "SIMULATION FAILED"; tail -n 5 "$w/vvp.txt"; }
    echo "hitlog: lines $(wc -l < "$w/hits.txt") sha256 $(sha256sum "$w/hits.txt" | cut -c1-64)"
    } > "$o" 2>&1
    gzip -9 -n -c "$w/hits.txt" > "$R/rtl/$run.hits.gz"
}

case ${1:-} in
rtl) shift; rtl "$@" ;;
all)
    for kind in p8budget full; do for d in 16 64 256; do for m in 0 1; do for s in row0 row1M; do
        echo "$d $m $s $kind"
    done; done; done; done | xargs -P 4 -L 1 bash "$0" rtl ;;
*) echo "usage: see header"; exit 2 ;;
esac
