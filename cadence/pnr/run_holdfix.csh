#!/bin/csh -f
# P15 optional hold pass (holdfix.tcl) on a finished PnR run, output in a new folder.
# usage: ./run_holdfix.csh <source run folder name in $W/pnr> <new folder name in $W/pnr> [cpus]
# Start with systemd-run --user (it survives logout; nohup did not). Output: <new>/holdfix.log, holdfix.stdout, route.enc, rpt/.
# Optional environment (passed to holdfix.tcl): HOLDFIX_HOLD_TARGET (ns), HOLDFIX_DRC_RETRY (any value).
if ($#argv < 2) then
  echo "usage: $0 <source folder> <new folder> [cpus]"
  exit 1
endif
set W = $HOME/cadence_chipin_work/lfu_cache
set SRC = $W/pnr/$1
set OUT = $W/pnr/$2
set CPUS = 16
if ($#argv >= 3) then
  set CPUS = $3
endif
source /opt/cadence/cshrc
source $W/local.env
if (-e $OUT/holdfix.log) then
  echo "$OUT holds a previous hold pass; move it away first"
  exit 1
endif
set RUN = `echo $1 | sed -E 's/_pnr[0-9.]+(_.*)?$//'`
set MODE = `echo $RUN | sed -E 's/^v[0-9]+_m([0-9]+)_.*/\1/'`
set DEPTH = `echo $RUN | sed -E 's/^v[0-9]+_m[0-9]+_d([0-9]+)_.*/\1/'`
setenv PNR_TOP lfu_cache_controller_CACHE_DEPTH${DEPTH}_COUNTER_MODE${MODE}
setenv PNR_CPUS $CPUS
setenv HOLDFIX_SRC $SRC
mkdir -p $OUT/rpt
cp -p $SRC/constraints.sdc $SRC/rpt/multirow.txt $SRC/rpt/corners.txt $OUT/rpt/ 
mv $OUT/rpt/constraints.sdc $OUT/
cd $OUT
innovus -nowin -files $W/pnr/holdfix.tcl -log holdfix.log < /dev/null >& holdfix.stdout
grep -q "HOLDFIX DONE" holdfix.stdout && echo "$2 done" || echo "$2 FAILED (see $OUT/holdfix.log)"
