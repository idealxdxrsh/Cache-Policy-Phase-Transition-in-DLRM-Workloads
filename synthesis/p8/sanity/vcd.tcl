source power_common.tcl
puts "== read_vcd -scope tb/dut -begin_time 10250 -end_time 1010249 inv_power.vcd.gz"
# window: dump from 10250 ps to 1010250 ps ($dumpoff writes X at 1010250; exclude it)
read_vcd -scope tb/dut -begin_time 10250 -end_time 1010249 inv_power.vcd.gz
report_activity_annotation -report_annotated -report_unannotated
report_power -digits 6
report_power -instances [get_cells *] -digits 6
