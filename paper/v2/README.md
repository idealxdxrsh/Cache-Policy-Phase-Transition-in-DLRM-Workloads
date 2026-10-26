# paper/v2: rewritten paper (IEEEtran conference, two-column, 10 pt)

Source of truth: `results/P7/CLAIMS.md` and `results/P7/TABLES.md`. The old manuscript is in `paper/old/ieee_final.pdf`.
Authors: "Adarsh [YOUR FULL NAME]" (placeholder for the full name) and Pravin Mane; affiliation from the official
BITS Pilani pages (https://www.bits-pilani.ac.in/goa/pravin-sakharam-mane,
https://www.bits-pilani.ac.in/goa/electrical-and-electronics-engineering/). No e-mail, no student ID, no postcode.

## Title options (working title = 1)
1. Frequency-Based Replacement for DLRM Embedding Caches: A Trace-Driven Study and a Synthesizable LFU Controller
2. Does LFU Help DLRM Embedding Caches? Per-Table and Shared-Cache Trace Simulation on Criteo, with an Open-PDK LFU Controller
3. Reset-on-Eviction LFU for Shared Embedding Caches: Criteo Trace Simulation and a Gate-Level-Verified Controller on NanGate45

## Build (from the repository root)
```
python3 -I tools/make_tables.py                          # results/P7/TABLES.md from committed files
for f in fig_shared fig_large fig_pertable fig_profile fig_fmax; do .venv/bin/python paper/v2/figs/$f.py; done
python3 -I tools/paper_numbers_check.py > paper/v2/numbers_check.txt   # must end with "0 failed"
python3 -I tests/test_paper_numbers_check.py                          # planted old-paper figures must fail
cd paper/v2 && latexmk -pdf main.tex
```
Figures read committed files only (`git show HEAD:<path>`), so commit results before regenerating them.
matplotlib 3.8.4 from `.venv`; fonts Liberation Serif + STIX, embedded as TrueType (pdf.fonttype 42).

## Files
| File | Content | Reads |
|---|---|---|
| `main.tex` | paper | - |
| `refs.bib` | verified references only | - |
| `TODO_refs.md` | unverified fields and references left out | - |
| `numbers_check.txt` | output of `tools/paper_numbers_check.py` | `main.tex`, `results/P7/TABLES.md` |
| `figs/fig_shared.py` | Fig. 4, shared cache vs capacity | `results/P3b/rows_*/parts/*.csv` |
| `figs/fig_large.py` | Fig. 3, five large tables by policy | `results/P3/rows_10000000/figs/hit_rates.csv`, `zipf_per_table.csv` |
| `figs/fig_pertable.py` | Fig. 2, per-table LFU minus LRU at 256 | `results/P3/rows_*/figs/hit_rates.csv` |
| `figs/fig_profile.py` | Fig. 5, embedding share vs batch | `results/P4/h{100_413621,200_413622}/results.csv`, `tools/p4_results.py` |
| `figs/fig_fmax.py` | Fig. 6, Fmax vs depth with noise bands | `results/P5*/d*_m*_1000MHz/sta.txt`, noise-floor designs |
| Fig. 1 | controller diagram, TikZ in `main.tex` | drawn from `rtl/v2/lfu_cache_controller.v` |

## Numbers in main.tex
Plain numbers must appear in TABLES.md exactly. Rounded numbers (hit rates to one decimal, Fmax to integer MHz, area
to integer um^2) are written `\rnd{shown}{source}`; the checker requires `source` to be a TABLES.md value and
`shown` to be its rounding. The "Older evidence" section of TABLES.md is excluded. Known limit of a value-only
check: an old figure that equals a genuine TABLES.md value (65) cannot be rejected by value, so the test also checks
that main.tex contains none of the old figures.

## Checks done for this version
- `latexmk -pdf`: no errors, no overfull boxes (`main.log`).
- `pdffonts main.pdf`: every font embedded, no Type 3.
- Every page rendered to PNG and inspected; 6 pages; abstract 198 words.
- `tools/paper_numbers_check.py`: 451 numbers, 0 failed (108 rounded with `\rnd`; one whitelisted year, 2014).
- `tests/test_paper_numbers_check.py`: 7 tests pass; no planted old figure is accepted.
- Underfull \vbox messages (2) are IEEEtran flush-bottom stretch around floats; no overfull boxes.
