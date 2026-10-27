"""P8: trace-simulator policies vs the RTL on exactly the requests a slice replay issued.

Usage: python -I tools/p8_compare.py <slice.hex> <slice.json> <rtl result txt> [<netlist result txt>]
The result files are synthesis/p8/run_p8.sh outputs (line `p8_power ... requests=R ... win_first_req=a
win_last_req=b`). The first R addresses of the slice (the requests the RTL completed, from a cold start) are run
through the trace simulator's LRU and LFU (reset on eviction) classes (trace_sim/run_trace_sim.py, unchanged), cold
start, at 256 entries and at the RTL's depth. Hits are counted over all R requests and over the recorded window's
requests [a, b]. The RTL's hits come from its responses (hit_flag), counted per request: all R requests, and the
requests issued in the window (winreq_hits), the same set as the simulator's window count.
Known differences: on equal counts the RTL evicts the lowest slot index, the simulator the entry that entered
earliest; RTL counters saturate at 63, the simulator's at 255; RTL COUNTER_MODE 1 keeps the slot's count for a new tag.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'trace_sim'))
from run_trace_sim import LFUResetCache, LRUCache  # noqa: E402


def result(path):
    line = next(l for l in Path(path).read_text().splitlines() if l.startswith('p8_power'))
    return {k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)', line)}


def run(policy, cap, addrs, a, b):
    c = policy(cap)
    tot = win = 0
    for i, x in enumerate(addrs):
        if c.access(x):
            tot += 1
            if a <= i <= b:
                win += 1
    return tot, win


def main():
    addrs_all = [int(l, 16) for l in Path(sys.argv[1]).read_text().split()]
    meta = json.loads(Path(sys.argv[2]).read_text())
    rtl = result(sys.argv[3])
    gl = result(sys.argv[4]) if len(sys.argv) > 4 else None
    r, a, b = rtl['requests'], rtl['win_first_req'], rtl['win_last_req']
    addrs = addrs_all[:r]
    out = {'slice': meta['slice'], 'start_row': meta['start_row'], 'start_access': meta['start_access'],
           'depth': rtl['depth'], 'mode': rtl['mode'], 'requests': r,
           'distinct_keys_replayed': max(addrs) + 1 if addrs else 0,
           'window_requests': (b - a + 1) if a >= 0 else 0, 'window_first_req': a, 'window_last_req': b,
           'rtl_hits': rtl['hits'], 'rtl_responses': rtl['responses'], 'rtl_winreq_hits': rtl['winreq_hits'],
           'rtl_winreq_responses': rtl['winreq_responses']}
    if gl:
        out['netlist_equals_rtl'] = all(gl[k] == rtl[k] for k in ('requests', 'responses', 'hits', 'misses',
                                                                  'winreq_hits', 'winreq_responses',
                                                                  'win_first_req', 'win_last_req'))
    for cap in sorted({256, rtl['depth']}):
        for name, pol in (('lru', LRUCache), ('lfu_reset', LFUResetCache)):
            t, w = run(pol, cap, addrs, a, b)
            out[f'sim_{name}_{cap}_hits'] = t
            out[f'sim_{name}_{cap}_win_hits'] = w
    print(json.dumps(out))


if __name__ == '__main__':
    main()
