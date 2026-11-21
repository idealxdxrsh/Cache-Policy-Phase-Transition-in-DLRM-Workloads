#!/bin/csh -f
# P15 place and route on C2 with Innovus (batch, one session: stageA.tcl then stageB.tcl, see pnr.tcl).
# usage: ./run_pnr.csh <run> <period_ns> [cpus]
#   <run>: a Genus results folder in $W/results, e.g. v3_m0_d16_p0.8 or v2_m0_d256_p0.8_nomerge; its netlist.v is
#          placed and routed. Depth and mode are read from the name (top cell lfu_cache_controller_CACHE_DEPTH<d>_
#          COUNTER_MODE<m>, as written by Genus).
#   <period_ns>: PnR clock period; the SDC is $W/constraints.sdc.in with this period (same template as synthesis).
#   [cpus]: setMultiCpuUsage -localCpu (default 8).
# Output: $W/pnr/<run>_pnr<period>/ with stageA.log (whole session), fp.enc, place.enc, cts.enc, route.enc, rpt/.
# Library paths, cell names, the site name and the body-bias pin names come from $W/local.env (on C2 only, not in
# the repo). Variables used here besides CORELIB_GLOB and CLKLIB_GLOB (all globs are expanded in Tcl):
#   PRLIB_GLOB          liberty of the physical-cell library (optional)
#   PNR_TECH_LEFS       technology, via-rule and site LEF files (globs, in this order)
#   PNR_CELL_LEFS       cell LEF files (globs)
#   PNR_QRC_GLOB        RC extraction tech file, nominal corner
#   PNR_SITE            core site name
#   PNR_BODY_PWR        body-bias pin and net name, power side; PNR_BODY_GND the ground side
#   PNR_ENDCAP_LR       end cap for left and right row ends
#   PNR_ENDCAP_TOP      end caps for the top row (list, widest first); PNR_ENDCAP_BOTTOM for the bottom row
#   PNR_WELLTAP         well-tap cell (has the body-bias pins)
#   PNR_FILLERS         filler cells (list, widest first)
#   PNR_CTS_BUF_PAT     get_lib_cells pattern for the clock-tree buffers; PNR_CTS_INV_PAT for the inverters
# Optional environment: PNR_TAG (folder suffix), PNR_BODY_MODE (route|convert, see stageA.tcl);
#   PNR_ENDCAP_CORNER_TL, _TR, _BL, _BR  corner end caps (optional, stageA.tcl)
# Long runs: start with systemd-run --user (it survives logout; nohup did not), e.g.
#   mkdir -p $W/pnr/<run>_pnr<p>; systemd-run --user --unit=<name> csh -fc 'cd $W/pnr/<run>_pnr<p>; csh -f $W/pnr/run_pnr.csh <run> <p> 16 >& job.log'
# Started directly over ssh instead, the job dies when that session ends.
if ($#argv < 2) then
  echo "usage: $0 <run> <period_ns> [cpus]"
  exit 1
endif
set RUN = $1
set PERIOD = $2
set CPUS = 8
if ($#argv >= 3) set CPUS = $3
set W = $HOME/cadence_chipin_work/lfu_cache
source /opt/cadence/cshrc
source $W/local.env
set MODE = `echo $RUN | sed -E 's/^v[0-9]+_m([0-9]+)_.*/\1/'`
set DEPTH = `echo $RUN | sed -E 's/^v[0-9]+_m[0-9]+_d([0-9]+)_.*/\1/'`
if (! -f $W/results/$RUN/netlist.v) then
  echo "no netlist $W/results/$RUN/netlist.v"
  exit 1
endif
setenv PNR_DIR $W/pnr
setenv PNR_NETLIST $W/results/$RUN/netlist.v
setenv PNR_TOP lfu_cache_controller_CACHE_DEPTH${DEPTH}_COUNTER_MODE${MODE}
setenv PNR_CPUS $CPUS
set OUT = $W/pnr/${RUN}_pnr$PERIOD
if ($?PNR_TAG) then
  set OUT = ${OUT}_$PNR_TAG
endif
# the folder may already exist (systemd-run launch writes job.log into it first); refuse only a previous run
if (-e $OUT/stageA.log) then
  echo "$OUT holds a previous run; move it away first"
  exit 1
endif
mkdir -p $OUT/rpt
sed "s/PERIOD_PLACEHOLDER/$PERIOD/g" $W/constraints.sdc.in > $OUT/constraints.sdc
setenv PNR_SDC $OUT/constraints.sdc
cd $OUT
innovus -nowin -files $W/pnr/pnr.tcl -log stageA.log < /dev/null >& innovus.stdout
grep -q "PNR DONE" innovus.stdout && echo "$RUN $PERIOD done" || echo "$RUN $PERIOD FAILED (see $OUT/stageA.log)"
