# Notes on this waveform

`lfu_cache_waves.vcd` (ends at 3,985 ns) shows: freq_count[13] = 23, freq_count[15] = 13, freq_count[14] = 7,
all other lines = 1.

The testbench sends 10 repeat reads of one address, 5 of another and 3 of a third. The counters are about double
that because `next_state` and `current_state` are both registers in `LFU.v`: every state lasts two cycles, so a
hit increments the counter twice (count = 1 + 2 x hits). Hits are therefore not single-cycle either.
The testbench clock is 100 MHz and the modelled memory latency is 5 cycles; it prints results but checks nothing.
