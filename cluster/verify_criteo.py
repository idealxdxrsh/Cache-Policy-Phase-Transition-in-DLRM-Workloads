"""Verify a Criteo DAC file: row count, 40 columns, label in {0,1},
columns 1..13 integer-or-empty, columns 14..39 8-char lowercase hex or empty.

Usage: python -I verify_criteo.py FILE OUT_JSON
"""
import json
import re
import sys

HEX = re.compile(rb"[0-9a-f]{8}")
INT = re.compile(rb"-?[0-9]+")


def main() -> None:
    path, out = sys.argv[1], sys.argv[2]
    rows = bad_ncols = bad_label = bad_int = bad_hex = 0
    empty_cat = nonempty_cat = 0
    examples = []
    with open(path, "rb") as f:
        for line in f:
            rows += 1
            cols = line.rstrip(b"\r\n").split(b"\t")
            if len(cols) != 40:
                bad_ncols += 1
                if len(examples) < 5:
                    examples.append(f"row {rows}: {len(cols)} columns")
                continue
            if cols[0] not in (b"0", b"1"):
                bad_label += 1
            for c in cols[1:14]:
                if c and not INT.fullmatch(c):
                    bad_int += 1
            for c in cols[14:40]:
                if not c:
                    empty_cat += 1
                elif HEX.fullmatch(c):
                    nonempty_cat += 1
                else:
                    bad_hex += 1
                    if len(examples) < 5:
                        examples.append(f"row {rows}: non-hex {c[:20]!r}")
    res = dict(file=path, rows=rows, bad_ncols=bad_ncols, bad_label=bad_label,
               bad_int_fields=bad_int, cat_hex_fields=nonempty_cat,
               cat_empty_fields=empty_cat, cat_non_hex_fields=bad_hex,
               cols_14_39_all_hex_or_empty=(bad_hex == 0 and bad_ncols == 0),
               examples=examples)
    with open(out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
