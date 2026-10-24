#!/bin/bash -l
#SBATCH -J p4_env
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH --mem=8G
#SBATCH -t 01:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# Create the P4 venv on /scratch (python 3.11 from the dlrm_cache conda env) and
# pip install the CUDA 12.6 PyTorch wheel. Download ~3.41 GiB (results/P4/PLAN.md).
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
ENV=$W/envs/p4_torch
OUT=$W/results/P4; mkdir -p "$OUT"
[ -e "$ENV" ] && { echo "$ENV already exists; not touching it" | tee "$OUT/env_error.txt"; exit 1; }
$W/envs/dlrm_cache/bin/python -m venv "$ENV"
"$ENV/bin/pip" install --no-cache-dir --index-url https://download.pytorch.org/whl/cu126 \
    --extra-index-url https://pypi.org/simple "torch==2.14.1+cu126" "numpy==1.26.4" \
    > "$OUT/env_install_log.txt" 2>&1
{ "$ENV/bin/python" -c "import torch, numpy; print('torch', torch.__version__, 'cuda', torch.version.cuda, 'numpy', numpy.__version__)"
  du -sh "$ENV"; "$ENV/bin/pip" freeze; } > "$OUT/env_install.txt"
