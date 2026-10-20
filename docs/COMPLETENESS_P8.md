# Completeness and the false-alarm budget at native cadence, through the funnel

Generated 2026-09-05T23:24:44Z by `scripts/p8_completeness.py analyze` from `data/survey/runs/inj_p8`, `data/survey/runs/fa_p8` and the injection funnel under `data/survey/p8/inj_funnel/` (rules p7.0, config `survey_p8`). Every number is [M]. The pipeline finds candidates; nothing here is a detection.

## 1. What was measured

* Sample: 300 stars drawn at random (seed 20260904) from the 2,000-star `targets_p8.csv`; 2,100 batman injections (7 per star; period log-uniform in four equal-log bins over 0.5-30 d, radius log-uniform 1-4 Earth radii converted to Rp/R* per star, impact parameter uniform 0-0.9, quadratic limb darkening by Teff). Products are selected and brought to the common exposure first, then the model is multiplied into SAP and corrected flux before detrending and clipping, matching the completed search. Jobs by status: {'ok': 2100}; outcomes: {'recovered': 1163, 'missed': 855, 'alias': 82}.
* Recovery rule (fixed before the run, the prompt-2 rule): an accepted candidate with period within 1% of the injected period and overlapping transit windows; ratios 2, 3, 1/2, 1/3 are `alias` (reported, never credited).
* Expected SNR: the matched-filter SNR of the injected model on the star's own UN-injected prepared native-cadence series (sigma = 1.4826 x MAD per cadence).
* Through the gates: every recovered injection went through Stage A of the funnel (the prompt-6 event rules and six criteria at native cadence) and the full-phase secondary scan, with the products re-injected in memory; the real funnel's pre-gate (epoch-consistent, stitch SNR >= 7.1, >= 3 transits) is applied in the central whole-funnel curve and reported separately to show its losses.

Here, through-funnel completeness ends after the pre-gate, Stage A and secondary scan, as specified in Part 1e. The later Stage B, blind TLS and Stage D checks are not calibrated by this injection run; their losses can only reduce the number reaching a final verdict.

## 2. Recovery at each level

| level | through / injected | fraction | SNR50 (16-84%) | SNR90 (16-84%) |
|---|---:|---:|---|---|
| search only | 1,163 / 2,100 | 55.4% | 13.2 (12.9-13.5) | 31.6 (30.1-33.3) |
| search + pre-gate | 1,121 / 2,100 | 53.4% | 14.1 (13.8-14.4) | 31.4 (29.9-33.0) |
| search + Stage A | 1,093 / 2,100 | 52.0% | 14.6 (14.3-15.0) | 36.7 (34.7-38.7) |
| search + Stage A + secondary gate | 904 / 2,100 | 43.0% | 20.2 (19.6-21.0) | 75.2 (69.7-81.9) |
| the whole funnel (pre-gate, Stage A, secondary gate) | 896 / 2,100 | 42.7% | 20.4 (19.8-21.2) | 74.0 (68.6-80.3) |

### By expected SNR

| expected SNR | n | search only | whole funnel |
|---|---:|---:|---:|
| 0-5 | 309 | 7/309 (2%) | 1/309 (0%) |
| 5-7.1 | 197 | 9/197 (5%) | 0/197 (0%) |
| 7.1-9 | 145 | 30/145 (21%) | 15/145 (10%) |
| 9-12 | 195 | 71/195 (36%) | 54/195 (28%) |
| 12-20 | 363 | 241/363 (66%) | 182/363 (50%) |
| 20-50 | 625 | 559/625 (89%) | 437/625 (70%) |
| 50-1e+09 | 266 | 246/266 (92%) | 207/266 (78%) |

### By period bin, radius, Tmag and the rotation proxy

Every fraction uses all injected signals in the bin as its denominator. The last column is the central whole-funnel outcome.

| bin | n | recovered | search + A + secondary | search + pre-gate + A + secondary |
|---|---:|---:|---:|---:|
| period 0.50-1.39 d | 525 | 320/525 (61%) | 276/525 (53%) | 276/525 (53%) |
| period 1.39-3.87 d | 525 | 303/525 (58%) | 256/525 (49%) | 255/525 (49%) |
| period 3.88-10.76 d | 525 | 279/525 (53%) | 218/525 (42%) | 216/525 (41%) |
| period 10.80-29.96 d | 525 | 261/525 (50%) | 154/525 (29%) | 149/525 (28%) |
| radius 1.0-1.41 R_earth | 513 | 34/513 (7%) | 26/513 (5%) | 25/513 (5%) |
| radius 1.41-2.0 R_earth | 513 | 202/513 (39%) | 167/513 (33%) | 164/513 (32%) |
| radius 2.0-2.83 R_earth | 545 | 445/545 (82%) | 347/545 (64%) | 343/545 (63%) |
| radius 2.83-4.0 R_earth | 529 | 482/529 (91%) | 364/529 (69%) | 364/529 (69%) |
| Tmag 12.5-13.0 | 679 | 401/679 (59%) | 314/679 (46%) | 310/679 (46%) |
| Tmag 13.0-13.5 | 819 | 453/819 (55%) | 360/819 (44%) | 358/819 (44%) |
| Tmag 13.5-14.0 | 602 | 309/602 (51%) | 230/602 (38%) | 228/602 (38%) |
| Tmag 14.0-14.5 | 0 | 0/0 | 0/0 | 0/0 |
| rotation semi-amplitude 0.0-0.5 ppt | 1421 | 825/1421 (58%) | 712/1421 (50%) | 706/1421 (50%) |
| rotation semi-amplitude 0.5-1.0 ppt | 308 | 171/308 (56%) | 117/308 (38%) | 115/308 (37%) |
| rotation semi-amplitude 1.0-3.0 ppt | 210 | 117/210 (56%) | 50/210 (24%) | 50/210 (24%) |
| rotation semi-amplitude 3.0-10.0 ppt | 105 | 34/105 (32%) | 17/105 (16%) | 17/105 (16%) |
| rotation semi-amplitude 10.0-1000000000.0 ppt | 35 | 12/35 (34%) | 5/35 (14%) | 5/35 (14%) |
| rotation semi-amplitude 1000000000.0-inf ppt | 21 | 4/21 (19%) | 3/21 (14%) | 3/21 (14%) |

Rotation-proxy accounting: 0 missing/nonfinite; 21 injections on TICs [233622554, 233630091, 233731417] are in the explicit >= 1e+09 ppt bin. Extreme raw-photometry proxies are reported separately; this is not a physical rotation measurement or an exclusion gate.

### Period x expected SNR (search only)

| period bin \ SNR | 0-5 | 5-7.1 | 7.1-9 | 9-12 | 12-20 | 20-50 | 50-1e+09 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.50-1.39 d | 0/5 (0%) | 0/26 (0%) | 1/22 (5%) | 3/44 (7%) | 28/88 (32%) | 162/197 (82%) | 126/143 (88%) |
| 1.39-3.87 d | 1/40 (2%) | 0/55 (0%) | 2/36 (6%) | 8/51 (16%) | 62/93 (67%) | 160/178 (90%) | 70/72 (97%) |
| 3.88-10.76 d | 2/108 (2%) | 2/50 (4%) | 5/35 (14%) | 26/52 (50%) | 72/97 (74%) | 133/143 (93%) | 39/40 (98%) |
| 10.80-29.96 d | 4/156 (3%) | 7/66 (11%) | 22/52 (42%) | 34/48 (71%) | 79/85 (93%) | 104/107 (97%) | 11/11 (100%) |

### Period x expected SNR (search + pre-gate + A + secondary)

| period bin \ SNR | 0-5 | 5-7.1 | 7.1-9 | 9-12 | 12-20 | 20-50 | 50-1e+09 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.50-1.39 d | 0/5 (0%) | 0/26 (0%) | 1/22 (5%) | 2/44 (5%) | 24/88 (27%) | 139/197 (71%) | 110/143 (77%) |
| 1.39-3.87 d | 0/40 (0%) | 0/55 (0%) | 1/36 (3%) | 5/51 (10%) | 54/93 (58%) | 136/178 (76%) | 59/72 (82%) |
| 3.88-10.76 d | 0/108 (0%) | 0/50 (0%) | 4/35 (11%) | 22/52 (42%) | 59/97 (61%) | 100/143 (70%) | 31/40 (78%) |
| 10.80-29.96 d | 1/156 (1%) | 0/66 (0%) | 9/52 (17%) | 25/48 (52%) | 45/85 (53%) | 62/107 (58%) | 7/11 (64%) |

## 3. What the funnel does to a real signal

Of the recovered injections, 1163 have a Stage A record; decisions {'PASS': 1093, 'FAIL': 70, 'ERROR': 0, None: 0}. Criteria failing (a candidate can fail several): {'kept_events_ge_3': 13, 'top_share_le_50pct': 21, 'depths_consistent_p_ge_1e-3': 34, 'kept_snr_ge_7': 24, 'snr_without_top_ge_5': 20, 'depth_within_0.5_2x_survey': 10}.
Secondary gate on the 1093 Stage A passers, by variant (planets by construction): {'bound': {'PASS': 904, 'FAIL': 189}, 'quiet_bound': {'PASS': 1032, 'FAIL': 61}, 'quiet_zero': {'PASS': 1032, 'FAIL': 61}, 'quiet_bound_hold': {'PASS': 969, 'FAIL': 61, 'HOLD': 63}, 'quiet_zero_N2': {'PASS': 1032, 'FAIL': 61}, 'quiet_zero_N3': {'PASS': 1006, 'FAIL': 87}, 'quiet_zero_N5': {'PASS': 968, 'FAIL': 125}, 'quiet_bound_N2': {'PASS': 1032, 'FAIL': 61}, 'quiet_bound_N3': {'PASS': 1006, 'FAIL': 87}, 'quiet_bound_N5': {'PASS': 968, 'FAIL': 125}}.

Depth-consistency p-values on the recovered injections (constant input depth; uniformity is the ideal error-model benchmark):

| errors | n | below 1e-3 (false-kill rate) | below 1e-2 | below 0.05 | p10 / p50 / p90 | KS uniform p |
|---|---:|---:|---:|---:|---|---:|
| white | 1163 | 10.7% | 21.5% | 35.4% | 0.001 / 0.131 / 0.705 | 9.8e-155 |
| inflated | 1163 | 2.9% | 7.1% | 16.4% | 0.019 / 0.361 / 0.878 | 5.2e-25 |

## 4. False alarms (the same stars, no injection)

| stage | candidates | per star |
|---|---:|---:|
| accepted by the search | 2,097 | 6.99 |
| past the pre-gate | 586 | 1.953 |
| past Stage A | 36 | 0.1200 |
| past the secondary gate | 2 | 0.0067 |

Stage A records: 586 of 586 pre-gate passers; 300 of 300 stars searched ok.
The seeded sample of 55 Stage A failures has secondary gates {'PASS': 32, 'FAIL': 23, 'HOLD': 0}; these are diagnostic and do not enter the passing false-alarm budget.
Stage A criterion failures (a candidate can fail several): {'kept_events_ge_3': 99, 'kept_snr_ge_7': 507, 'top_share_le_50pct': 291, 'snr_without_top_ge_5': 518, 'depth_within_0.5_2x_survey': 390, 'depths_consistent_p_ge_1e-3': 79}.

## 5. Wall clock

Search per injection job (cached products, no download): median / p90 / max [170.9215908000042, 450.46639037000244, 655.2262950000004] s; 773 jobs hit the detection budget. Stage A per candidate median / p90 [226.0, 1133.6] s; secondary scan [5.4, 18.479999999999997] s.

## 6. Statistical assumptions [A]

The SNR curves use the prompt-2 two-parameter logistic model and 1,000 resamples of individual injections for the 16-84% intervals. Injections on the same star share its noise; these intervals do not model that within-star dependence or population-model uncertainty. SNR50 and SNR90 are fitted curve crossings, which can lie beyond the sampled SNR range.
The p-value distribution is conditional on recovery, ephemeris estimation and event removal. Its departure from uniformity is a diagnostic of the combined process, not an isolated test of the error bars. The measured fraction killed is still the calibration loss for those recovered injections. The rotation proxy is a sinusoidal fit to corrected photometry and can be dominated by extreme flux outliers.
