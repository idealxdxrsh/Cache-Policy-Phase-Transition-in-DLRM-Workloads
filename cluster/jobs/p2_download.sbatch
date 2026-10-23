#!/bin/bash -l
#SBATCH -J p2_dl
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH -t 04:00:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# Downloads the Criteo Display Advertising Challenge archive (dac.tar.gz) from
# figshare (the Kaggle competition now lists only random_submission.zip).
# Source, size and checksum are recorded in results/P2/SOURCE.md.
set -euo pipefail
# Safety net: a stale KAGGLE_API_TOKEN in ~/.bashrc broke Kaggle auth (job 412860)
unset KAGGLE_API_TOKEN
W=/scratch/rahulkmr/Adarsh
OUT=$W/results/P2; mkdir -p "$OUT"
URL=https://ndownloader.figshare.com/files/10082655   # DOI 10.6084/m9.figshare.5732310.v1
NAME=dac.tar.gz
SIZE=4576820670                                       # bytes, figshare API
MD5=df9b1b3766d9ff91d5ca3eb3d23bed27                  # figshare supplied+computed MD5
RAW=$W/data/criteo/raw          # downloaded archives only
EXT=$W/data/criteo/extracted    # extracted files only
LOG=$OUT/download.txt
eval "$(conda shell.bash hook)"; conda activate /scratch/rahulkmr/Adarsh/envs/dlrm_cache
mkdir -p "$RAW" "$EXT"
{ echo "host $(hostname)"; date -Is; echo "source $URL"; } > "$LOG"

# 1. Reachability: fetch one byte; stop early if this node cannot reach the host
code=$(curl -sS -L -r 0-0 -o /dev/null --max-time 30 -w "%{http_code}" "$URL" 2>>"$LOG") || code=000
echo "reachability: HTTP $code" >> "$LOG"
if [ "$code" != 206 ] && [ "$code" != 200 ]; then
    echo "ERROR: compute node $(hostname) cannot reach $URL (HTTP $code); nothing downloaded" | tee -a "$LOG"
    exit 2
fi

# 2. Space check: archive plus extracted train.txt/test.txt (~12.6 GB) need ~20 GB free
free_gb=$(df -P -BG "$RAW" | awk 'NR==2 {sub("G","",$4); print $4}')
echo "free on $(df -P "$RAW" | awk 'NR==2 {print $6}'): ${free_gb} GB" >> "$LOG"
[ "$free_gb" -ge 20 ] || { echo "ERROR: need >= 20 GB free, have ${free_gb} GB" | tee -a "$LOG"; exit 3; }

# 3. Download (resumable into .part; renamed only when complete)
if [ -f "$RAW/$NAME" ]; then
    echo "$NAME present: skipping download" >> "$LOG"
else
    curl -sS -L --fail --retry 3 --retry-delay 30 -C - -o "$RAW/$NAME.part" "$URL" 2>>"$LOG"
    mv "$RAW/$NAME.part" "$RAW/$NAME"
fi

# 4. Verify size and MD5 BEFORE extracting; a bad archive is kept, not deleted
got_size=$(stat -c %s "$RAW/$NAME")
got_md5=$(md5sum "$RAW/$NAME" | cut -d' ' -f1)
got_sha=$(sha256sum "$RAW/$NAME" | cut -d' ' -f1)
{ echo "== archive $NAME"; echo "size   $got_size (expected $SIZE)"; echo "md5    $got_md5 (expected $MD5)";
  echo "sha256 $got_sha (computed here; source publishes none)"; } >> "$LOG"
if [ "$got_size" != "$SIZE" ] || [ "$got_md5" != "$MD5" ]; then
    echo "ERROR: size/MD5 mismatch; not extracting. File kept at $RAW/$NAME" | tee -a "$LOG"
    exit 4
fi
echo "checksum OK" >> "$LOG"

# 5. Safe extraction in Python (-I): zipfile strips unsafe paths; tarfile uses filter='data'.
python -I "$W/repo/cluster/safe_extract.py" "$RAW" "$EXT" >> "$LOG" 2>&1
echo "== extracted (bytes)" >> "$LOG"
find "$EXT" -type f -printf "%s %P\n" | sort -k2 >> "$LOG"
date -Is >> "$LOG"
