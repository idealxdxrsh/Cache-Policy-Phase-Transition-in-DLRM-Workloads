# gem5 results

| Run | File | Status |
|-----|------|--------|
| LRU, 2 MB L2 | `lru_2mb/stats.txt` | included (full gem5 stats) |
| LFU, 2 MB L2 | `lfu_2mb/stats.txt` | included (L2 cache counters only) |
| LRU / LFU, 256 kB | `lru_256k/`, `lfu_256k/` | not available: no gem5 `stats.txt` or `m5out` found on Sharanga (searched 2026-10-26); run scripts are here |
| LRU / LFU, 512 kB | `lru_512k/`, `lfu_512k/` | not available: neither stats nor run scripts found on Sharanga (searched 2026-10-26) |

The 2 MB files reproduce the withdrawn manuscript's L2 misses, 304,590 (LRU) vs 293,995 (LFU). These runs model a
CPU with DDR4, not a GPU, the "LFU" run is gem5's LFURP (reset on eviction), and they were not re-run; claim status
in `results/P7/CLAIMS.md`, rows 7 to 11.
