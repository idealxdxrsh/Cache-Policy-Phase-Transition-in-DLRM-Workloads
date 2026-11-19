# P16 multi-corner timing of a finished routed design (sign-off of the existing layout: no optimisation, no ECO, no
# re-routing, nothing saved). Restores <P16_SRC>/route.enc, keeps the restored analysis settings (on-chip variation,
# CPPR both, no derates set by the flow), adds two corners from the same library family next to the typical view AV
# that the design was optimised in, and runs timeDesign -postRoute (setup and hold) with one view active at a time:
#   tt: AV     typical 1.00 V 25 C libraries, nominal RC (as in P15)
#   ss: AV_SS  slow 0.90 V 125 C libraries, SigRCmax RC, RC temperature 125 C
#   ff: AV_FF  fast 1.10 V -40 C libraries, SigCmin RC, RC temperature -40 C
# Every library and RC file comes from local.env on C2 (CORELIB_SS_GLOB, CLKLIB_SS_GLOB, CORELIB_FF_GLOB,
# CLKLIB_FF_GLOB, PNR_QRC_MAX_GLOB, PNR_QRC_MIN_GLOB; optional PRLIB_SS_GLOB / PRLIB_FF_GLOB, as PRLIB_GLOB for tt).
# Run by run_p16.csh in the output folder. Reports: rpt/<tt|ss|ff>/{setup,hold}/, rpt/p16_settings.txt.
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
set FF [concat [expand [list $env(CORELIB_FF_GLOB) $env(CLKLIB_FF_GLOB)]] [optglob PRLIB_FF_GLOB]]
set QMAX [lindex [expand [list $env(PNR_QRC_MAX_GLOB)]] 0]
set QMIN [lindex [expand [list $env(PNR_QRC_MIN_GLOB)]] 0]
create_library_set -name LS_SS -timing $SS
create_library_set -name LS_FF -timing $FF
create_rc_corner -name RC_MAX -qx_tech_file $QMAX -T 125
create_rc_corner -name RC_MIN -qx_tech_file $QMIN -T -40
create_delay_corner -name DC_SS -library_set LS_SS -rc_corner RC_MAX
create_delay_corner -name DC_FF -library_set LS_FF -rc_corner RC_MIN
create_analysis_view -name AV_SS -constraint_mode CM -delay_corner DC_SS
create_analysis_view -name AV_FF -constraint_mode CM -delay_corner DC_FF
setExtractRCMode -engine postRoute

set fp [open rpt/p16_settings.txt w]
puts $fp "source $env(P16_SRC)"
puts $fp "analysisType [getAnalysisMode -analysisType]"
puts $fp "cppr [getAnalysisMode -cppr]"
puts $fp "views [all_analysis_views]"
puts $fp "library files per set: SS [llength $SS], FF [llength $FF]"
close $fp

foreach {tag view} {tt AV ss AV_SS ff AV_FF} {
  set_analysis_view -setup [list $view] -hold [list $view]
  timeDesign -postRoute -outDir rpt/$tag/setup
  timeDesign -postRoute -hold -outDir rpt/$tag/hold
  set fp [open rpt/p16_settings.txt a]
  puts $fp "$tag view $view done"
  close $fp
}
puts "P16 DONE"
exit
