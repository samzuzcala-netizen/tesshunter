# BATCH_1 - eM ranks 1-1,500 + K ranks 1-500 (incl. the 60-star smoke)

Generated 2026-10-18T14:21Z by `s1/protocol/report_s1.py`.  Tags: [M] measured, [I] interpretation.  SUBMIT / HOLD are candidates for the user's review, not detections; nothing was uploaded or submitted.

## Stars and unknowns [M]

* stars: 2000; download states: {'complete': 2000}
* searched (COMPLETE): 2000; search unknowns: 0
* partition-limited fraction: 14.0% (280 stars); sector-matched expectation 22.7%; S-P (expectation + 10 pp, user decision 2026-10-16) not triggered

| phase | stage | status | complete / total | unknowns | wall h |
|---|---|---|---|---|---|
| s1_b1_A | A | CLOSED | 4444 / 4479 | 35 | 17.09 |
| s1_b1_A_retry | A | CLOSED | 25 / 35 | 10 | 0.58 |
| s1_b1_B | B | CLOSED | 122 / 122 | 0 | 0.05 |
| s1_b1_B2 | B | CLOSED | 2 / 2 | 0 | 0.01 |
| s1_b1_C | C | CLOSED | 122 / 122 | 0 | 2.95 |
| s1_b1_C2 | C | CLOSED | 2 / 2 | 0 | 0.27 |
| s1_b1_D | D | CLOSED | 17 / 17 | 0 | 0.5 |
| s1_b1_D2 | D | STOPPED | 1 / 13 | 6 | 0.5 |
| s1_b1_D3 | D | STOPPED | 1 / 14 | 1 | 0.18 |
| s1_b1_D4 | D | CLOSED | 13 / 13 | 0 | 0.56 |
| s1_b1_dl | download | CLOSED | 1933 / 1940 | 7 | 6.86 |
| s1_b1_dl_retry | download | CLOSED | 7 / 7 | 0 | 0.04 |
| s1_b1_nb | neighbours | CLOSED | 67 / 67 | 0 | 0.13 |
| s1_b1_nb2 | neighbours | CLOSED | 1 / 1 | 0 | 0.02 |
| s1_b1_nb2_bulk | neighbours | CLOSED | 2 / 2 | 0 | 0.01 |
| s1_b1_nb_bulk | neighbours | CLOSED | 2 / 2 | 0 | 0.01 |
| s1_b1_S | S | CLOSED | 136 / 136 | 0 | 0.14 |
| s1_b1_S2 | S | CLOSED | 2 / 2 | 0 | 0.01 |
| s1_b1_search_a | search | CLOSED | 207 / 207 | 0 | 4.36 |
| s1_b1_search_b | search | CLOSED | 1194 / 1194 | 0 | 25.5 |
| s1_b1_search_c | search | CLOSED | 539 / 539 | 0 | 9.29 |
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
| search -> accepted / pre-gate | 2000 | 37590 accepted, 4655 pre-gate | 0 |
| A | 4655 | 141 | 11 |
| S (bound_alias) | 141 | PASS 127, HOLD 0 | 0 |
| B | 127 | 127 | 0 |
| C | 127 | 32 | 0 |
| D | 32 | SUBMIT 7, HOLD 16, KILL 9 | 0 |

* SUBMIT + HOLD per 1,000 searched stars: 11.5 (S-L at 30); in the eM slice: 18
* KILL by deciding condition: {'K8': 5, 'K7': 2, 'K5': 1, 'K6': 1}

## Stage C walls [M]

{'n': 127, 'min': 124.137292499654, 'median': 469.93187810014933, 'p90': 1543.8020477600396, 'max': 2028.6093013002537, 'over_4h': 0, 'over_4h_frac': 0.0}

## Cost [M]

Phase wall hours by stage (overlapping network phases counted separately): {'A': 18.7, 'B': 0.06, 'C': 3.53, 'D': 1.74, 'S': 0.16, 'download': 7.16, 'neighbours': 0.18, 'search': 41.36}
(plan ~120 queue-hours per batch, ~601 in total).

## Disk [M]

GB by category: {'fits_cache': 6.579, 'store': 6.226, 'stitched': 3.104, 'search': 5.402, 'funnel_case_roots': 19.247, 'tesscut_pixel_cache': 23.439, 'tesscut_fpp_cache': 8.3, 'packets': 0.017, 'receipts': 0.428, 'runtimes': 0.067, 'controllers': 0.402, 'total_s1_root': 74.074}

Rates: {'fits_per_sector_mb': 0.153, 'store_per_sector_mb': 0.144, 'stitched_per_sector_mb': 0.072, 'search_per_star_mb': 2.701, 'search_per_sector_mb': 0.125, 'funnel_per_A_candidate_mb': 4.135, 'd_per_D_candidate_gb': 0.992}

Projection: {'basis': 'batch 1 rates; FITS pruned after each search (A), TESScut pruned after each batch report (B)', 'remaining_list_sectors': 160417, 'store_gb': 23.1, 'stitched_gb': 11.6, 'search_gb': 20.1, 'funnel_gb': 77.1, 'peak_fits_cache_gb': 25.0, 'peak_tesscut_gb_one_batch': 44.6, 'final_s1_root_gb_approx': 167.7, 'peak_extra_gb': 69.6}

## SUBMIT / HOLD candidates

| TIC | slice | verdict | tier | deciding | period d | depth ppt | stitch SNR | hard stop | TCE | pixel coverage | packet |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 116046773 | K | SUBMIT | 2 | None | 5.64717 | 0.829 | 13.4 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic116046773_P5.6472` |
| 116047785 | eM_slice | HOLD | None | H1 | 29.22897 | 0.85 | 7.1 | CLEAN | none | **incomplete** (none: 79) | `D:\tesshunter_s1\packets\s1_b1\tic116047785_P29.2290` |
| 155913240 | eM_slice | HOLD | None | H2 | 14.91579 | 3.784 | 36.8 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic155913240_P14.9158` |
| 155949537 | eM_slice | HOLD | None | H2 | 38.8999 | 0.856 | 7.3 | CLEAN | none | **incomplete** (none: 78) | `D:\tesshunter_s1\packets\s1_b1\tic155949537_P38.8999` |
| 159341729 | K | HOLD | None | H1 | 14.30161 | 0.383 | 11.4 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic159341729_P14.3016` |
| 160603808 | eM_slice | SUBMIT | 2 | None | 48.99088 | 11.157 | 10.7 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic160603808_P48.9909` |
| 165638563 | eM_slice | HOLD | None | H2 | 5.61141 | 1.818 | 18.2 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic165638563_P5.6114` |
| 18229070 | eM_slice | HOLD | None | H1 | 22.94841 | 0.965 | 7.4 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic18229070_P22.9484` |
| 188580030 | eM_slice | HOLD | None | H5 | 31.48996 | 1.645 | 8.9 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic188580030_P31.4900` |
| 188830138 | K | SUBMIT | 2 | None | 1.18114 | 0.401 | 11.5 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic188830138_P1.1811` |
| 193718989 | eM_slice | SUBMIT | 2 | None | 24.53354 | 1.842 | 10.4 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic193718989_P24.5335` |
| 201247574 | eM_slice | HOLD | None | H5 | 16.56043 | 1.206 | 10.1 | CLEAN | none | **incomplete** (none: 2) | `D:\tesshunter_s1\packets\s1_b1\tic201247574_P16.5604` |
| 207432717 | eM_slice | HOLD | None | H2 | 43.44707 | 1.928 | 11.5 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic207432717_P43.4471` |
| 233204110 | K | HOLD | None | H1 | 48.37713 | 0.829 | 9.3 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic233204110_P48.3771` |
| 245821988 | eM_slice | HOLD | None | H5 | 17.8537 | 0.565 | 7.8 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic245821988_P17.8537` |
| 246940708 | eM_slice | HOLD | None | H2 | 25.13681 | 5.39 | 28.3 | FLAG | 1 TCE | **incomplete** (none: 71) | `D:\tesshunter_s1\packets\s1_b1\tic246940708_P25.1368` |
| 259270670 | eM_slice | HOLD | None | H1 | 43.83609 | 2.232 | 7.3 | CLEAN | none | **incomplete** (none: 15,57,58,59,60,73,74,75,78) | `D:\tesshunter_s1\packets\s1_b1\tic259270670_P43.8361` |
| 262843927 | eM_slice | HOLD | None | H2 | 24.10889 | 0.87 | 8.9 | CLEAN | none | **incomplete** (none: 95,96,97) | `D:\tesshunter_s1\packets\s1_b1\tic262843927_P24.1089` |
| 270573718 | eM_slice | HOLD | None | H3 | 41.38386 | 1.499 | 9.9 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic270573718_P41.3839` |
| 335745090 | eM_slice | SUBMIT | 2 | None | 36.36634 | 0.976 | 7.5 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic335745090_P36.3663` |
| 382098683 | K | SUBMIT | 2 | None | 4.35128 | 0.427 | 10.7 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic382098683_P4.3513` |
| 423314730 | eM_slice | SUBMIT | 2 | None | 0.7448 | 0.298 | 9.5 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic423314730_P0.7448` |
| 458513927 | eM_slice | HOLD | None | K8_HOLD | 17.96227 | 1.978 | 9.3 | CLEAN | none | complete | `D:\tesshunter_s1\packets\s1_b1\tic458513927_P17.9623` |
