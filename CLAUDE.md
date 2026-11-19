# Project: cache-policy study for DLRM embedding lookups (BITS Pilani Goa, SOP)
Owner: Adarsh. Mentor: Prof. Pravin Mane. Read PLAN.md for tasks. Work ONE phase at a time.

Layout: rtl/v2 (current), rtl/v1_* (old, buggy), trace_sim/, profiling/, gem5/, synthesis/, results/<phase>/, tools/, bench/.

Cluster: `ssh rahulkmr@hpc.bits-hyderabad.ac.in` alias. Everything heavy goes through sbatch. Never `srun --pty`.
Partitions: `compute`, `gpu_h100_4`. Find the H200 partition with `sinfo`; do not guess.
Work dir: /scratch/rahulkmr/Adarsh/ (may be purged: git + rsync results back after each phase).
No password/OTP prompts: if one appears, stop and tell the user.

Hard rules
1. No number in README/paper/resume/summary without a results file path.
2. Never invent, estimate or round up a number.
3. Label honestly: gem5 = CPU + DDR4 (not a GPU); Yosys without liberty = gate counts only; open PDK != TSMC.
4. Ask before: deleting, system-wide installs, git push, >1 GPU or >2h GPU, running unknown downloaded scripts.
5. Secrets (Kaggle token, ssh keys) are never read, printed or committed.
6. Never add Co-Authored-By or Claude-Session lines, or any Claude attribution, to commit messages or PR descriptions.

Lab server C2 (licensed commercial library; P12/P13). These rules have the same weight as the hard rules.
- Library, LEF, docs and tech files stay on C2: never copy them off, read or print their contents, or open their PDFs.
  Only file names and the tool reports of our own runs may be looked at.
- The repo is public. No library name, cell name, library file name or path, C2 host address or C2 user name in any
  tracked file. Library paths live only in local.env on C2 (gitignored as cadence/local.env).
- Name the technology only as "a commercial 28nm FD-SOI standard-cell library, typical corner"; area in "library units".
  Exception, paper only (approved by Prof. Mane, 2026-11-19): the paper may name the vendor and node, as "an
  STMicroelectronics 28nm FD-SOI standard-cell library (accessed through CMP)" at first mention, "the 28nm FD-SOI
  library" elsewhere, and thank CMP and STMicroelectronics in the acknowledgements. Nothing else from the kit: no cell
  names, library file names or paths, metal stack or layer details, C2 host or user names.
- Raw reports, logs, netlists and SDF stay off the repo (C2 and ~/c2_results/). Only aggregate tables
  (results/P12|P13/TABLES.md from tools/c2_collect.py, tools/p13_power_table.py) and SUMMARY.md are committed;
  publishing these aggregates was approved by Prof. Mane.
- Before every commit run `python3 -I tools/check_no_lib_leak.py` (it reads the identifying patterns from the
  gitignored tools/leak_patterns.local, which must never be committed); commit only if it prints PASS.
- Connect only through the user's master socket (`ssh -S ~/.ssh/c2.sock ...`); never ask for or read a password.
  Jobs started over it die when the socket closes (logind kills the session); at most 4 tool jobs at a time.
- Long C2 jobs (Genus, Xcelium, Innovus): linger is on, so start them as `systemd-run --user --unit=<unique-name> csh -fc 'cd <run dir>; <cmd> >& <run dir>/job.log'`; they survive logout (tested: nohup died, the unit survived). Check with `systemctl --user status <unit>`.

Keep usage low
- Do not poll. Use `sbatch --dependency=afterok` chains.
- One driver script per phase, writing results/<phase>/SUMMARY.md (<40 lines).
- Use `tail -n 40` / `grep`, not `cat`, on logs.
- Each phase ends with SUMMARY.md + git commit + stop.

Known corrections to earlier claims
- Old 83.74% came from annotated ranges; EmbeddingBag kernel share is 71.8% and the run was launch-bound.
- The "160,000x" miss-latency claim is wrong (picoseconds read as cycles).
- No TSMC data exists. LFU.v FSM takes 2 cycles per state (bug).
- Current RTL has no per-address history; the counter scheme is pending Prof. Mane.
