read_libs [list $::env(CORELIB) $::env(CLKLIB)]
read_hdl $::env(RTL_FILE)
elaborate -parameters [list [list CACHE_DEPTH $::env(DEPTH)] [list COUNTER_MODE $::env(MODE)]] $::env(TOP)
# merge-off experiment: genus_lfu.tcl runs merge the per-group req_addr copies (GLO-42). optimize_merge_seq false
# stops merging for these instances only; every other flop keeps the default (inherited from optimize_merge_flops).
# 320 = GROUPS x ADDR_WIDTH = 16 x 20 at the default parameters.
set grp [get_db insts *req_addr_grp_reg*]
puts "nomerge: [llength $grp] req_addr_grp_reg instances after elaborate"
if {[llength $grp] != 320} { puts "nomerge: expected 320 req_addr_grp_reg instances, stopping"; exit 1 }
set_db $grp .optimize_merge_seq false
read_sdc $::env(SDC_FILE)
set_db syn_generic_effort medium
set_db syn_map_effort medium
set_db syn_opt_effort medium
syn_generic
syn_map
syn_opt
file mkdir $::env(OUT)
report_timing > $::env(OUT)/timing.rpt
report_area   > $::env(OUT)/area.rpt
report_power  > $::env(OUT)/power.rpt
report_qor    > $::env(OUT)/qor.rpt
report_gates  > $::env(OUT)/gates.rpt
write_hdl > $::env(OUT)/netlist.v
write_sdc > $::env(OUT)/out.sdc
write_sdf -timescale ns -nonegchecks -recrem split -edges check_edge -setuphold split > $::env(OUT)/delays.sdf
exit
