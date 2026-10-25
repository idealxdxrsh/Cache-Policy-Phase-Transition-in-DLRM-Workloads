"""P5d noise floor: write logically identical rewrites of rtl/v2 for the synthesis flow.

Usage: python -I tools/p5d_null_variants.py <in.v> <outdir>
Each variant is one exact text substitution that does not change the logic (operand order of an
equality, an OR, or a comparison written the other way round). Any Fmax difference between these
and the unmodified RTL is variation from the flow (Yosys/abc structuring), not a design effect.
Every old text must occur exactly once, else nothing is written.
"""
import sys
from pathlib import Path

VARIANTS = {
    "null_tagcmp_swap": ("(tag_store[g] == req_addr_grp[g / GSIZE]);",
                         "(req_addr_grp[g / GSIZE] == tag_store[g]);"),
    "null_hitor_swap": ("assign h_any[g] = h_any[2*g+1] | h_any[2*g+2];",
                        "assign h_any[g] = h_any[2*g+2] | h_any[2*g+1];"),
    "null_stageB_gt": ("wire take_r = rv < lv;", "wire take_r = lv > rv;"),
}


def main():
    src = Path(sys.argv[1]).read_text()
    out = Path(sys.argv[2])
    for old, _ in VARIANTS.values():
        if src.count(old) != 1:
            sys.exit(f"found {src.count(old)} times: {old!r}")
    out.mkdir(parents=True, exist_ok=True)
    for name, (old, new) in VARIANTS.items():
        (out / f"{name}.v").write_text(src.replace(old, new))


if __name__ == "__main__":
    main()
