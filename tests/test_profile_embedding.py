"""
CPU tests for tools/profile_embedding.py at tiny sizes (skipped without torch).

Runs with:  python3 -m unittest tests.test_profile_embedding -v
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

try:
    import torch
    import profile_embedding as pe
except ImportError:          # the trace-sim venv has no torch
    torch = None


@unittest.skipIf(torch is None, 'torch not installed')
class TestIndices(unittest.TestCase):
    def test_uniform_in_range(self):
        idx, wrapped = pe.make_indices('uniform', 1000, 3, 4, 50, seed=1)
        self.assertEqual(tuple(idx.shape), (3, 4, 50))
        self.assertTrue(0 <= idx.min() and idx.max() < 1000)
        self.assertFalse(wrapped)

    def test_zipf_rank_distribution(self):
        gen = torch.Generator().manual_seed(0)
        for alpha in (0.6, 0.85, 1.1):
            r = pe.zipf_ranks(2_000_000, 10_000, alpha, gen)
            self.assertTrue(1 <= r.min() and r.max() <= 10_000)
            counts = torch.bincount(r, minlength=10_001)[1:].double()
            ranks = torch.arange(1, 10_001, dtype=torch.float64)
            sel = slice(9, 1000)     # skip the first ranks (floor of a continuous CDF)
            slope = np.polyfit(np.log(ranks[sel].numpy()), np.log(counts[sel].numpy()), 1)[0]
            self.assertAlmostEqual(-slope, alpha, delta=0.1, msg=f'alpha {alpha}')

    def test_zipf_id_map_is_bijection(self):
        for rows in (1000, 10_000):
            r = torch.arange(1, rows + 1)
            ids = ((r - 1) * pe.ZIPF_MULT + pe.ZIPF_TABLE_SHIFT * 3) % rows
            self.assertEqual(len(torch.unique(ids)), rows)

    def test_zipf_tables_differ_and_in_range(self):
        idx, _ = pe.make_indices('zipf1.1', 5000, 2, 3, 400, seed=2)
        self.assertTrue(0 <= idx.min() and idx.max() < 5000)
        self.assertNotEqual(torch.mode(idx[:, 0].flatten()).values.item(),
                            torch.mode(idx[:, 1].flatten()).values.item())

    def test_criteo_order_modulo_and_wrap(self):
        with tempfile.TemporaryDirectory() as d:
            for t in range(2):
                np.arange(100 * t, 100 * t + 30, dtype=np.uint32).tofile(
                    os.path.join(d, f'table_{t:02d}.u32'))
            idx, wrapped = pe.make_indices('criteo', 7, 2, 2, 5, seed=0, criteo_dir=d)
            self.assertFalse(wrapped)
            self.assertEqual(idx[1, 1].tolist(), [(100 + 5 + i) % 7 for i in range(5)])
            idx, wrapped = pe.make_indices('criteo', 1000, 4, 2, 10, seed=0, criteo_dir=d)
            self.assertTrue(wrapped)
            self.assertEqual(idx[3, 0].tolist(), list(range(0, 10)))


@unittest.skipIf(torch is None, 'torch not installed')
class TestModel(unittest.TestCase):
    def test_embed_equals_manual_pooled_sum(self):
        torch.manual_seed(0)
        m = pe.Model(3, 50, 4, torch.device('cpu'))
        idx = torch.randint(50, (3, 6))
        offsets = torch.arange(0, 6, 2)          # batch 3, pooling 2
        out = m.embed(idx, offsets)
        self.assertEqual(tuple(out.shape), (3, 12))
        for t in range(3):
            w = m.embs[t].weight
            for s in range(3):
                expect = w[idx[t, 2 * s]] + w[idx[t, 2 * s + 1]]
                self.assertTrue(torch.allclose(out[s, 4 * t:4 * t + 4], expect))
        self.assertEqual(tuple(m.mlp(out).shape), (3, 1))

    def test_run_config_counts(self):
        m = pe.Model(2, 20, 4, torch.device('cpu')).eval()
        idx, _ = pe.make_indices('uniform', 20, 5, 2, 8, seed=0)
        emb, mlp, wall = pe.run_config(m, idx, torch.arange(8), 2, 3, torch.device('cpu'))
        self.assertEqual((len(emb), len(mlp)), (3, 3))
        self.assertTrue(all(x > 0 for x in emb + mlp) and wall > 0)


@unittest.skipIf(torch is None, 'torch not installed')
class TestEndToEnd(unittest.TestCase):
    def test_cli_tiny_cpu_all_patterns(self):
        with tempfile.TemporaryDirectory() as d:
            tr = os.path.join(d, 'tr')
            os.makedirs(tr)
            for t in range(3):
                np.random.default_rng(t).integers(0, 2**32, 500, dtype=np.uint32).tofile(
                    os.path.join(tr, f'table_{t:02d}.u32'))
            out = os.path.join(d, 'out')
            r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'tools', 'profile_embedding.py'),
                                '--device', 'cpu', '--out', out, '--rows', '1000', '5000',
                                '--dims', '8', '16', '--batches', '4', '16', '--tables', '3',
                                '--warmup', '2', '--iters', '3', '--criteo_dir', tr],
                               capture_output=True, text=True, timeout=600)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            with open(os.path.join(out, 'results.csv'), newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2 * 2 * 5 * 2)
            self.assertEqual({x['status'] for x in rows}, {'ok'})
            self.assertEqual({x['pattern'] for x in rows}, set(pe.PATTERNS))
            for x in rows:
                self.assertEqual(x['timer'], 'perf_counter')
                self.assertGreater(float(x['emb_ms_median']), 0)
                self.assertTrue(0 < float(x['emb_share_median']) < 1)
                self.assertEqual(int(x['emb_lookup_bytes']), 3 * int(x['batch']) * int(x['dim']) * 4)
            with open(os.path.join(out, 'env.json')) as f:
                env = json.load(f)
            self.assertEqual(env['env']['torch'], torch.__version__)
            self.assertEqual(env['args']['iters'], 3)

    def test_criteo_requires_dir(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'tools', 'profile_embedding.py'),
                                '--device', 'cpu', '--out', d, '--patterns', 'criteo'],
                               capture_output=True, text=True, timeout=120)
            self.assertNotEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main()
