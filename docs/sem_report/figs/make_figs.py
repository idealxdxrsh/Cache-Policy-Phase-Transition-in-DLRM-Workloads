"""Build the report's figures with the paper's figure scripts (paper/v2/figs), writing the PDFs into this folder.

Usage (from the repository root): .venv/bin/python docs/sem_report/figs/make_figs.py
The scripts read committed result files only (git show HEAD:<path>); style.OUT is pointed here so paper/v2/figs is not
touched. The cropped layout images are used from paper/v2/figs (see paper/v2/figs/crop_layout.py).
"""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER_FIGS = HERE.parents[2] / 'paper' / 'v2' / 'figs'
sys.path.insert(0, str(PAPER_FIGS))
import style  # noqa: E402

style.OUT = HERE
for name in ('fig_l2', 'fig_shared', 'fig_tiebreak', 'fig_pertable', 'fig_large', 'fig_profile'):
    sys.argv = [name]
    runpy.run_path(str(PAPER_FIGS / f'{name}.py'), run_name='__main__')
sys.argv = ['fig_fmax', str(HERE / 'fig_fmax.pdf'), '6.2']       # output path and width (inches)
runpy.run_path(str(PAPER_FIGS / 'fig_fmax.py'), run_name='__main__')
