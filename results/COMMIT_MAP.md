# COMMIT_MAP: commit IDs before and after removing Claude attribution lines from commit messages

On 2026-10-26 every commit message in the local history had its `Co-Authored-By: Claude ...` line removed (53
commits; there were no `Claude-Session` lines) with `git filter-branch --msg-filter`. Nothing else changed: author,
committer, dates and trees are identical and every parent maps to the rewritten parent (checked commit by commit);
`git diff` between the old and new branch heads is empty. Because a commit ID covers its message and its parents,
every rewritten commit has a new ID. The one commit made on GitHub (40d20a7, GPG-signed by GitHub) was excluded from the
rewrite and keeps its ID and signature.

Local backups (not pushed): branch and tag `backup-before-rewrite` (old head 6a2ed63), tags
`backup-before-rewrite-rtl-v2-baseline` (1483717) and `backup-before-rewrite-rtl-v2-final` (baba9e5), and
`refs/original/refs/heads/{merge-origin-main,master}` written by filter-branch.

## Refs

| ref | old | new |
|---|---|---|
| branch merge-origin-main (pushed as main) | 6a2ed63 | 6c8b506 |
| branch master | 419af98 | c1065e2 |
| tag rtl-v2-baseline | 1483717 | 0d66a3a |
| tag rtl-v2-final | baba9e5 | 7705a7b |
| GitHub main before the force-push | e9c725e | (replaced) |

Files at both tags are identical before and after (`git diff` of old and new tag: empty).

## All commits (oldest first)

| old | new | subject |
|---|---|---|
| 6c0def5 | 379a5ce | P0: cluster setup check (partitions, scratch, quota, modules) |
| 08f7108 | 10cd602 | P1: COUNTER_MODE in rtl/v2, per-mode tests, mutation script |
| d4c3478 | 9f88492 | P3 prep: Count-Min W-TinyLFU, ARC, vector-capacity sweep, policy tests |
| f04cd65 | 4ffc77a | P3 prep: per-table results + Zipf fit, Belady, array job path, plots, timing |
| 2735138 | b239ad9 | P2: conda env on /scratch via --prefix, bootstrap built (job 412815) |
| 6a3f2cb | 1ebd69c | P2: download Criteo dac.tar.gz from figshare with MD5 check before extract |
| 80c2d53 | 22935f6 | P2: Criteo DAC downloaded and verified (jobs 412889, 412890) |
| bbbff08 | 2b2d674 | P3: driver matches submitted chain (10M dump 2 h, array %6, no --wait); job IDs 412923-412928 |
| a7bdb14 | d0f9ac8 | P3: replace /usr/bin/time (missing on node6, job 412923 exit 127) with tools/timev.py |
| a84d9a9 | b167b20 | P3: 2M and 10M Criteo trace-sim results, TABLES.md, SUMMARY.md (jobs 412934-412939) |
| 0269f44 | 0d58370 | P3: ANALYSIS.md (large tables, per-table vs shared cache, LRU vs LFU over all capacities) |
| 7e5ef3f | 5b31d08 | P3b prep: shared-cache simulator (one cache, all tables), tests, mutation 10/10, 200k synthetic t... |
| cc57240 | 9e8da2f | P3b: save each policy/capacity to parts/*.csv on completion; 2 h limit |
| c81407a | 35c1d7d | P3b: shared-cache results at 2M rows (job 413067), RESULTS.md |
| 881ea07 | 6a8633d | P3b: driver takes row count; 10M uses --mem=32G, 2 h (sized from 2M job 413067) |
| 64b2e7d | 8513ea7 | env: add python-dotenv to environment.yml (cluster env NOT updated yet) |
| 79f9adc | cc9e875 | P3b: 10M shared-cache results (job 413106) beside 2M in RESULTS.md |
| 913a794 | 7c2737b | P3b: SUMMARY.md updated with the 10M shared-cache run (job 413106) |
| 2720003 | 447abdd | P3b: SUMMARY.md under 40 lines |
| 5932e57 | 6f94bcc | P4 prep: profile_embedding.py (EmbeddingBag vs MLP, CUDA events), CPU tests, env/GPU job scripts,... |
| 23da462 | f238e6d | P4: GPU preflight (driver >= 525.60.13, torch CUDA available) before heavy work; env du to result... |
| d430aaf | 9fcc897 | P4: env 413583 and H100 413584 submitted; H200 rejected (max 4 CPUs per H200 GPU) |
| d88244d | c7e8091 | P4: GPU jobs use 4 CPUs (gpu_h200_8 limit is 4 per GPU; H100 matched) |
| 5ed35bb | d6a38ac | P4: resubmitted GPU jobs with -c 4: H100 413586 -> H200 413587 after env 413583 |
| 359ee58 | 08533d4 | P4: env job downloads from the PyTorch cu126 index only (PyPI read timeout, job 413583), then ins... |
| b1ef6aa | 18cf305 | P4: attempt 3 submitted: env 413620 -> H100 413621 -> H200 413622 |
| daf1601 | 04c34be | P4: results from H100 413621 and H200 413622, RESULTS.md and SUMMARY.md |
| ff9b002 | ed7da13 | P4: SUMMARY.md states MLP sizes, bag size and pooling mode with source line numbers |
| 14d58e5 | 2aa8f1a | P5: plan for NanGate45 + OpenSTA on rtl/v2 (nothing downloaded yet) |
| 939011a | b5d85b7 | P5: NanGate45 + OpenSTA on rtl/v2, depth 16/64/256 x COUNTER_MODE 0/1 x 1 GHz/500 MHz |
| b87baf0 | 99cdde6 | P5: critical-path analysis (depth 16 and 256, mode 0) and rtl/v2 header states the NanGate45 result |
| 1483717 | 0d66a3a (tag rtl-v2-baseline) | P5: CRITICAL_PATH.md Stage B ends at line 146 |
| 0140ad1 | 4debe84 | P5b: Stage-B reduction tree + per-group address copies; before/after on NanGate45 (not TSMC, pre-... |
| 2a9f4ae | fac3366 | P5b: SUMMARY.md under 40 lines |
| 3ebb34f | 73016e0 | P5c: Stage-A reduction tree; tree only vs tree + address copies (copies kept); NanGate45, not TSM... |
| baba9e5 | 7705a7b (tag rtl-v2-final) | P5d: hit_idx priority tree (final RTL, tag rtl-v2-final); noise floor; NanGate45, not TSMC, pre-l... |
| 37c353c | b69a931 | P5e: measurement flow only (no RTL change): why -D did not bind, timing-driven ABC flow, noise fl... |
| d7a2b54 | 4188580 | P5f: gate-level sim setup (Yosys-generated cell models checked, coverage), 8 local unit tests, cl... |
| 18b6aeb | 42a8201 | P5f: depth-16 Yosys equivalence RTL vs netlist, local, one at a time: 4/4 runs, 2977/2977 $equiv ... |
| 215d493 | 02518be | P5f: cluster results and SUMMARY: 12/12 lockstep 200,000 cycles 0 mismatches 0 X, 16/16 unit test... |
| b80f0ce | c5511a5 | P5f: SUMMARY under 40 lines; slurm .out files were empty (gitignored *.out) |
| 10ce5a2 | 1575c09 | P7: TABLES.md from committed files (tools/make_tables.py), CLAIMS.md (36 earlier claims checked, ... |
| 4cee536 | e615881 | P7: TABLES.md adds dataset size, P4 launch-bound flags and skip counts, slew/cap violators, P5d->... |
| 7e124a7 | 5d51bad | P7: paper/v2 rewritten from scratch (IEEEtran conference, 6 pages) from CLAIMS.md and TABLES.md; ... |
| 2af6b00 | afb8a0f | P7: counter-saturation check of the P5f lockstep stimulus (RTL only, local, Icarus 12): all 6 dep... |
| bbe9e23 | b26a522 | P7: paper/v2 revision: large-table caveat, address copies within noise, P4 rows/pattern sensitivi... |
| 369e572 | eef1260 | P7: paper/v2 README: underfull vbox messages are listed, not denied |
| 2b194ae | c83ade6 | P7: paper/v2 author line: Adarsh (name placeholder removed) |
| b4e354b | aed35b8 | P7: paper/v2 authors in separate IEEE author blocks (Adarsh; Pravin Mane, co-author) |
| 419af98 | c1065e2 | README: apply results/P7/README.diff; current paper is paper/v2/main.pdf, old manuscript in paper... |
| 40d20a7 | 40d20a7 (unchanged) | Initialize README with project details and findings |
| bcaa7a6 | 7389788 | Merge origin/main (unrelated history: one commit adding readme.md) into local history |
| 4aef0a9 | da9adb6 | Remove the old remote readme.md; README.md is the project README (old claims: see results/P7/CLAI... |
| e9c725e | d1324d1 | PUSH_CHECKLIST.md: pre-push checks, remote merge, tags and unpushed commits (nothing pushed) |
| 6a2ed63 | 6c8b506 | CLAUDE.md: rule 6, no Claude attribution in commit messages or PR descriptions |

## Files whose commit IDs were updated (ID-only edits, checked: nothing else changed)

- `paper/v2/main.tex` (9)
- `results/P3/jobs.txt` (1)
- `results/P4/jobs.txt` (2)
- `results/P5b/SUMMARY.md` (1)
- `results/P5c/SUMMARY.md` (1)
- `results/P5d/COMPARE.md` (2)
- `results/P5d/SUMMARY.md` (3)
- `results/P5d/attempt1_packed_vectors/COMPARE.md` (2)
- `results/P5d/attempt1_packed_vectors/run_checks.txt` (2)
- `results/P5d/run_checks.txt` (2)
- `results/P5f_gls/SUMMARY.md` (2)
- `results/P5f_gls/netlists/FLOW_VERSION.txt` (2)
- `results/P7/CLAIMS.md` (2)
- `results/P7/SUMMARY.md` (1)
- `results/P7/counter_sat/d16_m0.txt` (1)
- `results/P7/counter_sat/d16_m1.txt` (1)
- `results/P7/counter_sat/d256_m0.txt` (1)
- `results/P7/counter_sat/d256_m1.txt` (1)
- `results/P7/counter_sat/d64_m0.txt` (1)
- `results/P7/counter_sat/d64_m1.txt` (1)
- `results/PUSH_CHECKLIST.md` (20)
- `synthesis/p5c/run_p5c.sh` (4)
- `synthesis/p5d/run_p5d.sh` (7)
- `tools/p5d_compare.py` (1)
- `results/P7/TABLES.md`: regenerated by `tools/make_tables.py` (it prints the commit that last changed each source).

## Files that still cite old IDs, on purpose

- `rtl/v2/lfu_cache_controller.v` (header comment cites 2a9f4ae and 3ebb34f): left unchanged so that `rtl/v2` stays
  byte-identical to tag `rtl-v2-final`, which `tools/make_tables.py` checks and the synthesized netlists come from.
- The RTL variant copies under `results/P5d/noise/rtl/` and `results/P5d/attempt1_packed_vectors/` (cite 2a9f4ae):
  left unchanged because they are the exact files that were synthesized for the noise-floor runs.
- Use the table above to translate these IDs: 2a9f4ae -> fac3366, 3ebb34f -> 73016e0.

Commit messages may mention earlier commit IDs in their text; message bodies were not edited apart from removing
the attribution line, so those mentions are old IDs (translate them with the table).
