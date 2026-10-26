source power_common.tcl
puts "== vectorless, set_power_activity -input_ports a -activity 1.0 -duty 0.5 (1 transition per 1 ns cycle = 1e9 per second)"
set_power_activity -input_ports [get_ports a] -activity 1.0 -duty 0.5
report_power -digits 6
report_power -instances [get_cells *] -digits 6
