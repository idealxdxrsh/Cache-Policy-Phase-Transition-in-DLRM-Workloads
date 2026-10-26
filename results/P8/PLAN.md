# P8 plan: power analysis of the final controller (rtl-v2-final, P5e netlists) — NOT RUN YET, awaiting OK

Every power number this phase produces will carry the label:
**"NanGate45, typical corner, pre-layout, no clock tree, no extracted parasitics, flip-flop storage, activity from
<method> over <N> cycles"**. No comparison to any other process or chip.

## 0. Inputs
- Netlists: the P5e-flow 1 GHz netlists of tag `rtl-v2-final` (commit 7705a7b), regenerated in P5f with sha256 equal
  to `results/P5e/new/netlists.sha256` (`results/P5f_gls/netlists/netlists.sha256`); 6 configurations: depth 16, 64,
  256 x COUNTER_MODE 0, 1.
- Liberty: NanGate45 typical (`results/P5/SOURCES.md`: sha256 8d540a4d...4e9b1, corner typical, 25C, 1.1V).
- OpenSTA 3.1.0 (commit 7b261909c1), the same binary as P5-P5e.

## 1. Liberty check (done, read-only)
- 135 cells; 2,459 `internal_power` groups; 1,942 state-dependent `leakage_power` groups; `cell_leakage_power` in 126
  cells; units: leakage 1 nW, voltage 1 V, capacitance 1 fF, time 1 ns.
- The 9 cells without leakage or internal power are FILLCELL_X1..X32, TAPCELL_X1, LOGIC0_X1, LOGIC1_X1.
- All 84 cell types used by the netlists (`results/P5f_gls/COVERAGE.md`) have both leakage and internal-power data.
  Sequential cells used: DFFR_X1, DFF_X1.
- Commands: see the session record; the check script is a one-off read of the liberty (not committed, the liberty is
  not redistributed).

## 2. OpenSTA facts that shape the plan (installed version, source in `~/eda/src/OpenSTA/power`)
- Present: `report_power`, `read_vcd` (gzip OK; `-scope`, `-begin_time`, `-end_time`), `read_saif`,
  `set_power_activity`, `report_activity_annotation`.
- Report groups: Sequential, Combinational, **Clock**, Macro, Pad. An instance counts as Clock only if all its outputs
  are clock nets. With an ideal clock and no clock tree there are no such instances, so **Clock will be 0 W**; the
  flip-flops' clock-pin internal power is reported under Sequential. Every report will say this next to the 0.
- Vectorless defaults: input ports 0.1 transitions per clock period (= 1e8/s at 1 GHz), duty 0.5; the clock net 2
  transitions per period; flip-flop outputs take the activity of their D input, limited to
  2 x duty x (1 - duty) x clock density when D toggles faster than half the clock (`Power::seedRegOutputActivities`).
- Pitfall found in the sanity check: `set_power_activity -density` is "transitions per library time unit" and gave a
  wrong scale; the plan uses only `-activity` (transitions per clock cycle).

## 3. Sanity check on a hand-checkable netlist (done; `synthesis/p8/sanity/`, outputs `results/P8/sanity/`)
Netlist: one INV_X1 (`\inv[0]`) between ports, input slew 0.00117378 ns and load 3.795620 fF (liberty table index
points, no interpolation, no wire load), 1 GHz clock; plus four more INV_X1 through an escaped internal vector
(`\cnt[1] [1:0]`) and a 2-bit port `w[1:0]`, and one DFF_X1 (group check only). Liberty values used (single entries):
INV_X1 ZN rise_power 1.942968, fall_power -0.000070 at those index points; leakage 10.102224 (A=0) and 18.604146
(A=1) nW; V = 1.1.

| `\inv[0]` | hand calculation | OpenSTA, set_power_activity -activity 1.0 | OpenSTA, read_vcd (1000 cycles) |
|---|---|---|---|
| internal W | 1e9 x (1.942968 - 0.000070)/2 fJ = 9.71449e-07 | 9.714489e-07 | 9.719347e-07 (+0.05%) |
| switching W | 0.5 x 3.795620 fF x 1.1^2 x 1e9 = 2.29635e-06 | 2.296350e-06 | 2.297498e-06 (+0.05%) |
| leakage W | (10.102224 + 18.604146)/2 nW = 1.4353185e-08 | 1.435318e-08 | 1.435318e-08 |
| total W | 3.282152e-06 | 3.282152e-06 | 3.283786e-06 |

- Default vectorless (0.1 per cycle): internal 9.714490e-08, switching 2.296350e-07 W = hand values x 0.1 (exact).
- VCD +0.05% on every cell: window-edge effect of the 1000-cycle dump; the runs below use `-begin_time/-end_time` on
  cycle boundaries and 10,000-cycle windows.
- Name mapping: 19 of 20 pins annotated from the Icarus VCD, including the escaped vector `\cnt[1] [0]`/`[1]` and the
  bus port `w[1:0]`. Not annotated: the 1-bit vector port `y[0]` (Icarus writes `y[0:0]` as plain `y`); its net is
  annotated through `\inv[0]/ZN`, so power is unaffected. The controller has no 1-bit vector ports.
- Clock group 0 W; the DFF_X1 is in Sequential (as section 2 predicts).

## 4. Configurations and activity methods
All at the 1 GHz clock (period 1 ns), typical corner, wire-load model 5K_hvratio_1_1, same constraints as
`synthesis/p5/sta.tcl` (BUF_X1 input driver, 3.795620 fF output load). **Question 1 below: these netlists do not meet
1 GHz (pre-layout Fmax 542-660 MHz, `results/P5e/SUMMARY.md`).**

(a) **Vectorless**: OpenSTA default input activity 0.1 per cycle, duty 0.5, on every input except `rst_n`, which is
set to activity 0, duty 1 (held inactive, as in operation; otherwise the reset net would toggle every flip-flop's
reset pin); flip-flop outputs propagated by OpenSTA's rule above. Label method "vectorless (OpenSTA default 0.1 per
cycle on inputs, rst_n held)".

(b) **Vector-based**: zero-delay gate-level simulation of the same netlist with the Yosys-generated cell models
(Icarus; as P5f), the RTL not instantiated. Two stimuli, same request/fill handshake as P5f (fill delay 0-3 cycles,
seed 1):
  - (b1) the P5f random stimulus of `synthesis/p5f/tb_gls_lockstep.sv` (seed 1);
  - (b2) a Criteo request stream (section 5): one request outstanding, the next one presented in the cycle after the
    response.
  - Window: W = 20,000 cycles of warm-up (not recorded), then N = 10,000 cycles recorded. In P5f the random stimulus
    gave 200,000/65,436 = about 3 cycles per response at depth 16 (`results/P5f_gls/cluster/lockstep/`), so N covers
    roughly 3,300 responses; the exact counts will be reported.
  - Hit rate of the stimulus = hits / responses, counted by the testbench over the window and over the whole run.
    For reference, the P5f random stimulus over 200,000 cycles: 57,297 hits of 65,436 responses at depth 16 mode 0
    (`results/P7/TABLES.md`).
  - Zero delay means no glitches, so combinational switching and internal power are lower bounds for this activity.

## 5. Criteo request stream (b2)
- First 2,000,000 rows of Criteo DAC `train.txt` (on Sharanga, `/scratch/rahulkmr/Adarsh/data/criteo/extracted/`),
  access order and keys exactly as P3b's shared cache (`trace_sim/run_shared_cache.py`: rows in file order, tables
  0..25 within a row, empty/non-hex fields skipped, key = table << 32 | id).
- Address mapping (**Question 2**): keys are numbered in order of first appearance (dense IDs) and the ID is the
  20-bit request address. Only the first W+N cycles' worth of requests is replayed (about 10,000 requests), far fewer
  distinct keys than 2^20, so there is no aliasing; the script checks this and writes the count. "256-entry-sized"
  is read as: the same stream drives depth 16, 64 and 256, and the shared-cache result at 256 entries (P3b) is the
  reference workload. If you meant a different mapping (e.g. folding keys into a 256-entry address range), say so.
- The RTL policy differs from the simulators (tie-break, 63 vs 255 saturation; `results/P7/CLAIMS.md`), so the
  RTL hit rate will not equal the P3b number; both will be stated, not compared as equal.

## 6. Activity file size, format and name mapping
- Size bound: at most one value change per net per cycle. Depth 256 has 151,253 `wire` declarations (local
  `results/P5f_gls/netlists/d256_m0_1000MHz/netlist.v`, not committed); at about 8 bytes per change that is at most
  about 1.2 GB per 1,000 cycles uncompressed, so a full 10,000-cycle VCD could reach about 12 GB. The real value
  depends on the toggle rate, measured first on depth 16 (pilot, local, 2,000 cycles).
- Format: **SAIF, written by streaming**. vvp writes the VCD into a named pipe; a Python reader (`tools/vcd2saif.py`,
  new) counts toggles and high time per signal over the window and writes a SAIF file (one line per net, size
  independent of N). No large VCD is stored. OpenSTA reads it with `read_saif -scope`. Before use, the converter is
  validated on the sanity netlist: `read_saif` must give the same power as `read_vcd` within 0.1%. If the pilot shows
  the depth-16/64 VCD under 2 GB gzipped, those may also be read directly with `read_vcd` as a cross-check.
- Name mapping: scope `tb/gl` (testbench instance of the netlist); escaped Yosys names and bus ports map as shown in
  the sanity check. Every run records `report_activity_annotation` (annotated / unannotated pin counts); acceptance:
  every unannotated pin is listed, and the run is flagged if more than 1% of pins are unannotated.

## 7. Expected run time and memory (from measured P5-P5f runs; the VCD overhead is unknown until the pilot)
| step | depth 16 | depth 64 | depth 256 | source |
|---|---|---|---|---|
| P5f gate-level lockstep, 200,000 cycles, with RTL model | 7:53 | 25:07 | 1:37:59 | `results/P7/TABLES.md` (P5f) |
| its peak RSS | 65 MB | 212 MB | 820 MB | same |
| iverilog compile peak RSS (cluster) | 165 MB | 547 MB | 2.1 GB | `results/P5f_gls/cluster/{sim,lockstep}/` |
| OpenSTA timing run, wall / peak RSS | 1.5 s / 100 MB | 4.5 s / 226 MB | 16.8 s / 747 MB | `results/P5e/new/d*_m0_1000MHz/time_sta.txt` |
- One P8 simulation run is 30,000 cycles (W + N) without the RTL model, so the simulation itself should take well
  under the P5f times scaled by 30,000/200,000; VCD output and the SAIF reader add an unknown factor, measured in the
  pilot. The power step is one OpenSTA run per configuration and method.
- Plan: depth 16 and 64 locally (both stimuli, both modes) after the pilot; depth 256 on the cluster (memory, and the
  Criteo data is there). OpenSTA is installed locally only, so the cluster writes SAIF files and the power step runs
  locally on them (SAIF files are small).

## 8. Cluster jobs (none submitted; need your OK)
| job | what | partition / CPUs | memory | time limit | dependency |
|---|---|---|---|---|---|
| p8_stream | build the Criteo request stream (section 5) from the first 2,000,000 rows -> stream file + stats | compute / 1 | 8 GB | 1:00:00 | none |
| p8_gls256 (array 1-4, %4) | depth 256 x mode 0/1 x stimulus random/Criteo: gate-level simulation, VCD pipe -> SAIF | compute / 4 | 8 GB | 4:00:00 | afterok p8_stream |
- Optional, only if the pilot shows depth 64 is slow locally: p8_gls64 (array 1-4), compute / 4, 4 GB, 2:00:00.
- After the jobs: rsync SAIF files and logs back, `sacct` for MaxRSS, then the local OpenSTA power runs.

## 9. Execution order once approved
1. `tools/vcd2saif.py` + validation on the sanity netlist (read_saif vs read_vcd within 0.1%).
2. Pilot: depth 16 mode 0, random stimulus, 2,000 cycles, local: VCD bytes per cycle, sim time, annotation coverage.
3. Vectorless runs, 6 configurations, local.
4. Cluster: p8_stream, then p8_gls256; locally in parallel: depth 16 and 64 vector-based runs.
5. Power: one `report_power` per configuration and method; tables with internal, switching, leakage and total power,
   split Sequential / Combinational / Clock (0, explained), plus N, warm-up W, hit rate, annotation coverage, and the
   label above. `results/P8/SUMMARY.md` (< 40 lines), commit, stop.

## 10. Questions for you before running
1. The 1 GHz netlists do not meet 1 GHz. Report power at 1 GHz anyway (as asked, labelled "at 1 GHz clock; timing not
   met at 1 GHz pre-layout"), or also at 500 MHz (met at depths 16 and 64), or energy per cycle (power / frequency)?
2. Criteo address mapping: dense first-appearance IDs (section 5), or another reading of "256-entry-sized address
   space"?
3. Criteo replay handshake: one request outstanding, next request the cycle after the response, fill delay 0-3
   cycles as P5f. OK?
4. Window: 20,000 warm-up + 10,000 recorded cycles for every configuration. OK?
5. Vectorless: rst_n held inactive (activity 0). OK?
