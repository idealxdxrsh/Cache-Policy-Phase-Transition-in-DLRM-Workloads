# P2 summary: Criteo DAC dataset downloaded and verified

Every number below is copied from the file named next to it.

## Source (SOURCE.md, download.txt)
- figshare DOI 10.6084/m9.figshare.5732310.v1, `dac.tar.gz` (third-party upload; record license CC0)
- Archive size 4576820670 bytes, MD5 df9b1b3766d9ff91d5ca3eb3d23bed27: both match the figshare values
- SHA-256 (computed, source publishes none): ffb2ecbbc4ca478d2e87cc5168cca29f35a51ac5132c3a8fdea78c378c4e4c33

## Extracted files, bytes (download.txt)
| File | Bytes |
|---|---|
| train.txt | 11147184845 |
| test.txt | 1460246311 |
| readme.txt | 1927 |

## train.txt checks (verify.json, verify_head.txt; script cluster/verify_criteo.py)
- Rows: 45840617 (`wc -l` in verify_head.txt agrees)
- Rows without 40 tab-separated columns: 0
- Labels outside {0,1}: 0
- Integer columns 1-13, non-integer non-empty fields: 0
- Categorical columns 14-39: 1061312074 fields are 8-char lowercase hex, 130543968 empty, 0 other
- `cols_14_39_all_hex_or_empty`: true
- Consistency: 1061312074 + 130543968 = 1191856042 = 45840617 rows x 26 columns

## Jobs (sacct)
- 412889 p2_dl: COMPLETED, exit 0, 00:09:15, node21
- 412890 p2_verify: COMPLETED, exit 0, 00:08:40, node21
- Environment: bootstrap 412815 (COMPLETED); env at /scratch/rahulkmr/Adarsh/envs/dlrm_cache

## Not done / caveats
- train.txt MD5 was not computed, so it was not compared with the third-party value in the zzbased/kaggle-2014-criteo README.
- Criteo's own terms for this data could not be read; CC0 is the figshare uploader's label.
- python-dotenv is not yet in the env (environment.yml change pending a bootstrap update).
- jobs.txt is a stale record from the first driver run (jobs 412385/412386/412392).
- Data lives on /scratch (may be purged); re-download is reproducible from SOURCE.md.
