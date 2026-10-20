# READY_K1: K-dwarf survey preparation (prompt K1), decision document

Dated 2026-10-14 (UTC). Branch `k1/prepare` (local; nothing pushed). Tags: [M] measured, [R] review,
[A] adopted/registered, [I] interpretation. Nothing in K1 is a detection, a discovery or a submission. Nothing
was uploaded to ExoFOP, VSX, TFOP or anywhere else, and nobody was contacted.

## 1. Final state: **NOT_READY**

[A] G1 fails: 29 of 55 HELD-OUT known planets (expected SNR >= 20, >= 3 transits) reach the Stage C endpoint,
52.7% (Wilson 40-65%) against the registered 60%.

* The one bounded repair found no clear implementation defect behind any of the 26 losses (section 5). By rule
  the state is NOT_READY.
* G2 (non-inferiority to P12) and G3 (adversarial SUBMIT <= 5%) pass.
* On the same planets K1 beats the current P12 pipeline: 29 vs 24 reach C (+9.1 pp). Over all 141 HELD-OUT
  planets it is 39 vs 26.

## 2. Population counts [M] (`k1/results/POPULATION_K1.md`)

* All-sky query envelope: 1,295,195 stars.
* After the class, Tmag, |b|, LMC/SMC, contamination, Gaia main-sequence, hard-stop, FFI-majority and
  >= 5-usable-sector cuts: **70,059 (60,915 K, 9,144 eM)**.
  * [M] The review's ~83,000 K counted >= 5 list sectors in 1-105. The registered usable-sector rule
    (1-98; QLP 80/83/85 only via TESS-SPOC) plus the Gaia check explain the difference
    (`population_count_decomposition.json`).
* **Survey list:** 7,000 K + 3,000 eM by E_new (`k1/survey/targets_k1.csv`, sha256 5768d330...).
* **Reserve:** 15,000.
* **Delivery-day refresh (2026-10-14):** 0 stars gained a TOI/CTOI or other hard-stop REJECT. 48 carry a SPOC
  TCE (FLAG + period veto). 0 overlap with the calibration exposure ledger, so survey blindness held.
* **A4 re-rank** did not fire: 4.2% of the top 7,000 K changed under the noise refit (rule: > 10%).

## 3. Every change made, with its measured effect

The 14-item change list, with K1 code behind new parameters or presets:

1. **K + eM all-sky pool** (`scripts/build_k1_population.py`): census above. The rank reproduces the review
   within 1% (A5: K top-10k 8.95 vs 9.0, eM 2.38 / 8.06 vs 2.4 / 8.1).
2. **Gaia main-sequence check** (Bp-Rp 0.85-2.50, Pecaut & Mamajek): removes 3,400 K stars; unit tests pass
   (dwarfs pass, subgiants rejected, binaries flagged).
3. **No global deep clip:** a 20 ppt, 3 h transit keeps >= 95% of in-transit cadences, and isolated dips are
   still removed (tests).
4. **Duration grid** 0.02-0.35 d in 14 log steps: a 5.5 h injection is recovered at its true duration ± 1 step
   (test).
5. **Window 1.1 d:** 5 h transits keep >= 0.85 of their depth (test).
6. **K1 namespace/workers** asserting the presets: the DEV dry run passed every stage. P12 regression:
   * suites 786 + 1 skipped / 7 / 98 / 248, and 0 smoke differences, unchanged;
   * 11 of 12 stored P12 cases replay field-for-field; the 12th differs only in a budget-limited partition.
7. **Merit = E_new** (`rank_k1.py`): see 1.
8. **Stage D real author/exposure + Tmag-scaled apertures:** tests at 600 s and 1,800 s.
9. **K1 hard stop:** REJECT on TOI/CTOI/NASA/EB/TTT; FLAG within 21"; TCE sidecar veto (tests).
10. **Mixed-cadence all-sector ingestion:**
    * E1 as registered: **+18.5 pp** recovery through S (42.9% vs 24.3%, [+13.1, +23.8]);
    * FA ratio 1.22; wall ratio 1.69.
11. **S mode `bound_alias`:** E2 retention 313 vs 256 (`bound`) of 517; adversarial pass-through 0/35.
12. **Noise-relative SAP-ramp test:** E3 -0.13 pp; not adopted.
13. **K8 density kill to HOLD for P > 10 d** (k1.0 tiers): tier tests pass. No HELD-OUT planet was killed by K8;
    the 2 KILLs were K5 and K6.
14. **Search budget:** E4 gave 8,100 s (15% partition-limited in the pilot; 9.1% in Part D injections; 0% in
    Part F).

**Amendments** (all registered in `k1/manifests/registration.json`):

1. QLP 74-79 must be v02.
2. Exposure-aware Stage A per-event depth (limb-darkened template integrated over the exposure). Pilot:
   survey_k1 injections through A went from 15 to 19 of 26; 5 very-high-SNR depth-consistency kills
   remained (sector-to-sector scatter).
3. E1 under E2's mode. Post-hoc, chosen by the user. Moot after amendment 7.
4. and 5. Adversarial path definition (period-only matching; host shared by two sets).
6. Injection C sample truncated at 58/147 (user decision).
7. **Evaluator:** the identity rule uses the candidate's stitch re-measured period. Chunk periods drifted over the
   ~7-year baseline, so 117 of 119 high-SNR "search misses" were matching failures. Search plateau 0.64 -> 0.99.
   Every decision unchanged.

**Operational:**

* Non-search phases opt out of Windows power throttling (searches keep the calibrated default).
* Timed-out jobs get 4x their deadline on retry.
* A contention repair re-ran 5 HELD-OUT searches.

## 4. Rule outcomes E1-E4 [A] (`k1/protocol/RULES_K1.md` section 7; `k1/results/decisions_E.json`)

| rule | result | outcome |
|---|---|---|
| E1 (as registered) | +18.53 pp [+13.11, +23.83]; FA 1.22; wall 1.69 | **survey_k1** |
| E2 | retention `bound_alias` 35.0% -> 60.5% post-fix (313 / 517); pass-through 0/35 | **`bound_alias`** |
| E3 | -0.13 pp | **not adopted (legacy ramp)** |
| E4 | 37.5% / 20% / 15% at 2,700 / 5,400 / 8,100 s | **8,100 s**, not qualified |

**Calibration** (`k1/results/CALIBRATION_K1.md`):

| quantity | value |
|---|---|
| search SNR50 / SNR90 | 10.7 / 18.4 |
| S (`bound_alias`) SNR50 | 11.05 (plateau 0.83) |
| through-C curve | x50 14.4, w 2.4, cmax 0.79 |
| FA per star (survey_k1) | 2.69 pre-gate; 0.088 at A; 0.088 at S |

## 5. Gates G1-G3 with intervals [M/A] (`k1/results/VALIDATION_K1.md`)

| gate | result | outcome |
|---|---|---|
| **G1** | 29/55 = 52.7%; Wilson 39.8-65.3%; host bootstrap 40.4-66.7% | **FAIL** (>= 60%) |
| **G2** | +9.1 pp (K1 29 vs P12 24); host bootstrap -3.8 to +22.4 | **PASS** (>= -5 pp) |
| **G3** | 0/53 SUBMIT (Wilson 0-6.8%); SUBMIT + HOLD 1/53 | **PASS** |

**G1 losses by stage:**

| stage | losses | cause |
|---|---|---|
| search | 8 | TTV system TOI-216, aliases, two absent |
| A | 5 | all depth-consistency at SNR 22-84: mixed-product depth scatter |
| S | 2 | off-phase dips |
| C | 11 | 6 sibling substitutions in multi-planet systems (a loss by RULES 1.5); 5 spurious 50-108 d TLS peaks, also lost by P12's frozen C |

**Recovered known planets at Stage D:** 11 SUBMIT, 26 HOLD, 2 KILL (TOI-1174 b: K6 odd/even; TOI-2322 c: K5
alias of a deeper signal).

## 6. Cost

**K1 Parts C-F, actual [M]:**

* 32 controller phases, ~164 phase-wall hours, 2,238 job-wall hours.
* Elapsed ~6 days, 2026-10-08 to 10-14.
* User-approved budget at STOP-C: ~224 priced queue-hours.

**Survey, priced [M-based]:** ~1,376 queue-hours (1.5x), about 57 days on this machine.

| stage | queue-hours |
|---|---|
| search | 345 |
| A | 117 |
| C | 809 |
| D | 104 |

* Stage C on >= 20-sector stars dominates; 34% of the list has >= 30 sectors.
* (`k1/results/survey_price.json`)

**Disk [M]:**

* K1 data on D: today ~82 GB (runs 5.3, funnel 50.3, lightkurve cache 19.4, stitched 2.1, store 1.1, injected
  1.4, receipts 2.0).
* Survey forecast ~290-390 GB on D: (616 GB free).
* C: ~36 GB free; it drifted down outside K1.

**Bytes:**

* Light-curve store ~1.3 MB per star.
* Stage D pixel cutouts ~0.2 GB per D candidate.

## 7. Exceptions

1. **G1 fail**, the reason for NOT_READY.
2. **Amendment 3 (post-hoc E1, user decision).** Now moot: E1 as registered adopts survey_k1 after
   amendment 7.
3. **Injection C sample truncated (amendment 6, user decision).** C | S rests on 58 items. There is none below
   expected SNR 10, and >= 13-sector hosts are under-represented (15 of 51 planned).
4. **Search conditions shifted.** Calibration searches ran power-throttled onto the E-cores (cpu/wall 0.64).
   HELD-OUT searches later ran partly on the P-cores (0.7-0.87; 0% partition-limited vs 9-14%).
   * [I] G1 is if anything flattered; G2 compared both arms under identical conditions.
5. **Deterministic Stage C error.** On one adversarial blend host (630 ppt signal), 4 candidates end in a frozen
   p10 code edge case. They are reported as unknown.
6. **Deterministic Stage A errors.** 18 pre-gate candidates with duration > P/2 (0.2%). Unknown, never passes.
7. **No data in arm.** 4 injections (one host without s56 data) and 3 P12-paired hosts. Counted as that arm's
   non-recoveries.
8. **Contention window** (19:43-20:03Z, 2026-10-11): repaired by re-running the 5 affected partition-limited
   searches.

## 8. What remains unmeasured

* Stage C | S below expected SNR 10, and on >= 13-sector hosts (thin).
* Stage C on natural false alarms: the FA hosts stopped at S. The SUBMIT/HOLD-per-1,000 forecast (5-15) assumes
  P12's C pass fraction.
* Stage D on injections.
* eM-slice behaviour beyond the injection hosts; the TOI-calibrated vs published occurrence split is not
  resolved (yield 1.9 vs 6.5).
* The survey's own partition-limited rate under whichever CPU conditions it runs.
* TLS run time beyond ~43 sectors.

## 9. False assumptions (do not re-adopt)

* **"The pilot's flat per-star cost prices the survey."** Search and Stage C costs grow steeply with usable
  sectors. Price by n_usable (`price_survey_k1.py`).
* **"A chunk-level BLS period is good enough to match over the full baseline."** It drifts off over ~7 years.
  Use the stitch period (amendment 7).
* **"Box-mean per-event depths are comparable across 200 / 600 / 1,800 s exposures."** They are not (amendment 2).
* **"Hidden background workers use the whole CPU."** Windows confined them to the E-cores until they opted out.
* **"E1 should be judged under `bound` regardless of the funnel's mode."** It nearly reversed the cadence
  decision before the evaluator fix.
* **"A per-job deadline sized from a 40-host pilot covers continuous-viewing-zone hosts."** It does not:
  A > 1,800 s and C 10-15 h on 30-43-sector stars.
* **"Killing a bash orchestrator kills its in-flight launcher."** On Windows it does not.
* **"The review's ~83,000 K count"** used list sectors 1-105, not the usable-sector rule.

## 10. What is needed to launch

The survey must **not** be launched under K1. Two paths:

* **(a) A follow-up prompt (K2)** that keeps everything frozen here and addresses, with its own registered rules
  and a fresh HELD-OUT check:
  1. Stage A depth consistency on mixed TESS-SPOC/QLP products (5 of 26 G1 losses), e.g. per-product depth
     normalisation;
  2. Stage C handling of multi-planet systems (mask accepted siblings before the blind TLS) and of spurious
     long-period peaks (11 losses);
  3. a cheaper Stage C for long-baseline stars (binned TLS input), to bring the ~1,376 queue-hour price down.
* **(b) An explicit user decision** to launch the frozen package as is, on the G2 evidence (K1 non-inferior to,
  and ahead of, P12) and G3. That launch would follow `k1/survey/LAUNCH_PLAN_K1.md`, starting with
  `plan_k1.py download` and `search` for batch 1 under `controller_k1.py`. It is not authorised by K1's rules.
