#!/bin/bash
# P5d driver, local only (no cluster). NanGate45, not TSMC. Pre-layout. No power step.
# hit_idx priority loop -> balanced priority tree, on top of P5c (commit 73016e0).
# Steps:
#   sim       unmodified testbench, depths 16/64/256 x modes 0/1               -> results/P5d/sim/
#   lockstep  vs rtl-v2-baseline, P5b (fac3366), P5c (73016e0); also checks at
#             most one match per cycle and compares hit_idx on every hit       -> results/P5d/lockstep_vs_<ref>.txt
#   synth     same flow as P5/P5b/P5c, 1 GHz and 500 MHz                       -> results/P5d/d*/
#   noise     3 logically identical rewrites of the P5d RTL (tools/p5d_null_variants.py),
#             1 GHz only, all depths/modes: spread of Fmax = flow noise floor -> results/P5d/noise/
#   bash synthesis/p5d/run_p5d.sh [sim|lockstep|synth|noise]...   default: all four
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
R=$ROOT/results/P5d
STEPS=${*:-"sim lockstep synth noise"}
W=$(mktemp -d); trap 'rm -r "$W"' EXIT
for step in $STEPS; do case $step in
sim)
    mkdir -p "$R/sim"
    for d in 16 64 256; do for m in 0 1; do
        iverilog -g2012 -Ptb_lfu_cache.COUNTER_MODE=$m -Ptb_lfu_cache.CACHE_DEPTH=$d -o "$W/sim" \
            "$ROOT/rtl/v2/lfu_cache_controller.v" "$ROOT/rtl/v2/tb_lfu_cache.sv"
        (cd "$W" && vvp -n sim) > "$R/sim/sim_d${d}_m${m}.txt"
        echo "d=$d m=$m: $(grep -c FAIL "$R/sim/sim_d${d}_m${m}.txt") FAIL lines; $(grep -o 'ALL TESTS PASSED' "$R/sim/sim_d${d}_m${m}.txt" || echo NOT PASSED)"
    done; done ;;
lockstep)
    pids=()
    for ref in rtl-v2-baseline fac3366 73016e0; do
        REF=$ref OUT=$R/lockstep_vs_$ref.txt bash "$ROOT/synthesis/p5b/run_lockstep.sh" > /dev/null &
        pids+=($!)
    done
    for p in "${pids[@]}"; do wait "$p"; done
    for ref in rtl-v2-baseline fac3366 73016e0; do
        echo "vs $ref: $(grep -c 'LOCKSTEP PASSED' "$R/lockstep_vs_$ref.txt")/6 passed"
    done ;;
synth)
    pids=()
    for ds in "16 64" "256"; do
        OUTDIR=results/P5d bash "$ROOT/synthesis/p5/run_p5.sh" $ds > "$W/synth_${ds// /_}.txt" 2>&1 &
        pids+=($!)
    done
    rc=0; for p in "${pids[@]}"; do wait "$p" || rc=1; done
    cat "$W"/synth_*.txt > "$R/run_synth.txt"
    gzip -f "$R"/d*/yosys.log
    (cd "$R" && sha256sum d*/netlist.v > netlists.sha256)
    exit $rc ;;
noise)
    python3 -I "$ROOT/tools/p5d_null_variants.py" "$ROOT/rtl/v2/lfu_cache_controller.v" "$R/noise/rtl"
    pids=()
    for v in null_tagcmp_swap null_hitor_swap null_stageB_gt; do
        FREQS=1000 RTL=$R/noise/rtl/$v.v OUTDIR=results/P5d/noise/$v bash "$ROOT/synthesis/p5/run_p5.sh" \
            > "$W/noise_$v.txt" 2>&1 &
        pids+=($!)
    done
    rc=0; for p in "${pids[@]}"; do wait "$p" || rc=1; done
    cat "$W"/noise_*.txt > "$R/noise/run_synth.txt"
    gzip -f "$R"/noise/null_*/d*/yosys.log
    (cd "$R/noise" && sha256sum null_*/d*/netlist.v > netlists.sha256)
    exit $rc ;;
*) echo "unknown step $step"; exit 2 ;;
esac; done
