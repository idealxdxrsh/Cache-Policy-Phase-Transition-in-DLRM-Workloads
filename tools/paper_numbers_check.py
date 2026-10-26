"""Check that every number in the paper's .tex files comes from results/P7/TABLES.md (or a short whitelist).

Usage: python3 -I tools/paper_numbers_check.py [paper dir, default paper/v2] [tables, default results/P7/TABLES.md]
Exit 1 if any number fails. Prints every number with the TABLES.md line it matched, so each match can be audited.
Tested by tests/test_paper_numbers_check.py (planted old-paper figures must fail).

Two forms are accepted in the .tex:
- a plain number must equal a TABLES.md value exactly (636.1 matches 636.1, not 636 or 636.10);
- a rounded number is written \\rnd{shown}{source} (the macro typesets only `shown`): `source` must equal a TABLES.md
  value exactly, and `shown` must be `source` rounded half-up to the decimals written in `shown`
  (\\rnd{636}{636.1}, \\rnd{71.8}{71.8034}). So every rounding names the value it was rounded from.

What counts as a number in the .tex: a digit sequence (thousands commas allowed, optional decimals) that is not glued
to a letter or underscore on its left (H100, P5e, NanGate45, d16_m0 are names). Removed before scanning: comments;
tikzpicture environments; optional [...] arguments; the arguments of layout/reference commands (label, ref, cite,
includegraphics, usepackage, url, ...); tabular column specs; lengths such as 0.5\\columnwidth or 3pt. Signs are
ignored (-0.0357 matches 0.0357).
TABLES.md values: digit sequences not glued to a letter (zipf0.85 is a name), up to the heading "## Older evidence":
that section holds old figures that were not reproduced (and some that are contradicted), and the paper may not use it.
"""
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

WHITELIST = {'2014': 'year (Criteo challenge)'}
STOP = '## Older evidence'
DROP_ARG = ('label', 'ref', 'eqref', 'cite', 'includegraphics', 'usepackage', 'documentclass', 'bibliography',
            'bibliographystyle', 'input', 'url', 'vspace', 'hspace', 'setlength', 'addtolength', 'cmidrule',
            'multicolumn', 'multirow', 'IEEEoverridecommandlockouts', 'path', 'src', 'linewidth', 'arraystretch',
            'renewcommand', 'newcommand', 'DeclareUrlCommand', 'fontsize', 'texttt', 'begin')
NUM = re.compile(r'(?<![A-Za-z_\d.])\d[\d,]*(?:\.\d+)?(?![\d])')
RND = re.compile(r'\\rnd\{([^{}]*)\}\{([^{}]*)\}')


def norm(s):
    return s.strip().lstrip('-').lstrip('\u2212').rstrip(',').replace(',', '').replace('{', '').replace('}', '')


def decimals(v):
    return len(v.split('.')[1]) if '.' in v else 0


def rounded(v, k):
    return str(Decimal(v).quantize(Decimal(1).scaleb(-k), rounding=ROUND_HALF_UP))


def index(tables):
    where = {}
    for i, ln in enumerate(tables.read_text().splitlines(), 1):
        if ln.startswith(STOP):
            break
        for m in NUM.finditer(ln):
            where.setdefault(norm(m.group(0)), i)
    return where


def clean(tex):
    tex = re.sub(r'(?<!\\)%.*', '', tex)
    tex = re.sub(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}', ' ', tex, flags=re.S)
    tex = tex.replace('{,}', ',').replace('\\,', ' ').replace('$', ' ')
    tex = re.sub(r'(\\begin\{tabular\*?\})(\{[^}]*\})?\{[^{}]*(\{[^{}]*\}[^{}]*)*\}', r'\1', tex)
    for _ in range(3):
        tex = re.sub(r'\\(' + '|'.join(DROP_ARG) + r')\*?(\[[^\]]*\])*(\{[^{}]*\})?(\{[^{}]*\})?', ' ', tex)
    tex = re.sub(r'(?<=\\)[A-Za-z]+\[[^\]]*\]', '', tex)
    tex = re.sub(r'\d*\.?\d+\s*\\(columnwidth|textwidth|linewidth|baselineskip)', ' ', tex)
    tex = re.sub(r'(?<![A-Za-z_\d])\d*\.?\d+(pt|in|cm|mm|em|ex)\b', ' ', tex)
    tex = re.sub(r'\\[A-Za-z]+', ' ', tex)
    return tex


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'paper/v2')
    tables = Path(sys.argv[2] if len(sys.argv) > 2 else 'results/P7/TABLES.md')
    where = index(tables)
    bad, n = [], 0

    def fail(name, shown, why):
        bad.append((name, shown))
        print(f'FAIL      {name}: {shown:>14}  {why}')

    for tex in sorted(root.glob('*.tex')):
        text = re.sub(r'(?<!\\)%.*', '', tex.read_text())
        text = text.replace(r'\newcommand{\rnd}[2]{#1}', ' ')
        for m in RND.finditer(text):                                     # rounded numbers
            n += 1
            shown, srcv = norm(m.group(1)), norm(m.group(2))
            if srcv not in where:
                fail(tex.name, m.group(1), f'\\rnd source {m.group(2)} not in TABLES.md')
            elif rounded(srcv, decimals(shown)) != shown or decimals(srcv) < decimals(shown):
                fail(tex.name, m.group(1), f'is not {m.group(2)} rounded to {decimals(shown)} decimals')
            else:
                print(f'rounded   {tex.name}: {m.group(1):>14}  from {m.group(2)}, TABLES.md:{where[srcv]}')
        for ln in clean(RND.sub(' ', text)).splitlines():               # plain numbers
            for m in NUM.finditer(ln):
                v = norm(m.group(0))
                if not v:
                    continue
                n += 1
                if v in where:
                    print(f'ok        {tex.name}: {m.group(0):>14}  TABLES.md:{where[v]}')
                elif v in WHITELIST:
                    print(f'whitelist {tex.name}: {m.group(0):>14}  {WHITELIST[v]}')
                else:
                    fail(tex.name, m.group(0), f'not in TABLES.md; context: {ln.strip()[:90]}')
    print(f'\n{n} numbers checked against {tables} (up to "{STOP}"); {len(bad)} failed.')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
