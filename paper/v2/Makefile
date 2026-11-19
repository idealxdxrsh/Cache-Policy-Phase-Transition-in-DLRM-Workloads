# Build the paper. The PDF is built only if every number in the .tex files is a macro with a results/ source.
#   make          macros, number check, figures, PDF
#   make check    macros and number check only
# Figures read committed files only (git show HEAD:), so commit results before regenerating them.
# fig_layout_v*_d256.png are cropped once from screenshots that are never committed (figs/crop_layout.py).
ROOT := ../..
PY   ?= python3
VPY  ?= $(ROOT)/.venv/bin/python
FIGS := fig_l2 fig_shared fig_tiebreak

.PHONY: all check figs clean
all: check figs
	latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

check:
	cd $(ROOT) && $(PY) -I tools/make_paper_macros.py
	cd $(ROOT) && $(PY) -I tools/paper_numbers_check.py --macros paper/v2 > paper/v2/numbers_check.txt; \
	  status=$$?; tail -n 3 paper/v2/numbers_check.txt; exit $$status

figs:
	cd figs && for f in $(FIGS); do $(abspath $(VPY)) $$f.py || exit 1; done

clean:
	latexmk -C main.tex
