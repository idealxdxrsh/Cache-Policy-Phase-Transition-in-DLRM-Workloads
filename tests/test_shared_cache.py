"""
Tests for trace_sim/run_shared_cache.py (one cache over all tables).

Runs with:  python3 -m unittest discover -s tests -v
"""
import os
import random
import sys
import tempfile
import unittest
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'trace_sim'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import run_shared_cache as sc                   # noqa: E402
import run_trace_sim as ts                      # noqa: E402
import gen_synthetic_criteo as gen              # noqa: E402


def write_rows(path, rows):
    """rows: list of {table: id_int}; tables not given are empty fields."""
    with open(path, 'w') as f:
        for r in rows:
            cats = [f'{r[t]:08x}' if t in r else '' for t in range(26)]
            f.write('\t'.join(['0'] + ['1'] * 13 + cats) + '\n')


def parse_direct(path, n_rows=None):
    """Independent reference: (table, id) tuples in row order, tables 0..25."""
    out = []
    with open(path) as f:
        for i, line in enumerate(f):
            if n_rows is not None and i >= n_rows:
                break
            fields = line.rstrip('\n').split('\t')
            out += [(t, int(fields[14 + t], 16)) for t in range(26) if fields[14 + t]]
    return out


def reference_lru(seq, cap):
    """Plain LRU on (table, id) tuples; returns per-table hit counts."""
    cache, hits = OrderedDict(), [0] * 26
    for k in seq:
        if k in cache:
            cache.move_to_end(k)
            hits[k[0]] += 1
        else:
            if len(cache) >= cap:
                cache.popitem(last=False)
            cache[k] = 1
    return hits


class SyntheticCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.tmp.name, 'synth.txt')
        gen.generate(cls.path, rows=1500, seed=11)
        cls.ref = parse_direct(cls.path)
        cls.keys, cls.n, cls.per_table = sc.load_shared_trace(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class TestSharedLoader(SyntheticCase):
    def test_row_order_and_table_qualified_keys(self):
        self.assertEqual(self.n, 1500)
        self.assertEqual([(sc.key_table(k), k & 0xFFFFFFFF) for k in self.keys], self.ref)

    def test_per_table_counts_match_per_table_loader(self):
        traces, _ = ts.load_criteo_traces(self.path)
        self.assertEqual(self.per_table, [len(t) for t in traces])
        for t in range(26):
            self.assertEqual([k & 0xFFFFFFFF for k in self.keys if sc.key_table(k) == t], traces[t])

    def test_row_limit(self):
        keys, n, _ = sc.load_shared_trace(self.path, n_rows=200)
        self.assertEqual(n, 200)
        self.assertEqual(len(keys), len(parse_direct(self.path, 200)))

    def test_same_id_in_two_tables_is_two_keys(self):
        p = os.path.join(self.tmp.name, 'collide.txt')
        write_rows(p, [{0: 5, 1: 5}, {1: 5, 25: 5}])
        keys, _, per = sc.load_shared_trace(p)
        self.assertEqual(len(set(keys)), 3)
        self.assertEqual(per[0], 1)
        self.assertEqual(per[1], 2)
        self.assertEqual(per[25], 1)
        res = sc.run_shared(keys, per, [100], 1, [ts.LRUCache])[100]['LRU']
        self.assertEqual((res['hits'], res['misses']), (1, 3))
        self.assertEqual(res['per_table'][1]['hits'], 1)

    def test_order_within_row_is_table_0_to_25(self):
        p = os.path.join(self.tmp.name, 'order.txt')
        write_rows(p, [{25: 1, 3: 2, 0: 3}])
        keys, _, _ = sc.load_shared_trace(p)
        self.assertEqual([sc.key_table(k) for k in keys], [0, 3, 25])

    def test_empty_fields_skipped(self):
        p = os.path.join(self.tmp.name, 'empty.txt')
        write_rows(p, [{}, {7: 9}])
        keys, n, per = sc.load_shared_trace(p)
        self.assertEqual(n, 2)
        self.assertEqual(list(keys), [sc.make_key(7, 9)])
        self.assertEqual(sum(per), 1)

    def test_wide_id_rejected(self):
        p = os.path.join(self.tmp.name, 'wide.txt')
        with open(p, 'w') as f:
            f.write('\t'.join(['0'] + ['1'] * 13 + ['1ffffffff'] + [''] * 25) + '\n')
        with self.assertRaises(ValueError):
            sc.load_shared_trace(p)


class TestSharedSimulation(SyntheticCase):
    def test_lru_matches_reference_total_and_per_table(self):
        for cap in (1, 64, 256, 1000):
            res = sc.run_shared(self.keys, self.per_table, [cap], 1, [ts.LRUCache])[cap]['LRU']
            ref = reference_lru(self.ref, cap)
            self.assertEqual(res['hits'], sum(ref), cap)
            self.assertEqual([r['hits'] for r in res['per_table']], ref, cap)
            self.assertEqual(res['hits'] + res['misses'], len(self.ref))

    def test_huge_capacity_only_compulsory_misses(self):
        cap = len(set(self.ref)) + 10
        res = sc.run_shared(self.keys, self.per_table, [cap], 1)[cap]
        self.assertEqual(set(res), {p.name for p in sc.POLICIES})
        for name, r in res.items():
            self.assertEqual(r['misses'], len(set(self.ref)), name)

    def test_single_table_equals_per_table_simulator(self):
        # Table 0 keys equal raw ids (0 << 32 | id), so the shared run on a
        # table-0-only trace must match run_trace_sim exactly, policy by policy.
        trace = [i for t, i in self.ref if t == 0]
        keys = [k for k in self.keys if sc.key_table(k) == 0]
        per = [len(keys)] + [0] * 25
        for cap in (16, 128):
            res = sc.run_shared(keys, per, [cap], 1)[cap]
            for p in sc.POLICIES:
                c = p(cap)
                for k in trace:
                    c.access(k)
                self.assertEqual((res[p.name]['hits'], res[p.name]['misses']),
                                 (c.hits, c.misses), f'{p.name}@{cap}')

    def test_shared_differs_from_per_table_caches(self):
        # 26 private caches of 64 hold more than one shared 64-entry cache.
        cap = 64
        shared = sc.run_shared(self.keys, self.per_table, [cap], 1, [ts.LRUCache])[cap]['LRU']
        traces, _ = ts.load_criteo_traces(self.path)
        private = 0
        for tr in traces:
            c = ts.LRUCache(cap)
            for k in tr:
                c.access(k)
            private += c.hits
        self.assertLess(shared['hits'], private)

    def test_parallel_equals_serial(self):
        caps = [64, 512]
        a = sc.run_shared(self.keys, self.per_table, caps, 1)
        b = sc.run_shared(self.keys, self.per_table, caps, 3)
        for c in caps:
            for p in sc.POLICIES:
                for k in ('hits', 'misses', 'per_table'):
                    self.assertEqual(a[c][p.name][k], b[c][p.name][k], f'{p.name}@{c} {k}')

    def test_every_policy_and_capacity_present(self):
        res = sc.run_shared(self.keys, self.per_table, sc.DEFAULT_CAPACITIES[:2], 1)
        for c in sc.DEFAULT_CAPACITIES[:2]:
            self.assertEqual(sorted(res[c]), sorted(p.name for p in sc.POLICIES))
            for r in res[c].values():
                self.assertEqual(sum(t['hits'] for t in r['per_table']), r['hits'])
                self.assertEqual([t['hits'] + t['misses'] for t in r['per_table']], self.per_table)

    def test_policy_list_and_capacities_match_request(self):
        self.assertEqual(sorted(p.name for p in sc.POLICIES),
                         sorted(['LRU', ts.LFUResetCache.name, ts.LFUCache.name,
                                 'ARC', ts.WTinyLFUCache.name]))
        self.assertEqual(sc.DEFAULT_CAPACITIES, [256, 1000, 10000, 100000])

    def test_lfu_beats_lru_on_scan_mixed_shared_trace(self):
        # Sanity on a crafted trace: a hot set in table 0 plus a one-off scan in table 1.
        rng = random.Random(3)
        rows = []
        for i in range(3000):
            rows.append({0: rng.randrange(20), 1: 100000 + i})
        p = os.path.join(self.tmp.name, 'scan.txt')
        write_rows(p, rows)
        keys, _, per = sc.load_shared_trace(p)
        res = sc.run_shared(keys, per, [20], 1, [ts.LRUCache, ts.LFUCache])[20]
        self.assertGreater(res[ts.LFUCache.name]['hits'], res['LRU']['hits'])
        self.assertEqual(res['LRU']['per_table'][1]['hits'], 0)


if __name__ == '__main__':
    unittest.main()
