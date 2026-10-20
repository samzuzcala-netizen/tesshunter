# K1 calibration (Part D): injections, false alarms, DEV sets

Dated 2026-10-12 (UTC). Prompt K1, Part D4. Tags: [M] measured, [A] adopted/registered, [I] interpretation.

**Sources:**

* `k1/results/calibration_partD.json`, under prediction lock `partD` (26,803 files, bundle 71f56386...);
* `e1e2_amended.json`, `decisions_E.json`;
* ledgers in `k1/results/ledgers/`.

All numbers are after AMENDMENT_K1_20261012_7 (evaluator: the candidate period in rule 2.2 is the stitch
re-measured period). The pre-fix values are kept in `*_prefix_amend7.json`. Intervals are host-bootstrap 95%
(2,000-4,000 resamples, seed 20261011) unless marked Wilson. Nothing here is a detection.

## 1. What was run [M]

* Searches (8,100 s budget):
  * 1,000 injections on 250 hosts (170 K, 80 eM; 4 per host), under survey_k1 and survey_k1_s56;
  * 250 uninjected false-alarm hosts under both arms;
  * 99 DEV hosts (64 known-planet, 35 adversarial) under survey_k1.
  * 2,599 jobs in all: 2,595 complete, plus 4 NO_DATA_IN_ARM. One injection host has no sector >= 56, so
    its 4 injections are s56 non-recoveries.
* Stage A, legacy and SAP-ramp variant: 17,622 jobs.
  * 36 deterministic errors: 18 pre-gate candidates whose duration is longer than P/2 (no out-of-transit
    baseline), each in both variants.
  * 2 timeouts at 7,200 s.
* Stage S, every mode from one scan: 3,623 jobs.
* DEV B / C / D: 61 C jobs. Hosts with 30-40 sectors needed 6-9 h each.
* Injection C sample: 58 of the 147 planned completed (AMENDMENT_K1_20261012_6, user decision).

## 2. Frozen configuration and rule outcomes [A]

| configuration item | value |
|---|---|
| arm | survey_k1 (all usable sectors 1-98) |
| search budget | 8,100 s |
| S mode | `bound_alias` |
| SAP-ramp rule | legacy |
| amendments in force | 1-7 (`k1/protocol/AMENDMENT_K1_*.md`) |

| rule | outcome (post amendment 7) |
|---|---|
| E1 as registered (`bound`) | +18.53 pp (42.9% vs 24.3%), [+13.11, +23.83]; FA ratio 1.22; wall ratio 1.69 -> **survey_k1** |
| E1 under `bound_alias` (amendment 3) | +23.94 pp (50.6% vs 26.6%), [+18.18, +29.55] -> survey_k1 |
| E2 | `bound_alias` 313, recurrent(_corr) 310, `empirical_bound` 289, `bound` 256 of 517; DEV adversarial pass-through 0/35 for every mode -> **`bound_alias`** |
| E3 | ramp 567 vs legacy 568 of 757 (-0.13 pp); A-level FA ratio 1.00 -> **not adopted** |
| E4 | partition-limited 37.5% / 20% / 15% at 2,700 / 5,400 / 8,100 s (pilot, n = 40) -> **8,100 s**, not qualified |

[A] Before amendment 7, E1 as registered failed (+2.70 pp). That led to the post-hoc AMENDMENT_K1_20261011_3,
chosen by the user. With the evaluator defect fixed, the registered rule gives survey_k1 by itself, so
amendment 3 no longer changes the outcome.

## 3. Completeness, survey_k1 arm (1,000 injections)

Columns give count (%; host-bootstrap 95%).

| expected SNR | n | search | pre-gate | A | S (`bound_alias`) |
|---|---|---|---|---|---|
| < 7 | 243 | 5 (2%; 0-4) | 0 | 0 | 0 |
| 7-10 | 85 | 23 (27%; 17-38) | 11 (13%; 6-21) | 8 (9%; 3-17) | 8 (9%; 3-17) |
| 10-15 | 93 | 59 (63%; 53-73) | 56 (60%; 49-70) | 55 (59%; 48-69) | 55 (59%; 48-69) |
| 15-20 | 81 | 73 (90%; 83-96) | 73 (90%; 83-96) | 72 (89%; 81-95) | 68 (84%; 75-91) |
| 20-30 | 108 | 100 (93%; 87-97) | 100 (93%; 87-97) | 88 (81%; 74-89) | 80 (74%; 65-82) |
| 30-40 | 72 | 72 (100%) | 72 (100%) | 68 (94%; 89-99) | 65 (90%; 83-96) |
| >= 40 | 318 | 315 (99%; 98-100) | 315 (99%; 98-100) | 277 (87%; 83-91) | 263 (83%; 78-87) |

**SNR50 / SNR90** (logistic in log SNR with a free plateau; 50% / 90% crossings):

| stage | SNR50 | SNR90 | plateau |
|---|---|---|---|
| search | 10.7 | 18.4 | 0.99 |
| pre-gate | 11.5 | 16.5 | 0.99 |
| A | 11.1 | not reached | 0.87 |
| S `bound` | 11.7 | not reached | 0.71 |
| S `bound_alias` | 11.05 | not reached | 0.83 |

The P10-convention two-parameter fit gives SNR50 10.9 (search) and 16.7 (S `bound_alias`).

**By period (S `bound_alias`):**

| period | retained |
|---|---|
| 0.5-1 d | 60% |
| 1-3 d | 65% |
| 3-10 d | 53% |
| 10-20 d | 51% |
| 20-50 d | 37% |

**By radius:**

| radius | retained |
|---|---|
| 1-1.5 Re | 8% |
| 1.5-2 Re | 37% |
| 2-2.83 Re | 55% |
| 2.83-4 Re | 69% |
| 4-8 Re | 83% |

**By Tmag:** 10-11: 68%; 11-12: 56%; 12-13.6: 43%.

**By usable sectors:** 5-7: 55%; 8-12: 60%; >= 13: 47%.

**By class:** K 59% (55-63); eM 43% (37-50).

These rows mix the injected SNR distribution of each bin. The SNR table above is the completeness function.

**Losses at A and S in the high-SNR bins.** At expected SNR >= 40, 87% pass A and 83% pass S.

* [M] The A losses are mainly the depth-consistency criterion at very high SNR, from sector-to-sector depth
  scatter of 3-5% (seen in the C4 pilot after amendment 2).
* [I] That is a property of the frozen p10.0 criterion, not a cadence defect; it is not changed.

**Stage C given S** (injection C sample, 58 completed of 147 planned; amendment 6):

| stratum | n | reach C | Wilson 95% |
|---|---|---|---|
| 7-10 | 0 | - | (borrows 10-15) |
| 10-15 | 13 | 7 (54%) | 29-77% |
| 15-20 | 10 | 6 (60%) | 31-83% |
| 20-40 | 25 | 22 (88%) | 70-96% |
| >= 40 | 10 | 10 (100%) | 72-100% |

By usable sectors:

| sectors | reach C |
|---|---|
| 0-8 | 17/20 |
| 8-13 | 14/23 |
| 13-20 | 2/3 |
| 20-30 | 4/4 |
| >= 30 | 8/8 |

[I] There is no sign that C retention is lower on long-baseline hosts, though those counts are small. Two
cautions about the sample:

* The truncation under-represents hosts with >= 13 sectors (15 of 51 planned completed).
* The sample was drawn with the pre-amendment-7 matcher, so injections whose only S-passing path had a drifting
  chunk period could not be selected.

**Through C** (S x C|S per bin):

| expected SNR | through C |
|---|---|
| 7-10 | 0.05 (C borrowed) |
| 10-15 | 0.32 |
| 15-20 | 0.50 |
| 20-40 | 0.71 |
| >= 40 | 0.83 |

**Yield-model curve** (yieldlib form, cmax / (1 + exp(-(SNR - x50) / w))) for Part G:

| curve | x50 | w | cmax |
|---|---|---|---|
| through C | 14.4 | 2.4 | 0.79 |
| through S | 10.7 | 0.9 | 0.82 |
| review USER model (Oct 3-4) | 12.5 | 2.5 | 0.65 |

## 4. False alarms per star (250 uninjected FA hosts) [M]

| arm | pre-gate | A (legacy) | A (ramp) | S `bound` | S `bound_alias` | partition-limited |
|---|---|---|---|---|---|---|
| survey_k1 | 2.69 | 0.088 | 0.088 | 0.040 | 0.088 | 14.4% |
| survey_k1_s56 | 2.21 | 0.096 | 0.092 | 0.040 | 0.080 | 0.0% |

* [M] The injection searches were partition-limited at 9.1% (survey_k1) and 0.3% (survey_k1_s56).
* [I] About 9 natural false alarms per 100 stars survive S under the frozen mode. B passes almost everything,
  so these set the survey's Stage C load.

## 5. DEV sets [M]

* **DEV known planets** (78 planets on 64 hosts, survey_k1, catalogue redacted at D):

  | stage | reached |
  |---|---|
  | search | 46 |
  | pre-gate | 44 |
  | A | 39 |
  | S (`bound_alias`) | 37 |
  | B | 37 |
  | C | 30 |

  At D: 6 SUBMIT, 18 HOLD, 6 KILL.
* **DEV adversarial negatives** (35 hosts): 0 reached SUBMIT or HOLD, under every S mode.

## 6. Defects found and fixed during Parts C-D (evaluator or protocol, each with an amendment) [M]

1. **Stage A per-event depth on mixed exposures (amendment 2).** The C4 pilot's Stage A killed 10 high-SNR
   injections on depth consistency. The fix is an exposure-integrated limb-darkened template; it took the pilot
   from 15 to 19 of 26.
2. **Evaluator candidate period (amendment 7).** The identity rule used chunk-level periods, which drift over
   the ~7-year baseline. 117 of 119 high-SNR "misses" were matching failures. The fix raised the search plateau
   from 0.64 to 0.99.
3. **Adversarial path definitions (amendments 4-5).** These were written before Part F.

Operational findings:

* Windows power throttling confined hidden workers to the E-cores. Non-search phases now opt out;
  searches keep the default, as calibrated.
* Timed-out jobs get 4x their deadline on retry.
* The duration > P/2 geometry errors are deterministic: 18 candidates, 0.2% of pre-gate. A pre-gate check would
  turn them into rejections; this is not adopted.
* Stage C blind TLS on 30-40-sector hosts takes 6-9 h per candidate (~20-30 CPU-h). This dominates the survey
  price (`k1/results/survey_price.json`).

## 7. Unmeasured or weakly measured

* C | S below expected SNR 10: no sample item completed.
* C | S on >= 13-sector hosts: 15 items.
* Stage D on injections: not run (DEV only).
* Partition-limited hosts are 9-14% of survey_k1 hosts at 8,100 s. Searches in Part F ran somewhat faster than
  in Part D (power-throttling shift; see RESUME).
