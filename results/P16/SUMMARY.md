# P16: multi-corner timing of the final routed designs (sign-off of the existing P15 layouts) on the lab server C2
Technology: a commercial 28nm FD-SOI standard-cell library; corners tt = typical 1.00 V 25 C + nominal RC, ss = slow 0.90 V 125 C
+ SigRCmax RC, ff = fast 1.10 V -40 C + SigCmin RC. Every number is from results/P16/TABLES.md (tools/p16_collect.py; raw reports
stay off the repo). Flow: cadence/pnr/p16_corners.tcl, run_p16.csh: restore route.enc, add the corners, timeDesign -postRoute per
corner; no optimisation, ECO or re-routing. On-chip variation, CPPR both, no derates, SDC as in P15.
**The designs were optimised (placement, clock tree, routing, setup and hold fixing) at the typical corner only, so slow- and
fast-corner failures are expected and are not a flow error.**
## Check
- tt reproduces the P15 reports of the same databases for all 5 designs (setup and hold WNS, TNS and violating paths identical).

## Timing (WNS ns, violating paths in brackets; TABLES.md "Timing per design and corner")
| design | period ns | tt setup | tt hold | ss setup | ss hold | ff setup | ff hold |
|---|---|---|---|---|---|---|---|
| d16 v3 | 0.8 | -0.001 (1) | 0.056 (0) | -0.221 (1435) | 0.034 (0) | 0.174 (0) | 0.039 (0) |
| d256 v2 | 1.0 | 0.022 (0) | 0.009 (0) | -0.257 (21072) | -0.217 (6048) | 0.213 (0) | -0.070 (1707) |
| d256 v3 | 1.0 | 0.014 (0) | 0.008 (0) | -0.236 (22222) | -0.212 (6507) | 0.214 (0) | -0.064 (2698) |
| d256 v2 | 1.1 | 0.029 (0) | 0.033 (0) | -0.265 (16305) | -0.178 (4688) | 0.221 (0) | -0.036 (563) |
| d256 v3 | 1.1 | 0.030 (0) | 0.051 (0) | -0.262 (17366) | -0.180 (5834) | 0.234 (0) | -0.032 (1136) |
- Setup: fails at ss for all 5 (d256: in reg2reg paths only), met at ff for all 5.
- Hold (TABLES.md "Path groups"): d16 meets hold at all three corners. d256 at ss: every failing hold path is in the 'default'
  group (inputs to registers, registers to outputs, against the 0.2 x period SDC input/output delay on an ideal clock); reg2reg
  hold is met at ss (+0.012 to +0.065 ns). d256 at ff: mostly 'default' as well; reg2reg hold fails only in the 1.0 ns layouts
  (v2 -0.002 ns, 14 paths; v3 -0.005 ns, 46 paths). The cause of the I/O hold failures was not diagnosed further.
- Met at all three corners: none of the 5 designs.

## Derived figure (not a measurement): slow-corner period = PnR period - ss setup WNS (TABLES.md "Derived")
| design | PnR period ns | ss setup WNS ns | derived slow-corner period ns |
|---|---|---|---|
| d16 v3 | 0.8 | -0.221 | 1.021 |
| d256 v2 / v3 | 1.0 | -0.257 / -0.236 | 1.257 / 1.236 |
| d256 v2 / v3 | 1.1 | -0.265 / -0.262 | 1.365 / 1.362 |
- Same layouts at their PnR clock, not re-optimised at the new period; ignores hold (the I/O hold checks use the 0.2 x period
  I/O delays, so they would change with the period too). The 1.1 ns layouts give a larger figure than the 1.0 ns ones; the
  figure describes each layout as optimised for its own typical-corner target, not the RTL.
- v3 against v2 at ss setup: one layout per version and period; differences of 0.003-0.021 ns, not a design comparison.

## Limits
- Innovus timeDesign with tQuantus extraction per RC corner (no separate sign-off STA; delay-calculation and SI settings as
  restored, not checked); one layout per design and period. Licence: aggregate numbers only, no library data or names.
