#!/bin/bash
# P12 stream driver on C2. usage: run_stream.sh <stream> <ver> <mode>
# Runs depth 256, 64, 16 at period 2.0 ns sequentially; skips a run whose results folder already has timing.rpt.
# One line per run in sweep_<stream>.log; Genus runs in work_<stream>/ so parallel streams do not share fv/.
S=$1; VER=$2; MODE=$3
W=$HOME/cadence_chipin_work/lfu_cache
mkdir -p "$W/sweep_logs" "$W/work_$S"
cd "$W/work_$S" || exit 1
LOG=$W/sweep_$S.log
echo "$(date '+%F %T') stream $S: $VER mode $MODE, driver pid $$" >> $LOG
for depth in 256 64 16; do
  run=${VER}_m${MODE}_d${depth}_p2.0
  if [ -s "$W/results/$run/timing.rpt" ]; then
    echo "$(date '+%F %T') $run skipped (timing.rpt exists)" >> $LOG
    continue
  fi
  start=$(date '+%F %T'); t0=$(date +%s)
  "$W/run_genus.csh" $VER $MODE $depth 2.0 < /dev/null > "$W/sweep_logs/$run.stdout" 2>&1
  rc=$?
  n=0
  for r in timing area gates power qor; do [ -s "$W/results/$run/$r.rpt" ] && n=$((n + 1)); done
  echo "start=$start $run exit=$rc reports=$n/5 wall_s=$(( $(date +%s) - t0 ))" >> $LOG
done
echo "$(date '+%F %T') stream $S done" >> $LOG
