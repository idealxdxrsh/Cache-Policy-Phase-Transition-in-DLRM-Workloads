# P13 power from simulation activity, without re-synthesis: read the libraries, the run's netlist and SDC (0.8 ns
# clock), the TCF of the netlist instance written by the SDF gate-level run (run_gls.csh with GLS_TCF), mapped to the
# netlist top with -tcf_instance; then report_power (power_engine default: joules) and report_sdb_annotation
# (activity annotation coverage) into $OUT.
read_libs [list $::env(CORELIB) $::env(CLKLIB)]
read_netlist $::env(NETLIST) -top $::env(TOP)
read_sdc $::env(SDC_FILE)
# P15 post-route: parasitics extracted by Innovus (SPEF_FILE set by run_power.csh from PWR_SPEF)
if {[info exists ::env(SPEF_FILE)]} { read_spef $::env(SPEF_FILE) }
read_tcf -tcf_instance $::env(TCF_INSTANCE) $::env(TCF_FILE)
report_power > $::env(OUT)/power_tcf.rpt
report_sdb_annotation > $::env(OUT)/sdb_annotation.rpt
exit
