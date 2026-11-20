# Semester report.
#   make             numbers, checks, figures-independent build of report.pdf (repository copy: student ID omitted)
#   make submission  report_submission.pdf with the student ID read from student_id.local (gitignored, never
#                    committed: the ID is also a lab-server user name). The file holds one line:
#                    \newcommand{\studentid}{<ID>}
#   make figs        regenerate figs/*.pdf from committed results (paper figure scripts, output redirected here)
ROOT := ../..
PY   ?= python3
VPY  ?= $(ROOT)/.venv/bin/python

.PHONY: all check figs submission clean
all: check
	latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex

check:
	cd $(ROOT) && $(PY) -I tools/make_paper_macros.py --target report
	cd $(ROOT) && $(PY) -I tools/paper_numbers_check.py --macros docs/sem_report > docs/sem_report/numbers_check.txt; \
	  status=$$?; tail -n 3 docs/sem_report/numbers_check.txt; exit $$status

figs:
	cd $(ROOT) && $(abspath $(VPY)) docs/sem_report/figs/make_figs.py

submission: check
	@test -f student_id.local || { echo 'student_id.local is missing (see the Makefile header)'; exit 1; }
	latexmk -pdf -interaction=nonstopmode -halt-on-error -jobname=report_submission \
	  -pdflatex='pdflatex %O "\def\withid{}\input{%S}"' report.tex

clean:
	latexmk -C report.tex; latexmk -C -jobname=report_submission report.tex
