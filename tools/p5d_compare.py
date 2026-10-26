"""Before/after tables for P5d. NanGate45, not TSMC. Pre-layout. No power numbers.

Usage: python -I tools/p5d_compare.py <liberty>
Columns: P5 = rtl-v2-baseline (results/P5); P5b (results/P5b); P5c = Stage A + Stage B trees + address
copies (results/P5c/tree_copies, commit 73016e0); P5d = P5c + hit_idx priority tree (results/P5d, final RTL);
P5d packed = the same tree written as flat vectors (results/P5d/attempt1_packed_vectors).
Same table code as tools/p5b_compare.py; Fmax = 1 / (period - WNS) of that netlist.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p5b_compare import main  # noqa: E402

RUNS = [('P5', 'results/P5'), ('P5b', 'results/P5b'), ('P5c', 'results/P5c/tree_copies'), ('P5d', 'results/P5d'),
        ('P5d packed', 'results/P5d/attempt1_packed_vectors')]

if __name__ == '__main__':
    main(RUNS)
