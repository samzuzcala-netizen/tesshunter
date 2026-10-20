# BATCH_1 - smoke (first 60 stars of batch 1)

Generated 2026-10-16T01:04Z by `s1/protocol/report_s1.py`.  Tags: [M] measured, [I] interpretation.  SUBMIT / HOLD are candidates for the user's review, not detections; nothing was uploaded or submitted.

## Stars and unknowns [M]

* stars: 60; download states: {'complete': 60}
* searched (COMPLETE): 60; search unknowns: 0
* partition-limited fraction: 16.7% (10 stars); sector-matched expectation 31.5%; S-P (expectation + 10 pp, user decision 2026-10-16) not triggered

| phase | stage | status | complete / total | unknowns | wall h |
|---|---|---|---|---|---|
| s1_b1_smoke2_A | A | CLOSED | 103 / 103 | 0 | 0.56 |
| s1_b1_smoke2_B | B | CLOSED | 3 / 3 | 0 | 0.0 |
| s1_b1_smoke2_C | C | CLOSED | 3 / 3 | 0 | 0.31 |
| s1_b1_smoke2_dl | download | CLOSED | 40 / 40 | 0 | 0.18 |
| s1_b1_smoke2_nb | neighbours | CLOSED | 1 / 1 | 0 | 0.0 |
| s1_b1_smoke2_nb_bulk | neighbours | CLOSED | 2 / 2 | 0 | 0.01 |
| s1_b1_smoke2_S | S | CLOSED | 3 / 3 | 0 | 0.01 |
| s1_b1_smoke2_search | search | CLOSED | 40 / 40 | 0 | 1.01 |
| s1_b1_smoke_A | A | CLOSED | 72 / 73 | 1 | 0.47 |
| s1_b1_smoke_dl | download | CLOSED | 20 / 20 | 0 | 0.08 |
| s1_b1_smoke_search | search | CLOSED | 20 / 20 | 0 | 1.2 |

## Funnel counts [M]

| stage | jobs | pass | unknown |
|---|---|---|---|
| search -> accepted / pre-gate | 60 | 1193 accepted, 176 pre-gate | 0 |
| A | 176 | 3 | 1 |
| S (bound_alias) | 3 | PASS 3, HOLD 0 | 0 |
| B | 3 | 3 | 0 |
| C | 3 | 0 | 0 |
| D | 0 | SUBMIT 0, HOLD 0, KILL 0 | 0 |

* SUBMIT + HOLD per 1,000 searched stars: 0.0 (S-L at 30); in the eM slice: 0
* KILL by deciding condition: none

## Stage C walls [M]

{'n': 3, 'min': 925.3054432999343, 'median': 987.0496156997979, 'p90': 1080.3481032200157, 'max': 1103.6727251000702, 'over_4h': 0, 'over_4h_frac': 0.0}

## Cost [M]

Phase wall hours by stage (overlapping network phases counted separately): {'A': 1.03, 'B': 0.0, 'C': 0.31, 'S': 0.01, 'download': 0.26, 'neighbours': 0.01, 'search': 2.21}
(plan ~120 queue-hours per batch, ~601 in total).

## Disk [M]

GB by category: {'fits_cache': 0.999, 'store': 0.215, 'stitched': 0.128, 'search': 0.183, 'funnel_case_roots': 0.951, 'tesscut_pixel_cache': 0.0, 'tesscut_fpp_cache': 0.0, 'packets': 0.0, 'receipts': 0.02, 'runtimes': 0.003, 'controllers': 0.014, 'total_s1_root': 3.123}

Rates: {'fits_per_sector_mb': 0.568, 'store_per_sector_mb': 0.122, 'stitched_per_sector_mb': 0.073, 'search_per_star_mb': 3.055, 'search_per_sector_mb': 0.104, 'funnel_per_A_candidate_mb': 5.405, 'd_per_D_candidate_gb': 0.0}

## SUBMIT / HOLD candidates

None.
