# P13: SDF variants for an existing netlist, without re-synthesis: read the libraries, the run's netlist and SDC,
# report timing (must equal the run's timing.rpt), then one write_sdf per variant in $VARIANTS into
# $OUT/delays_<v>.sdf. delays.sdf (written by genus_lfu.tcl) is not touched; an existing variant file is kept.
# Every variant keeps -timescale ns -nonegchecks from genus_lfu.tcl; only the timing-check form changes:
#   a: Genus defaults (no -setuphold / -recrem / -edges)
#   b: SETUPHOLD and RECREM combined when both exist, library check edges (-edges check_edge)
#   c: b with -nosplit_timing_check (no rise/fall split, so no edge on the data pin of a check)
read_libs [list $::env(CORELIB) $::env(CLKLIB)]
read_netlist $::env(NETLIST) -top $::env(TOP)
read_sdc $::env(SDC_FILE)
report_timing > $::env(OUT)/timing_reread.rpt
set base {-timescale ns -nonegchecks}
array set opt {
    a {}
    b {-setuphold merge_when_paired -recrem merge_when_paired -edges check_edge}
    c {-setuphold merge_when_paired -recrem merge_when_paired -edges check_edge -nosplit_timing_check}
}
foreach v $::env(VARIANTS) {
    set f $::env(OUT)/delays_$v.sdf
    if {[file exists $f]} { puts "sdf_variant $v: $f exists, not overwritten"; continue }
    puts "sdf_variant $v: write_sdf $base $opt($v)"
    eval write_sdf $base $opt($v) > $f
}
exit
