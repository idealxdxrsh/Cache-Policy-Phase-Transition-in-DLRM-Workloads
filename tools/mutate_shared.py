#!/usr/bin/env python3
"""
Mutation check for tests/test_shared_cache.py: each mutant is a deliberately
broken copy of trace_sim/run_shared_cache.py, and the test suite must FAIL on it.

Usage (from the repo root):  python3 tools/mutate_shared.py
Exit code 0 only if every mutant is caught.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'trace_sim', 'run_shared_cache.py')

MUTANTS = {
    'key_unqualified': ('    return table << ID_BITS | fid', '    return fid'),
    'tables_reversed_in_row': ('            for t, col in enumerate(cat_cols):',
                               '            for t, col in reversed(list(enumerate(cat_cols))):'),
    'empty_field_as_id_0': ("                if col < len(row) and row[col].strip():\n"
                            "                    try:\n"
                            "                        fid = int(row[col], 16)",
                            "                if col < len(row):\n"
                            "                    try:\n"
                            "                        fid = int(row[col] or '0', 16)"),
    'row_limit_off_by_one': ('            if n_rows and rows_loaded >= n_rows:',
                             '            if n_rows and rows_loaded > n_rows:'),
    'wide_id_allowed': ('                    if fid >> ID_BITS:', '                    if False:'),
    'hit_attributed_wrong_table': ('            hits[key_table(key)] += 1',
                                   '            hits[key_table(key) % 25] += 1'),
    'per_table_misses_wrong': ("'misses': per_table[t] - hits[t]", "'misses': per_table[t]"),
    'capacity_off_by_one': ('    cache = policy_cls(capacity)', '    cache = policy_cls(capacity + 1)'),
    'job_dropped': ('    jobs = [(p, c) for c in capacities for p in policies]',
                    '    jobs = [(p, c) for c in capacities for p in policies][:-1]'),
    'policy_missing': ('POLICIES = [LRUCache, LFUResetCache, LFUCache, ARCCache, WTinyLFUCache]',
                       'POLICIES = [LRUCache, LFUResetCache, LFUCache, ARCCache]'),
}


def main():
    src = open(SRC).read()
    missed = 0
    for name, (old, new) in MUTANTS.items():
        assert src.count(old) == 1, f"{name}: pattern not unique in source"
        with tempfile.TemporaryDirectory() as d:
            for sub in ('trace_sim', 'tests', 'tools'):
                shutil.copytree(os.path.join(ROOT, sub), os.path.join(d, sub),
                                ignore=shutil.ignore_patterns('results', '__pycache__'))
            with open(os.path.join(d, 'trace_sim', 'run_shared_cache.py'), 'w') as f:
                f.write(src.replace(old, new))
            r = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                '-p', 'test_shared_cache.py'],
                               cwd=d, capture_output=True, text=True, timeout=900)
        last = next((l for l in reversed(r.stderr.splitlines())
                     if l.startswith(('OK', 'FAILED'))), '?')
        caught = r.returncode != 0
        missed += not caught
        print(f"{name:28s} {'CAUGHT' if caught else 'MISSED'}  ({last})", flush=True)
    print(f"\n{len(MUTANTS) - missed}/{len(MUTANTS)} mutants caught")
    return 1 if missed else 0


if __name__ == '__main__':
    sys.exit(main())
