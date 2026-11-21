#!/bin/csh -f
# P16 multi-corner timing (p16_corners.tcl) of a finished PnR run; output in a new folder, the source run is not changed.
# usage: ./run_p16.csh <source run folder name in $W/pnr> [cpus]
# Output: $W/p16/<source>/ with p16.log, p16.stdout, rpt/{tt,ss,ff}/{setup,hold}/, rpt/p16_settings.txt.
# Start with systemd-run --user (it survives logout; nohup did not), e.g.
#   systemd-run --user --unit=p16-<name> csh -fc 'csh -f $W/pnr/run_p16.csh <source> 16 >& $W/p16/<source>.job.log'
if ($#argv < 1) then
  echo "usage: $0 <source folder> [cpus]"
  exit 1
endif
set W = $HOME/cadence_chipin_work/lfu_cache
set SRC = $W/pnr/$1
set OUT = $W/p16/$1
set CPUS = 16
if ($#argv >= 2) then
  set CPUS = $2
endif
source /opt/cadence/cshrc
source $W/local.env
if (! -e $SRC/route.enc.dat) then
  echo "$SRC/route.enc.dat not found"
  exit 1
endif
if (-e $OUT/p16.log) then
  echo "$OUT holds a previous P16 run; move it away first"
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
innovus -nowin -files $W/pnr/p16_corners.tcl -log p16.log < /dev/null >& p16.stdout
grep -q "P16 DONE" p16.stdout && echo "$1 P16 done" || echo "$1 P16 FAILED (see $OUT/p16.log)"
