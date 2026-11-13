#!/bin/bash
# P12 merge-off experiment on C2. usage: run_nomerge.sh
# v2 m0 and v3 m0 at depth 256, each at period 0.8 then 0.65 ns; the two versions run in parallel (2 Genus jobs at a
# time) with genus_lfu_nomerge.tcl into results/<run>_nomerge/, each version in work_nomerge_<ver>/ (same design name).
# Refuses to start if more than 2 Genus jobs are already running, so the total stays at 4 or fewer. Skips a run that
# is complete (5 reports non-empty, genus.log reached the script's exit, stdout ends with "Normal exit.").
# One line per run in sweep_nomerge.log, with the number of req_addr_grp_reg flip-flops in netlist.v and whether it is 320.
W=$HOME/cadence_chipin_work/lfu_cache
LOG=$W/sweep_nomerge.log
mkdir -p "$W/sweep_logs"
running=$(ps -u "$USER" -o args | grep -c -E '^[^ ]*genus -f ')
if [ "$running" -gt 2 ]; then
  echo "$(date '+%F %T') not started: $running Genus jobs already running (limit 4 including these 2)" >> $LOG
  exit 1
fi
nrep() { local n=0 r; for r in timing area gates power qor; do [ -s "$W/results/$1/$r.rpt" ] && n=$((n + 1)); done; echo $n; }
complete() {
  [ "$(nrep $1)" -eq 5 ] && grep -q -E '^@file\(genus_lfu_nomerge\.tcl\) [0-9]+: exit$' "$W/results/$1/genus.log" 2>/dev/null &&
    [ "$(tail -n 1 "$W/sweep_logs/$1.stdout" 2>/dev/null)" = "Normal exit." ]
}
grp() { grep -o -E 'req_addr_grp_reg\[[0-9]+\]\[[0-9]+\]' "$W/results/$1/netlist.v" 2>/dev/null | sort -u | wc -l; }
stream() {
  local VER=$1 period run start t0 rc c n ok
  mkdir -p "$W/work_nomerge_$VER"
  cd "$W/work_nomerge_$VER" || return 1
  for period in 0.8 0.65; do
    run=${VER}_m0_d256_p${period}_nomerge
    if complete $run; then
      echo "$(date '+%F %T') $run skipped (complete)" >> $LOG
      continue
    fi
    start=$(date '+%F %T'); t0=$(date +%s)
    "$W/run_genus_nomerge.csh" $VER 0 256 $period < /dev/null > "$W/sweep_logs/$run.stdout" 2>&1
    rc=$?
    c=no; complete $run && c=yes
    n=$(grp $run); ok=no; [ "$n" -eq 320 ] && ok=yes
    echo "start=$start $run exit=$rc reports=$(nrep $run)/5 complete=$c req_addr_grp_flops=$n is_320=$ok" \
         "wall_s=$(( $(date +%s) - t0 ))" >> $LOG
  done
}
echo "$(date '+%F %T') merge-off driver pid $$ (Genus jobs running before start: $running)" >> $LOG
stream v2 &
stream v3 &
wait
echo "$(date '+%F %T') merge-off done" >> $LOG
