#!/usr/bin/env python3
"""
Mutation check for tests/test_rtl_exact.py: each mutant is a deliberately
broken copy of trace_sim/rtl_exact.py, and the test suite must FAIL on it.

Usage (from the repo root):  python3 tools/mutate_rtl_exact.py
Exit code 0 only if every mutant is caught.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'trace_sim', 'rtl_exact.py')

MUTANTS = {
    'fast_fill_highest_invalid': ('            s = self.n_valid                       # lowest invalid slot (eff 0)',
                                  '            s = self.cap - 1 - self.n_valid'),
    'fast_hit_no_saturation': ('            c = self.cnt[s]\n            if c != self.cmax:',
                               '            c = self.cnt[s]\n            if True:'),
    'fast_stale_entries_used': ('            while cnt[heap[0][1]] != heap[0][0]:\n                heapq.heappop(heap)',
                                '            while False:\n                pass'),
    'fast_mode_ignored': ('        c = _install_count(self.mode, self.cnt[s], self.cmax)',
                          '        c = _install_count(0, self.cnt[s], self.cmax)'),
    'install_count_0': ('        return 1\n    return old + 1 if old != cmax else old',
                        '        return 0\n    return old + 1 if old != cmax else old'),
    'mode1_install_no_saturation': ('    return old + 1 if old != cmax else old', '    return old + 1'),
    'struct_tie_takes_right': ('            node[i] = rv if rv[0] < lv[0] else lv',
                               '            node[i] = rv if rv[0] <= lv[0] else lv'),
    'struct_hit_no_saturation': ('            if self.cnt[s] != self.cmax:\n                self.cnt[s] += 1\n            self.hits += 1',
                                 '            self.cnt[s] += 1\n            self.hits += 1'),
    'struct_mode_ignored': ('self.cnt[victim] = _install_count(self.mode, self.cnt[victim], self.cmax)',
                            'self.cnt[victim] = _install_count(0, self.cnt[victim], self.cmax)'),
    'variant_tie_always_oldest': ("        t = slot if self.tie == 'slot' else self.seq", '        t = self.seq'),
    'variant_cmax_ignored': ('            if f < self.cmax:', '            if f < 255:'),
    'variant_victim_slot_not_reused': ('            slot = t\n', '            slot = len(self.cache)\n'),
    'rotate_no_rekey': ('            elif a < self.P:', '            elif False:'),
    'rotate_victim_ptr_off_by_one': ('            self.P = a + 1', '            self.P = a'),
    'rotate_step_by_two': ('            self.P += 1', '            self.P += 2'),
    'young_never_cleared': ('        if y:\n            for t in self.young_list:', '        if False:\n            for t in self.young_list:'),
    'young_not_set': ('        self.young[s] = 1', '        self.young[s] = 0'),
    'candidate_mode_swapped': ('f"Rotate-victim mode {m}", mode=m,', 'f"Rotate-victim mode {m}", mode=0,'),
    'candidates_not_registered': ('P9_POLICIES = RTL_EXACT + ABLATIONS + CANDIDATES', 'P9_POLICIES = RTL_EXACT + ABLATIONS'),
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
            with open(os.path.join(d, 'trace_sim', 'rtl_exact.py'), 'w') as f:
                f.write(src.replace(old, new))
            try:
                r = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                    '-p', 'test_rtl_exact.py'],
                                   cwd=d, capture_output=True, text=True, timeout=300)
            except subprocess.TimeoutExpired:
                r = None                    # a hang is not a detection
        last = '300 s timeout' if r is None else next((l for l in reversed(r.stderr.splitlines())
                                                      if l.startswith(('OK', 'FAILED'))), '?')
        caught = r is not None and r.returncode != 0
        missed += not caught
        print(f"{name:32s} {'CAUGHT' if caught else 'MISSED'}  ({last})", flush=True)
    print(f"\n{len(MUTANTS) - missed}/{len(MUTANTS)} mutants caught")
    return 1 if missed else 0


if __name__ == '__main__':
    sys.exit(main())
