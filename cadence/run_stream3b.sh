#!/bin/bash
# P12 third sweep, restart after the interruption, on C2. usage: run_stream3b.sh <ver> <mode>
# Runs depth 256, 64, 16 (in that order), each at period 0.8, 0.65 then 0.5 ns, sequentially, skipping every
# complete run: all 5 reports non-empty, genus.log reached the script's exit (line 20) and the stdout ends with
# "Normal exit.". One line per run in sweep3b_<ver>m<mode>.log; Genus runs in work3b_<ver>m<mode>/.
VER=$1; MODE=$2; S=${VER}m${MODE}
W=$HOME/cadence_chipin_work/lfu_cache
mkdir -p "$W/sweep_logs" "$W/work3b_$S"
cd "$W/work3b_$S" || exit 1
LOG=$W/sweep3b_$S.log
nrep() { local n=0 r; for r in timing area gates power qor; do [ -s "$W/results/$1/$r.rpt" ] && n=$((n + 1)); done; echo $n; }
complete() {
  [ "$(nrep $1)" -eq 5 ] && grep -q '^@file(genus_lfu.tcl) 20: exit' "$W/results/$1/genus.log" 2>/dev/null &&
    [ "$(tail -n 1 "$W/sweep_logs/$1.stdout" 2>/dev/null)" = "Normal exit." ]
}
echo "$(date '+%F %T') stream $S: $VER mode $MODE, driver pid $$" >> $LOG
for depth in 256 64 16; do
  for period in 0.8 0.65 0.5; do
    run=${VER}_m${MODE}_d${depth}_p${period}
    if complete $run; then
      echo "$(date '+%F %T') $run skipped (complete)" >> $LOG
      continue
    fi
    start=$(date '+%F %T'); t0=$(date +%s)
    "$W/run_genus.csh" $VER $MODE $depth $period < /dev/null > "$W/sweep_logs/$run.stdout" 2>&1
    rc=$?
    c=no; complete $run && c=yes
    echo "start=$start $run exit=$rc reports=$(nrep $run)/5 complete=$c wall_s=$(( $(date +%s) - t0 ))" >> $LOG
  done
done
echo "$(date '+%F %T') stream $S done" >> $LOG
