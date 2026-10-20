# HANDOFF P3: submission-grade vetting

Date: 2026-09-02. Branch `improve/recovery`. Environment as in `CTOI_PROMPTS.md`
(double-nested repo path, `tesshunter_venv` Python 3.13, lightkurve 2.6.0,
numpy 2.5.1, batman 2.5.3, numba 0.67).

Session start state, measured [M]: `git status` clean; 11,536 files in
`data/cache/lightkurve` (the P2 prefetch); `pytest tests/ -q` 265 passed,
1 skipped, 53 s. The tree was healthy.

Evidence tags: [M] measured in this session, [A] adopted assumption,
[R] refuted or unavailable. The pipeline finds candidates; nothing in this
document is a detection.

## Summary

| item | before (P2) | after (P3) |
|---|---|---|
| dev benchmark (24 planets), recovered / alias / missed / FP | 17 / 2 / 5 / 12 | 19 / 2 / 3 / 8 (TRAPPIST-1 e and f gained; no recovery lost) |
| dev mean depth error, planets recovered in both (17) | 13.02% | 10.29% |
| dev mean depth error, all recovered | 13.02% (17) | 22.54% (19; the two K2 gains carry 96% and 157%) |
| holdout (6 planets), recovered / alias / missed / FP | 4 / 0 / 2 / 8 | 4 / 0 / 2 / 8 |
| verdict mislabels, dev / holdout | 0 / 1 | 0 / 0 |
| adversarial: known planets promising / ambiguous / FP (n = 18) | not measured | 9 / 9 / 0 |
| adversarial: eclipsing binaries reaching "promising" (n = 18) | not measured | 0 (16 likely FP, 2 ambiguous) |
| adversarial: blends reaching "promising" (n = 22) | not measured | 0 (12 likely FP, 4 ambiguous, 6 not detected) |
| test suite | 265 passed | 305 passed, 1 skipped, network-free |

What shipped: a limb-darkened transit fit with a profile-likelihood
stellar-density test and a density prior (Part A); TRICERATOPS FPP and
NFPP with the real TIC / Gaia neighbours and every raw output kept (Part B);
the period-aware secondary-eclipse test, the alias resolver's odd/even
re-test at P and 2P, fit-based gate-6 anchors and gate 7's second condition
(Part C); a one-page packet per survivor with `ctoi_fields.json` (Part D);
and the 58-target adversarial harness (Part E). Measurement changed the
design nine times on the way (section "What was refuted"); the two that
matter most for prompt 4 are that TRICERATOPS's FPP is unstable on
inflated giants and some M dwarfs (Part B) and that the P0 centroid module
cannot separate planets from blends by significance on bright stars
(Part E). NFPP and the a/R* test were the stable discriminants.

## Environment changes (not repo code)

* TRICERATOPS 1.1.0 and pytransit 2.9.1 were installed into
  `tesshunter_venv` with their dependency chains (arviz, emcee, corner,
  seaborn, mechanicalsoup, pyrr, meepmeep, pyopencl, pytools, siphash24,
  xarray, tables and the rest). One dependency could not be built:
  `celerite` 0.4 needs MSVC on Windows and has no Python 3.13 wheel [M].
  pytransit imports it unconditionally in its `lpf` sub-package although
  TRICERATOPS only uses `pytransit.QuadraticModel`, so a three-file import
  shim (`celerite/__init__.py`, `terms.py`, `solver.py`, every class raising
  ImportError when instantiated) was written into
  `tesshunter_venv/Lib/site-packages/celerite/`. Nothing in this repo or in
  TRICERATOPS touches celerite at run time; the shim exists so the import
  succeeds. It is recorded here because a fresh venv will need it again (or a
  compiler).
* The Claret (2017) TESS limb-darkening tables were fetched from Vizier
  (`J/A+A/600/A30`, tables 25 and ab) and reduced to solar metallicity under
  `data/limb_darkening/` (committed, 56 kB).

## Part A: physical transit fit

### What shipped

`src/tesshunter/transit_fit.py` (new), `src/tesshunter/limb_darkening.py`
(new), `src/tesshunter/stellar.py` (new).

* **Model.** batman quadratic limb-darkened transit, circular orbit,
  exposure-time integration (3, 5 or 7 sub-samples for cadences above 4, 12
  and 22 minutes), coefficients interpolated in (Teff, log g) from the Claret
  2017 ATLAS table (Teff >= 3500 K) or PHOENIX table (below), with the
  survey's coarse anchors as the fallback when the tables are missing (the
  fit records which was used).
* **Fit.** Bounded least squares (scipy `trf`) over epoch, period, Rp/R*,
  ln a/R*, impact parameter and baseline, in a window of +/- 3 durations
  around every transit of the all-transits-masked, unbinned flatten (the
  product P2's depth re-measurement already built). Three starts in
  (b, a/R*); among starts within delta chi2 < 1 the least grazing wins.
  Uncertainties from the Jacobian covariance scaled by the reduced chi2;
  derived quantities (T14, T23, maximum and duration-averaged depth, Rp in
  Earth and Jupiter radii with the TIC radius error, stellar density) by
  Monte-Carlo propagation. `mcmc=True` runs emcee from the least-squares
  solution and reports posterior medians and 16-84% half-widths; the
  pipeline uses least squares, the packet script can ask for emcee.
* **Stellar density test.** Every star with a catalog density (TIC `rho`,
  or mass and radius, or radius alone with M ~ R [A]) gets two fits: free,
  and with a/R* confined to the catalog value's 3-sigma range. The profile
  delta chi2 between them, divided by the square of a Winn (2008) red-noise
  beta measured on the residuals, is the consistency statistic:
  `a_rs_inconsistent` when it exceeds 9 AND the free-fit density differs
  from the catalog density by more than a factor 3. When the data cannot
  reject the catalog range (delta chi2 < 9) the constrained solution is
  adopted for the reported parameters (the usual density prior) and
  `density_prior_adopted` says so; the free solution is always kept in
  `free_*`. A covariance-based sigma is reported but not used for the flag:
  measured on synthetic injections, the b to a/R* degeneracy let the
  least-squares fit of a 2 R_Earth planet at SNR ~15 land on a grazing
  solution (b = 0.96, a/R* 7 against a true 20) that a covariance test
  called 5.9 sigma inconsistent, while the profile test correctly found the
  catalog range within 1 sigma and the density prior brought Rp/R* from
  0.026 back to 0.021 (true 0.020) [M].
* **Odd/even from the template.** The fitted model, scaled by one linear
  factor per transit, gives a depth per event; parity means use the LARGER
  of the white-noise error and the event-to-event scatter over sqrt(n).
  Flagged at 4 sigma AND 25% of the mean with at least 3 events per parity.
  The empirical error was forced by Pi Men c: on white noise alone its
  parity depths differed by 7.5 "sigma" (0.371 against 0.278 ppt), on the
  event scatter by 1.5 [M].
* **Depth.** The fitted model maximum becomes `depth_ppt`
  (`depth_source = "fit"`) when the fit converged, sees a dip at >= 3 sigma
  (white noise), has Rp/R* < 0.85 and a duration below a quarter of the
  period; otherwise the flat-bottom estimator (`depth_ppt_flat`) and then
  the BLS box (`depth_ppt_bls`) as before. Both the maximum and the
  duration-averaged depth are reported; the reported `depth_err` is the
  statistical error at the fitted shape times the red-noise beta, and
  `depth_err_shape` includes the shape degeneracy.
* **Stellar parameters.** `search_target` looks the star up in the TIC once
  (Teff, log g, radius, mass, density with errors, Tmag, contamination
  ratio, Gaia magnitudes), cached as one JSON per star under
  `data/cache/tic/`, non-fatal, TESS targets with a numeric id only;
  `stellar_params=` accepts a container or dict instead, and the survey path
  passes its `targets_v1.csv` row. `TESSHUNTER_OFFLINE=1` forbids every
  catalog query in the module; the test suite sets it.

### Synthetic validation [M]

batman injections (quadratic LD 0.35/0.25, a solar-type star with M = 1.0
+/- 0.08 and R = 1.0 +/- 0.05, 54-81 day baselines with gaps), started from
a perturbed ephemeris (period +0.03%, epoch +0.2 T14, duration x1.3, depth
x0.8), least squares only unless stated. `tests/test_transit_fit.py` holds
the first four as regression tests.

| case | cadence, noise | Rp/R* fit (true) | a/R* fit (true; catalog) | b fit (true) | T14 fit (true), h | depth fit (true max), ppt | density flag | odd/even | time |
|---|---|---|---|---|---|---|---|---|---|
| hot Jupiter, P 3.3 d | 2 min, 1000 ppm | 0.0798 +/- 0.0005 (0.080) | 10.15 +/- 0.29 (10.0; 9.3) | 0.25 +/- 0.11 (0.30) | 2.613 +/- 0.027 (2.621) | 7.463 +/- 0.029 (7.472) | no | 1.1 sigma | 0.9 s |
| 2 R_Earth, P 7.45 d, SNR ~15 | 2 min, 500 ppm | 0.0207 +/- 0.0028 (0.020) | 19.0 +/- 12.5 (20.0; 16.1), prior adopted | 0.58 +/- 0.76 (0.50) | 2.52 +/- 0.52 (2.53) | 0.472 +/- 0.020 (0.451) | no (delta chi2 < 9) | 0.6 sigma | 0.6 s |
| same, emcee 32 x 600 | | 0.0213 +/- 0.0008 | 16.8 +/- 1.9 | 0.69 +/- 0.09 | | | | | 4.6 s |
| survey star, P 12.1 d | 30 min, 1500 ppm | 0.050 +/- 0.026 (0.050) | 24.6 +/- 67 (25.0; 22.2) | 0.01 (0.20), unconstrained | 3.95 +/- 0.06 (3.81) | 3.01 +/- 0.23 (2.95) | no | 0.9 sigma | 3.5 s |
| grazing, P 2.2 d, b 0.95 | 30 min, 1500 ppm | 0.30 +/- 64 (0.10), unconstrained | 6.8 +/- 2.3 (7.0; 7.1) | 1.20 (0.95) | 1.28 +/- 0.35 (1.35) | 6.73 +/- 0.28 (6.19) | no | 1.2 sigma | 0.7 s |
| diluted eclipse: 20%-deep on a companion, diluted x100 | 2 min | 0.056 | 2.00 (5.0; 8.95) | 0.95 | | | YES: ratio 0.011, delta chi2 2.8e7 | | |
| EB, secondary 40% of primary, folded at P/2 | 10 min | | | | | | | 58.4 sigma at P/2, 0.7 sigma at P | |

Reading: at high SNR every parameter is recovered inside its error; at
survey SNR the fit is honest about what it cannot constrain (b and Rp/R*
errors of order the value, reported as `rp_rs_constrained=False`) while the
depth and duration stay good; the grazing case shows the Rp/R* to b
degeneracy the packet must not hide; the diluted eclipse and the
half-period EB are the two false-positive signatures the fit was built to
expose, and both come out at very high significance.

The synthetic small-planet case before the profile test and the density
prior [M]: the covariance-based sigma called it 5.9 sigma inconsistent
(free fit b = 0.96, a/R* 7.1) and Rp/R* came out 0.026 for a true 0.020;
this is the measurement that replaced the covariance test.

## Part B: false-positive probability

`src/tesshunter/fpp.py` (new) wraps `triceratops.target`: TIC neighbours
within 10 pixels and a TESScut cutout per sector (up to 3 sectors) from
TRICERATOPS itself; the photometric aperture per sector from the SPOC
optimal aperture when the light curve is SPOC, otherwise a circular
aperture of the radius `contamination.estimate_aperture_radius_px` gives
for the target's Tmag centred on the target's pixel position in the cutout
(TRICERATOPS's own 5x5 box as the last resort; the source is recorded); the
phase-folded, detrended curve within +/- 3 durations (at most 6000 points);
the fitted period and the on-target depth with `dilution_corrected=True`.
The Gaia DR3 field-star population TRICERATOPS queries for the blended
scenarios is cached per star under `data/cache/fpp/gaia_background/`
(TRICERATOPS writes it to the working directory, which is switched to that
folder during the call). Raw outputs are kept: `probs.csv` (every scenario
row), `stars.csv` (the neighbour table with flux ratios and the depth each
star would need) and `result.json`, keyed by TIC, period, depth, sectors and
the sampling settings. `FPPResult.blocks_packet` is FPP > 0.5. Cost [M]:
`calc_probs` with 100,000 draws takes 50 s on a 3,000-point fold and 290 s on
20,000 points, plus the TESScut downloads (10-110 MB per sector) and one
Gaia TAP query per star the first time.

### How the folded curve is handed over, and why it matters [M]

TRICERATOPS assumes white noise with one error per point. Three input modes
were built and compared on four known planets (`fold_mode`; 100,000 draws,
SPOC apertures, same fits): `subsample` (up to 6,000 raw cadences within
+/- 3 T14, error = robust scatter), `subsample` with the error multiplied by
the fit's red-noise beta, and `binned` (all cadences binned to T14/25, error
= robust scatter of the binned out-of-transit points, which carries the red
noise at the bin timescale; TRICERATOPS's documented usage).

| known planet | Rp (fit), beta | subsample, white error | subsample x beta | binned T14/25 |
|---|---|---|---|---|
| GJ 436 b (TIC 138819293, M dwarf, 6.4 ppt) | 3.8 R_Earth, 1.5 | FPP 0.999 (STP 0.999) | 0.993 (STP) | 0.997 (STP) |
| WASP-76 b (TIC 293435336, 1.9 R_Sun F star, 13 ppt) | 21.9 R_Earth, 4.4 | 1.0 (PEB 1.0) | 1.0 (EB 0.81, PEB 0.19) | 0.000 (DTP 1.0), 32 s |
| TOI-836 c (TIC 440887364, K dwarf, 1.3 ppt) | 2.5 R_Earth, 4.9 | 1.0 (BEBx2P 1.0) | 0.021 (TP 0.86) | 1.0 (BEBx2P 1.0) |
| HAT-P-59 b (TIC 229400092, 1.5 R_Sun, 10 ppt) | 13.1 R_Earth, 1.0 | 0.978 (EB 0.76, PEB 0.22) | 0.978 (same; beta = 1) | 0.000 (PTP 0.997), 246 s; T14/12 bins: 0.000, 32 s |

(STP: planet around a bound secondary; PEB / DEB / BEB: eclipsing binary
bound / diluting / in the background; PTP / DTP: planet on the target with
a bound or unbound diluting star, which count as a planet.
FPP = 1 - P(TP) - P(PTP) - P(DTP).)

Reading: the binned input is right on two of the four (WASP-76 b, HAT-P-59
b), the beta-scaled sub-sample on one (TOI-836 c) and the white-error
sub-sample on none; GJ 436 b, a bright M dwarf with a b = 0.85 transit,
comes out "planet around a bound secondary" in every mode. Small input
changes flip a whole scenario from ~0 to ~1: the likelihood contrast
between scenarios is enormous compared with the priors and the split is
decided by the noise model, not the star. On the adversarial planets
(Part E) the values are reported as measured and the FPP > 0.5 rule is
applied as the prompt states, with its cost on known planets counted;
prompt 4 should not rank on FPP alone and prompt 5 should treat an FPP
near 0 or near 1 as a statement about the input unless the scenario table
is read. `binned` is the shipped default (the documented input, the best
of the three here, and 5-10x faster); the other two remain available
(`fold_mode=`, `red_noise_beta=`). NFPP, which needs only the aperture
geometry, was stable (0 or ~1e-77 for isolated stars in every mode).

## Part C: the weaknesses

All four changes below ran together through the frozen dev benchmark
(section "Benchmark"); the per-change attribution is from the result files
and notes of that run [M].

### C1: period-aware secondary test (weakness 4) and the alias resolver (weakness 5)

* **Secondary.** `vetting.planetary_secondary_bound_ppt(rp_rs, a_rs, teff)`
  is the deepest secondary an irradiated planet can show: dayside thermal
  emission at `T_day = Teff sqrt(R*/a) (2/3)^(1/4)` (no heat redistribution,
  zero Bond albedo, Planck integrated over 600-1000 nm against the star)
  plus reflected light at geometric albedo 1, at the FITTED a/R* and Rp/R*.
  A measured secondary deeper than twice that bound is a stellar eclipse:
  the flag stacks with any other high-risk flag (and is a hard veto with an
  odd/even mismatch, as before); within the bound the flag is still raised
  (the reader must see the measurement; such a system stays "ambiguous",
  never "promising") but does not stack. The fixed-ratio-plus-radius
  exemption of the improvement report survives only as the fallback when no
  fit is available. Values [M]: WASP-18 b-like (Rp/R* 0.097, a/R* 3.5, Teff
  6226 K) bound 1.14 ppt (thermal 0.37, reflected 0.77, T_day <= 3007 K)
  against a measured 0.07 ppt; the same companion at a/R* 12 (P ~ 5 d) bound
  0.068 ppt, so the 0.5 ppt secondary of a late-M companion that the legacy
  ratio test exempted is now 7 times over the bound and stacks
  (`tests/test_vetting_p3.py`). The degeneracy the report described is real
  and remains at the shortest periods: at a/R* 3.5 an M-dwarf companion's
  own light (~0.5 ppt) sits inside the planetary bound, and the design there
  is unchanged (flagged, not stacked, never promising).
* **Alias resolver.** `bls_search._odd_even_retest` runs on every resolver
  winner (all three return paths, after `_descend_to_fundamental`) when the
  winner has SNR >= 7, at least 4 dip events and a trial at twice its period
  exists: the template odd/even test at P and at 2P; the doubled period is
  chosen only when the parities differ significantly at P and do not at 2P.
  On a synthetic EB with a 40% secondary folded at half its period the test
  reads 58 sigma at P/2 and 0.7 sigma at P and the resolver moves to the true
  period; on a true fundamental it does nothing (`tests/test_gates_p3.py`).
  Cost: one fixed-period fit (~0.3-1 s) per qualifying winner. On the dev
  benchmark no candidate was moved (`odd_even_retest=False` on all 32 rows),
  i.e. the change is free there and its value is measured on the adversarial
  EBs (Part E).

### C2: exclusion zones anchored on a false positive (weakness 1)

At acceptance every candidate gets a fixed-period fit on the working binned
curve (`pipeline._anchor_plausibility`, ~0.5 s); it carves a gate-6
exclusion zone only if Rp/R* <= 0.2 and (when a density is available) the
a/R* is consistent with the star. `_ringing_neighbour` skips non-carving
anchors; the candidate itself is still masked so the search continues. The
decision and the fit are stored on the planet row (`carves_exclusion_zone`,
`gate_fit`) and a note names the reason. On the final dev benchmark run [M]
six accepted candidates did not carve: TRAPPIST-1's 5.895 d and 6.372 d
deep boxes (Rp/R* 0.22 and 0.21 on the working curve), HD 63433's two
rotation artifacts (0.25, 0.26), LHS 3844's 5.82 d false positive (0.28) and
WASP-126's 11.75 d false positive (density ratio 1e5). This is exactly the
case the report reproduced: TRAPPIST-1 e at 6.0996 d sits 3.47% from the
5.895 d false positive and is now RECOVERED (found at 6.10125 d, 0.03% off),
and TRAPPIST-1 f (9.07493 d against 9.20669, 1.4%) with it. The two gains
come with fewer false positives on that target (2 against 5), not more,
because the deep boxes are still masked after acceptance and are now
flagged by the density test.

### C3: gate 7's second condition (weakness 2)

A railed duration alone no longer vetoes: the box depth must also imply
Rp/R* > 0.2 (`GATE7_MIN_RP_RS`). The three catastrophic TRAPPIST-1 boxes
(52-96 ppt, Rp/R* 0.23-0.31) are still vetoed (the 10.78 d 95.5 ppt note
appears in the run as before); a shallow railed fit is kept and left to
vetting. No dev-benchmark candidate was newly kept by the second condition
[M: no "gate 7 second condition" note; INFO lines are not in the harness
logs, which run at WARNING].

### Not in the prompt, forced by measurement

* **No-dip flag.** A candidate whose limb-darkened fit sees no significant
  dip (depth < 3 sigma on white noise) keeps its box depth and gets a
  high-risk flag. Measured on the dev set: every recovered planet is above
  3 sigma (the weakest, TOI-700 b at BLS SNR 5.2, at 3.7) and the two
  HD 63433 rotation artifacts at BLS SNR 89 and 104 are at 1.1 and 0.3
  sigma; they were "promising" and "likely false positive" before and are
  "ambiguous" and "likely false positive" now.
* **Red-noise beta.** Without it HD 63433 c (a real planet on a young,
  spotted star) was flagged a/R*-inconsistent at profile delta chi2 = 70;
  beta saturates at its cap of 5 on that star and the statistic becomes 2.8.
* **Fitted-depth acceptance.** The fitted depth is shipped only when the fit
  describes the box event: significant dip, Rp/R* < 0.85, T14 below a
  quarter of the period and within 0.2-4 times the box duration (HD 63433
  c's fit ran to a 29-hour transit on rotation residuals and would otherwise
  have been shipped).
* **Template odd/even supersedes the point-based test** when both parities
  have at least 3 events. Forced by the first adversarial batch: the legacy
  test (per-point in-transit depths against the white-noise scatter) called
  WASP-39 b, WASP-14 b and KELT-11 b odd/even-different at 5.3, 3.3 and 6.1
  sigma, which with the elevated-SNR flag made three known hot Jupiters
  "likely false positive"; the template test read 1.3, 0.5 and 0.5 sigma on
  the same data. The legacy number stays in the notes and still decides
  when the template has too few events.
* **Elevated SNR demoted to medium when every fit-based test is clean**
  (significant transit-shaped dip, density-consistent, not grazing, no
  stellar secondary, no odd/even mismatch). The flag was a proxy for
  variability fitted as a transit; those tests now measure that directly.
  Same batch: TOI-674 b and TOI-1796 b (GJ 436 b) at SNR 114 and 173 with
  perfect fits and FPP < 1e-12 were "ambiguous" on the SNR flag alone. It
  stays high risk without a fit or when any test is not clean.
* **TRICERATOPS errors times beta.** With white-noise errors on bright,
  red-noise-dominated stars one scenario took probability 1.0 (WASP-76 b:
  PEB = 1.0 at beta 4.4; TOI-836 c: BEBx2P = 1.0 at beta 4.9). The
  per-point error handed to `calc_probs` is now the robust scatter times
  the fit's beta.
* **TESScut pre-check.** TRICERATOPS silently drops a sector whose cutout
  download fails and its per-sector pixel coordinates then no longer match
  the aperture list (KELT-11: IndexError inside `calc_depths`). The wrapper
  fetches the cutouts first (same cache) and passes only the sectors that
  have one.

## Part D: the packet

`src/tesshunter/packet.py` (new; re-exported from `reporting` as
`generate_packet`), `scripts/make_packet.py`. One directory per candidate:
`packet.md` (one page), `summary.png` (nine panels: detrended light curve
with every predicted transit marked, folded curve with the fitted model,
odd/even overlay, secondary-eclipse window with the deepest planetary
secondary drawn, per-unit folds, per-transit depths from the template,
in-transit centroid shift, TIC stars within 60 arcsec with Tmag and Gaia G
and the aperture circle, and the parameter / FPP / completeness text),
`ctoi_fields.json`, `fit.json`, `fpp.json`, `vetting.json`,
`neighbours.csv`, `packet.json`.

`ctoi_fields.json["form_fields"]` holds, in order: target ("TIC nnn"),
tic_id, discovery_source, period_days, period_err_days, epoch_bjd,
epoch_err_days, depth_ppm, depth_err_ppm, duration_hours,
duration_err_hours, disposition ("PC"), tag (left as `FILL_ME`),
candidate_name, paper_url, notes. The list comes from the ExoFOP-TESS
candidate guidelines page (`/tess/candidate_help.php`, read 2026-09-02): the
form asks for the TID name, discovery source, period, transit midpoint
(BJD), depth (ppm), duration, a tag, a paper URL and an initial note, with
candidate name and disposition (PC or FP) optional, and all four of period,
epoch, depth and duration must be present and positive for TOI working
group consideration [M]. The bulk-upload column list sits behind a login
and was not reproduced [R]. `supplementary` carries Rp/R*, Rp, a/R* (fitted
and catalog), impact parameter, inclination, the duration-averaged depth,
both stellar densities, SNR, transit count, FPP, NFPP, the verdict and flags,
sectors and the star; `provenance` the fit method, limb darkening, catalog
versions and the packet directory. The completeness figure is the P2
logistic curve evaluated at the matched-filter SNR of the fitted model on
the star's own detrended data binned to 30 minutes, with the caveat that the
curve was measured for the survey preset.

Demonstration [M]: `docs/packets/toi270_c_demo/` for TOI-270 c (TIC
259377017, SPOC sectors 3, 4, 5), built by
`scripts/make_packet.py --tic 259377017 --period 5.66` (final code; the
search takes ~30 s, the centroid check on two TPFs ~20 s and TRICERATOPS with
200,000 draws on the 150-point binned fold ~2 min the first time, cached
after). Contents: P = 5.660201 +/- 0.000060 d, T0 = 1389.50232 +/- 0.00050
BTJD, T14 = 1.64 +/- 0.20 h, depth 4.038 +/- 0.091 ppt (statistical error
0.066 times the red-noise beta 1.4; duration-averaged 3.41; ExoFOP lists
3,452 ppm), Rp/R* = 0.0589 +/- 0.0015, Rp = 2.40 +/- 0.10
R_Earth, a/R* = 26.8 +/- 3.7 against 25.5 +/- 0.3 from the TIC density
(prior adopted, delta chi2 0.2), b = 0.30 +/- 0.42; odd/even 0.7 sigma; no
secondary (measured -0.07 ppt, planetary bound 0.005 ppt); centroid shift
0.003 px (1.7 sigma) over sectors 3 and 4; 8 TIC stars within 60 arcsec, the
brightest neighbour 3.4 magnitudes fainter at 54 arcsec; TIC contamination
ratio 0.0103; FPP 0.080, NFPP 7e-77 with the SPOC apertures over 64 TIC
stars and 18 scenarios; matched-filter SNR 56 where the P2 curve gives a
recovery fraction of 0.78; verdict "promising planet candidate" both on
the light curve alone and after the pixel-level checks (the legacy
contamination test lists one "high-risk" neighbour, TIC 259377015 at 54
arcsec, which the NFPP demotes to a medium note). The cross-match was not
run for the demo (`--crossmatch` runs it; TOI-270 would be a hard stop).

## Part E: adversarial check

### Harness

`scripts/adversarial_vetting.py`. The target list
(`data/adversarial/targets_v1.csv`, seed 20260902) is drawn from the cached
catalogs: `planet` = ExoFOP TOIs with TFOPWG disposition CP or KP, Planet SNR
>= 15, Tmag <= 12, period 0.5-20 d, depth 300-30,000 ppm, one row per star;
`eb` = TESS EB catalog (Prsa et al. 2022) stars with Tmag <= 11.5, period
0.5-20 d, morphology coefficient < 0.6 (detached or semi-detached, so the
eclipses are transit-like rather than sinusoidal), primary depth 0.5-40%,
not in the TOI list; `blend` = ExoFOP TOIs retired as FP whose comment names
a nearby or background eclipsing binary (NEB, BEB, NPC), Tmag <= 12.5,
period 0.3-20 d, depth >= 300 ppm. Quotas 15 / 15 / 10 with reserves (3, 3
and 12; the blend TOIs mostly came out of FFI searches and often have no
2-minute data).

Each target runs `search_target` on SPOC 2-minute data (up to 3 sectors)
over a period window of 1/3.2 to 3.2 times the known period, so P/2 and 2P
are inside and the alias resolver is exercised, with the P3 vetting stack;
when the star has no 2-minute product the search is repeated with any
author and cadence (SPOC > TESS-SPOC > QLP). The accepted candidate matching
the known period (or a harmonic of it) is the one vetted; TRICERATOPS then
runs on it with 100,000 draws, the SPOC apertures where the data are SPOC
and a Tmag-sized circular aperture otherwise. Eight workers, one process
per target, one JSON per target under `data/adversarial/runs/v1/`
(git-ignored), summary in `data/adversarial/adversarial_results_v1.csv` and
`docs/ADVERSARIAL_VETTING.md`.

### What the first batch changed

The first ten planet-class results were read before the eclipsing binaries
had run and forced the four changes listed under Part C ("Not in the
prompt"): three known hot Jupiters were "likely false positive" on the
point-based odd/even test plus the SNR flag, two clean planets were
"ambiguous" on the SNR flag alone, and TRICERATOPS put probability 1.0 on a
single scenario for two planets with white-noise errors. The whole set was
then re-run from scratch with the final code; the matrix below is from that
run and is therefore not an independent test of those four changes, only
of everything else.

### Confusion matrix [M]

All 58 listed targets completed (18 planets, 18 eclipsing binaries, 22
blends; two eclipsing binaries needed a third attempt after their worker
hung inside a MAST call twice). Full per-target table, flags and numbers
in `docs/ADVERSARIAL_VETTING.md` and
`data/adversarial/adversarial_results_v1.csv`.
"Verdict" is the automated verdict on the candidate matching the known
period after the pixel-level checks and TRICERATOPS have been folded in;
"light curve only" is the verdict before them.

| truth | n | promising | ambiguous | likely false positive | found at a harmonic (its verdict) | not detected |
|---|---:|---:|---:|---:|---|---:|
| planet (CP/KP TOIs) | 18 | 9 | 9 | 0 | 0 | 0 |
| eclipsing binary (Prsa 2022) | 18 | 0 | 2 | 11 | 5 (all likely false positive) | 0 |
| blend (TOI retired as NEB/BEB/NPC) | 22 | 0 | 3 | 10 | 3 (2 likely false positive, 1 ambiguous) | 6 |

Acceptance: 0 eclipsing binaries and 0 blends reach "promising" (the
limit was 2). No known planet is called a false positive.

With the FPP gate (FPP <= 0.5 required for a packet): 8 planets proceed, 1
"promising" planet is blocked (WASP-39 b, TIC 181949561, FPP 0.76 with the
EB scenario at 0.37: an inflated 1.4 R_Jup hot Jupiter, the regime where
TRICERATOPS cannot separate a giant planet from a late-M companion without
radial velocities); 4 of the 18 planets have FPP > 0.5 in all (WASP-39 b;
Kepler-14 b, TIC 158561566, FPP 0.91 with NFPP 0.55, a planet in a known
binary; GPX-1 b, TIC 245392284, FPP 0.95, a brown dwarf; TOI-836 c, TIC
440887364, FPP 1.0 through the BEBx2P scenario on the binned input, 0.02 on
the beta-scaled sub-sample, Part B). Median FPP: planets 0.011, eclipsing
binaries 1.0 (17 of 17 with a value above 0.5), blends 1.0 (15 of 16).

What separates the classes, by flag [M]:

* Light-curve-only verdicts: 12 of 18 planets "promising", but also 9 of the
  40 eclipsing binaries and blends. The light-curve stack alone catches the
  eclipsing binaries mostly through the hard depth veto and the alias
  resolver (5 of 18 found at P/2 and vetoed there; a/R* inconsistent on 5,
  stellar secondary on 2, odd/even on 1) and cannot see a blend on a
  neighbour.
* The pixel-level checks and TRICERATOPS move 28 verdicts: every one of the
  9 eclipsing binaries and blends that were "promising" on the light curve
  goes to "likely false positive" or "ambiguous" (NFPP >= 0.1 on 15 of the
  16 blends with a value, centroid flag on 6 blends, a/R* inconsistent on 4
  blends); 3 known planets go from "promising" to "ambiguous" through the
  centroid check (TIC 199671901 at 7.5 sigma for a 0.003 px shift, TIC
  347430350, TIC 456862677) and 1 through NFPP (Kepler-14 b, 0.55).
* The 9 "ambiguous" planets: 5 centroid flags at 3.3-7.5 sigma on shifts of
  0.003-0.025 px (the flagged blends sit at 4.3-14.9 sigma on 0.004-0.025 px,
  so the P0 centroid module's significance does not separate the classes on
  bright stars), 1 NFPP (Kepler-14 b), 1 dayside secondary within its
  planetary bound (WASP-76 b, flagged but not stacked as designed), 2 with
  medium flags only (GPX-1 b, KELT-11 b: per-unit depth disagreement plus a
  sub-4-sigma centroid).
* Not detected: 6 blends, all with the fallback data or a shallow signal
  (440-2,400 ppm at Tmag 10-11 on 2 to 3 sectors) whose period was not
  accepted inside the search window; they are not vetting failures, they
  never reached vetting.

Thresholds set after seeing these results [A], all stated in the code:
the SNR demotion (first batch), the NFPP-clears-contamination rule and the
4-sigma centroid split. The matrix above was produced by re-applying the
final rules to the stored per-target outputs (`--reapply`), not by a fresh
run; the stored light-curve verdicts, fits, centroid, contamination and
TRICERATOPS outputs are unchanged by that.

## Benchmark, frozen scorer [M]

Same cache, same harness, same frozen `score.py`; reference sets are the P2
results (`results/p2_speed`, `results/holdout_p2_speed`). Dev at concurrency
10, holdout at 5. Every change of this prompt is in the run (`p3_vetting`,
`holdout_p3_vetting`); the adversarial run and the TRICERATOPS A/B were
executing on the same machine during the final runs, so the wall clocks are
under load.

Dev set (24 planets in range, 10 targets):

| metric | P2 reference | P3 |
|---|---|---|
| recovered | 17 | 19 |
| alias | 2 | 2 |
| missed | 5 | 3 |
| false positives | 12 | 8 |
| neutral (harmonic of an out-of-range planet) | 0 | 2 |
| verdict mislabels | 0 | 0 |
| mean depth error, all recovered | 13.02% (n = 17) | 22.54% (n = 19) |
| mean depth error, the 17 planets recovered in both | 13.02% | 10.29% |

The two new recoveries are TRAPPIST-1 e (found at 6.10125 d, 0.03% from
6.09962) and f (9.07493 d, 1.4% from 9.20669), both released by the gate-6
change (Part C2); their depths on the K2 1-minute data are 96% and 157% off
(three deep artifacts share the curve), which is what moves the all-recovered
mean up while the like-for-like mean moves down. No planet recovered in P2
is lost. The four fewer false positives are TRAPPIST-1 (5 to 2) and
HD 108236 (1 to 0: its 15.86 d candidate is now found at 9.678 d, a
harmonic of the out-of-range planet f, and scores neutral). Per-planet depth
errors, P2 to P3: WASP-18 b 8.1 to 4.1%, Pi Men c 7.0 to 3.0%, TOI-700 b
85.1 to 26.7%, HD 108236 e 5.4 to 0.5%, L 98-59 d 6.6 to 17.3%, TOI-700 c
1.9 to 11.5% (9 of 17 better). Which depth definition the catalogues use
is not uniform: over the 19 recovered planets the fitted maximum gives
22.1%, the duration-averaged depth 19.2%, the flat-bottom estimator 17.3%
(n = 18) and the box 40.1%; the maximum is shipped because it is the
quantity a CTOI form and a physical model define, with the mean reported
next to it.

Verdicts on the dev planets: 16 of the 19 recovered are "promising", 3 are
"ambiguous" (WASP-18 b: its 0.07 ppt dayside secondary, within the planetary
bound, flagged but not stacked; TRAPPIST-1 b; HD 108236 e). Every accepted
false positive on HD 63433 and TRAPPIST-1 that used to be "promising" is now
"ambiguous" or "likely false positive" (no-dip and density flags).

Holdout (6 planets in range, 5 targets):

| metric | P2 reference | P3 |
|---|---|---|
| recovered / alias / missed / FP | 4 / 0 / 2 / 8 | 4 / 0 / 2 / 8 |
| verdict mislabels | 1 (WASP-121 b) | 0 |
| mean depth error (n = 4) | 10.83% | 10.76% |

WASP-121 b was "likely false positive" in P2 (elevated SNR plus the
point-based odd/even test) and is "ambiguous" now; an intermediate P3 state
made it FP again through its 0.08 ppt dayside secondary stacking with the
inflated-radius flag, which is why a planet-consistent secondary now never
stacks (Part C).

Wall clock per target (s), P2 to P3: HD 108236 545 to 390, HD 63433 328 to
257, L 98-59 215 to 174, LHS 3844 357 to 271, Pi Men 100 to 92, TOI-270 80
to 70, TOI-700 68 to 66, TRAPPIST-1 165 to 142, WASP-126 92 to 85, WASP-18
189 to 152; holdout AU Mic 453 to 335, GJ 357 628 to 418, HD 21749 88 to
87, TOI-125 450 to 348, WASP-121 199 to 168. The characterisation stage (all
fits) costs 1 to 5 s per target; the gate-6 fits and the resolver re-test are
inside "detect". The P3 runs happened to be faster than the P2 runs on every
target (the P2 numbers were taken while other jobs ran too); the point is
that the fit adds seconds, not minutes.

Suite: 305 passed, 1 skipped, 102 s (P2: 265 passed). The suite is
network-free: `tests/conftest.py` sets `TESSHUNTER_OFFLINE=1`.

## What was refuted or changed by measurement

* A covariance-based a/R* consistency test: on a synthetic 2 R_Earth planet
  at SNR ~15 the least-squares fit landed on a grazing solution and the
  covariance called the catalog density 5.9 sigma away. Replaced by the
  profile delta chi2 test with the density prior.
* White-noise errors for the template odd/even test: Pi Men c came out 7.5
  sigma odd/even-different. Replaced by the event-to-event scatter (1.5
  sigma) and a 3-events-per-parity minimum.
* The profile test on white-noise errors: HD 63433 c at delta chi2 = 70.
  Discounted by a red-noise beta (5 on that star; 2.8 after).
* Shipping the fitted depth whenever the fit converged: HD 63433's rotation
  artifacts at BLS SNR 89-104 got fitted depths of 0.17 and 0.09 ppt at 1.1
  and 0.3 sigma, and HD 63433 c's fit ran to a 29-hour duration. Guarded
  (significance, Rp/R*, duration fraction, duration ratio).
* Radius-only stars had no density test, so the 114 and 91 ppt TRAPPIST-1
  boxes (Rp/R* 0.29-0.31, a/R* 500-575 for periods of 6 days) were
  "promising". The M ~ R fallback [A] gives them a density; both are now
  flagged (delta chi2 250 and 1518 after beta) and "ambiguous".
* TRICERATOPS on the full 20,000-point fold: 290-730 s per candidate.
  Capped at 6,000 points, then replaced by the binned fold (Part B).
* **Network calls inside TRICERATOPS and the download layer can hang
  without a timeout.** During the final adversarial run the disk filled
  (the TESScut cutouts, 10-110 MB per sector, on top of the 11 GB P2
  prefetch cache). Downloads then failed, 87 zero-byte light-curve files
  were left in the lightkurve cache (lightkurve later refused them as "not
  a supported data product", which read as "no data" for seven eclipsing
  binaries until the files were purged), and every one of the eight
  workers sat for six hours on an open connection to `mast-cluster.stsci.edu`
  (130.167.220.x, first misread as the Gaia archive) without completing a
  target; a later run hung the same way on one target. Mitigations: the
  Gaia field-star query runs in a child process killed after 240 s (the
  blended-star scenarios are skipped when it fails, and the result says
  so), every worker and every `run_fpp` call sets a 300 s socket timeout, a
  cached TRICERATOPS FAILURE is never served again, the harness has
  `--redo-no-data` and `--redo-network-errors` to retry, and the cutout
  cache is disposable (`data/cache/lightkurve/tesscut`). What is NOT fixed:
  a worker inside an astroquery call that neither errors nor times out;
  the orchestrator has no per-job wall-clock kill. Prompt 4's survey
  orchestrator (`run_survey.py`) does have one and should be the model.
* The ExoFOP bulk-upload column list: behind a login [R]. The form fields
  from the public guidelines page are what `ctoi_fields.json` carries.

## Assumptions the results rest on [A]

* Circular orbits in the fit; eccentricity shows up as a density mismatch in
  the "high" direction and is named as a possible cause in the note.
* Stellar density from TIC `rho` (with its error), else mass and radius
  (10% / 15% fractional errors when the catalog gives none), else radius
  alone with M ~ R in solar units and a 30% mass error.
* The a/R* flag thresholds: density ratio outside a factor 3 AND profile
  delta chi2 above 9 after dividing by beta squared (beta capped at 5).
* The secondary bound: zero redistribution, zero Bond albedo, geometric
  albedo 1, a flat 600-1000 nm band; margin factor 2.
* Rp/R* 0.2 as the planet-shaped limit for gates 6 and 7.
* TRICERATOPS settings: 100,000 draws (200,000 for the demo packet), 20
  samples per scenario, 10-pixel search radius, Gaia DR3 field population,
  a circular Tmag-sized aperture where no SPOC aperture exists.
* The completeness figure in a packet reuses the P2 curve (survey preset)
  at the candidate's own matched-filter SNR.

## Still open

1. **The elevated-SNR flag** is now medium when every fit-based test is
   clean and high risk otherwise (Part C, "Not in the prompt"). The
   demotion was decided on the first adversarial batch and then the full
   set was re-run; Part E's matrix is from that re-run, so it is not an
   independent test of the change.
2. **The a/R* test is one-sided in practice.** The "high" direction (fit
   denser than the star) also flags eccentric orbits and wrong harmonics;
   both are named in the note but not separated.
3. **beta saturates at 5 on the most active stars** (HD 63433), where the
   profile test is then effectively off; such stars fall back to the other
   flags.
4. **TRAPPIST-1 depths.** The two new recoveries (e, f) carry depths 2-2.6
   times the catalog values on the K2 1-minute data with three deep
   artifacts in the same curve; the shipped mean depth error over the 19
   recovered planets is therefore above P2's over 17 even though every
   planet recovered in both is at least as good (section "Benchmark").
5. **The survey path has not been re-run** with the fit in the loop; the
   per-star cost (one quick fit per accepted candidate plus one full fit per
   planet, and the resolver re-test on strong winners) was measured only on
   the benchmark targets (Benchmark section). Prompt 4 should measure the
   median on its first 50 stars before committing 20 workers.
6. **TRICERATOPS needs network at run time** (TESScut, TIC, Gaia) and one
   Gaia query per star; on dense fields the TIC table reaches 180 stars and
   `calc_probs` slows accordingly. The 6,000-point cap and the per-star
   caches are the mitigation; no offline mode exists.
7. **ExoFOP bulk-upload format** not verified (login). The human enters the
   fields from `ctoi_fields.json` by hand or confirms the column order
   inside ExoFOP.
8. **celerite shim** lives in the venv, not the repo (Environment changes).
9. **The P0 centroid module** flags 0.003-0.025 px shifts on bright stars
   at 3-8 sigma for known planets and at 4-15 sigma for real blends; its
   error model (median error times a fixed red-noise factor) does not carry
   the systematics that dominate at that level. It is the one pixel-level
   test that produced false flags on the adversarial planets; NFPP did not.
   Prompt 5's independent centroid work should not reuse it as is.
10. **The adversarial orchestrator has no per-job wall-clock kill**; the
    survey orchestrator (`scripts/run_survey.py`) has one and prompt 4 should
    use that one, not this harness, for anything at scale.

## Files

* `src/tesshunter/transit_fit.py`, `limb_darkening.py`, `stellar.py`,
  `fpp.py`, `packet.py` (new); `vetting.py`, `pipeline.py`,
  `bls_search.py`, `survey.py`, `reporting.py` (changed).
* `data/limb_darkening/claret2017_tess_quadratic_{atlas_z0_xi2,phoenix_z0_q}.csv`.
* `scripts/adversarial_vetting.py`, `scripts/make_packet.py`;
  harness-side `compare_p3.py` (in the benchmark directory, not the repo).
* `data/adversarial/targets_v1.csv`, `data/adversarial/adversarial_results_v1.csv`,
  `docs/ADVERSARIAL_VETTING.md`; per-target JSON under
  `data/adversarial/runs/v1/` (ignored by git).
* `docs/packets/toi270_c_demo/` (the demonstration packet).
* `tests/test_transit_fit.py`, `test_vetting_p3.py`, `test_gates_p3.py`,
  `test_fpp.py`, `test_packet.py`, `tests/conftest.py`;
  `tests/test_depth_remeasure.py` adjusted for the fit-first depth.
* Benchmark result sets: `results/p3_vetting`, `results/holdout_p3_vetting`
  in the harness directory; the reference sets are untouched.
* Caches (ignored): `data/cache/tic/`, `data/cache/tic_cone/`,
  `data/cache/fpp/`.
