source power_common.tcl
puts "== vectorless, OpenSTA default input activity (0.1 x clock frequency, duty 0.5)"
report_power -digits 6
report_power -instances [get_cells *] -digits 6
