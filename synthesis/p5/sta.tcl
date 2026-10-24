# OpenSTA, pre-layout: ideal clock, liberty wire-load model 5K_hvratio_1_1 (the liberty default_wire_load),
# input/output delay 0 relative to clk; inputs driven by BUF_X1 and outputs loaded with 3.795620 fF, the same
# as synthesis/p5/abc.constr. NanGate45, not TSMC. No power commands.
read_liberty $::env(LIB)
read_verilog $::env(OUT)/netlist.v
link_design lfu_cache_controller
set_wire_load_model -name 5K_hvratio_1_1
create_clock -name clk -period $::env(PERIOD_NS) [get_ports clk]
set_input_delay 0 -clock clk [delete_from_list [all_inputs] [get_ports clk]]
set_output_delay 0 -clock clk [all_outputs]
set_driving_cell -lib_cell BUF_X1 -pin Z [delete_from_list [all_inputs] [get_ports clk]]
set_load 3.795620 [all_outputs]
# rst_n (async reset, fanout = every DFFR) has no reset tree before layout, like the ideal clock: its
# recovery/removal paths are excluded here and its slew/cap violation is still listed below.
set_false_path -from [get_ports rst_n]
puts "PERIOD_NS $::env(PERIOD_NS)"
report_wns -digits 4
report_tns -digits 4
report_worst_slack -max -digits 4
report_worst_slack -min -digits 4
report_check_types -max_slew -max_capacitance -max_fanout -violators
report_checks -path_delay max -digits 4 -fields {slew cap fanout}
report_checks -path_delay min -digits 4
