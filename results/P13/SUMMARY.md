# P13: gate-level simulation and power of the merge-off netlists v2/v3_m0_d256_p0.8_nomerge on the lab server C2
Technology: a commercial 28nm FD-SOI standard-cell library, typical corner; clock 0.8 ns; 200,000 requests per slice; netlist in lockstep with its RTL, every cycle.
Every number is from results/P13/TABLES.md (tools/p13_power_table.py on the raw reports, which stay off the repo). Flow: cadence/run_gls.csh,
synthesis/p13/tb_gls_c2.sv, cadence/genus_power.tcl, run_power.csh, genus_write_sdf.tcl. Aggregate results published with Prof. Mane's approval.

## Lockstep (TABLES.md "Lockstep"; SDF inputs 160 ps after the clock edge)
| netlist | slice | cycles | zero-delay: mismatching / X cycles | SDF: mismatching / X cycles | netlist hit log vs P9/P10 RTL log |
|---|---|---|---|---|---|
| v2 | row0 | 815771 | 0 / 0 | 0 / 0 | 0 of 200000 lines differ (both modes) |
| v2 | row1M | 808867 | 0 / 0 | 0 / 0 | 0 of 200000 |
| v3 | row0 | 738077 | 0 / 0 | 0 / 0 | 0 of 200000 |
| v3 | row1M | 743408 | 0 / 0 | 0 / 0 | 0 of 200000 |
SDF: path delays annotated 870937/870937 (v3), 835004/835005 (v2); timing checks 0% annotated (conditional checks in the cell models; 3 write_sdf variants tried, all 0%: TABLES.md "SDF variants").

## Power (report_power with each SDF run's TCF) and energy per request = total x cycles x 0.8 ns / 200,000 (TABLES.md "Power")
Label: path delays annotated, timing checks not annotated; flip-flop outputs and ports 100% annotated, combinational driver nets 42% annotated; combinational logic is 1.5 to 2.2% of total power, so its uncertainty bounds total power by about +/-2.2%.
| netlist | slice | total W | internal | switching | leakage | logic share | driver nets annotated | energy/request | P12 vectorless W |
|---|---|---|---|---|---|---|---|---|---|
| v2 | row0 | 2.27987e-01 | 2.25406e-01 | 2.47059e-03 | 1.10065e-04 | 1.49% | 41.95% | 743.94 pJ | 2.77266e-01 |
| v2 | row1M | 2.27986e-01 | 2.25430e-01 | 2.44648e-03 | 1.10096e-04 | 1.49% | 41.95% | 737.64 pJ | 2.77266e-01 |
| v3 | row0 | 2.29104e-01 | 2.25857e-01 | 3.13610e-03 | 1.10367e-04 | 2.00% | 42.15% | 676.39 pJ | 2.75337e-01 |
| v3 | row1M | 2.29615e-01 | 2.26108e-01 | 3.39665e-03 | 1.10360e-04 | 2.21% | 42.15% | 682.79 pJ | 2.75337e-01 |
v3 vs v2 energy per request (TABLES.md "v3 against v2 per slice"): row0 -67.56 pJ (-9.08%), row1M -54.85 pJ (-7.44%); total power +0.49% / +0.71%, cycles -9.52% / -8.09%.

## Limitations
- Pre-layout: no LEF, library default (zero) wireload, no extracted parasitics; one typical corner only.
- Timing checks not annotated in SDF simulation: 0 violations is not a timing sign-off.
- Partial activity coverage: combinational driver nets about 42% annotated (rest computed by Genus).
- Energy per request depends on the testbench's miss model (cycles per miss come from the testbench's fill handshake, 0-3 random cycles, not a real memory system) and on two 200,000-request slices (row0, row1M) of one dataset.
- Covers only the two merge-off d256 m0 netlists; one simulation per point.
- Licence: the library is used under a licence; only aggregate results are published (approved by Prof. Mane), no library data, cell names or raw reports.
