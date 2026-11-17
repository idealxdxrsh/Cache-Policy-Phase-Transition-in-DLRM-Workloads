# P15 stage B: placement, clock tree, routing, optimisation, fillers, reports. Runs in the stage A session (pnr.tcl).
# trim before any regular PG routing exists (on a routed design editTrim cuts the body-pin wires)
editTrim -nets $PG
# clock tree: only the clock library's buffers and inverters
set bufs {}
set invs {}
foreach c [get_object_name [get_lib_cells $env(PNR_CTS_BUF_PAT)]] { lappend bufs [file tail $c] }
foreach c [get_object_name [get_lib_cells $env(PNR_CTS_INV_PAT)]] { lappend invs [file tail $c] }
foreach c [concat $bufs $invs] { setDontUse $c false }
# multi-row cells stay dont_use (stage A), also if a clock-tree pattern matched one
foreach c $MULTIROW { setDontUse $c true }
set bufs [lmap c $bufs { expr {[lsearch -exact $MULTIROW $c] < 0 ? $c : [continue]} }]
set invs [lmap c $invs { expr {[lsearch -exact $MULTIROW $c] < 0 ? $c : [continue]} }]
set_ccopt_property buffer_cells $bufs
set_ccopt_property inverter_cells $invs
# place, clock tree, route
place_opt_design
saveDesign place.enc
create_ccopt_clock_tree_spec
ccopt_design
optDesign -postCTS -hold
saveDesign cts.enc
routeDesign
optDesign -postRoute -setup -hold
addFiller -cell [env_list PNR_FILLERS] -prefix FILL
ecoRoute -fix_drc
# extra DRC pass (from the d256 0.9/1.0 ns runs on): check, fix again; the reports below are on the saved design
verify_drc -report rpt/drc_pass1.rpt
ecoRoute -fix_drc
saveDesign route.enc

# reports (raw reports stay on C2 and in ~/c2_results/p15)
timeDesign -postRoute -outDir rpt/setup
timeDesign -postRoute -hold -outDir rpt/hold
verify_drc -report rpt/drc.rpt
verifyConnectivity -report rpt/conn.rpt
verifyConnectivity -nets $PG -report rpt/conn_pg.rpt
# metal only: masterslice (well) layers not used for PG connectivity
verifyConnectivity -nets $PG -noSoftPGConnect -report rpt/conn_pg_metal.rpt
# well taps: every standard cell at most WT_RULE (40 um, library note) from a well tap
verifyWellTap -cell $env(PNR_WELLTAP) -rule $WT_RULE -report rpt/welltap.rpt
# the same check without the bottom and top rows (they hold only end caps, so no tap can be placed in them)
lassign [lindex [dbGet top.fPlan.coreBox] 0] cx1 cy1 cx2 cy2
set rh [lindex [dbGet top.fPlan.rows.box_sizey] 0]
verifyWellTap -cell $env(PNR_WELLTAP) -rule $WT_RULE \
  -area [list $cx1 [expr {$cy1 + $rh}] $cx2 [expr {$cy2 - $rh}]] -report rpt/welltap_inner.rpt
report_power -outfile rpt/power.rpt
summaryReport -outfile rpt/summary.rpt
# design metrics without cell names: core and die area, instance counts, placed cell area (um^2)
proc box_area {b} { return [expr {([lindex $b 2] - [lindex $b 0]) * ([lindex $b 3] - [lindex $b 1])}] }
set core [lindex [dbGet top.fPlan.coreBox] 0]
set die  [lindex [dbGet top.fPlan.box] 0]
set all  [dbGet top.insts]
set phys [dbGet -p top.insts.isPhysOnly 1]
if {$phys eq "0x0"} { set phys {} }
set nphys [llength $phys]
set logic_area 0.0
foreach b [dbGet [dbGet -p top.insts.isPhysOnly 0].box] { set logic_area [expr {$logic_area + [box_area $b]}] }
set fm [open rpt/metrics.txt w]
puts $fm "core_box_um $core"
puts $fm "core_area_um2 [format %.3f [box_area $core]]"
puts $fm "die_area_um2 [format %.3f [box_area $die]]"
puts $fm "insts_total [llength $all]"
puts $fm "insts_physical_only $nphys"
puts $fm "insts_logic [expr {[llength $all] - $nphys}]"
foreach p {FILL ENDCAP_LR ENDCAP_TB WT} { puts $fm "insts_prefix_$p [llength [dbGet -e top.insts.name ${p}*]]" }
puts $fm "insts_multirow [llength [p15_multirow_insts]]"
puts $fm "logic_cell_area_um2 [format %.3f $logic_area]"
puts $fm "logic_utilisation_core [format %.4f [expr {$logic_area / [box_area $core]}]]"
close $fm
puts "STAGE B DONE"
