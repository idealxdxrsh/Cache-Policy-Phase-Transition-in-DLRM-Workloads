"""Fail if any tracked file contains confidential strings from the C2 flow: library names, cell names, library file
names or paths, the C2 host address or user name.

Usage: python3 -I tools/check_no_lib_leak.py                       scan every tracked file (git ls-files); exit 1 on
                                                                   any match, or if the local pattern file is
                                                                   missing, empty or tracked
       python3 -I tools/check_no_lib_leak.py --history                scan every commit reachable from any ref
                                                                   (git log --all -p: all local branches, tags and
                                                                   remote-tracking branches), patches and commit
                                                                   messages; reports commit hash, file and pattern
                                                                   number only; exit 1 on any match
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


def kinds(regs, line):
    idx = [i for i, r in enumerate(regs) if r.search(line)]
    return [f'generic {i + 1}' if i < len(GENERIC) else f'local {i - len(GENERIC) + 1}' for i in idx]


def history(regs, big):
    # one stream: a marker line per commit, its message, then its patch; text patches only (binary ones are counted)
    cmd = ['git', 'log', '--all', '-p', '--no-color', '--no-ext-diff', '--format=@@LEAKCHECK %H%n%B%n@@LEAKCHECK-END']
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE)
    found = {}                                   # (commit, file) -> {pattern: 'added' or 'removed/context'}
    commits = binary = 0
    commit, where, in_msg = None, None, False
    for raw in proc.stdout:
        line = raw.decode('utf-8', 'replace').rstrip('\n')
        if line.startswith('@@LEAKCHECK ') and len(line) == 12 + 40:
            commit, where, in_msg = line[12:24], '(commit message)', True
            commits += 1
            continue
        if line == '@@LEAKCHECK-END':
            in_msg, where = False, None
            continue
        if not in_msg:
            if line.startswith('diff --git '):
                where = line.split(' b/', 1)[-1]
                continue
            if line.startswith('+++ b/') or (line.startswith('--- a/') and where is None):
                where = line[6:]
            if line.startswith('Binary files '):
                binary += 1
                continue
        if commit is None or not big.search(line):
            continue
        tag = 'added' if (not in_msg and line.startswith('+') and not line.startswith('+++')) or in_msg else \
            'removed/context'
        for k in kinds(regs, line):
            slot = found.setdefault((commit, where), {})
            if slot.get(k) != 'added':
                slot[k] = tag
    if proc.wait() != 0:
        sys.exit('FAIL: git log failed')
    for (c, w), ks in sorted(found.items()):
        print(f"LEAK commit {c} {w} ({', '.join(f'{k}: {t}' for k, t in sorted(ks.items()))})")
    hit_commits = len({c for c, _ in found})
    print(f'scanned {commits} commits (patches and messages; {binary} binary patches not scanned) with {len(GENERIC)} '
          f'generic + {len(regs) - len(GENERIC)} local patterns: '
          f'{"FAIL, " + str(hit_commits) + " commits with matches" if found else "PASS, no matches"}')
    sys.exit(1 if found else 0)


def main():
    if sys.argv[1:2] == ['--add-from-gates']:
        add_from_gates(sys.argv[2])
        return
    pats = GENERIC + local_patterns()
    regs = [re.compile(p) for p in pats]
    big = re.compile('|'.join(f'(?:{p})' for p in pats))
    if sys.argv[1:2] == ['--history']:
        history(regs, big)
    files = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.split(b'\0')
    hits = 0
    for name in (f.decode() for f in files if f):
        path = ROOT / name
        if not path.is_file():
            continue
        for n, line in enumerate(path.read_bytes().decode('utf-8', 'replace').splitlines(), 1):
            if not big.search(line):
                continue
            print(f"LEAK {name}:{n} (pattern {', '.join(kinds(regs, line))})")
            hits += 1
    print(f'scanned {sum(1 for f in files if f)} tracked files with {len(GENERIC)} generic + {len(pats) - len(GENERIC)} '
          f'local patterns: {"FAIL, " + str(hits) + " matching lines" if hits else "PASS, no matches"}')
    sys.exit(1 if hits else 0)


if __name__ == '__main__':
    main()
