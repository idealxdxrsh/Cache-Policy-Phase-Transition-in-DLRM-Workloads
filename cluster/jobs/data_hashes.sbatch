#!/bin/bash -l
#SBATCH -J data_hashes
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH --mem=2G
#SBATCH -t 01:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# sha256 and size of the key data on /scratch, so a later purge can be detected and the files verified
# (results/P2/data_hashes.txt). Coreutils only: works without any conda env.
#   check later: cd /scratch/rahulkmr/Adarsh && sha256sum -c <(grep -v '^#' data_hashes.txt | awk '{print $1"  "$3}')
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
OUT=$W/results/P2/data_hashes.txt; mkdir -p "$(dirname "$OUT")"
cd "$W"
mapfile -t P3 < <(find data/p3/traces_2000000 data/p3/traces_10000000 -type f | sort)
FILES=(data/criteo/extracted/train.txt data/criteo/raw/dac.tar.gz "${P3[@]}" data/p14/rows_2000000/stream.npz)
{
  echo "# sha256  bytes  path (relative to $W); job $SLURM_JOB_ID on $(hostname), $(date -Is)"
  for f in "${FILES[@]}"; do
    printf '%s  %s  %s\n' "$(sha256sum "$f" | cut -d' ' -f1)" "$(stat -c %s "$f")" "$f"
  done
  echo "# files: ${#FILES[@]}"
} > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
