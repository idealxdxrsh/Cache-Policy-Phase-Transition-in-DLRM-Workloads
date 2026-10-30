#!/bin/bash
# P12 sweep on C2: 12 sequential Genus runs, v2/v3 x mode 0/1 x depth 16/64/256, period 2.0 ns.
# One line per run in sweep.log; Genus stdout per run in sweep_logs/.
cd "$HOME/cadence_chipin_work/lfu_cache" || exit 1
mkdir -p sweep_logs
LOG=sweep.log
echo "start $(date '+%F %T')" >> $LOG
for ver in v2 v3; do
  for mode in 0 1; do
    for depth in 16 64 256; do
      run=${ver}_m${mode}_d${depth}_p2.0
      t0=$(date +%s)
      ./run_genus.csh $ver $mode $depth 2.0 < /dev/null > sweep_logs/$run.stdout 2>&1
      rc=$?
      n=0
      for r in timing area gates power qor; do [ -s results/$run/$r.rpt ] && n=$((n + 1)); done
      echo "$(date '+%F %T') $run exit=$rc reports=$n/5 wall_s=$(( $(date +%s) - t0 ))" >> $LOG
    done
  done
done
echo "done $(date '+%F %T')" >> $LOG
