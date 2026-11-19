# Project status, 2026-11-14 (branch rtl-v3)
Every number is copied from the results file named on its line.

## Findings P9-P13
- P9 (results/P9/SUMMARY.md): the RTL-vs-simulator hit gap is the tie-break; the RTL-exact model matched 24/24 RTL runs, 0 mismatches in 2,560,448 requests; RTL-exact m0 loses to LRU at every size (2M rows, 256 entries: 39.3685% vs 41.4010%).
- P10 (results/P10/SUMMARY.md): Rotate-victim tie-break in rtl/v3 (mode 0 only); RTL vs simulator lockstep 0 mismatches in all 12 slice runs; d256 row0 mode-0 hits 103,382 (v3) vs 81,221 (v2 rule).
- P11 (results/P11/SUMMARY.md): v3 m0 equals LFU-reset on the full traces (+4,921,393 hits over v2 at 64 entries, 2M rows); NanGate45 Fmax changes within the 6.44% same-logic flow variation; v2 m1 = v3 m1 proven equivalent at depth 16 and 64; gate-level lockstep 24/24 pass, 0 mismatching cycles.
- P12 (results/P12/SUMMARY.md): Genus, a commercial 28nm FD-SOI standard-cell library, typical corner, pre-layout: depth 256 meets 0.8 ns and fails 0.65 ns for all 4 version/mode pairs (Fmax of failing runs 1251.6-1278.8 MHz); merge-off keeps the 320 address copies and raises 0.65 ns Fmax by +4.06% (v2) / +4.60% (v3).
- P13 (results/P13/SUMMARY.md): merge-off d256 netlists at 0.8 ns, zero-delay and SDF (path delays only) lockstep, 0 mismatches over 200,000 requests per slice; power 2.27986e-01 to 2.29615e-01 W; energy per request 743.94 / 737.64 pJ (v2) and 676.39 / 682.79 pJ (v3), -9.08% / -7.44% for v3 (fewer cycles); driver-net activity coverage 42%.

## Git (local refs only; the remote was not queried)
- All P9-P13 work is committed on rtl-v3. origin/rtl-v3 (remote-tracking ref) = d98b10e, the commit before this one; it was not pushed from this session. This STATUS.md commit is not pushed.
- origin/main = 7dd5f5c (2026-10-28); rtl-v3 is 19 commits ahead of it before this commit (all of P12/P13) and not merged.
- Tag rtl-v2-final = 7705a7b, contained in origin/main; whether the tag itself is on the remote is not known locally.
- Off the repo: raw C2 reports and SUMMARY_P12_P13.md in ~/c2_results/; the C2 work dir on C2; tools/leak_patterns.local (gitignored).

## Open items
- History leak check: tools/check_no_lib_leak.py --history PASS (145 commits, patches and messages); 559 binary patches are not scanned (a raw-blob scan is not written). Run both checks again before any push.
- Push: this commit on rtl-v3, and the tag rtl-v2-final; only with Adarsh's approval (CLAUDE.md rule 4).
- Paper rewrite with P9-P13: not started.
- P14 GPU profiling prep: not started.
- Innovus after PnR notes: not started (P12/P13 are pre-layout; the C2 kit has LEF and parasitic-extraction files by name).

## C2 rules that matter (full text in CLAUDE.md)
- Library, LEF, docs and tech files never leave C2 and are never read or printed; only file names and our own tool reports.
- No library, cell, host or user names in any tracked file; name the technology only as "a commercial 28nm FD-SOI standard-cell library, typical corner"; area in library units.
- Raw reports stay off the repo; only TABLES.md / SUMMARY.md aggregates are committed (approved by Prof. Mane).
- Before a commit: python3 -I tools/check_no_lib_leak.py must print PASS; before a push also --history.
- Connect only through the master socket (ssh -S ~/.ssh/c2.sock); jobs started over it die when it closes; at most 4 tool jobs; no polling.
- A run is complete only if its 5 reports are non-empty, its log reached the script's exit and its stdout ends with "Normal exit.".
