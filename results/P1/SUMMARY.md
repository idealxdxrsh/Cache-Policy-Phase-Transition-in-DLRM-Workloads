# P1 RTL fix: summary (2026-10-23)

Tools (local): Icarus Verilog 12.0, Yosys 0.33 (Ubuntu apt packages).
Reproduce: `bash rtl/v2/run_rtl.sh` then `python3 tools/mutate_rtl.py`.

## Change
- `rtl/v2/lfu_cache_controller.v`: new parameter `COUNTER_MODE` (default 0).
  - 0: count set to 1 when a tag is installed (reset-on-eviction LFU).
  - 1: original v2 (slot keeps its count; new tag gets old count + 1).
  - 2: not implemented (address-indexed history is pending Prof. Mane). Any mode
    other than 0/1 stops at elaboration with `$fatal` (`results/P1/mode2_check.txt`).
  - Neither implemented mode keeps per-address history.
- `rtl/v2/tb_lfu_cache.sv`: COUNTER_MODE parameter (`-P tb_lfu_cache.COUNTER_MODE=N`),
  VCD only with `+vcd`, new test [7]: victim identity, the other 255 lines unchanged,
  install count (mode 0: 1, mode 1: 3+1=4) and the mode-specific next victim.
- `rtl/v2/run_rtl.sh`: loops over modes 0 and 1; dropped the `srun --pty` hint.
- `tools/mutate_rtl.py`: mutation check (new).

## Tests (`results/P1/sim_mode0.txt`, `results/P1/sim_mode1.txt`)
- Mode 0: ALL TESTS PASSED (7 tests). Mode 1: ALL TESTS PASSED (7 tests).
- Test [5] skewed workload: 1932/2000 hits (96.60%) in both modes, so this test
  does not tell the modes apart; only test [7] does.

## Mutation (`results/P1/mutation.txt`)
- Baseline passes in both modes. 6 mutants x 2 modes = 12 runs.
- Killed in every mode where they can have an effect: stale_victim_reg, stale_stageA,
  double_increment_hit, double_increment_fill (mode 1), install_count_2 (mode 0),
  mode0_keeps_count (mode 0).
- 3 runs survive as expected, because they change code the mode never executes:
  double_increment_fill/mode 0, install_count_2/mode 1, mode0_keeps_count/mode 1.
- RESULT: OK, exit status 0.

## Synthesis (`results/P1/synth_cells_mode0.txt`)
- Generic Yosys `synth`, no liberty, default COUNTER_MODE=0 only: 144487 cells.
  This is a generic gate count only: no area, timing or power, and not TSMC.
  Per-mode synthesis on NanGate45 is P5.

## Open
- COUNTER_MODE=2 is waiting on Prof. Mane's decision on the counter scheme.
