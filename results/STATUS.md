# Project status, 2026-11-21 (branches rtl-v3 and main)

The per-phase findings are in the phase index of `README.md` and in each `results/<phase>/SUMMARY.md`; numbers are
not repeated here. This file replaces the hand-off of 2026-11-14 (in git history), whose open items were stale.

## State
- Phases P0 to P16 are done and committed (P6, an optional gem5 sweep, was not run). The paper is `paper/v2`
  (draft; tag `paper-draft-1`), the semester report `docs/sem_report`, the next-semester plan `docs/plan_next_sem`.
- RTL: v2 = tag `rtl-v2-final`; v3 (Rotate-victim) = tag `rtl-v3-final`, the commit that last changed `rtl/v3`
  (its sha256 is the one recorded in `results/P11/equiv/`).
- `main` is fast-forwarded to `rtl-v3` locally. Nothing in this update has been pushed; push only with Adarsh's approval.

## Checks before any push
- `python3 -I tools/check_no_lib_leak.py` and `python3 -I tools/check_no_lib_leak.py --history` must print PASS.
- `python3 -I tools/paper_numbers_check.py --readme README.md`, `make` in `paper/v2` (number check, then PDF).

## Open items (detail in `docs/plan_next_sem`)
- Multi-corner sign-off: per-corner I/O clock latency or multi-corner optimisation (`results/P16/SUMMARY.md`).
- SDF timing checks are not annotated in any gate-level run; H200 performance counters are blocked.
- No LICENSE file has been chosen yet.
