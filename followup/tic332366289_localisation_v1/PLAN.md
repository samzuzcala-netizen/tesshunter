# PLAN: TIC 332366289 pixel-level source localisation (follow-up v1)

Written 2026-10-01 ~17:30 UTC, after input verification and before any new source-position fit.
All numerical choices are in `config.json`. They are **adopted follow-up choices**, not frozen P12 rules.
This work changes no P12 code, record, packet, verdict or tier.

## Question

Which star supplies the missing light of the ~18.748-d dimming attributed to TIC 332366289
(Gaia DR3 1415338513130475136), or why can the TESS pixels not tell?

## Inputs (verified read-only; hashes in `inputs/integrity_before.json`)

- Stage A record: 4 observed events: E00 (s57, kept), E32 (s79, kept), E33 (s80, kept), E39 (s84, excluded: scattered-light flag on 50% of in-event cadences + PDC gap 0.00 d). E29 (s77) has no in-transit data.
- Packet fit "4 transits" = the 3 kept events + the excluded E39: `scripts/audit_p5.py fit_step` windows all light-curve data around every predicted transit and does not read Stage A's keep/exclude list. The fitted ephemeris is therefore partly informed by an excluded event.
- Pixels: cached TESScut 21x21 SPOC-FFI cubes (s57, 77, 78, 79, 80, 84), 200-s cadence, not background subtracted (FLUX_BKG = 0). Every TESScut frame matches exactly one TESS-SPOC light-curve cadence within 52 s (median offsets -41 to +46 s by sector, a barycentric-convention difference). The matched TESS-SPOC TIME is the frame time. The QLP sector-80 timing problem (166-206 s) is a QLP-product issue; TESScut s80 agrees with TESS-SPOC s80 to +14...+27 s.
- PRF: official TESS PRF models (MAST `start_s0004`, VERSION UPDATED_2.0), 4 bracketing CCD grid points per camera/CCD.
- Scene: Gaia DR3 cone 600" and TIC v8.2 cone 400" (one bounded query each, saved with provenance).

## Primary settings

- Ephemeris E_A (Stage A survey ephemeris under which the 3 events were kept): P = 18.748084871649127 d, T0 = 2869.8700663100585 BTJD, duration 2.228 h.
- Sensitivity E_F (packet fit): P = 18.748273038412112 d, T0 = 2869.85249375544 BTJD, T14 1.93 h. Its centres are 15-25 min earlier than E_A's.
- Windows: in-event |t - tc| <= duration/2; guard 1.0 h; reference 5.0 h on each side. Momentum dumps are never bridged.
- Difference image: D = per-pixel linear-in-time baseline (fit to both reference sides) evaluated at the in-event times, minus the in-event image, averaged over in-event frames. Signed, unclipped, never normalised by total flux.
- Uncertainty: formal per-pixel error from reference-residual scatter, scaled by a per-sector factor kappa calibrated on the calibration half of the independent null windows.
- Fit region: 11x11 pixels centred on the target's registered pixel. Nuisance: plane background (3 terms) in every model.
- Models per difference image: M0 (plane only), M_T (target position), M_n (each neighbour), M_free (0.05-px grid within 4.5 px). Amplitude A is signed missing flux in e-/s (PRF normalised to unit total flux).
- Joint fit: common sky position mapped into each event's native WCS/PRF. Event-specific amplitude and plane. Registration uncertainty (floor 0.1 px per axis) is propagated by Monte Carlo over per-sector offsets. Events are never stacked as arrays.
- Contours: 2-dof profile-likelihood Delta chi2 = 2.30 / 6.18 / 11.83 (68.27 / 95.45 / 99.73%). Formal contours only mean something when the amplitude is significant, and they are reported separately from empirically tested coverage.

## Sensitivity set (small, predeclared)

1. Ephemeris E_F windows. 2. Quadratic baseline. 3. Gaussian PRF fitted to the scene. 4. s84 (E39) as a diagnostic, never pooled.

## Validation

- Focused unit tests: WCS/pixel transforms, PRF normalisation/orientation, time/mask alignment, sign convention, uncertainty propagation. Plus a blended-star regression: a shallow eclipse on a star one pixel off-target, where the flux-weighted centroid barely moves but the difference-image fit lands on the eclipsing star.
- Complete-procedure pixel injections into out-of-event control windows from the same sectors. Control windows never overlap any predicted event window under either ephemeris. Only the host's modelled PRF contribution is subtracted, with a trapezoid shape integrated over each cadence. Hosts: the target and each listed neighbour. Amplitude is matched to the aperture (reproduces 6.5 ppt in the TESS-SPOC optimal aperture) and capped at the host's total flux, with the cap recorded. Half the injections use a perturbed injected PRF (width x U(0.9, 1.1), offset N(0, 0.1 px)) while the fit always uses the primary PRF.
- Workload: smoke test of 5 per host and sector, then up to 100 per host per sector on the 4-h control grid. That reuses about 35-37 independent noise windows per sector, so effective sample sizes are quoted by independent window.
- Null windows: the same recipe without injection. Calibration half sets kappa. Evaluation half measures false detections and false localisations. A joint null distribution is built by combining one null window per sector.
- Reported: confusion matrix, localisation bias, contour coverage, failed fits, with Wilson intervals and denominators.

## Decision rules (predeclared; full text in config.json)

`TARGET_LOCALISED` needs pixel detection, the target inside the joint 95.45% region, every catalogue source within 3 px spatially excluded (Delta chi2 >= 9 relative to the best catalogue host, and in >= 2 of 3 leave-one-out fits at >= 4) or flux-infeasible, joint-injection coverage >= 85%, and target-to-neighbour confusion <= 5%.
`NEIGHBOUR_LOCALISED`, `OFF_TARGET_UNASSIGNED`, `INCONSISTENT_EVENTS` (two or more detected events with position-consistency p < 0.01), and otherwise `UNRESOLVED`. `OPERATIONAL_BLOCKED` applies only if a needed step fails.
The analysis is not adjusted to restore the frozen Tier 2 label.

## Resource limits

Two workers at most, one numerical thread, 4-h wall ceiling from 17:10 UTC, 10 GB new downloads (used: ~0.3 MB PRF + 0.2 MB catalogues), bounded network calls with at most one retry. Checkpoints go in `results/`. Large arrays go to `D:\tesshunter_followup\tic332366289_localisation_v1\`.
