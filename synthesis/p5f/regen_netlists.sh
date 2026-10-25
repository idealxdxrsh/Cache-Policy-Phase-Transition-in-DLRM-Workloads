#!/bin/bash
# P5f: regenerate the P5e-flow netlists of rtl-v2-final (depths 16/64/256 x modes 0/1 x 1 GHz/500 MHz) into
# results/P5f_gls/netlists/, with exactly the settings of synthesis/p5e/run_p5e.sh (its export line is reused).
# Local only. NanGate45, not TSMC. Pre-layout.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
R=$ROOT/results/P5f_gls/netlists; mkdir -p "$R"
eval "$(grep '^export YS_IN=' "$ROOT/synthesis/p5e/run_p5e.sh")"
git -C "$ROOT" diff --quiet rtl-v2-final -- rtl/v2/lfu_cache_controller.v || { echo "rtl/v2 differs from rtl-v2-final"; exit 1; }
{ echo "rtl: $(git -C "$ROOT" rev-parse rtl-v2-final^{commit}) (tag rtl-v2-final), rtl/v2/lfu_cache_controller.v"
  echo "flow: synthesis/p5e + synthesis/p5 at commit $(git -C "$ROOT" log -1 --format=%H -- synthesis/p5e synthesis/p5)"
  echo "ABC_BUDGET_PS=$ABC_BUDGET_PS"
  (cd "$ROOT" && sha256sum synthesis/p5e/synth_td.ys.in synthesis/p5e/abc_td.script.in synthesis/p5/run_p5.sh synthesis/p5/abc.constr synthesis/p5/sta.tcl)
  echo "yosys: $(yosys -V)"; } > "$R/FLOW_VERSION.txt"
for d in 256 64 16; do for m in 0 1; do for f in 1000 500; do echo "$d $m $f"; done; done; done |
    xargs -P "${JOBS:-8}" -L 1 bash -c 'OUTDIR=results/P5f_gls/netlists MODES=$2 FREQS=$3 bash "$0/synthesis/p5/run_p5.sh" $1' "$ROOT" \
    > "$R/run_synth.txt" 2>&1
sort -o "$R/run_synth.txt" "$R/run_synth.txt"
gzip -f "$R"/d*/yosys.log
(cd "$R" && sha256sum d*/netlist.v > netlists.sha256)
