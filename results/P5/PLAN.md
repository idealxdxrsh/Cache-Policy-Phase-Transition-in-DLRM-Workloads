# P5 plan: NanGate45 synthesis + OpenSTA timing of rtl/v2 (local, nothing downloaded or run yet)
Every result from this phase is labelled **"NanGate45, not TSMC"**. No power numbers: no power step is planned.

## Configurations
- `rtl/v2/lfu_cache_controller.v`, CACHE_DEPTH 16, 64, 256 x COUNTER_MODE 0, 1 x clock 1 GHz (1.0 ns), 500 MHz (2.0 ns)
  = 12 synthesis + STA runs. Other parameters at their defaults: ADDR_WIDTH 20, VECTOR_WIDTH 128, COUNTER_WIDTH 6, GROUPS 16
  (so depth 16 has 1 slot per group).
- "Every COUNTER_MODE" = 0 and 1. Mode 2 is not implemented (pending Prof. Mane) and elaboration stops with `$fatal`
  by design (lines 58-59); the driver records that failure once, as a check.
- Before synthesis: simulate every depth x mode with Icarus. `tb_lfu_cache.sv` fixes `CACHE_DEPTH = 256` as a localparam
  (line 15), so it would become a parameter (default 256, unchanged behaviour). Whether the testbench passes at 16 and 64
  is unknown until run; a failure stops the phase for that depth.

## Flow (driver `synthesis/p5/run_p5.sh`, local, no cluster job)
1. Yosys 0.33 (installed, `/usr/bin/yosys`): `read_verilog -sv`, `chparam`, `synth -flatten`, `dfflibmap -liberty`,
   `abc -liberty -D <period ps>`, `opt_clean`, `stat -liberty`, `write_verilog`. One netlist per clock (abc uses the target).
2. OpenSTA: `read_liberty`, `read_verilog`, `link_design`, `create_clock -period {1.0|2.0} clk`, input/output delay 0
   relative to clk, ideal clock, liberty wire-load model. `report_checks` (max and min), `report_wns`, `report_tns`, slew/cap
   violators.
- Reported per run: cell count, flip-flop count, cell area from `stat -liberty` (the sum of liberty cell areas, not a
  placed layout area), WNS/TNS, critical path. The planned Fmax is 1/(period - WNS) and is labelled pre-layout.
- The tag/data/counter arrays become flip-flops (no SRAM macro; ORFS `fakeram45` models are not real memories, so they are
  not used). Most of the area at depth 256 will be the 256 x 128-bit data array as flops; this will be stated.
- Outputs: `results/P5/d<D>_m<M>_<F>MHz/{yosys.log, stat.txt, netlist.v, sta.txt, time.txt}`, `results/P5/SUMMARY.md`.
  Wall time and peak RSS are measured with `tools/timev.py` (runtime not known yet: no NanGate45 run has been done).

## What needs downloading / installing (ask before each)
| item | source (pinned) | size | licence |
|---|---|---|---|
| NanGate45 liberty `NangateOpenCellLibrary_typical.lib` | OpenROAD-flow-scripts `flow/platforms/nangate45/lib/`, last changed in commit 6c6fc7e21b2d0b5b88b1a52d0a5860ea4d88e9e5 (2021-07-20) | 6,692,032 bytes (GitHub API) | `flow/platforms/nangate45/LICENSE` = Apache-2.0; the file's own header (NanGate/Si2 Open Cell Library terms) is read after download, before use |
| CUDD (required by OpenSTA) | github.com/cuddorg/cudd, tag 3.0.0 = f54f533303640afd5dbe47a05ebeabb3066f2a25 | repo 2,466 KiB (GitHub API) | BSD-3-Clause |
| OpenSTA | github.com/parallaxsw/OpenSTA, no release tags; pin the newest master commit at least 2 weeks old, SHA recorded | repo 57,323 KiB (GitHub API) | GPL-3.0 |
| apt build deps (**needs sudo, system-wide**) | Ubuntu 24.04: cmake swig bison flex tcl-dev libeigen3-dev (zlib1g-dev, g++, make, git present) | `apt-get install -s`: 17 new packages, 18,189,998 bytes download, 71,419 KiB installed | Ubuntu archive packages |
- CUDD and OpenSTA are built from source with their own `configure` / CMake scripts (downloaded scripts: needs your OK)
  into a user prefix `~/eda` (sources in `~/eda/src`), not `/usr/local`. Build size is unknown until built; 20G free on `/`.
- The liberty file goes to `~/eda/pdk/nangate45/`, with its sha256 recorded in `results/P5/sources.txt`; it is not committed.
- Not used: OpenROAD (no placement/routing planned), Docker (not installed), conda (not installed).

## Labels in every results file and SUMMARY.md
"NanGate45, not TSMC"; "pre-layout (wire-load model, ideal clock)"; "area = sum of liberty cell areas"; "no power".
