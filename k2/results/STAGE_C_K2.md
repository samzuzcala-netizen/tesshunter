# K2 Part 1: a cheaper Stage C (rule C1)

Dated 2026-10-15 (UTC). Prompt K2, Part 1. Tags: [M] measured, [A] adopted/registered, [I] interpretation.
Nothing here is a detection.

**Sources:**

* `k2/results/c1_rc_v3a.json` (rule evaluation, per-job table);
* `k2/results/timing_rc_v3.json` and `timing_rc_v3a.json`;
* `k2/results/price_k2.json`, `survey_price_k2_part1.json`;
* receipts `D:/tesshunter_k2/funnel_receipts/rc_v3a/C/` (119) and `rc_v3/C/` (10, first registration).

**Rules:** `k2/protocol/RULES_K2.md` section 2 and AMENDMENT_K2_20261014_1.

## 1. Outcome [A]

**V3 (30-min bins, propagated bin errors, TLS oversampling 2 on baselines > 1,000 d) is adopted.** It was the first
variant in cost order and it meets (a)-(c) on all 119 R-C jobs, so V2, V4 and V1 were not run.

| criterion | result | rule | outcome |
|---|---|---|---|
| (a) C-endpoint retention, 58 injections + 37 DEV planets | **77 / 95 vs K1 75 / 95: +2.1 pp**, paired host bootstrap 95% [-2.1, +6.3] | >= -2 pp, lower bound >= -5 pp | PASS |
| (b) DEV adversarial jobs (K1 FAIL) now PASS | **0 of 5** | none | PASS |
| (c) median wall on >= 20-sector hosts (22 jobs) | **30,716 s -> 1,015 s: 30.2x** (median per-job ratio 29.2x) | >= 3x | PASS |

Run conditions [M]:

* 6 workers x 4 TLS threads, power throttling opted out, as K1's C phases.
* Concurrent phases: only network-bound ones (downloads and neighbour queries for the fresh set).
* 0 unknowns.

## 2. Speed-up by usable sectors [M]

| n_usable | jobs | K1 median wall | V3 median wall | median ratio |
|---|---|---|---|---|
| 0-8 | 64 | 923 s | 158 s | 6.1x |
| 8-13 | 29 | 2,213 s | 235 s | 8.6x |
| 13-20 | 4 | 4,777 s | 370 s | 14.0x |
| 20-30 | 5 | 29,655 s | 795 s | 35.0x |
| >= 30 | 17 | 31,450 s | 1,088 s | 29.0x |

* Total R-C job-wall: K1 220 h; V3 11.1 h.
* [I] The gain grows with baseline, which is where K1's cost was.
  * 30-min bins cut 200-s data 9x and 600-s data 3x.
  * Oversampling 2 cuts the period grid 1.5x on the 79 jobs with > 1,000-d baselines.

## 3. Agreement with K1 by usable-sector class [M]

| n_usable | jobs | same decision | same blind period (1%) |
|---|---|---|---|
| 0-8 | 64 | 62 | 61 |
| 8-13 | 29 | 26 | 25 |
| 13-20 | 4 | 3 | 3 |
| 20-30 | 5 | 5 | 5 |
| >= 30 | 17 | 17 | 17 |

## 4. Every decision that flipped, with its cause [M]

| job | survey P | K1 | V3 | cause |
|---|---|---|---|---|
| dev_k1_175532955_p01 | 11.660 d | PASS | FAIL | strongest peak 5.830 d (1:2 alias, SDE 67 in both); K1 passed the alias depth test (p 0.018); V3's TLS gives < 3 usable per-transit depths |
| dev_k1_63283780_p02 | 15.945 d | PASS | FAIL | same: 1:2 alias 7.973 d, SDE 43 / 41; < 3 usable per-transit depths under V3 |
| inj_137802649_2_k1_p02 | 11.661 d | PASS | FAIL | same: 1:2 alias 5.830 d, SDE 40 / 39; < 3 usable per-transit depths under V3 |
| inj_142091677_1_k1_p05 | 26.452 d | FAIL | PASS | K1 strongest peak a spurious 106.65 d (SDE 32); V3 strongest = survey period (SDE 21) |
| inj_148962167_1_k1_p05 | 12.068 d | FAIL | PASS | K1 strongest peak a spurious 51.39 d (SDE 26); V3 strongest = survey period (SDE 20) |
| inj_219004585_2_k1_p04 | 43.199 d | FAIL | PASS | K1 strongest peak 86.37 d (2:1 alias, fails its depth test); V3 strongest = survey period (SDE 58) |

[I] Two mechanisms explain the flips:

* **Losses: the 2:1 alias path.** On 30-min bins, TLS returns per-transit depth uncertainties for fewer
  transits, so the 2:1 alias rescue (`revet_p6.alias_depths_consistent`, >= 3 usable depths) fails more often.
  All three losses are survey candidates found at twice the true period.
* **Gains: spurious long-period peaks.** K1's native-cadence TLS sometimes prefers a spurious long-period peak
  (51-107 d). K1 lost 5 HELD-OUT planets this way. Binning removes some of these.

For the items of rule (a): one injection lost (inj_137802649_2), three injections gained. The two DEV flips
are paths of TOI-929 b (5.830 d) and Kepler-210 c (7.973 d). Each planet has a second matched path
(dev_k1_175532955_p03, dev_k1_63283780_p04) that reaches the endpoint under both K1 and V3, so the DEV planet
count at the endpoint is unchanged (30 of 37).

## 5. V3 as first registered (record only) [M]

The 10-job timing check under the registered `bin_lc` errors (label `rc_v3`) had the same speed. But 5 of 8
K1-PASS jobs failed: SDE at the true period was 2-6, against K1's 31-110.

* The in-bin-scatter error from 3-9 points per bin gave the top 1% of bins 49-73% of the chi-square weight
  (K1's native C input: 3-7%).
* AMENDMENT_K2_20261014_1 replaced it with the propagated error before any further measurement. Under the
  amendment the same 10 jobs agree with K1 on 9 decisions and recover the 10th.
* The amendment was written after seeing those 10 outcomes; C1 was decided on all 119.

## 6. Survey price with the V3 unit costs [M-based]

`price_survey_k1.py` logic, K1's list distribution, workers and margin; only Stage C unit costs replaced
(`k2/results/survey_price_k2_part1.json`).

| stage | K1 queue-hours | K2 (V3) queue-hours |
|---|---|---|
| search | 345 | 345 |
| A | 117 | 117 |
| S + B | 0.6 | 0.6 |
| C | **809** | **34** |
| D | 104 | 104 |
| **total** | **1,376 (~57 days)** | **601 (~25 days)** |

**C unit cost by n_usable** (mean, K1 -> V3):

| n_usable | K1 | V3 |
|---|---|---|
| 0-8 | 1,359 s | 153 s |
| 8-13 | 2,627 s | 248 s |
| 13-20 | 6,932 s | 395 s |
| 20-30 | 21,538 s | 746 s |
| >= 30 | 28,276 s | 1,037 s |

[I] Search (345 qh) is now the largest item, then A and D.

## 7. Budget check (K-B) [M]

The amended timing check priced Parts 1-4 at **45 queue-hours** expected (66 if V2, V4 and V1 had also been
needed), under the 120 queue-hour stop (`price_k2.json`).
