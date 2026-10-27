#!/usr/bin/env python3
"""
P9: slot-indexed LFU policies modelling rtl/v2/lfu_cache_controller.v (git tag rtl-v2-final), the
LFU-reset ablations between run_trace_sim.LFUResetCache and the RTL, and candidate hardware tie-break
rules (simulated only; none of them is in the RTL).

RTL rules modelled (read from rtl/v2/lfu_cache_controller.v):
  - Lines are slots 0..N-1. A request hits if a valid slot holds its tag; the hit slot's freq_cnt is
    incremented unless it is 63 (COUNTER_WIDTH = 6, saturating).
  - On a miss the victim is the slot with the smallest effective count eff = 0 for an invalid slot,
    freq_cnt + 1 for a valid one; on equal eff the lowest slot index wins (Stage A per-group trees and
    Stage B across groups both keep the lower index on ties, so the whole selection is the lowest index
    among the minimum). Invalid slots therefore fill first, lowest index first. There is no
    invalidation path (valid bits are cleared only at reset and for the victim in EVICT, which FILL sets
    again), so the invalid slots are always slots n_valid..N-1.
  - Every miss installs the request (no bypass). COUNTER_MODE 0: the installed tag's count is 1.
    COUNTER_MODE 1: the slot keeps its count and adds 1 (saturating at 63); a never-used slot has 0.

Classes (each takes the capacity in lines; `name` is the policy name used by run_shared_cache.py):
  RTLStructuralModel  literal O(N)-per-miss model: eff(), per-group Stage A and Stage B trees in the
                      RTL's heap order. Power-of-two depths only. Used to validate the fast models.
  RTLExactCache       fast RTL model (lazy heap over (count, slot)); RTLExactMode0 / RTLExactMode1.
  LFUResetVariant     run_trace_sim.LFUResetCache with the tie-break ('oldest' = earliest install, as
                      LFUResetCache; 'slot' = lowest slot index) and the saturation value as parameters.
                      Written separately from RTLExactCache (keyed by address, not by slot), so the
                      'slot' + 63 variant equalling RTLExactMode0 is a check between two implementations.
  RotatingTieCache    candidate rule: among equal eff, the first slot at or after a pointer (circular
                      priority); advance='victim' (pointer = victim + 1), 'step' (pointer + 1 per
                      eviction) or 'none' (pointer stays 0, i.e. the RTL rule; used as a check).
  YoungBitCache       candidate rule: one bit per slot, set on install; among equal eff a slot with the
                      bit clear wins, then the lowest index; if the chosen victim has the bit set (every
                      minimum-eff slot is young), all bits are cleared.
"""
import heapq

RTL_CMAX = 63      # COUNTER_WIDTH = 6
RTL_GROUPS = 16    # GROUPS default of the RTL (tb_power.sv does not override it)


def _rate(hits, misses):
    total = hits + misses
    return hits / total * 100 if total > 0 else 0.0


def _install_count(mode, old, cmax):
    """freq_cnt written in FILL: 1 (mode 0), or the slot's count + 1, saturating (mode 1)."""
    if mode == 0:
        return 1
    return old + 1 if old != cmax else old


class RTLStructuralModel:
    """Literal model of the RTL, one request at a time, O(N) work per request."""
    name = "RTL structural model"

    def __init__(self, capacity, mode=0, groups=RTL_GROUPS, cmax=RTL_CMAX):
        gsize = capacity // groups
        if (mode not in (0, 1) or groups < 2 or groups & (groups - 1) or capacity % groups
                or gsize & (gsize - 1)):
            raise ValueError(f"depth {capacity}, groups {groups}, mode {mode}: not an RTL configuration")
        self.cap, self.mode, self.groups, self.gsize, self.cmax = capacity, mode, groups, gsize, cmax
        self.tag = [0] * capacity
        self.cnt = [0] * capacity
        self.valid = [False] * capacity
        self.hits = self.misses = 0

    def _eff(self, s):
        return self.cnt[s] + 1 if self.valid[s] else 0

    @staticmethod
    def _tree_min(leaves):
        """Balanced min tree in heap order over (eff, slot) leaves; a node takes the right child only
        if its eff is strictly smaller (the RTL's a_take_r / take_r)."""
        n = len(leaves)
        node = [None] * (n - 1) + list(leaves)
        for i in range(n - 2, -1, -1):
            lv, rv = node[2 * i + 1], node[2 * i + 2]
            node[i] = rv if rv[0] < lv[0] else lv
        return node[0]

    def access(self, key):
        match = [s for s in range(self.cap) if self.valid[s] and self.tag[s] == key]
        if match:
            s = match[0]                                        # hit_idx: lowest matching slot
            if self.cnt[s] != self.cmax:
                self.cnt[s] += 1
            self.hits += 1
            return True
        self.misses += 1
        stage_a = [self._tree_min([(self._eff(g * self.gsize + i), g * self.gsize + i)
                                   for i in range(self.gsize)])[1] for g in range(self.groups)]
        victim = self._tree_min([(self._eff(s), s) for s in stage_a])[1]
        self.valid[victim] = False                              # EVICT
        self.tag[victim] = key                                  # FILL
        self.valid[victim] = True
        self.cnt[victim] = _install_count(self.mode, self.cnt[victim], self.cmax)
        return False

    @property
    def hit_rate(self):
        return _rate(self.hits, self.misses)


class RTLExactCache:
    """Fast model of the RTL policy. The lazy heap holds (count, slot); an entry is current when the
    slot's count still equals it, and every count change pushes a new entry, so the smallest current
    entry is the lowest slot among the minimum count (all slots are valid once the cache is full)."""
    name = "RTL-exact"

    def __init__(self, capacity, mode=0, cmax=RTL_CMAX):
        if mode not in (0, 1):
            raise ValueError(f"mode {mode}: only COUNTER_MODE 0 and 1 exist")
        self.cap, self.mode, self.cmax = capacity, mode, cmax
        self.slot_of = {}                  # tag -> slot, valid slots only
        self.tag = [None] * capacity
        self.cnt = [0] * capacity          # freq_cnt (kept across tags; used by mode 1)
        self.n_valid = 0
        self.heap = []
        self.hits = self.misses = 0

    def _rebuild(self):
        self.heap = [(self.cnt[s], s) for s in range(self.n_valid)]
        heapq.heapify(self.heap)

    def access(self, key):
        s = self.slot_of.get(key)
        if s is not None:
            c = self.cnt[s]
            if c != self.cmax:
                c += 1
                self.cnt[s] = c
                heapq.heappush(self.heap, (c, s))
                if len(self.heap) > 4 * self.cap + 10000:
                    self._rebuild()
            self.hits += 1
            return True

        self.misses += 1
        if self.n_valid < self.cap:
            s = self.n_valid                       # lowest invalid slot (eff 0)
            self.n_valid += 1
        else:
            heap, cnt = self.heap, self.cnt
            while cnt[heap[0][1]] != heap[0][0]:
                heapq.heappop(heap)
            s = heapq.heappop(heap)[1]
            del self.slot_of[self.tag[s]]
        c = _install_count(self.mode, self.cnt[s], self.cmax)
        self.cnt[s] = c
        self.tag[s] = key
        self.slot_of[key] = s
        heapq.heappush(self.heap, (c, s))
        return False

    @property
    def hit_rate(self):
        return _rate(self.hits, self.misses)

    @property
    def dram_reads(self):
        return self.misses


class RTLExactMode0(RTLExactCache):
    name = "RTL-exact mode 0"

    def __init__(self, capacity):
        super().__init__(capacity, mode=0)


class RTLExactMode1(RTLExactCache):
    name = "RTL-exact mode 1"

    def __init__(self, capacity):
        super().__init__(capacity, mode=1)


class LFUResetVariant:
    """run_trace_sim.LFUResetCache with two parameters: tie ('oldest': the key that entered the cache
    earliest, as LFUResetCache; 'slot': the lowest slot index, slots assigned like the RTL: the next
    free slot while filling, then the victim's slot) and cmax (counter saturation value)."""
    name = "LFU-reset variant"

    def __init__(self, capacity, tie='oldest', cmax=255):
        if tie not in ('oldest', 'slot'):
            raise ValueError(f"tie {tie!r}")
        self.cap, self.tie, self.cmax = capacity, tie, cmax
        self.cache = {}            # key -> tie value (install sequence number or slot)
        self.freq = {}
        self.heap = []             # (freq, tie value, key), lazy
        self.seq = 0
        self.hits = self.misses = 0

    def _valid(self, entry):
        f, t, k = entry
        return self.cache.get(k) == t and self.freq.get(k) == f

    def access(self, key):
        if key in self.cache:
            f = self.freq[key]
            if f < self.cmax:
                f += 1
                self.freq[key] = f
                heapq.heappush(self.heap, (f, self.cache[key], key))
                if len(self.heap) > 4 * self.cap + 10000:
                    self.heap = [(self.freq[k], t, k) for k, t in self.cache.items()]
                    heapq.heapify(self.heap)
            self.hits += 1
            return True

        self.misses += 1
        if len(self.cache) >= self.cap:
            while not self._valid(self.heap[0]):
                heapq.heappop(self.heap)
            _, t, victim = heapq.heappop(self.heap)
            del self.cache[victim]
            del self.freq[victim]           # RESET on eviction
            slot = t
        else:
            slot = len(self.cache)          # next free slot (no invalidation path)
        self.seq += 1
        t = slot if self.tie == 'slot' else self.seq
        self.cache[key] = t
        self.freq[key] = 1
        heapq.heappush(self.heap, (1, t, key))
        return False

    @property
    def hit_rate(self):
        return _rate(self.hits, self.misses)

    @property
    def dram_reads(self):
        return self.misses


class LFUResetLowestSlot(LFUResetVariant):
    name = "LFU-reset lowest-slot"

    def __init__(self, capacity):
        super().__init__(capacity, tie='slot', cmax=255)


class LFUReset6bit(LFUResetVariant):
    name = "LFU-reset 6-bit"

    def __init__(self, capacity):
        super().__init__(capacity, tie='oldest', cmax=RTL_CMAX)


class LFUResetLowestSlot6bit(LFUResetVariant):
    name = "LFU-reset lowest-slot 6-bit"

    def __init__(self, capacity):
        super().__init__(capacity, tie='slot', cmax=RTL_CMAX)


class RotatingTieCache:
    """Candidate rule (not in the RTL): among slots with the minimum eff, the first slot at or after a
    pointer, wrapping (circular priority). In hardware: the min-tree key gains one low-order bit,
    (slot < ptr), above the index tie-break. The pointer is kept as an absolute, never-decreasing value
    P (position P mod N). One lazy heap per eff value holds (A, slot, version), A = the next absolute
    pointer value >= P at which the pointer reaches the slot; entries whose A has been passed are
    re-keyed when they reach the top, and entries with an old version are dropped."""
    name = "rotating tie-break"

    def __init__(self, capacity, mode=0, advance='victim', cmax=RTL_CMAX):
        if mode not in (0, 1) or advance not in ('victim', 'step', 'none'):
            raise ValueError(f"mode {mode}, advance {advance!r}")
        n = capacity
        self.cap, self.mode, self.advance, self.cmax = n, mode, advance, cmax
        self.P = 0
        self.slot_of = {}
        self.tag = [None] * n
        self.cnt = [0] * n
        self.eff = [0] * n                     # 0 = invalid, else count + 1
        self.ver = [0] * n
        self.size = [0] * (cmax + 2)           # slots per eff value
        self.size[0] = n
        self.heaps = [[] for _ in range(cmax + 2)]
        self.heaps[0] = [(s, s, 0) for s in range(n)]     # sorted, so already a heap
        self.entries = n
        self.hits = self.misses = 0

    def _key(self, s):
        pos = self.P % self.cap
        return self.P - pos + s + (self.cap if s < pos else 0)

    def _push(self, s):
        heapq.heappush(self.heaps[self.eff[s]], (self._key(s), s, self.ver[s]))
        self.entries += 1
        if self.entries > 4 * self.cap + 10000:
            self.heaps = [[] for _ in range(self.cmax + 2)]
            for t in range(self.cap):
                self.heaps[self.eff[t]].append((self._key(t), t, self.ver[t]))
            for h in self.heaps:
                heapq.heapify(h)
            self.entries = self.cap

    def _move(self, s, e):
        self.size[self.eff[s]] -= 1
        self.size[e] += 1
        self.eff[s] = e
        self.ver[s] += 1
        self._push(s)

    def access(self, key):
        s = self.slot_of.get(key)
        if s is not None:
            if self.cnt[s] != self.cmax:
                self.cnt[s] += 1
                self._move(s, self.cnt[s] + 1)
            self.hits += 1
            return True

        self.misses += 1
        e = 0
        while not self.size[e]:
            e += 1
        heap, ver = self.heaps[e], self.ver
        while True:
            a, s, v = heap[0]
            if v != ver[s]:
                heapq.heappop(heap)
                self.entries -= 1
            elif a < self.P:
                heapq.heapreplace(heap, (self._key(s), s, v))
            else:
                break
        heapq.heappop(heap)
        self.entries -= 1
        if self.advance == 'victim':
            self.P = a + 1
        elif self.advance == 'step':
            self.P += 1
        if self.tag[s] is not None:
            del self.slot_of[self.tag[s]]
        self.cnt[s] = _install_count(self.mode, self.cnt[s], self.cmax)
        self.tag[s] = key
        self.slot_of[key] = s
        self._move(s, self.cnt[s] + 1)
        return False

    @property
    def hit_rate(self):
        return _rate(self.hits, self.misses)

    @property
    def dram_reads(self):
        return self.misses


class YoungBitCache:
    """Candidate rule (not in the RTL): one 'young' bit per slot, set when a tag is installed. The
    min-tree key is (eff, young, slot). If the chosen victim is young, every slot with the minimum eff is
    young; all young bits are then cleared (one global clear), and the victim is the same slot. Lazy heap
    of (eff, young, slot, version)."""
    name = "young-bit tie-break"

    def __init__(self, capacity, mode=0, cmax=RTL_CMAX):
        if mode not in (0, 1):
            raise ValueError(f"mode {mode}")
        n = capacity
        self.cap, self.mode, self.cmax = n, mode, cmax
        self.slot_of = {}
        self.tag = [None] * n
        self.cnt = [0] * n
        self.eff = [0] * n
        self.young = [0] * n
        self.ver = [0] * n
        self.young_list = []                   # slots set young since the last clear
        self.heap = [(0, 0, s, 0) for s in range(n)]
        self.hits = self.misses = 0

    def _push(self, s):
        self.ver[s] += 1
        heapq.heappush(self.heap, (self.eff[s], self.young[s], s, self.ver[s]))
        if len(self.heap) > 4 * self.cap + 10000:
            self.heap = [(self.eff[t], self.young[t], t, self.ver[t]) for t in range(self.cap)]
            heapq.heapify(self.heap)

    def _top(self):
        heap, ver = self.heap, self.ver
        while heap[0][3] != ver[heap[0][2]]:
            heapq.heappop(heap)
        return heap[0]

    def access(self, key):
        s = self.slot_of.get(key)
        if s is not None:
            if self.cnt[s] != self.cmax:
                self.cnt[s] += 1
                self.eff[s] = self.cnt[s] + 1
                self._push(s)
            self.hits += 1
            return True

        self.misses += 1
        _, y, s, _ = self._top()
        if y:
            for t in self.young_list:
                if self.young[t]:
                    self.young[t] = 0
                    self._push(t)
            self.young_list = []
            assert self._top()[2] == s
        heapq.heappop(self.heap)
        if self.tag[s] is not None:
            del self.slot_of[self.tag[s]]
        self.cnt[s] = _install_count(self.mode, self.cnt[s], self.cmax)
        self.eff[s] = self.cnt[s] + 1
        self.tag[s] = key
        self.slot_of[key] = s
        self.young[s] = 1
        self.young_list.append(s)
        self._push(s)
        return False

    @property
    def hit_rate(self):
        return _rate(self.hits, self.misses)

    @property
    def dram_reads(self):
        return self.misses


def _named(base, name, **kw):
    """Module-level subclass with a fixed name and parameters (picklable for the worker pool)."""
    cls = type(name.replace(' ', '_').replace('-', '_'), (base,),
               {'name': name, '__init__': lambda self, capacity: base.__init__(self, capacity, **kw)})
    cls.__module__ = __name__
    globals()[cls.__name__] = cls
    return cls


CANDIDATES = [_named(RotatingTieCache, f"Rotate-victim mode {m}", mode=m, advance='victim') for m in (0, 1)] + \
             [_named(RotatingTieCache, f"Rotate-step mode {m}", mode=m, advance='step') for m in (0, 1)] + \
             [_named(YoungBitCache, f"Young-bit mode {m}", mode=m) for m in (0, 1)]

ABLATIONS = [LFUResetLowestSlot, LFUReset6bit, LFUResetLowestSlot6bit]
RTL_EXACT = [RTLExactMode0, RTLExactMode1]
P9_POLICIES = RTL_EXACT + ABLATIONS + CANDIDATES
