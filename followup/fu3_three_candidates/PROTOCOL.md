# FU3 frozen analysis protocol: TIC 270573718, TIC 262843927, TIC 193718989

Version 1.0, frozen 2026-10-18 (UTC) **before** any sector > 98 (or any other sector not used by the
discovery search) is downloaded or inspected for these targets, and before any candidate-specific threshold is
tuned. The SHA-256 of this file is recorded in `manifests/protocol_freeze.json`. Any later change is an
amendment: a new dated section at the end of this file with its reason, and a new hash. Earlier text is never
edited.

## 0. Scope, inputs, outputs

* Targets: TIC 270573718 (P ~ 41.3837 d), TIC 262843927 (P ~ 24.1089 d), TIC 193718989 (P ~ 24.5329 d).
* Read-only inputs (hashed in `manifests/input_manifest.csv`): the S1 survey store, search, funnel and packet
  products under `D:\tesshunter_s1`; the discovery code at repo commit df39814a9 (branch `s1/survey`); the
  batch-1 deep-vetting bundle (`Codex\2026-10-18\do-an-in-depth-analysis-of`) and the seven-candidate
  continuation bundle (`Codex\2026-10-18\continue-the-seven-candidate-tess-analysis`).
* The 22-page report "THREE TESS CANDIDATES / Further archival constraints" was NOT found on this computer
  (searched Downloads, Documents, Desktop, D:). Its claims are taken only from the user's prompt and are
  labelled "prompt-stated, source unavailable" wherever used.
* All new code, tables, figures and the report live under `Documents\TESS_followup_262_193_270`; large
  downloads under `D:\tess_fu3_cache`. No input file is modified.
* The S1 survey (batch 2) is running on this machine. FU3 uses at most 6 concurrent CPU workers and at most 4
  concurrent MAST/TESScut requests, and never touches `D:\tesshunter_s1` except to read.

## 1. Reference ephemerides (frozen)

For each target the reference ephemeris is the discovery packet's adopted fit (`fit.json` `adopted`:
P, T0 in BTJD = BJD_TDB - 2457000, T14), copied into `results/s00_provenance_<tic>.json`. All times are
BTJD_TDB. Ground data are converted from their native system (MJD_UTC, HJD, Gaia TCB) to BJD_TDB at the
observatory before folding.

A conditional timing covariance is reconstructed in s03 from per-event mid-times measured on the
discovery-data products only (sectors <= 98, the products used by the search), by weighted linear least
squares with per-event errors inflated by sqrt(max(1, chi2_red)). This covariance and the resulting
predictions for every later epoch are written to `results/s03_ephemeris_<tic>.json` before any later-sector
data are opened. Prediction windows for new data use the +/-3 sigma propagated timing envelope.

## 2. Data tiers and independence

* D-orig: the exact products the discovery search used (TESS-SPOC PDCSAP and QLP det_flux, sectors <= 98).
* D-alt: other pipeline reductions of the same FFI/TPF photons (TESS-SPOC SAP, QLP SAP, SPOC 2-min, TGLC,
  GSFC-ELEANOR-LITE, TASOC, TARS) and FU3's own TESScut extractions. These are sensitivity tests. They are
  never counted as independent detections.
* D-new: TESS data from sectors not used by the discovery search (sector > 98 or a sector absent from the
  discovery store), and any non-TESS time series. Only D-new can provide an independent recurrence test.
* A retrospective split of D-orig (early versus late) is not independent confirmation, because event
  identities and the period alias were selected on the full data set.

## 3. Event admission and measurement (common to every reduction)

* Admission is by coverage only, never by fitted sign or depth. An event is admitted when, after the
  product's quality mask (bitmask 'default' for SPOC/TESS-SPOC; QLP quality != 0 removed) and removal of
  non-finite values, (a) at least 50% of the predicted in-transit interval [tc - T14/2, tc + T14/2] has
  cadences, (b) the in-transit interval has >= 3 points after binning to max(native cadence, 10 min), and
  (c) each side of the event has >= 4 binned points within 3*T14 (capped at 0.4 P) of tc.
* Every admitted event is measured; failed, negative or zero measurements are kept in the tables.
* Model: local baseline polynomial (degree 1 primary, degree 2 sensitivity) times a fixed-shape transit
  template from the adopted fit (batman, quadratic limb darkening from the packet, supersampled to the
  product exposure). The free amplitude is the depth scale; the fitted quantity reported is the depth at
  mid-transit in ppt.
* Errors: white scatter of the out-of-transit residuals, inflated by the time-averaging beta factor
  (residual rms in bins of T14/3 versus white expectation, beta >= 1). Event-to-event excess scatter is added
  when pooling (chi2_red > 1 inflates the pooled error by sqrt(chi2_red)).
* Pooled statistics: inverse-variance mean, chi2 against a constant depth, fraction of positive events,
  leave-one-sector-out influence, and the share of total S/N^2 carried by the strongest event.
* Systematics context for each event: distance to the nearest data-segment edge (gap > 0.5 d), momentum
  dumps (quality bit 32/5) within T14, scattered-light flags, background level relative to the sector
  median, and pixel-centroid motion.

## 4. Timing

* Per-event mid-times: profile likelihood over a +/-1.0*T14 grid (step <= 2 min) with the depth scale and
  baseline re-optimised at each trial time; 1-sigma interval from delta chi2 = 1 after beta inflation;
  multimodal or edge-truncated profiles are flagged and their interval is the full region with delta chi2 < 1.
* O-C against the reference ephemeris; linear refit; quadratic and two-segment alternatives.
* A timing variation is claimed only if (a) a non-linear model improves chi2 by >= 11.8 (3 sigma, 2 extra
  parameters) after per-event error inflation, (b) the same sign pattern appears in at least two
  reductions with different photometric extraction (D-orig plus one D-alt), and (c) it survives
  leave-one-sector-out. Otherwise "not established".

## 5. TIC 270573718 contradiction (first priority)

1. Reproduce the continuation's 0.29 (corrected) and 8.19 (aperture) values exactly from its code and inputs.
2. Decompose: event sets, early/late split membership, early-fit epoch/period corrections, extrapolated
   shifts, each late event's contribution, leave-one-sector-out and leave-one-event-out influence on the
   early-predicts-late S/N, and the same statistic on a common event set and common split for both series.
3. Trace each event to FITS product, sector, camera/CCD, cadence, flux column, quality mask, CROWDSAP /
   FLFRCSAP (TESS-SPOC) or QLP dilution correction, background, detrending window.
4. Predeclared fresh TESScut extractions for every sector with an admitted event: circular apertures of
   radius 1.0, 1.5 and 2.0 px on the propagated Gaia position; a neighbour-excluding aperture (pixels where
   the predicted target PRF fraction of the total catalogued flux is >= 0.5); backgrounds = annulus median
   (5-9 px, catalogue sources G < 18 masked) and a fitted linear sky plane; and a PRF scene fit (all Gaia
   sources with G < G_target + 6 within 90 arcsec, positions fixed, fluxes free per cadence plus a sky plane)
   where the out-of-transit scene residual rms is <= 0.1 of the target peak. Failing extractions are kept in
   the table with their failure reason.
5. Injection/recovery before normalisation and detrending: the adopted transit model scaled to the D-orig
   depth is injected into (a) the pixel cubes as a PRF-shaped flux loss at the target position, at the real
   event epochs shifted by +/-3, +/-5 and +/-7 T14 (12 injections per sector, using out-of-transit phases),
   and (b) the PDCSAP/QLP flux before the survey's biweight (window 0.75 d) at the same shifted epochs.
   Recovery fraction = recovered/injected depth. Negative controls: the same measurement at >= 200 random
   out-of-transit epochs per target per reduction gives the empirical single-event null distribution.
6. Twice-period binaries near 82.7674 d: equal-depth twins, free unequal depths (odd/even), eccentric
   secondary at free phase, and third-light dilution; half-phase (P and 2P) secondary measurements in every
   reduction; global phase scan p-value from 500 sector-preserving phase shifts.
7. Classification (decided by the rules, not by preference):
   * (i) likely processing artefact: the dip is absent (pooled depth < 2 sigma above zero) or inconsistent
     (> 3 sigma below the D-orig depth) in at least two target-centred raw-pixel extractions over the same
     events, OR the negative-control epochs produce single-event depths >= the median event depth at a rate
     > 10% in the reduction that carries the signal, OR the events sit preferentially on segment edges /
     momentum dumps (binomial p < 0.01 against the duty cycle).
   * (ii) persistent astrophysical dip, host unresolved: not (i), and the dip is present at a consistent
     depth (constant-depth p > 0.001) in at least two independent raw-pixel extractions, but host attribution
     or the binary alternatives are not resolved.
   * (iii) planet-favoured: (ii) plus target attribution robust to PRF family, aperture and baseline choice
     for every neighbour able to produce the depth, plus all 2P / eccentric / diluted EB alternatives
     disfavoured by delta chi2 >= 10 relative to the planet model in the corrected and one raw reduction.

## 6. TIC 262843927

* Sectors 31 and 88 (continuation "gross failures"): determine the cause from cutout geometry (target
  position relative to the CCD edge, gaps, the S31/S88 camera/CCD), WCS, scene, background and quality
  flags. Salvage only with the predeclared apertures of section 5.4 and only if the scene criterion passes.
  A failed repair stays excluded; it is never counted as a non-detection.
* NFPP = 0 audit: reconstruct TRICERATOPS's neighbour admission (the flux fraction / depth test it applies)
  and recompute with the actual aperture and PRF throughput; build the contamination map down to the Gaia
  completeness limit for the field and the stated limits of available archival images.
* 2P ~ 48.2179 d equal twins and the phase-0.387 feature: the earlier p = 0.493 stands unless a corrected
  analysis with a stated reason replaces it.
* Radius / duration / impact parameter: profile-likelihood fits with stellar-radius and density priors,
  exposure integration, eccentricity marginalised under a stated prior, and the smallest stellar / brown-dwarf
  blend family that fits.

## 7. TIC 193718989

* 9.8-arcsec neighbour: required eclipse depth with the actual TESS PRF and aperture throughput in each
  sector and a TESS-band flux ratio from Gaia BP/RP colours (not RP alone).
* ZTF: all accessible detections with flags, predicted in-event windows from the s03 covariance, censoring
  where non-detection metadata are not available; if forced photometry is not accessible, no stronger
  exclusion is claimed. Report the fraction of the depth-duration space of the 74%-eclipse model excluded.
* Corrected (4.91) versus aperture (2.31) retrospective S/N: decompose as in section 5.2.
* 2P ~ 49.0658 d twins, eccentric grazing (e ~ 0.836), hierarchical/background configurations, with
  eccentricity and tidal-survival priors stated explicitly.

## 8. Discovery-selection calibration (bounded)

* Faithful replay: the frozen search worker (`search_worker_k1.py`, preset survey_k1, 8,100 s budget) and
  the frozen pre-gate and Stage A on sign-inverted light curves (flux -> 2 - flux) of the three targets and of
  matched control stars from S1 batch 1 (same slice, Tmag within 0.5, usable sectors within +/-30%), plus
  injections of each candidate's signal (depth, T14, P) into the matched controls.
* Hard budget: 24 CPU-hours total, at most 4 concurrent workers; control counts fixed now: 3 inverted
  targets + 24 inverted controls + 24 injected controls (8 per candidate). No extension if the result is
  unfavourable or uninformative. If the budget is exhausted, the partial result is reported with its count.
* This calibration does not reproduce: the human/Codex review that chose seven of 23 SUBMIT/HOLD candidates,
  Stage B/C/D, or batch-to-batch adaptive choices. These are stated as uncovered.
* 2P searches: a fixed-period-grid BLS/TLS between 40 and 100 d (TIC 262843927, TIC 193718989) and 60 and
  130 d (TIC 270573718) on the corrected and one raw reduction; reported as targeted searches, not as part
  of the original survey.

## 9. Archive census

Outcome codes for every archive x target: DATA_WITH_TRANSIT_COVERAGE, DATA_NO_TRANSIT_COVERAGE, NO_DATA,
ACCESS_FAILED (with status/response), NOT_APPLICABLE. Matching of catalogued objects requires coordinate
agreement after proper-motion propagation (<= 2 arcsec for Gaia-precision catalogues, <= 1 TESS pixel for
TESS catalogues) and, for periodic-signal catalogues, period agreement within 1% at P, 2P or P/2 and epoch
agreement within 3 sigma. A failed endpoint, an incomplete catalogue or an observation without transit-phase
coverage is never turned into a negative scientific result.

## 10. New epochs (D-new)

* Use the pipeline product if one exists (QLP / TESS-SPOC / SPOC); otherwise a TESScut extraction with the
  1.5-px aperture of section 5.4 and annulus background (fixed now, not tuned on the new data).
* Statistic: pooled depth at the frozen s03 ephemeris; the timing is profiled within the +/-3 sigma
  envelope and the look-elsewhere effect of that profile is calibrated with the same profile at >= 200
  random out-of-transit epochs in the same sectors.
* Outcomes: DETECTED (calibrated p < 0.01 and depth consistent with D-orig within 3 sigma), INCONSISTENT
  (depth > 3 sigma below the D-orig depth with recovery >= 80% in injections at the same epochs),
  INCONCLUSIVE (otherwise), NO_COVERAGE.

## 11. Probabilities and reporting

* TRICERATOPS FPP = 1 - (TP + PTP + DTP); STP/BTP/NTP-family scenarios are false positives for the named
  host. Report target-host planet weight (TP + PTP + DTP) and any-host planet weight (adds STP, BTP, NTP)
  separately; never call FPP the probability that no planet exists.
* Image-localization scores, FPP and the shared SED are not multiplied as independent likelihoods. Repeated
  reductions of the same photons are not counted as independent.
* If no defensible calibrated posterior exists, report scenario-survival bounds (which scenarios survive at
  delta chi2 < 10 / are excluded only under named assumptions).
* Qualitative confidence levels: HIGH / MODERATE / LOW / VERY LOW, with the assumptions each depends on;
  no invented percentages.

## 12. Stopping rules

* Each branch stops when (a) its predeclared tests are complete, or (b) a predeclared test is blocked by data
  access (recorded), or (c) its compute budget is exhausted (recorded).
* "Diminishing returns" is declared for a question when the remaining public-data tests can only re-reduce the
  same photons and the preceding re-reductions changed the answer by less than its stated uncertainty.

## Amendment A1 (2026-10-18 ~21:25 UTC, after freeze; no threshold or test changed)

1. The 22-page report "THREE TESS CANDIDATES / Further archival constraints" WAS found after the freeze, at
   `C:\Users\seanj\.claude\tess_three_audit\output\pdf\TESS_three_candidate_archival_constraints.pdf`
   (2,154,824 bytes, 2026-10-18 14:11 local), with its bundle in `C:\Users\seanj\.claude\tess_three_audit`.
   It was read in full. It concerns TIC 382098683, 188830138 and 201247574 (the current top-three tier), not
   the three FU3 targets. Section 0's "not found" statement is superseded; that bundle is added to the
   read-only inputs.
2. Added D-alt reductions (tests added, none removed): TGLC light curves for sectors 12-55 obtained by streaming
   MAST's per-sector TGLC target lists (that report documents that MAST Portal/API indexing can omit them),
   for every FU3 sector where they exist; and a free-shape (trapezoid, free T14 and ingress) timing
   cross-check of every event in addition to the fixed-template profile of section 4.
3. Timing-error calibration (section 5.5 injections) is applied per cadence group (1800 / 600 / 200 s) and
   per reduction; the O-C significance of section 4 is reported both with formal and with
   injection-calibrated errors (adopted-shape and grazing-shape calibrations). The section-4 claim rule is
   unchanged and is applied to the calibrated errors.

## Amendment A2 (2026-10-18 ~22:50 UTC, after the section 4-5 results were seen; recorded as post-hoc)

These are additions and corrections made after results were seen. None changes a threshold of sections 4-5;
each is reported as post-hoc.
1. Added test (post-hoc): an empirical null for timing structure (s16_ttv_null.py). Strictly periodic copies of
   the adopted transit are injected at 24 shifted phases into the same light curves (real transits masked) and
   timed with the identical method. Two statistics are compared with the observed ones: the season-offset
   delta chi2 (formal errors) and a coherence statistic, max |median O-C| over seasons with >= 4 events. The
   section-4 claim rule is unchanged; this null is reported alongside it, not substituted for it.
2. Correction: the s07c neighbour list originally kept only Gaia sources with G < G_t + 6 within 4 px. It
   silently dropped TIC 193718989's 9.8-arcsec G = 19.6 neighbour, which section 7 names. Every Gaia source
   within 2.5 px is now tested regardless of brightness, and sources outside the scene model get an RP-ratio
   catalogue flux. Earlier outputs are kept as *_run1_Gcut.json and *_run2.json.
3. Correction: the first s15 Gaia-RV limit used P(p_sim >= p_obs). That is undefined when p_obs is in the upper
   tail under K = 0 (TIC 262843927, p = 0.977). It is replaced by the relative statistic
   R(K) = P(chi2 <= chi2_obs | K) / P(chi2 <= chi2_obs | K = 0).
4. The TTV/shape interplay test (s11 'season' mode, per-season timing offsets as nuisance parameters in the
   shape fit) is an added sensitivity analysis, reported for all three targets.

## Amendment A3 (2026-10-18 ~23:55 UTC, while the s08 replay was running; post-hoc where stated)

1. Post-hoc variant: the unbounded free-shape timing fit (A1) latched onto outliers in the unclipped FU3 pixel series
   (S1: 25 ppt over 1.1 h, at the duration bound). A bounded variant was added and run on PDCSAP and the pixel series:
   depth 0-3x adopted, T14 0.6-1.6x adopted, isolated > 5-sigma points (1-h running median) removed from each window.
   Both the unbounded and bounded results are reported; no threshold of section 4 changes.
2. Descriptive, read-only: the discovery funnel of S1 batch 1 (stage decisions per candidate and per star, and every
   pre-gate candidate of the three targets with its fate) is tabulated from the survey's own receipts (s08b).
3. Replay reporting (decided after 5 of 51 searches had finished, before any injected search ran): per-group Stage A
   pass counts with one-sided 95 % Clopper-Pearson upper limits on the per-star rate (inverted), recovery fractions
   through the pre-gate and Stage A with 68 % Clopper-Pearson intervals (injected), and the matched candidates' stitch
   S/N against the real candidate's discovery stitch S/N.  The frozen job order and budget are unchanged: the
   remaining work was estimated at about 19 CPU-h against 21 CPU-h left, so no reordering was needed.
## Amendment A4 (2026-10-19 ~00:50 UTC, at the user's request; added test, post-hoc)

1. Added test: over-luminosity for colour (s22_cmd_luminosity.py). Each target's absolute magnitude is compared with
   the single-star ridge (KDE mode of a clean subsample: RUWE < 1.2, non_single_star = 0, ipd_frac_multi_peak = 0)
   of Gaia DR3 stars within 100 pc (parallax/error > 20, 1.6 <= BP-RP <= 2.6, |C*| < 3 sigma), in M_G vs BP-RP,
   M_G vs G-RP, M_Ks vs BP-RP and M_Ks vs G-Ks (2MASS Ks quality A via the DR3 best-neighbour cross-match). Reported:
   the offset, the fraction of clean stars at the target's colour (+/-0.05 mag) that are at least as bright, and
   the fraction faint enough to be half of an equal-mass pair. The sample was queried in five colour slices
   because a single query was truncated at exactly 50,000 rows; that truncated cache is kept as
   gaia100pc_early_m_TRUNCATED50k.ecsv and was not used for any reported number.