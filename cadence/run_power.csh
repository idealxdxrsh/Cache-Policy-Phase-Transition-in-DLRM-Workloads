#!/bin/csh -f
# usage: ./run_power.csh <run> <gls_folder> <tcf_instance>
#   e.g. ./run_power.csh v3_m0_d256_p0.8_nomerge v3_m0_d256_p0.8_nomerge_row0_sdf_tcf <instance name in the TCF>
# genus_power.tcl on results/<run>/netlist.v and constraints.sdc with p13/runs/<gls_folder>/activity.tcf; writes
# power_tcf.rpt, sdb_annotation.rpt and genus_power.log into p13/runs/<gls_folder>/. Genus runs in p13/work_pwr_<gls_folder>/.
# Optional overrides (P15 post-route power; unset = P13 behaviour): PWR_NETLIST, PWR_SDC, PWR_SPEF (parasitics read
# with read_spef), PWR_GLS_ROOT (folder holding <gls_folder>, instead of $W/p13/runs).
set RUN = $1
set GF = $2
set W = $HOME/cadence_chipin_work/lfu_cache
source /opt/cadence/cshrc
# library dir and globs are set in $W/local.env (on C2 only, not in the repo)
source $W/local.env
set MODE = `echo $RUN | sed -E 's/^v[0-9]+_m([0-9]+)_.*/\1/'`
set DEPTH = `echo $RUN | sed -E 's/^v[0-9]+_m[0-9]+_d([0-9]+)_.*/\1/'`
setenv NETLIST $W/results/$RUN/netlist.v
setenv TOP lfu_cache_controller_CACHE_DEPTH${DEPTH}_COUNTER_MODE$MODE
setenv SDC_FILE $W/results/$RUN/constraints.sdc
set GROOT = $W/p13/runs
if ($?PWR_GLS_ROOT) then
    set GROOT = $PWR_GLS_ROOT
endif
if ($?PWR_NETLIST) then
    setenv NETLIST $PWR_NETLIST
endif
if ($?PWR_SDC) then
    setenv SDC_FILE $PWR_SDC
endif
if ($?PWR_SPEF) then
    setenv SPEF_FILE $PWR_SPEF
endif
setenv TCF_FILE $GROOT/$GF/activity.tcf
setenv TCF_INSTANCE $3
setenv OUT $GROOT/$GF
setenv CORELIB `ls $CORELIB_GLOB`
setenv CLKLIB  `ls $CLKLIB_GLOB`
mkdir -p $W/p13/work_pwr_$GF
cd $W/p13/work_pwr_$GF
genus -f $W/genus_power.tcl -log $OUT/genus_power.log
