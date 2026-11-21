#!/bin/csh -f
# P15: export_gls.tcl on finished PnR folders, one Innovus session at a time (one licence).
# usage: ./run_export.csh <PnR folder name in $W/pnr> ...   Start with systemd-run --user (it survives logout; nohup did not).
# Output: <folder>/gls/ and <folder>/export.log; counts of physical-only instances left in the netlist in gls/check.txt.
set W = $HOME/cadence_chipin_work/lfu_cache
source /opt/cadence/cshrc
foreach F ($argv)
  set RUN = `echo $F | sed -E 's/_pnr[0-9.]+(_.*)?$//'`
  set MODE = `echo $RUN | sed -E 's/^v[0-9]+_m([0-9]+)_.*/\1/'`
  set DEPTH = `echo $RUN | sed -E 's/^v[0-9]+_m[0-9]+_d([0-9]+)_.*/\1/'`
  setenv DIAG_TOP lfu_cache_controller_CACHE_DEPTH${DEPTH}_COUNTER_MODE${MODE}
  cd $W/pnr/$F
  innovus -nowin -files $W/pnr/export_gls.tcl -log export.log < /dev/null >& export.stdout
  grep -q "EXPORT DONE" export.stdout && echo "$F export done" || echo "$F export FAILED"
  echo "netlist_insts_FILL `grep -cE '^\s*\S+\s+FILL' gls/post_route.v`" > gls/check.txt
  echo "netlist_insts_ENDCAP `grep -cE '^\s*\S+\s+ENDCAP' gls/post_route.v`" >> gls/check.txt
  echo "netlist_insts_WT `grep -cE '^\s*\S+\s+WT' gls/post_route.v`" >> gls/check.txt
  grep -E "SDF VARIANT" export.stdout >> gls/check.txt
end
echo "EXPORT ALL DONE"
