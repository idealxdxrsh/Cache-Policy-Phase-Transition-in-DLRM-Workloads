#!/bin/bash -l
#SBATCH -J p4_env
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH --mem=8G
#SBATCH -t 01:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# Create the P4 venv on /scratch (python 3.11 from the dlrm_cache conda env) and
# pip install the CUDA 12.6 PyTorch wheel. Download ~3.41 GiB (results/P4/PLAN.md).
# Job 413583 failed: PyPI's file host (--extra-index-url) slowed to 8.2 kB/s on the cuDNN wheel and
# pip hit "Read timed out" (exit 2); download.pytorch.org ran at 31.0 MB/s. Every dependency is on the
# cu126 index, so PyPI is not used. Wheels are downloaded to $WHL first (kept across reruns; pip skips
# files already there), then installed offline. $ENV/.p4_complete marks a finished env.
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
ENV=$W/envs/p4_torch
WHL=$W/wheels/p4_cu126
IDX=https://download.pytorch.org/whl/cu126
PKGS=("torch==2.14.1+cu126" "numpy==1.26.4")
OUT=$W/results/P4; mkdir -p "$OUT" "$WHL"
[ -e "$ENV" ] && { echo "$ENV already exists; not touching it" | tee "$OUT/env_error.txt"; exit 1; }
$W/envs/dlrm_cache/bin/pip download --dest "$WHL" --index-url "$IDX" --timeout 120 --retries 10 --resume-retries 20 \
    --only-binary=:all: "${PKGS[@]}" > "$OUT/env_download_log.txt" 2>&1
$W/envs/dlrm_cache/bin/python -m venv "$ENV"
"$ENV/bin/pip" install --no-index --find-links "$WHL" "${PKGS[@]}" > "$OUT/env_install_log.txt" 2>&1
{ "$ENV/bin/python" -c "import torch, numpy; print('torch', torch.__version__, 'cuda', torch.version.cuda, 'numpy', numpy.__version__)"
  "$ENV/bin/pip" freeze; } > "$OUT/env_install.txt"
du -sh "$ENV" > "$OUT/env_du.txt"
du -sh "$WHL" >> "$OUT/env_du.txt"
touch "$ENV/.p4_complete"
