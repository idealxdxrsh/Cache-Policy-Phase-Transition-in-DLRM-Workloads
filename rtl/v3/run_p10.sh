#!/bin/bash
# P10 driver (local, Icarus only, no synthesis): rtl/v3 = rtl-v2-final + Rotate-victim in COUNTER_MODE 0.
#   bash rtl/v3/run_p10.sh tb        # tb_lfu_cache.sv TESTS 1-8, depths 16/64/256 x modes 0/1 -> results/P10/tb/
#   bash rtl/v3/run_p10.sh mutants   # TEST 8 against 3 broken copies of v3 (must FAIL) -> results/P10/mutants.txt
#   bash rtl/v3/run_p10.sh rtl D M SLICE   # one lockstep RTL run, all 200,000 requests of the slice
#   bash rtl/v3/run_p10.sh all       # tb, mutants, the 12 RTL runs (4 at a time), then tools/p10_lockstep.py
# Lockstep: synthesis/p9/tb_hitlog.sv (unchanged) logs hit_flag per request on the P8 slices of the P3b stream
# (results/P8/stimulus/<slice>.hex, stream.json: matches_p3b). Output results/P10/rtl/<run>.txt and
# <run>.hits.gz (not committed); work files in results/P10/work/ (not committed).
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
R=$ROOT/results/P10; S=$ROOT/results/P8/stimulus; V3=$ROOT/rtl/v3
PY=${PY:-python3}
TV="$PY -I $ROOT/tools/timev.py"

rtl() {     # rtl D M SLICE  (warm/win only shape tb_hitlog's power window; FULL=1 replays every request)
    local d=$1 m=$2 slice=$3 warm win=10000
    if [ "$d" = 256 ]; then warm=100000; else warm=20000; fi
    local run=d${d}_m${m}_${slice}_full
    local w=$R/work/$run o=$R/rtl/$run.txt tf=$S/$slice.hex; mkdir -p "$w" "$R/rtl"
    {
    echo "# P10 $run: zero-delay RTL simulation (rtl/v3), tb_hitlog FULL=1 WARM=$warm WIN=$win SEED=1"
    echo "rtl: rtl/v3/lfu_cache_controller.v sha256 $(sha256sum "$V3/lfu_cache_controller.v" | cut -c1-64)"
    echo "trace: $tf sha256 $(sha256sum "$tf" | cut -c1-64)"
    echo "iverilog: $(iverilog -V 2>&1 | head -n 1)"
    $TV iverilog -g2012 -DUSE_RTL -Ptb_hitlog.CACHE_DEPTH=$d -Ptb_hitlog.COUNTER_MODE=$m -Ptb_hitlog.STIM=1 \
        -Ptb_hitlog.WARM=$warm -Ptb_hitlog.WIN=$win -Ptb_hitlog.SEED=1 -Ptb_hitlog.FULL=1 \
        -o "$w/sim.vvp" "$V3/lfu_cache_controller.v" "$ROOT/synthesis/p9/tb_hitlog.sv" \
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

mutants() {  # each mutant must fail TEST 8 (depth 256, mode 0); the sed must change the file
    local w=$R/work/mutants out=$R/mutants.txt; mkdir -p "$w"
    : > "$out"
    while IFS='|' read -r name expr; do
        sed "$expr" "$V3/lfu_cache_controller.v" > "$w/$name.v"
        if cmp -s "$w/$name.v" "$V3/lfu_cache_controller.v"; then echo "$name: SED DID NOT APPLY" >> "$out"; continue; fi
        iverilog -g2012 -P tb_lfu_cache.COUNTER_MODE=0 -P tb_lfu_cache.CACHE_DEPTH=256 -o "$w/$name.vvp" \
            "$w/$name.v" "$V3/tb_lfu_cache.sv" && vvp -n "$w/$name.vvp" > "$w/$name.log"
        if grep -q "ALL TESTS PASSED" "$w/$name.log"; then r="NOT CAUGHT"; else r="caught"; fi
        echo "$name: $r; $(grep -c FAIL: "$w/$name.log") failed checks, $(grep -c 'tie test' "$w/$name.log") in TEST 8" >> "$out"
    done <<'EOF'
no_rotate (v2 rule: ROTATE = 0)|s/^localparam ROTATE = (COUNTER_MODE == 0);/localparam ROTATE = 0;/
ptr_no_increment (ptr <= victim_reg)|s/ptr <= victim_reg + 1'b1;/ptr <= victim_reg;/
stageB_no_wrap (Stage B leaf wrap = 0)|s/ROTATE && (stageA_min\[g\] < ptr)/1'b0/
EOF
    cat "$out"
}

case ${1:-} in
tb) mkdir -p "$R/tb"; bash "$V3/run_rtl.sh" "$R/tb" ;;
mutants) mutants ;;
rtl) shift; rtl "$@" ;;
all)
    bash "$0" tb || exit 1
    mutants
    for d in 16 64 256; do for m in 0 1; do for s in row0 row1M; do echo "$d $m $s"; done; done; done \
        | xargs -P 4 -L 1 bash "$0" rtl
    $PY -I "$ROOT/tools/p10_lockstep.py" 4 ;;
*) echo "usage: see header"; exit 2 ;;
esac
