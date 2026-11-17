#!/bin/csh -f
# P15 diagnosis of the PG-rail shorts: diag_shorts.tcl on the place, cts and route databases of each finished run,
# one Innovus session at a time (one licence), then which shorting instances are in the Genus netlist.
# usage: ./run_diag.csh <run folder name> ...   (folders in $W/pnr, e.g. v2_m0_d256_p0.8_nomerge_pnr0.8)
# Start with systemd-run --user (see CLAUDE.md). Output in each folder's rpt/ (diag_*.txt) and diag.log.
set W = $HOME/cadence_chipin_work/lfu_cache
source /opt/cadence/cshrc
foreach F ($argv)
  set D = $W/pnr/$F
  set RUN = `echo $F | sed -E 's/_pnr[0-9.]+(_.*)?$//'`
  set MODE = `echo $RUN | sed -E 's/^v[0-9]+_m([0-9]+)_.*/\1/'`
  set DEPTH = `echo $RUN | sed -E 's/^v[0-9]+_m[0-9]+_d([0-9]+)_.*/\1/'`
  setenv DIAG_TOP lfu_cache_controller_CACHE_DEPTH${DEPTH}_COUNTER_MODE${MODE}
  cd $D
  foreach DB (place cts route)
    setenv DIAG_DB $DB
    innovus -nowin -files $W/pnr/diag_shorts.tcl -log diag_$DB.log < /dev/null >& diag_$DB.stdout
    grep -q "DIAG DONE $DB" diag_$DB.stdout && echo "$F $DB done" || echo "$F $DB FAILED"
  end
  awk '{print $1}' rpt/diag_present_route.txt > rpt/diag_insts.txt
  if (-z rpt/diag_insts.txt) then
    touch rpt/diag_in_netlist.txt
  else
    grep -owF -f rpt/diag_insts.txt $W/results/$RUN/netlist.v | sort -u > rpt/diag_in_netlist.txt
  endif
  echo "$F netlist: `wc -l < rpt/diag_in_netlist.txt` of `wc -l < rpt/diag_insts.txt` shorting instances"
end
echo "DIAG ALL DONE"
