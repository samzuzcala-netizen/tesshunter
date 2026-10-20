# SPECIFICITY_P12

Generated 2026-09-27T15:18:36.220050+00:00 by `p12/protocol/report_specificity_p12.py`. Every number is [M]; nothing in Part 4 changes a rule; a failure is a label.

## The launch bar

| clause | measured | N | Wilson 95% | threshold | printed |
|---|---:|---:|---|---|---|
| LB1a | 0 | 1 | 0.0-79.3% | <= 1 of N1 | NOT MEASURED |
| LB1b | 0 | 1 | 0.0-79.3% | <= 1 of N1_D | NOT MEASURED |
| LB2a | 0 | 13 | 0.0-22.8% | <= 1 of 13 | HOLDS |
| LB2b | 0 | 1 | 0.0-79.3% | <= 1 of N2_D | NOT MEASURED |
| LB3 | 0 | 0 | n/a | <= 1 of n_fit | NOT MEASURED |
| LB4 | 0.956989247311828 | 558 | 93.7-97.1% | >= 0.90 | HOLDS |

bar_met = **False** (bar_met = LB1a decisive AND every decisive clause holds; a non-decisive clause is NOT MEASURED). What N can detect: the Wilson 95% upper bound is 11.4% on 0 of 30, 16.7% on 1 of 30, 22.8% on 0 of 13, 43.4% on 0 of 5; the bar detects a gross specificity failure (one binary in ten passing) and cannot detect a 3% false-SUBMIT rate.

## Set (i): TESS Ten Thousand binaries, in-domain (LB1a, LB1b)

Targets 1; N1 (searched COMPLETE) 1; N1_D 1.

| stage | stars of N1 with a candidate there |
|---|---|
| accepted | 1 / 1 (100.0%, Wilson 95% 20.7-100.0%) (candidates: 11) |
| pregate | 1 / 1 (100.0%, Wilson 95% 20.7-100.0%) (candidates: 4) |
| A | 1 / 1 (100.0%, Wilson 95% 20.7-100.0%) (candidates: 2) |
| S | 0 / 1 (0.0%, Wilson 95% 0.0-79.3%) (candidates: 0) |
| B | 0 / 1 (0.0%, Wilson 95% 0.0-79.3%) (candidates: 0) |
| C_pass | 1 / 1 (100.0%, Wilson 95% 20.7-100.0%) (candidates: 1) |
| C_unresolved | 0 / 1 (0.0%, Wilson 95% 0.0-79.3%) (candidates: 0) |
| D | 1 / 1 (100.0%, Wilson 95% 20.7-100.0%) (candidates: 1) |
| SUBMIT | 0 / 1 (0.0%, Wilson 95% 0.0-79.3%) (candidates: 0) |

### Autopsies of every candidate that reached D

- **TIC 160492103 tic160492103_p01** (family ratio 1): verdict KILL (K2); fired H2, K2, K5, K6, K8; not measurable K0, H4; F5 {"localisation": "on_target_consistent", "n_sectors_measurable": 13, "per_sector": [{"sector": 56, "net_depth_ppt": 138.3418, "net_err_ppt": 1.3658, "k7_absent"; K10 None (None); catalogue redacted (4a).

## LB1c: adjacent domain (K and late-K dwarfs), not the M-dwarf domain (reported, never part of bar_met)

Targets 30; N1 (searched COMPLETE) 18; N1_D 4.

| stage | stars of N1 with a candidate there |
|---|---|
| accepted | 18 / 18 (100.0%, Wilson 95% 82.4-100.0%) (candidates: 140) |
| pregate | 18 / 18 (100.0%, Wilson 95% 82.4-100.0%) (candidates: 50) |
| A | 15 / 18 (83.3%, Wilson 95% 60.8-94.2%) (candidates: 25) |
| S | 0 / 18 (0.0%, Wilson 95% 0.0-17.6%) (candidates: 0) |
| B | 0 / 18 (0.0%, Wilson 95% 0.0-17.6%) (candidates: 0) |
| C_pass | 4 / 18 (22.2%, Wilson 95% 9.0-45.2%) (candidates: 4) |
| C_unresolved | 0 / 18 (0.0%, Wilson 95% 0.0-17.6%) (candidates: 0) |
| D | 4 / 18 (22.2%, Wilson 95% 9.0-45.2%) (candidates: 4) |
| SUBMIT | 0 / 18 (0.0%, Wilson 95% 0.0-17.6%) (candidates: 0) |

### Autopsies of every candidate that reached D

- **TIC 52245789 tic52245789_p01** (family ratio 1): verdict KILL (K2); fired H2, K2, K8; not measurable K0, H4; F5 {"localisation": "on_target_consistent", "n_sectors_measurable": 4, "per_sector": [{"sector": 68, "net_depth_ppt": 167.432, "net_err_ppt": 0.9334, "k7_absent": ; K10 None (None); catalogue redacted (4a).
- **TIC 188664469 tic188664469_p01** (family ratio 1): verdict KILL (K2); fired K2, K8; not measurable K0, H4; F5 {"localisation": "on_target_consistent", "n_sectors_measurable": 6, "per_sector": [{"sector": 57, "net_depth_ppt": 140.2336, "net_err_ppt": 1.4302, "k7_absent":; K10 None (None); catalogue redacted (4a).
- **TIC 160492103 tic160492103_p01** (family ratio 1): verdict KILL (K2); fired H2, K2, K5, K6, K8; not measurable K0, H4; F5 {"localisation": "on_target_consistent", "n_sectors_measurable": 13, "per_sector": [{"sector": 56, "net_depth_ppt": 138.3418, "net_err_ppt": 1.3658, "k7_absent"; K10 None (None); catalogue redacted (4a).
- **TIC 237912030 tic237912030_p01** (family ratio 1): verdict KILL (K2); fired K2; not measurable K0, H1, H4; F5 {"localisation": "unlocalised", "n_sectors_measurable": 4, "per_sector": [{"sector": 68, "net_depth_ppt": 11.594, "net_err_ppt": 0.341, "k7_absent": false, "not; K10 None (None); catalogue redacted (4a).

## Set (iii): the P9 held-out negatives (LB2a, LB2b)

LB2a 0 / 13 end to end; LB2b 0 / 1 at D (NOT MEASURED).

- **TIC 287669537 tic287669537_P1.2950** (family ratio None): verdict KILL (K2); fired K2, K8; not measurable none; F5 null; K10 None (None).

## The P9 positives

Blind leg: 0 of 13 signals reached D.
Ephemeris-assisted (LB3; ephemeris-assisted, not a funnel retention): 0 of n_fit 0 KILLed by K6, K8 or K10.

## Set (ii): natural load of the E_cal false-alarm stars (reported, not a bar clause)

stop-rule-2 form, a natural rate; unlabelled final-population stars: a SUBMIT here is a candidate listed with opened_in_part4, and its star's Part 5 verdict is the one delivered.

| stage | of the A passers |
|---|---|
| C_pass | 5 / 28 (17.9%, Wilson 95% 7.9-35.6%) |
| C_unresolved | 0 / 28 (0.0%, Wilson 95% 0.0-12.1%) |
| D | 5 / 28 (17.9%, Wilson 95% 7.9-35.6%) |
| SUBMIT | 0 / 28 (0.0%, Wilson 95% 0.0-12.1%) |
| HOLD | 0 / 28 (0.0%, Wilson 95% 0.0-12.1%) |
| KILL | 5 / 28 (17.9%, Wilson 95% 7.9-35.6%) |

## Zero-compute labelled rows

- set (i) S kills against SPOC DV secondary statistics (P12 sidecar): {"S_kills": 2, "with_a_TCE": 0, "label": "zero-compute, labelled; the sidecar carries no DV secondary statistic column, so the row lists the TCEs matched"}
- P8 170 and P10.3 24 S rejections against TESS-EB and VSX in the snapshot: {"label": "zero-compute, labelled; reported from the snapshot hard-stop table and the recorded rejections", "source": "p12/manifests/hard_stop_p12.json; data/survey/p8/secondary; p10/part3 secondary records"}
