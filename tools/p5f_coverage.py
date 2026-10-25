"""P5f: list every distinct cell type in the netlists and whether the generated models cover it.

Usage: python -I tools/p5f_coverage.py <models.v> <cellcheck.md> <netlist.v>...   (prints Markdown; exit 1 on any FAIL)
A cell type is covered (PASS) only if (a) models.v defines a module of that name and (b) tools/p5f_cellcheck.py
reported PASS for it in <cellcheck.md>. Scan flip-flops (SDFF*) and any instance whose type is neither a model
nor a cell are reported as well. Instance lines are those of Yosys write_verilog: `  <TYPE> <name> (`.
"""
import re
import sys
from collections import Counter
from pathlib import Path

INST = re.compile(r'^\s+([A-Za-z_]\w*)\s+(\\\S+|[\w$]+)\s+\(', re.M)
KEYWORDS = {'module', 'wire', 'input', 'output', 'reg', 'assign', 'inout'}


def main():
    models = set(re.findall(r'^module\s+(\w+)', Path(sys.argv[1]).read_text(), re.M))
    checked = dict(re.findall(r'^\| (\w+) \|.*\| (PASS|FAIL) \|$', Path(sys.argv[2]).read_text(), re.M))
    per = {}
    for n in sys.argv[3:]:
        per[n] = Counter(t for t, _ in INST.findall(Path(n).read_text()) if t not in KEYWORDS)
    allc = Counter()
    for c in per.values():
        allc.update(c)
    fail = 0
    out = [f'{len(models)} model modules in the generated file; {len(per)} netlists; {len(allc)} distinct cell types.',
           '', '| cell type | instances (all netlists) | netlists using it | model module | cell check | coverage |',
           '|---|---|---|---|---|---|']
    for t in sorted(allc):
        has = t in models
        chk = checked.get(t, 'not checked')
        ok = has and chk == 'PASS'
        fail += not ok
        out.append(f'| {t} | {allc[t]:,} | {sum(t in c for c in per.values())} of {len(per)} | {"yes" if has else "NO"} | '
                   f'{chk} | {"PASS" if ok else "FAIL"} |')
    scan = sorted(t for t in allc if t.startswith('SDFF'))
    out += ['', f'Scan flip-flops (SDFF*) in any netlist: {", ".join(scan) if scan else "none"}.',
            f'Cell types without full coverage: {fail}.']
    print('\n'.join(out))
    sys.exit(1 if fail or scan else 0)


if __name__ == '__main__':
    main()
