#!/bin/bash
# P8 cluster task: one depth-256 zero-delay simulation (netlist with the VCD window, or RTL for the hit-count check).
# Line SLURM_ARRAY_TASK_ID of the task list: "D M STIM WARM WIN MODEL [SLICE]" -> synthesis/p8/run_p8.sh sim with
# NOPOWER=1; the VCD stays in $P/results/work/<run>/act.vcd.gz for the local OpenSTA step after rsync.
set -uo pipefail
P=/scratch/rahulkmr/Adarsh/p8
export PATH=/home/rahulkmr/.conda/envs/rtl_sim/bin:$PATH PY=python3 NOPOWER=1
export P8_OUT=$P/results P8_NETLISTS=/scratch/rahulkmr/Adarsh/gls/netlists
export P8_MODELS=/scratch/rahulkmr/Adarsh/gls/models/nangate45_cells_yosys.v P8_STIMULUS=$P/stimulus
read -r d m stim warm win model slice < <(sed -n "${SLURM_ARRAY_TASK_ID}p" "$1")
echo "task ${SLURM_ARRAY_JOB_ID:-?}_${SLURM_ARRAY_TASK_ID:-?} host $(hostname): $d $m $stim $warm $win $model ${slice:-}"
bash "$P/code/synthesis/p8/run_p8.sh" sim "$d" "$m" "$stim" "$warm" "$win" "$model" ${slice:+"$slice"}
