# Implementation report (synthesis, gate-level simulation, place and route, corners).
#   make             tables, number macros, number check, PDF (repository copy: student ID omitted)
#   make check       tables, macros and number check only
#   make submission  synthesis_report_submission.pdf with the student ID from ../sem_report/student_id.local
#                    (gitignored, never committed: the ID is also a lab-server user name)
# Every number is \R{key}: gen_tables.py lays out the tables, tools/make_paper_macros.py --target synth defines the
# keys from committed results files, tools/paper_numbers_check.py --macros fails on any digit without a source.
ROOT := ../..
PY   ?= python3
ID   ?= ../sem_report/student_id.local

.PHONY: all check submission clean
all: check
	latexmk -pdf -interaction=nonstopmode -halt-on-error synthesis_report.tex

check:
	cd $(ROOT) && $(PY) -I docs/synthesis_report/gen_tables.py
	cd $(ROOT) && $(PY) -I tools/make_paper_macros.py --target synth
	cd $(ROOT) && $(PY) -I tools/paper_numbers_check.py --macros docs/synthesis_report > docs/synthesis_report/numbers_check.txt; \
	  status=$$?; tail -n 3 docs/synthesis_report/numbers_check.txt; exit $$status

submission: check
	@test -f $(ID) || { echo '$(ID) is missing (one line: \newcommand{\studentid}{<ID>})'; exit 1; }
	latexmk -pdf -interaction=nonstopmode -halt-on-error -jobname=synthesis_report_submission \
	  -pdflatex='pdflatex %O "\def\withid{}\input{%S}"' synthesis_report.tex

clean:
	latexmk -C synthesis_report.tex; latexmk -C -jobname=synthesis_report_submission synthesis_report.tex
