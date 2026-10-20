# RULES_K2 - registration for prompt K2 (cheaper Stage C, cross-product depth consistency, sibling masking)

Registered 2026-10-14 (UTC) before any K2 measurement (no K2 Stage A, Stage C, Stage D, search or timing job
has run).  Its SHA-256 is recorded in `k2/manifests/registration.json`.  Any later change is an amendment: a new
dated file `k2/protocol/AMENDMENT_K2_<date>_<n>.md`, hashed into the same manifest.  This file is never edited
after registration except to append outcome sections at the end, each dated and re-hashed.

Tags: [A] adopted here before measurement; [K1] carried over from `k1/protocol/RULES_K1.md` and its amendments
1-7; [P] from the prompt (`PROMPT_K2_PREPARE.md`).  Nothing in K2 is a detection, a discovery or a submission.

K2 builds on K1's frozen configuration [K1]: `survey_k1` (all usable sectors 1-98, native mixed cadence),
8,100 s search budget, pre-gate (stitch SNR >= 7.1, >= 3 stitch transits, epoch consistent), Stage A p10.0 with
amendment 2's exposure-aware depth and the legacy SAP-ramp rule, Stage S mode `bound_alias`, Stage B p10.0 with
the per-window cadence rule, Stage C p10.0 strongest-peak rule (blind TLS 0.5-110 d, oversampling 3, conditional
robust fallback, coarsest-in-transit-cadence duration floor), Stage D k1.0 tiers.  K2 changes only what sections
2-4 adopt.  Every K1 search result, pre-gate list and Stage S/B receipt is reused as is [P].

---------------------------------------------------------------------------------------------

## 1. Definitions [A]

### 1.1 Reference sets (all from K1; no new truth)
* **R-C** (C reference): the 119 completed K1 Stage C jobs of labels `dev_k1` (61, on DEV known-planet and DEV
  adversarial hosts) and `inj_k1` (58, the truncated injection C sample of amendment 6).  Each R-C job is
  re-run in a K2 case root that is a copy of its K1 case root without the Stage C/D outputs (`stageC/`,
  `stageD/`, `fit/`, `pixels/`, `crossmatch*`, `tls/<key>.json`, `tls/<key>_spectrum.npz` and any
  `tls/<key>_res*` / `_peak*` files), so K1's prepared series and A/S/B records are reused.
* **R-A** (A reference): the pre-gate candidates of (i) the Part D `survey_k1` injection searches
  (`inj_<id>_k1`) of injections with expected SNR (`snr_exp_k1`) >= 20; (ii) the 250 false-alarm hosts'
  `survey_k1` searches (`fa_k1`); (iii) the DEV known-planet and DEV adversarial hosts' searches (`dev_k1`).
* **HELD-OUT, seen set**: K1's HELD-OUT known planets (141 on 107 hosts; G1 cohort 55) and HELD-OUT adversarial
  negatives (53), with K1's searches (`ho_k1`) and K1's paired P12 arm (`p12_paired`, reused unchanged).  Their
  losses are known from K1, so every K2 number on this set is labelled **"seen set, design-informed"**.
* **Fresh confirmatory set** (section 5): known planets meeting K1's selection rules but not used in K1, plus
  fresh adversarial negatives.  Sealed until its own prediction lock.

### 1.2 n_usable of a job
The number of products in the prepared series of the job's K1 case root (`prep/<key>.json`, `products`), i.e.
RULES_K1 1.1's realised count.  Classes: 0-8, 8-13, 13-20, 20-30, >= 30 (left-closed).

### 1.3 C endpoint [K1]
RULES_K1 1.5: a path matched to the planet or injection (RULES_K1 2.2 with amendment 7) passes the pre-gate, A,
S, B and has Stage C decision PASS, and the Stage C blind period matches the truth period within 1% at a ratio in
{1, 2, 1/2, 3, 1/3}.  An item reaches the endpoint when ANY of its matched paths does.

### 1.4 Queue-hours
For a phase: (sum of job wall seconds) / (workers) / 3600 x 1.5 margin, the `price_survey_k1.py` convention.

### 1.5 Intervals [K1]
Wilson 95% for proportions; host bootstrap with 10,000 draws, seed 20261011, percentile 95%, paired differences
on the same host draws (hosts = TIC ids).

---------------------------------------------------------------------------------------------

## 2. Rule C1: a cheaper Stage C [A]

### 2.1 The variants
Each variant changes only the series the Stage C TLS runs read and, for V3/V4, the blind-TLS oversampling.  The
**C input** of a variant is K1's prepared C input (`tls/<key>_lc.npz` arrays `time`, `flux`, `flux_err`:
detrended and clipped at native cadence exactly as in K1) transformed by:

| variant | transformation of the K1 C input | blind-TLS oversampling |
|---|---|---|
| **V3** | every point binned to 30 min | 2 when the C input's baseline (max - min time) exceeds 1,000 d, else 3 |
| **V2** | every point binned to 30 min | 3 |
| **V4** (the one added variant) | points of products with native cadence finer than 10 min binned to 10 min; 600-s and 1800-s products native | as V3 |
| **V1** | as V4 | 3 |

* Binning is `tesshunter.audit_prep.bin_lc` (fixed-width bins, bin time = mean time, bin error = in-bin scatter
  / sqrt(n - 1) for >= 3 points, else the propagated error).  V2/V3 bin the whole concatenated series on one grid
  starting at its first point; V1/V4 bin each product (sector) on its own grid starting at its first point.  A
  point's product is identified through `sector_unbinned` and the prepared products list.  No clipping is
  applied after binning (the native-cadence clips of K1 already ran).
* The narrow forced TLS of Stage C reads the same C input (oversampling max(o, 5) as in K1).
* The cadence duration floor (coarsest in-transit cadence, `funnel_k1.coarsest_in_transit_cadence_days`) is
  computed on the C input's times, so it follows the binned cadence (30-min bins snap to 1800 s, 10-min bins to
  600 s).
* Cost order (fewest points x periods first), fixed here: **V3, V2, V4, V1**.  V4 is the one variant the prompt
  allows to be added.
* Everything else in Stage C (period range 0.5-110 d, the strongest-peak decision, the robust fallback, the 2:1
  alias depth test, TLS stellar priors, 4 TLS threads) is K1's.

### 2.2 Adoption (evaluated on R-C)
Items for (a): each of the 58 injection-sample items (its sampled candidate is its only R-C path) and each DEV
known planet with at least one matched path that has an R-C job.  Retention R = items reaching the C endpoint /
items, items weighted equally.

* **(a)** R(variant) - R(K1) >= -2 pp, and the paired host-bootstrap 2.5th percentile >= -5 pp.
* **(b)** No R-C job on a DEV adversarial host that is FAIL in K1 is PASS under the variant.
* **(c)** On R-C jobs with n_usable >= 20: median K1 wall / median variant wall >= 3, where wall is the funnel
  receipt's `wall_seconds` and both run at 4 TLS threads.  K2's R-C phases run with 6 workers x 4 TLS threads
  (as K1's C phases), power throttling opted out, and no other CPU-heavy K2 phase at the same time (network-bound
  downloads are allowed).  Process-tree CPU seconds are reported beside the wall times.

Order: run V3 on R-C (the 10-job timing check of section 7 is its first 10 jobs); adopt it if (a)-(c) hold.
Otherwise run V2, then V4, then V1, stopping at the first that qualifies.  If none qualifies, K1's Stage C is kept
and the best trade-off is reported.  Paired agreement with K1 (decision, blind period within 1%) is reported by
n_usable class.

---------------------------------------------------------------------------------------------

## 3. Rule A1: cross-product depth consistency in Stage A [A]

### 3.1 The criterion
A new `tesshunter.event_vet` option `DEPTH_CONSISTENCY_FAMILIES` (default `None` = K1 exactly).  When it is set,
the kept-event statistics also record, for both scopes below, the families of kept events, each family's weighted
mean depth and error, the within-family chi-square and its p-value.  Errors are the ones the K1 gate reads (the
red-noise-inflated errors under p10.0).

* Scopes: **A1a `author`**: families TESS-SPOC (with SPOC) vs QLP.  **A1b `author_exposure`**: those families
  split further by exposure class (cadence snapped to 120 / 200 / 600 / 1800 s).
* within-family chi-square = sum over families of sum((d_i - m_f)^2 / s_i^2), dof = sum(n_f - 1); p_within = the
  chi-square survival function (1.0 when dof = 0).
* Family means agree when every family f agrees with the dominant family D (largest sum of 1/s^2):
  0.8 <= m_f / m_D <= 1.25, OR |m_f - m_D| <= 3 sqrt(e_f^2 + e_D^2).  If m_D <= 0 the means do not agree.
* Stage A's `depths_consistent_p_ge_1e-3` criterion under A1 = K1's test (p_const >= 1e-3) **OR** (p_within >=
  1e-3 AND family means agree).  Every other A criterion, the chosen-ephemeris rule and amendment 2's
  exposure-aware depth are unchanged.  A1 is therefore a monotone relaxation of K1's Stage A.

### 3.2 Measurement scope
Because of monotonicity, a K1 Stage A PASS stays PASS under A1 and only K1 FAIL receipts can change.  Stage A is
re-run (fresh K2 case root, live gate scope A1a, both scopes recorded) only for R-A candidates whose K1 Stage A
decision is FAIL and on which at least one examined ephemeris failed `depths_consistent_p_ge_1e-3`.  A1b
decisions are recomputed offline from the same receipts (per-ephemeris criteria and the K1 chosen-ephemeris rule
re-applied).  Determinism check: 20 K1 A-PASS candidates of R-A (order sha256("20261015:k2:det:" + candidate_id))
are also re-run; each must PASS with the K1 per-ephemeris p_const reproduced, and every re-run's K1-scope decision
must equal its K1 receipt.  A mismatch is a STOP-G amendment.  S runs on every new A passer; B (neighbour record
required, `bound_alias` PASS/HOLD) on new S passers of the injection and DEV searches (the FA hosts stop at S, as
in K1).

### 3.3 Adoption
For a scope, all must hold:
* (i) injection retention through A (matched path passing the pre-gate and A) at `snr_exp_k1` >= 20 rises by
  >= 3 pp over K1 (pool: every Part D `survey_k1` injection with expected SNR >= 20; 498 in K1's calibration
  table);
* (ii) A-level false alarms per FA star (A PASS candidates on the 250 FA hosts / 250) rise <= 1.2x;
* (iii) the DEV adversarial A-pass rate (A PASS / pre-gate candidates on the 35 DEV adversarial hosts) rises by
  <= 5 pp absolute.  The host-level rate (hosts with any A PASS) is reported beside it.

Order: A1a; if A1a fails any of (i)-(iii), A1b; if both fail, A1 is not adopted.

---------------------------------------------------------------------------------------------

## 4. Rule M1: sibling masking in Stage C [A]

### 4.1 The mask
Before the blind TLS of a candidate X on a star, remove from X's C input every cadence within +/- 1 x T14 of a
predicted mid-time of every **sibling** Y, then apply the adopted C1 variant's binning.

* Y is a sibling of X when Y is another candidate of the same search job (same light curve), Y's stitch SNR is
  higher than X's, Y passed S under the frozen mode (`bound_alias` gate PASS or HOLD, the B eligibility rule), and
  Y's period is not within 1% of X's period at a ratio in {1, 2, 1/2, 3, 1/3} (an alias of X is X's own signal,
  which K1's C rule already handles).
* Y's ephemeris: its Stage A forced-TLS period and T0 when usable; otherwise its stitch period (amendment 7) and
  `epoch_btjd`.  T14 = max(forced-TLS duration, the candidate's `duration_days`).
* "Passed S" uses the S receipts of the configuration in force at that point (K1's, plus A1-rescued candidates'
  S receipts when A1 is adopted).

### 4.2 Evaluation and adoption
M1 runs on top of the adopted C1 variant (K1's C if none).  It is re-run only on the R-C jobs on DEV hosts and
injection-sample hosts that have at least one sibling; every other R-C job keeps its C1 result.  Stage D (k1.0,
catalogue redacted) runs on every new Stage C PASS among them.  Adopt M1 if both hold:
* DEV known-planet C-endpoint recovery (the DEV items of 2.2) does not fall, and on multi-planet DEV hosts (>= 2
  planets in the DEV truth table) it rises by at least one planet;
* no DEV adversarial host gains a path with a k1.0 SUBMIT or HOLD.

---------------------------------------------------------------------------------------------

## 5. The fresh confirmatory set [A]

* **Known planets.**  K1's selection code (`build_sets_k1.build_kp`: pscomppars tran_flag 1 / not controversial
  plus TOI CP/KP, the same planet, host, observed-transit and ephemeris rules) on a fresh NASA pull and K1's
  delivery-day TOI snapshot (2026-10-14).  Excluded: every host of K1's acquisition pool (`kp_hosts.csv`), every
  host of any K1 set (injection, false-alarm, adversarial), the survey list and the reserve.  The remaining
  eligible hosts in K1's hash order ("20261009:k1:kp"); realised-data eligibility (>= 3 observed transits in the
  `survey_k1` arm) and expected SNR exactly as `finalize_kp_k1.py`; K1's cap of 220 planets (hosts whole, hash
  order).
* **Adversarial negatives.**  `build_sets_k1.build_adv`'s rules on K1's 2026-10-08 catalogue snapshot, excluding
  K1's 88 adversarial hosts, every K1 set, the survey list and the reserve; the next 50 EB hosts and 20 blend
  targets in hash order "20261012:k1:adv".
* Truth goes to `k2/truth/` (hash in `k2/manifests/`); no K2 worker may read a path under `k1/truth` or
  `k2/truth`.  The fresh set is downloaded under `D:/tesshunter_k2`, searched with frozen `survey_k1` at 8,100 s
  plus the paired P12 arm (`p12_paired_worker_k1.py`), funnelled under the frozen K2 configuration, locked, then
  unsealed and evaluated.

---------------------------------------------------------------------------------------------

## 6. Freeze, gates and final state [A]

* **Freeze.** After C1, A1 and M1: `k2/protocol/config.json` and `k2/manifests/freeze_k2.json` (K1's frozen
  configuration plus the adopted C1 / A1 / M1, source hashes).
* **Seen set.** Re-run only the changed stages on the `ho_k1` outputs: A where A1 is adopted (K1 FAILs with a
  depth-consistency failure, as 3.2), S/B on new passers, C on every B PASS path (`bound_alias`) under the frozen
  K2 C, D on C passes (catalogue redacted).  P12 arm reused.  Prediction lock, then G1-G3 with
  `evaluate_partF_k1.py` logic.
* **Gates [K1, unchanged].** G1: >= 60% of planets with expected SNR >= 20 and >= 3 observed transits reach the C
  endpoint.  G2: (K2-configuration minus frozen P12) paired difference >= -5 pp (point estimate).  G3: <= 5% of
  adversarial negatives have a path reaching SUBMIT (a path matched to a known planet of the host is excluded,
  amendment 4); SUBMIT + HOLD reported.
* **Deciding set.** The fresh set if its G1 cohort has >= 20 planets; otherwise the seen set, and the state is at
  best READY_WITH_EXCEPTIONS.
* **Final state.**
  * NOT_READY: a stop rule ended K2 without a decision, or any of G1-G3 fails on the deciding set after the
    bounded repair.
  * READY_WITH_EXCEPTIONS: G1-G3 pass on the deciding set, and at least one of: the deciding set is the seen set;
    a registered fix (C1, A1 or M1) was not adopted; a gate fails on the other set.  Each exception is listed
    with its measured cost.
  * READY_TO_LAUNCH: G1-G3 pass on the fresh set, every fix adopted, no exception.
* **One bounded repair** [K1 4]: clear implementation defects only, never threshold retuning; DEV first, then
  once on the fresh set.

---------------------------------------------------------------------------------------------

## 7. Budget, supervision and stop rules [P]

* **Timing check and K2 budget (K-B).** The first 10 V3 R-C jobs (two per n_usable class, order
  sha256("20261015:k2:timing:" + candidate_id)) run first.  Parts 1-4 are then priced with the measured V3/K1 wall
  ratio applied to K1's unit costs by n_usable class (1.4 convention).  Above 120 queue-hours: pause with options.
* Any phase forecast above 30 minutes runs detached under `k2/protocol/controller_k2.py` (copy of
  `controller_k1.py` with K2 roots); one early check about 10 minutes after launch, then one check-in every 60
  minutes; no polling.
* **K-D** C: < 25 GB or D: < 100 GB: pause.  **K-E** a survey-list star downloaded or searched: record, replace
  from the reserve, continue.  **K-F** MAST outage > 6 h, or unknowns > 10% of a phase after its retry: pause;
  unknowns stay unknown.  **K-G** a registered rule cannot be applied as written: dated amendment before acting;
  pause if the choice is not mechanical.
* The survey is not launched.  Nothing is uploaded, nobody is contacted, nothing is pushed.

## 8. Seeds [A]

| use | seed / order |
|---|---|
| host bootstrap | 20261011 (K1) |
| timing-check job order | sha256("20261015:k2:timing:" + candidate_id) |
| A determinism-check sample | sha256("20261015:k2:det:" + candidate_id) |
| fresh known-planet host order | "20261009:k1:kp" (K1) |
| fresh adversarial order | "20261012:k1:adv" (K1) |

## 9. Outcomes (appended after measurement; empty at registration)

### 9.1 C1 outcome (appended 2026-10-15T00:45Z; AMENDMENT_K2_20261014_1 in force)
* [M] V3 on all 119 R-C jobs (`rc_v3a`): (a) 77/95 vs K1 75/95, +2.1 pp, host bootstrap [-2.1, +6.3] -> holds;
  (b) 0 of 5 DEV adversarial K1-FAIL jobs PASS -> holds; (c) >= 20-sector median wall 30,716 s -> 1,015 s, 30.2x
  -> holds.  **Adopted: V3** (first in cost order); V2, V4, V1 not run.  Report: `k2/results/STAGE_C_K2.md`.

### 9.2 A1 outcome (appended 2026-10-15T04:10Z)
* [M] Determinism check 1,055/1,055 (K1 decisions and per-ephemeris p_const reproduced).  A1a: retention through A
  434 vs 433 of 498 (+0.2 pp), FA ratio 1.00, DEV adversarial A-pass +2.2 pp -> fails (i).  A1b: 443 (+2.0 pp),
  FA ratio 1.05, adversarial +4.4 pp -> fails (i).  **A1 not adopted**; Stage A stays K1's.  Report:
  `k2/results/STAGE_A_K2.md`.

### 9.3 M1 outcome (appended 2026-10-15T05:05Z)
* [M] On top of V3, 14 R-C jobs with siblings (all on DEV known-planet hosts; siblings from K1's S receipts, A1 not
  adopted).  DEV planets at the C endpoint 30 -> 31 of 37 (gained TOI-1803 b, Kepler-210 b; lost TOI-1438 c); on the
  12 multi-planet DEV hosts 4 -> 5; injections 47 -> 47.  Stage D on the 2 new passes: Kepler-210 b SUBMIT, TOI-1803 b
  KILL (K2); no DEV adversarial host gains SUBMIT/HOLD.  **M1 adopted.**  Frozen K2 configuration: K1's + C1 = V3
  (amendment 1) + M1; A1 not adopted.

### 9.4 Gates and final state (appended 2026-10-15T17:40Z)
* [M] Fresh set (deciding; G1 cohort 64 >= 20), lock `fresh` (e13f6cca...): G1 38/64 = 59.4% (Wilson 47-71%) FAIL by
  one planet; G2 +10.9 pp (K2 38 vs P12 31) PASS; G3 0/70 SUBMIT (1 HOLD) PASS.
* [M] Seen set (design-informed), lock `seen` (48d6d5cf...): G1 31/55 = 56.4% FAIL (K1 29/55); G2 +12.7 pp PASS; G3
  1/53 SUBMIT PASS.
* [A] Bounded repair: every fresh G1 loss attributed (search 1, A 12, S 5, C 8); none is a clear implementation defect
  (frozen criteria; one measured V3 trade-off); nothing to fix.  **Final state: NOT_READY** (G1 fails on the
  deciding set after the bounded repair).  Report: `k2/results/VALIDATION_K2.md`.
