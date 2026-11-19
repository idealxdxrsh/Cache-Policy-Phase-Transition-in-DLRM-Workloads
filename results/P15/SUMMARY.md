# P15: Innovus place and route, post-route GLS and power of the d16 and merge-off d256 netlists on the lab server C2
Technology: a commercial 28nm FD-SOI standard-cell library, typical corner (typical 1.00 V 25 C libraries, nominal RC); areas in library units.
Every number is from results/P15/TABLES.md (tools/p15_collect.py, tools/p15_gls_table.py; raw reports stay off the repo). Flow: cadence/pnr/
(stageA/B.tcl, diag_shorts.tcl, export_gls.tcl), cadence/run_gls.csh, run_power.csh, genus_power.tcl. Netlists synthesised at 0.8 ns.

## First flow defect and fix (TABLES.md "Diagnosis", "Fix")
- d256 PG-rail shorts (15/6/11/7) = all instances of the one double-height master; fix: 29 multi-row cells dont_use, netlist ones
  resized (v2 8, v3 6), 0 after route. d16 (v3, 0.8 ns): DRC 0, connectivity 0, setup WNS -0.001 ns (1 path).
## Timing, d256 v2/v3 merge-off, target-slack flow (setup target slack 0.03 ns, extra postRoute setup opt; TABLES.md "Met/failed bracket")
| run | period ns | setup WNS / TNS ns (viol. paths) | hold WNS / TNS ns (viol. paths) | DRC | conn. problems all nets |
|---|---|---|---|---|---|
| v2 | 0.9, after 2 hold passes | -0.008 / -0.139 (56) | 0.010 / 0.000 (0) | 0 | 0 |
| v2 | 1.0, after 2 hold passes | 0.022 / 0.000 (0) | 0.009 / 0.000 (0) | 0 | 0 |
| v2 | 1.1 | 0.029 / 0.000 (0) | 0.033 / 0.000 (0) | 0 | 0 |
| v3 | 0.9, after 2 hold passes | -0.056 / -60.911 (1841) | 0.010 / 0.000 (0) | 0 | 0 |
| v3 | 1.0, after 2 hold passes | 0.014 / 0.000 (0) | 0.008 / 0.000 (0) | 0 | 0 |
| v3 | 1.1 | 0.030 / 0.000 (0) | 0.051 / 0.000 (0) | 0 | 0 |
- Bracket (target-slack flow, latest hold pass per period): v2 and v3 tightest met 1.0 ns, loosest failed 0.9 ns (setup; the hold passes
  leave setup unchanged). Before them 1.0 ns missed hold (v2 -0.001 ns, 3 paths; v3 -0.002 ns, 8 paths); passes (holdfix.tcl): optDesign
  -postRoute -hold, then hold target slack 0.01 ns plus one DRC-retry ecoRoute. Earlier flows failed 0.9-1.1 ns. GLS, power, v2/v3: 1.1 ns only.
## Post-route GLS at 1.1 ns (TABLES.md "Post-route GLS", "SDF variant check", "Export"), both 200,000-request slices
- Innovus netlist (no physical-only cells) and SDF. Zero-delay and SDF lockstep passed, v2 and v3, row0 and row1M: 0 mismatching and 0 X
  cycles, hit logs identical to the P9/P10 RTL logs. SDF path delays 100.00% annotated (v2 841055/841055, v3 878949/878949); timing
  checks 0.00% (v2 0/468796, v3 0/450970; both write_sdf variants; SDF has 40245 / 40253 TIMINGCHECK blocks), so 0 violations is no check.
## Post-route power at 1.1 ns (TABLES.md "Post-route power"): post-route, typical corner, path delays annotated, timing checks not annotated
Genus report_power: routed netlist, SDC, Innovus SPEF (0 nets not annotated), TCF of the SDF run. Energy/request = total x cycles x 1.1 ns / 200,000.
| netlist | slice | total W | internal | switching | leakage | logic share (bound) | driver nets annotated | energy/request |
|---|---|---|---|---|---|---|---|---|
| v2 | row0 | 2.25440e-01 | 1.75024e-01 | 5.02946e-02 | 1.21369e-04 | 2.72% | 48.74% | 1011.49 pJ |
| v2 | row1M | 2.24874e-01 | 1.74806e-01 | 4.99472e-02 | 1.21410e-04 | 2.48% | 48.74% | 1000.41 pJ |
| v3 | row0 | 2.27787e-01 | 1.75912e-01 | 5.17499e-02 | 1.25777e-04 | 3.21% | 48.95% | 924.68 pJ |
| v3 | row1M | 2.28118e-01 | 1.76001e-01 | 5.19920e-02 | 1.25761e-04 | 3.34% | 48.95% | 932.72 pJ |
- v3 against v2: energy per request row0 -86.81 pJ (-8.58%), row1M -67.70 pJ (-6.77%); total power +1.04% / +1.44%, cycles -9.52% / -8.09%.
- Coverage: ports and flop outputs 100%, driver nets 48.74% / 48.95% asserted (rest computed); logic share 2.48-3.34% = uncertainty
  bound; registers 71.89-72.92%, clock tree 24.54-24.80% (its nets are not listed separately in the coverage report).
## Method notes and limitations
- One typical corner; Innovus checks only (no signoff STA/DRC/LVS); well-tap rule 40 um: 2 violations per run, in end-cap-only rows.
  Not comparable with P13 power (0.8 ns, no clock tree or parasitics). Energy depends on the testbench miss model.
- Licence: only aggregate results are published (approval Prof. Mane gave for P12/P13); no library data, cell names or raw reports.
