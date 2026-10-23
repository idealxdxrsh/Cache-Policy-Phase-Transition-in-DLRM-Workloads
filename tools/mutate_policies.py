#!/usr/bin/env python3
"""
Mutation check for tests/test_policies.py: each mutant is a deliberately
broken copy of trace_sim/run_trace_sim.py, and the test suite must FAIL on it.

Usage (from the repo root):  python3 tools/mutate_policies.py
Exit code 0 only if every mutant is caught.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'trace_sim', 'run_trace_sim.py')

MUTANTS = {
    'lru_no_refresh': ('            self.cache.move_to_end(key)\n            self.hits += 1',
                       '            self.hits += 1'),
    'lfu_history_dropped': ('            del self.cache[victim]          # freq[victim] is kept',
                            '            del self.cache[victim]; del self.freq[victim]'),
    'cms_no_saturate': ('            if row[i] < mc:\n                row[i] += 1',
                        '            row[i] = (row[i] + 1) & 255'),
    'cms_no_aging': ('        if self.additions >= self.sample_size:\n            self.age()',
                     '        pass'),
    'wtlfu_admit_on_tie': ('if self.sketch.estimate(candidate) > self.sketch.estimate(victim):',
                           'if self.sketch.estimate(candidate) >= self.sketch.estimate(victim):'),
    'wtlfu_no_promote': ('            del self.probation[key]\n            self.protected[key] = 1\n',
                         '            self.probation.move_to_end(key)\n'),
    'wtlfu_always_admit': ('        if self.sketch.estimate(candidate) > self.sketch.estimate(victim):',
                           '        if True:'),
    'arc_p_wrong_sign': ('self.p = min(c, self.p + max(len(self.b2) / len(self.b1), 1))',
                         'self.p = max(0, self.p - max(len(self.b2) / len(self.b1), 1))'),
    'arc_ghost_to_t1': ('            del self.b1[key]\n            self.t2[key] = 1',
                        '            del self.b1[key]\n            self.t1[key] = 1'),
    'arc_no_b2_trim': ('                if total >= 2 * c:\n                    self.b2.popitem(last=False)\n',
                       '                pass\n'),
    'arc_t1_hit_stays': ('            del self.t1[key]\n            self.t2[key] = 1\n            self.hits += 1',
                         '            self.t1.move_to_end(key)\n            self.hits += 1'),
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
            with open(os.path.join(d, 'trace_sim', 'run_trace_sim.py'), 'w') as f:
                f.write(src.replace(old, new))
            r = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                               cwd=d, capture_output=True, text=True, timeout=900)
        last = next((l for l in reversed(r.stderr.splitlines())
                     if l.startswith(('OK', 'FAILED'))), '?')
        caught = r.returncode != 0
        missed += not caught
        print(f"{name:22s} {'CAUGHT' if caught else 'MISSED'}  ({last})", flush=True)
    print(f"\n{len(MUTANTS) - missed}/{len(MUTANTS)} mutants caught")
    return 1 if missed else 0


if __name__ == '__main__':
    sys.exit(main())
