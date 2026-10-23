#!/bin/bash -l
#SBATCH -J p2_dl
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH -t 04:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# Downloads the Kaggle Criteo Display Advertising Challenge data.
# The kaggle CLI reads ~/.kaggle/kaggle.json itself; this script never touches it.
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
OUT=$W/results/P2; mkdir -p "$OUT"
COMP=criteo-display-ad-challenge
RAW=$W/data/criteo/raw          # downloaded archives only
EXT=$W/data/criteo/extracted    # extracted files only
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
mkdir -p "$RAW" "$EXT"
{ echo "host $(hostname)"; date -Is; kaggle --version; echo "competition $COMP"; } > "$OUT/download.txt"
kaggle competitions files -c "$COMP" >> "$OUT/download.txt" 2>&1
if [ -z "$(ls -A "$RAW")" ]; then
    kaggle competitions download -c "$COMP" -p "$RAW" 2>&1 | tail -n 5 >> "$OUT/download.txt"
else
    echo "raw dir non-empty: skipping download" >> "$OUT/download.txt"
fi
echo "== archives (bytes, sha256)" >> "$OUT/download.txt"
for f in "$RAW"/*; do
    echo "$(stat -c %s "$f") $(sha256sum "$f" | cut -d' ' -f1) $(basename "$f")" >> "$OUT/download.txt"
done
# Safe extraction in Python (-I): zipfile strips unsafe paths; tarfile uses filter='data'.
python -I "$W/repo/cluster/safe_extract.py" "$RAW" "$EXT" >> "$OUT/download.txt" 2>&1
echo "== extracted (bytes)" >> "$OUT/download.txt"
find "$EXT" -type f -printf "%s %P\n" | sort -k2 >> "$OUT/download.txt"
date -Is >> "$OUT/download.txt"
