"""P5c: write the tree-only variant of rtl/v2 (per-group address copies removed).

Usage: python -I tools/p5c_strip_copies.py <in.v> <out.v>
Each substitution restores the rtl-v2-baseline form of a line the P5b address copies changed
(tag compare and tag write use req_addr_reg again; the copy registers and their always block
are removed). Every old text must occur exactly once, else nothing is written.
"""
import sys
from pathlib import Path

SUBS = [
    ("// Per-group copies of req_addr_reg, loaded in the same cycle with the same value,\n"
     "// so each copy drives only its group's GSIZE tag comparators and tag writes.\n"
     "// keep: stops synthesis from merging the identical registers back into one.\n"
     "(* keep *) reg [ADDR_WIDTH-1:0] req_addr_grp [0:GROUPS-1];\n", ""),
    ("(tag_store[g] == req_addr_grp[g / GSIZE]);", "(tag_store[g] == req_addr_reg);"),
    ("integer ag;\n"
     "always @(posedge clk or negedge rst_n) begin\n"
     "    if (!rst_n)\n"
     "        for (ag = 0; ag < GROUPS; ag = ag + 1) req_addr_grp[ag] <= {ADDR_WIDTH{1'b0}};\n"
     "    else if (state == IDLE && req_valid)\n"
     "        for (ag = 0; ag < GROUPS; ag = ag + 1) req_addr_grp[ag] <= req_addr;\n"
     "end\n\n", ""),
    ("                for (i = 0; i < CACHE_DEPTH; i = i + 1)\n"
     "                    if (victim_reg == i) tag_store[i] <= req_addr_grp[i / GSIZE];\n",
     "                tag_store[victim_reg]   <= req_addr_reg;\n"),
    ("//   - P5b: per-group registered copies of the request address\n"
     "//     drive the tag comparators and tag writes (same cycle)\n", ""),
]


def main():
    src = Path(sys.argv[1]).read_text()
    for old, new in SUBS:
        n = src.count(old)
        if n != 1:
            sys.exit(f"found {n} times: {old[:60]!r}")
        src = src.replace(old, new)
    if "req_addr_grp" in src:
        sys.exit("req_addr_grp still present")
    Path(sys.argv[2]).write_text(src)


if __name__ == "__main__":
    main()
