# P12: Genus synthesis of rtl-v2-final (v2) and rtl-v3 (v3) on the lab server C2
Technology: a commercial 28nm FD-SOI standard-cell library, typical corner; area in library units; pre-layout.
Every number is from results/P12/TABLES.md (tools/c2_collect.py on the raw reports, which stay off the repo); flow in
cadence/ (genus_lfu.tcl, run_genus.csh, genus_lfu_nomerge.tcl). Aggregate results published with Prof. Mane's approval.

## Timing brackets: tightest period met / loosest failed (ns); Fmax = 1 / (period - WNS) of failing runs (TABLES.md "Timing limit")
| ver | mode | depth 16 | depth 64 | depth 256 |
|---|---|---|---|---|
| v2 | 0 | 0.65 / 0.5; 1647.4 MHz | 0.8 / 0.65; 1529.1 (0.65), 1329.8 (0.5) | 0.8 / 0.65; 1259.4 (0.65), 1251.6 (0.5) |
| v2 | 1 | 0.65 / 0.5; 1618.1 MHz | 0.8 / 0.65; 1526.7 (0.65), 1328.0 (0.5) | 0.8 / 0.65; 1262.6 (0.65), 1264.2 (0.5) |
| v3 | 0 | 0.65 / 0.5; 1602.6 MHz | 0.8 / 0.65; 1506.0 (0.65), 1447.2 (0.5) | 0.8 / 0.65; 1256.3 (0.65), 1267.4 (0.5) |
| v3 | 1 | 0.65 / 0.5; 1689.2 MHz | 0.65 / 0.5; 1512.9 (0.5) | 0.8 / 0.65; 1278.8 (0.65), 1262.6 (0.5) |
Fmax v3 - v2, mode 0 / mode 1 (mode 1 = same logic, results/P11/equiv/ at depth 16 and 64 = noise reference; TABLES.md "v3 against v2 Fmax"): d16 0.5 ns -2.72% / +4.39%; d64 0.5 ns +8.83% / +13.92%; d64 0.65 ns -1.51% / not measured (v3 met); d256 0.5 ns +1.27% / -0.13%; d256 0.65 ns -0.25% / +1.28%. Only d256 0.5 ns has a mode-0 difference above the mode-1 one at the same point, and it is below the other d256 mode-1 difference (1.28%).

## Area at 2.0 ns (all 12 runs met timing), v2 -> v3 (TABLES.md "v3 - v2 at the same mode, depth and period")
| depth | mode 0 (logic change) | mode 1 (noise reference) |
|---|---|---|
| 16 | 14025.408 -> 14081.222 (+0.40%) | 14106.518 -> 14076.979 (-0.21%) |
| 64 | 54195.782 -> 54254.534 (+0.11%) | 54440.746 -> 54296.803 (-0.26%) |
| 256 | 214925.587 -> 214687.478 (-0.11%) | 216284.880 -> 214873.853 (-0.65%) |

## Merge-off: optimize_merge_seq false on req_addr_grp_reg, mode 0, depth 256 (TABLES.md "Merge-off")
- The normal flow merges the per-group address copies (Genus message GLO-42); merge-off keeps all 320 req_addr_grp_reg flops (is_320 = yes, 4 runs); flip-flops 39925 -> 40245 (v2), 39933 -> 40253 (v3).
- 0.65 ns: Fmax v2 1259.4 -> 1310.6 MHz (+4.06%), v3 1256.3 -> 1314.1 MHz (+4.60%); area +0.31% (v2), +4.06% (v3). 0.8 ns: met in both flows.

## Limitations
- Pre-layout: no LEF, library default (zero) wireload, no extracted parasitics; one typical corner only.
- One synthesis run per point; the mode-1 v3 - v2 difference is the only noise estimate.
- P12 power (TABLES.md) is vectorless (default switching activity).
- Normal-flow netlists lack the per-group address copies (Genus merges them); only the merge-off runs keep them.
- Fmax from a failing run depends on the target period (v2 m0 d64: 1529.1 MHz at 0.65 ns, 1329.8 MHz at 0.5 ns), so the met/failed period bracket is the reliable figure.
- Area at tight periods varies between runs: v2 vs v3 normal flow differ by -4.87% (mode 0, d256, 0.65 ns; logic differs), the same-logic mode-1 difference reaches -3.41% (d256, 0.5 ns; -2.62% at 0.65 ns). Merge-off area changes (+0.31%, +4.06% at 0.65 ns; -0.10%, +1.10% at 0.8 ns) are within 4.87%, but v3's +4.06% is above the largest same-logic difference.
- Licence: the library is used under a licence; only aggregate results are published (approved by Prof. Mane), no library data, cell names or raw reports.
