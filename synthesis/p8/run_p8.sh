#!/bin/bash
# P8 driver (local; the depth-256 simulations run on the cluster via synthesis/p8/gls_task.sh).
# Power of rtl-v2-final, P5e-flow 500 MHz netlists (results/P5f_gls/netlists/d<D>_m<M>_500MHz/netlist.v, sha256 as
# results/P5e/new/netlists.sha256). Every number: "NanGate45, typical corner, pre-layout, no clock tree, no extracted
# parasitics, flip-flop storage, activity from <method> over <N> cycles".
#   bash synthesis/p8/run_p8.sh vectorless                 # 6 configurations, OpenSTA default activity
#   bash synthesis/p8/run_p8.sh sim D M STIM WARM WIN [MODEL] [SLICE]
#        STIM random|criteo; MODEL gl (netlist, VCD + power) | rtl (RTL, counts only, no VCD) | glnovcd (timing pilot)
#        SLICE row0|row1M (criteo only; results/P8/stimulus/<SLICE>.hex + .json from tools/p8_stream.py)
#   bash synthesis/p8/run_p8.sh pilot                      # depth 16 mode 0 random: gl with and without VCD
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
# Overridable for the cluster (synthesis/p8/gls_task.sh): P8_OUT, P8_NETLISTS, P8_MODELS, P8_STIMULUS; NOPOWER=1 skips
# the OpenSTA step (OpenSTA is installed locally only).
R=${P8_OUT:-$ROOT/results/P8}; N=${P8_NETLISTS:-$ROOT/results/P5f_gls/netlists}
M=${P8_MODELS:-$ROOT/results/P5f_gls/models/nangate45_cells_yosys.v}; S=${P8_STIMULUS:-$ROOT/results/P8/stimulus}
export LIB=${LIB:-$HOME/eda/pdk/nangate45/NangateOpenCellLibrary_typical.lib}
STA=${STA:-$HOME/eda/bin/sta}
PY=${PY:-python3}
TV="$PY -I $ROOT/tools/timev.py"
mkdir -p "$R"

power() {   # power <netlist> <out> [vcd t0 t1]
    NETLIST=$1 PERIOD_NS=2.0 VCD=${3:-} VCD_T0=${4:-0} VCD_T1=${5:-0} \
        $TV "$STA" -no_init -exit "$ROOT/synthesis/p8/power.tcl" > "$2" 2> "${2%.txt}_time.txt"
}

sim() {     # sim D M STIM WARM WIN MODEL SLICE
    local d=$1 m=$2 stim=$3 warm=$4 win=$5 model=${6:-gl} slice=${7:-}
    local run=d${d}_m${m}_${stim}${slice:+_$slice}_${model}_w${warm}_n${win}
    local w=$R/work/$run o=$R/sim/$run.txt; mkdir -p "$w" "$R/sim"
    local net=$N/d${d}_m${m}_500MHz/netlist.v src par=(-Ptb_power.CACHE_DEPTH=$d -Ptb_power.COUNTER_MODE=$m
          -Ptb_power.WARM=$warm -Ptb_power.WIN=$win -Ptb_power.STIM=$([ "$stim" = random ] && echo 0 || echo 1))
    local plus=()
    if [ "$stim" = criteo ]; then
        local tf=$S/$slice.hex
        plus+=("+trace=$tf" "+nreq=$(grep -c . "$tf")")
    fi
    if [ "$model" = rtl ]; then
        src=("$ROOT/rtl/v2/lfu_cache_controller.v" "$ROOT/synthesis/p8/tb_power.sv"); par+=(-DUSE_RTL)
    else
        $PY -I "$ROOT/tools/p5f_wrap.py" "$net" "$d" "$m" "$w" > /dev/null || { echo "wrap failed" > "$o"; return 1; }
        src=("$M" "$w/netlist_gl.v" "$ROOT/synthesis/p8/tb_power.sv")
    fi
    {
    echo "# P8 $run: zero-delay simulation, 500 MHz clock (2 ns), $model; fill data random (seed 1; real embedding data is not random)"
    echo "netlist: $([ "$model" = rtl ] && echo "RTL rtl/v2 (rtl-v2-final)" || echo "$net sha256 $(sha256sum "$net" | cut -c1-64)")"
    echo "iverilog: $(iverilog -V 2>&1 | head -n 1)"
    $TV iverilog -g2012 "${par[@]}" -o "$w/sim.vvp" "${src[@]}" > "$w/iverilog.txt" 2> "$w/compile_time.txt"
    echo "compile: $(grep -E 'Elapsed|Maximum resident' "$w/compile_time.txt" | awk -F': ' '{printf "%s ", $2}')"
    if [ "$model" = gl ]; then
        [ -e "$w/act.vcd" ] && mv "$w/act.vcd" "$w/act.vcd.old.$$"; mkfifo "$w/act.vcd"
        ( tee >(wc -c > "$w/vcd_raw_bytes") < "$w/act.vcd" | gzip -1 > "$w/act.vcd.gz" ) &
        local gz=$!
        $TV vvp -n "$w/sim.vvp" "${plus[@]}" "+vcd=$w/act.vcd" > "$w/vvp.txt" 2> "$w/run_time.txt"
        wait $gz; sleep 1
        echo "vcd: raw_bytes $(cat "$w/vcd_raw_bytes") gzip_bytes $(stat -c %s "$w/act.vcd.gz")"
    else
        $TV vvp -n "$w/sim.vvp" "${plus[@]}" > "$w/vvp.txt" 2> "$w/run_time.txt"
    fi
    echo "run: $(grep -E 'Elapsed|Maximum resident' "$w/run_time.txt" | awk -F': ' '{printf "%s ", $2}')"
    grep '^p8_power' "$w/vvp.txt" || { echo "SIMULATION FAILED"; tail -n 5 "$w/vvp.txt"; }
    } > "$o" 2>&1
    if [ "$model" = gl ] && [ -z "${NOPOWER:-}" ] && grep -q '^p8_power' "$w/vvp.txt"; then
        local t0 t1
        t0=$(grep -oP 't_begin_ps=\K\d+' "$w/vvp.txt"); t1=$(grep -oP 't_end_ps=\K\d+' "$w/vvp.txt")
        mkdir -p "$R/power"
        power "$net" "$R/power/$run.txt" "$w/act.vcd.gz" "$t0" "$t1"
    fi
}

case ${1:-} in
vectorless)
    mkdir -p "$R/power"
    for d in 16 64 256; do for m in 0 1; do
        power "$N/d${d}_m${m}_500MHz/netlist.v" "$R/power/d${d}_m${m}_vectorless.txt"
    done; done ;;
sim) shift; sim "$@" ;;
pilot)
    sim 16 0 random 20000 10000 glnovcd
    sim 16 0 random 20000 10000 gl ;;
*) echo "usage: see header"; exit 2 ;;
esac
