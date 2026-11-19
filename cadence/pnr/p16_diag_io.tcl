# P16 diagnosis of the I/O hold failures (read-only: nothing is saved, no design or constraint change). Restores
# <P16_SRC>/route.enc, adds the slow corner as in p16_corners.tcl, and with one view active at a time (tt = AV, ss = AV_SS)
# writes, for the hold (early) check:
#   rpt/diag/<tag>_in2reg.rpt   worst path from a data input to a register (full clock path)
#   rpt/diag/<tag>_reg2out.rpt  worst path from a register to an output (full clock path)
#   rpt/diag/<tag>_counts.txt   number of violating hold paths in2reg / reg2out (up to 50000 each)
# Run by run_p16_diag.csh in the output folder.
proc expand {pats {need 1}} {
  set out {}
  foreach p $pats {
    set m [lsort [glob -nocomplain $p]]
    if {$m eq "" && $need} { error "P16: no file matches a pattern of $pats" }
    set out [concat $out $m]
  }
  return $out
}
proc optglob {name} { if {[info exists ::env($name)]} { return [expand [list $::env($name)] 0] } ; return {} }
setMultiCpuUsage -localCpu $env(PNR_CPUS)
restoreDesign $env(P16_SRC)/route.enc.dat $env(PNR_TOP)
set SS [concat [expand [list $env(CORELIB_SS_GLOB) $env(CLKLIB_SS_GLOB)]] [optglob PRLIB_SS_GLOB]]
set QMAX [lindex [expand [list $env(PNR_QRC_MAX_GLOB)]] 0]
create_library_set -name LS_SS -timing $SS
create_rc_corner -name RC_MAX -qx_tech_file $QMAX -T 125
create_delay_corner -name DC_SS -library_set LS_SS -rc_corner RC_MAX
create_analysis_view -name AV_SS -constraint_mode CM -delay_corner DC_SS
setExtractRCMode -engine postRoute
file mkdir rpt/diag
set INS [remove_from_collection [all_inputs] [get_ports clk]]
set OUTS [all_outputs]
foreach {tag view} {tt AV ss AV_SS} {
  set_analysis_view -setup [list $view] -hold [list $view]
  timeDesign -postRoute -hold -outDir rpt/diag/${tag}_hold
  report_timing -early -from $INS -to [all_registers] -path_type full_clock -max_paths 1 > rpt/diag/${tag}_in2reg.rpt
  report_timing -early -from [all_registers] -to $OUTS -path_type full_clock -max_paths 1 > rpt/diag/${tag}_reg2out.rpt
  set fp [open rpt/diag/${tag}_counts.txt w]
  foreach {name from to} [list in2reg $INS [all_registers] reg2out [all_registers] $OUTS] {
    if {[catch {set c [report_timing -collection -early -from $from -to $to -max_paths 50000 -max_slack 0]} err]} {
      puts $fp "$name n/a ($err)"
    } else {
      puts $fp "$name violating_hold_paths [sizeof_collection $c]"
    }
  }
  close $fp
}
puts "P16 DIAG DONE"
exit
