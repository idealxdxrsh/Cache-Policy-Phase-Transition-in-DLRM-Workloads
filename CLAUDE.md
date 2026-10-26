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
