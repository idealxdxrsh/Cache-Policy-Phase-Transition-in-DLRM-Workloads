// One NanGate45 INV_X1 between two ports, for a hand-checkable OpenSTA test.
module inv1 (a, clk, y);
  input a, clk;
  output y;
  INV_X1 u1 (.A(a), .ZN(y));
endmodule
