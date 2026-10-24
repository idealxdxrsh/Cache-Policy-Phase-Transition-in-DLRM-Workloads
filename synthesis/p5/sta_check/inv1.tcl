# Expected (liberty INV_X1, A->ZN, input slew 0.00117378 ns = index_1[0],
# load 3.795620 fF = index_2[2], table points, no interpolation):
#   cell_rise = 0.0142069 ns, cell_fall = 0.00763425 ns
#   max path (y rising) slack = 1.0 - 0.0142069 = 0.9857931 ns
read_liberty $::env(LIB)
read_verilog inv1.v
link_design inv1
create_clock -name clk -period 1.0 [get_ports clk]
set_input_delay 0 -clock clk [get_ports a]
set_output_delay 0 -clock clk [get_ports y]
set_input_transition 0.00117378 [get_ports a]
set_load 3.795620 [get_ports y]
report_checks -path_delay max -fields {slew cap input_pins} -digits 7
report_checks -path_delay max -rise_to [get_ports y] -fields {slew cap} -digits 7 -format end
report_checks -path_delay max -fall_to [get_ports y] -fields {slew cap} -digits 7
