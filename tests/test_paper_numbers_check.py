"""tools/paper_numbers_check.py must reject the old paper's unsupported figures and accept TABLES.md values at the
displayed rounding. Run: python3 -I tests/test_paper_numbers_check.py (from the repository root)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL, TABLES = ROOT / 'tools/paper_numbers_check.py', ROOT / 'results/P7/TABLES.md'
# old-paper figures marked CONTRADICTED or UNSUPPORTED in results/P7/CLAIMS.md
PLANTED = ['83.74', '5.15', '6,791', '2.45', '1,070', '935', '160,000', '4,048', '2,730', '1.22',
           '3.00', '0.61', '6.88', '14.88', '5.23', '6.27', '9.65', '0.85', '0.2359']
# Old figures that also occur in TABLES.md as genuine, unrelated values: a value-only check cannot reject them, so
# test_paper_text_has_no_old_figures checks that the paper does not contain them at all.
COLLIDING = {'65': 'TABLES.md: 65 lines at counter maximum (counter saturation, depth 256 mode 0); old: -65 ps slack',
             '0.0049': 'TABLES.md: +0.0049 ns WNS change (multicycle cross-check, depth 256 mode 0); old: 0.0049% of HBM TDP'}


def run(text):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / 't.tex').write_text(text)
        p = subprocess.run([sys.executable, '-I', str(TOOL), d, str(TABLES)], capture_output=True, text=True)
        return p.returncode, p.stdout


class PaperNumbersCheck(unittest.TestCase):
    def test_each_planted_old_figure_fails(self):
        passed = [v for v in PLANTED if run(f'The old paper said {v} here.\n')[0] == 0]
        print('planted figures the checker would accept:', passed or 'none')
        self.assertEqual(passed, [], 'checker accepted old figures; see CLAIMS.md before relaxing this list')

    def test_planted_old_figures_fail_even_as_rounded(self):
        for v in PLANTED:
            self.assertEqual(run(f'\\rnd{{{v}}}{{{v}}} here.\n')[0], 1, v)

    def test_exact_and_rounded_tables_values_pass(self):
        for t in ('636.1', '71.8034', '45,840,617', '\\rnd{636}{636.1}', '\\rnd{71.8}{71.8034}', '\\rnd{26744}{26744.438}'):
            self.assertEqual(run(f'Value {t}.\n')[0], 0, t)

    def test_plain_rounded_and_wrong_rounding_fail(self):
        for t in ('636', '71.8', '26744', '\\rnd{637}{636.1}', '\\rnd{71.9}{71.8034}', '\\rnd{71.81}{71.8034}',
                  '\\rnd{636}{636.2}'):
            self.assertEqual(run(f'Value {t}.\n')[0], 1, t)

    def test_older_evidence_section_not_usable(self):
        for v in ('83.75', '2.56', '5.15', '3.00'):                  # in TABLES.md only under "## Older evidence"
            self.assertEqual(run(f'Value {v}.\n')[0], 1, v)

    def test_comments_and_lengths_ignored(self):
        self.assertEqual(run('% 99999.123 in a comment\n\\includegraphics[width=0.93\\columnwidth]{x}\n')[0], 0)

    DOCS = [ROOT / 'paper/v2/main.tex'] + sorted((ROOT / 'docs/synthesis_report').glob('*.tex'))

    def test_paper_text_has_no_old_figures(self):
        import re
        for f in self.DOCS:
            tex = re.sub(r'(?<!\\)%.*', '', f.read_text())
            found = [v for v in PLANTED + list(COLLIDING)
                     if re.search(r'(?<![\w.,])' + re.escape(v) + r'(?!\d|[.,]\d)', tex)]
            self.assertEqual(found, [], f'old (contradicted or unsupported) figures in {f.relative_to(ROOT)}')

    def test_no_pre_rewrite_commit_ids(self):
        import re
        cmap = (ROOT / 'results/COMMIT_MAP.md').read_text()
        old = {o for o, n in re.findall(r'^\| ([0-9a-f]{7}) \| ([0-9a-f]{7})', cmap, re.M) if o != n}
        self.assertTrue(len(old) > 50, 'COMMIT_MAP.md not parsed')
        for f in self.DOCS:
            ids = set(re.findall(r'(?<![0-9a-f])[0-9a-f]{7}(?![0-9a-f])', f.read_text()))
            self.assertEqual(sorted(ids & old), [], f'pre-rewrite commit IDs in {f.relative_to(ROOT)}')

    def test_report_numbers_pass(self):
        rep = ROOT / 'docs/synthesis_report'
        if list(rep.glob('*.tex')):
            p = subprocess.run([sys.executable, '-I', str(TOOL), str(rep), str(TABLES)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:])


if __name__ == '__main__':
    unittest.main()
