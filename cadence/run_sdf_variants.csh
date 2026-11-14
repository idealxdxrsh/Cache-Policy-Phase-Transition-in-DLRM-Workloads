#!/bin/csh -f
# usage: ./run_sdf_variants.csh <run> <variant>...   e.g. ./run_sdf_variants.csh v3_m0_d256_p0.8_nomerge a b c
# genus_write_sdf.tcl on results/<run>/netlist.v and constraints.sdc; writes results/<run>/delays_<v>.sdf,
# timing_reread.rpt and genus_sdf_variants.log. Genus runs in p13/work_sdf_<run>/.
set RUN = $1
set W = $HOME/cadence_chipin_work/lfu_cache
source /opt/cadence/cshrc
# library dir and globs are set in $W/local.env (on C2 only, not in the repo)
source $W/local.env
set MODE = `echo $RUN | sed -E 's/^v[0-9]+_m([0-9]+)_.*/\1/'`
set DEPTH = `echo $RUN | sed -E 's/^v[0-9]+_m[0-9]+_d([0-9]+)_.*/\1/'`
setenv NETLIST $W/results/$RUN/netlist.v
setenv TOP lfu_cache_controller_CACHE_DEPTH${DEPTH}_COUNTER_MODE$MODE
setenv SDC_FILE $W/results/$RUN/constraints.sdc
setenv OUT $W/results/$RUN
setenv VARIANTS "$argv[2-]"
setenv CORELIB `ls $CORELIB_GLOB`
setenv CLKLIB  `ls $CLKLIB_GLOB`
mkdir -p $W/p13/work_sdf_$RUN
cd $W/p13/work_sdf_$RUN
genus -f $W/genus_write_sdf.tcl -log $OUT/genus_sdf_variants.log
