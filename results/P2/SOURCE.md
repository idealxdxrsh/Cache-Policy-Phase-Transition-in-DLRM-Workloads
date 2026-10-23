# P2 dataset source: Criteo Display Advertising Challenge (Kaggle 2014)

| Field | Value |
|---|---|
| Dataset | Criteo Display Advertising Challenge (Kaggle, 2014), archive `dac.tar.gz` |
| Host | figshare, "Kaggle Display Advertising Challenge dataset", uploaded by Zilong Jiang (third party, not Criteo) |
| DOI | 10.6084/m9.figshare.5732310.v1 |
| Record | https://figshare.com/articles/dataset/Kaggle_Display_Advertising_Challenge_dataset/5732310 |
| Download URL | https://ndownloader.figshare.com/files/10082655 (redirects to AWS S3 eu-west-1) |
| File size | 4576820670 bytes (figshare API `files[0].size`) |
| MD5 | df9b1b3766d9ff91d5ca3eb3d23bed27 (figshare `supplied_md5` = `computed_md5`) |
| MD5, independent | same value listed in https://github.com/zzbased/kaggle-2014-criteo README |
| SHA-256 | not published by figshare; computed value goes in `download.txt` after the job |
| License (figshare record) | CC0, as set by the uploader. Criteo's own terms for this data could not be read (terms text on ailab.criteo.com did not render), so they may also apply. |

Metadata retrieved 2026-10-24 via `https://api.figshare.com/v2/articles/5732310`.

## Why not the other sources
- Criteo official link (`go.criteo.net/criteo-research-kaggle-display-advertising-challenge-dataset.tar.gz`) redirects to `criteostorage.blob.core.windows.net`, which did not resolve (DNS) from the cluster login node or the local machine on 2026-10-24.
- Kaggle competition `criteo-display-ad-challenge` lists only `random_submission.zip` (50495892 bytes) as of 2026-10-24.
- Kaggle dataset `mrkmakr/criteo-dataset` has `dac/train.txt` (11147184845 bytes) but no license or checksum.
- Hugging Face `reczoo/Criteo_x4` is a random 8:1:1 re-split, not the original `train.txt`.

## Verification (filled from results/P2/download.txt after the job)
- Download job ID: 412889 (verify: 412890), status pending
- Size / MD5 match: pending
- SHA-256 (computed): pending
