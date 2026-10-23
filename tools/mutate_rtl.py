#!/usr/bin/env python3
"""Mutation check for rtl/v2: the testbench must FAIL on broken RTL copies.

Each mutant is one exact text substitution in a copy of
lfu_cache_controller.v (the original is never modified). Every mutant is
simulated in every COUNTER_MODE. A mutant is "killed" if the testbench does
not print ALL TESTS PASSED. Cells marked equivalent change code that the
mode never executes, so surviving there is expected.

    python3 tools/mutate_rtl.py [--out results/P1/mutation.txt]
Exit status is non-zero if the unmutated RTL fails or any non-equivalent
mutant survives.
"""
import argparse, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
RTL = ROOT / "rtl/v2/lfu_cache_controller.v"
TB = ROOT / "rtl/v2/tb_lfu_cache.sv"
MODES = (0, 1)

# name -> (description, old text, new text, modes where the mutant is equivalent)
MUTANTS = {
    "stale_victim_reg": (
        "EVICT does not latch the new victim; FILL writes the previous victim slot",
        "victim_reg                <= victim_comb;", "", ()),
    "stale_stageA": (
        "Stage A group minima never refreshed (victim from stale/reset indices)",
        "if (state == LOOKUP && !hit_detected) begin",
        "if (state == LOOKUP && !hit_detected && 1'b0) begin", ()),
    "double_increment_hit": (
        "hit adds 2 to the counter instead of 1",
        "freq_cnt[hit_idx] <= freq_cnt[hit_idx] + 1'b1;",
        "freq_cnt[hit_idx] <= freq_cnt[hit_idx] + 2'd2;", ()),
    "double_increment_fill": (
        "mode-1 fill adds 2 to the slot count instead of 1",
        "freq_cnt[victim_reg] <= freq_cnt[victim_reg] + 1'b1;",
        "freq_cnt[victim_reg] <= freq_cnt[victim_reg] + 2'd2;", (0,)),
    "install_count_2": (
        "mode-0 install sets the count to 2 instead of 1",
        "freq_cnt[victim_reg] <= {{(COUNTER_WIDTH-1){1'b0}}, 1'b1};",
        "freq_cnt[victim_reg] <= {{(COUNTER_WIDTH-2){1'b0}}, 2'b10};", (1,)),
    "mode0_keeps_count": (
        "COUNTER_MODE ignored: mode 0 behaves like mode 1",
        "if (COUNTER_MODE == 0)", "if (1'b0)", (1,)),
}


def simulate(rtl_path, mode, work):
    exe = work / f"sim_m{mode}"
    c = subprocess.run(["iverilog", "-g2012", f"-Ptb_lfu_cache.COUNTER_MODE={mode}",
                        "-o", str(exe), str(rtl_path), str(TB)],
                       capture_output=True, text=True)
    if c.returncode != 0:
        return False, "compile error: " + c.stderr.strip().splitlines()[-1]
    r = subprocess.run(["vvp", "-n", str(exe)], capture_output=True, text=True,
                       cwd=work, timeout=600)
    out = r.stdout
    fails = [l.strip() for l in out.splitlines() if "FAIL" in l]
    return "ALL TESTS PASSED" in out, "; ".join(fails[:3]) or "(no FAIL lines)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results/P1/mutation.txt"))
    args = ap.parse_args()
    src = RTL.read_text()
    lines, bad = [], False
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        for m in MODES:
            ok, info = simulate(RTL, m, work)
            lines.append(f"baseline mode={m}: {'PASS' if ok else 'FAIL ' + info}")
            bad |= not ok
        for name, (desc, old, new, equiv) in MUTANTS.items():
            n = src.count(old)
            if n != 1:
                lines.append(f"{name}: target text found {n} times, mutant not applied")
                bad = True
                continue
            mpath = work / f"{name}.v"
            mpath.write_text(src.replace(old, new))
            for m in MODES:
                passed, info = simulate(mpath, m, work)
                if m in equiv:
                    verdict = "survived (equivalent, expected)" if passed else "KILLED (equivalent cell)"
                else:
                    verdict = "KILLED" if not passed else "SURVIVED (testbench gap)"
                    bad |= passed
                lines.append(f"{name} mode={m}: {verdict} | {desc}" +
                             ("" if passed else f" | {info}"))
    lines.append("RESULT: " + ("FAIL" if bad else "OK (all non-equivalent mutants killed)"))
    text = "\n".join(lines) + "\n"
    pathlib.Path(args.out).write_text(text)
    print(text, end="")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
