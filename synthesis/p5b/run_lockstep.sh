#!/bin/bash
# Lockstep: rtl-v2-baseline vs current rtl/v2 at depths 16/64/256, modes 0/1. Local, small.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
W=$(mktemp -d); trap 'rm -r "$W"' EXIT
git -C "$ROOT" show rtl-v2-baseline:rtl/v2/lfu_cache_controller.v \
    | sed 's/^module lfu_cache_controller /module lfu_cache_controller_base /' > "$W/base.v"
grep -q '^module lfu_cache_controller_base ' "$W/base.v"
OUT=${OUT:-$ROOT/results/P5b/lockstep.txt}; : > "$OUT"
for d in 16 64 256; do for m in 0 1; do
    iverilog -g2012 -P tb_lockstep.CACHE_DEPTH=$d -P tb_lockstep.COUNTER_MODE=$m -o "$W/ls" \
        "$W/base.v" "$ROOT/rtl/v2/lfu_cache_controller.v" "$ROOT/synthesis/p5b/tb_lockstep.sv"
    vvp -n "$W/ls" | grep -v '^\$finish\|finish called' | tee -a "$OUT"
done; done
