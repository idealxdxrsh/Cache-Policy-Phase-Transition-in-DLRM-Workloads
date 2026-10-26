#!/bin/bash
# P5c driver, local only (no cluster). NanGate45, not TSMC. Pre-layout. No power step.
# Stage-A reduction tree on top of P5b (commit fac3366), in two variants:
#   results/P5c/rtl/tree_copies.v  Stage A tree + Stage B tree + per-group address copies
#   results/P5c/rtl/tree_only.v    the same minus the copies (tools/p5c_strip_copies.py)
# Steps: unmodified testbench at depths 16/64/256 x modes 0/1; lockstep of each variant
# against rtl-v2-baseline and against P5b (fac3366); synth + OpenSTA, same flow as P5/P5b.
#
# Decision rule, fixed before any P5c synthesis run: the address copies are kept only if,
# at depth 256, tree_copies has a Fmax at least 5% above tree_only in BOTH modes, in both
# the 1 GHz and the 500 MHz netlists. Otherwise they are reverted in rtl/v2 (they stay in
# git history: P5b commit 4debe84 and the P5c commit that precedes the revert).
#
#   bash synthesis/p5c/run_p5c.sh [sim|lockstep|synth]...   default: all three
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
R=$ROOT/results/P5c
P5B=fac3366
STEPS=${*:-"sim lockstep synth"}
W=$(mktemp -d); trap 'rm -r "$W"' EXIT
for step in $STEPS; do case $step in
sim)
    mkdir -p "$R/sim"
    for v in tree_copies tree_only; do for d in 16 64 256; do for m in 0 1; do
        iverilog -g2012 -Ptb_lfu_cache.COUNTER_MODE=$m -Ptb_lfu_cache.CACHE_DEPTH=$d -o "$W/sim" \
            "$R/rtl/$v.v" "$ROOT/rtl/v2/tb_lfu_cache.sv"
        (cd "$W" && vvp -n sim) > "$R/sim/${v}_d${d}_m${m}.txt"
        echo "$v d=$d m=$m: $(grep -c FAIL "$R/sim/${v}_d${d}_m${m}.txt") FAIL lines; $(grep -o 'ALL TESTS PASSED' "$R/sim/${v}_d${d}_m${m}.txt" || echo NOT PASSED)"
    done; done; done ;;
lockstep)
    for v in tree_copies tree_only; do
        for ref in rtl-v2-baseline $P5B; do
            REF=$ref DUT=$R/rtl/$v.v OUT=$R/lockstep_${v}_vs_${ref}.txt bash "$ROOT/synthesis/p5b/run_lockstep.sh" > /dev/null
            echo "$v vs $ref: $(grep -c 'LOCKSTEP PASSED' "$R/lockstep_${v}_vs_${ref}.txt")/6 passed"
        done
    done ;;
synth)
    # 4 parallel streams (one per variant x {16+64, 256}); each run is < 1 GB RSS (P5b: 871832 kB at depth 256)
    pids=()
    for v in tree_copies tree_only; do
        for ds in "16 64" "256"; do
            RTL=$R/rtl/$v.v OUTDIR=results/P5c/$v bash "$ROOT/synthesis/p5/run_p5.sh" $ds \
                > "$W/synth_${v}_${ds// /_}.txt" 2>&1 &
            pids+=($!)
        done
    done
    rc=0; for p in "${pids[@]}"; do wait "$p" || rc=1; done
    cat "$W"/synth_*.txt > "$R/run_synth.txt"
    gzip -f "$R"/tree_*/d*/yosys.log
    for v in tree_copies tree_only; do
        (cd "$R/$v" && sha256sum d*/netlist.v > netlists.sha256)
    done
    exit $rc ;;
*) echo "unknown step $step"; exit 2 ;;
esac; done
