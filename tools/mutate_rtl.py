#!/usr/bin/env python3
"""Mutation check for rtl/v2 (or rtl/v3 with --v3): the testbench must FAIL on broken RTL copies.

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

    python3 tools/mutate_rtl.py [--out results/P1/mutation.txt] [--depths 16 64 256] [--lockstep] [--v3]

--v3 (P11): mutate rtl/v3/lfu_cache_controller.v under rtl/v3/tb_lfu_cache.sv (TESTS 1-8). The v2 mutants are
applied with the v3 key width (`*EW +: EW]` -> `*KW +: KW]`; the tree leaf value is `{eff(...), wrap}`), and the
V3_MUTANTS below (Rotate-victim, COUNTER_MODE 0 only, so equivalent in mode 1) are added. --lockstep compares
against rtl-v2-baseline; with --v3 it is used in mode 1 only (v3 mode 1 is the v2 logic; v3 mode 0 has a different
tie rule, so a mode-0 survivor is reported as SURVIVED).
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
    # P5d: hit_idx priority tree.
    # Equivalent in every mode: the right child wins a tie only when both subtrees match,
    # i.e. two valid slots hold the requested tag, which the RTL never allows (invariant in
    # results/P5d/SUMMARY.md; the lockstep counts 0 multi-match cycles). Kept to document that.
    "hit_tree_prefer_right": (
        "hit tree takes the right child whenever it matches (equivalent: at most one slot matches)",
        "wire h_take_r = !h_any[2*g+1] && h_any[2*g+2];", "wire h_take_r = h_any[2*g+2];", (0, 1)),
    "hit_tree_never_right": (
        "hit tree always keeps the left child",
        "wire h_take_r = !h_any[2*g+1] && h_any[2*g+2];", "wire h_take_r = 1'b0;", ()),
    "hit_tree_any_left_only": (
        "hit tree node ignores matches in its right subtree",
        "assign h_any[g] = h_any[2*g+1] | h_any[2*g+2];", "assign h_any[g] = h_any[2*g+1];", ()),
    "hit_tree_index_left": (
        "hit tree node forwards the left index even when it takes the right child",
        "assign h_idx[g] = h_take_r ? h_idx[2*g+2] : h_idx[2*g+1];",
        "assign h_idx[g] = h_idx[2*g+1];", ()),
    "hit_leaf_wrong_index": (
        "hit tree leaf carries the mirrored slot's index",
        "assign h_idx[CACHE_DEPTH-1+g] = g;",
        "assign h_idx[CACHE_DEPTH-1+g] = CACHE_DEPTH-1-g;", ()),
}


# P11: rtl/v3 Rotate-victim mutants. Mode 1 never uses ptr or the wrap bit (ROTATE = 0), so all are
# equivalent there. At depth 16, GSIZE = 1: Stage A has no nodes, so its wrap bit changes no logic.
V3_MUTANTS = {
    "rot_disabled": (
        "Rotate-victim off: mode 0 falls back to the v2 lowest-index rule",
        "localparam ROTATE = (COUNTER_MODE == 0);", "localparam ROTATE = 0;", (1,)),
    "rot_ptr_no_increment": (
        "ptr loads the victim itself instead of victim + 1",
        "ptr <= victim_reg + 1'b1;", "ptr <= victim_reg;", (1,)),
    "rot_ptr_never_loaded": (
        "ptr is never loaded in FILL (stays 0: v2 rule with a wider key)",
        "if (ROTATE)\n                    ptr <= victim_reg + 1'b1;",
        "if (1'b0)\n                    ptr <= victim_reg + 1'b1;", (1,)),
    "rot_ptr_no_reset": (
        "ptr is not reset (X until the first FILL)",
        "        ptr        <= {IDX_WIDTH{1'b0}};\n", "", (1,)),
    "rot_stageA_no_wrap": (
        "Stage A leaves ignore the wrap bit",
        "ROTATE && (g*GSIZE + s < ptr)", "1'b0", (1,), (16,)),
    "rot_stageB_no_wrap": (
        "Stage B leaves ignore the wrap bit",
        "ROTATE && (stageA_min[g] < ptr)", "1'b0", (1,)),
    "rot_stageA_le": (
        "Stage A wrap = (slot <= ptr): the slot at ptr counts as wrapped",
        "(g*GSIZE + s < ptr)", "(g*GSIZE + s <= ptr)", (1,), (16,)),
    "rot_stageB_le": (
        "Stage B wrap = (slot <= ptr): the slot at ptr counts as wrapped",
        "(stageA_min[g] < ptr)", "(stageA_min[g] <= ptr)", (1,)),
    # Equivalent in every mode: mode 0 already loads ptr in FILL, and mode 1 never reads ptr (wrap is
    # ROTATE && ..., ROTATE = 0). Kept to document that.
    "rot_ptr_loaded_in_mode1": (
        "ptr also loads in mode 1 (equivalent: mode 1 never reads ptr)",
        "if (ROTATE)\n                    ptr <=", "if (1'b1)\n                    ptr <=", (0, 1)),
}


def v3_text(s):
    """A v2 mutant's text in rtl/v3 form: 8-bit key, tree leaf value {eff(...), wrap}."""
    return s.replace('*EW +: EW] = eff(', '*KW +: KW] = {eff(').replace('*EW +: EW]', '*KW +: KW]')


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
    ap.add_argument("--v3", action="store_true")
    args = ap.parse_args()
    global RTL, TB
    mutants = MUTANTS
    if args.v3:
        RTL, TB = ROOT / "rtl/v3/lfu_cache_controller.v", ROOT / "rtl/v3/tb_lfu_cache.sv"
        mutants = {k: (v[0], v3_text(v[1]), v3_text(v[2]), *v[3:]) for k, v in MUTANTS.items()}
        mutants.update(V3_MUTANTS)
    src = RTL.read_text()
    lines, bad = [], False
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        for d in args.depths:
            for m in MODES:
                ok, info = simulate(RTL, m, work, d)
                lines.append(f"baseline depth={d} mode={m}: {'PASS' if ok else 'FAIL ' + info}")
                bad |= not ok
        for name, (desc, old, new, equiv, *eq_depths) in mutants.items():
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
                    elif args.lockstep and not (args.v3 and m == 0):
                        ls_ok, ls_info = lockstep(mpath, m, work, d)
                        verdict = ("testbench passed; SURVIVED lockstep" if ls_ok
                                   else "testbench passed; KILLED by lockstep")
                        info = ls_info
                        bad |= ls_ok
                    else:
                        verdict = "SURVIVED (testbench gap" + ("; no lockstep reference for v3 mode 0)" if args.lockstep else ")")
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
