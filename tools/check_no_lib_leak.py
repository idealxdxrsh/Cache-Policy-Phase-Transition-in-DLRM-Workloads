"""Fail if any tracked file contains confidential strings from the C2 flow: library names, cell names, library file
names or paths, the C2 host address or user name.

Usage: python3 -I tools/check_no_lib_leak.py                       scan every tracked file (git ls-files); exit 1 on
                                                                   any match, or if the local pattern file is
                                                                   missing, empty or tracked
       python3 -I tools/check_no_lib_leak.py --add-from-gates <dir>
                                                                   append the cell and library names from every
                                                                   gates.rpt (Genus report_gates) under <dir> to
                                                                   the local pattern file; prints counts only
Patterns: GENERIC below (committed: they name nothing specific) plus one regular expression per line from
tools/leak_patterns.local. That file is gitignored, because the identifying patterns (library and cell names, host,
user) must not themselves be in the repo; '#' lines are comments. A match is reported as file:line and the pattern
number, never the matched text, so the output can be shown or logged.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / 'tools' / 'leak_patterns.local'
GENERIC = [
    r'(?<!\*)\.lib\.gz',                                       # compressed liberty file names (not '*' globs)
    r'_soc\.lef',                                              # LEF file names
    r'FOUNDR[Y]',                                              # vendor-kit directory name
    r'(?<![\w.=-])10\.\d{1,3}\.\d{1,3}\.\d{1,3}(?![\w.-])',    # private IPv4 address, not a version string
    r'\b20\d\d[a-z]\d[a-z]\d{4,5}[a-z]\b',                     # student-ID user names
]


def local_patterns():
    if not LOCAL.exists():
        sys.exit(f'FAIL: {LOCAL.relative_to(ROOT)} is missing (it holds the identifying patterns; see the docstring)')
    tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', str(LOCAL)], cwd=ROOT, capture_output=True)
    if tracked.returncode == 0:
        sys.exit(f'FAIL: {LOCAL.relative_to(ROOT)} is tracked by git; it must stay local')
    pats = [p for p in LOCAL.read_text().splitlines() if p.strip() and not p.startswith('#')]
    if not pats:
        sys.exit(f'FAIL: {LOCAL.relative_to(ROOT)} has no patterns')
    return pats


def add_from_gates(top):
    names = set()
    for rpt in Path(top).expanduser().rglob('gates.rpt'):
        rows = False   # inside the per-cell table: from the 'Gate ... Library' header to its 'total' line
        for line in rpt.read_text(errors='replace').splitlines():
            f = line.split()
            if f[:1] == ['Gate'] and 'Library' in f:
                rows = True
            elif rows and f[:1] == ['total']:
                rows = False
            elif rows and len(f) == 4 and f[1].isdigit():   # cell, instances, area, library
                names.update((f[0], f[3]))
    old = set(LOCAL.read_text().splitlines()) if LOCAL.exists() else set()
    new = sorted(re.escape(n) for n in names if re.escape(n) not in old)
    with LOCAL.open('a') as fh:
        fh.writelines(p + '\n' for p in new)
    print(f'{len(names)} cell and library names found, {len(new)} added to {LOCAL.relative_to(ROOT)}')


def main():
    if sys.argv[1:2] == ['--add-from-gates']:
        add_from_gates(sys.argv[2])
        return
    pats = GENERIC + local_patterns()
    regs = [re.compile(p) for p in pats]
    big = re.compile('|'.join(f'(?:{p})' for p in pats))
    files = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.split(b'\0')
    hits = 0
    for name in (f.decode() for f in files if f):
        path = ROOT / name
        if not path.is_file():
            continue
        for n, line in enumerate(path.read_bytes().decode('utf-8', 'replace').splitlines(), 1):
            if not big.search(line):
                continue
            idx = [i for i, r in enumerate(regs) if r.search(line)]
            kind = ', '.join(f'generic {i + 1}' if i < len(GENERIC) else f'local {i - len(GENERIC) + 1}' for i in idx)
            print(f'LEAK {name}:{n} (pattern {kind})')
            hits += 1
    print(f'scanned {sum(1 for f in files if f)} tracked files with {len(GENERIC)} generic + {len(pats) - len(GENERIC)} '
          f'local patterns: {"FAIL, " + str(hits) + " matching lines" if hits else "PASS, no matches"}')
    sys.exit(1 if hits else 0)


if __name__ == '__main__':
    main()
