#!/bin/bash -l
# Idempotent: creates the dlrm_cache conda env from cluster/environment.yml,
# or updates it in place if it already exists. User-space only.
# Env and package cache live on /scratch: home quota is full (P2 job 412530).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_YML="$HERE/environment.yml"
ENV_PREFIX=/scratch/rahulkmr/Adarsh/envs/dlrm_cache
export CONDA_PKGS_DIRS=/scratch/rahulkmr/Adarsh/envs/pkgs
mkdir -p "$CONDA_PKGS_DIRS"

eval "$(conda shell.bash hook)"
# conda-meta/history marks a finished env; a bare dir may be a failed create
if [ -f "$ENV_PREFIX/conda-meta/history" ]; then
    echo "env $ENV_PREFIX exists: updating"
    conda env update --prefix "$ENV_PREFIX" -f "$ENV_YML" --prune
else
    echo "env $ENV_PREFIX missing: creating"
    conda env create --prefix "$ENV_PREFIX" -f "$ENV_YML"
fi
conda activate "$ENV_PREFIX"
python -V
python -c "import numpy, pandas, matplotlib; print('numpy', numpy.__version__, 'pandas', pandas.__version__)"
kaggle --version
