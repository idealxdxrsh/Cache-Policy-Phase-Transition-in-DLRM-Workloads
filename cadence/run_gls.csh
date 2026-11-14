#!/bin/csh -f
# P13 gate-level simulation on C2 with xrun.
# usage: ./run_gls.csh <run> <row0|row1M> <zero|sdf> [nreq [sdf_file]]
#   <run>: a results folder, e.g. v3_m0_d256_p0.8_nomerge; version, mode and depth are read from its name.
#   zero: no SDF, specify blocks ignored, timing checks off, zero gate delays; inputs driven at half period (P11).
#   sdf:  results/<run>/<sdf_file> (default delays.sdf) annotated, timing checks on; inputs driven 0.2 x period
#         after the rising edge (the SDC input delay); timing violations counted in the xrun log; SDF log sdf.log
#         (-sdf_verbose) and annotation statistics sdfstats.txt in the run directory.
#   With GLS_TCF set in the environment: switching activity of the netlist instance in activity.tcf
#   (xmsim dumptcf -scope tb_gls_c2.gl -eot, written at the end of the simulation; -access +r); folder suffix _tcf.
# Clock period 0.8 ns in both modes (PERIOD_PS = 800, timescale 1ps). Compiles the netlist unchanged, the three main
# cell models (globs GLS_*_V_GLOB in $W/local.env, on C2 only), the run's RTL and synthesis/p13/tb_gls_c2.sv.
# Output: $W/p13/runs/<run>_<slice>_<mode>[_n<nreq>]/ with xrun.log, hits_rtl.txt, hits_gl.txt, summary.txt.
# The reference hit log is the P9 (v2) / P10 (v3) RTL log of the slice, first <nreq> lines.
set RUN = $1
set SLICE = $2
set GMODE = $3
set W = $HOME/cadence_chipin_work/lfu_cache
source /opt/cadence/cshrc
source $W/local.env
set VER = `echo $RUN | sed -E 's/^(v[0-9]+)_.*/\1/'`
set MODE = `echo $RUN | sed -E 's/^v[0-9]+_m([0-9]+)_.*/\1/'`
set DEPTH = `echo $RUN | sed -E 's/^v[0-9]+_m[0-9]+_d([0-9]+)_.*/\1/'`
set TRACE = $W/p13/stim/$SLICE.hex
set REF = $W/p13/ref/${VER}_d${DEPTH}_m${MODE}_$SLICE.hits.gz
set NREQ = `grep -c . $TRACE`
set TAG = ${RUN}_${SLICE}_$GMODE
if ($#argv >= 4) then
    set NREQ = $4
    set TAG = ${TAG}_n$NREQ
endif
set SDFN = delays.sdf
if ($#argv >= 5) then
    set SDFN = $5
    set TAG = ${TAG}_$SDFN:r
endif
set PERIOD_PS = 800
if ($GMODE == zero) then
    set IN_PS = 400
    set OPTS = (-nospecify -notimingchecks -delay_mode zero)
else if ($GMODE == sdf) then
    set IN_PS = 160
    set OPTS = (-define GLS_SDF -sdf_verbose -sdfstats sdfstats.txt)
else
    echo "mode must be zero or sdf"
    exit 1
endif
if ($?GLS_TCF) set TAG = ${TAG}_tcf
set OUT = $W/p13/runs/$TAG
mkdir -p $OUT
cd $OUT
if ($?GLS_TCF) then
    echo "dumptcf -scope tb_gls_c2.gl -eot -output activity.tcf -overwrite" > tcf.tcl
    echo "run" >> tcf.tcl
    echo "exit" >> tcf.tcl
    set OPTS = ($OPTS -access +r -input tcf.tcl)
endif
if ($GMODE == sdf) ln -sf $W/results/$RUN/$SDFN delays.sdf
set CORE_V = `ls $GLS_CORE_V_GLOB`
set CLK_V = `ls $GLS_CLK_V_GLOB`
set PR_V = `ls $GLS_PR_V_GLOB`
set NETLIST = $W/results/$RUN/netlist.v
set RTL = $W/rtl/$VER/lfu_cache_controller.v
set TB = $W/p13/tb/tb_gls_c2.sv
set T0 = `date +%s`
xrun -64bit -sv -timescale 1ps/1ps -l xrun.log $OPTS \
    -define GL_MODULE=lfu_cache_controller_CACHE_DEPTH${DEPTH}_COUNTER_MODE$MODE \
    -defparam tb_gls_c2.CACHE_DEPTH=$DEPTH -defparam tb_gls_c2.COUNTER_MODE=$MODE \
    -defparam tb_gls_c2.PERIOD_PS=$PERIOD_PS -defparam tb_gls_c2.IN_PS=$IN_PS \
    $NETLIST -v $CORE_V -v $CLK_V -v $PR_V $RTL $TB -top tb_gls_c2 \
    +trace=$TRACE +nreq=$NREQ +hitlog=hits_rtl.txt +gl_hitlog=hits_gl.txt < /dev/null >& xrun.stdout
set RC = $status
set T1 = `date +%s`
@ WALL = $T1 - $T0
zcat $REF | head -n $NREQ > ref.txt
set DR = `paste -d'|' ref.txt hits_rtl.txt | awk -F'|' '$1 == $2 {next} {n++} END {print n+0}'`
set DG = `paste -d'|' ref.txt hits_gl.txt | awk -F'|' '$1 == $2 {next} {n++} END {print n+0}'`
echo "# P13 gls ${TAG}: $VER netlist results/$RUN in lockstep with $VER RTL, mode $GMODE, period $PERIOD_PS ps, inputs $IN_PS ps after the rising edge" > summary.txt
echo "netlist sha256 `sha256sum < $NETLIST | cut -c1-64`" >> summary.txt
echo "rtl sha256 `sha256sum < $RTL | cut -c1-64`" >> summary.txt
echo "tb sha256 `sha256sum < $TB | cut -c1-64`" >> summary.txt
echo "trace $SLICE sha256 `sha256sum < $TRACE | cut -c1-64`, requests replayed $NREQ" >> summary.txt
echo "xrun exit=$RC wall_s=$WALL" >> summary.txt
grep -E '^gls_c2 |LOCKSTEP' xrun.log >> summary.txt
echo "reference ${VER}_d${DEPTH}_m${MODE}_$SLICE (first $NREQ lines): hits_rtl lines `wc -l < hits_rtl.txt` differing $DR; hits_gl lines `wc -l < hits_gl.txt` differing $DG" >> summary.txt
if ($GMODE == sdf) then
    echo "sdf file: results/$RUN/$SDFN" >> summary.txt
    grep -A2 'SDF statistics' xrun.log >> summary.txt
    echo "timing violations: `grep -c 'Timing violation' xrun.log`" >> summary.txt
    echo "sdf.log message ids (count):" >> summary.txt
    grep -o -E '\*[WEF],[A-Z0-9]+' sdf.log | sort | uniq -c >> summary.txt
endif
if ($?GLS_TCF) echo "tcf: activity.tcf `stat -c %s activity.tcf` bytes" >> summary.txt
echo "xrun message ids (count):" >> summary.txt
grep -o -E '\*[WEF],[A-Z0-9]+' xrun.log | sort | uniq -c >> summary.txt
