#!/bin/bash
# P5: Yosys 0.33 + NanGate45 liberty + OpenSTA on rtl/v2, local (no cluster).
# NanGate45, not TSMC. Pre-layout. No power step.
#   bash synthesis/p5/run_p5.sh [depths...]     default: 16 64 256
# Liberty and sta paths: results/P5/SOURCES.md.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
LIB=${LIB:-$HOME/eda/pdk/nangate45/NangateOpenCellLibrary_typical.lib}
STA=${STA:-$HOME/eda/bin/sta}
PY=${PY:-python3}
DEPTHS=${*:-"16 64 256"}
for d in $DEPTHS; do
  for m in 0 1; do
    for f in 1000 500; do
      p=$((1000000 / f))                     # period in ps
      out=$ROOT/results/P5/d${d}_m${m}_${f}MHz; mkdir -p "$out"
      sed -e "s|@D@|$d|g; s|@M@|$m|g; s|@P@|$p|g; s|@LIB@|$LIB|g; s|@OUT@|$out|g" \
          -e "s|@RTL@|$ROOT/rtl/v2/lfu_cache_controller.v|g; s|@CONSTR@|$ROOT/synthesis/p5/abc.constr|g" "$ROOT/synthesis/p5/synth.ys.in" > "$out/synth.ys"
      "$PY" -I "$ROOT/tools/timev.py" yosys -q -l "$out/yosys.log" "$out/synth.ys" 2> "$out/time_yosys.txt"
      LIB=$LIB OUT=$out PERIOD_NS=$(awk "BEGIN{print $p/1000}") \
          "$PY" -I "$ROOT/tools/timev.py" "$STA" -no_init -exit "$ROOT/synthesis/p5/sta.tcl" \
          > "$out/sta.txt" 2> "$out/time_sta.txt"
      echo "d=$d m=$m ${f}MHz: $(grep -m1 '^wns' "$out/sta.txt")"
    done
  done
done
