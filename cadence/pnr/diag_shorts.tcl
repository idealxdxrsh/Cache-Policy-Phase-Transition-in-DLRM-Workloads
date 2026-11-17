# P15 diagnosis of the PG-rail shorts (verify_drc "Special Wire of Net <pg> & Pin of Cell <inst>") in a finished run.
# One Innovus session per saved database; run by run_diag.csh from the run folder. Environment:
#   DIAG_DB   place | cts | route   (database <DIAG_DB>.enc.dat in the current folder)
#   DIAG_TOP  top cell name
# Writes (current folder):
#   rpt/diag_present_<db>.txt  instance present in that database (1/0), one line per shorting instance
#   route only: rpt/diag_shorts.txt  per shorting instance: master, height in rows, orientation, master site, class,
#               row orientation and row site at the instance's bottom edge (cell names: stays on C2 / ~/c2_results)
#               rpt/diag_census.txt  every multi-row logic instance in the design, counted by alignment class; names-free
# Height comes from the tool's database (dbGet cell.size_y), not from reading library files.
proc rd {f} { set h [open $f]; set t [read $h]; close $h; return $t }
setMultiCpuUsage -localCpu 8
set db $env(DIAG_DB)
restoreDesign $db.enc.dat $env(DIAG_TOP)

set insts {}
foreach {- n} [regexp -all -inline -line {^SHORT: .*Special Wire of Net \S+ & Pin of Cell (\S+)} [rd rpt/drc.rpt]] {
  lappend insts $n
}
set insts [lsort -unique $insts]
proc find_inst {n} {
  set p [dbGet -e -p top.insts.name $n]
  if {$p eq "" || $p eq "0x0"} { return "" }
  return [lindex $p 0]
}
set fp [open rpt/diag_present_$db.txt w]
foreach n $insts { puts $fp "$n [expr {[find_inst $n] ne {}}]" }
close $fp

if {$db eq "route"} {
  proc val {expr} { if {[catch {uplevel 1 [list dbGet {*}$expr]} v]} { return n/a }; if {$v eq ""} { return - }; return $v }
  set rh [lindex [dbGet top.fPlan.rows.box_sizey] 0]
  lassign [lindex [dbGet top.fPlan.coreBox] 0] cx1 cy1 cx2 cy2
  foreach r [dbGet top.fPlan.rows] {
    set y [format %.3f [dbGet $r.box_lly]]
    set rowo($y) [dbGet $r.orient]
    set rows($y) [val [list $r.site.name]]
  }
  proc rowinfo {y} {
    global rowo rows
    set k [format %.3f $y]
    if {[info exists rowo($k)]} { return [list $rowo($k) $rows($k)] }
    return [list off-row off-row]
  }
  set fp [open rpt/diag_shorts.txt w]
  puts $fp "# row height $rh um; row sites: [lsort -unique [dbGet top.fPlan.rows.site.name]]; row orients: [lsort -unique [dbGet top.fPlan.rows.orient]]"
  puts $fp "# inst master height_um height_rows inst_orient master_site master_class/subclass bottom_row_orient bottom_row_site lly_um llx_um"
  foreach n $insts {
    set i [find_inst $n]
    if {$i eq ""} { puts $fp "$n missing"; continue }
    set c [dbGet $i.cell]
    set h [dbGet $c.size_y]
    lassign [lindex [dbGet $i.box] 0] x1 y1 x2 y2
    lassign [rowinfo $y1] ro rs
    puts $fp "$n [dbGet $c.name] $h [format %.3f [expr {$h / $rh}]] [dbGet $i.orient] [val [list $c.site.name]] \
[val [list $c.baseClass]]/[val [list $c.subClass]] $ro $rs [format %.3f $y1] [format %.3f $x1]"
  }
  close $fp
  # census: every logic instance whose master is taller than one row or has a site other than the main row site, by (master site, bottom-row orient, inst
  # orient, row-grid alignment, in the shorts list); counts only
  array set inshort {}
  foreach n $insts { set inshort($n) 1 }
  array set cnt {}
  set nmulti_masters 0
  set nlogic_masters 0
  set nother_site_masters 0
  set site_cnt {}
  foreach s [dbGet top.fPlan.rows.site.name] { dict incr site_cnt $s }
  set mainsite [lindex [lsort -stride 2 -index 1 -integer -decreasing $site_cnt] 0]
  foreach c [dbGet -u [dbGet -p top.insts.isPhysOnly 0].cell] {
    incr nlogic_masters
    set nr [expr {[dbGet $c.size_y] / $rh}]
    set site [val [list $c.site.name]]
    if {$nr < 1.001 && $site eq $mainsite} { continue }
    if {$nr >= 1.001} { incr nmulti_masters } else { incr nother_site_masters }
    set ps [dbGet -p2 top.insts.cell.name [dbGet $c.name]]
    foreach i $ps {
      lassign [lindex [dbGet $i.box] 0] x1 y1 x2 y2
      lassign [rowinfo $y1] ro rs
      set sh [info exists inshort([dbGet $i.name])]
      set key "rows=[format %.2f $nr] master_site_is_row_site=[expr {$site eq $rs}] bottom_row_orient=$ro inst_orient=[dbGet $i.orient] in_shorts=$sh"
      if {![info exists cnt($key)]} { set cnt($key) 0 }
      incr cnt($key)
    }
  }
  set fp [open rpt/diag_census.txt w]
  puts $fp "logic_masters_used $nlogic_masters"
  puts $fp "multirow_masters_used $nmulti_masters"
  puts $fp "single_row_other_site_masters_used $nother_site_masters"
  puts $fp "row_sites [llength [dict keys $site_cnt]]"
  foreach k [lsort [array names cnt]] { puts $fp "count $cnt($k) $k" }
  close $fp
}
puts "DIAG DONE $db"
exit
