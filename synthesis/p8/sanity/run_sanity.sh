#!/bin/bash
# P8 power-flow sanity check, local, seconds. Writes results/P8/sanity/*.txt.
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(cd ../../.. && pwd); R=$ROOT/results/P8/sanity; mkdir -p "$R"
export LIB=${LIB:-$HOME/eda/pdk/nangate45/NangateOpenCellLibrary_typical.lib}
STA=${STA:-$HOME/eda/bin/sta}
W=$(mktemp -d)
cp inv_power.v power_common.tcl "$W"/
iverilog -g2012 -o "$W/tb.vvp" "$ROOT/results/P5f_gls/models/nangate45_cells_yosys.v" inv_power.v tb_inv_power.v
(cd "$W" && vvp -n tb.vvp > /dev/null && gzip -f inv_power.vcd)
{ echo "# iverilog: $(iverilog -V 2>&1 | head -n 1)"; { zcat "$W/inv_power.vcd.gz" | head -n 40 || true; }; echo ...; echo "value-change lines: $(zcat "$W/inv_power.vcd.gz" | grep -c '^[01]')"; } > "$R/vcd_head.txt"
for t in vectorless_default vectorless_set vcd; do
  cp "$t.tcl" "$W"/; (cd "$W" && "$STA" -no_init -exit "$t.tcl") > "$R/$t.txt" 2>&1
done
echo "OpenSTA: $("$STA" -version)" > "$R/versions.txt"
rm -r "$W"
