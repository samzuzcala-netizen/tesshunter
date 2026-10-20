# COMPLETENESS_P12

Generated 2026-10-01T09:24:32.878826+00:00 by `p12/protocol/report_completeness_p12.py`. Every number is [M] unless marked.

**Scope.** injection completeness is measured through S, with C on the 30-injection sample; no injection runs through D; D-level behaviour on planets is measured only by LB3 on the 12 ephemeris-assisted P9 hosts; the delivered list is end to end, and its D-level completeness is not calibrated by injections.

Frozen input: arm A (KEEP_ARCHIVAL).

## 1. Injection recovery under p12.0 on the frozen input

Scope (header): injection completeness is measured through S, with C on the 30-injection sample; no injection runs through D; D-level behaviour on planets is measured only by LB3 on the 12 ephemeris-assisted P9 hosts; the delivered list is end to end, and its D-level completeness is not calibrated by injections.

| level | through / injected | SNR50 | SNR90 |
|---|---:|---:|---:|
| search only | 1,012 / 1,687 | 10.6 | 22.5 |
| search, alias credited | 1,064 / 1,687 | 9.6 | 20.2 |
| search + pre-gate | 969 / 1,687 | 11.6 | 23.1 |
| search + Stage A | 956 / 1,687 | 11.8 | 26.1 |
| search + Stage A + secondary gate | 794 / 1,687 | 16.2 | 58.7 |
| the whole funnel (pre-gate, Stage A, secondary gate) | 783 / 1,687 | 16.6 | 58.0 |
| policy loss (INPUT_INELIGIBLE hosts, not misses) | 413 of 2,100 | | |

### By radius

| bin | n | search | through S | whole funnel |
|---|---:|---:|---:|---:|
| 1-1.41 | 414 | 51/414 (12.3%) | 41/414 (9.9%) | 39/414 (9.4%) |
| 1.41-2 | 408 | 183/408 (44.9%) | 150/408 (36.8%) | 146/408 (35.8%) |
| 2-2.83 | 440 | 383/440 (87.0%) | 303/440 (68.9%) | 298/440 (67.7%) |
| 2.83-4 | 425 | 395/425 (92.9%) | 300/425 (70.6%) | 300/425 (70.6%) |

### By period

| bin | n | search | through S | whole funnel |
|---|---:|---:|---:|---:|
| 0.5-1.39 | 423 | 278/423 (65.7%) | 240/423 (56.7%) | 240/423 (56.7%) |
| 1.39-3.87 | 423 | 283/423 (66.9%) | 240/423 (56.7%) | 237/423 (56.0%) |
| 3.88-10.76 | 422 | 243/422 (57.6%) | 185/422 (43.8%) | 183/422 (43.4%) |
| 10.8-29.96 | 417 | 208/417 (49.9%) | 129/417 (30.9%) | 123/417 (29.5%) |

### By tmag

| bin | n | search | through S | whole funnel |
|---|---:|---:|---:|---:|
| 12.5-13 | 476 | 318/476 (66.8%) | 263/476 (55.3%) | 259/476 (54.4%) |
| 13-13.5 | 658 | 395/658 (60.0%) | 304/658 (46.2%) | 302/658 (45.9%) |
| 13.5-14 | 553 | 299/553 (54.1%) | 227/553 (41.0%) | 222/553 (40.1%) |

### By rotation

| bin | n | search | through S | whole funnel |
|---|---:|---:|---:|---:|
| 0-0.5 | 1155 | 730/1155 (63.2%) | 637/1155 (55.2%) | 631/1155 (54.6%) |
| 0.5-1 | 266 | 157/266 (59.0%) | 113/266 (42.5%) | 111/266 (41.7%) |
| 1-3 | 168 | 96/168 (57.1%) | 36/168 (21.4%) | 34/168 (20.2%) |
| 3-10 | 56 | 17/56 (30.4%) | 4/56 (7.1%) | 4/56 (7.1%) |
| 10-1e+09 | 21 | 7/21 (33.3%) | 0/21 (0.0%) | 0/21 (0.0%) |
| 1e+09-1.79769e+308 | 21 | 5/21 (23.8%) | 4/21 (19.0%) | 3/21 (14.3%) |

C retention on the 30-injection sample: {"FAIL": 10, "PASS": 20}.

SNR50 and SNR90 of P10 for comparison: `COMPLETENESS_P10.md` (pre-P11 sector set) [P10].

## 2. Real-signal retention on the 436 (development-exposed, EB-contaminated)

Part 2 search-level recovery [M]: {"independent_present": {"stratum": "INDEPENDENT", "present_families": 377, "recovered": 156, "fraction": 0.41379310344827586, "ci95": [0.35308627347726873, 0.47928994082840237], "hosts": 173, "per_host": {"21028557": {"recovered": 0, "present": 1}, "29002055": {"recovered": 0, "present": 4}, "30186108": {"recovered": 1, "present": 1}, "30719871": {"recovered": 0, "present": 1}, "31020027": {"recovered": 1, "present": 1}, "31109583": {"recovered": 2, "present": 2}, "32090581": {"recovered": 2, "present": 3}, "33866201": {"recovered": 1, "present": 3}, "33878971": {"recovered": 2, "present": 5}, "47424649": {"recovered": 0, "present": 1}, "52284854": {"recovered": 1, "present": 1}, "55387764": {"recovered": 0, "present": 1}, "91449810": {"recovered": 0, "present": 1}, "138399197": {"recovered": 1, "present": 2}, "141271216": {"recovered": 0, "present": 1}, "149216532": {"recovered": 0, "present": 3}, "150066550": {"recovered": 2, "present": 6}, "159508998": {"recovered": 1, "present": 1}, "159510452": {"recovered": 1, "present": 2}, "160118032": {"recovered": 0, "present": 2}, "160272538": {"recovered": 2, "present": 2}, "160419850": {"recovered": 1, "present": 1}, "160491815": {"recovered": 3, "present": 3}, "160535706": {"recovered": 1, "present": 1}, "160536227": {"recovered": 1, "present": 2}, "160602230": {"recovered": 2, "present": 3}, "161725589": {"recovered": 1, "present": 1}, "165528645": {"recovered": 1, "present": 1}, "165530589": {"recovered": 2, "present": 4}, "167244982": {"recovered": 1, "present": 1}, "167603285": {"recovered": 0, "present": 1}, "167754525": {"recovered": 2, "present": 2}, "177033503": {"recovered": 1, "present": 4}, "177352028": {"recovered": 1, "present": 1}, "177352893": {"recovered": 1, "present": 4}, "177389302": {"recovered": 1, "present": 1}, "179381768": {"recovered": 0, "present": 3}, "188600399": {"recovered": 2, "present": 2}, "188626183": {"recovered": 0, "present": 1}, "188777430": {"recovered": 0, "present": 3}, "188819782": {"recovered": 0, "present": 4}, "198185267": {"recovered": 0, "present": 1}, "198189672": {"recovered": 1, "present": 1}, "198236067": {"recovered": 1, "present": 3}, "198407957": {"recovered": 2, "present": 5}, "198410955": {"recovered": 0, "present": 1}, "198557860": {"recovered": 2, "present": 4}, "199573123": {"recovered": 3, "present": 6}, "200769811": {"recovered": 1, "present": 1}, "201248233": {"recovered": 1, "present": 1}, "207142605": {"recovered": 0, "present": 1}, "214709620": {"recovered": 1, "present": 1}, "219105733": {"recovered": 1, "present": 1}, "219468088": {"recovered": 0, "present": 1}, "219518400": {"recovered": 0, "present": 1}, "219773818": {"recovered": 1, "present": 1}, "219793020": {"recovered": 1, "present": 2}, "219797811": {"recovered": 2, "present": 2}, "219798240": {"recovered": 0, "present": 1}, "219806427": {"recovered": 1, "present": 1}, "219816797": {"recovered": 1, "present": 1}, "219818112": {"recovered": 1, "present": 2}, "219878156": {"recovered": 0, "present": 1}, "224601129": {"recovered": 2, "present": 7}, "224608234": {"recovered": 2, "present": 3}, "229406415": {"recovered": 0, "present": 1}, "229615901": {"recovered": 0, "present": 1}, "229670194": {"recovered": 0, "present": 1}, "229675969": {"recovered": 0, "present": 3}, "229738650": {"recovered": 1, "present": 2}, "229764903": {"recovered": 0, "present": 1}, "229781039": {"recovered": 0, "present": 1}, "229796245": {"recovered": 2, "present": 8}, "230073281": {"recovered": 2, "present": 6}, "230081659": {"recovered": 1, "present": 1}, "230090756": {"recovered": 1, "present": 2}, "230129453": {"recovered": 2, "present": 2}, "230131178": {"recovered": 1, "present": 4}, "232521209": {"recovered": 1, "present": 3}, "232616019": {"recovered": 2, "present": 5}, "232616666": {"recovered": 0, "present": 6}, "233045481": {"recovered": 1, "present": 1}, "233060572": {"recovered": 1, "present": 5}, "233070089": {"recovered": 2, "present": 2}, "233192430": {"recovered": 1, "present": 1}, "233233165": {"recovered": 1, "present": 3}, "233533428": {"recovered": 1, "present": 1}, "233544878": {"recovered": 0, "present": 2}, "233547261": {"recovered": 2, "present": 4}, "233570240": {"recovered": 1, "present": 2}, "233657141": {"recovered": 2, "present": 4}, "235568228": {"recovered": 0, "present": 1}, "235684525": {"recovered": 1, "present": 1}, "235936782": {"recovered": 1, "present": 1}, "236760750": {"recovered": 0, "present": 1}, "237108542": {"recovered": 2, "present": 3}, "237201422": {"recovered": 0, "present": 1}, "237280122": {"recovered": 1, "present": 1}, "237940278": {"recovered": 2, "present": 2}, "238891168": {"recovered": 0, "present": 1}, "255747145": {"recovered": 0, "present": 1}, "258955379": {"recovered": 2, "present": 2}, "259100107": {"recovered": 1, "present": 1}, "259131513": {"recovered": 0, "present": 1}, "259374524": {"recovered": 1, "present": 1}, "260271317": {"recovered": 0, "present": 2}, "262110281": {"recovered": 0, "present": 2}, "264004258": {"recovered": 1, "present": 1}, "270186294": {"recovered": 0, "present": 1}, "270491761": {"recovered": 1, "present": 1}, "271891098": {"recovered": 2, "present": 2}, "272703569": {"recovered": 0, "present": 2}, "273550461": {"recovered": 1, "present": 1}, "278776514": {"recovered": 0, "present": 1}, "279574462": {"recovered": 1, "present": 1}, "282923395": {"recovered": 1, "present": 1}, "284190375": {"recovered": 1, "present": 2}, "284762958": {"recovered": 0, "present": 1}, "287400661": {"recovered": 1, "present": 1}, "287438823": {"recovered": 0, "present": 7}, "288268554": {"recovered": 1, "present": 1}, "288611627": {"recovered": 1, "present": 1}, "293164461": {"recovered": 0, "present": 3}, "298264674": {"recovered": 2, "present": 2}, "300561485": {"recovered": 0, "present": 2}, "302426993": {"recovered": 0, "present": 2}, "309618860": {"recovered": 1, "present": 1}, "314825931": {"recovered": 0, "present": 2}, "322949743": {"recovered": 2, "present": 2}, "329248235": {"recovered": 0, "present": 1}, "336077042": {"recovered": 0, "present": 2}, "350734035": {"recovered": 2, "present": 2}, "350824771": {"recovered": 0, "present": 1}, "353808664": {"recovered": 1, "present": 1}, "353898013": {"recovered": 1, "present": 16}, "356975864": {"recovered": 3, "present": 4}, "357045188": {"recovered": 0, "present": 6}, "357045189": {"recovered": 2, "present": 5}, "359388713": {"recovered": 0, "present": 2}, "364588832": {"recovered": 1, "present": 1}, "367856004": {"recovered": 1, "present": 1}, "367856400": {"recovered": 0, "present": 1}, "375059160": {"recovered": 0, "present": 1}, "375145971": {"recovered": 1, "present": 1}, "376870091": {"recovered": 1, "present": 2}, "376928980": {"recovered": 2, "present": 4}, "377165060": {"recovered": 1, "present": 1}, "382635553": {"recovered": 0, "present": 1}, "383553281": {"recovered": 2, "present": 2}, "388106735": {"recovered": 1, "present": 5}, "394121998": {"recovered": 0, "present": 2}, "394122618": {"recovered": 0, "present": 2}, "394590611": {"recovered": 1, "present": 1}, "410213494": {"recovered": 0, "present": 1}, "420947477": {"recovered": 0, "present": 1}, "424389265": {"recovered": 1, "present": 2}, "428888136": {"recovered": 0, "present": 1}, "428991040": {"recovered": 2, "present": 3}, "431479577": {"recovered": 2, "present": 2}, "441740483": {"recovered": 4, "present": 4}, "441795882": {"recovered": 3, "present": 4}, "441804260": {"recovered": 1, "present": 1}, "441811894": {"recovered": 0, "present": 2}, "445854456": {"recovered": 0, "present": 1}, "458481937": {"recovered": 1, "present": 1}, "459189437": {"recovered": 0, "present": 2}, "459192460": {"recovered": 1, "present": 2}, "459979376": {"recovered": 1, "present": 2}, "461579141": {"recovered": 2, "present": 3}, "461597569": {"recovered": 1, "present": 5}, "462616035": {"recovered": 1, "present": 1}, "462637035": {"recovered": 1, "present": 1}, "470679985": {"recovered": 1, "present": 5}}, "bootstrap": {"seed": 2026092001, "draws": 10000, "bit_generator": "PCG64", "unit": "whole host"}}}.
P10.3 funnel [P10.3]: 156/377 INDEPENDENT present families recovered; 174 -> 131 -> 37 -> 13 -> 13 through the funnel.
Part 5 on the same hosts, re-matched after the lock through C and D: see `docs/AUDIT_P12.md` [M, "same hosts, final search"].

## 3. False-alarm and independent-negative rates per stage

Part 2 false alarms per E_cal star: {"accepted": 11.157676348547717, "pregate": 1.991701244813278, "A": 0.11618257261410789, "S": 0.012448132780082987, "B": 0.012448132780082987}.
Part 5 natural load, p8_2000: {"accepted": 10.2731, "pregate": 2.029, "A": 0.1282, "A_unknown": 0.0049, "S": 0.016, "S_on_A_fail_sample": 0.09, "B": 0.016, "C_pass": 0.0025, "C_unresolved": 0.0, "D": 0.0025, "SUBMIT": 0.0006, "HOLD": 0.0018, "KILL": 0.0} per star.
Part 5 natural load, p10_436: {"accepted": 8.8165, "pregate": 2.5206, "A": 0.6697, "A_unknown": 0.0161, "S": 0.0665, "S_on_A_fail_sample": 0.0872, "B": 0.0665, "C_pass": 0.0275, "C_unresolved": 0.0, "D": 0.0275, "SUBMIT": 0.0, "HOLD": 0.0115, "KILL": 0.0161} per star.
Part 5 natural load, E1: {"accepted": 10.0562, "pregate": 2.1767, "A": 0.2096, "A_unknown": 0.0096, "S": 0.0342, "S_on_A_fail_sample": 0.1151, "B": 0.0342, "C_pass": 0.0027, "C_unresolved": 0.0, "D": 0.0027, "SUBMIT": 0.0014, "HOLD": 0.0, "KILL": 0.0014} per star.
Part 4 TTT negatives: LB1a 0 / 1, LB1b 0 / 1 (Wilson intervals in SPECIFICITY_P12.md).

## 4. What the frozen pipeline recovers, by class

At radius 1 to 1.41 Re the frozen pipeline recovers 41/414 (9.9%) of injected planets on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S.
At radius 1.41 to 2 Re the frozen pipeline recovers 150/408 (36.8%) of injected planets on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S.
At radius 2 to 2.83 Re the frozen pipeline recovers 303/440 (68.9%) of injected planets on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S.
At radius 2.83 to 4 Re the frozen pipeline recovers 300/425 (70.6%) of injected planets on stars of Tmag 12.5 to 14 with at least 3 policy sectors through the funnel to S.
At P in [0.5, 1.39] d the frozen pipeline recovers 240/423 (56.7%) of injected planets of 1 to 4 Re through the funnel to S.
At P in [1.39, 3.87] d the frozen pipeline recovers 240/423 (56.7%) of injected planets of 1 to 4 Re through the funnel to S.
At P in [3.88, 10.76] d the frozen pipeline recovers 185/422 (43.8%) of injected planets of 1 to 4 Re through the funnel to S.
At P in [10.8, 29.96] d the frozen pipeline recovers 129/417 (30.9%) of injected planets of 1 to 4 Re through the funnel to S.

Stated limits: the S gate's 17.2% false kill (200 / 1,164, `stop_rule_1_decision.json`); the photometry test was flux-level (no dilution or throughput); the pixel lever is untested; sectors above 105 are counted, not searched; stars removed by the input policy are the policy-loss row.

S modes (report-only): {"utc": "2026-09-26T13:28:14.439840+00:00", "table": [{"mode": "bound", "false_kill_rate": 0.1729185727355901, "n_false_kills": 189, "kill_retention": 1.0, "kills_retained": 26, "tic233007823_fail": true, "eligible": true}, {"mode": "empirical_bound", "false_kill_rate": 0.12168344007319305, "n_false_kills": 133, "kill_retention": 0.8076923076923077, "kills_retained": 21, "tic233007823_fail": true, "eligible": false}, {"mode": "recurrent_bound", "false_kill_rate": 0.036596523330283626, "n_false_kills": 40, "kill_retention": 0.6923076923076923, "kills_retained": 18, "tic233007823_fail": true, "e

## 5. The extension

See `COMPLETENESS_EXT.md`: 600 injections, whole funnel 213.

## 6. The yield model

| model | through S on the 2,000 | observed |
|---|---:|---:|
| model (DC15, claimed fraction 0.03, never validated by an observed count) | 21.09 [P10] | 26 |

No forecast of the candidate count is made.

## Closing sentence (6b)

The registered P12 work on these inputs is complete; these measurements bound what it can find, and the specific experiments that could move those bounds are pixel-level photometry, the only untested input change with a measured noise lever; a detrending-window test on the 2b instrument (about 20 queue-hours); an unexposed in-domain truth-positive set, which the records do not contain.

## 7. Assumptions

The assumptions of `PROMPT_P12.md` section 9 hold as registered; each measured one is reported in its section above (9.1 costs, 9.2 false-alarm rates, 9.3 C cost, 9.4 D cost, 9.5 eligibility, 9.6 SML, 9.7 TTT, 9.8 P9 hosts).
