#!/usr/bin/env python3
"""Mutation check for rtl/v2: the testbench must FAIL on broken RTL copies.

Each mutant is one exact text substitution in a copy of
lfu_cache_controller.v (the original is never modified). Every mutant is
simulated in every COUNTER_MODE. A mutant is "killed" if the testbench does
not print ALL TESTS PASSED. Cells marked equivalent change code that the
mode never executes (or, for a depth, logic that is not generated at that
depth), so surviving there is expected.

With --lockstep, a mutant the testbench does not kill is also run against the
rtl-v2-baseline tag in synthesis/p5b/tb_lockstep.sv (every port compared every
cycle, plus the victim slot in every EVICT cycle); it is then reported as
"KILLED by lockstep" or "SURVIVED". The testbench verdict is always shown.

    python3 tools/mutate_rtl.py [--out results/P1/mutation.txt] [--depths 16 64 256] [--lockstep]
Exit status is non-zero if the unmutated RTL fails or any non-equivalent
mutant survives.
"""
import argparse, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
RTL = ROOT / "rtl/v2/lfu_cache_controller.v"
TB = ROOT / "rtl/v2/tb_lfu_cache.sv"
LOCKSTEP_TB = ROOT / "synthesis/p5b/tb_lockstep.sv"
MODES = (0, 1)

# name -> (description, old text, new text, modes where the mutant is equivalent
#          [, depths where it is equivalent in every mode])
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
    # P5b: Stage B reduction tree
    "tree_tie_right": (
        "tree node takes the right child on ties (victim order differs from the serial loop)",
        "wire take_r = rv < lv;", "wire take_r = rv <= lv;", ()),
    "tree_never_right": (
        "tree node always keeps the left child",
        "wire take_r = rv < lv;", "wire take_r = 1'b0;", ()),
    "tree_value_left": (
        "tree node forwards the left value even when it takes the right index",
        "assign tree_val[g*EW +: EW] = take_r ? rv : lv;", "assign tree_val[g*EW +: EW] = lv;", ()),
    "tree_index_left": (
        "tree node forwards the left index even when it takes the right value",
        "assign tree_idx[g*IDX_WIDTH +: IDX_WIDTH] = take_r ? tree_idx[(2*g+2)*IDX_WIDTH +: IDX_WIDTH]",
        "assign tree_idx[g*IDX_WIDTH +: IDX_WIDTH] = take_r ? tree_idx[(2*g+1)*IDX_WIDTH +: IDX_WIDTH]", ()),
    # Equivalent in every mode: Stage B is only used in EVICT, where an invalid slot is one
    # never filled since reset, whose counter reset cleared to 0, so eff(1, 0) = 1 is still
    # below every valid line's eff (count >= 1, eff >= 2). Kept to document that.
    "tree_leaf_ignores_valid": (
        "tree leaf treats every slot as valid (equivalent: invalid slots always have count 0 in EVICT)",
        "assign tree_val[(GROUPS-1+g)*EW +: EW] = eff(valid_bits[stageA_min[g]],",
        "assign tree_val[(GROUPS-1+g)*EW +: EW] = eff(1'b1,", (0, 1)),
    "tree_leaf_wrong_index": (
        "tree leaf carries the mirrored group's index with this group's value",
        "assign tree_idx[(GROUPS-1+g)*IDX_WIDTH +: IDX_WIDTH] = stageA_min[g];",
        "assign tree_idx[(GROUPS-1+g)*IDX_WIDTH +: IDX_WIDTH] = stageA_min[GROUPS-1-g];", ()),
    # P5b: per-group address copies
    "addr_copy_never_loaded": (
        "per-group address copies are never loaded (stay at reset value)",
        "    else if (state == IDLE && req_valid)\n        for (ag",
        "    else if (1'b0)\n        for (ag", ()),
    "addr_copy_last_group_stale": (
        "the last group's address copy is never loaded",
        "for (ag = 0; ag < GROUPS; ag = ag + 1) req_addr_grp[ag] <= req_addr;",
        "for (ag = 0; ag < GROUPS - 1; ag = ag + 1) req_addr_grp[ag] <= req_addr;", ()),
    "addr_copy_one_cycle_late": (
        "address copies load req_addr_reg (the previous request) instead of req_addr",
        "for (ag = 0; ag < GROUPS; ag = ag + 1) req_addr_grp[ag] <= req_addr;",
        "for (ag = 0; ag < GROUPS; ag = ag + 1) req_addr_grp[ag] <= req_addr_reg;", ()),
    # P5c: Stage A reduction tree (one per group). At depth 16, GSIZE = 1: the tree is a single
    # leaf with no nodes, so these mutants change no generated logic there (equivalent).
    "a_tree_tie_right": (
        "Stage A node takes the right child on ties (slot order differs from the serial loop)",
        "wire a_take_r = a_rv < a_lv;", "wire a_take_r = a_rv <= a_lv;", (), (16,)),
    "a_tree_never_right": (
        "Stage A node always keeps the left child",
        "wire a_take_r = a_rv < a_lv;", "wire a_take_r = 1'b0;", (), (16,)),
    "a_tree_value_left": (
        "Stage A node forwards the left value even when it takes the right index",
        "assign a_val[s*EW +: EW] = a_take_r ? a_rv : a_lv;", "assign a_val[s*EW +: EW] = a_lv;", (), (16,)),
    "a_tree_index_left": (
        "Stage A node forwards the left index even when it takes the right value",
        "assign a_idx[s*IDX_WIDTH +: IDX_WIDTH] = a_take_r ? a_idx[(2*s+2)*IDX_WIDTH +: IDX_WIDTH]",
        "assign a_idx[s*IDX_WIDTH +: IDX_WIDTH] = a_take_r ? a_idx[(2*s+1)*IDX_WIDTH +: IDX_WIDTH]", (), (16,)),
    "a_leaf_wrong_index": (
        "Stage A leaf carries the mirrored slot's index with this slot's value",
        "assign a_idx[(GSIZE-1+s)*IDX_WIDTH +: IDX_WIDTH] = g*GSIZE + s;",
        "assign a_idx[(GSIZE-1+s)*IDX_WIDTH +: IDX_WIDTH] = g*GSIZE + (GSIZE-1-s);", (), (16,)),
    "a_root_is_first_leaf": (
        "Stage A registers the group's first slot instead of the tree root",
        "assign stageA_comb[g*IDX_WIDTH +: IDX_WIDTH] = a_idx[IDX_WIDTH-1:0];",
        "assign stageA_comb[g*IDX_WIDTH +: IDX_WIDTH] = a_idx[(GSIZE-1)*IDX_WIDTH +: IDX_WIDTH];", (), (16,)),
}


def simulate(rtl_path, mode, work, depth=256):
    exe = work / f"sim_m{mode}"
    c = subprocess.run(["iverilog", "-g2012", f"-Ptb_lfu_cache.COUNTER_MODE={mode}",
                        f"-Ptb_lfu_cache.CACHE_DEPTH={depth}",
                        "-o", str(exe), str(rtl_path), str(TB)],
                       capture_output=True, text=True)
    if c.returncode != 0:
        return False, "compile error: " + c.stderr.strip().splitlines()[-1]
    r = subprocess.run(["vvp", "-n", str(exe)], capture_output=True, text=True,
                       cwd=work, timeout=600)
    out = r.stdout
    fails = [l.strip() for l in out.splitlines() if "FAIL" in l]
    return "ALL TESTS PASSED" in out, "; ".join(fails[:3]) or "(no FAIL lines)"


def lockstep(rtl_path, mode, work, depth):
    base = work / "base.v"
    if not base.exists():
        src = subprocess.run(["git", "-C", str(ROOT), "show", "rtl-v2-baseline:rtl/v2/lfu_cache_controller.v"],
                             capture_output=True, text=True, check=True).stdout
        base.write_text(src.replace("module lfu_cache_controller ", "module lfu_cache_controller_base ", 1))
    exe = work / "ls"
    c = subprocess.run(["iverilog", "-g2012", f"-Ptb_lockstep.COUNTER_MODE={mode}",
                        f"-Ptb_lockstep.CACHE_DEPTH={depth}", "-o", str(exe),
                        str(base), str(rtl_path), str(LOCKSTEP_TB)], capture_output=True, text=True)
    if c.returncode != 0:
        return False, "lockstep compile error"
    out = subprocess.run(["vvp", "-n", str(exe)], capture_output=True, text=True, cwd=work, timeout=1200).stdout
    summ = [l for l in out.splitlines() if l.startswith("lockstep ")]
    return "LOCKSTEP PASSED" in out, (summ[0] if summ else "(no summary)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results/P1/mutation.txt"))
    ap.add_argument("--depths", nargs="+", type=int, default=[256])
    ap.add_argument("--lockstep", action="store_true")
    args = ap.parse_args()
    src = RTL.read_text()
    lines, bad = [], False
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        for d in args.depths:
            for m in MODES:
                ok, info = simulate(RTL, m, work, d)
                lines.append(f"baseline depth={d} mode={m}: {'PASS' if ok else 'FAIL ' + info}")
                bad |= not ok
        for name, (desc, old, new, equiv, *eq_depths) in MUTANTS.items():
            n = src.count(old)
            if n != 1:
                lines.append(f"{name}: target text found {n} times, mutant not applied")
                bad = True
                continue
            mpath = work / f"{name}.v"
            mpath.write_text(src.replace(old, new))
            for d in args.depths:
                for m in MODES:
                    passed, info = simulate(mpath, m, work, d)
                    if m in equiv or d in (eq_depths[0] if eq_depths else ()):
                        verdict = "survived (equivalent, expected)" if passed else "KILLED (equivalent cell)"
                    elif not passed:
                        verdict = "KILLED by testbench"
                    elif args.lockstep:
                        ls_ok, ls_info = lockstep(mpath, m, work, d)
                        verdict = ("testbench passed; SURVIVED lockstep" if ls_ok
                                   else "testbench passed; KILLED by lockstep")
                        info = ls_info
                        bad |= ls_ok
                    else:
                        verdict = "SURVIVED (testbench gap)"
                        bad = True
                    lines.append(f"{name} depth={d} mode={m}: {verdict} | {desc}" +
                                 ("" if passed and not args.lockstep else f" | {info}"))
                    print(lines[-1], flush=True)
    lines.append("RESULT: " + ("FAIL" if bad else "OK (all non-equivalent mutants killed)"))
    text = "\n".join(lines) + "\n"
    pathlib.Path(args.out).write_text(text)
    print(text, end="")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
