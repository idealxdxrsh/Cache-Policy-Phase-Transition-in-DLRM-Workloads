# Same constraints as the P5 inverter check (synthesis/p5/sta_check/inv1.tcl): input slew and output load at liberty
# table index points, no wire-load model, 1 GHz clock (ideal). NanGate45, typical corner.
read_liberty $::env(LIB)
read_verilog inv_power.v
link_design inv_power
create_clock -name clk -period 1.0 [get_ports clk]
set_input_delay 0 -clock clk [get_ports a]
set_output_delay 0 -clock clk [get_ports {y[0] q w[0] w[1]}]
set_input_transition 0.00117378 [get_ports a]
set_load 3.795620 [get_ports {y[0] q w[0] w[1]}]
