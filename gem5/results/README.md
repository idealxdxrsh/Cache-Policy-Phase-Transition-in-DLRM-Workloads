# gem5 results

| Run | File | Status |
|-----|------|--------|
| LRU, 2 MB L2 | `lru_2mb/stats.txt` | included (full gem5 stats) |
| LFU, 2 MB L2 | `lfu_2mb/stats.txt` | included (L2 cache counters only) |
| LRU / LFU, 256 kB | `lru_256k/`, `lfu_256k/` | not in this repo yet: copy `stats.txt` from the Sharanga run directories |
| LRU / LFU, 512 kB | `lru_512k/`, `lfu_512k/` | not in this repo yet, and the 512 kB run scripts are not here either |

The 2 MB files reproduce the paper's numbers: L2 misses 304,590 (LRU) vs 293,995 (LFU).
