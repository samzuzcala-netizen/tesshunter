# K1 validation gate (Part F): HELD-OUT known planets and negatives

Dated 2026-10-14 (UTC). Prompt K1, Part F. Tags: [M] measured, [A] adopted/registered, [I] interpretation.

**Sources:** `k1/results/validation_partF.json`; ledger `k1/results/ledgers/heldout_kp.csv`.

**Procedure:**

1. Blind search, then the funnel.
2. Prediction lock `partF` (1,998 files, bundle 50bf44bc...), written before any HELD-OUT truth was read.
3. Matching by rule 2.2 with amendments 4, 5 and 7.

**Arms:**

* K1, frozen: survey_k1, 8,100 s, S `bound_alias`, legacy ramp, amendments 1-7.
* P12, frozen: an isolated copy of aee65172b running `survey_p10` and the p10.0 funnel on sectors 56-98 (FFI
  products from the K1 store).

Nothing here is a detection.

## 1. Gates [A]

| gate | result | rule | outcome |
|---|---|---|---|
| **G1** | **29 / 55 = 52.7%** reach the Stage C endpoint (Wilson 40-65%; host bootstrap 40-67%). The cohort is HELD-OUT planets with expected SNR >= 20 and >= 3 observed transits, on 44 hosts. | >= 60% | **FAIL** |
| **G2** | K1 29 vs P12 24 on the same 55: **+9.1 pp** (host bootstrap -3.8 to +22.4). K1-only 10, P12-only 5. | point estimate >= -5 pp | PASS |
| **G3** | **0 / 53** HELD-OUT adversarial negatives reach SUBMIT (Wilson 0-6.8%). SUBMIT + HOLD = 1 (EB TIC 396902326, HOLD). The any-candidate bound gives the same: 0 SUBMIT, 1 HOLD. | <= 5% SUBMIT | PASS |

[R] The Oct 3-4 comparable figure was 27/41 = 66%.

## 2. One bounded repair: stage attribution of every G1 loss [M]

These are the 26 cohort planets not reaching Stage C. Each is attributed to the last stage reached by its
best matched path (the Oct 3 stage-ledger method).

| lost at | n | planets and cause |
|---|---|---|
| search | 8 | see below |
| A | 5 | see below |
| S (`bound_alias`) | 2 | TOI-4010 d, TOI-1248 b (A-pass paths fail on a significant off-phase dip; TOI-1248 b's best path also fails A) |
| C | 11 | see below |

**Search losses:**

* TOI-216.02, twice (two catalogue rows). The host has large transit-timing variations; candidates sit
  within 1% of the period but a linear ephemeris never coincides.
* TOI-1533 c and TIC 349520724 b: no candidate near the period.
* TOI-4010 b: candidate 0.4% off, no pre-gate.
* TOI-942 c: candidate at 1/3 P, fails A.
* TOI-2133 b: candidate 0.5% off; coverage 0.09.
* TOI-238 c: candidate at 2P, coverage 0.22.
* None of these hosts was partition-limited.

**Stage A losses (all `depths_consistent_p_ge_1e-3`):**

* TOI-1759 b (SNR 84);
* TOI-1260 c (22);
* TOI-220 b (66);
* TOI-1105 b (40);
* TOI-2654 b (75).

Per-event depths are inconsistent with a constant at p = 1e-5 to 1e-8. [I] Mixed TESS-SPOC / QLP products and
sectors give real depth differences of a few percent (aperture and dilution), which the frozen chi-square
resolves at high SNR. The same behaviour cost 13% of the injections at expected SNR >= 40.

**Stage C losses:**

* Sibling substitution (blind TLS strongest peak = another planet of the system; RULES 1.5 counts this as a
  loss by design):
  * TOI-1260 c / d / .03, all to TOI-1260 b at 3.127 d;
  * TOI-1749 d, to 4.489 d;
  * TOI-1346 b, to 5.503 d;
  * TOI-712 b, to TOI-712 c at 51.7 d.
* Strongest peak at a spurious long period (50-108 d): TOI-1533 b, TOI-4504 b, K2-55 b, TOI-5289.01,
  TOI-942 b. P12's frozen C also fails all five.
* TOI-2084 b: strongest peak at 8.149 d.

**Repair decision [A].** None of the 26 losses traces to a clear implementation defect:

* the substitutions are the registered C rule;
* the long-period peaks occur in P12's frozen C as well;
* the A losses are the frozen criterion applied as registered;
* the search misses are TTVs, aliases or genuinely absent candidates; no budget or matching bug was found.

Changing the A depth-consistency test or the C strongest-peak rule would be method or threshold changes, which
the repair clause excludes. **The bounded repair has nothing to fix, so G1 stands and the final state is
NOT_READY.**

[I] Fixing all five A losses would bring G1 to 34/55 = 61.8%. Those are the cheapest gains for a later prompt,
but they are a method change.

## 3. All HELD-OUT known planets (141 planets, 107 hosts) [M]

| arm | search | pre-gate | A | S | B | C |
|---|---|---|---|---|---|---|
| K1 | 62 | 59 | 53 | 51 (`bound_alias`) | 51 | **39** |
| P12 | 45 | 42 | 37 | 31 (`bound`) | 31 | **26** |

**By expected SNR (K1 / P12 reaching C):**

| expected SNR | n | K1 | P12 |
|---|---|---|---|
| < 7 | 65 | 0 | 0 |
| 7-10 | 4 | 1 | 0 |
| 10-15 | 10 | 4 | 0 |
| 15-20 | 7 | 5 | 2 |
| 20-30 | 20 | 8 | 7 |
| 30-40 | 14 | 8 | 5 |
| >= 40 | 21 | 13 | 12 |

[I] K1's gain over P12 comes from the older sectors (more transits and SNR) and from `bound_alias` at S. It is
largest at expected SNR 10-20.

* Three P12 searches had no data in sectors >= 56 (NO_DATA_IN_ARM; counted as P12 non-recoveries).
* The full stage tables by period, radius, Tmag and n_usable are in `validation_partF.json`.

## 4. Stage D outcomes of recovered known planets [M]

39 planets reach the Stage C endpoint. Stage D ran with the catalogue redacted and k1.0 tiers:

| tier | n |
|---|---|
| SUBMIT | 11 |
| HOLD | 26 |
| KILL | 2 |

The two KILLs:

* **TOI-1174 b:** K6, odd/even depth difference above 3 sigma.
* **TOI-2322 c:** K5, the period is an integer alias of a deeper accepted signal in the system.

The p12.0 tiers also KILL both.

## 5. Exceptions and conditions [M]

* **Search conditions differed from calibration.** Part F searches ran faster than Part D's: Windows
  power-throttling shifted, and workers reached the P-cores. HELD-OUT searches hit no partition limit (0 / 159),
  against 9-14% in Part D. [I] If anything this flatters G1 relative to calibration conditions; G2 ran under
  identical conditions for both arms.
* **Contention window.** A mistakenly started C phase overlapped the HELD-OUT search 19:43-20:03Z on
  2026-10-11. The 5 partition-limited jobs from that window were re-run alone; the 49 not limited were kept
  (identical by construction).
* **Stage C errors.** 4 HELD-OUT Stage C jobs ended in a deterministic error ('NoneType / float' after TLS) on
  adversarial blend host TIC 251857119 (630 ppt signal). It is a frozen p10 code edge case; those candidates are
  reported as unknown, not as rejections.
* **Shared host.** One host, TIC 232612416, is both a HELD-OUT known-planet host and a HELD-OUT EB. Its
  planet-matched candidates are excluded from G3 (amendment 4).
