# P8 power: OpenSTA report_power on one netlist. NanGate45, typical corner, pre-layout, no clock tree, no extracted
# parasitics, flip-flop storage. Constraints as synthesis/p5/sta.tcl (wire-load 5K_hvratio_1_1, ideal clock, BUF_X1
# input driver, 3.795620 fF output load) with the clock period PERIOD_NS (2.0 for 500 MHz).
# rst_n is held inactive (set_case_analysis 1): activity 0, duty 1.
# Activity: if VCD is set, read_vcd -scope tb_power/gl over [VCD_T0, VCD_T1 - 1] ps (the recorded window; the X values
# written by $dumpoff at VCD_T1 are excluded); otherwise vectorless (OpenSTA default 0.1 transitions per clock cycle,
# duty 0.5, on the other inputs; flip-flop outputs propagated from their D inputs).
# CLOCK_ONLY=1 (no VCD): every cell pin and input at activity 0, duty 0.5, except the flip-flop CK pins (2 transitions
# per cycle, the clock) and RN pins and rst_n (duty 1, reset inactive); set per pin because -global would override the
# case analysis and the clock (power/Power.cc findActivity). The only switching is the clock, and
# the Sequential internal power is the flip-flops' clock-pin internal power alone.
# INST_OUT=<file>: also write report_power -instances for every cell to that file.
read_liberty $::env(LIB)
read_verilog $::env(NETLIST)
link_design lfu_cache_controller
set_wire_load_model -name 5K_hvratio_1_1
create_clock -name clk -period $::env(PERIOD_NS) [get_ports clk]
set_input_delay 0 -clock clk [delete_from_list [all_inputs] [get_ports clk]]
set_output_delay 0 -clock clk [all_outputs]
set_driving_cell -lib_cell BUF_X1 -pin Z [delete_from_list [all_inputs] [get_ports clk]]
set_load 3.795620 [all_outputs]
set_false_path -from [get_ports rst_n]
set_case_analysis 1 [get_ports rst_n]
puts "PERIOD_NS $::env(PERIOD_NS)"
if {[info exists ::env(VCD)] && $::env(VCD) ne ""} {
  puts "ACTIVITY read_vcd $::env(VCD) window_ps $::env(VCD_T0) [expr {$::env(VCD_T1) - 1}]"
  read_vcd -scope tb_power/gl -begin_time $::env(VCD_T0) -end_time [expr {$::env(VCD_T1) - 1}] $::env(VCD)
  report_activity_annotation
} elseif {[info exists ::env(CLOCK_ONLY)] && $::env(CLOCK_ONLY) ne ""} {
  puts "ACTIVITY clock only (all other pins activity 0, duty 0.5)"
  set_power_activity -input -activity 0 -duty 0.5
  set_power_activity -input_ports [get_ports rst_n] -activity 0 -duty 1
  set_power_activity -pins [get_pins *] -activity 0 -duty 0.5
  set_power_activity -pins [get_pins */CK] -activity 2 -duty 0.5
  set_power_activity -pins [get_pins */RN] -activity 0 -duty 1
} else {
  puts "ACTIVITY vectorless default"
}
report_power -digits 6
if {[info exists ::env(INST_OUT)] && $::env(INST_OUT) ne ""} {
  report_power -instances [get_cells *] -digits 6 > $::env(INST_OUT)
}
