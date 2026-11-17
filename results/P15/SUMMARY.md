# P15: Innovus place and route of the d16 and merge-off d256 netlists on the lab server C2
Technology: a commercial 28nm FD-SOI standard-cell library, typical corner (typical 1.00 V 25 C libraries, nominal RC); areas in library units.
Every number is from results/P15/TABLES.md (tools/p15_collect.py on the run reports, which stay off the repo). Flow: cadence/pnr/
(run_pnr.csh, pnr.tcl, stageA.tcl, stageB.tcl); diagnosis: cadence/pnr/diag_shorts.tcl, run_diag.csh. Netlists synthesised at 0.8 ns.

## First flow: d256 PG-rail shorts caused by double-height cells (TABLES.md "Diagnosis", "DRC and PG-connectivity breakdown")
- d256 v2/v3 at 0.8 and 0.9 ns: 15 / 6 / 11 / 7 instances each shorted 3 PG rails on M2 and had unconnected PG terminals.
- Each run uses exactly 1 multi-row master (height 2.00 rows, on a row of its own site, 2 row sites in the design); every
  multi-row instance shorts and no other does; 0 single-row masters of another site. d16 uses none (1 row site), DRC 0.
- Origin: Genus netlist names 2-4 per run, the rest created by Innovus restructuring (FE_RC prefix) in place_opt (4-6) and
  CTS + postCTS optimisation (0-7); none in postRoute optimisation.

## Fix (stageA.tcl, stageB.tcl; TABLES.md "Fix")
- All 29 library cells taller than one core-site row are dont_use; the netlist's multi-row instances (v2 8, v3 6, d16 0) are
  resized to single-row cells with ecoChangeCell before the floorplan (all resized, 0 left); 0 multi-row instances after route.

## Fixed flow results (TABLES.md "Post-route results", flow "multi-row dont_use")
| run | period ns | setup WNS / TNS ns (viol. paths) | hold WNS ns (viol.) | DRC | conn. problems all nets | power mW |
|---|---|---|---|---|---|---|
| v3 d16 | 0.8 | -0.001 / -0.001 (1) | 0.056 (0) | 0 | 0 | 21.4664 |
| v2 d256 | 0.9 | -0.022 / -0.547 (144) | 0.001 (0) | 2 | 0 | 318.0970 |
| v2 d256 | 1.0 | -0.007 / -0.092 (37) | 0.000 (0) | 0 | 0 | 274.9076 |
| v3 d256 | 0.9 | -0.071 / -85.861 (1863) | -0.002 (9) | 2 | 0 | 316.2335 |
| v3 d256 | 1.0 | -0.007 / -0.030 (22) | 0.004 (0) | 1 | 0 | 271.4632 |
- d16 stays clean (DRC 0, connectivity 0). PG shorts and PG opens are gone in all d256 runs; the remaining DRC are 1-2 M1
  signal-wire spacing violations (OppositeEol, Notch), the kind the first flow also had (1-6 per run).
- No d256 run meets setup; at 1.0 ns both miss by 0.007 ns (reg2reg paths). Well-tap rule 40 um: 2 violations full core,
  0 inner rows, in every run. Run time 0:47:50 to 0:57:35 per d256 run, 0:04:41 for d16 (16 CPUs).
- v3 vs v2 (from TABLES.md rows; not at timing closure): power -0.59% at 0.9 ns, -1.25% at 1.0 ns; logic area +2.55% / +0.42%.

## Method notes and limitations
- Body bias: only the well-tap body-bias pins are marked and routed by routeDesign; the end-cap body pins are not.
- Corner cells: the library's dedicated corner end caps (top/bottom end-cap family; Innovus's corner options crossed, stageA.tcl);
  end-cap rules not checked against a design-rule manual. Full-core well-tap violations are in the end-cap-only bottom/top rows.
- Power: report_power, Innovus default activity (0.2), not comparable with P13. One typical corner; no signoff extraction,
  STA or DRC/LVS deck (Innovus checks only); d16 is v3 only.
- The fix resizes 8 (v2) / 6 (v3) netlist instances before placement, on top of Innovus's own optimisation; not re-verified by GLS.
- Licence: only aggregate results are published (approval Prof. Mane gave for P12/P13); no library data, cell names or raw reports.
