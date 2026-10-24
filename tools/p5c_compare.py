"""Before/after tables for P5c. NanGate45, not TSMC. Pre-layout. No power numbers.

Usage: python -I tools/p5c_compare.py <liberty>
Columns: P5 = rtl-v2-baseline (results/P5); P5b = Stage-B tree + address copies (results/P5b);
P5c tree only = Stage A + Stage B trees, no address copies (results/P5c/tree_only);
P5c tree + copies = the same plus the P5b address copies (results/P5c/tree_copies).
Same table code as tools/p5b_compare.py; Fmax = 1 / (period - WNS) of that netlist.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p5b_compare import main  # noqa: E402

RUNS = [('P5', 'results/P5'), ('P5b', 'results/P5b'),
        ('P5c tree only', 'results/P5c/tree_only'), ('P5c tree + copies', 'results/P5c/tree_copies')]

if __name__ == '__main__':
    main(RUNS)
