#!/bin/csh -f
# P16 I/O hold diagnosis (p16_diag_io.tcl, read-only) of a finished PnR run; output in $W/p16/<source>_diag/.
# usage: ./run_p16_diag.csh <source run folder name in $W/pnr> [cpus]
# Start with systemd-run --user (see CLAUDE.md).
if ($#argv < 1) then
  echo "usage: $0 <source folder> [cpus]"
  exit 1
endif
set W = $HOME/cadence_chipin_work/lfu_cache
set SRC = $W/pnr/$1
set OUT = $W/p16/$1_diag
set CPUS = 16
if ($#argv >= 2) then
  set CPUS = $2
endif
source /opt/cadence/cshrc
source $W/local.env
if (-e $OUT/diag.log) then
  echo "$OUT holds a previous diagnosis; move it away first"
  exit 1
endif
set RUN = `echo $1 | sed -E 's/_pnr[0-9.]+(_.*)?$//'`
set MODE = `echo $RUN | sed -E 's/^v[0-9]+_m([0-9]+)_.*/\1/'`
set DEPTH = `echo $RUN | sed -E 's/^v[0-9]+_m[0-9]+_d([0-9]+)_.*/\1/'`
setenv PNR_TOP lfu_cache_controller_CACHE_DEPTH${DEPTH}_COUNTER_MODE${MODE}
setenv PNR_CPUS $CPUS
setenv P16_SRC $SRC
mkdir -p $OUT/rpt
cp -p $SRC/constraints.sdc $OUT/
cd $OUT
innovus -nowin -files $W/pnr/p16_diag_io.tcl -log diag.log < /dev/null >& diag.stdout
grep -q "P16 DIAG DONE" diag.stdout && echo "$1 P16 diag done" || echo "$1 P16 diag FAILED (see $OUT/diag.log)"
