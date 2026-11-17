# P15: library-cell facts needed for the multi-row fix, from the tool's database (no library files read).
# Run in a finished run folder: innovus -nowin -files diag_libcells.tcl (restores fp.enc). Writes rpt/diag_libcells.txt
# (cell names: stays on C2) and the help text of the commands considered for the fix.
restoreDesign fp.enc.dat $env(DIAG_TOP)
set rh [lindex [dbGet top.fPlan.rows.box_sizey] 0]
set fp [open rpt/diag_libcells.txt w]
puts $fp "libcell_attributes: [dbGet [lindex [dbGet head.libCells] 0].?]"
set n 0; set multi {}
foreach c [dbGet head.libCells] {
  incr n
  if {[dbGet $c.size_y] > $rh + 0.001} { lappend multi "[dbGet $c.name] [dbGet $c.size_y] [dbGet $c.site.name]" }
  lappend all "[dbGet $c.name] [dbGet $c.size_y] [dbGet $c.site.name]"
}
puts $fp "libcells $n multirow [llength $multi]"
foreach m $multi { puts $fp "multirow $m" }
foreach m $all { puts $fp "cell $m" }
close $fp
# help text goes to the session log (diag_libcells.log)
foreach cmd {setDontUse ecoChangeCell setOptMode} { puts "HELP BEGIN $cmd"; catch {help $cmd}; puts "HELP END $cmd" }
puts "DIAG DONE libcells"
exit
