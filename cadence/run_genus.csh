#!/bin/csh -f
# usage: ./run_genus.csh <v2|v3> <mode> <depth> <period_ns>
set VER = $1
set MODE = $2
set DEPTH = $3
set PERIOD = $4
set W = $HOME/cadence_chipin_work/lfu_cache
source /opt/cadence/cshrc
# library dir and globs are set in $W/local.env (on C2 only, not in the repo)
source $W/local.env
setenv RTL_FILE $W/rtl/$VER/lfu_cache_controller.v
setenv TOP lfu_cache_controller
setenv MODE $MODE
setenv DEPTH $DEPTH
setenv OUT $W/results/${VER}_m${MODE}_d${DEPTH}_p${PERIOD}
mkdir -p $OUT
sed "s/PERIOD_PLACEHOLDER/$PERIOD/g" $W/constraints.sdc.in > $OUT/constraints.sdc
setenv SDC_FILE $OUT/constraints.sdc
setenv CORELIB `ls $CORELIB_GLOB`
setenv CLKLIB  `ls $CLKLIB_GLOB`
genus -f $W/genus_lfu.tcl -log $OUT/genus.log
