# K2 validation (Part 4): G1-G3 on the fresh confirmatory set and the seen HELD-OUT set

Dated 2026-10-15 (UTC). Prompt K2, Part 4. Tags: [M] measured, [A] adopted/registered, [I] interpretation.
Nothing here is a detection.

**Sources:**

* `k2/results/gates_fresh.json`, `gates_seen.json` (with per-planet ledgers);
* prediction locks `k2/manifests/prediction_lock_fresh.json` (2,668 files, bundle e13f6cca...) and
  `prediction_lock_seen.json` (2,156 files, bundle 48d6d5cf...).

**Configuration (frozen):** `k2/protocol/config.json` (sha d47da619...) = K1's frozen configuration + Stage C
input V3 (30-min bins, propagated errors; AMENDMENT_K2_20261014_1) + M1 sibling masking; Stage A is K1's (A1 not
adopted).

**Arms:**

* the K2 arm under the frozen configuration;
* P12 = the isolated aee65172b copy (`survey_p10`, sectors 56-98, p10.0 funnel), on the same hosts.

**Procedure:**

1. Blind search.
2. Funnel, with Stage D catalogue-redacted.
3. Prediction lock.
4. Only then were the truth tables read; matching by RULES_K1 2.2 with amendments 4, 5 and 7.

## 1. Gates [A]

**Fresh set: the deciding set.** 64 planets in the G1 cohort (>= 20 required).

| gate | result | rule | outcome |
|---|---|---|---|
| **G1** | **38 / 64 = 59.4%** reach the Stage C endpoint (Wilson 47-71%; host bootstrap 47-72%); 55 hosts | >= 60% (39 / 64) | **FAIL, by one planet** |
| **G2** | K2 38 vs P12 31: **+10.9 pp** (host bootstrap -1.6 to +24.2); K2-only 13, P12-only 6 | >= -5 pp | PASS |
| **G3** | **0 / 70** fresh adversarial negatives reach SUBMIT (Wilson 0-5.2%); SUBMIT + HOLD 1 (EB TIC 311035838, HOLD) | <= 5% | PASS |

**Seen HELD-OUT set: "seen set, design-informed".** K1's 141 planets, 55 in the G1 cohort, and 53 negatives.

| gate | K2 | K1 (same set) | rule | outcome |
|---|---|---|---|---|
| **G1** | **31 / 55 = 56.4%** (Wilson 43-69%) | 29 / 55 = 52.7% | >= 60% | FAIL |
| **G2** | K2 31 vs P12 24: **+12.7 pp** (boot -2.0 to +26.4) | +9.1 pp | >= -5 pp | PASS |
| **G3** | **1 / 53** SUBMIT (1.9%; Wilson 0.3-9.9%); SUBMIT + HOLD 2 | 0 / 53 | <= 5% | PASS |

## 2. The one bounded repair: attribution of every fresh G1 loss [M]

26 cohort planets do not reach the C endpoint. Each is attributed to the last stage reached by its best matched
path.

| lost at | n | planets and cause |
|---|---|---|
| search | 1 | TOI-1064 c: no candidate near the period |
| A | 12 | see below |
| S (`bound_alias`) | 5 | see below |
| C | 8 | see below |

**Stage A losses (12):** TOI-125 c, TOI-332 b, TOI-2200 b (SNR 231), TOI-1782.01, TOI-1782.02, TOI-213 b,
TOI-2095 b, LHS 1903 c, LHS 1903 d, TOI-4342 b, TOI-1301.01, TOI-283 b.

* Every one fails `depths_consistent_p_ge_1e-3`, the frozen K1 criterion. A1 was not adopted.
* Some also fail the depth ratio or the top-event criteria.

**Stage S losses (5):** TOI-125 d, TOI-1245 b, TOI-1184 b, TOI-1472 b, K2-266 e. Each has a significant
secondary dip in SAP flux (phases 0.33-0.72) under the frozen `bound_alias` rule.

**Stage C losses (8):**

| planet | cause |
|---|---|
| K2-136 c, TOI-1064 b, Kepler-102 e, TOI-1798.01, TOI-783 b | blind strongest peak at a spurious long period (33-101 d); K1's (and P12's) frozen C weakness |
| TOI-4342 c | sibling substitution by TOI-4342 b (5.54 d). Not masked by M1 because b's own candidate failed Stage A (M1 masks only S-passers). |
| TOI-4405 b | 1:2 alias whose per-transit depths are inconsistent (chi2 72,692 / 84) |
| TOI-1739 b | 1:2 alias test fails on "fewer than 3 usable per-transit depths" (below) |

**TOI-1739 b in detail [M/I]:**

* On the 30-min C input, TLS fits a one-bin duration, so every transit holds one binned point. TLS reports zero
  uncertainty for such transits, and the frozen alias test discards them.
* This is the measured V3 trade-off counted in rule C1 (3 R-C flips by the same mechanism; net +2.1 pp).
* Changing it would change the alias test or its depth source: a method change, not a bug fix.

**Repair decision [A].** None of the 26 losses traces to a clear implementation defect.

* The A, S and C losses are the frozen criteria applied as registered.
* The one V3-specific loss is a measured property of the adopted variant.
* The fresh set has no Stage C errors.
* The repair clause excludes threshold or method changes.

**The bounded repair has nothing to fix, so G1 stands at 38/64 and the final state is NOT_READY.**

[I] G1 misses by one planet, and the 60% bar sits well inside its interval (47-71%). The measurement cannot
distinguish 59.4% from 60%; the registered rule is the point estimate.

## 3. All planets by expected SNR [M]

Reaching the C endpoint, K2 / P12:

| expected SNR | fresh n | fresh K2 | fresh P12 | seen n | seen K2 | seen P12 |
|---|---|---|---|---|---|---|
| < 7 | 72 | 0 | 0 | 65 | 0 | 0 |
| 7-10 | 13 | 2 | 0 | 4 | 0 | 0 |
| 10-15 | 15 | 9 | 0 | 10 | 4 | 0 |
| 15-20 | 19 | 9 | 2 | 7 | 5 | 2 |
| 20-30 | 37 | 25 | 18 | 20 | 9 | 7 |
| 30-40 | 9 | 3 | 4 | 14 | 9 | 5 |
| >= 40 | 18 | 10 | 9 | 21 | 13 | 12 |
| **all** | **183** | **58** | **33** | **141** | **40** | **26** |

Funnel, fresh K2 arm (all 183 planets):

| search | pre-gate | A | S | B | C |
|---|---|---|---|---|---|
| 95 | 92 | 75 | 69 | 69 | 58 |

Funnel, fresh P12 arm (all 183 planets):

| search | pre-gate | A | S | B | C |
|---|---|---|---|---|---|
| 70 | 57 | 51 | 41 | 41 | 33 |

* [I] The K2 configuration's advantage over P12 is again largest at expected SNR 10-20 (all sectors, more transits).
* [I] Stage A's depth-consistency criterion is now the largest single loss in the strong cohort: 12 of 26 fresh,
  5 of 24 seen.

## 4. Stage D outcomes of recovered planets [M]

Catalogue-redacted, k1.0 tiers.

| set | SUBMIT | HOLD | KILL |
|---|---|---|---|
| fresh (58) | 27 | 30 | 1 (TOI-1694 b: K8 density, P 3.8 d) |
| seen (40) | 23 | 15 | 2 (TOI-1174 b K6, TOI-2322 c K5, as in K1) |

## 5. What changed against K1 on the seen set [M]

* **Stage C, same 102 paths:** K1 PASS 49 -> K2 PASS 54. Flips: FAIL->PASS 8, PASS->FAIL 2, PASS->ERROR 1.
* **G1 C losses** 11 -> 9. M1 recovers TOI-1260 d and TOI-1260 .03, both lost to sibling substitution in K1.
* **G3:** the new SUBMIT is V1 blend TIC 1950736 (TOI-4610.01).
  * Its Stage C period and fit match K1's (P 3.112943 vs 3.112946 d; T0 within 1 min).
  * But Stage D's TESScut download returned no sector-44 cutout this time (K1 lacked sector 19 instead).
  * K7a (pixel offset) then fired in one sector instead of two, so the blend was not killed.
  * [I] A transient MAST gap in Stage D, not an effect of V3 or M1. The seen set was locked before this was
    understood, and the job was not re-run.

## 6. Exceptions and conditions [M]

* **Contention.** Every Part 4 phase ran oversubscribed (fresh A, the seen-set C and the P12-arm C at the same
  time). Decisions do not depend on wall-clock time, but the HELD-OUT/fresh C walls are inflated
  (`survey_price_k2_final_all_receipts.json`).
* **Unknowns.**
  * Seen C 5 / 102: K1's deterministic edge case on blend TIC 251857119 (4), plus 1 new deterministic TLS crash
    (`transit.reference_transit` on 2,970 binned points, a 0.58-d candidate; K1 had passed it).
  * Fresh: 0.
  * P12 arm: 10 hosts with no usable data in sectors >= 56, counted as P12 non-recoveries, as in K1.
* **Stage D timeouts.**
  * 6 jobs passed 5,400 s on many-sector hosts; 5 completed on the 4x retry.
  * The 6th had already written a COMPLETE receipt before its process hung. It was kept (P12 rule).
* **K-D pause.**
  * C: fell below 25 GB: Stage D's FPP cutouts went to lightkurve's home cache on C:.
  * With the user's decision, K2's 8 GB were moved to D:, the cache was redirected (`XDG_CACHE_HOME`), and Stage
    D resumed. No effect on results.
* **One fresh A candidate** (TIC 234211934 p01) passed A only on its 7,200-s retry, after the other candidates' S
  and B had run. It failed S, so no M1 sibling set changed.
