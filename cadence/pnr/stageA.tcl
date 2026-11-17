# P15 stage A: init, floorplan, end caps, well taps, four-net power grid, body-bias connection of the well taps.
# Run from the output folder by run_pnr.csh (pnr.tcl). Every library path and cell name comes from the environment
# (local.env on C2); see run_pnr.csh for the variable list.
proc env_list {name} { return [regexp -all -inline {\S+} $::env($name)] }
proc expand {pats {need 1}} {
  set out {}
  foreach p $pats {
    set m [lsort [glob -nocomplain $p]]
    if {$m eq "" && $need} { error "P15: no file matches a pattern of $pats" }
    set out [concat $out $m]
  }
  return $out
}
set BP $env(PNR_BODY_PWR)
set BG $env(PNR_BODY_GND)
set PG [list vdd gnd $BP $BG]
set BODY [list $BP $BG]
setMultiCpuUsage -localCpu $env(PNR_CPUS)

# timing libraries and RC corner: typical 1.00 V 25 C, nominal RC
set LIBS [concat [expand [list $env(CORELIB_GLOB) $env(CLKLIB_GLOB)]] [expand [list $env(PRLIB_GLOB)] 0]]
set QRC [lindex [expand [list $env(PNR_QRC_GLOB)]] 0]
set fp [open mmmc.tcl w]
puts $fp "create_library_set -name LS_TT -timing {$LIBS}"
puts $fp "create_rc_corner -name RC_NOM -qx_tech_file $QRC -T 25"
puts $fp "create_delay_corner -name DC_TT -library_set LS_TT -rc_corner RC_NOM"
puts $fp "create_constraint_mode -name CM -sdc_files {$env(PNR_SDC)}"
puts $fp "create_analysis_view -name AV -constraint_mode CM -delay_corner DC_TT"
puts $fp "set_analysis_view -setup AV -hold AV"
close $fp
set init_lef_file [concat [expand [env_list PNR_TECH_LEFS]] [expand [env_list PNR_CELL_LEFS]]]
set init_verilog $env(PNR_NETLIST)
set init_top_cell $env(PNR_TOP)
set init_mmmc_file mmmc.tcl
set init_pwr_net [list vdd $BP]
set init_gnd_net [list gnd $BG]
init_design
setDesignMode -process 28
setAnalysisMode -analysisType onChipVariation -cppr both
foreach n $PG { globalNetConnect $n -type pgpin -pin $n -all }

# multi-row cells: in the first d256 runs every instance of a double-height master (its own double-height site) had
# its pins shorted to the PG rails and its PG pins unconnected (P15 diagnosis, cadence/pnr/diag_shorts.tcl). Fix:
# every library cell taller than one core-site row is dont_use, and the netlist's multi-row instances are resized
# to single-row cells with ecoChangeCell (downsize, then upsize, one step at a time) before the floorplan.
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
proc p15_cell_of {n} { return [dbGet [lindex [dbGet -p top.insts.name $n] 0].cell.name] }
set MULTIROW [p15_multirow_cells]
foreach c $MULTIROW { setDontUse $c true }
set mr_netlist [p15_multirow_insts]
set mr_swapped 0
foreach n $mr_netlist {
  set ok 0
  foreach dir {-downsize -upsize} {
    for {set k 0} {$k < 10} {incr k} {
      set before [p15_cell_of $n]
      if {[catch {ecoChangeCell -inst $n $dir}]} { break }
      set after [p15_cell_of $n]
      if {[lsearch -exact $MULTIROW $after] < 0} { set ok 1; break }
      if {$after eq $before} { break }
    }
    if {$ok} { break }
  }
  if {$ok} { incr mr_swapped }
}
set mr_left [llength [p15_multirow_insts]]
set fm [open rpt/multirow.txt w]
puts $fm "multirow_libcells [llength $MULTIROW]"
puts $fm "multirow_insts_netlist [llength $mr_netlist]"
puts $fm "multirow_insts_swapped $mr_swapped"
puts $fm "multirow_insts_left $mr_left"
close $fm
if {$mr_left > 0} { error "P15: $mr_left multi-row instances could not be resized to single-row cells (rpt/multirow.txt)" }

# floorplan: aspect 1.0, utilisation 0.6, 12 um core-to-die margins; inputs left, outputs right on M4
floorPlan -site $env(PNR_SITE) -r 1.0 0.6 12 12 12 12
editPin -pin [dbGet [dbGet top.terms.direction input  -p].name] -side Left  -layer M4 -spreadType side -fixOverlap 1
editPin -pin [dbGet [dbGet top.terms.direction output -p].name] -side Right -layer M4 -spreadType side -fixOverlap 1

# timing settings recommended for this library
set_global timing_cppr_transition_sense same_transition_expanded
set_global timing_use_latch_early_launch_edge false
set_global timing_enable_early_late_data_slews_for_setuphold_mode_checks false
set_global timing_allow_input_delay_on_clock_source true
set_global timing_enable_pessimistic_cppr_for_reconvergent_clock_paths true
set_global timing_enable_power_ground_constants true
setDelayCalMode -SIAware true
# routing settings (litho and antenna-diode options left out)
setNanoRouteMode -routeExpUseAutoVia true
setNanoRouteMode -drouteUseMultiCutViaEffort high
setNanoRouteMode -droutePostRouteSwapVia multiCut
setNanoRouteMode -routeTopRoutingLayer 6

# end caps: left/right row ends (all rows), then the top and bottom rows
setEndCapMode -reset
setEndCapMode -leftEdge $env(PNR_ENDCAP_LR) -rightEdge $env(PNR_ENDCAP_LR) -prefix ENDCAP_LR
# corner cells, one per corner of the core (PNR_ENDCAP_CORNER_TL/_TR/_BL/_BR: the cell for the top-left, top-right,
# bottom-left and bottom-right corner); if unset, the left/right end cap is used in the corners too.
# Innovus's -leftBottomCorner etc. name the corner of the cell's well, not the core corner: in P15 the cell given
# as -leftBottomCorner was placed at the bottom-right core corner. So the options are crossed here, and
# rpt/corners.txt (written below) lists the cell placed at each core corner.
if {[info exists env(PNR_ENDCAP_CORNER_TL)]} {
  setEndCapMode -rightTopCorner $env(PNR_ENDCAP_CORNER_TL) -leftTopCorner $env(PNR_ENDCAP_CORNER_TR) \
    -rightBottomCorner $env(PNR_ENDCAP_CORNER_BL) -leftBottomCorner $env(PNR_ENDCAP_CORNER_BR)
}
addEndCap
setEndCapMode -reset
setEndCapMode -topEdge [env_list PNR_ENDCAP_TOP] -bottomEdge [env_list PNR_ENDCAP_BOTTOM] -prefix ENDCAP_TB
addEndCap
# cell at each core corner (rpt/corners.txt: corner, instance, cell, orientation; stays on C2)
lassign [lindex [dbGet top.fPlan.coreBox] 0] cx1 cy1 cx2 cy2
set fc [open rpt/corners.txt w]
foreach {tag px py} [list BL $cx1 $cy1 BR $cx2 $cy1 TL $cx1 $cy2 TR $cx2 $cy2] {
  foreach i [dbGet -p top.insts.name ENDCAP_*] {
    lassign [lindex [dbGet $i.box] 0] a b c d
    if {abs($a - $px) < 0.001 && abs($b - $py) < 0.001 || abs($c - $px) < 0.001 && abs($b - $py) < 0.001 ||
        abs($a - $px) < 0.001 && abs($d - $py) < 0.001 || abs($c - $px) < 0.001 && abs($d - $py) < 0.001} {
      puts $fc "$tag [dbGet $i.name] [dbGet $i.cell.name] [dbGet $i.orient]"
    }
  }
}
close $fc
# well taps (body-bias connection), checkerboard, 160 um interval
# library note: every standard cell at most 40 um from a well tap; checkerboard with a 160 um interval meets it
set WT_INTERVAL 160
set WT_RULE 40
addWellTap -cell $env(PNR_WELLTAP) -checkerboard -cellInterval $WT_INTERVAL -prefix WT

# four-net power grid: rings M5/M6, core pins, M5 stripes every 20 um extended to the die boundary, vias
addRing -nets $PG -type core_rings -follow core \
  -layer {top M6 bottom M6 left M5 right M5} -width 1.0 -spacing 0.5 -offset 1.0
sroute -connect {corePin} -nets $PG -corePinTarget {ring} -allowJogging 1 -allowLayerChange 1
setAddStripeMode -stacked_via_bottom_layer M1 -stacked_via_top_layer M5
addStripe -nets $PG -layer M5 -direction vertical -width 0.5 -spacing 0.5 \
  -set_to_set_distance 20 -start_from left -extend_to design_boundary
editPowerVia -nets $PG -bottom_layer M1 -top_layer M5 -add_vias 1
editPowerVia -nets $PG -bottom_layer M5 -top_layer M6 -add_vias 1
verifyConnectivity -nets $PG -report rpt/conn_grid.rpt

# body-bias nets: the well-tap body pins are routed to the grid by NanoRoute together with the signal nets
# (routeDesign in stage B). Only the tap pins are marked: the end-cap body pins are not accessible to NanoRoute
# (NRGR-59), and marking them makes it flag both nets as open and route nothing. The end caps and all other cells
# join the taps by abutment of their body pins along each row once the rows are filled. Routing these pins here
# (before placement) does not work: placement deletes the regular routing of these nets (every cell is on them).
# PNR_BODY_MODE=convert routes them here and converts the wires to special wires instead; that survives placement
# but left 24 minimum-area violations on M3 in P15 at depth 16, so route (default) is used.
if {![info exists env(PNR_BODY_MODE)]} { set env(PNR_BODY_MODE) route }
setPGPinUseSignalRoute $env(PNR_WELLTAP):$BP $env(PNR_WELLTAP):$BG
if {$env(PNR_BODY_MODE) eq "convert"} {
  routePGPinUseSignalRoute -nets $BODY
  convertNetToSNet -keep_wire_extension 1 -nets $BODY
  catch {setPGPinUseSignalRoute -off $env(PNR_WELLTAP):$BP $env(PNR_WELLTAP):$BG}
}
verifyConnectivity -nets $PG -report rpt/conn_fp.rpt
verifyConnectivity -nets $PG -noSoftPGConnect -report rpt/conn_fp_metal.rpt
saveDesign fp.enc
puts "STAGE A DONE"
