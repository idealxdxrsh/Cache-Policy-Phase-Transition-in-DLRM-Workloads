# Push checklist for https://github.com/idealxdxrsh/Cache-Policy-Phase-Transition-in-DLRM-Workloads

Prepared 2026-10-26 on local branch `merge-origin-main`. **Nothing has been pushed**; no history was rewritten and
no force-push is needed.

## 1. README
- `results/P7/README.diff`: `git apply --check` passed and the diff was applied to `README.md` in commit 419af98.
  The diff still pointed to the old Google Drive manuscript, so in the same commit the paper links were changed:
  current paper `paper/v2/main.pdf`, superseded manuscript `paper/old/ieee_final.pdf` (the old synthesis report link
  is kept and labelled superseded).
- README still shows your student ID (`2023B1A31167G`, lines 4 and 349, as in the original README). Not changed;
  decide before pushing.

## 2. Pre-push checks
| Check | Result |
|---|---|
| Tracked files | 2,033 |
| Files over 50 MB (current tree) | none; largest `paper/old/ieee_final.pdf` 873,777 bytes |
| Largest blob in all history | same file, 873,777 bytes (GitHub limit 100 MB) |
| Netlists (`netlist.v`) | not tracked, never in history (gitignored; tracked `.v` files are RTL, RTL variants and a one-inverter STA test) |
| Generated cell models (`results/P5f_gls/models/`) | not tracked, never in history |
| NanGate45 liberty (`*.lib`, `*.lib.gz`) | not tracked, never in history |
| Criteo data (`criteo/`, `train.txt`, `dac.tar.gz`) | not tracked, never in history |
| `.venv/` | not tracked, never in history |
| LaTeX build files (`.aux .log .bbl .blg .fls .fdb_latexmk`) | not tracked; the one `.log` in history is `results/P2/bootstrap_full.log` (conda bootstrap log, scanned below) |
| Slurm `.out` | not tracked, never in history |
| Anything under `~/eda` | not tracked, never in history |
| History scan (`git log --all -p`, added lines): `KGAT_` | 0 |
| `api_key` | 0 |
| `BEGIN ... PRIVATE KEY` | 0 |
| GitHub/AWS/OpenAI-style tokens, `"key": "<32 hex>"` | 0 |
| `kaggle` | 82 lines in 19 files: CLI commands, docs, pip install log, `unset KAGGLE_API_TOKEN` (no value). No token. |
| `password` | 2 lines (CLAUDE.md rule, P0 summary "no password/OTP prompt"). No password. |
| `id_ed25519` | 3 lines in `cluster/ssh_config.example` (key file path and ssh-keygen example). No key material. |
| Your email in file contents | 0 |
| Author / committer emails (`git log --format='%ae %ce' \| sort -u`) | `adarsh25may.m@gmail.com adarsh25may.m@gmail.com` (all 50 local commits); remote commit 40d20a7 also uses it. Commit trailer: `Claude Opus 5.5 <noreply@anthropic.com>` |

Not secrets, but public once pushed: commit metadata email (above); cluster user name, cluster host name and
`/scratch` paths in scripts, logs and `.claude/settings.json` (tracked; permission rules only).

## 3. Remote and merge
- `git remote -v` was empty; `origin` was added (fetch and push URL
  `https://github.com/idealxdxrsh/Cache-Policy-Phase-Transition-in-DLRM-Workloads.git`) and fetched read-only.
- `origin/main`: one commit, 40d20a7 "Initialize README with project details and findings" (Adarsh, 2026-04-17),
  adding `readme.md` (408 lines): the old README with claims marked CONTRADICTED/UNSUPPORTED in
  `results/P7/CLAIMS.md` (83.74%, 5.15x, TSMC 28nm, +3.00%, ...). No tags on the remote.
- Merge on new branch `merge-origin-main`: `git merge origin/main --allow-unrelated-histories` (merge commit bcaa7a6).
  There was no textual conflict (`readme.md` vs `README.md` are different names, but they collide on
  case-insensitive filesystems). Resolution "keep our README": `readme.md` removed in follow-up commit 4aef0a9
  (the removal inside the merge commit failed, and the merge was not amended). Tree of `merge-origin-main` =
  tree of `master` (`git diff --stat master merge-origin-main` is empty).
- `origin/main` is an ancestor of `merge-origin-main`, so pushing it to `main` is a fast-forward.
- Tests on `merge-origin-main`:
  | Test | Result |
  |---|---|
  | `.venv/bin/python -m unittest tests.test_policies` | 40 tests OK |
  | `.venv/bin/python -m unittest tests.test_shared_cache` | 16 tests OK |
  | `.venv/bin/python -m unittest tests.test_profile_embedding` | 9 skipped (PyTorch not installed locally) |
  | `python3 -I tests/test_paper_numbers_check.py` | 7 tests OK; no planted old figure accepted |
  | `python3 -I tools/paper_numbers_check.py` | 451 numbers, 0 failed |
  | `rtl/v2/tb_lfu_cache.sv`, depths 16/64/256 x modes 0/1 (Icarus 12) | 6/6 ALL TESTS PASSED |

## 4. Tags and unpushed commits
- Local tags (both lightweight, neither on the remote): `rtl-v2-baseline` -> 1483717, `rtl-v2-final` -> baba9e5.
  Both are in the history of `merge-origin-main`.
- Commits on `merge-origin-main` not on `origin/main`: 52 (all 50 local commits from 6c0def5 to 419af98, the merge
  bcaa7a6 and 4aef0a9), plus this checklist commit. Every commit hash cited in the paper's Artifact Availability
  paragraph (a84d9a9, c81407a, 79f9adc, daf1601, 37c353c, d7a2b54, 18b6aeb, 215d493, 2af6b00) is among them.

## 5. Prof. Pravin Mane in the history
- `paper/v2`: named as co-author ("Pravin Mane", own IEEE author block) since commit bbe9e23; in the current
  `paper/v2/main.tex`, `paper/v2/README.md` and `paper/v2/main.pdf`. Commit 7e124a7 (first paper/v2) did not name
  him (its only "Mane" match is "Ben Manes", a TinyLFU author in `refs.bib`).
- Elsewhere (all versions in history): `CLAUDE.md` ("Mentor: Prof. Pravin Mane"; counter scheme pending him),
  `PLAN.md`, `README.md`, `results/P1/SUMMARY.md`, `results/P5/PLAN.md`, the header comment of `rtl/v2/lfu_cache_controller.v`
  and RTL variant copies under `results/P5c`, `results/P5d` ("pending Prof. Mane"), `results/P7/README.*`.
  Confirm he agrees to be named as co-author before the repository is public.

## 6. Commands to push (run them yourself)
```
cd ~/Cache-Policy-Phase-Transition-in-DLRM-Workloads
git switch merge-origin-main
git push origin merge-origin-main:main          # fast-forward of origin/main; no --force
git push origin rtl-v2-baseline rtl-v2-final    # the two tags
```
Optionally keep the local branch name in sync afterwards: `git branch -f master merge-origin-main` (local only).

If GitHub asks for credentials: GitHub does not accept your account password for `git push` over HTTPS. Either
(a) user name `idealxdxrsh` and a personal access token as the password (GitHub > Settings > Developer settings >
Personal access tokens; fine-grained, this repository only, Contents: read and write), or (b) install GitHub CLI and
run `gh auth login` (it sets up the credential helper), or (c) use SSH: add your public key to GitHub, then
`git remote set-url origin git@github.com:idealxdxrsh/Cache-Policy-Phase-Transition-in-DLRM-Workloads.git`.
No credential helper is configured here and `gh` is not installed. Do not paste a token into any file in the repo.
