# Completeness, arm A (archival) under the frozen input policy

Generated 2026-09-25T23:08:08.740405+00:00 by `p12/protocol/report_calibration_p12.py`. Every number is [M]. Scope: injection completeness through S; C on the 30-injection sample; no injection runs through D.

## Recovery at each level

| level | through / injected | fraction | SNR50 (16-84%) | SNR90 (16-84%) |
|---|---:|---:|---|---|
| search only | 1,012 / 1,687 | 60.0% | 10.6 (10.4-10.9) | 22.5 (21.4-23.7) |
| search, alias credited | 1,064 / 1,687 | 63.1% | 9.6 (9.4-9.8) | 20.2 (19.2-21.3) |
| search + pre-gate | 969 / 1,687 | 57.4% | 11.6 (11.3-11.9) | 23.1 (22.0-24.2) |
| search + Stage A | 956 / 1,687 | 56.7% | 11.8 (11.5-12.1) | 26.1 (24.8-27.7) |
| search + Stage A + secondary gate | 794 / 1,687 | 47.1% | 16.2 (15.6-16.8) | 58.7 (54.0-64.1) |
| the whole funnel (pre-gate, Stage A, secondary gate) | 783 / 1,687 | 46.4% | 16.6 (16.0-17.2) | 58.0 (53.5-63.2) |
| policy loss (INPUT_INELIGIBLE hosts, not misses) | 413 of 2,100 injections | | | |
| operational unknowns (kept in every denominator, never misses) | 0 of 1,687 eligible | | | |

### By expected_snr

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 0-5 | 278 | 5/278 (2%) | 1/278 (0%) | 1/278 (0%) |
| 5-7.1 | 163 | 11/163 (7%) | 3/163 (2%) | 2/163 (1%) |
| 7.1-9 | 126 | 43/126 (34%) | 26/126 (21%) | 21/126 (17%) |
| 9-12 | 158 | 91/158 (58%) | 69/158 (44%) | 64/158 (41%) |
| 12-20 | 283 | 223/283 (79%) | 176/283 (62%) | 176/283 (62%) |
| 20-50 | 480 | 446/480 (93%) | 357/480 (74%) | 357/480 (74%) |
| 50-1e+09 | 199 | 193/199 (97%) | 162/199 (81%) | 162/199 (81%) |

### By period

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 0.5-1.39 | 423 | 278/423 (66%) | 240/423 (57%) | 240/423 (57%) |
| 1.39-3.87 | 423 | 283/423 (67%) | 240/423 (57%) | 237/423 (56%) |
| 3.88-10.76 | 422 | 243/422 (58%) | 185/422 (44%) | 183/422 (43%) |
| 10.8-29.96 | 417 | 208/417 (50%) | 129/417 (31%) | 123/417 (29%) |

### By radius

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 1-1.41 | 414 | 51/414 (12%) | 41/414 (10%) | 39/414 (9%) |
| 1.41-2 | 408 | 183/408 (45%) | 150/408 (37%) | 146/408 (36%) |
| 2-2.83 | 440 | 383/440 (87%) | 303/440 (69%) | 298/440 (68%) |
| 2.83-4 | 425 | 395/425 (93%) | 300/425 (71%) | 300/425 (71%) |

### By tmag

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 12.5-13 | 476 | 318/476 (67%) | 263/476 (55%) | 259/476 (54%) |
| 13-13.5 | 658 | 395/658 (60%) | 304/658 (46%) | 302/658 (46%) |
| 13.5-14 | 553 | 299/553 (54%) | 227/553 (41%) | 222/553 (40%) |

### By rotation

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 0-0.5 | 1155 | 730/1155 (63%) | 637/1155 (55%) | 631/1155 (55%) |
| 0.5-1 | 266 | 157/266 (59%) | 113/266 (42%) | 111/266 (42%) |
| 1-3 | 168 | 96/168 (57%) | 36/168 (21%) | 34/168 (20%) |
| 3-10 | 56 | 17/56 (30%) | 4/56 (7%) | 4/56 (7%) |
| 10-1e+09 | 21 | 7/21 (33%) | 0/21 (0%) | 0/21 (0%) |
| 1e+09-inf | 21 | 5/21 (24%) | 4/21 (19%) | 3/21 (14%) |

## False alarms on the E_cal stars (uninjected arrays)

| stage | count | per star |
|---|---:|---:|
| accepted | 2689 | 11.1577 |
| pregate | 480 | 1.9917 |
| A | 28 | 0.1162 |
| S | 3 | 0.0124 |
| B | 3 | 0.0124 |

Search operational unknowns: 0.

## Stage C on the 30-injection sample

{"FAIL": 10, "PASS": 20}
