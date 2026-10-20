**AUTHORIZATION (user, 2026-10-15):** launch the frozen K2 package despite K2's NOT_READY (path (b) of `k2/READY_K2.md` section 10: G1 38/64 = 59.4%, one planet short of 60%; G2 +10.9 pp; G3 0/70). Covers running the survey exactly as frozen; no method or threshold change, no upload, submission or contact, no push.

# RESUME_S1 - prompt S1 (K-dwarf survey on the frozen K2 package)

Prompt: `C:\Users\seanj\Downloads\PROMPT_S1_SURVEY_LAUNCH.md`.  Frozen method: `k2/protocol/config.json` (sha d47da619...),
`k2/manifests/freeze_k2.json`, `k2/manifests/launch_package_k2.json`.  Data root `D:\tesshunter_s1`.
Evidence tags: [M] measured, [R] earlier record, [A] adopted, [I] interpretation.  Nothing here is a detection: SUBMIT /
HOLD are candidates for the user's review.

**Resume here:** read the last dated entry below, then `s1/manifests/` (owner files = open phases) and
`s1/logs/checkins.jsonl`.  Recovery recipes: prompt section 4.3.

## Dated log
- 2026-10-15 Start: branch `s1/survey` created from `k2/prepare` at `74b7860c1`.  `src/` identical to `74b7860c1`
  (no diff).  Working tree carries the 6 pre-K1 deleted-unstaged LibreOffice lock files under `p12/results/funnel/`
  and untracked P10/P12 files (never staged by S1).  [M] Free space C: 37.2 GB, D: 491.6 GB.  Windows Update paused
  until 2026-10-27T19:50Z; sleep timeout never (AC and DC); desktop-app keep-awake held for the session.
- 2026-10-15T20:06Z **Catalogue snapshot `20261015`** (`s1/work/snapshot_s1.py` = K2's snapshot_k2 logic; D:\tesshunter_s1\catalogs\snap_20261015,
  s1/manifests/catalog_snapshot_20261015.json): every source fetched fresh at 20:05-20:06Z (TOI, CTOI 5,138 incl. the 1,173
  RAVEN rows, NASA ps / pscomppars, TESS EB, SPOC TCE 134 runs, coordinates complete), TTT tables.  Operational: the 134
  published SPOC TCE raw files of K2's 2026-10-15 snapshot were copied in first (immutable files; only missing runs fetched).
- 2026-10-15T20:08Z **List refresh** (`plan_s1.py refresh 20261015` = part5_k2.refresh logic on k2/survey): 0 dropped, 0 added;
  10,000 stars (7,000 K + 3,000 eM) in the frozen order; status CLEAN 9,952 / FLAG 48 (all SPOC TCE); preparation-ledger
  overlap 0.  `s1/survey/targets_s1.csv`, `reserve_s1.csv`, `tce_sidecar_s1.csv` (175 TCE rows, 48 stars) are byte-identical
  to the K2 files (sha 7c54153f..., 1cacc7f5..., 8fec7424...).  Operational fixes in the refresh code (no effect here, list
  unchanged): a refilled reserve star takes its own slice (the reserve has no `slice` column), and an unchanged list is
  copied byte for byte.
- 2026-10-15T20:10Z **Tooling** (s1/protocol, s1/work; derived mechanically by `s1/work/make_tooling_s1.py` where marked):
  * `s1_common.py`: sets K2_DATA = K1_DATA = D:\tesshunter_s1 before importing k2_common, so the K2 controller logic,
    `k2_common.worker_env` (XDG_CACHE_HOME = D:\tesshunter_s1\xdg_cache) and every K1/K2 worker write under the S1 root;
    batches as literal rank ranges per slice (refills join the slice's last batch); the exposure ledger
    `s1/manifests/exposure_ledger_s1.csv` is appended under an exclusive lock directory [M: 8 concurrent writers x 50 rows ->
    400 rows, 1 header].
  * `controller_s1.py`, `launch_s1.ps1`, `s1/work/wait_s1.sh` (derived): S1 owners/STOP files/logs, script lookup
    s1 -> k2 -> k1 protocol, `s1_common.py` pinned, `search_s1.py` treated as a search job (Windows-default scheduling).
  * `checkin_s1.py`: checkin_k2 with S1 roots plus the section-4.2 health line (deltas since the last wake, worker-CPU gain,
    C: trend in GB/h, NO_PROGRESS and C_LOW_OR_FALLING flags).
  * Wrappers `download_s1.py`, `search_s1.py` run download_k1 / search_worker_k1 unchanged.  **Operational change:** the K1
    workers refuse every star of the frozen survey list (STOP-E, a preparation-time blindness guard reading
    k1/survey/targets_k1.csv); the wrappers lift that refusal (S1 is that survey) and apply the converse (refuse any star not
    on s1/survey/targets_s1.csv).  search_s1 imports search_worker_k1 then download_k1, the order the frozen worker's main()
    uses, so the worker process environment is identical.  download_s1 also routes the ledger row to the locked S1 ledger.
  * `plan_s1.py`: download / search / collect / funnel A-S-B-C / neighbours / D, from plan_k2 + plan_k1 logic; every stage
    plans only jobs without a result (the smoke subset and the rest of batch 1 share run `s1_b1`, label `s1_b1`); C refuses to
    plan while an A pass lacks an S receipt (M1 siblings need every S result); C runtimes set k2_copy_from = their own A/S/B
    case root (a no-op copy, as in the fresh-set fr_k1 C jobs); D plans with the C runtime's S mode, the launch snapshot
    20261015 and redact_catalogue = false.  Download retries are planned as attempt 2 (fresh per-attempt FITS cache) rather
    than controller -RetryOf (which would reuse attempt 1's cache folder).
  * Stars enter the search only with a complete download (index n_failed = 0 and >= 1 usable product); a download that stays
    incomplete after its retry is an unknown, not a partial search.
- 2026-10-15T20:10Z **Checks [M]:** k1/tests 60 passed, k2/tests 15 passed (s1/logs/tests_prelaunch); `git diff 74b7860c1 -- src/`
  empty.
- 2026-10-15T20:11Z **Smoke batch** = the first 20 stars of batch 1 in rank order (eM ranks 1-10 interleaved with K ranks
  1-10; they count toward batch 1).  Launched `s1_b1_smoke_dl` (20 jobs, 4 workers, 900 s): RUNNING, 4 active, owner present.
- 2026-10-15T20:16Z check-in s1_b1_smoke_dl: CLOSED complete 20/20 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 39.6 GB (n/a) / D 526.8 GB, flags none
- 2026-10-15T20:29Z check-in s1_b1_smoke_search: RUNNING complete 2/20 (+n/a), unknowns 0 (+n/a), active 18, owner alive True, worker CPU +10946 s, C 39.6 GB (n/a) / D 526.7 GB, flags none
- 2026-10-15T20:16Z `s1_b1_smoke_dl` CLOSED 20/20, 0 unknowns, 4.9 min (4 workers; 20-76 s per star; realised products = list n_usable).
  Ledger 20 rows.  Launched `s1_b1_smoke_search` (20 jobs, 24 workers, 13,860 s, Windows-default scheduling).
  Operational lesson: piping the launcher's output (`launch_s1.ps1 ... | grep`) hangs the Bash call, because the detached
  controller inherits the pipe handle; the stuck grep was stopped (the controller writes only to its log).  Never pipe the
  launcher.
- 2026-10-15T20:29Z early check `s1_b1_smoke_search`: 2/20 COMPLETE (eM 6-7 sectors, 409-506 s, 10-12 accepted, 0-3 pre-gate,
  0 partitions budget-limited), 18 active, worker cpu/wall 0.79, no errors; C 39.6 GB / D 526.7 GB.  Waiter armed (60 min).
- 2026-10-15T21:27Z **Pre-launch item 1 resolved (user):** Windows Update pause extended; [M] registry now
  PauseUpdatesExpiryTime 2026-11-19T21:25Z (~35 days; survey ~25 days); sleep and hibernate idle timeouts never (AC and DC);
  desktop-app keep-awake held.  Item 2 (disk) awaits the smoke-batch measurement.
- 2026-10-15T21:29Z check-in s1_b1_smoke_search: CLOSED complete 20/20 (+18), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 39.3 GB (-0.28 GB/h) / D 526.7 GB, flags none
- 2026-10-15T21:29Z `s1_b1_smoke_search` CLOSED 20/20, 0 unknowns, 1.20 h (walls 409-4,323 s).  Collect: 386 accepted, 73 pre-gate.
  **[M] Partition-limited 10/20 = 50%** (all 10 have 37-44 sectors; the exhausted partition is the smallest chunk, e.g. chunk0
  13k cadences / 222 s of the 8,100 s split).  [M] In the K1/K2 survey_k1 8,100-s records (1,756 searches) the fraction is 0%
  below 13 sectors, 3% at 13-19, 40% at 20-29, 59% at 30-36, 47% at >= 37 (S1 smoke >= 37: 10/12); the 9-14% calibration came
  from sets with median 5-9 sectors.  [I] Projected by sector bin from the K1/K2 rates: batch 1 22.7%, 2 14.6%, **3 27.1%**,
  4 21.6%, 5 18.8% (batch 1 ~33% if the smoke's >= 37-sector rate holds).  S-P (25%) is therefore likely to fire on list
  composition; raised with the user at the pre-launch pause (no method change).
- 2026-10-15T21:31Z Launched `s1_b1_smoke_A` (73 jobs, 28 workers opted out of throttling, 1,800 s): RUNNING 28 active.
- 2026-10-15T21:40Z check-in s1_b1_smoke_A: RUNNING complete 38/73 (+n/a), unknowns 1 (+n/a), active 28, owner alive True, worker CPU +10384 s, C 39.3 GB (n/a) / D 526.4 GB, flags ['UNKNOWNS_ROSE:0->1']
- 2026-10-15T21:58Z check-in s1_b1_smoke_A: CLOSED complete 72/73 (+34), unknowns 1 (+0), active 0, owner alive False, worker CPU +0 s, C 39.1 GB (-0.86 GB/h) / D 526.3 GB, flags none
- 2026-10-15T21:58Z `s1_b1_smoke_A` CLOSED 73: 72 FAIL, 0 PASS, 1 deterministic ERROR (s1_381949245_p01: duration 0.35 d > P/2 of
  P 0.632 d, `max() iterable argument is empty`: K1 gotcha 8; reproduces, reported unknown, no retry loop); max wall 1,197 s,
  0 timeouts.  **No smoke candidate reached S**, so S / neighbours / B / C / D were not exercised.  [R] K1 FA hosts: 22 A passes
  on 15 of 250 hosts (6%), all S PASS under bound_alias; P(0 of 20) ~ 17%.
- 2026-10-15T21:59Z Smoke disk [M] (s1/results/disk_smoke_20.json; 586 sectors, mean 29.3 per star vs list 20.4): FITS cache
  0.58 MB/sector, store 0.12, stitched 0.07, search 0.10 MB/sector (2.9 MB/star); funnel case roots 5.6 MB per A candidate
  (0.69 MB per searched sector; tls npz dominate); 3.65 pre-gate per star.
- 2026-10-15T22:00Z **Smoke extended (operational):** the next 40 stars of batch 1 in rank order (positions 21-60) so that
  S-D run on S1 paths before batch 1 (P(>= 1 A pass) ~ 96%); they count toward batch 1.  Launched `s1_b1_smoke2_dl` (40 jobs).
- 2026-10-15T22:11Z check-in s1_b1_smoke2_dl: CLOSED complete 40/40 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 39.1 GB (n/a) / D 525.5 GB, flags none
- 2026-10-15T22:11Z `s1_b1_smoke2_dl` CLOSED 40/40, 0 unknowns, 0.18 h.  Launched `s1_b1_smoke2_search` (40 jobs, 24 workers,
  13,860 s, Windows-default).  Pre-launch pause questions put to the user (chat): disk options A (delete FITS cache of ingested
  stars, ~118 GB) / B (delete finished batches' TESScut caches) / C (archive K1/K2 trees) / D (another drive), recommended A+B;
  S-P handling (1) as written (default) or (2) sector-matched expectation + 10 pp.  Batch 1 proper waits for the answer.
- 2026-10-15T22:22Z check-in s1_b1_smoke2_search: RUNNING complete 3/40 (+n/a), unknowns 0 (+n/a), active 24, owner alive True, worker CPU +13425 s, C 39.1 GB (n/a) / D 525.4 GB, flags none
- 2026-10-15T23:12Z check-in s1_b1_smoke2_search: CLOSED complete 40/40 (+37), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 38.8 GB (-0.28 GB/h) / D 525.3 GB, flags none
- 2026-10-15T23:12Z `s1_b1_smoke2_search` CLOSED 40/40, 0 unknowns, 1.01 h; worker cpu/wall 0.99 (first wave 0.79).  [M] Partition-
  limited 0/40 in this wave (0/22 with >= 37 sectors) vs 10/12 in the first wave: the budget is wall-clock, so the fraction
  depends on Windows' throttling state as well as on sectors (K1 gotcha 1: the state shifts by itself).  Smoke total 10/60 =
  16.7%.  Collect: 1,193 accepted, 176 pre-gate (103 new).  Launched `s1_b1_smoke2_A` (103 jobs, 28 workers, 1,800 s).
- 2026-10-15T23:23Z check-in s1_b1_smoke2_A: RUNNING complete 29/103 (+n/a), unknowns 0 (+n/a), active 28, owner alive True, worker CPU +7604 s, C 38.8 GB (n/a) / D 525.0 GB, flags none
- 2026-10-15T23:47Z check-in s1_b1_smoke2_A: CLOSED complete 103/103 (+74), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 38.8 GB (-0.00 GB/h) / D 524.7 GB, flags none
- 2026-10-15T23:48Z check-in s1_b1_smoke2_S: CLOSED complete 3/3 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 38.8 GB (n/a) / D 524.7 GB, flags none
- 2026-10-15T23:47Z `s1_b1_smoke2_A` CLOSED 103/103, 0 unknowns (max wall 1,783 s, no timeout): 3 PASS, all on TIC 272237600
  (p02-p04: 10.34 / 12.93 / 14.22 d; its p01 0.862 d, stitch SNR 101, failed A).  `s1_b1_smoke2_S` 3/3: bound FAIL, bound_alias
  PASS (all 3).  Neighbours (`s1_b1_smoke2_nb_bulk` SIMBAD + VSX 2/2, `s1_b1_smoke2_nb` Gaia 1/1; GAIA id kept as text).
  `s1_b1_smoke2_B` 3/3 PASS (star flags: RUWE 1.42, ipd_frac_multi_peak 64%, astrometric excess noise sig 56.5).
- 2026-10-15T23:51Z Launched `s1_b1_smoke2_C` (3 jobs, V3, bound_alias, A1 none, M1 siblings: p03 masks p02, p04 masks p02+p03;
  8 workers x 4 TLS threads, 14,400 s).
- 2026-10-16T00:01Z check-in s1_b1_smoke2_C: RUNNING complete 0/3 (+n/a), unknowns 0 (+n/a), active 3, owner alive True, worker CPU +8088 s, C 38.8 GB (n/a) / D 524.7 GB, flags none
- 2026-10-16T00:09Z check-in s1_b1_smoke2_C: CLOSED complete 3/3 (+3), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 36.5 GB (-16.33 GB/h) / D 524.7 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-16T00:09Z `s1_b1_smoke2_C` CLOSED 3/3, 0 unknowns, 925-1,104 s (V3, oversampling 2 on the 2,720-d baseline): all FAIL.
  p02 / p03 blind TLS peaks at 0.86175 d (SDE 88.6 / 89.2) = the star's p01 signal (which failed A, so M1 could not mask it);
  p04 peak 0.535 d SDE 7.1.  No smoke candidate reached D.
- 2026-10-16T00:09Z **C: incident (not S1):** C: free 38.8 -> 34.0 GB between 23:51Z and 00:12Z while only S1's 3 C jobs ran
  (they write to D:).  [M] Writers: AppXSvc (Microsoft Store app deployment, ~11 MB/s) and DoSvc (Delivery Optimization); no
  growth in ~/.cache, %TEMP%, repo data/cache or C:\Windows\Temp.  Store app updates are not covered by the Windows Update
  pause.  C: levelled at 34.0 GB (floor 25; check-in flag 27); watched at every wake.
- 2026-10-16T00:10Z **Stage D dry run** (`s1/work/dryrun_d_s1.py s1_272237600_p02 1`; nothing launched): the plan_s1 D runtime
  has exactly stage_d_worker_k1.RUNTIME_FIELDS, catalogue = D:\tesshunter_s1\catalogs\snap_20261015 (stamp k1:snap_20261015),
  redact_catalogue false (real hard stop; this star CLEAN), neighbour record + case root on the S1 root, s_mode bound_alias
  matching the Stage C record's rules_version p10.0-partial.  The D worker itself is K1's, unchanged and exercised in K2.
- 2026-10-16T00:11Z **Smoke result (60 stars, counted in batch 1)** (`s1/results/SMOKE_B1.md`): download 60/60, search 60/60
  (0 unknowns; partition-limited 10/60 = 16.7%), 1,193 accepted, 176 pre-gate, A 3 PASS / 172 FAIL / 1 deterministic unknown,
  S 3 bound_alias PASS, B 3 PASS, C 0 PASS; D not reached.  Receipts written by every stage that ran.  [M] walls: search median
  1,833 s (max 4,323), A max 1,783 s, C 925-1,104 s.  [M] Disk (s1/results/disk_smoke_60.json): FITS 0.568 MB/sector, store
  0.122, stitched 0.073, search 0.104 MB/sector, funnel 5.4 MB per A candidate (~0.54 MB per searched sector).
  [I] Projection on 203,548 list sectors: FITS 116 + store 25 + stitched 15 + search 21 + funnel ~110 = ~287 GB, plus Stage D
  0.35 GB x 150-1,200 D candidates (0.015-0.12 per star) = 52-420 GB -> ~340-710 GB vs ~425 GB usable on D: (524.7 free,
  floor 100).  **PAUSE (item 2) for the user's disk choice; S-P handling question open.**
- 2026-10-16T00:15Z **User decisions (pre-launch pause, chat)** -> `s1/manifests/decision_prelaunch.json`:
  * **Disk: A + B.**  A: delete each star's FITS download cache (D:\tesshunter_s1\lightkurve\tic<id>) once its store is written
    and its batch's search has closed (n_failed = 0 stars only; receipts s1/manifests/prune_fits_*.json).  B: delete a finished
    batch's TESScut caches (lightkurve_funnel\tesscut, xdg_cache\lightkurve\tesscut) after its batch report, only files older
    than the batch's last D closure and only while no D phase is open (receipts prune_tesscut_*.json).  [I] projection
    ~180-255 GB.
  * **S-P: sector-matched + 10 pp** (replaces the absolute 25%): pause when a batch's partition-limited fraction exceeds the
    mean of the K1/K2 bin rates over its searched stars (0-7: 0, 8-12: 0, 13-19: 0.034, 20-29: 0.402, 30-36: 0.586,
    >= 37: 0.473; frozen now, before batch 1) by more than 10 pp.
- 2026-10-16T01:04Z Pruning A on the 60 smoke stars (`s1/work/prune_s1.py fits 1 --first 60`): 60 FITS caches, 1.0 GB freed
  (receipt s1/manifests/prune_fits_b1_*.json).  report_s1 now evaluates S-P as decided (smoke: 16.7% observed vs 31.5%
  sector-matched expectation -> not triggered).
- 2026-10-16T01:05Z **BATCH 1 LAUNCHED.**  `s1_b1_dl`: 1,940 stars (batch 1 minus the 60 smoke stars), 4 workers, 900 s.
- 2026-10-16T01:14Z check-in s1_b1_dl: RUNNING complete 42/1940 (+n/a), unknowns 0 (+n/a), active 4, owner alive True, worker CPU +16 s, C 36.1 GB (n/a) / D 524.9 GB, flags none
- 2026-10-16T01:58Z `s1_b1_dl` 204/1,940 at 52 min (~3.9 stars/min; ETA ~7.4 h), 5 unknowns = MAST search_lightcurve timeouts at
  the 240-s bound (transient; attempt-2 retry after close).  Search consumes ~0.8 stars/min (24 workers, mean wall 1,835 s), so
  the batch-1 search starts now in sequential parts: `s1_b1_search_a` = the 207 stars downloaded so far (24 workers, 13,860 s);
  part b = everything downloaded when part a closes (one search phase at a time).
  [I] ETA (measured walls by sector bin, K1/K2/S1, 24 workers, 92% packing): search b1 45 h, b2 34, b3 54, b4 46, b5 41 =
  ~220 h; plus ~20 h of A/S/B/C between batches -> last search closes ~300 h from now (~2026-10-28); survey end ~330-350 h.
- 2026-10-16T02:07Z check-in s1_b1_dl: RUNNING complete 250/1940 (+208), unknowns 6 (+6), active 4, owner alive True, worker CPU +27 s, C 36.1 GB (-0.00 GB/h) / D 521.1 GB, flags ['UNKNOWNS_ROSE:0->6']
- 2026-10-16T02:07Z check-in s1_b1_search_a: RUNNING complete 3/207 (+n/a), unknowns 0 (+n/a), active 24, owner alive True, worker CPU +13234 s, C 36.1 GB (n/a) / D 521.1 GB, flags none
- 2026-10-16T02:15Z check-in s1_b1_dl: RUNNING complete 286/1940 (+36), unknowns 6 (+0), active 2, owner alive True, worker CPU +30 s, C 34.9 GB (-8.79 GB/h) / D 520.4 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-16T02:15Z check-in s1_b1_search_a: RUNNING complete 8/207 (+5), unknowns 0 (+0), active 24, owner alive True, worker CPU +10505 s, C 34.9 GB (-8.79 GB/h) / D 520.4 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-16T02:20Z **C: watch:** 36.1 GB (02:07Z) -> 34.9 (02:15Z) -> 32.47 (02:18Z), then flat for 90 s.  Not found in: ~/.cache,
  %TEMP%, C:\Windows\Temp, repo data/cache, ~/.astropy (absent), AppData\Roaming / Local\Packages (<0.1 GB recent), SoftwareDistribution
  (0.04 GB); pagefile fixed at 4 GB; SearchIndexer idle; S1 workers write D: only.  Store/update services running (AppXSvc,
  InstallService, UsoSvc, wuauserv; earlier AppXSvc burst at 00:09Z), so [I] likely Store app servicing into protected folders.
  Memory: commit ~61 of 68 GB, 19 GB RAM free (24 searches + downloads + user apps).  Floor 25 GB: tracked at every wake.
- 2026-10-16T03:15Z check-in s1_b1_dl: RUNNING complete 523/1940 (+237), unknowns 6 (+0), active 3, owner alive True, worker CPU +44 s, C 34.6 GB (-0.28 GB/h) / D 516.1 GB, flags none
- 2026-10-16T03:15Z check-in s1_b1_search_a: RUNNING complete 54/207 (+46), unknowns 0 (+0), active 24, owner alive True, worker CPU +26526 s, C 34.6 GB (-0.28 GB/h) / D 516.1 GB, flags none
- 2026-10-16T04:16Z check-in s1_b1_dl: RUNNING complete 779/1940 (+256), unknowns 7 (+1), active 3, owner alive True, worker CPU +14 s, C 34.6 GB (-0.00 GB/h) / D 512.0 GB, flags ['UNKNOWNS_ROSE:6->7']
- 2026-10-16T04:16Z check-in s1_b1_search_a: RUNNING complete 108/207 (+54), unknowns 0 (+0), active 24, owner alive True, worker CPU +20465 s, C 34.6 GB (-0.00 GB/h) / D 512.0 GB, flags none
- 2026-10-16T05:16Z check-in s1_b1_dl: RUNNING complete 1047/1940 (+268), unknowns 7 (+0), active 4, owner alive True, worker CPU +46 s, C 34.0 GB (-0.62 GB/h) / D 508.2 GB, flags none
- 2026-10-16T05:16Z check-in s1_b1_search_a: RUNNING complete 160/207 (+52), unknowns 0 (+0), active 24, owner alive True, worker CPU +30923 s, C 34.0 GB (-0.62 GB/h) / D 508.2 GB, flags none
- 2026-10-16T06:17Z check-in s1_b1_dl: RUNNING complete 1396/1940 (+349), unknowns 7 (+0), active 4, owner alive True, worker CPU +15 s, C 33.7 GB (-0.21 GB/h) / D 504.6 GB, flags none
- 2026-10-16T06:17Z check-in s1_b1_search_a: RUNNING complete 206/207 (+46), unknowns 0 (+0), active 1, owner alive True, worker CPU +2004 s, C 33.7 GB (-0.21 GB/h) / D 504.6 GB, flags none
- 2026-10-16T06:20Z `s1_b1_search_a` at 206/207 (tail: s1_279251357, 43 sectors, 2,033 s elapsed), 0 unknowns; `s1_b1_dl` 1,396/1,940,
  7 unknowns (MAST 240-s timeouts).  Launched `s1_b1_search_b` (1,194 stars downloaded and not searched; 24 workers, 13,860 s):
  for <= ~40 min 25 search processes run (part a's tail + 24); no A/C phase open.  Operational fix: the first part-b plan
  included the job still running in part a (no result yet); plan_s1.plan_search now skips jobs of open search phases
  (`open_phase_jobs`).  The rewritten runtime of that job was byte-identical (deterministic planner); nothing ran twice.
- 2026-10-16T06:22Z `s1_b1_search_a` CLOSED 207/207, 0 unknowns, 4.36 h (its tail finished at 2,071 s, so there was no overlap with part b); the tail job's recorded runtime_sha256 equals the runtime file.
- 2026-10-16T06:28Z check-in s1_b1_dl: RUNNING complete 1462/1940 (+66), unknowns 7 (+0), active 4, owner alive True, worker CPU +22 s, C 33.7 GB (+0.02 GB/h) / D 503.7 GB, flags none
- 2026-10-16T06:28Z check-in s1_b1_search_b: RUNNING complete 6/1194 (+n/a), unknowns 0 (+n/a), active 24, owner alive True, worker CPU +12786 s, C 33.7 GB (n/a) / D 503.7 GB, flags none
- 2026-10-16T07:29Z check-in s1_b1_dl: RUNNING complete 1774/1940 (+312), unknowns 7 (+0), active 4, owner alive True, worker CPU +25 s, C 33.5 GB (-0.23 GB/h) / D 500.8 GB, flags none
- 2026-10-16T07:29Z check-in s1_b1_search_b: RUNNING complete 44/1194 (+38), unknowns 0 (+0), active 24, owner alive True, worker CPU +33148 s, C 33.5 GB (-0.23 GB/h) / D 500.8 GB, flags none
- 2026-10-16T07:56Z check-in s1_b1_dl: CLOSED complete 1933/1940 (+159), unknowns 7 (+0), active 0, owner alive False, worker CPU +0 s, C 33.5 GB (+0.08 GB/h) / D 499.5 GB, flags none
- 2026-10-16T07:56Z check-in s1_b1_search_b: RUNNING complete 69/1194 (+25), unknowns 0 (+0), active 24, owner alive True, worker CPU +20387 s, C 33.5 GB (+0.08 GB/h) / D 499.5 GB, flags none
- 2026-10-16T07:56Z `s1_b1_dl` CLOSED 1,933/1,940 (6.85 h); 7 unknowns: 5 MAST search_lightcurve timeouts at the 240-s bound, 1
  RemoteServiceError, 1 aborted connection on one sector (TIC 271799311, 42/43 products).  Launched `s1_b1_dl_retry` (attempt 2,
  fresh FITS cache, 3,600 s = 4x, 4 workers).  `s1_b1_search_b` 69/1,194, 0 unknowns.
- 2026-10-16T07:59Z check-in s1_b1_dl_retry: CLOSED complete 7/7 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 33.5 GB (n/a) / D 499.4 GB, flags none
- 2026-10-16T07:59Z check-in s1_b1_search_b: RUNNING complete 71/1194 (+2), unknowns 0 (+0), active 24, owner alive True, worker CPU +4274 s, C 33.5 GB (-0.08 GB/h) / D 499.4 GB, flags none
- 2026-10-16T07:59Z `s1_b1_dl_retry` CLOSED 7/7 COMPLETE (attempt 2).  **Batch 1 downloads 2,000/2,000, 0 unknowns.**  Search part c (the ~540 stars downloaded after part b was planned) follows part b.
- 2026-10-16T08:59Z check-in s1_b1_search_b: RUNNING complete 123/1194 (+52), unknowns 0 (+0), active 24, owner alive True, worker CPU +24063 s, C 33.3 GB (-0.23 GB/h) / D 499.1 GB, flags none
- 2026-10-16T10:00Z check-in s1_b1_search_b: RUNNING complete 174/1194 (+51), unknowns 0 (+0), active 24, owner alive True, worker CPU +27745 s, C 33.3 GB (-0.01 GB/h) / D 498.8 GB, flags none
- 2026-10-16T11:00Z check-in s1_b1_search_b: RUNNING complete 228/1194 (+54), unknowns 0 (+0), active 24, owner alive True, worker CPU +25750 s, C 33.3 GB (-0.00 GB/h) / D 498.6 GB, flags none
- 2026-10-16T12:01Z check-in s1_b1_search_b: RUNNING complete 278/1194 (+50), unknowns 0 (+0), active 23, owner alive True, worker CPU +22918 s, C 33.3 GB (-0.02 GB/h) / D 498.3 GB, flags none
- 2026-10-16T13:01Z check-in s1_b1_search_b: RUNNING complete 326/1194 (+48), unknowns 0 (+0), active 24, owner alive True, worker CPU +27316 s, C 32.7 GB (-0.56 GB/h) / D 498.0 GB, flags none
- 2026-10-16T14:02Z check-in s1_b1_search_b: RUNNING complete 390/1194 (+64), unknowns 0 (+0), active 24, owner alive True, worker CPU +22692 s, C 32.6 GB (-0.09 GB/h) / D 497.7 GB, flags none
- 2026-10-16T15:02Z check-in s1_b1_search_b: RUNNING complete 443/1194 (+53), unknowns 0 (+0), active 23, owner alive True, worker CPU +27930 s, C 32.4 GB (-0.24 GB/h) / D 497.5 GB, flags none
- 2026-10-16T16:03Z check-in s1_b1_search_b: RUNNING complete 508/1194 (+65), unknowns 0 (+0), active 24, owner alive True, worker CPU +25973 s, C 32.1 GB (-0.25 GB/h) / D 497.2 GB, flags none
- 2026-10-16T17:03Z check-in s1_b1_search_b: RUNNING complete 572/1194 (+64), unknowns 0 (+0), active 24, owner alive True, worker CPU +26644 s, C 31.9 GB (-0.24 GB/h) / D 496.9 GB, flags none
- 2026-10-16T18:25Z **C: incident 2 (C_LOW_OR_FALLING):** C: 34.6 GB (03:15Z) -> 31.9 (17:03Z, ~-0.25 GB/h) -> 29.72 (18:04Z) ->
  29.09 (18:15Z) -> 28.41 (18:21Z), flat since.  60-s sample: -226 MB with only ~110 MB of process writes (Chrome, Codex app).
  [M] Not S1 (workers write D:; repo s1/ 19 MB; venv no writes).  Full scan of accessible C: files: 0.83 GB of >20-MB files
  written in 3 h (Codex app sqlite 0.46 GB, Antigravity updater 0.16 GB, logs); no growth in ~/.claude, %TEMP%, Claude app data,
  Chrome, ProgramData (all top folders), Steam / Epic / BlueStacks, $Recycle.Bin, SoftwareDistribution, WinSxS\Temp,
  Windows\Installer.  `System Volume Information` modified today; shadow storage / restore points / vssadmin need elevation
  (access denied).  [I] Most likely a System Restore shadow-copy diff area growing with write churn on C:, or Store servicing
  (AppXSvc + InstallService running).  Nothing deleted.  User informed; if C: < 25 GB the controller stops launching (STOP-D)
  and the phase is resumed by relaunching the same job list once space is back.
- 2026-10-16T18:51Z check-in s1_b1_search_b: RUNNING complete 647/1194 (+75), unknowns 0 (+0), active 23, owner alive True, worker CPU +29875 s, C 79.7 GB (+26.49 GB/h) / D 496.5 GB, flags none
- 2026-10-16T18:51Z **C: incident 2 resolved by the user** (freed space): C: 74-80 GB free (from 28.4).  `s1_b1_search_b` 647/1,194, 0 unknowns; batch 1 searched 914, partition-limited 33; RAM free 27 GB.
- 2026-10-16T19:15Z check-in s1_b1_search_b: RUNNING complete 674/1194 (+27), unknowns 0 (+0), active 24, owner alive True, worker CPU +19696 s, C 79.9 GB (+0.44 GB/h) / D 496.4 GB, flags none
- 2026-10-16T19:16Z `s1_b1_search_b` 674/1,194, 0 unknowns.  [M] Partition-limited 33 -> 46 of 941 in 25 min: the searches completing
  18:48-19:13Z ran at cpu/wall 0.64-0.79 (usually 0.99) and 13/27 (all 34-44 sectors) hit a partition budget.  Contention from
  user-side activity (the C: cleanup; Epic Games overlay EOSOverlayRenderer running, i.e. likely a game); the budget is
  wall-clock, so heavy desktop use during searches reduces search depth on high-sector stars.  cpu/wall back to 0.93.  S-P as
  decided: 4.9% observed vs ~25% sector-matched expectation, not near firing.  User told.
- 2026-10-16T20:15Z check-in s1_b1_search_b: RUNNING complete 739/1194 (+65), unknowns 0 (+0), active 24, owner alive True, worker CPU +25672 s, C 187.0 GB (+106.42 GB/h) / D 496.1 GB, flags none
- 2026-10-16T21:16Z check-in s1_b1_search_b: RUNNING complete 786/1194 (+47), unknowns 0 (+0), active 24, owner alive True, worker CPU +34207 s, C 187.0 GB (+0.00 GB/h) / D 495.9 GB, flags none
- 2026-10-16T22:17Z check-in s1_b1_search_b: RUNNING complete 833/1194 (+47), unknowns 0 (+0), active 24, owner alive True, worker CPU +24709 s, C 185.9 GB (-1.05 GB/h) / D 495.7 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-16T23:17Z check-in s1_b1_search_b: RUNNING complete 870/1194 (+37), unknowns 0 (+0), active 24, owner alive True, worker CPU +25139 s, C 185.0 GB (-0.89 GB/h) / D 495.6 GB, flags none
- 2026-10-16T23:20Z `s1_b1_search_b` 870/1,194, 0 unknowns.  [M] Worker cpu/wall steady at 0.63-0.64 since ~22:20Z (the K1-documented
  E-core power-throttling level), while a Steam game runs in the foreground (`game`, `gameoverlayui64`); the 13 searches with
  >= 30 sectors completed since were all partition-limited (batch 1: 76/1,137 = 6.7%; sector-matched expectation ~25%).
  Windows-default scheduling is the calibrated condition for searches (frozen), so it is not overridden.  [I] While the
  foreground game holds, high-sector stars get shallower searches; S-P is evaluated on the batch as decided.
- 2026-10-17T00:18Z check-in s1_b1_search_b: RUNNING complete 919/1194 (+49), unknowns 0 (+0), active 23, owner alive True, worker CPU +22604 s, C 185.0 GB (+0.01 GB/h) / D 495.4 GB, flags none
- 2026-10-17T00:18Z User closed the game; [M] search workers back to cpu/wall 0.99 over the last 60 s (cumulative 0.63 for the jobs that ran through it).
- 2026-10-17T01:18Z check-in s1_b1_search_b: RUNNING complete 976/1194 (+57), unknowns 0 (+0), active 24, owner alive True, worker CPU +30765 s, C 185.1 GB (+0.02 GB/h) / D 495.2 GB, flags none
- 2026-10-17T02:19Z check-in s1_b1_search_b: RUNNING complete 1009/1194 (+33), unknowns 0 (+0), active 24, owner alive True, worker CPU +22563 s, C 186.2 GB (+1.16 GB/h) / D 495.0 GB, flags none
- 2026-10-17T02:21Z `s1_b1_search_b` 1,009/1,194, 0 unknowns; batch 1 searched 1,276, partition-limited 110 (8.6%).  [M] Workers throttled again (instant cpu/wall 0.63) with no game running: Windows' default state shifts by itself (K1 gotcha 1); calibrated condition, not overridden.
- 2026-10-17T03:19Z check-in s1_b1_search_b: RUNNING complete 1037/1194 (+28), unknowns 0 (+0), active 24, owner alive True, worker CPU +26827 s, C 186.2 GB (-0.02 GB/h) / D 494.9 GB, flags none
- 2026-10-17T04:19Z check-in s1_b1_search_b: RUNNING complete 1076/1194 (+39), unknowns 0 (+0), active 24, owner alive True, worker CPU +26418 s, C 186.2 GB (-0.03 GB/h) / D 494.7 GB, flags none
- 2026-10-17T05:20Z check-in s1_b1_search_b: RUNNING complete 1113/1194 (+37), unknowns 0 (+0), active 24, owner alive True, worker CPU +30093 s, C 186.2 GB (+0.02 GB/h) / D 494.6 GB, flags none
- 2026-10-17T06:20Z check-in s1_b1_search_b: RUNNING complete 1157/1194 (+44), unknowns 0 (+0), active 24, owner alive True, worker CPU +25548 s, C 186.0 GB (-0.24 GB/h) / D 494.4 GB, flags none
- 2026-10-17T07:11Z `s1_b1_search_b` 1,190/1,194 + 4-job tail (0 unknowns).  Launched `s1_b1_search_c` (the last 539 batch-1 stars; 539 + 1,457 searched + 4 in part b = 2,000; 24 workers): <= 28 concurrent searches while part b's tail finishes (<= ~1 h).  Tail waiter s1/work/wait_tail_s1.sh added.
- 2026-10-17T07:48Z check-in s1_b1_search_b: CLOSED complete 1194/1194 (+37), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 185.3 GB (-0.48 GB/h) / D 494.2 GB, flags none
- 2026-10-17T07:48Z check-in s1_b1_search_c: RUNNING complete 13/539 (+n/a), unknowns 0 (+n/a), active 24, owner alive True, worker CPU +23838 s, C 185.3 GB (n/a) / D 494.2 GB, flags none
- 2026-10-17T07:48Z `s1_b1_search_b` CLOSED 1,194/1,194, 0 unknowns, 25.5 h.  Part c 13/539.  Batch 1 searched 1,474, partition-limited 188 (12.8%).
- 2026-10-17T08:48Z check-in s1_b1_search_c: RUNNING complete 47/539 (+34), unknowns 0 (+0), active 24, owner alive True, worker CPU +17779 s, C 184.8 GB (-0.45 GB/h) / D 494.1 GB, flags none
- 2026-10-17T08:50Z `s1_b1_search_c` 47/539, 0 unknowns; workers throttled (instant cpu/wall 0.64): every recent star with >= 24 sectors partition-limited.  Batch 1 205/1,508 = 13.6% vs S-P threshold ~36.7%.  [I] The K1 calibration (SNR50, E4 budget) was measured under this Windows-default throttled state (cpu/wall 0.64), so throttled periods match calibration; unthrottled periods search deeper.
- 2026-10-17T09:49Z check-in s1_b1_search_c: RUNNING complete 80/539 (+33), unknowns 0 (+0), active 24, owner alive True, worker CPU +33248 s, C 184.8 GB (-0.01 GB/h) / D 493.9 GB, flags none
- 2026-10-17T10:49Z check-in s1_b1_search_c: RUNNING complete 119/539 (+39), unknowns 0 (+0), active 24, owner alive True, worker CPU +24591 s, C 184.6 GB (-0.24 GB/h) / D 493.8 GB, flags none
- 2026-10-17T11:50Z check-in s1_b1_search_c: RUNNING complete 176/539 (+57), unknowns 0 (+0), active 24, owner alive True, worker CPU +18489 s, C 187.5 GB (+2.91 GB/h) / D 493.6 GB, flags none
- 2026-10-17T12:50Z check-in s1_b1_search_c: RUNNING complete 238/539 (+62), unknowns 0 (+0), active 24, owner alive True, worker CPU +19443 s, C 187.0 GB (-0.53 GB/h) / D 493.4 GB, flags none
- 2026-10-17T13:50Z check-in s1_b1_search_c: RUNNING complete 298/539 (+60), unknowns 0 (+0), active 23, owner alive True, worker CPU +21522 s, C 189.0 GB (+2.00 GB/h) / D 493.2 GB, flags none
- 2026-10-17T14:51Z check-in s1_b1_search_c: RUNNING complete 375/539 (+77), unknowns 0 (+0), active 24, owner alive True, worker CPU +16430 s, C 189.1 GB (+0.07 GB/h) / D 492.9 GB, flags none
- 2026-10-17T15:51Z check-in s1_b1_search_c: RUNNING complete 491/539 (+116), unknowns 0 (+0), active 23, owner alive True, worker CPU +20484 s, C 195.2 GB (+6.07 GB/h) / D 492.5 GB, flags none
- 2026-10-17T16:28Z check-in s1_b1_search_c: CLOSED complete 539/539 (+48), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 194.9 GB (-0.38 GB/h) / D 492.4 GB, flags none
- 2026-10-17T16:28Z **Batch 1 search complete:** `s1_b1_search_c` CLOSED 539/539 (0 unknowns).  Batch 1: 2,000/2,000 searched, 0 search
  unknowns, 0 download unknowns after retry.  [M] Partition-limited 280/2,000 = 14.0%; S-P (as decided): expectation 22.7%,
  threshold 32.7% -> not triggered.  Collect: 37,590 accepted, 4,655 pre-gate.  [M] Search wall: part a 4.36 h, b 25.5 h, c ~9.3 h.
- 2026-10-17T16:35Z Pruning A, batch 1: 1,940 FITS caches, 19.8 GB freed (receipt s1/manifests/prune_fits_b1_*.json).
- 2026-10-17T16:36Z Launched `s1_b1_A` (4,479 pre-gate candidates not done in the smoke; 28 workers opted out of throttling, 1,800 s).
- 2026-10-17T16:40Z check-in s1_b1_A: RUNNING complete 209/4479 (+n/a), unknowns 2 (+n/a), active 28, owner alive True, worker CPU +6962 s, C 194.9 GB (n/a) / D 511.7 GB, flags ['UNKNOWNS_ROSE:0->2']
- 2026-10-17T17:40Z check-in s1_b1_A: RUNNING complete 500/4479 (+291), unknowns 6 (+4), active 27, owner alive True, worker CPU +12824 s, C 194.4 GB (-0.46 GB/h) / D 510.8 GB, flags ['UNKNOWNS_ROSE:2->6']
- 2026-10-17T18:42Z check-in s1_b1_A: RUNNING complete 908/4479 (+408), unknowns 9 (+3), active 28, owner alive True, worker CPU +6122 s, C 194.7 GB (+0.25 GB/h) / D 509.4 GB, flags ['UNKNOWNS_ROSE:6->9']
- 2026-10-17T19:42Z check-in s1_b1_A: RUNNING complete 1142/4479 (+234), unknowns 11 (+2), active 28, owner alive True, worker CPU +10663 s, C 194.5 GB (-0.25 GB/h) / D 508.4 GB, flags ['UNKNOWNS_ROSE:9->11']
- 2026-10-17T20:43Z check-in s1_b1_A: RUNNING complete 1345/4479 (+203), unknowns 12 (+1), active 28, owner alive True, worker CPU +13947 s, C 194.5 GB (-0.00 GB/h) / D 507.4 GB, flags ['UNKNOWNS_ROSE:11->12']
- 2026-10-17T21:43Z check-in s1_b1_A: RUNNING complete 1576/4479 (+231), unknowns 13 (+1), active 27, owner alive True, worker CPU +7462 s, C 194.2 GB (-0.22 GB/h) / D 506.3 GB, flags ['UNKNOWNS_ROSE:12->13']
- 2026-10-17T22:45Z check-in s1_b1_A: RUNNING complete 1836/4479 (+260), unknowns 13 (+0), active 28, owner alive True, worker CPU +23662 s, C 194.3 GB (+0.01 GB/h) / D 505.3 GB, flags none
- 2026-10-17T23:45Z check-in s1_b1_A: RUNNING complete 1919/4479 (+83), unknowns 17 (+4), active 28, owner alive True, worker CPU +14964 s, C 193.9 GB (-0.31 GB/h) / D 504.7 GB, flags ['UNKNOWNS_ROSE:13->17']
- 2026-10-18T00:46Z check-in s1_b1_A: RUNNING complete 2150/4479 (+231), unknowns 18 (+1), active 28, owner alive True, worker CPU +16052 s, C 193.8 GB (-0.19 GB/h) / D 503.7 GB, flags ['UNKNOWNS_ROSE:17->18']
- 2026-10-18T01:46Z check-in s1_b1_A: RUNNING complete 2359/4479 (+209), unknowns 20 (+2), active 28, owner alive True, worker CPU +20886 s, C 193.7 GB (-0.01 GB/h) / D 502.7 GB, flags ['UNKNOWNS_ROSE:18->20']
- 2026-10-18T02:47Z check-in s1_b1_A: RUNNING complete 2591/4479 (+232), unknowns 20 (+0), active 28, owner alive True, worker CPU +4116 s, C 194.0 GB (+0.26 GB/h) / D 501.7 GB, flags none
- 2026-10-18T03:47Z check-in s1_b1_A: RUNNING complete 2773/4479 (+182), unknowns 23 (+3), active 27, owner alive True, worker CPU +13035 s, C 194.0 GB (-0.00 GB/h) / D 500.8 GB, flags ['UNKNOWNS_ROSE:20->23']
- 2026-10-18T04:48Z check-in s1_b1_A: RUNNING complete 3120/4479 (+347), unknowns 27 (+4), active 26, owner alive True, worker CPU +2179 s, C 193.8 GB (-0.24 GB/h) / D 499.7 GB, flags ['UNKNOWNS_ROSE:23->27']
- 2026-10-18T05:48Z check-in s1_b1_A: RUNNING complete 3291/4479 (+171), unknowns 28 (+1), active 28, owner alive True, worker CPU +16322 s, C 193.8 GB (+0.00 GB/h) / D 498.8 GB, flags ['UNKNOWNS_ROSE:27->28']
- 2026-10-18T06:49Z check-in s1_b1_A: RUNNING complete 3378/4479 (+87), unknowns 29 (+1), active 28, owner alive True, worker CPU +16060 s, C 193.8 GB (-0.01 GB/h) / D 498.1 GB, flags ['UNKNOWNS_ROSE:28->29']
- 2026-10-18T07:49Z check-in s1_b1_A: RUNNING complete 3628/4479 (+250), unknowns 32 (+3), active 28, owner alive True, worker CPU +12717 s, C 193.8 GB (+0.01 GB/h) / D 497.0 GB, flags ['UNKNOWNS_ROSE:29->32']
- 2026-10-18T08:50Z check-in s1_b1_A: RUNNING complete 3876/4479 (+248), unknowns 35 (+3), active 28, owner alive True, worker CPU +6179 s, C 193.8 GB (-0.01 GB/h) / D 496.0 GB, flags ['UNKNOWNS_ROSE:32->35']
- 2026-10-18T09:35Z check-in s1_b1_A: CLOSED complete 4444/4479 (+568), unknowns 35 (+0), active 0, owner alive False, worker CPU +0 s, C 193.8 GB (+0.01 GB/h) / D 494.7 GB, flags none
- 2026-10-18T09:35Z `s1_b1_A` CLOSED 4,444/4,479 (19.0 h); 25 TIMEOUT (1,800 s, many-sector stars) + 10 deterministic ERROR (`max()
  iterable argument is empty`, duration > P/2; K1 gotcha 8).  Batch 1 A (incl. smoke): 139 PASS on 77 stars, 4,480 FAIL, 11 ERROR,
  25 pending retry.  Launched `s1_b1_A_retry` (-RetryOf, TIMEOUT jobs at 7,200 s; ERROR jobs are refused by their existing receipt,
  as designed) and `s1_b1_S` (136 A passes not yet S-tested; 16 workers, 600 s).
- 2026-10-18T09:46Z check-in s1_b1_S: CLOSED complete 136/136 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 192.7 GB (n/a) / D 494.6 GB, flags none
- 2026-10-18T09:46Z check-in s1_b1_A_retry: RUNNING complete 2/35 (+n/a), unknowns 10 (+n/a), active 23, owner alive True, worker CPU +11649 s, C 192.7 GB (n/a) / D 494.6 GB, flags ['UNKNOWNS_ROSE:0->10']
- 2026-10-18T09:48Z check-in s1_b1_nb_bulk: CLOSED complete 2/2 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 192.7 GB (n/a) / D 494.6 GB, flags none
- 2026-10-18T09:48Z check-in s1_b1_A_retry: RUNNING complete 2/35 (+0), unknowns 10 (+0), active 23, owner alive True, worker CPU +2210 s, C 192.7 GB (n/a) / D 494.6 GB, flags none
- 2026-10-18T09:56Z check-in s1_b1_nb: CLOSED complete 67/67 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 192.7 GB (n/a) / D 494.6 GB, flags none
- 2026-10-18T09:56Z check-in s1_b1_A_retry: RUNNING complete 2/35 (+0), unknowns 10 (+0), active 23, owner alive True, worker CPU +11496 s, C 192.7 GB (-0.04 GB/h) / D 494.6 GB, flags none
- 2026-10-18T10:00Z check-in s1_b1_B: CLOSED complete 122/122 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 192.7 GB (n/a) / D 494.6 GB, flags none
- 2026-10-18T10:00Z check-in s1_b1_A_retry: RUNNING complete 6/35 (+4), unknowns 10 (+0), active 19, owner alive True, worker CPU +3943 s, C 192.7 GB (+0.10 GB/h) / D 494.6 GB, flags none
- 2026-10-18T10:00Z `s1_b1_S` CLOSED 136/136 (139 S receipts incl. smoke: bound_alias PASS 125, FAIL 14; 68 stars).  Neighbours `s1_b1_nb_bulk` 2/2 (SIMBAD 43/67 with objects, VSX 37/67), `s1_b1_nb` 67/67.  `s1_b1_B` CLOSED 122/122: B PASS 125/125 (68 stars), 0 unknowns.  C waits for `s1_b1_A_retry` (19 active, <= 7,200 s) and the S of any new A pass (M1 needs every S result; one CPU-heavy phase at a time).
- 2026-10-18T10:12Z check-in s1_b1_A_retry: CLOSED complete 25/35 (+19), unknowns 10 (+0), active 0, owner alive False, worker CPU +0 s, C 193.1 GB (+2.05 GB/h) / D 494.5 GB, flags none
- 2026-10-18T10:15Z `s1_b1_A_retry` CLOSED: the 25 TIMEOUT jobs COMPLETE at 4x (2 new PASS); the 10 ERROR jobs refused by their
  receipts (FileExistsError), as designed.  Batch 1 A final: 141 PASS, 4,503 FAIL, 11 deterministic ERROR (0.24%).  `s1_b1_S2`
  2/2 bound_alias PASS (TIC 219806608 p01, TIC 382098683 p08); neighbours round 2 for TIC 382098683 running.
- 2026-10-18T10:16Z All batch-1 S jobs closed -> launched `s1_b1_C` (122 B passes not yet C-tested; V3 + M1, 56 with siblings; 8 x 4
  TLS threads, 14,400 s).  The 2 retry candidates get B then their own C.  Batch 1 in C -> launched `s1_b2_dl` (2,000 stars, 4 workers).
- 2026-10-18T10:16Z check-in s1_b1_nb2: CLOSED complete 1/1 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 193.1 GB (n/a) / D 494.3 GB, flags none
- 2026-10-18T10:16Z check-in s1_b1_C: RUNNING complete 0/122 (+n/a), unknowns 0 (+n/a), active 8, owner alive True, worker CPU +4722 s, C 193.1 GB (n/a) / D 494.3 GB, flags none
- 2026-10-18T10:16Z check-in s1_b2_dl: RUNNING complete 6/2000 (+n/a), unknowns 0 (+n/a), active 4, owner alive True, worker CPU +49 s, C 193.1 GB (n/a) / D 494.3 GB, flags none
- 2026-10-18T10:17Z Neighbours round 2 (`s1_b1_nb2_bulk` 2/2, `s1_b1_nb2` 1/1); `s1_b1_B2` 2/2 PASS.  Their C (`s1_b1_C2`) runs after `s1_b1_C` closes (one C phase at a time).
- 2026-10-18T11:17Z check-in s1_b1_C: RUNNING complete 52/122 (+52), unknowns 0 (+0), active 8, owner alive True, worker CPU +2607 s, C 192.9 GB (-0.22 GB/h) / D 490.7 GB, flags none
- 2026-10-18T11:17Z check-in s1_b2_dl: RUNNING complete 176/2000 (+170), unknowns 0 (+0), active 3, owner alive True, worker CPU +15 s, C 192.9 GB (-0.22 GB/h) / D 490.7 GB, flags none
- 2026-10-18T11:20Z `s1_b1_C` 52/122 (17 PASS so far, 0 unknowns, walls <= 1,592 s).  Launched `s1_b1_D` on the 17 C passes so far (network-bound, overlaps C): redact_catalogue false on all 17; hard stop CLEAN 16 / FLAG 1 (TCE sidecar 1); s_mode bound_alias; 6 workers, 5,400 s.  `s1_b2_dl` 176/2,000.
- 2026-10-18T11:34Z check-in s1_b1_D: RUNNING complete 8/17 (+n/a), unknowns 0 (+n/a), active 6, owner alive True, worker CPU +152 s, C 192.9 GB (n/a) / D 481.8 GB, flags none
- 2026-10-18T11:34Z check-in s1_b1_C: RUNNING complete 53/122 (+1), unknowns 0 (+0), active 8, owner alive True, worker CPU +27384 s, C 192.9 GB (+0.02 GB/h) / D 481.8 GB, flags none
- 2026-10-18T11:34Z check-in s1_b2_dl: RUNNING complete 201/2000 (+25), unknowns 0 (+0), active 4, owner alive True, worker CPU +21 s, C 192.9 GB (+0.02 GB/h) / D 481.8 GB, flags none
- 2026-10-18T11:36Z **First Stage D receipts on S1 paths** (`s1_b1_D` 9/17): all COMPLETE, errors none, redacted false, packets for SUBMIT/HOLD; walls 356-767 s; TESScut caches on D: (lightkurve_funnel 6.0 GB, xdg_cache 1.9 GB), C: flat.  Verdicts so far: SUBMIT 1 (tier 2), HOLD 7 (H1 x3, H2 x3, H5 x1), KILL 1 (K8).  Several from adjacent TIC ids (155913240 / 155943781 / 155949537; 116046773 / 116047785): [I] possibly one signal in neighbouring stars; reviewed in the batch report.  S-L watch: threshold 60 SUBMIT+HOLD for 2,000 stars.
- 2026-10-18T11:49Z check-in s1_b1_D: CLOSED complete 17/17 (+9), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 192.9 GB (-0.00 GB/h) / D 474.8 GB, flags none
- 2026-10-18T11:49Z check-in s1_b1_C: RUNNING complete 60/122 (+7), unknowns 0 (+0), active 8, owner alive True, worker CPU +13734 s, C 192.9 GB (-0.00 GB/h) / D 474.8 GB, flags none
- 2026-10-18T11:49Z check-in s1_b2_dl: RUNNING complete 224/2000 (+23), unknowns 0 (+0), active 4, owner alive True, worker CPU +41 s, C 192.9 GB (-0.00 GB/h) / D 474.8 GB, flags none
- 2026-10-18T11:50Z `s1_b1_D` CLOSED 17/17, 0 unknowns: SUBMIT 4, HOLD 12, KILL 1.  `s1_b1_C` 64 receipts (19 PASS).  [I] Projection ~36 SUBMIT+HOLD for batch 1 (S-L at 60).
- 2026-10-18T12:49Z check-in s1_b1_C: RUNNING complete 99/122 (+39), unknowns 0 (+0), active 8, owner alive True, worker CPU +18437 s, C 192.9 GB (-0.00 GB/h) / D 472.4 GB, flags none
- 2026-10-18T12:49Z check-in s1_b2_dl: RUNNING complete 343/2000 (+119), unknowns 12 (+12), active 4, owner alive True, worker CPU +24 s, C 192.9 GB (-0.00 GB/h) / D 472.4 GB, flags ['UNKNOWNS_ROSE:0->12']
- 2026-10-18T12:52Z **MAST outage from ~12:35Z:** every `s1_b2_dl` job since 12:35Z timed out at the 240-s search_lightcurve bound (12
  unknowns; 0 completions after 12:37Z); a MAST API probe timed out at 30 s.  Operational: `s1/manifests/STOP_s1_b2_dl` written (no new
  download launches; active jobs finish; resume = relaunch the same job list; the outage's unknowns go to the attempt-2 retry).
  **Stage D held during the outage** (missing TESScut cutouts change verdicts: K2 TIC 1950736).  Stage C (local) continues.  S-F
  applies if the outage exceeds 6 h (from 12:35Z -> 18:35Z).
- 2026-10-18T12:56Z check-in s1_b1_C: RUNNING complete 102/122 (+3), unknowns 0 (+0), active 8, owner alive True, worker CPU +10623 s, C 192.9 GB (-0.08 GB/h) / D 472.3 GB, flags none
- 2026-10-18T12:56Z check-in s1_b2_dl: STOPPED complete 343/2000 (+0), unknowns 18 (+6), active 0, owner alive False, worker CPU +0 s, C 192.9 GB (-0.08 GB/h) / D 472.3 GB, flags ['UNKNOWNS_ROSE:12->18', 'STOP:STOP file']
- 2026-10-18T13:12Z check-in s1_b1_C: CLOSED complete 122/122 (+20), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 192.9 GB (-0.02 GB/h) / D 472.2 GB, flags none
- 2026-10-18T13:12Z `s1_b1_C` CLOSED 122/122, 0 unknowns.  Batch 1 C: 30 PASS / 95 FAIL of 125 (max wall 2,029 s; 0 over 4 h -> S-C
  fine).  MAST back (API 200 in 0.46 s, TESScut 200 in 10 s): outage ~12:35-13:10Z (~35 min, well under S-F's 6 h).
- 2026-10-18T13:15Z Launched `s1_b1_C2` (the 2 A-retry candidates; 2 x 4 threads), `s1_b1_D2` (13 new C passes; 6 workers), and resumed
  `s1_b2_dl` (STOP file moved to s1/manifests/superseded/; same job list; completed and failed attempts are not re-run, the 18 outage
  unknowns go to the attempt-2 retry).  Batch 2 search starts when C2 closes (one CPU-heavy phase at a time).
- 2026-10-18T13:29Z check-in s1_b1_C2: CLOSED complete 2/2 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 192.9 GB (n/a) / D 470.6 GB, flags none
- 2026-10-18T13:29Z check-in s1_b1_D2: RUNNING complete 1/13 (+n/a), unknowns 0 (+n/a), active 6, owner alive True, worker CPU +54 s, C 192.9 GB (n/a) / D 470.6 GB, flags none
- 2026-10-18T13:29Z check-in s1_b2_dl: RUNNING complete 353/2000 (+10), unknowns 32 (+14), active 4, owner alive True, worker CPU +25 s, C 192.9 GB (+0.01 GB/h) / D 470.6 GB, flags ['UNKNOWNS_ROSE:18->32']
- 2026-10-18T13:30Z `s1_b1_C2` CLOSED 2/2 PASS (899 / 975 s): batch 1 C passes 32 (30 + 2).  MAST still degraded (search_lightcurve
  13:20-13:30Z: 9 timeouts / RemoteServiceError vs 10 completions; TESScut 200 in ~11 s; the first D2 job had 23/23 TESScut sectors):
  `STOP_s1_b2_dl` re-written (downloads paused until MAST is healthy).  Launched `s1_b2_search_a` (358 downloaded batch-2 stars, 24
  workers): batch 2 search started.
- 2026-10-18T13:34Z **Incident (operational, contained):** `s1_b1_D3` was planned for the 2 C2 passes but plan_d also took the 12 D2 jobs
  without receipts (plan_d did not skip jobs held by open phases).  D3 started one of them (s1_259270670_p07) while D2 ran it.  Action:
  `STOP_s1_b1_D3`; the duplicate worker tree (pids 36484, 50220) stopped with Stop-Process after ~15 s.  [M] It was still importing
  (log = lightkurve import warning only) and wrote nothing: every file in the case root was last written 13:30:35-36Z by D2's worker.
  D2 continues that job.  Fix: plan_s1 now skips every job held by any open phase (search, funnel and D planners), checked before any
  runtime is written.  D3 keeps its legitimate job (s1_219806608_p01); s1_382098683_p08 gets D after D2/D3 close.
- 2026-10-18T13:41Z check-in s1_b1_D2: RUNNING complete 1/13 (+0), unknowns 0 (+0), active 6, owner alive True, worker CPU +0 s, C 192.9 GB (-0.08 GB/h) / D 468.2 GB, flags ['STALLED_WORKERS:D_s1_b1_s1_259270670_p07,D_s1_b1_s1_261235862_p07,D_s1_b1_s1_262843927_p09,D_s1_b1_s1_264722332_p01,D_s1_b1_s1_287425024_p10,D_s1_b1_s1_335745090_p03', 'NO_PROGRESS_SINCE_LAST_WAKE']
- 2026-10-18T13:41Z check-in s1_b1_D3: STOPPED complete 1/14 (+n/a), unknowns 1 (+n/a), active 0, owner alive False, worker CPU +0 s, C 192.9 GB (n/a) / D 468.2 GB, flags ['UNKNOWNS_ROSE:0->1', 'STOP:STOP file']
- 2026-10-18T13:41Z check-in s1_b2_search_a: RUNNING complete 2/358 (+n/a), unknowns 0 (+n/a), active 24, owner alive True, worker CPU +9959 s, C 192.9 GB (n/a) / D 468.2 GB, flags none
- 2026-10-18T13:45Z D2's 6 active workers had flat CPU since ~13:13Z, each holding an established connection to MAST front-end
  130.167.220.112:443 (no response; logs = import warning only).  A real search_lightcurve probe (s1/work/mast_probe_s1.py) then
  answered in 8.3 s, so the 6 hung worker trees were stopped (Stop-Process) instead of waiting for the 5,400-s deadline; D2 closed
  STOPPED (1 COMPLETE, 6 stopped, 6 never launched); D3 STOPPED (1 COMPLETE: s1_219806608_p01; 1 = the stopped duplicate).
  No verdict came from the hung period.  STOP files archived.  Launched `s1_b1_D4` (the 13 C passes without a D receipt).
  s1/work/wait_mast_s1.sh now probes with a real search_lightcurve (bounded 90 s, 2 consecutive successes).
- 2026-10-18T13:55Z check-in s1_b1_D4: RUNNING complete 0/13 (+n/a), unknowns 0 (+n/a), active 6, owner alive True, worker CPU +69 s, C 192.7 GB (n/a) / D 464.5 GB, flags none
- 2026-10-18T13:55Z check-in s1_b2_search_a: RUNNING complete 3/358 (+1), unknowns 0 (+0), active 24, owner alive True, worker CPU +12128 s, C 192.7 GB (-1.01 GB/h) / D 464.5 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-18T13:52Z MAST healthy (2 consecutive search_lightcurve probes); `s1_b1_D4` progressing (TESScut cutouts downloading, MAST + AWS S3 connections, logs growing).  Resumed `s1_b2_dl` (STOP archived).
- 2026-10-18T14:17Z check-in s1_b1_D4: CLOSED complete 13/13 (+13), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 191.9 GB (-2.10 GB/h) / D 453.5 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-18T14:17Z check-in s1_b2_dl: RUNNING complete 425/2000 (+72), unknowns 32 (+0), active 4, owner alive True, worker CPU +26 s, C 191.9 GB (-1.28 GB/h) / D 453.5 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-18T14:17Z check-in s1_b2_search_a: RUNNING complete 9/358 (+6), unknowns 0 (+0), active 24, owner alive True, worker CPU +18519 s, C 191.9 GB (-2.10 GB/h) / D 453.5 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-18T14:17Z `s1_b1_D4` CLOSED 13/13, 0 unknowns.  **BATCH 1 COMPLETE** (`s1/results/BATCH_1.md`, `batch_1.json`, `disk_b1.json`):
  2,000 searched (0 unknowns at download/search after retry); partition-limited 14.0% (S-P threshold 32.7%: not triggered); 4,655
  pre-gate -> A 141 PASS (11 deterministic ERROR) -> S bound_alias 127 PASS -> B 127 -> C 32 PASS (0 unknowns; max 2,029 s; S-C fine)
  -> D: **SUBMIT 7, HOLD 16, KILL 9** (KILL: K8 5, K7 2, K5 1, K6 1).  SUBMIT+HOLD 11.5 per 1,000 (S-L 30: fine); eM slice 18 of 23.
  7 of 23 flagged "pixel coverage incomplete" (a Stage D centroid sector with source none; verdicts unchanged).  [M] Phase wall
  hours: search 41.4, A 18.7, C 3.5, D 1.7, download 7.2.  [M] Disk: TESScut ~1.0 GB per D candidate (K2 0.35); funnel 4.1 MB per
  A candidate; [I] projected final S1 root ~170 GB + ~70 GB transient peak, vs D: 453 GB free.
- 2026-10-18T14:25Z Pruning B, batch 1 (after its report, no D phase open): 528 TESScut files, 31.7 GB freed (cutoff = D4 closure
  14:17:29Z; receipt s1/manifests/prune_tesscut_b1_*.json).
- 2026-10-18T15:23Z check-in s1_b2_dl: RUNNING complete 889/2000 (+464), unknowns 32 (+0), active 4, owner alive True, worker CPU +11 s, C 191.6 GB (-0.28 GB/h) / D 481.1 GB, flags none
- 2026-10-18T15:23Z check-in s1_b2_search_a: RUNNING complete 42/358 (+33), unknowns 0 (+0), active 24, owner alive True, worker CPU +29650 s, C 191.6 GB (-0.28 GB/h) / D 481.1 GB, flags none
- 2026-10-18T15:25Z Batch 2: `s1_b2_dl` 889/2,000 (32 unknowns = outage, retry later); `s1_b2_search_a` 42/358.  [M] Interim partition-limited 21/42 = 50% vs 26% sector-matched for these stars (mean 24 sectors); workers throttled (cpu/wall 0.63-0.64).  [I] Batch 2 S-P threshold 24.6% (expectation 14.6%) may be exceeded if throttling persists; user informed in advance (options: accept a possible S-P pause, or the user's power-throttling exemption).
- 2026-10-18T16:24Z check-in s1_b2_dl: RUNNING complete 1325/2000 (+436), unknowns 32 (+0), active 4, owner alive True, worker CPU +13 s, C 189.5 GB (-2.07 GB/h) / D 478.0 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-18T16:24Z check-in s1_b2_search_a: RUNNING complete 66/358 (+24), unknowns 0 (+0), active 24, owner alive True, worker CPU +27690 s, C 189.5 GB (-2.07 GB/h) / D 478.0 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-18T17:24Z check-in s1_b2_dl: RUNNING complete 1797/2000 (+472), unknowns 32 (+0), active 4, owner alive True, worker CPU +15 s, C 188.4 GB (-1.09 GB/h) / D 475.0 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-18T17:24Z check-in s1_b2_search_a: RUNNING complete 93/358 (+27), unknowns 0 (+0), active 24, owner alive True, worker CPU +28995 s, C 188.4 GB (-1.09 GB/h) / D 475.0 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-18T17:47Z check-in s1_b2_dl: CLOSED complete 1968/2000 (+171), unknowns 32 (+0), active 0, owner alive False, worker CPU +0 s, C 188.3 GB (-0.22 GB/h) / D 474.0 GB, flags none
- 2026-10-18T17:47Z check-in s1_b2_search_a: RUNNING complete 100/358 (+7), unknowns 0 (+0), active 24, owner alive True, worker CPU +17789 s, C 188.3 GB (-0.23 GB/h) / D 474.0 GB, flags none
- 2026-10-18T17:48Z `s1_b2_dl` CLOSED 1,968/2,000 (32 unknowns, all from the 12:35-13:50Z MAST outage).  Launched `s1_b2_dl_retry` (attempt 2, 3,600 s).  `s1_b2_search_a` 100/358; batch 2 partition-limited 59/100 (throttled, high-sector first).
- 2026-10-18T18:02Z check-in s1_b2_dl_retry: CLOSED complete 32/32 (+n/a), unknowns 0 (+n/a), active 0, owner alive False, worker CPU +0 s, C 188.0 GB (n/a) / D 473.3 GB, flags none
- 2026-10-18T18:02Z check-in s1_b2_search_a: RUNNING complete 108/358 (+8), unknowns 0 (+0), active 24, owner alive True, worker CPU +10680 s, C 188.0 GB (-1.12 GB/h) / D 473.3 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-18T18:02Z `s1_b2_dl_retry` CLOSED 32/32 COMPLETE.  **Batch 2 downloads 2,000/2,000, 0 unknowns.**
- 2026-10-18T19:03Z check-in s1_b2_search_a: RUNNING complete 131/358 (+23), unknowns 0 (+0), active 24, owner alive True, worker CPU +28860 s, C 187.9 GB (-0.07 GB/h) / D 473.2 GB, flags none
- 2026-10-18T20:04Z check-in s1_b2_search_a: RUNNING complete 150/358 (+19), unknowns 0 (+0), active 24, owner alive True, worker CPU +40804 s, C 187.9 GB (-0.00 GB/h) / D 473.1 GB, flags none
- 2026-10-18T21:04Z check-in s1_b2_search_a: RUNNING complete 178/358 (+28), unknowns 0 (+0), active 24, owner alive True, worker CPU +30163 s, C 187.0 GB (-0.91 GB/h) / D 473.0 GB, flags none
- 2026-10-18T22:05Z check-in s1_b2_search_a: RUNNING complete 202/358 (+24), unknowns 0 (+0), active 24, owner alive True, worker CPU +25244 s, C 187.2 GB (+0.17 GB/h) / D 470.1 GB, flags none
- 2026-10-18T23:05Z check-in s1_b2_search_a: RUNNING complete 220/358 (+18), unknowns 0 (+0), active 24, owner alive True, worker CPU +30684 s, C 187.0 GB (-0.25 GB/h) / D 469.4 GB, flags none
- 2026-10-19T00:05Z check-in s1_b2_search_a: RUNNING complete 252/358 (+32), unknowns 0 (+0), active 24, owner alive True, worker CPU +31533 s, C 187.0 GB (+0.01 GB/h) / D 469.2 GB, flags none
- 2026-10-19T01:06Z check-in s1_b2_search_a: RUNNING complete 276/358 (+24), unknowns 0 (+0), active 24, owner alive True, worker CPU +24879 s, C 186.7 GB (-0.26 GB/h) / D 469.0 GB, flags none
- 2026-10-19T02:06Z check-in s1_b2_search_a: RUNNING complete 302/358 (+26), unknowns 0 (+0), active 24, owner alive True, worker CPU +24273 s, C 186.7 GB (-0.02 GB/h) / D 468.8 GB, flags none
- 2026-10-19T03:07Z check-in s1_b2_search_a: RUNNING complete 326/358 (+24), unknowns 0 (+0), active 24, owner alive True, worker CPU +25575 s, C 186.6 GB (-0.03 GB/h) / D 466.6 GB, flags none
- 2026-10-19T04:00Z `s1_b2_search_a` 354/358 (4-job tail, 0 unknowns); batch 2 partition-limited 209/326+ so far (throttled; part a was
  all K ranks 501-1000).  Launched `s1_b2_search_b` (1,642 = the rest of batch 2: 1,642 + 354 searched + 4 in part a = 2,000; 24 workers).
  **HAND-OFF (session usage limit reached; no waiter armed).** Detached controllers keep running.  Next steps for whoever resumes:
  1. `bash s1/work/wake_s1.sh 2 s1_b2_search_a s1_b2_search_b`; owner files in s1/manifests = open phases (recovery: prompt 4.3).
  2. When part b closes: `plan_s1.py collect 2`; S-P check (report_s1 sp_rate; batch 2 threshold ~24.6%; likely to FIRE under
     throttling -> pause and report to the user); `work/prune_s1.py fits 2`; then A (28 w, 1,800 s) -> A retry -> S -> neighbours
     (bulk then per-star) -> B -> C (all S closed; 8 x 4) -> D (6 w; hold D during MAST outages) -> report_s1.py 2 -> prune tesscut 2
     -> commit.  Batch 3 download may start when batch 2 is in C/D.
  3. After batch 2: eM rule (eM SUBMIT+HOLD in batches 1-2; batch 1 alone has 18 -> ">= 5: eM leads") -> PAUSE for the user before
     changing batches 3-5.
- 2026-10-19T11:22Z check-in s1_b2_search_a: CLOSED complete 358/358 (+32), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 185.1 GB (-0.19 GB/h) / D 465.4 GB, flags none
- 2026-10-19T11:22Z check-in s1_b2_search_b: RUNNING complete 223/1642 (+n/a), unknowns 0 (+n/a), active 24, owner alive True, worker CPU +29566 s, C 185.1 GB (n/a) / D 465.4 GB, flags none
- 2026-10-19T11:22Z Supervision resumed.  `s1_b2_search_a` CLOSED 358/358, 0 unknowns.  `s1_b2_search_b` 223/1,642, 0 unknowns.  Batch 2 searched 581, partition-limited 334 (57%; the K block first, throttled).
- 2026-10-19T12:23Z check-in s1_b2_search_b: RUNNING complete 283/1642 (+60), unknowns 0 (+0), active 24, owner alive True, worker CPU +22584 s, C 185.1 GB (+0.00 GB/h) / D 465.2 GB, flags none
- 2026-10-19T13:24Z check-in s1_b2_search_b: RUNNING complete 339/1642 (+56), unknowns 0 (+0), active 24, owner alive True, worker CPU +21360 s, C 185.1 GB (-0.01 GB/h) / D 465.0 GB, flags none
- 2026-10-19T14:24Z check-in s1_b2_search_b: RUNNING complete 400/1642 (+61), unknowns 0 (+0), active 24, owner alive True, worker CPU +21218 s, C 184.8 GB (-0.24 GB/h) / D 464.8 GB, flags none
- 2026-10-19T15:25Z check-in s1_b2_search_b: RUNNING complete 469/1642 (+69), unknowns 0 (+0), active 24, owner alive True, worker CPU +19698 s, C 184.8 GB (-0.00 GB/h) / D 464.6 GB, flags none
- 2026-10-19T16:25Z check-in s1_b2_search_b: RUNNING complete 533/1642 (+64), unknowns 0 (+0), active 24, owner alive True, worker CPU +16645 s, C 184.6 GB (-0.22 GB/h) / D 464.4 GB, flags none
- 2026-10-19T17:26Z check-in s1_b2_search_b: RUNNING complete 611/1642 (+78), unknowns 0 (+0), active 24, owner alive True, worker CPU +16342 s, C 184.5 GB (-0.07 GB/h) / D 464.2 GB, flags none
- 2026-10-19T18:27Z check-in s1_b2_search_b: RUNNING complete 680/1642 (+69), unknowns 0 (+0), active 24, owner alive True, worker CPU +25877 s, C 183.5 GB (-1.03 GB/h) / D 464.0 GB, flags ['C_LOW_OR_FALLING']
- 2026-10-19T19:28Z check-in s1_b2_search_b: RUNNING complete 763/1642 (+83), unknowns 0 (+0), active 24, owner alive True, worker CPU +16625 s, C 183.6 GB (+0.16 GB/h) / D 463.7 GB, flags none
- 2026-10-19T20:28Z check-in s1_b2_search_b: RUNNING complete 813/1642 (+50), unknowns 0 (+0), active 24, owner alive True, worker CPU +22134 s, C 183.6 GB (-0.08 GB/h) / D 463.5 GB, flags none
- 2026-10-19T21:28Z check-in s1_b2_search_b: RUNNING complete 883/1642 (+70), unknowns 0 (+0), active 23, owner alive True, worker CPU +20904 s, C 183.6 GB (+0.08 GB/h) / D 463.3 GB, flags none
- 2026-10-19T22:29Z check-in s1_b2_search_b: RUNNING complete 949/1642 (+66), unknowns 0 (+0), active 24, owner alive True, worker CPU +19844 s, C 183.6 GB (-0.01 GB/h) / D 463.1 GB, flags none
- 2026-10-19T23:29Z check-in s1_b2_search_b: RUNNING complete 1011/1642 (+62), unknowns 0 (+0), active 24, owner alive True, worker CPU +22077 s, C 183.6 GB (-0.00 GB/h) / D 462.9 GB, flags none
- 2026-10-20T00:30Z check-in s1_b2_search_b: RUNNING complete 1099/1642 (+88), unknowns 0 (+0), active 24, owner alive True, worker CPU +14461 s, C 189.7 GB (+5.99 GB/h) / D 462.6 GB, flags none
- 2026-10-20T01:30Z check-in s1_b2_search_b: RUNNING complete 1164/1642 (+65), unknowns 0 (+0), active 24, owner alive True, worker CPU +18341 s, C 189.7 GB (-0.01 GB/h) / D 462.4 GB, flags none
- 2026-10-20T02:31Z check-in s1_b2_search_b: RUNNING complete 1234/1642 (+70), unknowns 0 (+0), active 24, owner alive True, worker CPU +14933 s, C 189.7 GB (+0.00 GB/h) / D 462.2 GB, flags none
- 2026-10-20T03:31Z check-in s1_b2_search_b: RUNNING complete 1312/1642 (+78), unknowns 0 (+0), active 24, owner alive True, worker CPU +18566 s, C 189.5 GB (-0.15 GB/h) / D 462.0 GB, flags none
- 2026-10-20T04:32Z check-in s1_b2_search_b: RUNNING complete 1388/1642 (+76), unknowns 0 (+0), active 24, owner alive True, worker CPU +18917 s, C 189.6 GB (+0.07 GB/h) / D 461.7 GB, flags none
- 2026-10-20T05:32Z check-in s1_b2_search_b: RUNNING complete 1474/1642 (+86), unknowns 0 (+0), active 24, owner alive True, worker CPU +13181 s, C 189.6 GB (+0.00 GB/h) / D 461.5 GB, flags none
- 2026-10-20T06:32Z check-in s1_b2_search_b: RUNNING complete 1569/1642 (+95), unknowns 0 (+0), active 23, owner alive True, worker CPU +9362 s, C 189.8 GB (+0.19 GB/h) / D 461.2 GB, flags none
- 2026-10-20T07:33Z check-in s1_b2_search_b: RUNNING complete 1636/1642 (+67), unknowns 0 (+0), active 6, owner alive True, worker CPU +10842 s, C 188.8 GB (-0.92 GB/h) / D 461.0 GB, flags none
- 2026-10-20T08:16Z check-in s1_b2_search_b: CLOSED complete 1642/1642 (+6), unknowns 0 (+0), active 0, owner alive False, worker CPU +0 s, C 191.1 GB (+3.15 GB/h) / D 461.0 GB, flags none
- 2026-10-20T08:13Z **Batch 2 search complete:** `s1_b2_search_b` CLOSED 1,642/1,642; batch 2 2,000/2,000 searched, 0 unknowns; collect: 33,549
  accepted, 4,332 pre-gate.  **S-P FIRES:** partition-limited 524/2,000 = 26.2% > threshold 24.57% (sector-matched expectation 14.57% + 10 pp).
  [M] 99% of batch-2 searches ran throttled (cpu/wall 0.64); limited by sector bin 0-12: 0%, 13-19: 7%, 20-29: 57%, 30-36: 92%, >= 37: 97%
  (K1/K2 mixed-state table: 3/40/59/47%).  [M] Exhausted partitions are mostly single chunks (chunk0 487, chunk1-5 614) with a median 7%
  budget share; the full-baseline stitch search was exhausted on 36 stars (1.8%).  **PAUSED before Stage A** (s1/manifests/PAUSE_S-P_b2.json);
  options put to the user.  Pruning A, batch 2 done (search closed).  eM rule heads-up given at the same time (batch 1 alone: 18 eM SUBMIT+HOLD).
- 2026-10-20T11:35Z **User decisions** (S-P pause 08:18-11:35Z, 3.3 h) (s1/manifests/decision_S-P_b2.json): S-P batch 2 -> **exempt Python from power throttling and continue**
  (batch 2 proceeds to Stage A as searched; the user runs the two `powercfg /powerthrottling disable` commands; batches 3-5 search
  unthrottled, a recorded departure from the frozen Windows-default search scheduling from the time it is applied).  eM rule ->
  **decide after batch 2** (pause after batch 2's D).  K ranks 1,001-3,000 are needed under every eM option: their download may start
  while batch 2 is in C/D.  Pause file archived.
- 2026-10-20T11:35Z Launched `s1_b2_A` (4,332 pre-gate; 28 workers, 1,800 s).
- 2026-10-20T11:45Z check-in s1_b2_A: RUNNING complete 352/4332 (+n/a), unknowns 1 (+n/a), active 27, owner alive True, worker CPU +2133 s, C 191.5 GB (n/a) / D 476.1 GB, flags ['UNKNOWNS_ROSE:0->1']
- 2026-10-20T11:47Z Correction: the two entries above were first written with hand-made times (08:25Z / 08:27Z); the decision file says 11:34:47Z.  Early check `s1_b2_A`: 352/4,332 in ~10 min, 26 PASS, 1 deterministic ERROR (max()).
- 2026-10-20T12:46Z check-in s1_b2_A: RUNNING complete 917/4332 (+565), unknowns 3 (+2), active 27, owner alive True, worker CPU +3741 s, C 191.5 GB (-0.01 GB/h) / D 474.6 GB, flags ['UNKNOWNS_ROSE:1->3']
- 2026-10-20T13:47Z check-in s1_b2_A: RUNNING complete 1290/4332 (+373), unknowns 4 (+1), active 28, owner alive True, worker CPU +15065 s, C 191.2 GB (-0.22 GB/h) / D 473.3 GB, flags ['UNKNOWNS_ROSE:3->4']
- 2026-10-20T14:47Z check-in s1_b2_A: RUNNING complete 1597/4332 (+307), unknowns 8 (+4), active 28, owner alive True, worker CPU +6660 s, C 190.6 GB (-0.58 GB/h) / D 472.0 GB, flags ['UNKNOWNS_ROSE:4->8']
- 2026-10-20T15:48Z check-in s1_b2_A: RUNNING complete 1932/4332 (+335), unknowns 10 (+2), active 28, owner alive True, worker CPU +19187 s, C 191.5 GB (+0.84 GB/h) / D 470.8 GB, flags ['UNKNOWNS_ROSE:8->10']
- 2026-10-20T16:49Z check-in s1_b2_A: RUNNING complete 2272/4332 (+340), unknowns 12 (+2), active 28, owner alive True, worker CPU +1687 s, C 191.2 GB (-0.23 GB/h) / D 469.7 GB, flags ['UNKNOWNS_ROSE:10->12']
- 2026-10-20T17:49Z check-in s1_b2_A: RUNNING complete 2622/4332 (+350), unknowns 14 (+2), active 28, owner alive True, worker CPU +4079 s, C 191.2 GB (-0.01 GB/h) / D 468.4 GB, flags ['UNKNOWNS_ROSE:12->14']
- 2026-10-20T18:50Z check-in s1_b2_A: RUNNING complete 2865/4332 (+243), unknowns 18 (+4), active 27, owner alive True, worker CPU +6194 s, C 191.3 GB (+0.03 GB/h) / D 467.5 GB, flags ['UNKNOWNS_ROSE:14->18']
- 2026-10-20T19:50Z check-in s1_b2_A: RUNNING complete 3099/4332 (+234), unknowns 20 (+2), active 28, owner alive True, worker CPU +17972 s, C 191.0 GB (-0.26 GB/h) / D 466.5 GB, flags ['UNKNOWNS_ROSE:18->20']
