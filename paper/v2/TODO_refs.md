# References: open items (checked 2026-10-26)

## In refs.bib, but with fields not verified
- `gupta2020architectural` (HPCA 2020): venue, year and first authors verified; page numbers and DOI not confirmed
  (left out). Full author list abbreviated with "others".
- `ke2020recnmp` (ISCA 2020): title, venue and first author verified (Meta research page, arXiv 1912.12953); full
  author list, pages and DOI not confirmed (left out).
- `adnan2022fae` (PVLDB 15(1), 2022): title, authors, volume and issue verified; pages not confirmed (left out).
- `eisenman2019bandana`: published at MLSys 2019 (Proc. MLSys vol. 1); pages not confirmed (left out).
- `opensta`, `wolf_yosys`, `nangate45`, `icarus`, `criteo2014dac`: software/data web pages; no access date in the entry.

## Considered and left out (not verified)
- Acun et al., "Understanding Training Efficiency of Deep Learning Recommendation Models at Scale" (HPCA 2021).
- Breslau et al., "Web Caching and Zipf-like Distributions" (INFOCOM 1999).
- Clauset, Shalizi, Newman, "Power-law distributions in empirical data" (SIAM Review 2009) - would be needed if the
  paper discussed the Zipf-fit method.
- Kal et al., "SPACE: Locality-Aware Processing in Heterogeneous Memory for Personalized Recommendations" (ISCA 2021).
- Yang et al., "Mixed-Precision Embedding Using a Cache" (arXiv 2020).

## Rewrite of 2026-11-19 (28nm version)
- Cited now: all entries of refs.bib except `binkert2011gem5` (gem5 is no longer discussed). The open fields above
  still apply.
- Named without a citation (no verified entry): Nsight Compute, Cadence Genus / Xcelium / Innovus, CMP.
- Not cited, would need a verified source if the text is extended: a classic LRU/LFU reference, an FD-SOI technology
  overview (body bias), prior hardware LFU or replacement-unit designs, clock gating of register files.
- Claims about other papers to re-check against the papers themselves: Gupta et al. (embedding operators can dominate
  inference time), Bandana and FAE (skewed accesses, hot rows), ScratchPipe (future accesses known from the training
  pipeline).

## Verification of 2026-11-20 (readability revision)
Checked against each paper's own text (arXiv abstract page or the authors' PDF; dblp blocked automated access):
- Gupta et al. (HPCA 2020 preprint, arXiv 1906.03109v4): for RMC2 "SparseLengthsSum consumes 80% of the execution time
  of the model" -> paper says "embedding operations ... can dominate inference time" (no number quoted).
- RecNMP (arXiv 1912.12953): "dominated by memory-bound sparse embedding operations" -> "memory-bound".
- Bandana (arXiv 1811.05922): NVM as primary storage with a small DRAM cache. Its abstract does not claim access skew,
  so it is no longer cited for skew.
- FAE (PVLDB 2022, arXiv 2103.00686): accesses "highly skewed"; hot embeddings in GPU memory during training.
- ScratchPipe (ISCA 2022, arXiv 2205.04702): embedding cache that "sees the past but also the future" accesses.
- Added: Bagpipe (SOSP 2023, DOI 10.1145/3600006.3613142; lookahead caching and prefetching in training; ~1% of
  embeddings take >92% of accesses), Fleche (EuroSys 2022, DOI 10.1145/3492321.3519554; one GPU cache backend for all
  tables, inference), HugeCTR inference parameter server (RecSys 2022, DOI 10.1145/3523227.3546765; GPU embedding
  cache with hierarchical storage), UGache (SOSP 2023, DOI 10.1145/3600006.3613169; multi-GPU cache, policy from a
  hotness metric), EVStore (ASPLOS 2023, DOI 10.1145/3575693.3575718; 3-layer caching of embedding lookups for
  inference). Venue, year and DOI from each paper's ACM Reference Format block or arXiv record; authors and pages
  from the Crossref record of the DOI (the HPS RecSys record names Jie Liu, Ji Shi, Zehuan Wang, not the arXiv forms).
- Not confirmed and not used: "cDLRM: Look Ahead Caching ..." (RecSys 2021); no record found.
