# K2 Part 3: sibling masking in Stage C (rule M1)

Dated 2026-10-15 (UTC). Prompt K2, Part 3. Tags: [M] measured, [A] adopted/registered, [I] interpretation.
Nothing here is a detection.

**Sources:**

* `k2/results/m1_m1_v3.json`;
* `k2/manifests/m1_v3_siblings.json`;
* receipts `D:/tesshunter_k2/funnel_receipts/m1_v3/{C,D}/`.

**Rules:** `k2/protocol/RULES_K2.md` section 4.

## 1. Outcome [A]

**M1 is adopted**, on top of V3.

* The siblings come from K1's S receipts, because A1 was not adopted.
* 14 R-C jobs have at least one sibling under the registered definition. All 14 are on DEV known-planet hosts;
  no injection-sample job has one.

| criterion | C1 (V3) | C1 + M1 | rule | outcome |
|---|---|---|---|---|
| DEV planets at the C endpoint (37 with an R-C path) | 30 | **31** | does not fall | holds |
| on the 12 multi-planet DEV hosts (8 planets with an R-C path) | 4 | **5** | rises by >= 1 | holds |
| DEV adversarial hosts gaining SUBMIT/HOLD | - | **0** (no M1 job on an adversarial host) | none | holds |
| injection-sample items at the endpoint (reported) | 47 / 58 | 47 / 58 | - | - |

## 2. Every decision that changed [M]

| job | planet | survey P | C1 | C1 + M1 | sibling masked | Stage D |
|---|---|---|---|---|---|---|
| dev_k1_144401492_p03 | TOI-1803 b | 6.288 d | FAIL (strongest 12.886 d = TOI-1803 c) | **PASS** 6.293 d, SDE 30.8 | p01, 12.886 d | KILL (K2: its K1 S gate under `bound` is not a pass, so the normal D route refuses) |
| dev_k1_63283780_p05 | Kepler-210 b | 2.453 d | FAIL (strongest 7.973 d = Kepler-210 c) | **PASS** 2.453 d, SDE 26.1 | p04, 7.973 d | SUBMIT, tier 2 (catalogue redacted) |
| dev_k1_229650439_p06 | TOI-1438 c | 9.428 d | PASS, SDE 55.9 | **FAIL**, SDE 3.6 | p08, 5.140 d (TOI-1438 b) | - |

The other 11 jobs are FAIL under both.

**The loss [M/I]:**

* For TOI-1438 c, the mask removed only 7 of the planet's 660 in-transit points. Its transit SNR is unchanged
  (21.7 -> 21.8), and the strongest peak is still at 9.428 d.
* But TLS's installed SDE fell from 55.9 to 3.6, while the robust SDE is 63.3.
* The spectrum concentration (0.25) is below the 0.5 trigger of the K1 robust fallback, so the frozen C rule
  reads 3.6 and fails.
* [I] Masking a strong signal's transits leaves periodic gaps that distort TLS's spectrum normalisation. The
  robust fallback, which exists for this, is not triggered. This is the frozen C rule behaving as registered,
  not an M1 implementation defect.

## 3. Operational note [M]

The first Stage D attempt on the 2 new passes was refused by D's record check: the Stage C record's rule stamp
was `p10.0`, while D computed `p10.0-partial`.

* The rule-set version string encodes the S mode: `bound_alias` gives `p10.0-partial`.
* The K2 D planner had forced `bound_alias`, but these DEV case roots ran K1's calibration S mode `bound`.
* The planner now uses the C runtime's own S mode (K1's `plan_d` rule). The 2 refused receipts are archived in
  `D:/tesshunter_k2/superseded/m1_v3_D_stamp_mismatch`, and the re-run (`m1_v3_D2`) completed 2/2.
