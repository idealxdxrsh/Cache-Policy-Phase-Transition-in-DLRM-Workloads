"""
Tests for trace_sim/run_trace_sim.py cache policies.

Runs with either:
    python3 -m unittest discover -s tests -v
    python3 -m pytest tests/        (if pytest is installed)
"""
import os
import random
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'trace_sim'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import run_trace_sim as ts                      # noqa: E402
import gen_synthetic_criteo as gen              # noqa: E402


def resident(cache):
    """Number of lines currently holding data (ghost entries excluded)."""
    if isinstance(cache, (ts.LRUCache, ts.LFUCache, ts.LFUResetCache, ts.BeladyCache)):
        return len(cache.cache)
    if isinstance(cache, ts.TinyLFUCache):
        return len(cache.window) + len(cache.main)
    return len(cache)


def zipf_trace(n, vocab, alpha=1.0, seed=1):
    rng = random.Random(seed)
    weights = [r ** -alpha for r in range(1, vocab + 1)]
    return rng.choices(range(vocab), weights=weights, k=n)


class ReferenceLFU:
    """O(n)-scan LFU used only to check the heap-based classes."""

    def __init__(self, capacity, keep_history):
        self.cap, self.keep = capacity, keep_history
        self.cache, self.freq, self.seq = {}, {}, 0
        self.hits = self.misses = 0

    def access(self, key):
        if key in self.cache:
            self.freq[key] = min(255, self.freq[key] + 1)
            self.hits += 1
            return True
        self.misses += 1
        if len(self.cache) >= self.cap:
            victim = min(self.cache, key=lambda k: (self.freq[k], self.cache[k]))
            del self.cache[victim]
            if not self.keep:
                del self.freq[victim]
        self.seq += 1
        self.cache[key] = self.seq
        self.freq[key] = min(255, self.freq.get(key, 0) + 1) if self.keep else 1
        return False


class TestAllPolicies(unittest.TestCase):
    """Properties every policy must satisfy."""

    def test_policy_set(self):
        names = [p.name for p in ts.POLICIES]
        self.assertEqual(len(names), len(set(names)))
        for cls in (ts.LRUCache, ts.LFUCache, ts.LFUResetCache,
                    ts.WTinyLFUCache, ts.ARCCache):
            self.assertIn(cls, ts.POLICIES)

    def test_default_capacities_match_plan(self):
        self.assertEqual(ts.DEFAULT_CAPACITIES,
                         [64, 128, 256, 512, 1000, 2000, 5000,
                          10000, 20000, 50000, 100000])

    def test_capacity_never_exceeded_and_counts_add_up(self):
        trace = zipf_trace(20000, 3000, alpha=0.9)
        for cls in ts.POLICIES:
            for cap in (1, 2, 7, 64, 256):
                with self.subTest(policy=cls.name, cap=cap):
                    c = cls(cap)
                    for k in trace:
                        c.access(k)
                        self.assertLessEqual(resident(c), cap)
                    self.assertEqual(c.hits + c.misses, len(trace))
                    self.assertEqual(c.dram_reads, c.misses)

    def test_return_value_is_hit(self):
        trace = zipf_trace(5000, 500)
        for cls in ts.POLICIES:
            with self.subTest(policy=cls.name):
                c = cls(32)
                hits = sum(c.access(k) for k in trace)
                self.assertEqual(hits, c.hits)

    def test_single_key(self):
        for cls in ts.POLICIES:
            with self.subTest(policy=cls.name):
                c = cls(64)
                for _ in range(100):
                    c.access(42)
                self.assertEqual((c.hits, c.misses), (99, 1))

    def test_unique_scan_never_hits(self):
        for cls in ts.POLICIES:
            with self.subTest(policy=cls.name):
                c = cls(64)
                for k in range(5000):
                    c.access(k)
                self.assertEqual(c.hits, 0)

    def test_working_set_that_fits(self):
        # 50 keys cycled through a 64-line cache: only cold misses.
        for cls in ts.POLICIES:
            with self.subTest(policy=cls.name):
                c = cls(64)
                for _ in range(20):
                    for k in range(50):
                        c.access(k)
                self.assertEqual(c.misses, 50)

    def test_deterministic(self):
        trace = zipf_trace(10000, 2000)
        for cls in ts.POLICIES:
            with self.subTest(policy=cls.name):
                a, b = cls(128), cls(128)
                for k in trace:
                    a.access(k)
                    b.access(k)
                self.assertEqual(a.hits, b.hits)

    def test_mostly_monotone_in_capacity_on_zipf(self):
        # Not a theorem for LFU/ARC/TinyLFU, but on a stationary Zipf trace
        # a 16x larger cache must not do worse.
        trace = zipf_trace(30000, 5000, alpha=1.0)
        for cls in ts.POLICIES:
            with self.subTest(policy=cls.name):
                small, big = cls(64), cls(1024)
                for k in trace:
                    small.access(k)
                    big.access(k)
                self.assertGreater(big.hits, small.hits)


class TestLRU(unittest.TestCase):
    def test_hand_trace(self):
        c = ts.LRUCache(2)
        got = [c.access(k) for k in 'abacbab']
        # a b a(hit) c(evict b) b(evict a) a(evict c) b(hit)
        self.assertEqual(got, [False, False, True, False, False, False, True])


class TestLFU(unittest.TestCase):
    def test_heap_lfu_matches_reference(self):
        trace = zipf_trace(20000, 1500, alpha=0.8, seed=3)
        for cls, keep in ((ts.LFUCache, True), (ts.LFUResetCache, False)):
            for cap in (1, 5, 64):
                with self.subTest(policy=cls.name, cap=cap):
                    fast, ref = cls(cap), ReferenceLFU(cap, keep)
                    for k in trace:
                        self.assertEqual(fast.access(k), ref.access(k))

    def test_history_vs_reset(self):
        # cap 2. a=2, b=3; c evicts a; c=3; a returns and evicts b (tie, older).
        # History LFU: a resumes at 3, so d evicts c (tie, older) and a stays.
        # Reset LFU: a restarts at 1, so d evicts a.
        seq = list('aabbbccca') + ['d']
        h, r = ts.LFUCache(2), ts.LFUResetCache(2)
        for k in seq:
            h.access(k)
            r.access(k)
        self.assertTrue(h.access('a'))
        self.assertFalse(r.access('a'))


class TestCountMinSketch(unittest.TestCase):
    def test_width_rounds_to_power_of_two(self):
        self.assertEqual(ts.CountMinSketch(1000, 10**9).width, 1024)
        self.assertEqual(ts.CountMinSketch(64, 10**9).width, 64)
        self.assertEqual(ts.CountMinSketch(3, 10**9).width, 16)

    def test_never_underestimates_before_aging(self):
        sk = ts.CountMinSketch(256, sample_size=10**9)
        trace = zipf_trace(3000, 2000, alpha=0.7)
        true = {}
        for k in trace:
            sk.increment(k)
            true[k] = true.get(k, 0) + 1
        for k, n in true.items():
            self.assertGreaterEqual(sk.estimate(k), min(n, 15))
            self.assertLessEqual(sk.estimate(k), 15)

    def test_saturates_at_15(self):
        sk = ts.CountMinSketch(64, sample_size=10**9)
        for _ in range(100):
            sk.increment(7)
        self.assertEqual(sk.estimate(7), 15)

    def test_aging_halves(self):
        sk = ts.CountMinSketch(64, sample_size=20)
        for _ in range(10):
            sk.increment(1)
        for k in range(100, 109):
            sk.increment(k)
        self.assertEqual(sk.estimate(1), 10)
        self.assertEqual(sk.additions, 19)
        sk.increment(200)                   # 20th increment triggers aging
        self.assertEqual(sk.additions, 10)
        self.assertEqual(sk.estimate(1), 5)

    def test_unseen_key_mostly_zero(self):
        sk = ts.CountMinSketch(1024, sample_size=10**9)
        for k in range(200):
            sk.increment(k)
        zeros = sum(sk.estimate(k) == 0 for k in range(10**6, 10**6 + 1000))
        self.assertGreater(zeros, 990)


class TestWTinyLFU(unittest.TestCase):
    def test_layout(self):
        c = ts.WTinyLFUCache(1000)
        self.assertEqual((c.win_cap, c.main_cap, c.prot_cap), (10, 990, 792))
        c = ts.WTinyLFUCache(64)
        self.assertEqual((c.win_cap, c.main_cap, c.prot_cap), (1, 63, 50))
        self.assertEqual(c.sketch.sample_size, 640)

    def test_scan_resistance(self):
        # 50 hot keys, each round followed by 200 one-time keys.
        trace, nxt = [], 10**6
        for _ in range(100):
            trace += list(range(50))
            trace += list(range(nxt, nxt + 200))
            nxt += 200
        hot = 50 * 100
        lru, tl = ts.LRUCache(100), ts.WTinyLFUCache(100)
        for k in trace:
            lru.access(k)
            tl.access(k)
        self.assertEqual(lru.hits, 0)
        self.assertGreater(tl.hits, 0.9 * hot)
        self.assertLessEqual(tl.hits, hot)

    def test_admission_rejects_colder_candidate(self):
        c = ts.WTinyLFUCache(4)             # window 1, main 3
        for k in (1, 2, 3, 4):
            for _ in range(5):
                c.access(k)
        main = set(c.probation) | set(c.protected)
        self.assertEqual(main, {1, 2, 3})
        c.access(99)                        # pushes 4 out of the window
        c.access(98)                        # 99 (count 1) must be rejected
        main_after = set(c.probation) | set(c.protected)
        self.assertNotIn(99, main_after)
        self.assertEqual(list(c.window), [98])

    def test_admission_tie_keeps_victim(self):
        c = ts.WTinyLFUCache(4)             # window 1, main 3
        for k in (1, 2, 3, 4):
            c.access(k)                     # 1,2,3 -> probation; 4 in window
        self.assertEqual(list(c.probation), [1, 2, 3])
        self.assertEqual([c.sketch.estimate(k) for k in (1, 4)], [1, 1])
        c.access(5)                         # candidate 4 ties victim 1: rejected
        self.assertEqual(list(c.probation), [1, 2, 3])
        self.assertEqual(list(c.window), [5])

    def test_slru_promotion_and_demotion(self):
        c = ts.WTinyLFUCache(10)            # window 1, main 9, protected 7
        for k in range(10):
            c.access(k)
        self.assertEqual(list(c.probation), list(range(9)))
        for k in range(9):
            self.assertTrue(c.access(k))    # probation hit -> protected
        self.assertEqual(list(c.protected), list(range(2, 9)))
        self.assertEqual(list(c.probation), [0, 1])  # demoted protected LRU


class TestARC(unittest.TestCase):
    def test_hand_trace(self):
        c = ts.ARCCache(2)
        got = [c.access(k) for k in 'abacb']
        self.assertEqual(got, [False, False, True, False, False])
        # after 'c': b went to B1; ghost hit on b raises p to 1, a goes to B2
        self.assertEqual((list(c.t1), list(c.t2)), (['c'], ['b']))
        self.assertEqual((list(c.b1), list(c.b2)), ([], ['a']))
        self.assertEqual(c.p, 1)
        self.assertFalse(c.access('a'))     # ghost hit in B2: p back to 0
        self.assertEqual(c.p, 0)
        self.assertEqual((list(c.t1), list(c.t2)), ([], ['b', 'a']))
        self.assertEqual(list(c.b1), ['c'])

    def test_invariants(self):
        trace = zipf_trace(30000, 4000, alpha=0.8, seed=5)
        trace += list(range(10**6, 10**6 + 3000)) + trace[:5000]
        for cap in (1, 3, 64, 500):
            with self.subTest(cap=cap):
                c = ts.ARCCache(cap)
                for k in trace:
                    c.access(k)
                    t1, t2, b1, b2 = len(c.t1), len(c.t2), len(c.b1), len(c.b2)
                    self.assertLessEqual(t1 + t2, cap)
                    self.assertLessEqual(t1 + b1, cap)
                    self.assertLessEqual(t1 + t2 + b1 + b2, 2 * cap)
                    self.assertTrue(0 <= c.p <= cap)
                    lists = [set(c.t1), set(c.t2), set(c.b1), set(c.b2)]
                    self.assertEqual(sum(map(len, lists)), len(set().union(*lists)))

    def test_scan_resistance(self):
        # Keys seen twice live in T2 and survive a long one-time scan.
        c = ts.ARCCache(100)
        for _ in range(3):
            for k in range(50):
                c.access(k)
        for k in range(10**6, 10**6 + 1000):
            c.access(k)
        before = c.hits
        for k in range(50):
            c.access(k)
        self.assertEqual(c.hits - before, 50)


class TestTraceLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.tmp.name, 'synth.txt')
        gen.generate(cls.path, rows=2000, seed=7)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_generator_layout(self):
        with open(self.path) as f:
            rows = [line.rstrip('\n').split('\t') for line in f]
        self.assertEqual(len(rows), 2000)
        for r in rows:
            self.assertEqual(len(r), 40)
            self.assertIn(r[0], ('0', '1'))
            for v in r[14:40]:
                if v:
                    self.assertEqual(len(v), 8)
                    int(v, 16)

    def test_loader_matches_direct_parse(self):
        traces, n = ts.load_criteo_traces(self.path)
        self.assertEqual(n, 2000)
        self.assertEqual(len(traces), 26)
        with open(self.path) as f:
            rows = [line.rstrip('\n').split('\t') for line in f]
        for t in range(26):
            expect = [int(r[14 + t], 16) for r in rows if r[14 + t]]
            self.assertEqual(traces[t], expect)

    def test_row_limit(self):
        traces, n = ts.load_criteo_traces(self.path, n_rows=300)
        self.assertEqual(n, 300)
        self.assertTrue(all(len(t) <= 300 for t in traces))

    def test_sweep_on_synthetic(self):
        traces, _ = ts.load_criteo_traces(self.path, n_rows=500)
        total = sum(len(t) for t in traces)
        caps = [64, 256]
        res, cpu = ts.run_sweep(traces, caps, workers=1)
        self.assertEqual(set(cpu), {p.name for p in ts.POLICIES})
        for cap in caps:
            self.assertEqual(set(res[cap]), {p.name for p in ts.POLICIES})
            for v in res[cap].values():
                self.assertEqual(v['hits'] + v['misses'], total)
                self.assertEqual([r['table'] for r in v['per_table']], list(range(26)))
                self.assertEqual(sum(r['hits'] for r in v['per_table']), v['hits'])
                for r, tr in zip(v['per_table'], traces):
                    self.assertEqual(r['hits'] + r['misses'], len(tr))

    def test_per_table_matches_single_table_run(self):
        traces, _ = ts.load_criteo_traces(self.path, n_rows=500)
        res, _ = ts.run_sweep(traces, [128], workers=1)
        for t in (0, 13, 25):
            c = ts.LRUCache(128)
            for k in traces[t]:
                c.access(k)
            self.assertEqual(res[128]['LRU']['per_table'][t]['hits'], c.hits)

    def test_parallel_equals_serial(self):
        traces, _ = ts.load_criteo_traces(self.path, n_rows=300)
        pols = ts.POLICIES + ts.OFFLINE_POLICIES
        a, _ = ts.run_sweep(traces, [64], 1, pols)
        b, _ = ts.run_sweep(traces, [64], 3, pols)
        self.assertEqual(a, b)

    def test_dump_and_reload(self):
        traces, n = ts.load_criteo_traces(self.path, n_rows=400)
        d = os.path.join(self.tmp.name, 'dump')
        ts.dump_traces(traces, n, d, self.path)
        back, meta = ts.load_dumped_traces(d, [0, 7, 25])
        self.assertEqual(back, [traces[0], traces[7], traces[25]])
        self.assertEqual(meta['n_rows'], 400)

    def test_cli_trace_dir_subset(self):
        import json
        import subprocess
        d = os.path.join(self.tmp.name, 'cli')
        script = os.path.join(ROOT, 'trace_sim', 'run_trace_sim.py')
        subprocess.run([sys.executable, script, '--criteo_path', self.path,
                        '--n_rows', '300', '--dump_traces', d],
                       check=True, capture_output=True)
        subprocess.run([sys.executable, script, '--trace_dir', d, '--tables', '3', '4',
                        '--capacities', '64', '--belady', '--output', d, '--tag', 'r'],
                       check=True, capture_output=True)
        with open(os.path.join(d, 'r.json')) as f:
            out = json.load(f)
        self.assertEqual(out['meta']['tables'], [3, 4])
        self.assertEqual([s['table'] for s in out['tables']], [3, 4])
        self.assertIn(ts.BeladyCache.name, out['results']['64'])
        self.assertEqual([r['table'] for r in out['results']['64']['LRU']['per_table']], [3, 4])

    def test_array_parts_merge_equals_single_run(self):
        import json
        import subprocess
        import merge_results
        d = os.path.join(self.tmp.name, 'arr')
        script = os.path.join(ROOT, 'trace_sim', 'run_trace_sim.py')
        run = lambda *a: subprocess.run([sys.executable, script, *a],
                                        check=True, capture_output=True)
        caps = ['64', '512']
        run('--criteo_path', self.path, '--n_rows', '400', '--dump_traces', d)
        run('--criteo_path', self.path, '--n_rows', '400', '--capacities', *caps,
            '--belady', '--output', d, '--tag', 'single')
        parts = []
        for group in (['0', '1', '2'], [str(t) for t in range(3, 26)]):
            tag = 'part_' + group[0]
            run('--trace_dir', d, '--tables', *group, '--capacities', *caps,
                '--belady', '--workers', '2', '--output', d, '--tag', tag)
            with open(os.path.join(d, tag + '.json')) as f:
                parts.append(json.load(f))
        merged = merge_results.merge(parts[::-1])
        with open(os.path.join(d, 'single.json')) as f:
            single = json.load(f)
        self.assertEqual(merged['results'], single['results'])
        self.assertEqual(merged['tables'], single['tables'])
        self.assertEqual(merged['meta']['tables'], list(range(26)))
        with self.assertRaises(ValueError):
            merge_results.merge([parts[0], parts[0]])


class TestBelady(unittest.TestCase):
    def test_hand_trace(self):
        # cap 2. At c, next uses are a@3, b@4: evict b. a hits. At b, c and a
        # are never used again: evict either. d misses.
        trace = list('abcabd')
        c = ts.BeladyCache(2)
        c.prepare(trace)
        got = [c.access(k) for k in trace]
        self.assertEqual(got, [False, False, False, True, False, False])

    def test_never_worse_than_online_policies(self):
        for seed in range(4):
            trace = zipf_trace(8000, 1500, alpha=0.7 + 0.1 * seed, seed=seed)
            for cap in (1, 8, 64, 300):
                opt = ts.BeladyCache(cap)
                opt.prepare(trace)
                for k in trace:
                    opt.access(k)
                for cls in ts.POLICIES:
                    with self.subTest(seed=seed, cap=cap, policy=cls.name):
                        c = cls(cap)
                        for k in trace:
                            c.access(k)
                        self.assertGreaterEqual(opt.hits, c.hits)

    def test_cyclic_scan(self):
        # Cycle of n+1 keys through n lines: LRU never hits, MIN misses
        # only about once per n accesses after warm-up.
        n, rounds = 10, 50
        trace = list(range(n + 1)) * rounds
        opt, lru = ts.BeladyCache(n), ts.LRUCache(n)
        opt.prepare(trace)
        for k in trace:
            opt.access(k)
            lru.access(k)
        self.assertEqual(lru.hits, 0)
        self.assertGreater(opt.hits, 0.85 * len(trace))


class TestZipfFit(unittest.TestCase):
    def test_recovers_alpha(self):
        for alpha in (0.6, 0.9, 1.2):
            with self.subTest(alpha=alpha):
                trace = zipf_trace(200000, 1000, alpha=alpha, seed=11)
                est, npts = ts.zipf_exponent(trace)
                self.assertGreaterEqual(npts, 100)
                self.assertAlmostEqual(est, alpha, delta=0.05)

    def test_too_few_points(self):
        self.assertEqual(ts.zipf_exponent(list(range(100))), (None, 0))

    def test_table_stats(self):
        s = ts.table_stats([[1, 1, 2], []], [4, 9])
        self.assertEqual(s[0]['column'], 18)
        self.assertEqual((s[0]['accesses'], s[0]['unique']), (3, 2))
        self.assertEqual((s[1]['table'], s[1]['accesses']), (9, 0))


if __name__ == '__main__':
    unittest.main()
