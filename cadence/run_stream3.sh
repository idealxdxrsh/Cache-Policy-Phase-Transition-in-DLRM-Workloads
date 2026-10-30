#!/bin/bash
# P12 third sweep, one stream per version and mode, on C2. usage: run_stream3.sh <ver> <mode>
# Runs depth 256, 64, 16 (in that order), each at period 0.8, 0.65 then 0.5 ns, sequentially; skips a run whose
# results folder already has a non-empty timing.rpt. One line per run in sweep3_<ver>m<mode>.log;
# Genus runs in work3_<ver>m<mode>/ so parallel streams do not share fv/.
VER=$1; MODE=$2; S=${VER}m${MODE}
W=$HOME/cadence_chipin_work/lfu_cache
mkdir -p "$W/sweep_logs" "$W/work3_$S"
cd "$W/work3_$S" || exit 1
LOG=$W/sweep3_$S.log
echo "$(date '+%F %T') stream $S: $VER mode $MODE, driver pid $$" >> $LOG
for depth in 256 64 16; do
  for period in 0.8 0.65 0.5; do
    run=${VER}_m${MODE}_d${depth}_p${period}
    if [ -s "$W/results/$run/timing.rpt" ]; then
      echo "$(date '+%F %T') $run skipped (timing.rpt exists)" >> $LOG
      continue
    fi
    start=$(date '+%F %T'); t0=$(date +%s)
    "$W/run_genus.csh" $VER $MODE $depth $period < /dev/null > "$W/sweep_logs/$run.stdout" 2>&1
    rc=$?
    n=0
    for r in timing area gates power qor; do [ -s "$W/results/$run/$r.rpt" ] && n=$((n + 1)); done
    echo "start=$start $run exit=$rc reports=$n/5 wall_s=$(( $(date +%s) - t0 ))" >> $LOG
  done
done
echo "$(date '+%F %T') stream $S done" >> $LOG
