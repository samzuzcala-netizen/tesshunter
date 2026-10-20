# Completeness and the false-alarm budget at native cadence, through the funnel

Generated 2026-09-12T15:20:53Z by `p10/protocol/p10_completeness_calibration.py analyze` from `data/survey/p10/part2d/injection_search`, `data/survey/runs/p10_2b/e_fa` and the injection funnel under `data/survey/p10/part2d/calibration/inj_funnel/` (rules p10.0, config `survey_p10`). Every number is [M]. The pipeline finds candidates; nothing here is a detection.

## 1. What was measured

* Sample: 300 stars drawn at random (seed 20260904) from the 2,000-star `targets_p8.csv`; 2,100 batman injections (7 per star; period log-uniform in four equal-log bins over 0.5-30 d, radius log-uniform 1-4 Earth radii converted to Rp/R* per star, impact parameter uniform 0-0.9, quadratic limb darkening by Teff). Products are selected and brought to the common exposure first, then the model is multiplied into SAP and corrected flux before detrending and clipping, matching the completed search. Jobs by status: {'ok': 2100}; outcomes: {'recovered': 1240, 'missed': 765, 'alias': 95}.
* Recovery rule (fixed before the run, the prompt-2 rule): an accepted candidate with period within 1% of the injected period and overlapping transit windows; ratios 2, 3, 1/2, 1/3 are `alias` (reported, never credited).
* Expected SNR: the matched-filter SNR of the injected model on the star's own UN-injected prepared native-cadence series (sigma = 1.4826 x MAD per cadence).
* Through the gates: every recovered injection went through Stage A of the funnel (the prompt-6 event rules and six criteria at native cadence) and the full-phase secondary scan, with the products re-injected in memory; the real funnel's pre-gate (epoch-consistent, stitch SNR >= 7.1, >= 3 transits) is applied in the central whole-funnel curve and reported separately to show its losses.

Here, through-funnel completeness ends after the pre-gate, Stage A and secondary scan, as specified in Part 1e. The later Stage B, blind TLS and Stage D checks are not calibrated by this injection run; their losses can only reduce the number reaching a final verdict.

## 2. Recovery at each level

| level | through / injected | fraction | SNR50 (16-84%) | SNR90 (16-84%) |
|---|---:|---:|---|---|
| search only | 1,240 / 2,100 | 59.0% | 11.6 (11.3-11.9) | 29.8 (28.2-31.6) |
| search + pre-gate | 1,184 / 2,100 | 56.4% | 12.7 (12.5-13.0) | 30.1 (28.6-31.9) |
| search + Stage A | 1,164 / 2,100 | 55.4% | 13.0 (12.7-13.4) | 35.0 (33.0-37.3) |
| search + Stage A + secondary gate | 964 / 2,100 | 45.9% | 18.3 (17.7-19.0) | 77.0 (71.1-84.5) |
| the whole funnel (pre-gate, Stage A, secondary gate) | 952 / 2,100 | 45.3% | 18.6 (18.1-19.3) | 75.5 (69.8-82.7) |

### By expected SNR

| expected SNR | n | search only | whole funnel |
|---|---:|---:|---:|
| 0-5 | 309 | 6/309 (2%) | 1/309 (0%) |
| 5-7.1 | 197 | 13/197 (7%) | 0/197 (0%) |
| 7.1-9 | 145 | 44/145 (30%) | 23/145 (16%) |
| 9-12 | 195 | 104/195 (53%) | 79/195 (41%) |
| 12-20 | 363 | 267/363 (74%) | 202/363 (56%) |
| 20-50 | 625 | 560/625 (90%) | 440/625 (70%) |
| 50-1e+09 | 266 | 246/266 (92%) | 207/266 (78%) |

### By period bin, radius, Tmag and the rotation proxy

Every fraction uses all injected signals in the bin as its denominator. The last column is the central whole-funnel outcome.

| bin | n | recovered | search + A + secondary | search + pre-gate + A + secondary |
|---|---:|---:|---:|---:|
| period 0.50-1.39 d | 525 | 346/525 (66%) | 303/525 (58%) | 302/525 (58%) |
| period 1.39-3.87 d | 525 | 333/525 (63%) | 277/525 (53%) | 276/525 (53%) |
| period 3.88-10.76 d | 525 | 290/525 (55%) | 224/525 (43%) | 222/525 (42%) |
| period 10.80-29.96 d | 525 | 271/525 (52%) | 160/525 (30%) | 152/525 (29%) |
| radius 1.0-1.41 R_earth | 513 | 68/513 (13%) | 54/513 (11%) | 49/513 (10%) |
| radius 1.41-2.0 R_earth | 513 | 240/513 (47%) | 195/513 (38%) | 190/513 (37%) |
| radius 2.0-2.83 R_earth | 545 | 447/545 (82%) | 348/545 (64%) | 346/545 (63%) |
| radius 2.83-4.0 R_earth | 529 | 485/529 (92%) | 367/529 (69%) | 367/529 (69%) |
| Tmag 12.5-13.0 | 679 | 426/679 (63%) | 336/679 (49%) | 331/679 (49%) |
| Tmag 13.0-13.5 | 819 | 484/819 (59%) | 381/819 (47%) | 376/819 (46%) |
| Tmag 13.5-14.0 | 602 | 330/602 (55%) | 247/602 (41%) | 245/602 (41%) |
| Tmag 14.0-14.5 | 0 | 0/0 | 0/0 | 0/0 |
| rotation semi-amplitude 0.0-0.5 ppt | 1421 | 876/1421 (62%) | 756/1421 (53%) | 747/1421 (53%) |
| rotation semi-amplitude 0.5-1.0 ppt | 308 | 188/308 (61%) | 130/308 (42%) | 129/308 (42%) |
| rotation semi-amplitude 1.0-3.0 ppt | 210 | 124/210 (59%) | 51/210 (24%) | 49/210 (23%) |
| rotation semi-amplitude 3.0-10.0 ppt | 105 | 35/105 (33%) | 18/105 (17%) | 18/105 (17%) |
| rotation semi-amplitude 10.0-1000000000.0 ppt | 35 | 12/35 (34%) | 5/35 (14%) | 5/35 (14%) |
| rotation semi-amplitude 1000000000.0-inf ppt | 21 | 5/21 (24%) | 4/21 (19%) | 4/21 (19%) |

Rotation-proxy accounting: 0 missing/nonfinite; 21 injections on TICs [233622554, 233630091, 233731417] are in the explicit >= 1e+09 ppt bin. Extreme raw-photometry proxies are reported separately; this is not a physical rotation measurement or an exclusion gate.

### Period x expected SNR (search only)

| period bin \ SNR | 0-5 | 5-7.1 | 7.1-9 | 9-12 | 12-20 | 20-50 | 50-1e+09 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.50-1.39 d | 0/5 (0%) | 0/26 (0%) | 3/22 (14%) | 8/44 (18%) | 42/88 (48%) | 167/197 (85%) | 126/143 (88%) |
| 1.39-3.87 d | 1/40 (2%) | 1/55 (2%) | 6/36 (17%) | 28/51 (55%) | 71/93 (76%) | 156/178 (88%) | 70/72 (97%) |
| 3.88-10.76 d | 2/108 (2%) | 1/50 (2%) | 9/35 (26%) | 32/52 (62%) | 74/97 (76%) | 133/143 (93%) | 39/40 (98%) |
| 10.80-29.96 d | 3/156 (2%) | 11/66 (17%) | 26/52 (50%) | 36/48 (75%) | 80/85 (94%) | 104/107 (97%) | 11/11 (100%) |

### Period x expected SNR (search + pre-gate + A + secondary)

| period bin \ SNR | 0-5 | 5-7.1 | 7.1-9 | 9-12 | 12-20 | 20-50 | 50-1e+09 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.50-1.39 d | 0/5 (0%) | 0/26 (0%) | 2/22 (9%) | 6/44 (14%) | 39/88 (44%) | 145/197 (74%) | 110/143 (77%) |
| 1.39-3.87 d | 0/40 (0%) | 0/55 (0%) | 4/36 (11%) | 21/51 (41%) | 59/93 (63%) | 133/178 (75%) | 59/72 (82%) |
| 3.88-10.76 d | 0/108 (0%) | 0/50 (0%) | 6/35 (17%) | 27/52 (52%) | 58/97 (60%) | 100/143 (70%) | 31/40 (78%) |
| 10.80-29.96 d | 1/156 (1%) | 0/66 (0%) | 11/52 (21%) | 25/48 (52%) | 46/85 (54%) | 62/107 (58%) | 7/11 (64%) |

## 3. What the funnel does to a real signal

Of the recovered injections, 1240 have a Stage A record; decisions {'PASS': 1164, 'FAIL': 76, 'ERROR': 0, None: 0}. Criteria failing (a candidate can fail several): {'kept_events_ge_3': 12, 'top_share_le_50pct': 19, 'depths_consistent_p_ge_1e-3': 32, 'kept_snr_ge_7': 31, 'snr_without_top_ge_5': 22, 'depth_within_0.5_2x_survey': 9}.
Secondary gate on the 1164 Stage A passers, by variant (planets by construction): {'bound': {'PASS': 964, 'FAIL': 200}, 'quiet_bound': {'PASS': 1096, 'FAIL': 68}, 'quiet_zero': {'PASS': 1096, 'FAIL': 68}, 'quiet_bound_hold': {'PASS': 1026, 'FAIL': 68, 'HOLD': 70}, 'quiet_zero_N2': {'PASS': 1096, 'FAIL': 68}, 'quiet_zero_N3': {'PASS': 1071, 'FAIL': 93}, 'quiet_zero_N5': {'PASS': 1037, 'FAIL': 127}, 'quiet_bound_N2': {'PASS': 1096, 'FAIL': 68}, 'quiet_bound_N3': {'PASS': 1071, 'FAIL': 93}, 'quiet_bound_N5': {'PASS': 1037, 'FAIL': 127}}.

Depth-consistency p-values on the recovered injections (constant input depth; uniformity is the ideal error-model benchmark):

| errors | n | below 1e-3 (false-kill rate) | below 1e-2 | below 0.05 | p10 / p50 / p90 | KS uniform p |
|---|---:|---:|---:|---:|---|---:|
| white | 1240 | 10.0% | 21.0% | 35.6% | 0.001 / 0.131 / 0.706 | 1.1e-163 |
| inflated | 1240 | 2.6% | 6.2% | 16.5% | 0.024 / 0.353 / 0.879 | 1.6e-26 |

## 4. False alarms (the same stars, no injection)

| stage | candidates | per star |
|---|---:|---:|
| accepted by the search | 3,494 | 11.65 |
| past the pre-gate | 709 | 2.363 |
| past Stage A | 45 | 0.1500 |
| past the secondary gate | 2 | 0.0067 |

Stage A records: 709 of 709 pre-gate passers; 300 of 300 stars searched ok.
The seeded sample of 66 Stage A failures has secondary gates {'PASS': 41, 'FAIL': 25, 'HOLD': 0}; these are diagnostic and do not enter the passing false-alarm budget.
Stage A criterion failures (a candidate can fail several): {'kept_events_ge_3': 131, 'kept_snr_ge_7': 609, 'top_share_le_50pct': 340, 'snr_without_top_ge_5': 617, 'depths_consistent_p_ge_1e-3': 98, 'depth_within_0.5_2x_survey': 468}.

## 5. Wall clock

Search per injection job (cached products, no download): median / p90 / max [444.34680114999355, 1284.2754794299894, 1681.8797147999867] s; 463 jobs hit the detection budget. Stage A per candidate median / p90 [100.15, 517.1100000000001] s; secondary scan [4.4, 13.5] s.

## 6. Statistical assumptions [A]

The SNR curves use the prompt-2 two-parameter logistic model and 1,000 resamples of individual injections for the 16-84% intervals. Injections on the same star share its noise; these intervals do not model that within-star dependence or population-model uncertainty. SNR50 and SNR90 are fitted curve crossings, which can lie beyond the sampled SNR range.
The p-value distribution is conditional on recovery, ephemeris estimation and event removal. Its departure from uniformity is a diagnostic of the combined process, not an isolated test of the error bars. The measured fraction killed is still the calibration loss for those recovered injections. The rotation proxy is a sinusoidal fit to corrected photometry and can be dominated by extreme flux outliers.
