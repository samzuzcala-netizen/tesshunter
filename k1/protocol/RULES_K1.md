# RULES_K1 — registration for prompt K1 (prepare the K-dwarf survey)

Registered 2026-10-08 (UTC) before any calibration, injection, false-alarm, adversarial or
known-planet run.  Its SHA-256 is recorded in `k1/manifests/registration.json`.  Any later change
is an amendment: a new dated file `k1/protocol/AMENDMENT_K1_<date>_<n>.md` that states the change
and why, hashed into the same manifest.  This file is never edited after registration except to
append the outcome section at the end (Part E), which is itself a dated, hashed addition.

Tags: [A] adopted here before measurement; [R] from the review
(`NEXT_POPULATION_REVIEW_2026-10-07.md`); [P] from the prompt (`PROMPT_K1_PREPARE.md`).
Nothing in K1 is a detection, a discovery or a submission.

---------------------------------------------------------------------------------------------

## 1. Definitions [A]

### 1.1 Usable sector
A sector `s` is usable for a star when `1 <= s <= 98` and an archival FFI light curve exists:
TESS-SPOC (sectors 1-85), or QLP except sectors 80, 83 and 85 (those count only through
TESS-SPOC).  Sectors 99-104 (QLP barycentric timing error) and 105+ (QLP not released) are
excluded.  One product per usable sector, TESS-SPOC preferred over QLP.  Native cadence: 1800 s
(s1-26), 600 s (s27-55), 200 s (s56+).  Code: `k1/protocol/sector_policy_k1.py`.  A QLP
redelivery of 99-104 or release of 105 during K1 does not change this policy; it is recorded as a
post-freeze option.  `n_usable` counts usable sectors from the cached QLP / TESS-SPOC target lists
(Part A); `n_usable_s56` counts those in 56-98.  For calibration hosts the realised count is the
number of usable products actually downloaded and readable.

### 1.2 Arms
`survey_k1` = every usable sector; `survey_k1_s56` = usable sectors 56-98 only.  Calibration and
validation hosts use FFI products only (no SPOC 2-min), even where 2-min data exist.

### 1.3 Observed transit
An epoch of a transit ephemeris is observed in an arm when the usable products of that arm have
at least 50% of the expected in-transit cadences inside +/- T14/2 of the predicted mid-time (the
expected count is T14 / the product's cadence), the same coverage rule as the Stage A event rule.

### 1.4 Expected SNR
For a transit model (injection, or catalogue model for a known planet) on a host and arm:

    SNR_exp = sqrt( sum over cadences i of usable products, quality- and low-precision-masked,
                    of  delta_i^2 / sigma_p(i)^2 )

`delta_i = 1 - model_i` is the noiseless model at cadence i integrated over that product's
exposure (batman, quadratic limb darkening, supersampling 7); `sigma_p` is the per-cadence
empirical noise of product p (1.4826 x MAD of the detrended, masked flux of the UNINJECTED host,
window 1.1 d), i.e. the K1 empirical error.  White-noise matched-filter SNR on the real sampling.
"Computed on the all-sector data" (rule E1) means the `survey_k1` arm's products.  Known-planet
models use the catalogue Rp/R* (else Rp and TIC R*), a/R* from P and TIC M, R (else catalogue
a/R*), b from the catalogue (else 0), Claret limb darkening at the TIC Teff and log g, and the
verified ephemeris (2.4).

### 1.5 Pre-gate, stages and endpoints
Route (frozen machinery of P12 with K1 inputs): search -> pre-gate (`stitch_snr >= 7.1`,
`stitch_n_transits >= 3`, `stitch_epoch_consistent`) -> Stage A (p10.0 event rules and six
criteria; K1 cadence-aware counts) -> Stage S (secondary scan; the gate mode is rule E2's choice)
-> Stage B (p10.0 with the K1 per-window cadence rule) -> Stage C (blind TLS 0.5-110 d, p10.0
strongest-peak rule with the conditional robust fallback and the cadence duration floor; decision
rule unchanged) -> Stage D (K1 tiers: p12.0 plus the K8 long-period HOLD of change 13).

**Reaches Stage C (the Stage C endpoint):** a candidate path matched to the planet (2.2) passes
the pre-gate, A, S, B and has Stage C decision PASS, and the Stage C blind period itself matches
the planet's period within 1% at a ratio in {1, 2, 1/2, 3, 1/3} (the path still represents the
same planet; a substitution by a companion or unrelated signal is a loss at C).

A planet is retained at a stage when ANY of its matched paths is retained there (all paths are
kept; first loss is the last stage reached by the best path).

### 1.6 Partition-limited host
A host whose search record has at least one partition with `budget_exhausted = true`
(`survey.budget_exhausted` on the partition notes; traces on).

### 1.7 False alarms per star
On the uninjected false-alarm hosts: pre-gate FA = accepted candidates passing the pre-gate,
divided by hosts searched (status ok); A-level FA = Stage A PASS candidates per host; S-level FA
likewise per mode.

### 1.8 Intervals
Wilson 95% for proportions.  Host bootstrap: resample hosts with replacement, 10,000 draws, seed
20261011, percentile 95% interval; a paired difference is bootstrapped on the same host draw.

---------------------------------------------------------------------------------------------

## 2. Sets and matching [A]

### 2.1 Calibration and validation sets (drawn before any search; `k1/manifests/`)
* Injection hosts: 250 (170 K, 80 eM) from the reserve (Part A), stratified by Tmag (10-11,
  11-12, 12-13.5) x n_usable (5-7, 8-12, >= 13), equal allocation per cell within class where the
  cell holds enough stars (shortfalls reallocated to the nearest cell in Tmag, recorded).
  Seed 20261008.
* False-alarm hosts: 250 (170 K, 80 eM) from the reserve, same strata, disjoint.  Seed 20261018.
* Known planets: NASA pscomppars (confirmed, tran_flag = 1, pl_controv_flag = 0) plus TOIs with
  TFOPWG disposition CP or KP.  Host: class K or eM by the A3 Teff and radius cuts (TIC values),
  log g >= 4.3 where given, not GIANT, Tmag 9.5-14.0, any |b|.  Planet: P 0.5-50 d, Rp 1-8 R_E, at
  least 3 observed transits in the all-sector arm from the verified ephemeris.  Ephemeris check:
  the 1-sigma propagated mid-time uncertainty at every usable epoch < T14 / 2, using the best
  published solution (pscomppars default; if it fails, the most recent ps row with
  smaller propagated error; the choice and the propagated error are recorded before truth is
  sealed).  Cap 220 planets: if more qualify, hosts are ordered by SHA-256 of
  "20261009:k1:kp:<tic>" and taken whole until the cap.  Split by host into DEV (40%) and
  HELD-OUT (60%) by the same hash order (first 40% of hosts DEV), seed string "20261010".
* Adversarial negatives: EBs from the TESS Ten Thousand catalogue (Kostov et al. 2025, journal
  tables 3/4) and the TESS EB catalogue whose host meets the A3 stellar cuts (step 1) at Tmag
  10-13.5 with P 0.5-50 d (target >= 50); blends: a class K or eM star (A3 step 1, Tmag 10-13.5)
  within 42" of a known EB (same catalogues, P 0.5-50 d) within 3 Tmag, the EB not the target
  (target >= 20); plus `data/adversarial/targets_v1.csv` cases whose hosts fit A3 step 1.  Split
  DEV 40% / HELD-OUT 60% by host with the hash order "20261012:k1:adv:<tic>".
* Truth tables (known-planet ephemerides, injection parameters, EB periods) are written under
  `k1/truth/` and sealed (hash in the manifest).  Search and funnel workers never read them; a
  guard refuses any worker path containing `k1/truth`.  Matching happens only after a prediction
  lock that hashes every saved prediction (Part F, and for Part D the per-phase result hashes).
* Every star touched is recorded in `k1/manifests/exposure_ledger.csv`.

### 2.2 Matching (identity) rule
A candidate (P_c, T0_c, duration d_c) matches a planet or injection (P_t, T0_t, T14_t, timing
error sigma_t(epoch)) when for some r in {1, 2, 1/2, 3, 1/3}:
1. |P_c / (r P_t) - 1| < 0.01, and
2. on the actual timestamps of the arm's usable products, with truth events E_T (epochs with at
   least one cadence within T14_t/2 of the truth mid-time) and candidate events E_C (epochs with at
   least one cadence within d_c/2 of the candidate mid-time), a truth and a candidate event
   coincide when their mid-times differ by less than 0.5 max(T14_t, d_c) + 3 sigma_t(epoch);
   coverage = coinciding truth events / |E_T| >= 0.8 min(1, 1/r); precision = coinciding candidate
   events / |E_C| >= 0.8 min(1, r); and at least 3 coinciding events.
Timing-uncertainty and TTV cases are flagged and reported separately without changing outcomes.

---------------------------------------------------------------------------------------------

## 3. Decision rules (Part E) [A]

Applied exactly as written; outcomes are appended to section 7 with their numbers.

**E1 Cadence.**  Pool: injections with expected SNR in [7, 20] computed on the all-sector data.
Retention through S = matched search path that passes the pre-gate, A (legacy ramp rule) and S
under mode `bound`, divided by the pool size.  Adopt `survey_k1` over `survey_k1_s56` when ALL hold:
(a) R(k1) - R(s56) >= 3 pp with host-bootstrap lower bound > 0; (b) pre-gate FA per star
k1 / s56 <= 1.5 (on the 250 FA hosts); (c) total search wall time over the paired injection jobs
k1 / s56 <= 3.  If it fails and the all-sector arm loses mainly at P > 10 d or on partition-limited
hosts, one bounded diagnostic: raise the budget to 8,100 s for the losing subset (injections at
P > 10 d or on partition-limited hosts) under `survey_k1`, re-run that subset, and apply E1 once
more.  Otherwise `survey_k1_s56` is adopted and the failure is explained in writing.  The E2-E3
pools then use the adopted arm.

**E2 S mode.**  Pool: injections at expected SNR [7, 40] (adopted arm) plus DEV known planets with
>= 3 observed transits.  Retention through S under mode m = items whose matched path passes the
pre-gate, A (legacy ramp) and S(m), over the pool size, pooled with equal item weight.  Choose the
mode with the highest retention subject to: its DEV adversarial pass-through (fraction of DEV
negatives with at least one path reaching SUBMIT or HOLD at the end of D) does not exceed
`bound`'s by more than 5 percentage points (absolute).  Exact ties go to the simpler mode in the
order bound, empirical_bound, recurrent_bound, recurrent_bound_corr, bound_alias.  Every mode's
retention and pass-through is reported.  S modes are evaluated from the same A outputs (one scan
records every mode); B, C and D run once on the union of S passers.

**E3 SAP-ramp variant (change 12).**  Pool: injections with expected SNR >= 7 (adopted arm).
Adopt the noise-relative ramp (fail only if the ramp exceeds max(1 x depth, 3 x the event's SAP
depth error)) if retention through A (matched path passing pre-gate and A) improves by >= 2 pp
over the legacy rule AND A-level FA per star (variant / legacy) <= 1.2.

**E4 Budget.**  On the 40-host timing pilot (Part C4, survey_k1, one injection each), the
partition-limited fraction is measured at 2,700, 5,400 and 8,100 s.  Use the smallest tested
budget with <= 5% partition-limited hosts; if none qualifies, 8,100 s and report the fraction.
Clarification: E4 is applied right after C4 (before Part D) so that the injection, false-alarm
and validation runs use the chosen budget; it is restated with the other outcomes in Part E.

**A4 re-rank.**  If the Part C noise refit changes more than 10% of the members of the top 7,000 K
or the top 3,000 eM (|old set minus new set| / set size), re-rank before the freeze and record
both rankings.

**Freeze.**  After E1-E4: `k1/protocol/config.json` and `k1/manifests/freeze_k1.json` (source
hashes of every K1 protocol file and every touched `src` module).  Later changes are dated
amendments.

---------------------------------------------------------------------------------------------

## 4. Part F gate (HELD-OUT, frozen configuration) [A]

Blind search -> prediction lock (hash every saved prediction) -> unseal truth -> match (2.2).

* **G1:** among HELD-OUT known planets with expected SNR >= 20 (frozen arm) and >= 3 observed
  transits, at least 60% reach the Stage C endpoint (1.5).  Count, Wilson and host-bootstrap
  intervals reported.  (Oct 3-4 comparable figure 27/41 = 66% [R].)
* **G2:** non-inferiority to P12 on the same G1 cohort: the paired difference in Stage C endpoint
  recovery (K1 minus P12) has point estimate >= -5 pp; the host-bootstrap interval is reported.
  P12 = an isolated copy of `aee65172b` running `survey_p10` and the p12 funnel on its own
  sectors 56-98 policy inputs (QLP 80/83/85 excluded), FFI products only to match K1.
* **G3:** HELD-OUT adversarial negatives: at most 5% have a path reaching SUBMIT; SUBMIT plus HOLD
  is reported.  Stage D outcomes of every recovered known planet are reported; any KILL of a known
  planet is listed with its cause.
* **One bounded repair:** if G1 or G2 fails, attribute every loss to a stage (Oct 3 stage-ledger
  method); fix only clear implementation defects (bugs, not threshold retuning); re-run on DEV
  first, then once on HELD-OUT.  If it still fails the final state is NOT_READY.

---------------------------------------------------------------------------------------------

## 5. Stop rules [P]

* STOP-A: population sanity fails (class K after step 8 outside 40,000-170,000; class eM with
  n_usable >= 5 outside 5,000-60,000; or top-10,000 E_new differs from the review by > 2x). Pause.
* STOP-B: a P12 regression that cannot be fixed.  Pause.
* STOP-C: priced Parts D-F exceed 60 queue-hours.  Pause with options (fewer injections, not below
  600; fewer FA hosts, not below 150; a cheaper BLS grid only if a paired 100-injection check loses
  <= 2 pp).
* STOP-D: C: below 25 GB or D: below 100 GB free.  Pause, or relocate caches behind a junction with
  a receipt.
* STOP-E: a survey-list star is downloaded or searched: record it, move it to the exposed list,
  refill from the reserve in rank order, continue.
* STOP-F: a MAST/archive outage > 6 h, or unknowns > 10% of a phase.  Pause; unknowns are never
  relabelled as non-detections.
* STOP-G: a registered rule cannot be applied as written: write an amendment before acting; pause
  if the choice is not mechanical.

## 6. Seeds [A]

| use | seed |
|---|---|
| population build / ordering | 20261007 |
| injection-host draw | 20261008 |
| false-alarm-host draw | 20261018 |
| injection parameters | 20261009 |
| known-planet cap/split hash prefix | "20261009:k1:kp" / "20261010" |
| adversarial split hash prefix | "20261012:k1:adv" |
| host bootstrap | 20261011 |
| timing-pilot host draw | 20261013 |
| injection-C stratified sample | 20261014 |
| TRICERATOPS (unchanged from P12) | 20260902 |

## 7. Outcomes (appended in Part E; empty at registration)

Recorded 2026-10-11T19:39Z (Part E). Sources: k1/results/e1_partD.json, e1e2_amended.json, e3_partD.json,
timing_pilot.json, decisions_E.json. Prediction locks partD_S and partD_dev verified before each computation.

* **E4 (applied after C4, before Part D) [M/A].** Partition-limited fraction on the 40-host pilot (survey_k1):
  37.5% at 2,700 s, 20% at 5,400 s, 15% at 8,100 s. None <= 5%, so **8,100 s** is used; the fraction is reported
  (15%, 6/40). Part D measured 14.4% on the 250 FA hosts (survey_k1) and 0% (survey_k1_s56).
* **E1 as registered [M/A].** Pool: 259 injections (166 hosts), expected SNR 7-20 on the all-sector data; S mode
  `bound`. R(k1) 18.5%, R(s56) 15.8%, +2.70 pp, host-bootstrap 95% [-2.56, +7.78]: (a) fails. (b) pre-gate FA per
  star 2.692 / 2.212 = 1.22 holds. (c) search wall 1.69 holds. The registered outcome is survey_k1_s56. The
  diagnostic does not apply: of the 20 s56-only recoveries, 2 are at P > 10 d and 4 are on partition-limited hosts.
  The written explanation is k1/results/E1_DECISION_K1.md.
* **AMENDMENT_K1_20261011_3 (post-hoc; user decision in chat) [A].** E2 is applied on survey_k1 first, then E1's
  (a)-(c) are re-applied under the selected mode.
* **E2 [M/A].** Pool: 439 survey_k1 injections (expected SNR 7-40) plus 78 DEV planets = 517 items. Retention
  through S: `bound` 118 (22.8%), `empirical_bound` 137 (26.5%), `recurrent_bound` 158 (30.6%),
  `recurrent_bound_corr` 158 (30.6%), `bound_alias` 181 (35.0%). DEV adversarial pass-through to SUBMIT/HOLD at the
  end of D is 0/35 for every mode (limit `bound` + 5 pp = 5%). **Mode: `bound_alias`.**
* **E1 under `bound_alias` (amendment 3) [M/A].** R(k1) 28.6%, R(s56) 18.9%, +9.65 pp, host-bootstrap 95%
  [+3.94, +15.09]. (a) holds, (b) 1.22 holds, (c) 1.69 holds. **Adopted: survey_k1 (all usable sectors).**
* **E3 [M/A].** Pool: 757 survey_k1 injections (246 hosts), expected SNR >= 7. Retention through A: ramp variant
  354 vs legacy 355, a gain of -0.13 pp (rule: >= 2 pp). A-level FA per star 0.088 / 0.088 = 1.00. **Not adopted:
  the legacy SAP-ramp rule stays.**
* **Frozen:** survey_k1, time budget 8,100 s, S mode `bound_alias`, legacy ramp rule. Amendments 1 (QLP 74-79 v02)
  and 2 (exposure-aware Stage A depth) are in force.

**Addendum 2026-10-12T21:17Z: AMENDMENT_K1_20261012_7 (evaluator fix: P_c = the candidate's stitch re-measured period).**
Predictions are unchanged; the ledgers were recomputed under the partD_S / partD_dev / partD locks.

* [M] E1 as registered (`bound`): +18.53 pp (R 42.9% vs 24.3%), host-bootstrap 95% [+13.11, +23.83].
  (a), (b) and (c) all hold, so **survey_k1 under the registered rule itself**; amendment 3 no longer changes the
  outcome.
* [M] E2: `bound_alias` 313, `recurrent_bound` 310, `recurrent_bound_corr` 310, `empirical_bound` 289, `bound` 256
  (of 517). Adversarial pass-through is 0/35 for every mode. **`bound_alias` (unchanged).**
* [M] E1 under `bound_alias`: +23.94 pp [+18.18, +29.55]; R(k1) 50.6% vs R(s56) 26.6%.
* [M] E3: 567 vs 568, -0.13 pp. **Not adopted (unchanged).** E4 is unchanged.
* **Frozen configuration unchanged.**
