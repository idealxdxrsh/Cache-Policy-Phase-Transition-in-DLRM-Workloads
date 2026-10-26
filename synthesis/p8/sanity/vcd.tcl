source power_common.tcl
puts "== read_vcd -scope tb/dut inv_power.vcd.gz"
read_vcd -scope tb/dut inv_power.vcd.gz
report_activity_annotation -report_annotated -report_unannotated
report_power -digits 6
report_power -instances [get_cells *] -digits 6
