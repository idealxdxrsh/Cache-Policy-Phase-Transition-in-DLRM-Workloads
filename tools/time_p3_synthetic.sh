#!/bin/bash
# Local timing of the P3 array-task path on SYNTHETIC Criteo-format data.
# Every task runs exactly as one sbatch array task would: one table,
# all policies + Belady, all capacities, 4 workers, one at a time.
#   bash tools/time_p3_synthetic.sh <scratch_dir>
# Writes results/P3_prep/timing_{2M,10M}/ (per-table JSON + /usr/bin/time logs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$1"; mkdir -p "$S"
SIM="$ROOT/trace_sim/run_trace_sim.py"
PY=python3
WORKERS=4

run_size() {   # $1 = label, $2 = rows, $3.. = tables
    local label=$1 rows=$2; shift 2
    local out="$ROOT/results/P3_prep/timing_$label" data="$S/synth_$label.txt" tr="$S/traces_$label"
    mkdir -p "$out"
    [ -f "$data" ] || $PY "$ROOT/tools/gen_synthetic_criteo.py" --rows "$rows" --seed 0 --out "$data"
    /usr/bin/time -v $PY "$SIM" --criteo_path "$data" --n_rows "$rows" --dump_traces "$tr" \
        > "$out/dump_log.txt" 2> "$out/dump_time.txt"
    for t in "$@"; do
        tag=$(printf 'table_%02d' "$t")
        /usr/bin/time -v $PY "$SIM" --trace_dir "$tr" --tables "$t" --belady \
            --workers $WORKERS --output "$out" --tag "$tag" \
            > "$out/${tag}_log.txt" 2> "$out/${tag}_time.txt"
        echo "$label $tag $(grep -E 'Elapsed' "$out/${tag}_time.txt" | awk '{print $NF}')"
    done
}

run_size 2M 2000000 $(seq 0 25)
run_size 10M 10000000 0 12 25
