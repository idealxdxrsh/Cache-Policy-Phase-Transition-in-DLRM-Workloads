# P16: multi-corner timing of the final routed designs (sign-off of the existing P15 layouts) on the lab server C2
Technology: a commercial 28nm FD-SOI standard-cell library; corners tt = typical 1.00 V 25 C + nominal RC, ss = slow 0.90 V 125 C
+ SigRCmax RC, ff = fast 1.10 V -40 C + SigCmin RC. Every number is from results/P16/TABLES.md (tools/p16_collect.py,
tools/p16_diag_table.py; raw reports stay off the repo). Flow: cadence/pnr/p16_corners.tcl, run_p16.csh (restore route.enc, add
the corners, timeDesign -postRoute per corner), p16_diag_io.tcl (read-only path reports); nothing optimised, changed or saved.
**The designs were optimised (placement, clock tree, routing, setup and hold fixing) at the typical corner only, so slow- and
fast-corner failures are expected and are not a flow error.** Check: tt reproduces the P15 reports for all 5 designs.
## Timing (WNS ns, violating paths in brackets; TABLES.md "Timing per design and corner")
| design | period ns | tt setup | tt hold | ss setup | ss hold | ff setup | ff hold |
|---|---|---|---|---|---|---|---|
| d16 v3 | 0.8 | -0.001 (1) | 0.056 (0) | -0.221 (1435) | 0.034 (0) | 0.174 (0) | 0.039 (0) |
| d256 v2 | 1.0 | 0.022 (0) | 0.009 (0) | -0.257 (21072) | -0.217 (6048) | 0.213 (0) | -0.070 (1707) |
| d256 v3 | 1.0 | 0.014 (0) | 0.008 (0) | -0.236 (22222) | -0.212 (6507) | 0.214 (0) | -0.064 (2698) |
| d256 v2 | 1.1 | 0.029 (0) | 0.033 (0) | -0.265 (16305) | -0.178 (4688) | 0.221 (0) | -0.036 (563) |
| d256 v3 | 1.1 | 0.030 (0) | 0.051 (0) | -0.262 (17366) | -0.180 (5834) | 0.234 (0) | -0.032 (1136) |
- Setup fails at ss for all 5 (d256: reg2reg paths only), met at ff for all 5. None of the 5 meets setup and hold at all corners.
- Hold ("Path groups"): d16 met at all corners. d256 at ss: all failing paths are I/O paths ('default' group), reg2reg met (+0.012
  to +0.065 ns); at ff mostly I/O paths, reg2reg fails only in the 1.0 ns layouts (v2 -0.002 ns, 14 paths; v3 -0.005 ns, 46).
## Why the I/O hold checks fail (d256 v3 1.0 ns, TABLES.md "I/O hold diagnosis")
- Worst input-to-register hold path at ss: input delay 0.200 ns (SDC, on the ideal clock edge at 0), data arrival 0.202 ns; the
  capturing register's clock arrives at 0.414 ns (full propagated clock-tree delay), hold 0.000, slack -0.212 ns. At ss 6,503 of
  the 6,507 failing hold paths start at an input and none ends at an output (worst register-to-output hold slack +0.678 ns: a
  later launch clock only adds margin there).
- At tt the same path has slack +0.191 ns: the database holds, for the typical view only, a clock source latency of -0.315 ns
  written by the tool in the P15 flow (the flow scripts set none), which cancels the 0.319 ns tree delay for I/O paths (clock
  arrival 0.004 ns). The added ss and ff views have no such latency.
- Hypothesis confirmed: the failures come from I/O delays referenced to the ideal external clock against the propagated internal
  clock, compensated only in the view the design was built in. ff was not traced path by path. Sign-off would need block-level
  I/O constraints with clock latency for every corner, or multi-corner optimisation; neither is done here.
## Derived figure (not a measurement): slow-corner period = PnR period - ss setup WNS (TABLES.md "Derived")
| design | PnR period ns | ss setup WNS ns | derived slow-corner period ns |
|---|---|---|---|
| d16 v3 | 0.8 | -0.221 | 1.021 |
| d256 v2 / v3 | 1.0 | -0.257 / -0.236 | 1.257 / 1.236 |
| d256 v2 / v3 | 1.1 | -0.265 / -0.262 | 1.365 / 1.362 |
- Same layouts at their PnR clock, not re-optimised; ignores hold. Describes each layout as optimised for its own typical target,
  not the RTL; v3 against v2: one layout each, differences 0.003-0.021 ns, not a design comparison.
- Limits: Innovus timeDesign with tQuantus extraction per RC corner (no separate sign-off STA; delay-calculation and SI settings as
  restored, not checked); one layout per design and period. Licence: aggregate numbers only, no library data or names.
