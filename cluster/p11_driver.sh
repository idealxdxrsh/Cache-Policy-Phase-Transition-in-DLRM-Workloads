#!/bin/bash
# P11 driver (run locally). Two independent parts; heavy simulation runs through sbatch (CPU only, no GPU).
#   partA    sync the repo and the 256-entry reference files, submit the shared-cache jobs: 2M, then 10M afterok
#            (cluster/jobs/p11_shared.sbatch; LRU, LFU-reset (oldest), RTL-exact m0, Rotate-victim m0; 16/64/256)
#   synth    LOCAL: synthesis of rtl/v3 with the P5e flow unchanged (synthesis/p5/run_p5.sh with
#            synthesis/p5e/synth_td.ys.in + abc_td.script.in, ABC_BUDGET_PS=141.5, NanGate45 liberty, wire load
#            5K_hvratio_1_1, synthesis/p5/abc.constr, synthesis/p5/sta.tcl), depths 16/64/256 x modes 0/1 x
#            1000/500 MHz -> results/P11/synth/. Local because Yosys 0.33, OpenSTA 3.1.0 and the liberty (used
#            locally only, results/P5/SOURCES.md) are local; the cluster has Yosys 0.62 and no OpenSTA.
#   report   tools/p11_synth_report.py -> results/P11/SYNTH.md (v3 vs rtl-v2-final, results/P5e/new)
#   mutate   LOCAL: tools/mutate_rtl.py --v3 --lockstep (mode 1 only) at depths 16/64/256 -> results/P11/mutation.txt
#   gls      stage the 12 v3 netlists, P5f's cell models, rtl/v3, the testbench and the two slices on the cluster,
#            check their sha256 there, submit the lockstep arrays: depth 16, then 64 afterok, then 256 afterok
#   wait     one sbatch --wait job that starts after every P11 job has ended (afterany); blocks, no polling
#   fetch    copy the cluster results back to results/P11/cluster/
# Each submit step appends the job ids to results/P11/jobs.txt.
set -euo pipefail
H=rahulkmr@hpc.bits-hyderabad.ac.in
W=/scratch/rahulkmr/Adarsh
G=$W/p11gls
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
R=$ROOT/results/P11
LIB=${LIB:-$HOME/eda/pdk/nangate45/NangateOpenCellLibrary_typical.lib}
RUNS=$(for d in 256 64 16; do for m in 0 1; do for f in 1000 500; do echo "d${d}_m${m}_${f}MHz"; done; done; done)
SSH="ssh -o BatchMode=yes $H"
mkdir -p "$R"

case ${1:-} in
partA)
    $SSH "mkdir -p $W/repo $W/logs $W/results/P11"
    rsync -a --delete --exclude .git --exclude .venv --exclude results "$ROOT/" "$H:$W/repo/"
    for n in 2000000 10000000; do
        $SSH "mkdir -p $W/repo/p11_ref/rows_$n"
        rsync -a "$ROOT/results/P3b/rows_$n/shared_cache_results.json" "$H:$W/repo/p11_ref/rows_$n/p3b.json"
        rsync -a "$ROOT/results/P9/cluster/rows_${n}_setA/shared_cache_results.json" "$H:$W/repo/p11_ref/rows_$n/p9A.json"
        rsync -a "$ROOT/results/P9/cluster/rows_${n}_setB/shared_cache_results.json" "$H:$W/repo/p11_ref/rows_$n/p9B.json"
    done
    # limits as P9 (results/P9/jobs.txt): P9 set A/B took 3:39-5:31 (2M) and 17:55-24:36 (10M) for 24 tasks at
    # 256-100,000 entries; P11 has 12 tasks at 16-256 entries
    $SSH bash -l -s <<REMOTE | tee -a "$R/jobs.txt"
set -e
cd $W/repo/cluster/jobs
j2=\$(sbatch --parsable --mem=16G -t 01:00:00 --export=ALL,N_ROWS=2000000 p11_shared.sbatch)
j10=\$(sbatch --parsable --mem=32G -t 02:00:00 --dependency=afterok:\$j2 --kill-on-invalid-dep=yes --export=ALL,N_ROWS=10000000 p11_shared.sbatch)
echo "partA submitted \$(date -Is): rows=2000000 job=\$j2 (16G 1:00); rows=10000000 job=\$j10 (32G 2:00, afterok:\$j2)"
REMOTE
    ;;
synth)
    export YS_IN=$ROOT/synthesis/p5e/synth_td.ys.in ABC_IN=$ROOT/synthesis/p5e/abc_td.script.in ABC_BUDGET_PS=141.5
    export ROOT LIB
    git -C "$ROOT" diff --quiet b69a931 -- synthesis/p5 synthesis/p5e || { echo "P5e flow files differ from b69a931"; exit 1; }
    for d in 256 64 16; do for m in 0 1; do for f in 1000 500; do echo "$d $m $f"; done; done; done \
        | xargs -P "${JOBS:-8}" -L 1 bash -c 'OUTDIR=results/P11/synth RTL=$ROOT/rtl/v3/lfu_cache_controller.v \
            MODES=$1 FREQS=$2 bash "$ROOT/synthesis/p5/run_p5.sh" $0' > "$R/run_synth.txt" 2>&1
    gzip -f "$R"/synth/d*/yosys.log
    (cd "$R/synth" && sha256sum d*/netlist.v > netlists.sha256)
    sort -o "$R/run_synth.txt" "$R/run_synth.txt" ;;
report)
    python3 -I "$ROOT/tools/p11_synth_report.py" "$LIB" > "$R/SYNTH.md" ;;
mutate)
    python3 -I "$ROOT/tools/mutate_rtl.py" --v3 --lockstep --depths 16 64 256 --out "$R/mutation.txt" > "$R/mutation_log.txt" 2>&1 ;;
gls)
    $SSH "mkdir -p $G/netlists $G/models $G/rtl $G/tb $G/tools $G/stim $G/slurm $G/results"
    for r in $RUNS; do $SSH "mkdir -p $G/netlists/$r"; rsync -a "$R/synth/$r/netlist.v" "$H:$G/netlists/$r/"; done
    rsync -a "$R/synth/netlists.sha256" "$H:$G/netlists/"
    rsync -a "$ROOT/results/P5f_gls/models/nangate45_cells_yosys.v" "$H:$G/models/"
    rsync -a "$ROOT/rtl/v3/lfu_cache_controller.v" "$H:$G/rtl/"
    rsync -a "$ROOT/synthesis/p11/tb_gls_slice.sv" "$H:$G/tb/"
    rsync -a "$ROOT/tools/p5f_wrap.py" "$ROOT/tools/timev.py" "$H:$G/tools/"
    rsync -a "$ROOT/cluster/jobs/p11_gls.sbatch" "$H:$G/"
    rsync -a "$ROOT/results/P8/stimulus/row0.hex" "$ROOT/results/P8/stimulus/row1M.hex" "$H:$G/stim/"
    # sha256 of every staged source, under its path inside $G (checked there before submission)
    for pair in models/nangate45_cells_yosys.v=results/P5f_gls/models/nangate45_cells_yosys.v \
                rtl/lfu_cache_controller.v=rtl/v3/lfu_cache_controller.v tb/tb_gls_slice.sv=synthesis/p11/tb_gls_slice.sv \
                tools/p5f_wrap.py=tools/p5f_wrap.py tools/timev.py=tools/timev.py p11_gls.sbatch=cluster/jobs/p11_gls.sbatch \
                stim/row0.hex=results/P8/stimulus/row0.hex stim/row1M.hex=results/P8/stimulus/row1M.hex; do
        echo "$(sha256sum "$ROOT/${pair#*=}" | cut -c1-64)  ${pair%%=*}"
    done > "$R/gls_sources.sha256"
    rsync -a "$R/gls_sources.sha256" "$H:$G/"
    for d in 16 64 256; do
        for r in $RUNS; do case $r in d${d}_*) for s in row0 row1M; do echo "$r $s"; done ;; esac; done > "$R/gls_tasks_d$d.txt"
    done
    rsync -a "$R"/gls_tasks_d*.txt "$H:$G/"
    # limits from P5f (results/P5f_gls/SUMMARY.md, Icarus 11 on this cluster, 200,000 cycles of RTL + netlist):
    # vvp 8:17 (d16), 25:22 (d64), 1:40:57 (d256), d256 compile up to 13:09, peak RSS <= 2.15 GB; P11 slices run
    # 995,124-1,081,895 (d16), 817,581-890,436 (d64), 738,077-797,684 (d256) cycles (results/P10/rtl/*.txt), so
    # projected <= 0:46, 1:53, 6:56 per run (a projection, not a measurement); limits 2:00, 4:00, 12:00.
    $SSH bash -l -s <<REMOTE | tee -a "$R/jobs.txt"
set -e
cd $G
(cd netlists && sha256sum -c --quiet netlists.sha256) && echo "netlists sha256 OK"
sha256sum -c --quiet gls_sources.sha256 && echo "sources sha256 OK"
a=\$(sbatch --parsable -J p11gls16 --mem=8G -t 02:00:00 --array=1-8 p11_gls.sbatch $G/gls_tasks_d16.txt)
b=\$(sbatch --parsable -J p11gls64 --mem=8G -t 04:00:00 --array=1-8 --dependency=afterok:\$a --kill-on-invalid-dep=yes p11_gls.sbatch $G/gls_tasks_d64.txt)
c=\$(sbatch --parsable -J p11gls256 --mem=8G -t 12:00:00 --array=1-8 --dependency=afterok:\$b --kill-on-invalid-dep=yes p11_gls.sbatch $G/gls_tasks_d256.txt)
echo "gls submitted \$(date -Is): d16 array \$a (8 tasks, 8G 2:00); d64 array \$b (8G 4:00, afterok:\$a); d256 array \$c (8G 12:00, afterok:\$b)"
REMOTE
    ;;
wait)
    ids=$(grep -oE 'job=[0-9]+|array [0-9]+' "$R/jobs.txt" | grep -oE '[0-9]+' | paste -sd:)
    $SSH "cd $W/logs && sbatch --wait -p compute -c 4 --mem=1G -t 00:05:00 -J p11_wait -o $W/logs/p11_wait_%j.out \
        --dependency=afterany:$ids --wrap 'echo done'; sacct -X -n -j ${ids//:/,} -o JobID%20,JobName%12,State%12,ExitCode,Elapsed" \
        | tee "$R/sacct.txt" ;;
fetch)
    mkdir -p "$R/cluster"
    rsync -a "$H:$W/results/P11/" "$R/cluster/"
    rsync -a --exclude work "$H:$G/results" "$H:$G/slurm" "$R/cluster/gls/" ;;
*) echo "usage: see header"; exit 2 ;;
esac
