"""P8: Criteo request slices for the controller's power runs (option A: keys numbered inside each slice only).

Usage: python -I tools/p8_stream.py <criteo train.txt> <out_dir> [requests per slice, default 200000]
       [rows, default 2000000] [split row, default 1000000]   (the last two only for tests on small files)
The access stream is exactly P3b's shared-cache stream (trace_sim/run_shared_cache.py load_shared_trace, imported
unchanged): first 2,000,000 rows in file order, tables 0..25 within a row, empty/non-hex fields skipped, key =
table << 32 | id. Two slices of consecutive accesses: one starting at the first access of row 0, one at the first
access of row 1,000,000. Inside each slice, keys are numbered in order of first appearance (0, 1, 2, ...) and the
number is the 20-bit request address, so nothing wraps as long as a slice has fewer than 2^20 distinct keys
(checked). Writes <out>/row0.hex, <out>/row1M.hex (one hex address per line) and <out>/<slice>.json with the slice
position, its length and its number of distinct keys. Because the numbering is dense, the number of distinct keys in
any replayed prefix of a slice is max(address) + 1 over that prefix.
Also writes <out>/stream.json with the totals, cross-checked against P3b (46,128,690 accesses, 2,293,344 keys).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'trace_sim'))
from run_shared_cache import load_shared_trace  # noqa: E402

ROWS, SPLIT_ROW, AW = 2000000, 1000000, 20


def main():
    path, out = sys.argv[1], Path(sys.argv[2])
    per_slice = int(sys.argv[3]) if len(sys.argv) > 3 else 200000
    rows_n = int(sys.argv[4]) if len(sys.argv) > 4 else ROWS
    split = int(sys.argv[5]) if len(sys.argv) > 5 else SPLIT_ROW
    out.mkdir(parents=True, exist_ok=True)
    head, rows_head, _ = load_shared_trace(path, split)              # rows 0 .. split - 1
    keys, rows, per_table = load_shared_trace(path, rows_n)            # rows 0 .. rows_n - 1
    assert rows_head == split and rows == rows_n
    assert keys[:len(head)] == head, 'row-1,000,000 offset inconsistent'
    total = {'rows': rows, 'accesses': len(keys), 'unique_keys': len(set(keys)),
             'p3b_accesses': 46128690, 'p3b_unique_keys': 2293344,
             'split_row': split, 'first_access_of_split_row': len(head), 'requests_per_slice': per_slice}
    total['matches_p3b'] = total['accesses'] == 46128690 and total['unique_keys'] == 2293344
    for name, start, row in (('row0', 0, 0), ('row1M', len(head), split)):
        sl = keys[start:start + per_slice]
        ids, addr = {}, []
        for k in sl:
            if k not in ids:
                ids[k] = len(ids)
            addr.append(ids[k])
        assert len(ids) < (1 << AW), f'{name}: {len(ids)} distinct keys do not fit {AW} bits'
        (out / f'{name}.hex').write_text(''.join(f'{a:05x}\n' for a in addr))
        meta = {'slice': name, 'start_row': row, 'start_access': start, 'requests': len(sl),
                'distinct_keys': len(ids), 'address_bits': AW,
                'numbering': 'keys numbered 0,1,2,... in order of first appearance inside the slice'}
        (out / f'{name}.json').write_text(json.dumps(meta, indent=1) + '\n')
        print(json.dumps(meta))
    (out / 'stream.json').write_text(json.dumps(total, indent=1) + '\n')
    print(json.dumps(total))


if __name__ == '__main__':
    main()
