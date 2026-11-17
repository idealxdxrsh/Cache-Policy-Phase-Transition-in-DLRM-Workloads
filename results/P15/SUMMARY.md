# P15: Innovus place and route of the d16 and merge-off d256 netlists on the lab server C2
Technology: a commercial 28nm FD-SOI standard-cell library, typical corner (typical 1.00 V 25 C libraries, nominal RC); areas in library units.
Every number is from results/P15/TABLES.md (tools/p15_collect.py on the run reports, which stay off the repo). Flow: cadence/pnr/
(run_pnr.csh, pnr.tcl, stageA.tcl, stageB.tcl). Runs: v3_m0_d16_p0.8 at 0.8 ns; v2 and v3_m0_d256_p0.8_nomerge (P12/P13 netlists) at 0.8 and 0.9 ns.

## d16 (v3, 0.8 ns): clean except a 4 ps setup miss
- Setup WNS -0.004 ns, TNS -0.013 ns, 5 violating paths; hold WNS +0.057 ns, 0 violating.
- DRC 0; verifyConnectivity 0 problems on all nets, on the 4 PG nets and on the 4 PG nets metal only.
- Well-tap spacing rule 40 um: 2 violations on the full core, 0 on the inner rows (without the bottom and top end-cap rows).

## d256 (v2 and v3 merge-off): routed, but neither timing-closed nor DRC/PG clean
| run | period | setup WNS / TNS ns (viol. paths) | hold WNS ns (viol.) | DRC | PG conn. problems | power mW |
|---|---|---|---|---|---|---|
| v2 | 0.8 | -0.102 / -116.917 (1864) | -0.001 (2) | 46 | 48 | 366.2748 |
| v2 | 0.9 | -0.012 / -0.240 (70) | 0.000 (0) | 19 | 21 | 322.0320 |
| v3 | 0.8 | -0.164 / -241.688 (1922) | -0.003 (20) | 39 | 36 | 360.2312 |
| v3 | 0.9 | -0.077 / -96.836 (1874) | -0.002 (17) | 25 | 24 | 317.7485 |
- All connectivity problems are on the 4 PG nets (all-net count = PG count in every run).
- Defect (TABLES.md "DRC and PG-connectivity breakdown"): 15 / 6 / 11 / 7 logic instances (v2 0.8 / v2 0.9 / v3 0.8 / v3 0.9)
  each give 3 metal shorts between a PG special wire and a cell pin (45 / 18 / 33 / 21 shorts), and the same instances
  (overlap = all of them) have the unconnected PG terminals (IMPVFC-96: 45 / 18 / 33 / 21). Remaining DRC: 1 / 1 / 6 / 4
  end-of-line spacing on signal wires. Each run also has 3 IMPVFC-200 (special-route pieces not connected); d16 has none.
  Root cause not diagnosed yet (needs a query of the routed database on C2); d16 did not show it.
- Well-tap rule 40 um: 2 violations full core, 0 inner rows, in all 4 runs. Run time 0:57:09 to 1:03:15 per run (16 CPUs).
- v3 vs v2 (computed from TABLES.md rows): power -1.65% at 0.8 ns, -1.33% at 0.9 ns; logic cell area +2.33% / +1.78%.
  Neither design meets timing at either period, so these are not comparisons at timing closure.

## Method notes
- Body bias: only the well-tap body-bias pins are marked and routed by routeDesign; the end-cap body pins are not.
- Corner cells: the library's dedicated corner end caps of the top/bottom end-cap family, chosen by cell name and LEF class;
  Innovus's corner options are crossed against the core corners (stageA.tcl); end-cap rules not checked against a design-rule manual.
- Full-core well-tap violations (2 per run) are in the bottom and top rows, which hold only end caps (known limitation).

## Limitations
- Power is report_power with Innovus default activity (0.2 at primary inputs and sequential outputs), not simulation
  activity; it is not comparable with the P13 TCF-based power.
- One typical corner; no signoff extraction, STA or DRC/LVS deck (Innovus checks only); d256 has open DRC/PG defects; d16 is v3 only.
- Licence: the library is used under a licence; only aggregate results are published (approval Prof. Mane gave for P12/P13),
  no library data, cell names or raw reports.
