# RESUME_K2 - prompt K2 (cheaper Stage C, cross-product depth consistency, sibling masking; do not launch)

Prompt: `C:\Users\seanj\Downloads\PROMPT_K2_PREPARE.md` (identical copy in `..\PROMPT_K2_PREPARE.md`).
Registration: `k2/protocol/RULES_K2.md` (hash in `k2/manifests/registration.json`).
Evidence tags: [M] measured in K2, [R] review / K1 record, [A] adopted or registered, [I] interpretation.

**Resume here:** read the last dated entry below, then `k2/manifests/` and `k2/logs/checkins.jsonl`.

## Start-of-run record (2026-10-14 UTC)

1. Git [M]: branch `k2/prepare` created from `k1/prepare` at `1a1344283`.  Working tree before K2: the 6
   LibreOffice lock files under `p12/results/funnel/final*/` still deleted-unstaged (pre-K1, never staged), many
   untracked P10/P12 files.  K2 stages only `k2/` and the one shared `src` change.
2. Free space [M]: C: 35 GB, D: 563 GB (floors 25 / 100 GB).  C: is 10 GB above its floor; K2 writes data only to
   `D:\tesshunter_k2`.
3. K1 inputs read [R]: `k1/READY_K1.md`, `k1/results/VALIDATION_K1.md`, `k1/results/CALIBRATION_K1.md`,
   `k1/results/survey_price.json`, the dated log of `k1/RESUME_K1.md`.
4. R-C composition [R, K1 receipts]: 119 jobs (dev_k1 61: 56 on DEV known-planet hosts, 5 on DEV adversarial
   hosts; inj_k1 58).  K1 decisions PASS 77 / FAIL 42.  n_usable classes 0-8: 64, 8-13: 29, 13-20: 4, 20-30: 5,
   >= 30: 17 (22 jobs on >= 20-sector hosts, K1 median wall ~31,000 s).  K1 R-C job-wall total 220 h.
5. Design decision [A]: the C1 variants transform K1's prepared C input inside the K2 worker (patched
   `audit_p5.load_prepared`), so the input configuration, K1's A/S/B records and Stage D's consistency checks are
   unchanged in a copied case root.  A1 is the only shared-`src` change (`event_vet.DEPTH_CONSISTENCY_FAMILIES`,
   default None).  K1 workers run under the K2 controller with `K1_DATA=D:\tesshunter_k2`.

## Dated log
- 2026-10-14T16:59Z **Part 0: RULES_K2.md registered** (sha256 9599fc20..., LF file) before any K2 measurement.
- 2026-10-14T17:05Z K2 code: k2_common, c_input_k2 (V1-V4, M1 mask), funnel_k2 (A/S/B/C worker), controller_k2 /
  launch_k2.ps1 / checkin_k2 (derived from K1 by `k2/work/make_controller_k2.py`), event_vet A1 option.
  k2/tests 14 passed (C input: binning keeps the transit-integrated depth within 2%, the duration floor follows
  the binned cadence; M1 two-planet synthetic returns the masked planet's own period; A1: 5% product offset
  passes, alternating EB fails, 40% blend offset fails, default path unchanged and 60 K1 Stage A receipts
  re-evaluate to their recorded criteria; default C path reproduces K1 receipt dev_k1_144401492_p01 exactly).
- 2026-10-14T17:16Z Regression after the event_vet A1 option (`k2/work/run_regression_tests.sh part0`, logs
  k2/logs/tests_part0/): tests/ 786 passed + 1 skipped, p11 7, p11_5 98, k1/tests 60, k2/tests 14, p12 PASS 248,
  p8 smoke exit 0; identical to K1's baseline counts.  Part 0 committed.
- 2026-10-14T17:21Z check-in rc_v3_timing: RUNNING complete 1/10, unknowns 0, active 6, pending 3, owner alive True, C 36.4 GB / D 604.3 GB, flags none
- 2026-10-14T17:14-17:32Z **Timing check, V3 as first registered** (`rc_v3_timing`, 10 jobs, 6 workers x 4 TLS
  threads): CLOSED 10/10.  [M] V3/K1 wall ratio median 0.069 (0.029-0.040 on >= 20-sector hosts, i.e. 25-34x
  faster).  [M] But 5 of 8 K1-PASS jobs FAIL: SDE at the true period 2-6 vs K1 31-110.  Cause [M]: bin_lc's
  in-bin-scatter errors (3-9 points per bin) put 49-73% of the chi-square weight in the top 1% of bins (K1 native
  3-7%).  Fresh set built (138 known-planet hosts / 184 planets; 50 EB + 20 blend hosts, eligible counts 366/113
  reproduce K1's), downloaded (`fr_dl` 208/208, 0 unknowns), SIMBAD/VSX bulk done (`fr_nb_bulk`).  M1 plan: 14 R-C
  jobs with siblings (all DEV).  A1 plan: 1,035 rescue A re-runs + 20 determinism (R-A: 3,799 pre-gate candidates).
- 2026-10-14T17:58-22:38Z **Supervision lapse (4 h 41 min idle: last phase fr_nb_bulk closed 17:57:48Z, next launch 22:38:26Z).**  The session cron check-ins (one-shot early check +
  hourly) never fired, and a diagnostic TLS started in an unmanaged, power-throttled shell crawled for ~5 h; it
  was stopped unfinished.  Nothing K2 was running in that window.  Fix: crons deleted; supervision is now a
  background waiter (`k2/work/wait_k2.sh <max_min> <phases>`) that exits on a phase closure or after 60 min, so
  the session is re-invoked at least hourly.
- 2026-10-14T22:38Z **AMENDMENT_K2_20261014_1 registered**: C1 bin errors = propagated sqrt(sum e^2)/n (bin_lc
  in-bin scatter withdrawn); the 10 first-registration receipts stay under `rc_v3` as a record; amended V3 runs
  under `rc_v3a`.  k2 C-input tests 8 passed (new test: propagated errors, top-1% weight share < 5%).
- 2026-10-14T22:40Z Launched `rc_v3a_timing` (10 jobs, 6 x 4) and `fr_nb` (208 per-star Gaia neighbour records,
  4 workers, network).
- 2026-10-14T22:55Z check-in rc_v3a_timing: RUNNING complete 9/10, unknowns 0, active 1, pending 0, owner alive True, C 35.6 GB / D 602.8 GB, flags none
- 2026-10-14T22:55Z check-in fr_nb: CLOSED complete 208/208, unknowns 0, active 0, pending 0, owner alive False, C 35.6 GB / D 602.8 GB, flags none
- 2026-10-14T22:57Z **Amended V3 timing check** (`rc_v3a_timing`): CLOSED 10/10, 0 unknowns.  [M] Decisions match K1
  on 9/10 with the same blind periods and SDE within about +/-15%; the 10th (inj_219004585_2) was a K1 loss to a
  spurious 86.4-d peak and now finds 43.20 d.  [M] Wall ratio median 0.069 (0.029-0.042 on >= 20-sector hosts).
  The diagnosis of amendment 1 holds.  Fresh set finalized: 183 planets / 138 hosts, all with data; G1 cohort
  (SNR >= 20, >= 3 transits) = 64, so the fresh set decides.  Neighbours `fr_nb` 208/208 ok.
- 2026-10-14T22:58Z **K-B pricing** (`k2/results/price_k2.json`, model points x oversampling fitted on the timing
  check, k = 0.36): expected Parts 1-4 = 45 queue-hours (Part 1 V3 rest 2.4; Part 2 4.3; Part 3 1.2; Part 4 seen
  8.0; Part 4 fresh 29.2, of which the frozen P12 arm's Stage C 12.6); worst case with V2+V4+V1 also run 66 qh.
  Below 120: no pause.  Launched `rc_v3a_rest` (109 jobs, 6 x 4).
- 2026-10-14T23:05Z Fresh search planned (`fr_search`: 208 K1-arm survey_k1 8,100-s jobs + 138 P12-arm jobs), held
  until the timing-sensitive `rc_v3a_rest` closes.  [M] Exposure ledger: 13 of 208 download rows were lost to
  concurrent appends from 4 workers (the K1 "repeated header rows" race); backfilled from the download receipts
  (marked).  All 208 fresh hosts checked against the survey list + reserve: 0 overlap.  Gotcha: do not edit
  `k2_common.py` (or any pinned K2/K1 source) while a K2 phase runs; the controller re-hashes it every loop and
  fails the phase (SOURCE_CHANGED).
- 2026-10-14T23:58Z check-in rc_v3a_rest: RUNNING complete 28/109, unknowns 0, active 6, pending 75, owner alive True, C 35.6 GB / D 602.4 GB, flags none
- 2026-10-14T23:59Z check-in rc_v3a_rest: RUNNING 28/109 complete, 0 unknowns, 6 active, C 35.6 GB / D 602.4 GB.
  [M] So far (38 of 119 R-C jobs incl. timing): K1->V3a decisions PASS->PASS 27, FAIL->FAIL 9, FAIL->PASS 2, PASS->FAIL 0;
  both flips are K1 strongest peaks at 86-107 d replaced by the survey period (26.45 d, 43.20 d).
- 2026-10-15T00:37Z `rc_v3a_rest` CLOSED 109/109, 0 unknowns.  **C1 [M/A]: V3 adopted** (a) +2.1 pp (77 vs 75 of 95;
  boot [-2.1, +6.3]); (b) 0/5 adversarial flips; (c) 30.2x on >= 20-sector hosts.  Flips: 3 PASS->FAIL (1:2 alias
  path: < 3 usable TLS per-transit depths on 30-min bins), 3 FAIL->PASS (K1 spurious 51-107 d peaks).  DEV planets
  30/37 both; injections 45 -> 47 of 58.  Survey re-price (C units only): C 809 -> 34 qh, total 1,376 -> 601 qh
  (~25 days).  `k2/results/STAGE_C_K2.md`.  RULES_K2 9.1 appended, re-registered.  Part 1 committed.
- 2026-10-15T00:41Z Part 2 launched: `ra_a1_A` (1,055 Stage A jobs: 1,035 A1 rescues + 20 determinism; live scope A1a, both scopes recorded; 16 workers, 1,800 s).
- 2026-10-15T00:53Z check-in ra_a1_A: RUNNING complete 193/1055, unknowns 0, active 14, pending 848, owner alive True, C 35.3 GB / D 601.3 GB, flags none
- 2026-10-15T00:54Z early check ra_a1_A: RUNNING 193/1,055, 0 unknowns, 16 active, C 35.3 GB / D 601.3 GB; so far 192 FAIL / 1 PASS (1 receipt with an A1-rescued ephemeris).
- 2026-10-15T01:54Z check-in ra_a1_A: RUNNING complete 670/1055, unknowns 1, active 14, pending 370, owner alive True, C 35.3 GB / D 599.7 GB, flags ['UNKNOWNS_ROSE:0->1']
- 2026-10-15T01:54Z check-in ra_a1_A: RUNNING 670/1,055, 1 unknown (TIMEOUT at 1,800 s, inj_306472525_2_k1_p01; retry pass at close), C 35.3 GB / D 599.7 GB.  [M] so far 3 PASS / 669 FAIL.
- 2026-10-15T02:55Z check-in ra_a1_A: RUNNING complete 1053/1055, unknowns 1, active 1, pending 0, owner alive True, C 35.3 GB / D 598.5 GB, flags none
- 2026-10-15T02:56Z `ra_a1_A` CLOSED 1,053/1,055 complete, 2 TIMEOUT (CVZ hosts at 1,800 s: inj_306472525_2_k1_p01,
  dev_k1_293823982_p01) -> `ra_a1_A_retry` launched (4x deadline, 7,200 s).  [M] 24 candidates pass A under A1a or
  A1b (offline re-derivation); `ra_a1_S` launched on them.  [M/I] Diagnostic of the depth-failing ephemerides: the
  inconsistency is mostly within one product family (single-family ephemerides still fail), i.e. sector-to-sector
  scatter, not a TESS-SPOC/QLP offset.
- 2026-10-15T02:59Z ra_a1_S 24/24, ra_a1_B 14/14 (0 unknowns).  Launched `fr_search` (346 jobs: 208 survey_k1 8,100 s + 138 frozen P12; 24 workers, Windows-default throttling as calibrated); the 2-job A retry overlaps it (2 cores).
- 2026-10-15T04:05Z check-in fr_search: RUNNING complete 252/346, unknowns 6, active 24, pending 64, owner alive True, C 35.1 GB / D 597.9 GB, flags ['UNKNOWNS_ROSE:0->6']
- 2026-10-15T04:05Z check-in ra_a1_A_retry: CLOSED complete 2/2, unknowns 0, active 0, pending 0, owner alive False, C 35.1 GB / D 597.9 GB, flags none
- 2026-10-15T04:05Z check-in: `ra_a1_A_retry` CLOSED 2/2 (0 unknowns); `fr_search` RUNNING 252/346, 6 unknowns = P12-arm
  hosts with no sector >= 56 (deterministic `no_data`; NO_DATA_IN_ARM, counted as P12 non-recoveries as in K1).
- 2026-10-15T04:10Z **A1 [M/A]: not adopted** (A1a +0.2 pp, A1b +2.0 pp; bar +3 pp; determinism 1,055/1,055).  Within-
  family (sector-to-sector) depth scatter, not a product-family offset.  `k2/results/STAGE_A_K2.md`; RULES 9.2.
- 2026-10-15T04:29Z `fr_search` CLOSED: K1 arm 208/208 complete (partition-limited 1/208); P12 arm 128 ok + 10
  deterministic no-result (9 no product in sectors >= 56; TIC 396740648's only s>=56 product (QLP s73) leaves the frozen
  P12 preparation empty: "need at least one array to concatenate") -> NO_DATA_IN_ARM, P12 non-recoveries as in K1 (no
  retry: deterministic, 2.9% of the phase).  Collected: fr_k1 2,703 accepted / 850 pre-gate; fr_p12 1,089 / 279.
- 2026-10-15T04:31Z Launched `m1_v3_C` (14 M1 jobs, siblings from K1 S receipts since A1 is not adopted; 6 x 4),
  `fr_k1_A` (850, K1 Stage A, 12 workers) and `fr_p12_A` (279, frozen P12, 4 workers).  Timing no longer gates a
  rule, so these overlap.
- 2026-10-15T04:46Z `m1_v3_C` CLOSED 14/14: M1 vs C1 FAIL->PASS 2 (dev_k1_144401492_p03 6.293 d, dev_k1_63283780_p05 2.453 d), PASS->FAIL 1 (dev_k1_229650439_p06, 9.428 d, SDE 3.6 after masking).  `m1_v3_D` launched on the 2 new passes.
- 2026-10-15T04:55Z M1 preliminary [M]: DEV planets at the C endpoint 30 -> 31 (gained TOI-1803 b, Kepler-210 b; lost TOI-1438 c);
  multi-planet DEV hosts 4 -> 5; injections 47 -> 47; no M1 job on a DEV adversarial host.  TOI-1438 c: only 7 of its 660
  in-transit points masked, transit SNR unchanged (21.7 -> 21.8), but TLS installed SDE 55.9 -> 3.6 (robust SDE 63.3,
  concentration 0.25 < 0.5 fallback trigger): the masked series distorts the spectrum normalization; frozen C rule reads 3.6.
- 2026-10-15T05:00Z `m1_v3_D` refused both jobs (Stage C record stamp p10.0 vs D's p10.0-partial: plan_d forced s_mode bound_alias; the DEV case roots ran K1's calibration s_mode bound).  plan_d now uses the C runtime's s_mode (K1 plan_d's rule); refused receipts archived to D:/tesshunter_k2/superseded/m1_v3_D_stamp_mismatch; re-run as `m1_v3_D2`.
- 2026-10-15T05:02Z `m1_v3_D2` CLOSED 2/2: Kepler-210 b SUBMIT (tier 2, catalogue redacted); TOI-1803 b KILL (K2; its
  K1 S gate under `bound` is not a pass).  **M1 [M/A]: adopted** (DEV planets 30 -> 31, multi-planet hosts 4 -> 5, no
  adversarial gain).  `k2/results/STAGE_M1_K2.md`; RULES 9.3.
- 2026-10-15T05:06Z **FREEZE** `k2/protocol/config.json` (sha d47da619...) + `k2/manifests/freeze_k2.json` (73 sources):
  K1 frozen config + C1 = V3 (amendment 1) + M1; A1 not adopted.
- 2026-10-15T05:07Z Part 4 seen set: no A re-run (A1 not adopted: `seen_a1_A` 0 jobs).  Launched `seen_c_C` (K1's 102
  HELD-OUT B-pass paths, frozen V3 + M1, 28 with siblings; 4 workers x 4 threads beside fresh A).  Fresh A at 298/850
  (K1 arm) and 96/279 (P12 arm), 0 unknowns.
- 2026-10-15T06:08Z check-in fr_k1_A: RUNNING complete 557/850, unknowns 1, active 11, pending 281, owner alive True, C 34.5 GB / D 594.7 GB, flags ['UNKNOWNS_ROSE:0->1']
- 2026-10-15T06:08Z check-in fr_p12_A: RUNNING complete 272/279, unknowns 0, active 4, pending 3, owner alive True, C 34.5 GB / D 594.7 GB, flags none
- 2026-10-15T06:08Z check-in seen_c_C: RUNNING complete 25/102, unknowns 4, active 4, pending 69, owner alive True, C 34.5 GB / D 594.7 GB, flags ['UNKNOWNS_ROSE:0->4']
- 2026-10-15T06:09Z check-in: fr_k1_A 557/850 (1 TIMEOUT, CVZ host fr_k1_234211934_p01 -> retry at close); fr_p12_A 272/279; seen_c_C 25/102, 4 unknowns = K1's deterministic Stage C edge case on adversarial blend TIC 251857119 p02-p05 ('NoneType / float' after TLS), reproduced under V3; reported as unknown as in K1.
- 2026-10-15T06:35Z fr_p12_A 279/279, fr_p12_S 123/123, fr_p12_B 51/51 (0 unknowns).  Launched `fr_p12_C` (51 frozen-P12 Stage C jobs, 8 workers x 4 threads).
- 2026-10-15T07:35Z check-in fr_k1_A: RUNNING complete 803/850, unknowns 2, active 12, pending 33, owner alive True, C 33.7 GB / D 593.9 GB, flags ['UNKNOWNS_ROSE:1->2']
- 2026-10-15T07:36Z check-in seen_c_C: RUNNING complete 37/102, unknowns 4, active 4, pending 57, owner alive True, C 33.7 GB / D 593.9 GB, flags none
- 2026-10-15T07:36Z check-in fr_p12_C: RUNNING complete 24/51, unknowns 0, active 8, pending 19, owner alive True, C 33.7 GB / D 593.9 GB, flags none
- 2026-10-15T07:36Z check-in: fr_k1_A 803/850 (2 TIMEOUT -> retry at close), seen_c_C 37/102 (4 unknowns = TIC 251857119 edge case), fr_p12_C 24/51 (0 unknowns); C 35 GB / D ~597 GB.
- 2026-10-15T07:48Z fr_k1_A CLOSED 848/850 (2 TIMEOUT on CVZ hosts) -> fr_k1_A_retry (7,200 s); fr_k1_S launched on the A passers (8 workers).  Fresh K1-arm C waits for the retry (M1 sibling selection needs every S result).
- 2026-10-15T08:51Z check-in: fr_k1_S 178/288 (0 unknowns); fr_k1_B launched on the 86 S passers so far (a second B batch for the rest after S closes); fr_k1_A_retry 1/2; seen_c_C 47/102 (4 known unknowns); fr_p12_C 36/51 (0 unknowns).  Machine oversubscribed (all phases now timing-free).
- 2026-10-15T09:35Z fr_k1_S 288/288, fr_k1_B 86/86 + fr_k1_B2 46/46 (0 unknowns; B batch 2 = eligible minus completed receipts, filtered in a one-off step, planner unchanged).  Launched `fr_k1_C1` (132 B-pass paths, frozen V3 + M1, 41 with siblings; 6 x 4).  No candidate on the 2 A-retry hosts is at C; a retried candidate that passes A gets its own S/B/C pass.
- 2026-10-15T09:52Z fr_k1_A_retry CLOSED 2/2: fr_k1_234211934_p01 PASS (2,667 s), fr_k1_377662721_p03 FAIL (7,020 s).  The new A passer's S (`fr_k1_Sx`): bound_alias FAIL, so no B/C.  Fresh K1 arm complete through B (0 unknowns).  Helper k2/work/plan_rest.py writes not-yet-run jobs of a stage (frozen planner untouched).
- 2026-10-15T10:40Z fr_p12_C CLOSED 51/51 (0 unknowns).  seen_c_C 81/102, 5th unknown = ho_k1_408068720_p01 (P 0.580 d; K1 PASS at SDE 128): V3 input 2,970 points (s3 1800 s + s97 binned), TLS 1.32 raises in its final T0 fit (transit.reference_transit: numpy.min of an empty in-transit sample, 'zero-size array').  Reproduced on a narrow 0.57-0.59 d grid.  TLS library edge case triggered by sparse 30-min input with ~1-h transits; recorded as unknown (not a FAIL); candidate for the bounded repair only if it decides a gate.
- 2026-10-15T11:10Z seen_c_C CLOSED 97/102 + 5 deterministic unknowns (4.9%; 4 x TIC 251857119 K1 edge case, 1 x TLS T0-fit edge case); no retry (the worker refuses an existing receipt; the errors reproduce).  [M] K1 -> K2 decisions on the same 102 paths: PASS->PASS 46, FAIL->FAIL 41, FAIL->PASS 8, PASS->FAIL 2, PASS->ERROR 1, ERROR->ERROR 4.  Launched `seen_c_D` (54 C passes, catalogue redacted, 6 workers).
- 2026-10-15T12:02Z check-in seen_c_D: RUNNING complete 16/54, unknowns 0, active 6, pending 32, owner alive True, C 33.3 GB / D 580.9 GB, flags none
- 2026-10-15T12:02Z check-in fr_k1_C1: CLOSED complete 132/132, unknowns 0, active 0, pending 0, owner alive False, C 33.3 GB / D 580.9 GB, flags none
- 2026-10-15T12:03Z fr_k1_C1 CLOSED 132/132 (0 unknowns).  Launched `fr_k1_D` (fresh C passes, catalogue redacted, 6 workers) beside seen_c_D (16/54).
- 2026-10-15T12:06Z check-in: seen_c_D 16/54, fr_k1_D 0/67 (started 12:03), 0 unknowns; Stage D is TESScut-bound (~1 min per sector cutout; 20-40 min per multi-sector job, low CPU).  K2 through-C yield curve computed (x50 13.9, w 2.35, cmax 0.79; K1 14.4 / 2.42 / 0.79).  Catalogue snapshot 20261015 running (K2 root).
- 2026-10-15T12:15Z Part 5 (gate-independent pieces): catalogue snapshot 20261015 (K2 root; first try hit a transient
  IncompleteRead on the TESS EB catalogue, retried; vs 10/14 only the TOI table changed).  List refresh: 0 dropped,
  0 added, same 10,000 stars and order (k2/survey/targets_k2.csv), 48 SPOC-TCE FLAG, exposure-ledger overlap 0 (K1 +
  K2 ledgers).  Yield with the K2 curve: K 7.33 [4.82-8.82], eM 2.04 [1.23-2.67] TOI-calibrated / 7.02 [4.20-9.26]
  published (K1: 6.99 [4.52-8.57], 1.89, 6.50).
- 2026-10-15T12:16Z Survey re-price (part5_k2 price): 601 queue-hours (~25 days; C 34 qh from R-C V3 receipts) vs K1 1,376; sensitivity with every V3 receipt incl. the oversubscribed HELD-OUT/fresh C runs: 628 qh (C 61).
- 2026-10-15T12:18Z Stage D slow (seen_c_D 18/54, fr_k1_D 2/67 at ~12:23Z): every job re-downloads its TESScut cutouts (~1 min per sector) into the K2 cache.  lightkurve reuses a cached cutout matching sector/coordinates/size (search.py _fetch_tesscut_path), so K1's 19-GB cutout cache (same HELD-OUT hosts, identical MAST products) is copied into D:/tesshunter_k2/lightkurve_funnel/tesscut without overwriting; no effect on results.
- 2026-10-15T13:03Z check-in seen_c_D: RUNNING complete 22/54, unknowns 0, active 6, pending 26, owner alive True, C 29.3 GB / D 560.0 GB, flags none
- 2026-10-15T13:03Z check-in fr_k1_D: RUNNING complete 17/67, unknowns 0, active 6, pending 44, owner alive True, C 29.3 GB / D 560.0 GB, flags none
- 2026-10-15T13:03Z check-in: seen_c_D 22/54, fr_k1_D 17/67, 0 unknowns; D on CVZ hosts is TESScut-bound (~40 cutouts per job; some may exceed 5,400 s and retry fast from cache).
- 2026-10-15T14:06Z check-in seen_c_D: RUNNING complete 36/54, unknowns 3, active 2, pending 13, owner alive True, C 24.7 GB / D 548.1 GB, flags ['DISK_WITHIN_3GB_OF_FLOOR', 'UNKNOWNS_ROSE:0->3', 'STOP:STOP-D storage floor']
- 2026-10-15T14:06Z check-in fr_k1_D: RUNNING complete 38/67, unknowns 0, active 1, pending 28, owner alive True, C 24.7 GB / D 548.1 GB, flags ['DISK_WITHIN_3GB_OF_FLOOR', 'STOP:STOP-D storage floor']
- 2026-10-15T14:07Z **K-D fired: C: 24.7 GB < 25 GB.**  Both D controllers stopped launching (STOP-D storage floor):
  seen_c_D 36/54 complete (3 unknowns), 13 pending; fr_k1_D 38/67, 28 pending; 3 jobs still running.  Cause [M]:
  Stage D's FPP step (src/tesshunter/fpp.py `_sectors_with_cutouts`) downloads 22x22 TESScut cutouts with no
  download_dir, so lightkurve writes them to its HOME cache C:\Users\seanj\.cache\lightkurve\tesscut; this lightkurve
  ignores the LIGHTKURVE_CACHE variable K1/K2 set (only XDG_CACHE_HOME or a cache_dir config redirect it).  K2 wrote
  7.7 GB there (78 files) since 2026-10-14 16:58Z; the other 55 GB of that cache predate K2 (since 2026-09-02).
  [I] K1's "C: drifted down outside K1" was most likely the same cache.  Paused for the user (K-D).
- 2026-10-15T15:10Z **User decision (chat): relocate K2's cache.**  Both D phases closed STOPPED (seen_c_D 38/54 incl. 3
  unknowns; fr_k1_D 38/67 incl. 1 unknown).  Moved the 79 files (8.01 GB) K2 wrote to C:\Users\seanj\.cache\lightkurve\
  tesscut since 2026-10-14 16:58Z to D:\tesshunter_k2\xdg_cache\lightkurve\tesscut (moved, not deleted; receipt
  k2/manifests/relocation_lightkurve_cache.json); C: 24.7 -> 29.9 GB.  Operational change (no effect on results):
  k2_common.worker_env sets XDG_CACHE_HOME = D:\tesshunter_k2\xdg_cache (lightkurve.config.get_cache_dir verified ->
  D:); k2_common.py's hash now differs from freeze_k2.json (recorded here and in READY_K2).  Resumed seen_c_D and
  fr_k1_D (same job lists; completed receipts reused).  The 55 GB of pre-K2 files in that cache are untouched.
- 2026-10-15T15:44Z check-in seen_c_D: CLOSED complete 51/54, unknowns 3, active 0, pending 0, owner alive False, C 31.7 GB / D 532.7 GB, flags none
- 2026-10-15T15:44Z check-in fr_k1_D: RUNNING complete 49/67, unknowns 1, active 6, pending 11, owner alive True, C 31.7 GB / D 532.7 GB, flags ['UNKNOWNS_ROSE:0->1']
- 2026-10-15T15:46Z seen_c_D CLOSED 51/54; 3 TIMEOUT at 5,400 s (ho_k1_294329732_p01, 300812741_p07, 321669174_p01; many-sector hosts) -> seen_c_D_retry (4x, 21,600 s).  fr_k1_D 49/67 (1 TIMEOUT so far).  C: 30 GB stable; xdg cache on D: 11 GB.
- 2026-10-15T16:17Z seen_c_D_retry CLOSED 3/3 (seen D 54/54).  **Prediction lock `seen`** (2,156 files, bundle 48d6d5cf...).
- 2026-10-15T16:25Z **Seen set (design-informed) [M]:** G1 31/55 = 56.4% (Wilson 43-69%; host boot 44-70%) FAIL (K1 29/55);
  G2 +12.7 pp (K2 31 vs P12 24; boot -2.0..+26.4) PASS; G3 1/53 SUBMIT (1.9%; SUBMIT+HOLD 2) PASS.  All 141: C 40 (K1 39).
  G1 losses 24: search 8, A 5 (depth consistency), S 2, C 9 (K1 11; TOI-1260 d/.03 recovered by M1).  D on recovered
  planets: SUBMIT 23, HOLD 15, KILL 2.  New G3 SUBMIT = V1 blend TIC 1950736 (TOI-4610.01): same C period/fit as K1 (P
  3.112943 vs 3.112946; t0 within 1 min) but Stage D's TESScut sector set differed (K1: s19 missing, s44 present -> K7a
  in s43+s44 -> KILL; K2: s44 cutout missing ('none', not measurable) -> K7a in s43 only -> SUBMIT).  Transient MAST
  download gap in D's pixel step, not a C1/M1 effect; not re-run after the lock.
- 2026-10-15T17:13Z fr_k1_D CLOSED 64/67; 3 TIMEOUT at 5,400 s -> fr_k1_D_retry (4x).  C: 30 GB.
- 2026-10-15T17:18Z fr_k1_D_retry: 2/3 COMPLETE; the 3rd (fr_k1_231949697_p04) already had a COMPLETE receipt written 13:16:57Z (wall 1,274 s) whose process then hung until the 5,400-s kill (attempt result_sha256 = that receipt); kept per the P12 rule, retry refused by FileExistsError as designed.  Fresh D 67/67.
- 2026-10-15T17:17Z **Prediction lock `fresh`** (2,668 files, e13f6cca...).
- 2026-10-15T17:30Z **Fresh set (deciding) [M]:** G1 38/64 = 59.4% (Wilson 47-71%) **FAIL by one planet**; G2 +10.9 pp
  (K2 38 vs P12 31) PASS; G3 0/70 SUBMIT, 1 HOLD PASS.  Losses 26: search 1, A 12 (all depth consistency), S 5 (SAP
  secondary dips), C 8 (5 spurious 33-101 d peaks, 1 sibling whose own candidate failed A, 1 inconsistent 1:2 alias,
  1 V3 alias-test interaction: TOI-1739 b, one-bin TLS duration -> zero per-transit errors).  Bounded repair: no
  clear implementation defect -> nothing to fix.  **FINAL STATE NOT_READY.**  VALIDATION_K2.md; RULES 9.4.
- 2026-10-15T17:50Z Part 5: VALIDATION_K2.md, LAUNCH_PLAN_K2.md (status NOT_READY), READY_K2.md (final state NOT_READY), k2/manifests/launch_package_k2.json.  k2/tests 15 passed.  Shutdown: CronList empty, no owner files, no python processes, no background waiter.  Part 4-5 committed.  RESUME CLOSED.
