# P15 optional hold pass on a finished run: restore its route.enc, optDesign -postRoute -hold (fillers removed for it and
# re-inserted; optional hold target slack), ecoRoute -fix_drc (optional DRC check and one retry), save route.enc and write the same reports as stageB.tcl (copied from there) into the
# current folder (a new folder, so the source run is not changed). Run by run_holdfix.csh. Environment: HOLDFIX_SRC (source
# run folder), PNR_TOP, PNR_CPUS and the PNR_* names from local.env (well tap, fillers, site, body-bias pins).
proc env_list {name} { return [regexp -all -inline {\S+} $::env($name)] }
set BP $env(PNR_BODY_PWR)
set BG $env(PNR_BODY_GND)
set PG [list vdd gnd $BP $BG]
set WT_RULE 40
setMultiCpuUsage -localCpu $env(PNR_CPUS)
restoreDesign $env(HOLDFIX_SRC)/route.enc.dat $env(PNR_TOP)
# multi-row cells (as in stageA.tcl): taller than one core-site row; stay dont_use for the hold pass
proc p15_multirow_cells {} {
  set h0 {}
  foreach c [dbGet head.libCells] {
    if {[dbGet $c.site.name] eq $::env(PNR_SITE)} {
      set h [dbGet $c.size_y]
      if {$h0 eq "" || $h < $h0} { set h0 $h }
    }
  }
  set out {}
  foreach c [dbGet head.libCells] { if {[dbGet $c.size_y] > $h0 + 0.001} { lappend out [dbGet $c.name] } }
  return $out
}
proc p15_multirow_insts {} {
  set out {}
  foreach c $::MULTIROW {
    set p [dbGet -e -p2 top.insts.cell.name $c]
    if {$p ne "" && $p ne "0x0"} { foreach i $p { lappend out [dbGet $i.name] } }
  }
  return $out
}
set MULTIROW [p15_multirow_cells]
foreach c $MULTIROW { setDontUse $c true }
# timing of the source design as restored (should equal its own reports)
timeDesign -postRoute -outDir rpt/pre_hold/setup
timeDesign -postRoute -hold -outDir rpt/pre_hold/hold
# optional: HOLDFIX_HOLD_TARGET (ns) = setOptMode -holdTargetSlack for this pass (default: the restored setting)
if {[info exists env(HOLDFIX_HOLD_TARGET)]} { setOptMode -holdTargetSlack $env(HOLDFIX_HOLD_TARGET) }
deleteFiller -prefix FILL
optDesign -postRoute -hold
addFiller -cell [env_list PNR_FILLERS] -prefix FILL
ecoRoute -fix_drc
# optional: HOLDFIX_DRC_RETRY set = verify_drc (rpt/drc_pass1.rpt) and, if it finds a violation, one more ecoRoute -fix_drc
if {[info exists env(HOLDFIX_DRC_RETRY)]} {
  verify_drc -report rpt/drc_pass1.rpt
  set fd [open rpt/drc_pass1.rpt]; set t [read $fd]; close $fd
  if {![string match "*No DRC violations were found*" $t]} { puts "HOLDFIX DRC RETRY"; ecoRoute -fix_drc }
}
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
puts "HOLDFIX DONE"
exit
