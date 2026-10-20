# PREREGISTRATION P12 (Part 1a)

Written 2026-09-23 before any Part 1 to Part 6 measurement, sealed with `p12/protocol/config.json`, `PROMPT_P12.md` and every `p12/protocol/*.py` in `p12/manifests/registration_seal.json` (later modules and the Part 3 freeze receipt are sealed by immutable, hash-linked chain additions under `p12/manifests/registration_chain/`). `PROMPT_P12.md` (SHA-256 `8be9b707fa7da8a4c0e86e182f92963e21ec3f6fc4c799d52dda5612354b68a3`) is the governing text; this file restates its rules and thresholds, adds the amendment LB1c the user requested at decision point 1, and fixes the implementation readings the prompt leaves open. Evidence tags: [A] adopted before measurement, [P10] / [P10.3] / [P8] / [P9] inherited, [I] interpretation. A threshold changes only before its judged table exists, recorded in `p12/protocol/AMENDMENTS_P12.md`; a change that fails its bar is not adopted and not retried with a lower bar.

Decision point 1 (6.3): tier **E1** (`p12/manifests/decision_point_1.json`, 2026-09-23T15:42:19Z).

## 1. Objective and definitions (sections 2a, 2b, 3a, 8)

- `p12.0` = (population, photometry input, search preset, funnel rules, endpoint tiers). Components inherited from a settling measurement (2d) or decided in P12 by a rule written here before its measurement. Frozen in `p12/manifests/freeze_p12_0.json` (Part 3) before the launch bar is measured and before any per-candidate record of the final population is opened. The final search runs whether or not the bar is met; the final state names which.
- Final states (exactly one): `FINAL_SEARCH_DELIVERED_BAR_MET`, `FINAL_SEARCH_DELIVERED_BAR_NOT_MET`, `STOPPED_AFTER_FINAL_SEARCH_INCOMPLETE`, `STOPPED_BEFORE_FINAL_SEARCH`, with the conditions and deliverables of section 8. Expected with N1 = 1: `FINAL_SEARCH_DELIVERED_BAR_NOT_MET` [A].
- Nothing is a detection, discovery, confirmation or submission; the agent never submits, never pushes, never deletes historical data.

## 2. Population and inputs (2c, 0e, 5a)

- Core: the 2,000 P8 stars (`data/survey/targets_p8.csv`) and the 436 input-eligible bare-TCE stars (`p10/part3/manifests/targets_evaluated.csv`) under `hard_stop_p10` (bare TCE = FLAG with F7), re-checked on the P12 catalogue snapshot (0d): a new TOI, CTOI, NASA or TESS-EB match makes a star `REJECT_NOVELTY`. Input policy: fewer than 3 usable sectors (>= 3 sectors of >= 50 points, >= 100 finite points, finite scatter) = `INPUT_INELIGIBLE(sectors)`, listed, never searched. Measured: 1,622 of 2,000 and 436 of 436 eligible; 241 of 300 calibration hosts [M, Part 0].
- Photometry: SPOC / TESS-SPOC `pdcsap_flux`, QLP `det_flux`, preference SPOC > TESS-SPOC > QLP, biweight 0.75 d, frozen sector policy (`p10/part3/manifests/sector_policy_effective.json`, SHA-256 `27c1cc81…`): science sectors 56 to 105, QLP 80, 83, 85, 99 to 104 excluded, QLP 74 to 79 under the corrected-v02 comparison. One candidate change: QLP `DET_FLUX_SML` (Part 2). No pixel extractor, no SAP test.
- Search: `survey_p10` frozen (0.5 to 30 d, durations 0.02 to 0.20 d, slots 6/24/16, `rank_by="snr"`, 2,700 s detector budget; `src/tesshunter/survey.py` lines 230 to 237). No search change is tested.
- E1 (chosen): the top 1,000 of the 7,989 unselected qualified CLEAN stars by `M = sqrt(n_pol) / (sigma_Tmag x rad^2)` (`p12/manifests/targets_ext_E1.csv`); acquired, verified and calibrated as 5a; carries `population_tier = "E1"` in every table and packet; no admission rule.

## 3. Vetting route and the endpoint (2c, 1b)

- `p10.0` route: pre-gate (stitch SNR >= 7.1, >= 3 transits, epoch-consistent) -> A (six criteria) -> bound S -> B (flags) -> C (TLS at native cadence, SDE >= 9, strongest peak with the robust fallback, one-cadence duration floor, oversampling 3, 3 jobs x 8 threads) -> D. Stages A, S, B and C run the `p10.0` rules under `p12.0`.
- C on every B passer, no cap: deadline 12,240 s, one recorded retry at 36,000 s, then `UNRESOLVED` (never a rejection). D on every C passer and every UNRESOLVED case (UNRESOLVED capped at HOLD by H6).
- Endpoint `p12.0` = `p10.0` tiers (`src/tesshunter/verdict_tiers.py`, unedited) plus the overlay `p12/protocol/rules_p12.py`:

| id | change | p10.0 -> p12.0 |
|---|---|---|
| A1 | `TIER_DENSITY_RATIO_RANGE` (K8 guard) | (0.5, 2.0) -> (0.5, 2.5) |
| A2 | `TIER_ODD_EVEN_SIGMA` (K6) | 3.0 -> 3.5 sigma |
| A3 | H5 | holds when the K9b disagreement holds in exactly one measurable sector and no KILL fired (`TIER_MIN_SECTORS` unchanged) |
| A4 | K10 | a KILL after K9 if admitted by 1c, else flag F10 on every D record |
| A5 | H6 | a C outcome UNRESOLVED after the retry gets D and a verdict of at most HOLD |
| A6 | `candidate_tier` (SUBMITs) | tier 2 when F5 is `on_target_consistent` in >= 2 measurable sectors, or the TESScut centroid is informative in >= 2 sectors; else tier 1 |
| A7 | K0 wiring | `crossmatch_p12.py` + `hard_stop_p10` (bare TCE = FLAG with F7), not `cat.check` |

- Order: K0 .. K9, then K10 when admitted as a KILL; then H1 .. H4, H5, H6; SUBMIT otherwise. Every condition is evaluated and recorded; a missing input is not measurable (`fired = null`), never "not fired".
- A6 reading [A/I]: per sector with a usable centroid (available, >= 3 in-transit and >= 10 out-of-transit cadences, non-zero error), the 3-sigma radius is `3 x shift_err_px`; "within 3 sigma of the target" is `total_shift_px <= 3 x shift_err_px`; the radius must be <= 1 pixel; a capable neighbour is a star of the candidate's neighbour table whose flux ratio `10^(-0.4 x delta_mag)` (the table's Gaia delta magnitude standing for dTmag) is at least the reference depth D_ref (as a fraction); the table carries no direction, so a capable neighbour is excluded from the region only when `sep_px - total_shift_px > 3 x shift_err_px` (it lies beyond the region's farthest point). A consistent centroid failing the radius or neighbour condition is `target_consistent_unlocalised` and does not count.
- Every SUBMIT carries F1 to F10 and: "The field's validation bar (resolved source, localised repeated dimming, low FPP) is out of reach for TESS FFI photometry alone at Tmag 13.5; this is a candidate for follow-up, not a validated planet." If the bar is not met every SUBMIT's F9 names the failing clause.
- K9 reading [I]: K9 fires only on its numeric criterion (both clauses in >= 2 sectors) plus the reviewer's recorded decision. No reviewer record exists for new P12 candidates, so K9 cannot fire for them; a K9 criterion that holds is reported on the record and in the packet, a one-sector K9b disagreement is held by H5, and the user's review belongs to decision point 3. The plumbing test uses the P8 reviewer records, which is why its expected verdicts include K9.
- Redaction (negative sets TTT, TTT-adjacent, P9 negatives): `KNOWN_STATUS_REDACTED` for K0; the catalogue clause of K5 (K5b) and H4 computed, recorded and excluded. The natural set of 4d, the P9 positives and the ephemeris-assisted leg are not redacted.

## 4. K10 (1c), written before the calibration runs [A]

- K10e: `n_excluded / n_observed > 0.5` on the Stage A chosen ephemeris; not measurable when `n_observed < 4`.
- K10s: `sap_kept.weighted_mean_depth_ppt < 0.5 x det_kept.weighted_mean_depth_ppt`, the difference above 3 x the quadrature sum of their `err_ppt`, kept events in >= 2 sectors; not measurable when a depth or error is missing (fewer than two kept sectors is "not fired").
- Sets: (a) the four P8 reviewer artefact KILLs (`tic230120862_P16.7959`, `tic80256158_P10.8184`, `tic144277542_P12.9812`, `tic155895971_P13.1279`) and the two HOLDs (`tic154566869_P8.9053`, `tic404927114_P27.5436`); (b) the P8 Stage A passers, descriptive; (c) the Stage A PASS records of the sealed P10 2d injections; (d) the Stage A records of the 12 P9 named-planet rows of `tier_rederivation.csv` (TIC 33595516, 41422753 and the two uncertain TOIs excluded).
- Denominator [A]: fired / all records of the set; a not-measurable record counts as not fired. Wilson 95% intervals reported.
- Admission: eligible when the variant fires on <= 2.0% of (c) and on none of (d); K10 is the OR of eligible variants, re-checked against both bars (drop K10s, then K10e, until it passes); KILL when the OR fires on `tic144277542_P12.9812` and on >= 3 of the 4 artefact KILLs, else flag F10. Word `K10_KILL` or `K10_FLAG` in `p12/results/part1/k10_calibration.json`. Expected: `K10_FLAG`, the 144277542 class held by H5 [A, from the design-time look recorded in the prompt].

## 5. Part 1 checks (1d)

- Plumbing: the six P8 D inputs copied to `data/survey/p12/plumbing_p8/` with a receipt (the stage records the prompt names, plus the Stage C `tls` records D reads, the P8 reviewer `pixel_followup` records K9 reads, and the keys' table rows); `plumbing_d` (2 workers, 5,400 s) runs `stage_d_worker_p12.py --product-source p8_store` (p8.0 stage rules and survey_p8 ingestion, the products P8 used), 100,000 TRICERATOPS draws, cutouts re-fetched to `D:`, packets under `docs/packets/audit_p12/plumbing_p8/`, each record stamped under p10.0 and p12.0. Expected under p10.0: 230120862 KILL K9 (K9 H1 H2); 80256158 KILL K8 (K8 K9); 154566869 KILL K8 (K8 H1); 155895971 KILL K8 (K8 K9); 404927114 HOLD H3; 144277542 SUBMIT. Under p12.0 the same except 144277542 HOLD H5 (or KILL K10 if admitted and firing). A difference caused by a live measurement is recorded with both values and the expectation updated in AMENDMENTS_P12.md (measurements only, never rule constants); any other difference is a defect: fix once and re-run; a second failure is STOP-3.
- Re-scoring: `tier_rederivation_p12.py` re-scores the 35 saved records under p12.0; exactly the flips of 1b (A1: `tic178709444_P3.4721` KILL -> SUBMIT-equivalent; A2: `tic231702397_P5.0783` KILL -> SUBMIT-equivalent; A3: `tic144277542_P12.9812` SUBMIT -> HOLD H5) plus the K10 outcome; an unlisted flip is diagnosed (a correct consequence of a registered definition becomes a correction; an implementation error is fixed). The p10.0 evaluations with the overlay loaded reproduce the sealed `p10/results/tier_rederivation.json` exactly. Label: "re-scoring of seen records under pre-registered rules, not a validation".

## 6. Part 2: calibration under the frozen input policy and the photometry test

- Arm A (archival): every injection of `data/survey/injections_p8.csv` on `E_cal` (calibration hosts eligible under the policy; an injection on an ineligible host is `INPUT_INELIGIBLE`, reported, never a miss) prepared evaluator-side (`load_policy_products -> harmonise_cadence -> survey_p8.inject_products -> build_prepared`), searched blind under `survey_p10` (24 workers, 3,600 s), scored after the lock: recovered = period within 1% and overlapping windows; alias (2, 3, 1/2, 1/3) reported, never credited; expected SNR on the uninjected array. Funnel: pre-gate recorded on every recovered injection; A (1,200 s) on every recovered injection and every false-alarm pre-gate passer; S (300 s) on every A passer; B on the false-alarm S passers; one recorded retry pass per phase. C (3 x 8 threads, 12,240 s, retry 36,000 s) on 30 S-passing injections, 10 per expected-SNR bin [7,12), [12,20), [20,50), seed 20260908 over sorted job ids. Real leg: the 436 from their 0e arrays (asserted equal to the P10.3 prepared arrays by SHA-256), matched to the P12 sidecar by the P10.3 rule (exact or 2, 3, 1/2, 1/3 with the epoch check), INDEPENDENT present families counted. Report `COMPLETENESS_ARM_A.{md,json}` in the tables of `COMPLETENESS_P10.md` with alias-credited and policy-loss rows.
- SML rule [A]: a sector uses `DET_FLUX_SML` in place of `det_flux` iff the selected product is QLP, the column exists and its finite fraction is >= 0.9 of `det_flux`'s; all else unchanged; NaN errors filled by the robust-scatter rule; injections enter the swapped column like the default. Gate: arm B runs only if >= 100 `E_cal` hosts have >= 1 SML-usable sector and SML-usable sectors are >= 15% of the selected sector products on `E_cal`; else `KEEP_ARCHIVAL (NOT_TESTABLE)`.
- Arm B clauses (all required), paired on identical job and host ids, arm A's 2b rows as baseline: R_7_15 search-only gain B - A >= +5.0 pp; the same through pre-gate, A and S >= +3.0 pp; R_15_30 B >= A - 2.0 pp; false-alarm pre-gate passers B <= 1.5 x A; S passers B <= 3 x max(A, 2); INDEPENDENT present families on the 436 B - A >= 0 (paired bootstrap interval reported); median job wall B <= 3 x A; unknowns after the retry pass <= 5% per arm, an unknown counted a miss in B and a recovery in A. Word `ADOPT_SML` or `KEEP_ARCHIVAL`; on `ADOPT_SML` the remaining injections and the 30-injection C sample run on the SML input, `COMPLETENESS_ARM_B` is written and the core SML inputs are built.
- Report-only tabulations: `window_check.json` (retention and 1-hour noise at 1.0 and 1.5 d windows on the 60 arrays of `data/survey/p11/audit_prepared_v2/`), `long_period_tabulation.json` (INDEPENDENT present families with depth < 10 ppt and duration < 4.8 h per period bin beside injection recovery), `s_mode_restatement.json` (the 17.2% S false-kill rate, 200/1,164, a limit).
- After Part 2 `forecast_p12.json` is re-rendered with the measured wall ratio (at most 3), carrying every measured repricing forward.

## 7. Part 3: the freeze

`freeze_p12.py` writes `freeze_p12_0.json`: population, eligibility and E1 manifest hashes; the photometry word and its table's hash; the `survey_p10` preset hash; the `rules_p12.py` hash, the amendment table and the K10 word; sector policy, catalogue snapshot and sidecar hashes; seeds; completeness-table hashes; every `p12/protocol/*.py` hash; an exposure-ledger snapshot; appended to the registration seal as a chain link. From then no threshold, preset, policy, catalogue or population changes; the controller verifies the receipt before every `neg_*`, `bar_*`, `final_*` phase (mismatch = STOP-1).

## 8. Part 4: independent specificity, held-out endpoint, launch bar

- A negative is SUBMIT-equivalent when a candidate on it matching the binary's catalogue period family (exact or 2, 3, 1/2, 1/3 within 1%, scored after the prediction lock) ends SUBMIT (tier 1 or 2) under p12.0 with the redaction. End to end = under the final search's route (S and B gate); at D = under the forced route over the negatives reaching D. Blinding: no worker opens the TTT ephemerides or `p9/truth/`; predictions locked at search closure; every negative reaching D gets a one-paragraph autopsy in `SPECIFICITY_P12.md`.

| clause | instrument | threshold | decisive when |
|---|---|---|---|
| LB1a | TTT binaries under the domain cuts, end to end; N1 = stars searched COMPLETE | <= 1 of N1 | N1 >= 20; `bar_met` requires this clause decisive |
| LB1b | same set, forced route at D | <= 1 of N1_D | N1_D >= 5 |
| LB1c (amendment, reported, never part of bar_met) | TTT adjacent domain (K and late-K dwarfs), end to end (LB1c-a) and at D (LB1c-b) | <= 1 of N | N >= 20 |
| LB2a | 13 unexposed P9 negatives, end to end | <= 1 of 13 | always |
| LB2b | same set, forced route at D | <= 1 of N2_D | N2_D >= 5 |
| LB3 | 12 unexposed P9 positive hosts (13 signals), ephemeris-assisted A to D at the truth ephemeris after the blind lock: signals KILLed by K6, K8 or K10 / n_fit | <= 1 of n_fit | n_fit >= 5 |
| LB4 | non-2b injections on eligible hosts: whole-funnel recovery under p12.0 / recovery of the same job ids in `injection_outcomes_p10.csv` (`through_funnel_pregated`) | >= 0.90 | always |

- `bar_met` = LB1a decisive AND every decisive clause holds; a non-decisive clause is printed NOT MEASURED with its N and outcome and never counts as a pass. Wilson 95% upper bounds printed beside the table: 11.4% on 0/30, 16.7% on 1/30, 22.8% on 0/13, 43.4% on 0/5. The bar detects a gross specificity failure and cannot detect a 3% false-SUBMIT rate.
- Sets: (i) the TTT stars of `ttt_negatives.csv` (N1 = 1, from the journal MRT union) under phases `neg_ttt_*`; (i') LB1c, the 30 stars of `ttt_adjacent_negatives.csv` under phases `neg_ttta_*` with the same route, redaction and blinding; (iii) the P9 held-out hosts (12 positive hosts: TIC 239275865, 122063843, 298074836, 164778883, 158983792, 120315006, 48448415, 122673489 (two signals), 164832454, 399955825, 298837729, 120254625; 13 negatives: TIC 149473467, 151826930, 379783522, 287669537, 349059354, 269238622, 279462605, 172421004, 80025900, 265489698, 229804573, 207174531, 157568289), harness `p12/heldout/` copied from P9 with the eight registered edits of 4c, P9 layout as ceiling (4 search and A workers, 2 C x 8 threads, 2 D); (ii) the natural load of the E_cal false-alarm stars' A passers (C forced with retry, D not redacted), reported, a SUBMIT there listed with `opened_in_part4`.
- Worker path alias [A/I]: `blind_io_p12` protects every path component containing "ttt" (the TESS Ten Thousand table), so every path a `neg_ttt*` / `neg_ttta*` worker reads or writes uses "tenk" in place of "ttt" (controller receipts keep the registered phase names).

## 9. Part 5: the final search

- Every phase `final_*`; every worker verifies the freeze. E1 first: relocation (done at decision point 1, receipted), a 50-star acquisition pilot whose per-star bytes and wall replace the forecast's when higher, batches of 100 in ascending TIC (4 workers, 600 s, one transport-class retry pass, every `index.json` checked), neighbours, `verify_prepare`, the extension calibration (300 eligible extension stars by SHA-256 of `20260920:ext_cal:<TIC>`, 600 injections from a P12 copy of `scripts/make_injection_spec.py`, 2 per star, seed 20260920, 1 to 4 Re, 0.5 to 30 d, plus the same 300 as false-alarm stars, through search, pre-gate, A, S; `COMPLETENESS_EXT.{md,json}`); no admission rule.
- `final_search` (24 workers, 3,600 s), one attempt then exactly one recorded retry pass; unknowns are UNKNOWN in every table; predictions locked (`final_predictions_lock.json`) before the sidecar is opened. Collect, pre-gate, `final_A` (1,200 s, one retry pass), `final_S` (300 s) on every A passer and a seeded 10% of A failures (seed 20260920) for the natural-load table, `final_B` (300 s) on every S passer (PASS or HOLD), `final_C` on every B passer (no cap; ordered by `ranking.score_v2` for scheduling only; 12,240 s then 36,000 s; UNRESOLVED), `final_D` (2 workers, 5,400 s) on every C passer and UNRESOLVED case with the frozen snapshot, F7 from the P12 sidecar after the lock, the all-transit fit seeded by the Stage C accepted ephemeris (see 11), 100,000 TRICERATOPS draws, TESScut centroids (240 s per cutout), neighbour tables (P8's for the 2,000; `final_neighbours` for any star without one), difference images and fixed apertures where >= 16 clean sky pixels exist; a D measurement that did not run is H3, re-run once in `final_D_retry`, then delivered as HOLD H3. Candidate list, natural-load table against P10 (11.65 / 2.363 / 0.150 / 0.0067) and P10.3 (9.93 / 2.53 / 0.672 / 0.067 / 0.011) rates, novelty re-check (TOI and CTOI only, 600 s; `ALERTED_SINCE_SNAPSHOT`, no verdict change).

## 10. Part 6: completeness, audit, seals, shutdown

- `COMPLETENESS_P12.md` as 6a: recovery by radius (1.0-1.41, 1.41-2.0, 2.0-2.83, 2.83-4.0 Re), period (0.50-1.39, 1.39-3.87, 3.88-10.76, 10.80-29.96 d), Tmag (12.5-13, 13-13.5, 13.5-14) and rotation amplitude with bootstrap intervals, exact and alias-credited rows, the policy-loss row, SNR50 and SNR90 per stage beside P10's; scope stated wherever quoted (through S; C on the 30-injection sample; D only by LB3; the delivered list's D-level completeness is not calibrated by injections); one sentence per period and radius class with the through-S 10% recovery point; the limits; the extension's table; the yield model as one labelled row; assumptions.
- Closing sentence (6b) [A]: "The registered P12 work on these inputs is complete; these measurements bound what it can find, and the specific experiments that could move those bounds are X", X listing each item whose condition holds: (1) through-S recovery at 1.0 to 1.41 Re below 15% -> pixel-level photometry; (2) retention at 1.0 or 1.5 d above 0.935 by >= 0.02 with a 1-hour noise ratio <= 1.05 -> a detrending-window test (about 20 queue-hours); (3) >= 30 planet-like families above 5 d recovered >= 15 pp below the injection bin -> a long-period search variant; (4) LB3 NOT MEASURED -> an unexposed in-domain truth-positive set; (5) if none, new sectors beyond 105 with the probe count.
- Seals of every file under `p12/` and `data/survey/p12/`, `integrity_check_p12.py final` (0 mismatches), the three suites alone (891 passed 1 skipped / 118 passed / all P12 tests), `p9_verify_p12.py final` (397 checks, only `baseline_git_HEAD_unchanged` failing, `p9/results/verification.json` hash equal to entry), `ledger_p12.py final`, `final_shutdown_p12.py` (routine `DISABLED_VERIFIED`), final state on line 1 of `HANDOFF_P12.md` and `docs/AUDIT_P12.md`, commit "prompt 12 part 6: final delivery", decision point 3.

## 11. Implementation readings fixed now [A/I]

1. Stage D fit seed: under p10.0 stage rules `audit_p5.fit_step` seeds from the survey ephemeris and `measure_one` then refuses the fit; the P12 D worker seeds the fit from the Stage C blind ephemeris exactly as `audit_p5._p8_fit_input` does for p8.0 (period, epoch, the wider of the survey and TLS durations) and installs that seed for the downstream consistency checks. A Stage C UNRESOLVED case (H6) is seeded from the survey ephemeris, and its fit reads the Stage A forced narrow-TLS record in place of the absent blind TLS record (recorded on the fit record).
2. Stage D historical writers: `scripts/p8_stage_d_packets.py` `setup` calls `p8_funnel.set_root` (survey_p8 ingestion) and `scripts/p8_eb_difference_image.py` refuses non-P8 records, so D uses P12 copies (`stage_d_packets_p12.py`, `stage_d_pixels_p12.py`) with the pure historical methods imported read-only.
3. Controller and supervision: the Claude session check-in (6.2) is a session cron whose whole instruction is the check-in command and its contract; the historical Codex routines and the paused Codex P12 routine stay PAUSED; the detached launcher uses Windows PowerShell 5.1 when PowerShell 7 is absent.
4. LB1c: the enumerated cuts on the union with fresh TIC v8 metadata; no radius cut and no pool join (both encode the M-dwarf domain); 30 selected, the LB1a star among them [M, `ttt_adjacent_selection.json`].
5. Forecast: decision point 1 re-rendered `forecast_p12.json` with the E1 rows and the LB1c line; each planner-written jobs manifest is priced for STOP-6.

## 12. Stop rules (section 5)

STOP-1 integrity (a historical seal hash differs; `data/cache/catalogs/` changed; a guarded path in a worker's opened files; a live source hash differs from the freeze after Part 3); STOP-2 storage (`C:` below 25 GB + 1 GB with no permitted relocation, or `D:` below 50 GB); STOP-3 entry or engineering (a Part 1 expectation check or a copied module's test still failing after one fix); STOP-4 user stop (`p12/manifests/USER_STOP` or in chat); STOP-5 owner loss (unreconcilable by `recover_p12.py`, or a recycled owner file); STOP-6 overrun (a phase's queue-hours above twice its forecast with margin; the user writes `CONTINUE_<phase>` or `USER_STOP`); STOP-7 broken phase (more than 5% of a phase's jobs operational unknowns after its one recorded retry pass, outside Stage C). Not stops: a launch-bar clause failing or not decisive; K10 entering as a flag; the SML gate failing or the arm not adopted; N1 < 20; a development pair with more than 5% unknowns; a SUBMIT in the natural-load set; final-search unknowns <= 5% after the retry pass; Stage C timeouts. Every stop writes `stop_<id>_<utc>.json`, closes owned jobs by identity, pauses the routine (decision point 2).

## 13. Amendment table against `HANDOFF_P10.md` 0.7 / 0.8 and `PROMPT_P10_3.md`

| item | before | P12 |
|---|---|---|
| Stage C | capped (150 in score_v2 order; P10.3 cap left 23 of 29 B survivors unrun) | uncapped, one retry at 36,000 s, then UNRESOLVED |
| D on UNRESOLVED | none | D runs, verdict capped at HOLD (H6) |
| completeness | P10 2d on the pre-P11 sector set | re-measured under the frozen policy (Part 2) |
| stop rule 1 | go/no-go on SNR50 | SNR50 reported |
| stop rule 2 | negative SUBMIT-equivalent > 1/N | LB1a / LB1b / LB2a / LB2b with decisive-N guards |
| stop rule 3 | positive SUBMIT-equivalent 0 of 18 | LB3 on ephemeris-assisted fits with the n_fit >= 5 guard |
| tiers | SUBMIT / HOLD / KILL | two SUBMIT tiers (A6) |
| endpoint | p10.0 | A1 to A7 |
| negatives | natural route | forced route and catalogue redaction (4a) |
| population | core only | E1 extension, own calibration, no admission rule |
| LB1c | none | adjacent-domain negatives, reported, never in bar_met |

## 14. Seeds

NumPy PCG64 `20260920` for any new draw (without replacement over sorted keys); `2026092001` for every paired host bootstrap (10,000 draws, percentile 95% intervals); `2026092002` for fixtures and relocation samples; the sealed `20260902` (P8 injections), `20260904` (the 300 calibration stars) and `20260908` (the 2b subset, the C injection sample, the TTT and LB1c order) reused. Ordering hashes are `sha256("<seed>:<purpose>:<integer TIC>")` ascending.

## 15. Assumptions

Section 9 of the prompt, all sixteen, restated by reference and binding; plus [A] the LB1c adjacent-domain set is a fair test of the light-curve, fit and pixel conditions on K dwarfs and says nothing directly about the M-dwarf domain.
