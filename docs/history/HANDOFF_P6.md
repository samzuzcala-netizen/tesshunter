# HANDOFF P6: re-vetting all 405 survivors under the audit rules

Date: 2026-09-03. Branch `improve/recovery`. Environment as in `HANDOFF_P5.md`
(double-nested repo, `tesshunter_venv` Python 3.13, lightkurve 2.6.0,
transitleastsquares 1.32, wotan 1.10). No package was added in this prompt.

Session start state, measured [M]: `git status` clean on 6d5114c (the P5
commit); 30,660 files in `data/cache/lightkurve`; 506 FITS / 266 MB in
`data/cache/audit_lightkurve`; `pytest tests/ -q` 305 passed, 1 skipped,
143 s. End state: 305 passed, 1 skipped; **nothing under `src/` or `tests/`
changed** (`git status --short src tests` empty).

Evidence tags: [M] measured this session, [P4]/[P5] taken from those prompts,
[A] an adopted threshold or assumption. The pipeline finds candidates;
nothing here is a detection and nothing was submitted anywhere.

## Result in one line

**Clean null. 405 -> Stage A 7 -> Stage B 6 -> Stage C 0 -> Stage D 0.
SUBMIT 0, HOLD 0, KILL 405; no `ctoi_fields.json` was written and
`docs/packets/audit_p6/` does not exist.** `docs/REVET.md` has the funnel, the
artefact census, every Stage B/C candidate with its numbers, and the statement
of the null with what the census says about the survey's false-positive budget.

The census is the substantive result: **302 of the 405 survivors (75%) lose
their strongest event to a removal rule**, and 2,957 of 8,697 observed epochs
(34%) are removed. The single largest class is the one prompt 5 found in the
top ten — a dip that exists in the corrected flux and not in raw SAP (124
candidates).

## 1. What shipped

* `scripts/audit_p5.py` (modified, no rule or threshold changed):
  * `--out-root` and `--lc-root` are now parameters. The raw per-product
    arrays moved from `data/survey/p5/lc/` to a shared
    **`data/survey/audit_lc/`**, because they are downloaded data, not a
    per-prompt result; P5 records are untouched and still reproduce.
  * new `prepare` sub-command: the detrend/bin/clip half of `tls_step`,
    writing `<key>_lc.npz` plus a counters JSON under `<out-root>/prep/`.
    `tls`, `forced` and `events` all read that one file, so every step sees
    identical preprocessing.
  * new `forced` sub-command: the narrow TLS (+/- 1.5%, oversampling 5) alone,
    written to `<key>_forced.json`; `_ephemeris(source="tls")` reads either it
    or a full `tls` record.
  * `crossmatch` and `ctoi_fields` paths are root-aware
    (`crossmatch_p6.json`, `docs/packets/audit_p6/`); `set_roots` also makes
    the `fit/` directory.
  * `RULES_VERSION` stamped on every record written by `prepare`, `forced`,
    `tls`, `events` and `crossmatch`; `events` now honours it on its cache.
  * `neighbours` uses every survivor depth on the star for the dilution test,
    not only those ranked <= 30 (P5's records used the narrower list).
  * `_tls_summary` serialises a degenerate TLS result (NaN counts) as null
    instead of raising. One candidate needed this.
* `scripts/p6_download.py`: Stage 0 driver, four worker processes, one
  `search_lightcurve` per star, stars ordered by best P4 rank.
* `scripts/revet_p6.py`: the whole funnel. Sub-commands `stageA`, `stageB`,
  `stageC`, `stageD`, `slice`, `one`, `csv`, `funnel`, `census`, `report`,
  `verdict`, `eligible`. Every threshold is a module constant, copied into
  each record. Stages run as N top-level subprocess slices (TLS makes its own
  `multiprocessing.Pool`, so pooled workers cannot host it).
* `docs/REVET.md` (new), `docs/AUDIT.md` section 6 extended with the measured
  size of each recommended change, `.gitignore` for the new large artefacts.
* `data/survey/p6/`: `stageA/` (405 JSON), `stageB/` (7), `stageC/` (6),
  `stageA.csv`, `stageB.csv`, `stageC.csv`, `funnel_p6.json`,
  `census_p6.json`, `report_tables.md`, `download_p6.json`,
  `crossmatch_p6.json`, `stageD_empty.json`, `prep/`, `neighbours/`, `logs/`,
  `validation/`.

## 2. What was measured [M]

* **Stage 0**: 261 stars, 9,292 products (564 SPOC 2-min, 3,490 TESS-SPOC,
  5,238 QLP), **0 failed products**, 4.8 GB, 62 min on four workers. One star
  (TIC 160619012) hung on a stalled MAST read and was killed and re-downloaded
  alone in 33.5 s; two single products failed on transport errors and were
  re-downloaded.
* **Stage A**: all 405 candidates, 147 CPU-minutes (median 17 s per
  candidate), 16 slices. 7 PASS, 398 FAIL, 0 ERROR, all stamped `p6.2`. The
  ephemeris giving the most credit was the forced TLS for 234, the survey's
  for 163, the P4 packet refit for 8. Failures: kept depth outside 0.5-2x the
  survey depth 359, SNR without the top event < 5 356, kept SNR < 7 345, top
  event > 50% 251, depths inconsistent 75, fewer than 3 kept events 52.
  24 candidates fail exactly one criterion; 18 of those fail only depth
  consistency, at kept-event SNR 8 to 686 (eclipsing binaries and rotating
  stars, not noise).
* **Stage B**: 7 candidates, 5 stars, 2.6 min. 6 PASS, 1 FAIL. All six
  passers carry star-level flags, so none could have exceeded HOLD.
* **Stage C**: 6 candidates, 4 stars, 29 min at oversampling 3 (fewer than 40
  stars reached the stage). **0 PASS.** The blind peaks are 101.62, 79.97,
  0.9865, 9.585, 86.06 and 9.585 d against survey periods of 16.56, 65.03,
  44.89, 13.42, 76.06 and 14.04 d. The closest miss is rank 325
  (TIC 219419204): SDE 12.9 within 1% of its survey period, but only the
  second-strongest peak.
* **Artefact census over all 405** (chosen ephemeris; the survey ephemeris
  gives the same picture): strongest event kept 103, carried by a class 302.
  Per class, candidates carried / events removed: dip absent in SAP 124/164,
  SAP baseline ramp 117/790, PDC gap 93/374, scattered-light flag 88/1103,
  scattered-light ramp 78/1064, momentum dump 43/818, quality-flagged 36/616,
  sector/orbit edge 30/369. Per star: on 183 of 261 stars every survivor is
  carried by a class; on 45 none is.
* **PDC-made dips**: 232 sector/camera/CCD/product combinations, 467 events,
  sectors 1 to 105. TESS-SPOC 356 events, SPOC 68, QLP 43; cameras 3 and 4
  carry 73%; 291 of 467 in sectors 56 and later. Worst sectors 85, 75, 74,
  84, 67.
* **Binary hosts**: 109 of 405 candidates sit on a star with another accepted
  candidate at >= 30 ppt or >= 5x their depth; on 69 the deep events are
  inside the candidate's own search data.
* **Hard stop**: the six catalogs re-downloaded 18:04-18:08 UTC (262 s); all
  five Stage A survivor stars CLEAN.
* **Driver validation against prompt 5** (records in
  `data/survey/p6/validation/`): the refactored `prepare` reproduces P5's
  counters exactly (225,663 unbinned, 35,622 binned, 1/2/0 clips, threshold
  19.47 ppt); `forced` reproduces P5's ephemeris exactly (46.84166 d, T0
  1687.6053, SDE 3.71) and is identical at 1, 4 and 8 threads; the three P5
  `events` records are byte-identical under the survey, packet and TLS
  ephemerides; Stage B reproduces P5's two phase-independent exclusions
  (TIC 212261364 sector 27, TIC 290350156 sector 1) and Stage C reproduces
  P5's blind TLS for TIC 212261364 (12.25285 d, SDE 10.3).

## 3. What was refuted [M]

* **That the survivor list below the top ten holds a recoverable signal.**
  None of the 405 is re-detected by a blind TLS at its own period. The seven
  that pass the per-event test are, on the evidence of section 5 of
  `docs/REVET.md`, a catalogued contact eclipsing binary (TIC 188830181, VSX
  EW, SIMBAD EB\*), a catalogued rotational variable (TIC 201247574, Gaia
  VARIABLE / SOLAR_LIKE, VSX ROT), and three candidates on two stars whose
  Gaia astrometry is not that of a single object (TIC 219419204 RUWE 3.17,
  excess-noise significance 202; TIC 43668893 RUWE 11.60, significance 1560,
  `non_single_star` set).
* **That the frozen ranking orders the surviving evidence.** The P4 rank
  correlates with the number of Stage A criteria passed (Spearman rho = -0.37,
  p = 9e-15) but not at all with the kept-event SNR (rho = -0.065, p = 0.19,
  n = 405). The seven Stage A survivors sit at ranks 16, 98, 250, 279, 289,
  325 and 398.
* **That the PDC-made dips are a handful of sectors.** Prompt 5 named five;
  the full population gives 232 sector/camera/CCD combinations across the
  whole mission.
* **Not refuted**: P4's expectation of about 2.2 new signals (low 3.3, high
  1.1). Zero is inside that range, so this null does not by itself show the
  survey is broken.

## 4. Assumptions the verdicts rest on [A]

1. Every threshold is stated once in `docs/REVET.md` section 2 and was applied
   identically to all 405 by one code version (`p6.2`, in every record).
2. "The ephemeris that gives the candidate the most credit" is operationalised
   as the one passing the most of the six Stage A criteria, ties broken by
   kept-event SNR.
3. The Stage B window test uses `expected_t14_hours` as specified. Where the
   survey's box duration is shorter, a T14-long window measures a shallower
   dip; every Stage B record carries the same measurement at the survey
   duration and a per-sector margin so the effect is auditable.
4. A 2:1 or 1:2 alias would have needed TLS per-transit depths consistent at
   p >= 1e-3; no candidate reached that branch.
5. Gaia flags, deep-event hosts and neighbour dilution flag but never kill.

## 5. Still open

1. **The one borderline kill is CLOSED** (see section 5 below and
   `docs/REVET.md` section 10). Rank 16, TIC 233007823, is an eccentric
   eclipsing binary. The window question it raised is still open in general
   (a second pass should decide whether the Stage B window is T14 or the
   fitted duration), but it no longer hangs over any candidate.
2. **The depth-consistency criterion is the binding rule for real signals.**
   It removes 75 candidates, 18 of them otherwise clean at kept-event SNR 8 to
   686. It is doing its job on eclipsing binaries and spotted stars, but a
   transit with genuine depth variation from red noise or spot crossings fails
   it too. Worth re-deriving with a red-noise-inflated error before it is used
   as a survey gate.
3. **Test (i) has no power above about P = 17 d.** A TESS sector spans ~25 d,
   so five of the seven Stage B candidates had zero testable sectors. Most of
   the survivor list (median period 58 d) can never be excluded this way; a
   long-period equivalent is needed.
4. **The wotan window absorbs part of the transit.** Every clean signal in the
   population comes back at 0.5-0.9 of its survey depth, so the Stage A window
   of 0.5-2x is generous on one side and tight on the other. A second pass
   should either detrend with the transit masked or widen the window's lower
   bound deliberately, with the reason recorded.
5. **TIC 188830181 is an uncatalogued eclipsing binary** (SIMBAD EB\*, VSX EW,
   blind TLS 0.98650 d at SDE 17.3 with 85 transits) that is absent from the
   TESS EB catalog and every SPOC TCE list, like prompt 5's TIC 167304394. A
   human may wish to report both to an eclipsing-binary catalog. Neither is a
   CTOI.
6. **The `fit` sub-command is still untested code.** Nothing reached a verdict
   that needs it, so it was never exercised. Same for `write_ctoi_fields` and
   `revet_p6.py verdict`.
7. **The audit code is a script with no unit tests.** Porting the event rules
   into `src/tesshunter` with tests remains the first step of a second survey
   pass (`docs/AUDIT.md` section 6, change 1).

## 5b. Rank 16 resolved after the P6 commit [M]

The one borderline decision in the funnel was re-analysed on its own
(`scripts/rank16_analysis.py`, `scripts/secondary_scan.py`,
`data/survey/p6/rank16/`, `data/survey/p6/secondary_scan.json`).
**TIC 233007823 is an eccentric eclipsing binary, not a planet candidate.**

* Folding the whole baseline and scanning **every** phase returns exactly two
  dips above 5 sigma: the primary at phase 0.9996 (2.637 +/- 0.048 ppt,
  55.4 sigma) and a **secondary at phase 0.6048 (2.505 +/- 0.048 ppt,
  52.0 sigma)**. Nothing else.
* The secondary is real, not a flux-correction artefact: **2.516 +/- 0.044 ppt
  in raw SAP**, 42 kept events after every removal rule, median 8.4 sigma per
  event, epochs at integer multiples of the same period to 0.006 cycles over
  63 cycles.
* It is **0.950 +/- 0.026 times the primary depth**. The deepest secondary a
  planet could make at this period (a/R\* 27.0, T_eq 780 K) is 1.08e-3 ppt
  (thermal plus reflected). The measurement is **2,312 times that bound**.
* The pair is consistent as one eccentric orbit: phase offset +0.1052 gives
  e cos(omega) = +0.165, the duration ratio 1.05 h / 1.80 h gives
  e sin(omega) = -0.263, together e = 0.31, omega = -58 deg.
* Depths of only 2.6 ppt for near-equal eclipses require ~100x dilution;
  four Gaia neighbours within 3 px are bright enough, the nearest at
  14.6 arcsec (0.70 px, delta-G 4.73, 12.7 ppt if totally eclipsed).

**Two corrections to the record.** (a) The borderline Stage B kill was not
load-bearing: the blind TLS, run afterwards, gives a strongest peak of 75.58 d
at SDE 15.0 and only SDE 8.38 within 1% of the survey period, so Stage C would
have failed it too. (b) **The funnel has a real blind spot: no stage searched
for a secondary eclipse, and the P4 packets tested only phase 0.5.** This
secondary is at 0.605, so both were blind to a 52-sigma feature. A full-phase
secondary scan costs seconds per candidate and belongs in any second pass, as
a gate ahead of the expensive stage.

Running the same scan over all seven Stage A survivors: rank 16 is the only one
with a quiet scan (2 dips). Rank 98 has 2 dips but the second is only 5.7 sigma
on a catalogued rotational variable, so no claim is made. The other five
(ranks 250, 279, 289, 325, 398) show 14 to 41 dips at scattered phases, i.e.
the scan is measuring stellar variability, which is its own comment on how
transit-like those signals are and is consistent with all six failing the
blind TLS.

## 6. Files

* `scripts/audit_p5.py` (modified), `scripts/p6_download.py` (new),
  `scripts/revet_p6.py` (new), `scripts/rank16_analysis.py` (new),
  `scripts/secondary_scan.py` (new).
* `docs/REVET.md` (new), `docs/AUDIT.md` (section 6 extended),
  `HANDOFF_P6.md`, `.gitignore`.
* `data/survey/p6/`: `stageA/`, `stageB/`, `stageC/`, the three CSVs,
  `funnel_p6.json`, `census_p6.json`, `report_tables.md`, `download_p6.json`,
  `crossmatch_p6.json`, `stageD_empty.json`, `prep/`, `neighbours/`, `logs/`,
  `validation/`, `rank16/`, `secondary_scan.json`.
* Git-ignored, reproducible from MAST: `data/survey/audit_lc/` (4.8 GB of
  per-product arrays, 261 stars), `data/survey/p6/tls/*.npz` (detrended
  arrays and TLS spectra), `data/survey/p6/events/` (the per-ephemeris
  intermediates, reproduced per event with their removal reasons inside every
  Stage A record).

## 7. Re-running

```
py = C:/Users/seanj/Downloads/tesshunter_venv/Scripts/python.exe
$py scripts/p6_download.py 4                      # Stage 0, ~62 min
$py scripts/revet_p6.py stageA --slices 16 --threads 1
$py scripts/revet_p6.py stageB --slices 1
$py scripts/revet_p6.py stageC --slices 3 --threads 8 --oversampling 3
$py scripts/revet_p6.py stageD                    # empty while Stage C has no PASS
$py scripts/revet_p6.py census; $py scripts/revet_p6.py funnel; $py scripts/revet_p6.py report
$py scripts/rank16_analysis.py fold                   # the rank-16 resolution
$py scripts/rank16_analysis.py events --phase 0.0    --label primary
$py scripts/rank16_analysis.py events --phase 0.6048 --label secondary
$py scripts/rank16_analysis.py shape; $py scripts/rank16_analysis.py blend
$py scripts/secondary_scan.py                         # the same scan over all seven
```

Every stage is idempotent: a settled PASS/FAIL record short-circuits, an ERROR
or a missing star is retried on the next run, and a `RULES_VERSION` bump
re-runs the whole chain.
