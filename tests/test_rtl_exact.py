"""
Tests for trace_sim/rtl_exact.py (P9: RTL-exact policy, LFU-reset ablations, candidate tie-break rules).

Runs with:  python3 -m unittest discover -s tests -v
Synthetic data only. The RTL itself is checked against these models in tools/p9_validate.py.
"""
import os
import random
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'trace_sim'))

import rtl_exact as rx                          # noqa: E402
import run_shared_cache as sc                   # noqa: E402
import run_trace_sim as ts                      # noqa: E402

A, B, C, D, E, F, G, X, Y, Z = range(10)


def run(cache, keys):
    return [cache.access(k) for k in keys]


def zipf_trace(seed, n, n_keys, alpha=0.9):
    rng = random.Random(seed)
    w = [1 / (r ** alpha) for r in range(1, n_keys + 1)]
    return rng.choices(range(n_keys), weights=w, k=n)


def reference_slot_policy(keys, cap, mode, rule='none', cmax=63):
    """Independent O(N) reference written from the rule descriptions: eff = 0 (invalid) or count + 1;
    victim among the minimum eff by rule: 'none' lowest slot; 'victim' / 'step' first slot at or after
    ptr (wrapping), ptr = victim + 1 / ptr + 1; 'young' lowest slot without the young bit, else the
    lowest slot and all young bits cleared."""
    tag, cnt, valid, young, ptr, out = [None] * cap, [0] * cap, [False] * cap, [0] * cap, 0, []
    where = {}                                     # tag -> slot, for speed only
    for k in keys:
        s = where.get(k)
        if s is not None:
            cnt[s] = min(cnt[s] + 1, cmax)
            out.append(True)
            continue
        eff = [cnt[i] + 1 if valid[i] else 0 for i in range(cap)]
        cands = [i for i in range(cap) if eff[i] == min(eff)]
        if rule == 'young':
            old = [i for i in cands if not young[i]]
            v = old[0] if old else cands[0]
            if not old:
                young = [0] * cap
        else:
            ahead = [i for i in cands if i >= ptr]
            v = ahead[0] if ahead else cands[0]
            if rule == 'victim':
                ptr = (v + 1) % cap
            elif rule == 'step':
                ptr = (ptr + 1) % cap
        where.pop(tag[v], None)
        tag[v], valid[v], young[v], where[k] = k, True, 1, v
        cnt[v] = 1 if mode == 0 else min(cnt[v] + 1, cmax)
        out.append(False)
    return out


class SeqCase(unittest.TestCase):
    def assertSeq(self, got, want, msg=None):
        """Hit/miss sequences: report the first differing request (assertEqual's list diff is quadratic)."""
        if got != want:
            i = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
            self.fail(f"{msg}: sequences differ at request {i} (lengths {len(got)}, {len(want)})")


RANDOM_CASES = [(seed, cap, n_keys) for seed, (cap, n_keys) in enumerate(
    [(16, 8), (16, 40), (16, 300), (32, 100), (64, 50), (64, 700), (256, 2000)])]


class TestRTLRules(SeqCase):
    """Hand-computed sequences, each run on the structural model and the fast model."""

    def both(self, cap, mode):
        return (rx.RTLStructuralModel(cap, mode, groups=2), rx.RTLExactCache(cap, mode))

    def test_lowest_slot_tie_break(self):
        # A->0, B->1 (count 1 each); C evicts slot 0 (A); A evicts slot 0 (C); B still resident.
        for c in self.both(2, 0):
            self.assertSeq(run(c, [A, B, C, A, B]), [False, False, False, False, True])
        self.assertSeq(run(ts.LFUResetCache(2), [A, B, C, A, B]), [False] * 5)   # oldest: B evicted

    def test_invalid_slots_fill_first_lowest_index(self):
        for c in self.both(4, 0):
            run(c, [A, A, A, B, C, D])
            self.assertEqual(c.tag, [A, B, C, D])
            self.assertSeq(run(c, [A, B, C, D]), [True] * 4)

    def test_count_saturates_at_63(self):
        # X: 70 accesses, Y: 63. 6-bit: both 63, tie -> slot 0 (X) evicted by Z. 255: Y evicted.
        seq = [X] * 70 + [Y] * 63 + [Z, X]
        for c in self.both(2, 0):
            self.assertFalse(run(c, seq)[-1])
            self.assertEqual(c.misses, 4)
        self.assertTrue(run(ts.LFUResetCache(2), seq)[-1])
        self.assertTrue(run(rx.LFUResetLowestSlot(2), seq)[-1])
        self.assertFalse(run(rx.LFUReset6bit(2), seq)[-1])

    def test_count_never_exceeds_63(self):
        for mode in (0, 1):
            for c in self.both(2, mode):
                run(c, [X] * 200)
                self.assertEqual(c.cnt[0], 63)

    def test_mode1_continues_from_slot_count(self):
        seq = [A, A, A, B, C, A, D, E, F, A]
        # mode 0: B, C, D, E, F each start at 1 in slot 1; A (count 4) stays.
        # mode 1: slot 1 counts 1 (B), 2 (C), 3 (D), 4 (E); A 4 -> tie, F evicts slot 0 (A).
        for c in self.both(2, 0):
            self.assertSeq(run(c, seq), [False, True, True, False, False, True, False, False, False, True])
        for c in self.both(2, 1):
            self.assertSeq(run(c, seq), [False, True, True, False, False, True, False, False, False, False])
            self.assertEqual(c.cnt, [5, 5])

    def test_mode1_install_saturates(self):
        for c in self.both(2, 1):
            run(c, [X] * 100 + [Y, A] + [Y] * 70 + [B])
            # X 63 (slot 0), Y 63 (slot 1); B ties, replaces slot 0 and keeps 63 (no wrap to 0)
            self.assertEqual(c.tag, [B, Y])
            self.assertEqual(c.cnt, [63, 63])

    def test_structural_rejects_non_rtl_configurations(self):
        for cap, groups, mode in ((1000, 16, 0), (48, 16, 0), (16, 3, 0), (16, 16, 2)):
            with self.assertRaises(ValueError):
                rx.RTLStructuralModel(cap, mode, groups)
        with self.assertRaises(ValueError):
            rx.RTLExactCache(16, 2)

    def test_structural_tree_keeps_lowest_index_across_groups(self):
        # 8 slots, 4 groups of 2: fill, then raise slots 0..4 so that slots 5..7 are the minimum;
        # a new key must replace slot 5 (lowest in group 2), then slot 5 again.
        for c in (rx.RTLStructuralModel(8, 0, groups=4), rx.RTLExactCache(8, 0)):
            run(c, list(range(8)) + [0, 1, 2, 3, 4])
            run(c, [100])
            self.assertEqual(c.tag[5], 100)
            run(c, [101])
            self.assertEqual(c.tag[5], 101)
            self.assertEqual(c.tag[6:], [6, 7])


class TestEquivalences(SeqCase):
    def test_fast_equals_structural_request_by_request(self):
        for seed, cap, n_keys in RANDOM_CASES:
            keys = zipf_trace(seed, 5000, n_keys)
            for mode in (0, 1):
                ref = run(rx.RTLStructuralModel(cap, mode), keys)
                self.assertSeq(run(rx.RTLExactCache(cap, mode), keys), ref, (cap, n_keys, mode))
                self.assertSeq(ref, reference_slot_policy(keys, cap, mode), (cap, n_keys, mode))

    def test_named_classes(self):
        keys = zipf_trace(1, 4000, 200)
        self.assertSeq(run(rx.RTLExactMode0(32), keys), run(rx.RTLExactCache(32, 0), keys))
        self.assertSeq(run(rx.RTLExactMode1(32), keys), run(rx.RTLExactCache(32, 1), keys))
        self.assertNotEqual(run(rx.RTLExactMode0(32), keys), run(rx.RTLExactMode1(32), keys))

    def test_both_ablations_equal_rtl_exact_mode0(self):
        for seed, cap, n_keys in RANDOM_CASES + [(9, 1000, 5000)]:
            keys = zipf_trace(seed, 8000, n_keys, alpha=1.1)
            self.assertSeq(run(rx.LFUResetLowestSlot6bit(cap), keys), run(rx.RTLExactMode0(cap), keys), cap)

    def test_oldest_255_variant_equals_lfu_reset(self):
        for seed, cap, n_keys in RANDOM_CASES + [(9, 1000, 5000)]:
            keys = zipf_trace(seed, 8000, n_keys, alpha=1.1)
            self.assertSeq(run(rx.LFUResetVariant(cap, 'oldest', 255), keys),
                             run(ts.LFUResetCache(cap), keys), cap)

    def test_single_rule_variants_against_reference(self):
        # lowest-slot only = slot rule with 255; 6-bit only = LFU-reset with 63.
        for seed, cap, n_keys in RANDOM_CASES[:5]:
            keys = zipf_trace(seed, 6000, n_keys, alpha=1.2)
            self.assertSeq(run(rx.LFUResetLowestSlot(cap), keys),
                             reference_slot_policy(keys, cap, 0, cmax=255), cap)
            self.assertSeq(run(rx.LFUReset6bit(cap), keys), run(rx.LFUResetVariant(cap, 'oldest', 63), keys))

    def test_saturation_matters_on_heavy_keys(self):
        # Bursts of 1..150 repeats of one of 3 keys, 2 lines: a new line can pass 63 before the next
        # miss, so every resident line can be saturated and the 63 limit changes victims.
        rng = random.Random(0)
        keys = []
        for _ in range(400):
            keys += [rng.randrange(3)] * rng.randint(1, 150)
        self.assertNotEqual(run(rx.LFUResetLowestSlot(2), keys), run(rx.LFUResetLowestSlot6bit(2), keys))
        self.assertNotEqual(run(ts.LFUResetCache(2), keys), run(rx.LFUReset6bit(2), keys))
        self.assertSeq(run(rx.LFUResetLowestSlot6bit(2), keys), reference_slot_policy(keys, 2, 0))

    def test_heap_rebuild_keeps_results(self):
        # Hot keys climb to 63, are evicted and restart at 1: stale high-count entries pile up and the
        # heaps are rebuilt (counted for RTLExactCache); results must still equal the reference.
        rebuilds = []

        class Counting(rx.RTLExactCache):
            def _rebuild(self):
                rebuilds.append(1)
                super()._rebuild()

        # 256 lines, each hit 49 times with no miss in between: over 4 x 256 + 10000 heap entries.
        keys = [i for _ in range(50) for i in range(256)] + zipf_trace(5, 15000, 600)
        self.assertSeq(run(Counting(256, 0), keys), reference_slot_policy(keys, 256, 0))
        self.assertTrue(rebuilds)
        self.assertSeq(run(rx.LFUResetLowestSlot(256), keys), reference_slot_policy(keys, 256, 0, cmax=255))
        self.assertSeq(run(rx.RotatingTieCache(256, 0, 'victim'), keys),
                         reference_slot_policy(keys, 256, 0, 'victim'))
        self.assertSeq(run(rx.YoungBitCache(256, 1), keys), reference_slot_policy(keys, 256, 1, 'young'))


class TestCandidates(SeqCase):
    def test_rotate_none_equals_rtl(self):
        for seed, cap, n_keys in RANDOM_CASES:
            keys = zipf_trace(seed, 5000, n_keys)
            for mode in (0, 1):
                self.assertSeq(run(rx.RotatingTieCache(cap, mode, 'none'), keys),
                                 run(rx.RTLExactCache(cap, mode), keys), (cap, mode))

    def test_candidates_match_reference(self):
        for seed, cap, n_keys in RANDOM_CASES:
            keys = zipf_trace(seed, 5000, n_keys)
            for mode in (0, 1):
                for rule in ('victim', 'step'):
                    self.assertSeq(run(rx.RotatingTieCache(cap, mode, rule), keys),
                                     reference_slot_policy(keys, cap, mode, rule), (cap, mode, rule))
                self.assertSeq(run(rx.YoungBitCache(cap, mode), keys),
                                 reference_slot_policy(keys, cap, mode, 'young'), (cap, mode))

    def test_rotate_victim_hand_trace(self):
        # A B C fill slots 0..2; D evicts slot 0 (A); E evicts slot 1 (B) -> D still resident.
        self.assertSeq(run(rx.RotatingTieCache(3, 0, 'victim'), [A, B, C, D, E, D])[-1], True)
        self.assertSeq(run(rx.RTLExactCache(3, 0), [A, B, C, D, E, D])[-1], False)

    def test_rotate_step_differs_from_victim(self):
        seq = [A, B, C, D, A, E, F, E]
        # victim: E -> slot 1, ptr 2; F -> slot 2; E hits. step: ptr 1 after E; F -> slot 1 (E).
        self.assertTrue(run(rx.RotatingTieCache(4, 0, 'victim'), seq)[-1])
        self.assertFalse(run(rx.RotatingTieCache(4, 0, 'step'), seq)[-1])

    def test_young_bit_hand_trace(self):
        # A B C young; D: all young -> clear, slot 0; E: B (old) evicted, not D.
        c = rx.YoungBitCache(3, 0)
        self.assertSeq(run(c, [A, B, C, D, E, D]), [False] * 5 + [True])
        self.assertEqual(c.tag, [D, E, C])
        self.assertSeq(run(c, [F]), [False])          # C (old) evicted
        self.assertEqual(c.tag, [D, E, F])
        self.assertSeq(run(c, [G]), [False])          # D has count 2; E, F young: clear, slot 1
        self.assertEqual(c.tag, [D, G, F])

    def test_candidate_names_and_modes(self):
        names = [p.name for p in rx.CANDIDATES]
        self.assertEqual(names, ['Rotate-victim mode 0', 'Rotate-victim mode 1', 'Rotate-step mode 0',
                                 'Rotate-step mode 1', 'Young-bit mode 0', 'Young-bit mode 1'])
        keys = zipf_trace(2, 5000, 300)
        self.assertSeq(run(rx.CANDIDATES[1](32), keys), run(rx.RotatingTieCache(32, 1, 'victim'), keys))
        self.assertSeq(run(rx.CANDIDATES[2](32), keys), run(rx.RotatingTieCache(32, 0, 'step'), keys))
        self.assertSeq(run(rx.CANDIDATES[5](32), keys), run(rx.YoungBitCache(32, 1), keys))


class TestGeneral(SeqCase):
    def test_capacity_counts_and_compulsory_misses(self):
        keys = zipf_trace(6, 5000, 400)
        for p in rx.P9_POLICIES:
            for cap in (1, 7, 64):
                c = p(cap)
                out = run(c, keys)
                self.assertEqual(c.hits, sum(out), p.name)
                self.assertEqual(c.hits + c.misses, len(keys))
                self.assertLessEqual(len(c.slot_of if hasattr(c, 'slot_of') else c.cache), cap)
            c = p(len(set(keys)) + 5)
            run(c, keys)
            self.assertEqual(c.misses, len(set(keys)), p.name)

    def test_policy_names_unique_and_registered(self):
        names = [p.name for p in rx.P9_POLICIES]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names[:5], ['RTL-exact mode 0', 'RTL-exact mode 1', 'LFU-reset lowest-slot',
                                     'LFU-reset 6-bit', 'LFU-reset lowest-slot 6-bit'])
        self.assertEqual(names[5:], [p.name for p in rx.CANDIDATES])
        self.assertEqual(len(names), 11)
        self.assertEqual(sc.POLICIES, [ts.LRUCache, ts.LFUResetCache, ts.LFUCache, ts.ARCCache,
                                       ts.WTinyLFUCache])
        self.assertEqual(sc.SELECTABLE, sc.POLICIES + rx.P9_POLICIES)

    def test_shared_runner_parallel_equals_serial(self):
        keys = zipf_trace(7, 6000, 500)
        per = [len(keys)] + [0] * 25
        a = sc.run_shared(keys, per, [16, 64], 1, rx.P9_POLICIES)
        with tempfile.TemporaryDirectory() as d:
            b = sc.run_shared(keys, per, [16, 64], 3, rx.P9_POLICIES, part_dir=d)
            self.assertEqual(len(os.listdir(d)), 2 * len(rx.P9_POLICIES))
        for cap in (16, 64):
            for p in rx.P9_POLICIES:
                c = p(cap)
                run(c, keys)
                self.assertEqual((a[cap][p.name]['hits'], b[cap][p.name]['hits']), (c.hits, c.hits))


if __name__ == '__main__':
    unittest.main()
