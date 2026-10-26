// P8 sanity testbench: a toggles every 1 ns (period 1 ns, so 1e9 transitions per second on a and on y[0]);
// clk has period 1 ns. VCD window: CYCLES cycles after a 10-cycle start-up. Cell models: Yosys-generated from the
// liberty (results/P5f_gls/models/nangate45_cells_yosys.v), zero delay.
`timescale 1ns / 1ps
module tb;
  parameter CYCLES = 1000;
  reg a = 0, clk = 0;
  wire [0:0] y;
  wire q;
  wire [1:0] w;
  inv_power dut (.a(a), .clk(clk), .y(y), .q(q), .w(w));
  always #0.5 clk = ~clk;
  always #1 a = ~a;
  initial begin
    #10.25;
    $dumpfile("inv_power.vcd");
    $dumpvars(0, tb.dut);
    #(CYCLES);
    $dumpoff;
    $finish;
  end
endmodule
