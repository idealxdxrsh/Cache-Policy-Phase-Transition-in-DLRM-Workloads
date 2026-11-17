# P15: export a routed design for gate-level simulation and power. Run by run_export.csh in a finished PnR folder.
# Environment: DIAG_TOP (top cell). Writes gls/: post_route.v (saveNetlist, physical-only cells excluded),
# post_route.spef (extractRC, postRoute engine), delays_<v>.sdf (write_sdf variants, analysis view AV), timing/
# (timeDesign -postRoute again on the restored design, setup and hold, to compare with the run's own reports).
# The help text of write_sdf and saveNetlist goes to the session log.
setMultiCpuUsage -localCpu 8
restoreDesign route.enc.dat $env(DIAG_TOP)
file mkdir gls
foreach cmd {write_sdf saveNetlist} { puts "HELP BEGIN $cmd"; catch {help $cmd}; puts "HELP END $cmd" }
setExtractRCMode -engine postRoute
extractRC
timeDesign -postRoute -outDir gls/timing/setup
timeDesign -postRoute -hold -outDir gls/timing/hold
saveNetlist gls/post_route.v
rcOut -spef gls/post_route.spef
# a: defaults; b: SETUPHOLD/RECREM merged when paired, library check edges (the P13 Genus variant b)
array set opt {
  a {}
  b {-setuphold merge_when_paired -recrem merge_when_paired -edges check_edge}
}
foreach v {a b} {
  if {[catch {eval write_sdf -view AV $opt($v) gls/delays_$v.sdf} e]} { puts "SDF VARIANT $v FAILED: $e" } else { puts "SDF VARIANT $v OK" }
}
puts "EXPORT DONE"
exit
