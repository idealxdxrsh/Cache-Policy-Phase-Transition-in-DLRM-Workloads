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
