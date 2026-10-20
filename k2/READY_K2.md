# READY_K2: K-dwarf survey preparation, second pass (prompt K2), decision document

Dated 2026-10-15 (UTC). Branch `k2/prepare` (from `k1/prepare` 1a1344283; local, nothing pushed). Tags: [M] measured,
[R] review / K1 record, [A] adopted/registered, [I] interpretation. Nothing in K2 is a detection, a discovery or a
submission. Nothing was uploaded to ExoFOP, VSX, TFOP or anywhere else, and nobody was contacted. The survey was
not launched.

## 1. Final state: **NOT_READY**

[A] G1 fails on the deciding set (the fresh confirmatory set, 64 strong planets): **38 of 64 = 59.4%** reach the
Stage C endpoint, against the registered 60% (39 of 64). The miss is one planet.

* The one bounded repair found no clear implementation defect behind any of the 26 losses (section 5), so by
  rule the state is NOT_READY.
* G2 and G3 pass on the fresh set:
  * G2: +10.9 pp against frozen P12 (38 vs 31);
  * G3: 0 of 70 adversarial SUBMIT.
* [I] 60% lies well inside G1's 95% interval (47-71%). The data cannot tell 59.4% from 60%; the registered rule
  is the point estimate.

## 2. Inputs and sets [M]

* **Configuration:** K1's frozen package (survey_k1, 8,100 s, S `bound_alias`, legacy ramp, k1.0 tiers, K1
  amendments 1-7), unchanged except as below.
* **Reference sets (from K1, no new truth):**
  * R-C: 119 completed K1 Stage C jobs;
  * R-A: 3,799 pre-gate candidates (injections at expected SNR >= 20, the 250 FA hosts, the DEV hosts).
* **Fresh confirmatory set** (`k2/manifests/fresh_*`; built by K1's own selection code):
  * a fresh NASA pull, plus the 2026-10-14 TOI snapshot;
  * K1's pool, every K1 set, the survey list and the reserve excluded;
  * 183 planets on 138 hosts, all with data; G1 cohort 64;
  * 70 adversarial negatives: the next 50 EB hosts and 20 blend targets in K1's hash order.
* **Survey blindness:** 0 survey-list or reserve stars downloaded or searched. The exposure ledgers (K1 + K2) do
  not overlap the list.

## 3. Every change made, with its measured effect

**Registration:** `k2/protocol/RULES_K2.md`, registered before any K2 measurement; outcomes appended in section 9.

**Amendment 1 (AMENDMENT_K2_20261014_1): C1 bin errors propagated.**

* Under the first registration (`bin_lc`'s in-bin scatter), 5 of 8 K1-PASS timing jobs failed. The top 1% of bins
  carried 49-73% of the chi-square weight.
* With propagated errors the same 10 jobs agree with K1 on 9 decisions and recover the 10th.
* The amendment was written after seeing those 10 outcomes; C1 was decided on all 119.

**Rule outcomes:**

| rule | outcome | measured effect |
|---|---|---|
| **C1: cheaper Stage C** | **V3 adopted** (30-min bins, propagated errors, TLS oversampling 2 on > 1,000-d baselines) | (a) C-endpoint retention 77/95 vs K1 75/95, +2.1 pp (host bootstrap -2.1 to +6.3); (b) 0 of 5 DEV adversarial flips; (c) median Stage C wall on >= 20-sector hosts 30,716 s -> 1,015 s, **30.2x**. V2, V4 and V1 were not run. `k2/results/STAGE_C_K2.md` |
| **A1: within-product-family depth consistency** | **not adopted** | A1a (TESS-SPOC vs QLP): +0.2 pp; A1b (also by exposure): +2.0 pp. The bar is +3 pp. FA ratio 1.00 / 1.05; adversarial +2.2 / +4.4 pp. Determinism 1,055 / 1,055. `k2/results/STAGE_A_K2.md` |
| **M1: sibling masking in Stage C** | **adopted** (on top of V3) | DEV planets at the C endpoint 30 -> 31; multi-planet DEV hosts 4 -> 5; no adversarial gain. Gained TOI-1803 b and Kepler-210 b; lost TOI-1438 c (TLS SDE normalisation, 55.9 -> 3.6, with only 7 of 660 in-transit points masked). `k2/results/STAGE_M1_K2.md` |

**Shared-`src` change:** `event_vet.DEPTH_CONSISTENCY_FAMILIES` (default None = K1 exactly). Regression suites
unchanged: tests 786 + 1 skipped, p11 7, p11_5 98, k1 60, p12 248 PASS, P8 smoke 0 differences; k2/tests 15.

**Operational changes [M]:**

* **Supervision:** the session cron check-ins never fired (a 4 h 41 min idle lapse, 2026-10-14 17:58-22:38Z).
  Supervision moved to a background waiter (`k2/work/wait_k2.sh`) that wakes the session at least hourly.
* **Stage D cache:** lightkurve's home-cache downloads (Stage D FPP cutouts) were redirected to D: through
  `XDG_CACHE_HOME`, after the K-D pause and with the user's decision. `k2_common.py` therefore differs from its
  freeze hash; no effect on results.
* **D planner S mode:** Stage D is planned with the C runtime's S mode, so the rules stamp matches (`p10.0` vs
  `p10.0-partial`).

## 4. Rule outcomes C1 / A1 / M1 [A]

See section 3. Frozen K2 configuration: `k2/protocol/config.json` (sha d47da619...) + `k2/manifests/freeze_k2.json`
= K1 + V3 + M1; A1 not adopted.

## 5. Gates G1-G3 with intervals [M/A] (`k2/results/VALIDATION_K2.md`)

| gate | fresh (deciding) | seen, design-informed | K1 on the seen set |
|---|---|---|---|
| **G1** (>= 60%) | **38/64 = 59.4%** (Wilson 47-71%) **FAIL** | 31/55 = 56.4% (43-69%) FAIL | 29/55 = 52.7% |
| **G2** (>= -5 pp) | **+10.9 pp** (38 vs 31; boot -1.6 to +24.2) PASS | +12.7 pp (31 vs 24) PASS | +9.1 pp |
| **G3** (<= 5% SUBMIT) | **0/70** (1 HOLD) PASS | 1/53 (1.9%; 1 HOLD) PASS | 0/53 |

**Fresh G1 losses (26):**

| stage | n | cause |
|---|---|---|
| search | 1 | no candidate |
| A | 12 | all on the frozen depth-consistency criterion |
| S | 5 | SAP secondary dips |
| C | 8 | see below |

The 8 Stage C losses:

* 5 spurious long-period (33-101 d) TLS peaks;
* 1 sibling whose own candidate failed A, so M1 did not mask it;
* 1 genuinely inconsistent 1:2 alias;
* 1 V3 alias-test interaction (TOI-1739 b: the one-bin TLS duration gives zero per-transit errors).

**Bounded repair:** no clear implementation defect, so nothing was fixed.

**Recovered planets at Stage D:**

* fresh: SUBMIT 27, HOLD 30, KILL 1 (TOI-1694 b, K8);
* seen: SUBMIT 23, HOLD 15, KILL 2 (as in K1).

## 6. Cost

**K2 actual [M]:**

* ~30 controller phases from 2026-10-14 17:14Z to 2026-10-15 ~17:15Z. About 24 h elapsed, including the 4.7-h
  idle lapse and a ~1-h K-D pause.
* K-B pricing after the timing check: 45 queue-hours expected (66 worst case), against the 120 stop.

**Survey, priced [M-based]** (`k2/results/survey_price_k2_final.json`; K1's method with V3 Stage C unit costs):

| stage | K1 | K2 |
|---|---|---|
| search | 345 | 345 |
| A | 117 | 117 |
| S + B | 0.6 | 0.6 |
| C | 809 | **34** (61 using the oversubscribed HELD-OUT/fresh C walls) |
| D | 104 | 104 |
| **total** | **~1,376 qh (~57 days)** | **~601 qh (~25 days)** (628 sensitivity) |

**Expected yield** (`k2/results/yield_k2.json`; K2 through-C curve x50 13.9, w 2.35, cmax 0.79):

| slice | K2 | K1 |
|---|---|---|
| K, TOI-calibrated | **7.3** (4.8-8.8) | 7.0 |
| eM, TOI-calibrated | **2.0** (1.2-2.7) | 1.9 |
| eM, published | **7.0** (4.2-9.3) | 6.5 |

**Disk [M]:**

* D: ~510 GB free.
* C: ~30 GB, after moving K2's 8 GB of cutouts.
* The 55 GB of pre-K2 files in `C:\Users\seanj\.cache\lightkurve` are untouched; they belong to the user's
  earlier runs.

## 7. Exceptions

1. **G1 fail on the deciding set** (by one planet), the reason for NOT_READY. G1 also fails on the seen set.
2. **A1 not adopted:** a planned change dropped.
3. **Amendment 1 is post-hoc** (written after 10 timing outcomes).
4. **Seen-set G3 SUBMIT** (V1 blend TIC 1950736) comes from a transient TESScut gap in Stage D's pixel step
   (sector-44 cutout missing; K7 fired in 1 sector instead of 2), not from V3 or M1.
5. **One new deterministic Stage C error** on the seen set: TLS's final T0 fit crashes on a sparse binned input
   (2,970 points, a 0.58-d candidate that K1 passed). Reported as unknown.
6. **Contention:** the Part 4 phases ran oversubscribed. Decisions are unaffected; wall times are inflated.
7. **K-D pause** (C: below 25 GB) and the cache relocation, by the user's decision.
8. **The supervision lapse** of 4 h 41 min.

## 8. What remains unmeasured

* The fresh set under K1's configuration: no K1-arm C/D on the fresh hosts, so the K1-vs-K2 G1 delta on the fresh
  set is unmeasured. On the seen set it is +2 planets.
* Stage C on natural false alarms (FA hosts stop at S), so the SUBMIT/HOLD rate per 1,000 survey stars still
  assumes P12's C pass fraction.
* C | S below expected SNR 10 (no injection-sample item), and on >= 13-sector hosts (thin).
* How often V3's sparse-input TLS crash and the TESScut gaps would occur across the survey.
* Stage D on injections.

## 9. False assumptions (do not re-adopt)

* **"Binning the C input only needs `bin_lc`."** Its in-bin-scatter errors from 3-9 points let 1% of the bins
  dominate TLS. Propagate the per-cadence errors.
* **"A1 (a product-family split) fixes Stage A's high-SNR depth losses."** The scatter is sector-to-sector,
  within a pipeline (12 of 26 fresh G1 losses).
* **"`LIGHTKURVE_CACHE` keeps lightkurve off C:."** This lightkurve ignores it; downloads without a download_dir
  (Stage D FPP cutouts) go to the home cache. Use `XDG_CACHE_HOME`.
  * [I] K1's "C: drifted down outside K1" was most likely this.
* **"Session cron check-ins supervise long runs."** They did not fire here. Use a background waiter.
* **"Stage D's verdict is a function of the Stage C ephemeris."** It also depends on which TESScut cutouts
  download at run time.
* **"A controller TIMEOUT means no result."** A worker can write its COMPLETE receipt and then hang (kept, P12
  rule).
* K1's list still applies; see `k1/READY_K1.md` section 9.

## 10. What launching would take

The survey must **not** be launched under K2's rules. Paths:

* **(a) A follow-up prompt (K3)** that keeps K2's frozen package and addresses G1's remaining losses, with
  registered rules and a new fresh check:
  * **Stage A depth consistency** (12 of 26 fresh losses): a per-sector depth model (aperture / dilution) or a
    relative scatter tolerance, not a family split.
  * **Stage C spurious long-period peaks** (5): for example a peak-significance test against the period-dependent
    SDE floor, or a robust SDE.
  * **The V3 alias interaction:** take the per-transit depths for the 2:1 alias test from the native series.
  * **Robustness:** a TLS-exception fallback to the native input; retry TESScut downloads before marking a sector
    not measurable.
* **(b) An explicit user decision** to launch the frozen K2 package on the evidence:
  * G1 59.4%, one planet short; G2 +10.9 pp ahead of P12; G3 0/70.
  * It costs ~601 queue-hours (~25 days) instead of ~1,376.
  * That launch would follow `k2/survey/LAUNCH_PLAN_K2.md`. It is not authorised by K2's rules.
