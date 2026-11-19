#!/bin/bash -l
#SBATCH -J env_rebuild
#SBATCH -p compute
#SBATCH -N 1 -n 1 -c 4   # compute QOS cpulimit: min 4 CPUs
#SBATCH --mem=8G
#SBATCH -t 00:30:00
#SBATCH -o /scratch/rahulkmr/Adarsh/logs/%x_%j.out
# Offline rebuild of the dlrm_cache conda env after files were purged from /scratch (between 2026-11-16 23:17
# and 2026-11-17 22:47: 17,807 of 34,647 package files missing, python stdlib incomplete; P14 jobs 456795-7
# failed with "No module named 'enum'"). The 165 downloaded package archives in envs/pkgs matched the sha256
# hashes in conda-meta, so no download is needed:
#   1. rename the broken env to envs/dlrm_cache.purged_2026-11-19 (kept, not deleted);
#   2. copy the archives named in cluster/dlrm_cache.explicit.txt (conda list --explicit --md5 of the old env,
#      same 165 builds) into a fresh package cache, checking each md5, so the damaged extracted folders in
#      envs/pkgs are not reused;
#   3. conda create --offline at the original path (envs/p4_torch is a venv whose python links to it);
#   4. checks: no file of any package missing, imports, tool versions, p4_torch torch/numpy versions as in
#      results/P4/env_install.txt. Exit 0 only if every check passes (P14 main jobs are chained afterok).
# Not reinstalled: the pip-only packages kaggle and python-dotenv (only used by the P2 download).
set -euo pipefail
W=/scratch/rahulkmr/Adarsh
ENV=$W/envs/dlrm_cache
OLD=$W/envs/dlrm_cache.purged_2026-11-19
SRC=$W/envs/pkgs
PKGS=$W/envs/pkgs_2026-11-19
LIST=$W/repo/cluster/dlrm_cache.explicit.txt
OUT=$W/results/env_rebuild_$SLURM_JOB_ID; mkdir -p "$OUT"
R=$OUT/result.txt
fail() { echo "FAIL: $*" | tee -a "$R"; exit 1; }
echo "host $(hostname) job $SLURM_JOB_ID start $(date -Is)" > "$R"
[ -f "$LIST" ] || fail "no $LIST"
[ "$(grep -c '^https://' "$LIST")" = 165 ] || fail "$LIST does not list 165 packages"
# A rerun after a failed attempt finds the broken env already renamed (OLD exists, ENV absent) and the archives
# already in PKGS: both are reused, every archive in PKGS is md5-checked again.
[ -e "$OLD" ] && [ -e "$ENV" ] && fail "both $OLD and $ENV exist"
mkdir -p "$PKGS"
n=0
while read -r line; do
  url=${line%%#*}; md5=${line##*#}; fn=${url##*/}
  if [ ! -f "$PKGS/$fn" ]; then
    [ -f "$SRC/$fn" ] || fail "archive missing: $fn"
    cp -p "$SRC/$fn" "$PKGS/"
  fi
  [ "$(md5sum "$PKGS/$fn" | cut -d' ' -f1)" = "$md5" ] || fail "md5 mismatch: $fn"
  n=$((n+1))
done < <(grep '^https://' "$LIST")
# conda finds a cached archive through urls.txt (archive URL per line); without it the offline create tried to
# download every package (job 459996: "EnforceUnusedAdapter ... remote connection in offline mode").
grep '^https://' "$LIST" | sed 's/#.*//' > "$PKGS/urls.txt"
echo "archives in $PKGS md5-checked: $n; urls.txt lines: $(wc -l < "$PKGS/urls.txt")" | tee -a "$R"
if [ -e "$ENV" ]; then mv "$ENV" "$OLD"; echo "renamed $ENV -> $OLD" | tee -a "$R"; fi
export CONDA_PKGS_DIRS=$PKGS
eval "$(conda shell.bash hook)"
conda --version >> "$R"
conda create --offline --yes --prefix "$ENV" --file "$LIST" > "$OUT/create_log.txt" 2>&1 \
  || { tail -n 20 "$OUT/create_log.txt" >> "$R"; fail "conda create rc != 0"; }
echo "conda create done $(date -Is)" | tee -a "$R"
# Check 1: every file listed in conda-meta exists (system python: does not depend on the env)
c1=$(/usr/bin/python3 -I - "$ENV" 2>&1 <<'PY'
import glob, json, os, sys
p = sys.argv[1]; js = glob.glob(p + '/conda-meta/*.json'); tot = miss = 0
for j in js:
    fs = json.load(open(j)).get('files', [])
    tot += len(fs); miss += sum(not os.path.lexists(os.path.join(p, f)) for f in fs)
print(f'conda-meta packages {len(js)}, files listed {tot}, missing {miss}')
sys.exit(0 if len(js) == 165 and miss == 0 else 1)
PY
) || fail "conda-meta file check: $c1"
echo "$c1" | tee -a "$R"
# Check 2: imports and tools in dlrm_cache
c2=$("$ENV/bin/python" -I -c "import enum, sys, numpy, pandas, matplotlib; print('dlrm_cache python', sys.version.split()[0], 'numpy', numpy.__version__, 'pandas', pandas.__version__, 'matplotlib', matplotlib.__version__)" 2>&1) \
  || fail "dlrm_cache imports: $(echo "$c2" | tail -n 2)"
echo "$c2" | tee -a "$R"
c3=$("$ENV/bin/yosys" -V 2>&1 | head -n 1) || fail "yosys: $c3"
c4=$("$ENV/bin/iverilog" -V 2>&1 | head -n 1) || true
echo "yosys: $c3 / iverilog: $c4" | tee -a "$R"
# Check 3: the p4_torch venv (unchanged) on the rebuilt python
V=$("$W/envs/p4_torch/bin/python" -I -c "import enum, torch, numpy; print(torch.__version__, torch.version.cuda, numpy.__version__)" 2>&1 | tail -n 1) || true
echo "p4_torch torch/cuda/numpy: $V" | tee -a "$R"
[ "$V" = "2.14.1+cu126 12.6 1.26.4" ] || fail "p4_torch versions differ from results/P4/env_install.txt"
echo "ALL CHECKS PASSED $(date -Is)" | tee -a "$R"
du -sh "$ENV" "$PKGS" >> "$R"
