"""Check that every number in the paper's .tex files appears in results/P7/TABLES.md (or on a short whitelist).

Usage: python3 -I tools/paper_numbers_check.py [paper dir, default paper/v2] [tables, default results/P7/TABLES.md]
Exit 1 if any number is missing. Prints every number with the TABLES.md line it matched, so a match can be audited.

What counts as a number in the .tex: a digit sequence (thousands commas allowed, optional decimals) that is not glued
to a letter or underscore on its left (so H100, P5e, NanGate45, d16_m0 are names, not numbers). Removed before
scanning: comments; tikzpicture environments (drawing coordinates); optional [...] arguments; the arguments of
layout/reference commands (label, ref, cite, includegraphics, usepackage, ...); tabular column specs; lengths such
as 0.5\\columnwidth or 3pt. Signs are ignored (-0.0357 matches 0.0357). Matching is on the normalised string, so
636.1 does not match 636.10 or 636; numbers must be written as they appear in TABLES.md.
In TABLES.md every digit sequence counts, also inside names (zipf0.6 gives 0.6), because those are data values.
"""
import re
import sys
from pathlib import Path

WHITELIST = {'2014': 'year (Criteo challenge)'}
DROP_ARG = ('label', 'ref', 'eqref', 'cite', 'includegraphics', 'usepackage', 'documentclass', 'bibliography',
            'bibliographystyle', 'input', 'url', 'vspace', 'hspace', 'setlength', 'addtolength', 'cmidrule',
            'multicolumn', 'multirow', 'IEEEoverridecommandlockouts', 'path', 'linewidth', 'arraystretch',
            'renewcommand', 'newcommand', 'fontsize', 'texttt', 'begin')
NUM_TEX = re.compile(r'(?<![A-Za-z_\d.])\d[\d,]*(?:\.\d+)?(?![\d])')
NUM_TAB = re.compile(r'\d[\d,]*(?:\.\d+)?')


def norm(s):
    s = s.rstrip(',').replace(',', '')
    return s


def clean(tex):
    tex = re.sub(r'(?<!\\)%.*', '', tex)
    tex = re.sub(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}', ' ', tex, flags=re.S)
    tex = tex.replace('{,}', ',').replace('\\,', ' ').replace('$', ' ')
    tex = re.sub(r'(\\begin\{tabular\*?\})(\{[^}]*\})?\{[^{}]*(\{[^{}]*\}[^{}]*)*\}', r'\1', tex)
    for _ in range(3):
        tex = re.sub(r'\\(' + '|'.join(DROP_ARG) + r')\*?(\[[^\]]*\])*(\{[^{}]*\})?(\{[^{}]*\})?', ' ', tex)
    tex = re.sub(r'(?<=\\)[A-Za-z]+\[[^\]]*\]', '', tex)                      # optional args of other commands
    tex = re.sub(r'\d*\.?\d+\s*\\(columnwidth|textwidth|linewidth|baselineskip)', ' ', tex)
    tex = re.sub(r'(?<![A-Za-z_\d])\d*\.?\d+(pt|in|cm|mm|em|ex)\b', ' ', tex)
    tex = re.sub(r'\\[A-Za-z]+', ' ', tex)                                    # remaining command names
    return tex


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'paper/v2')
    tables = Path(sys.argv[2] if len(sys.argv) > 2 else 'results/P7/TABLES.md')
    where = {}
    for i, ln in enumerate(tables.read_text().splitlines(), 1):
        for m in NUM_TAB.finditer(ln):
            where.setdefault(norm(m.group(0)), i)
    missing, n = [], 0
    for tex in sorted(root.glob('*.tex')):
        for lno, ln in enumerate(clean(tex.read_text()).splitlines(), 1):
            for m in NUM_TEX.finditer(ln):
                v = norm(m.group(0))
                if not v:
                    continue
                n += 1
                if v in where:
                    print(f'ok        {tex.name}: {m.group(0):>14}  TABLES.md:{where[v]}')
                elif v in WHITELIST:
                    print(f'whitelist {tex.name}: {m.group(0):>14}  {WHITELIST[v]}')
                else:
                    missing.append((tex.name, m.group(0), ln.strip()[:100]))
                    print(f'MISSING   {tex.name}: {m.group(0):>14}  context: {ln.strip()[:100]}')
    print(f'\n{n} numbers checked against {tables}; {len(missing)} missing.')
    sys.exit(1 if missing else 0)


if __name__ == '__main__':
    main()
