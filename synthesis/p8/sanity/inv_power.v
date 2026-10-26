// P8 power sanity netlist (NanGate45 cells). One INV_X1 with escaped bus-bit names, checked by hand against the
// liberty power data, and one DFF_X1 only to show which report group a flip-flop lands in (not hand-checked).
// Name-mapping cases as in the Yosys netlists: an escaped internal vector (\cnt[1] , bits [1:0]) and a 2-bit
// output port w[1:0]. y[0:0] is a 1-bit vector port (Icarus writes it to the VCD without its range).
module inv_power (a, clk, y, q, w);
  input a, clk;
  output [0:0] y;
  output q;
  output [1:0] w;
  wire [1:0] \cnt[1] ;
  INV_X1 \inv[0]  (.A(a), .ZN(y[0]));
  INV_X1 \inv[1]  (.A(a), .ZN(\cnt[1] [0]));
  INV_X1 \inv[2]  (.A(\cnt[1] [0]), .ZN(\cnt[1] [1]));
  INV_X1 \inv[3]  (.A(\cnt[1] [1]), .ZN(w[0]));
  INV_X1 \inv[4]  (.A(w[0]), .ZN(w[1]));
  DFF_X1 \ff[0]  (.D(a), .CK(clk), .Q(q), .QN());
endmodule
