# Completeness, arm B (sml) under the frozen input policy

Generated 2026-10-01T15:05:48.023838+00:00 by `p12/protocol/report_calibration_p12.py`. Every number is [M]. Scope: injection completeness through S; C on the 30-injection sample; no injection runs through D.

## Recovery at each level

| level | through / injected | fraction | SNR50 (16-84%) | SNR90 (16-84%) |
|---|---:|---:|---|---|
| search only | 338 / 494 | 68.4% | 10.2 (9.8-10.6) | 20.9 (19.5-22.4) |
| search, alias credited | 368 / 494 | 74.5% | 8.9 (8.5-9.4) | 17.8 (16.6-19.1) |
| search + pre-gate | 321 / 494 | 65.0% | 11.2 (10.9-11.6) | 20.2 (18.9-21.4) |
| search + Stage A | 318 / 494 | 64.4% | 11.2 (10.9-11.6) | 21.7 (20.3-23.1) |
| search + Stage A + secondary gate | 293 / 494 | 59.3% | 12.1 (11.6-12.6) | 29.8 (26.9-32.8) |
| the whole funnel (pre-gate, Stage A, secondary gate) | 287 / 494 | 58.1% | 12.5 (12.0-13.0) | 29.0 (26.3-31.8) |
| policy loss (INPUT_INELIGIBLE hosts, not misses) | 106 of 600 injections | | | |
| operational unknowns (kept in every denominator, never misses) | 0 of 494 eligible | | | |

### By expected_snr

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 0-5 | 8 | 1/8 (12%) | 0/8 (0%) | 0/8 (0%) |
| 5-7.1 | 25 | 3/25 (12%) | 0/25 (0%) | 0/25 (0%) |
| 7.1-9 | 69 | 21/69 (30%) | 12/69 (17%) | 8/69 (12%) |
| 9-12 | 81 | 45/81 (56%) | 41/81 (51%) | 39/81 (48%) |
| 12-20 | 149 | 116/149 (78%) | 107/149 (72%) | 107/149 (72%) |
| 20-50 | 162 | 152/162 (94%) | 133/162 (82%) | 133/162 (82%) |
| 50-1e+09 | 0 | 0/0 | 0/0 | 0/0 |

### By period

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 0.5-1.39 | 112 | 56/112 (50%) | 53/112 (47%) | 53/112 (47%) |
| 1.39-3.87 | 123 | 82/123 (67%) | 76/123 (62%) | 76/123 (62%) |
| 3.88-10.76 | 126 | 89/126 (71%) | 76/126 (60%) | 75/126 (60%) |
| 10.8-29.96 | 133 | 111/133 (83%) | 88/133 (66%) | 83/133 (62%) |

### By radius

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 1-1.41 | 99 | 29/99 (29%) | 25/99 (25%) | 25/99 (25%) |
| 1.41-2 | 164 | 105/164 (64%) | 95/164 (58%) | 91/164 (55%) |
| 2-2.83 | 163 | 144/163 (88%) | 124/163 (76%) | 122/163 (75%) |
| 2.83-4 | 68 | 60/68 (88%) | 49/68 (72%) | 49/68 (72%) |

### By tmag

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 12.5-13 | 136 | 94/136 (69%) | 75/136 (55%) | 71/136 (52%) |
| 13-13.5 | 183 | 129/183 (70%) | 114/183 (62%) | 113/183 (62%) |
| 13.5-14 | 175 | 115/175 (66%) | 104/175 (59%) | 103/175 (59%) |

### By rotation

| bin | n | search only | through S | whole funnel |
|---|---:|---:|---:|---:|
| 0-0.5 | 335 | 247/335 (74%) | 226/335 (67%) | 224/335 (67%) |
| 0.5-1 | 86 | 51/86 (59%) | 45/86 (52%) | 43/86 (50%) |
| 1-3 | 50 | 28/50 (56%) | 14/50 (28%) | 12/50 (24%) |
| 3-10 | 13 | 4/13 (31%) | 3/13 (23%) | 3/13 (23%) |
| 10-1e+09 | 6 | 4/6 (67%) | 1/6 (17%) | 1/6 (17%) |
| 1e+09-inf | 4 | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |

## False alarms on the E_cal stars (uninjected arrays)

| stage | count | per star |
|---|---:|---:|
| accepted | 2728 | 11.3195 |
| pregate | 325 | 1.3485 |
| A | 27 | 0.1120 |
| S | 2 | 0.0083 |
| B | 0 | 0.0000 |

Search operational unknowns: 0.

## Stage C on the 30-injection sample

null
