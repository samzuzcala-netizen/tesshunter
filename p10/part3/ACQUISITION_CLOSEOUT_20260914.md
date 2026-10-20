# Part D acquisition close-out (2026-09-14, user's Claude session)

**State: the raw-product acquisition for all 473 post-A stars is complete.**
No controller owner exists, no P10.3 process is alive, and every phase has a
closure receipt with `source_hashes_unchanged: true`. This is an operational
close-out of the download step only. Source-FITS identity verification,
corrected-v02 checks for QLP 74 to 79, Gaia/SIMBAD/VSX, the native noise
record, final eligibility and STOP-1 remain Codex's Part D work, and nothing
from Part E onward was touched. No blind search, forced fit or ephemeris was
opened.

## What ran [M]

| Phase | Jobs | Complete | Unknowns | Queue h | Note |
|---|---:|---:|---:|---:|---|
| download_pilot (Codex, v1, 1,800 s) | 50 | 37 | 13 | 1.388 | 7 deadline, 3 stalled, 2 HTTP 502, 1 HTTP 404 |
| download_v2_batch_01 (600 s) | 100 | 100 | 0 | 0.344 | the 13 pilot failures at attempt 2, all complete |
| download_v2_batch_02 | 100 | 100 | 0 | 0.463 | |
| download_v2_batch_03 | 100 | 100 | 0 | 0.312 | |
| download_v2_batch_04 | 100 | 100 | 0 | 0.325 | |
| download_v2_batch_05 | 36 | 36 | 0 | 0.123 | |
| download_v2_retry (`--force`) | 6 | 6 | 0 | 0.013 | one product-level failure each, all now 0 |
| download_v2_retry_pilot (`--force`) | 3 | 3 | 0 | ~0.01 | pilot stars with one product-level failure, all now 0 |

Totals: 473/473 stars carry `index.json`; 11,532 products, 10,895 at sectors
56 and later; **0 products with a recorded failure**. New scientific queue
charge 2.98 of 31.98 h. Acquisition 12.10 GB cumulative of 15 GB (12.02 GB
new HTTP body bytes this run, plus 206,848 bytes of outstanding reservation
carried conservatively). Version-2 receipts: `results/download_v2/` (445
files), controller receipts under `results/controllers/download_v2_*`,
launcher receipts `manifests/download_v2_*_launcher.json`, eight bounded
check-ins appended to `logs/checkins.jsonl` and `RESUME_P10_3.md`.

Measured under D1: 21.5 to 31 MB of HTTP per star by batch (mean 26.4 MB, p90
44 MB), against 38 MB per star under the sector-27 superset. Disk consumption
was about 48 MB per star including arrays and receipts.

## Storage actions [M]

Drive `C:` fell to 27.7 GB during batch 05, 1.7 GB above the controller's own
abort line. Two regenerable caches were relocated to `D:` behind directory
junctions at their original paths, as the prompt authorizes; nothing was
deleted and no sealed evidence moved:

| Cache | Files | Bytes | Receipt |
|---|---:|---:|---|
| `data/cache/stitched` | 6,658 | 3,763,602,311 | `manifests/cache_relocation_stitched.json` |
| `data/cache/lightkurve/tesscut` | 324 | 21,004,824,598 | `manifests/cache_relocation_tesscut.json` |

Both verified byte-for-byte through the junction (PowerShell and Python
`os.walk`; Git Bash `find` does not descend junctions and reports 0, which is
recorded in the tesscut receipt). `C:` free at close: 54.0 GB. The resource
ledger's `cache_relocation` field points at both receipts. Earlier in the
evening the two orphaned git temporary packs were removed, repo-local
`gc.auto=0` / `maintenance.auto=false` were set, and the loose object store
was packed once (`MAIN_REVIEW_20260914.md` sections 1 and 6).

## Preliminary eligibility picture, not a registered cut [M]

Counting distinct sectors at 56 and later per star from `index.json` with the
QLP exclusions applied, but before FITS identity and timing verification: 436
stars have at least 3, 37 have fewer than 3, median 16. STOP-1 (at least 60
independent likely-periodic in-band families) therefore looks safe against the
98 counted after Part A, but the registered count belongs to Codex's
eligibility step.

## Open items for Codex

1. Fold amendments D1 to D4 into the preregistration amendment table
   (`AMENDMENTS_D1_D4_20260914.md` has the rows and hashes). Note the builder
   scope gap: `build_batches_v2.py retry` scans only version-2 batches; the
   three pilot stars were re-indexed from an inline manifest
   (`manifests/download_v2_retry_pilot_plan.json`).
2. Finish Part D: FITS identity and corrected-v02 verification, Gaia/SIMBAD/VSX
   (`scripts/p8_neighbours.py bulk` then `stars`), the native noise record,
   final eligibility, STOP-1.
3. Commit the P10.3 checkpoint with `-c maintenance.auto=false -c gc.auto=0`
   (now also set repo-locally). The check-in log, ledger, progress and resume
   files are modified tracked files; the new receipts and logs are untracked.
4. Proceed to Part E (timing pilot, level selection) in the Codex session.
