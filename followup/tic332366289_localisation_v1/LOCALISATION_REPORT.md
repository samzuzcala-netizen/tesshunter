# TIC 332366289: pixel-level source localisation (follow-up v1)

New post-P12, candidate-only follow-up. Executed 2026-10-01, 17:10 to 18:08 UTC. It is not a continuation or rerun of the frozen P12 search, not a blind validation, and not a planet test. **The frozen P12 verdict (SUBMIT, candidate tier 2) and every P12 record are untouched.** This report changes no tier.

## 1. Primary status: `UNRESOLVED`

**Which star supplies the missing light, or why can we not tell?**

The TESS pixels cannot tell. Three reasons, each measured:

1. **The pixel signal is weak and does not meet the predeclared, null-calibrated detection rule.** At the target's registered position, the three retained events give a joint missing flux of **1.46 ± 0.39 e⁻/s (S/N 3.73)**. None of the 130 null-window combinations reached that S/N. But the predeclared rule also requires the free-position search to beat the null 99th percentile, and it does not: Λ = 33.8 against a null p99 of 56.3. About 2% of noise-only windows do as well.
2. **The localisation does not single out a star.** The joint free-position best lies 57″ south of the target and comes entirely from one event (E32, sector 79). That event's difference image carries full-width row/column stripe structure (null fraction ≥ real 2–5%), so it is not a reliable offset. Among catalogue hosts, the target and Gaia DR3 1415338405755460480 (47″) are not separated (Δχ² 0.66). Neither is Gaia DR3 1415338306971353600 (27″, Δχ² 6.2 < 9). With E32 left out, the target is the best catalogue host, but the 27″ and 35″ neighbours stay within Δχ² 5.5–6.5.
3. **The procedure is not calibrated well enough at the observed amplitude.** For target-hosted pixel injections at the measured 1.46 e⁻/s, the formal 95.45% region covered the true host in **78/100** joint realisations, and **11/100** were assigned to a neighbour. The predeclared bars were ≥ 85% and ≤ 5%.

One quantitative finding sits outside the localisation and is labelled an interpretation (§8): **the pixel deficit at the target tracks the SAP light curve, not PDCSAP.** It is 4.2 ± 1.6, 2.1 ± 1.3 and 4.6 ± 2.0 ppt for E00/E32/E33. SAP gives 6.8 ± 1.7, 1.7 ± 1.2 and 4.5 ± 1.6 ppt; PDCSAP gives 8.1, 6.1 and 5.8 ppt. In sector 79 the dip is close to absent in the raw pixels. If the dip is astrophysical, **none of the four listed neighbours can produce the light-curve aperture depth while matching the missing flux measured at its own position.** Each would need 1.03–1.46× its total flux (SAP depth) or 1.78–2.53× (PDCSAP depth), i.e. 3.4–22 e⁻/s of missing flux at its own position. The pixels measure −0.16 to 1.05 e⁻/s there, a 3.6–8.0σ shortfall. This argues against the listed neighbours as the source of the light-curve dip. It is not a spatial localisation, and it does not exclude an unresolved source within ~1 px of the target.

Nothing here confirms, validates or restores a planet claim.

## 2. What was executed

- Read-only inspection of the candidate's Stage A/B/C/D, fit, packet, neighbour and pixel records. Inspection of `src/tesshunter/centroid.py` and `p12/protocol/rules_p12.py::centroid_support`. Integrity hashes were taken before and after (§12).
- Event table with exact frame masks (`events.csv`, `results/masks/`), matched by time to TESS-SPOC cadences.
- `PLAN.md` and `config.json` were written before any new source fit. Two disclosed revisions (§5).
- Standalone difference-image and PRF-localisation code (`code/`), using official TESS PRF models and Gaia DR3 + TIC scene catalogues, with 15 focused tests passing. One of those tests is a blended-star regression.
- Fits on all four observed events (3 primary + s84 diagnostic): per-event, joint, leave-one-out, registration Monte Carlo, and 4 predeclared sensitivity variants.
- Null controls: 130 windows per sector × 3 sectors and 130 joint combinations. Complete-procedure pixel injections: 11 host/amplitude configurations × 100 joint realisations (3,300 single-sector fits).
- Wall time ~58 min of the 4-h ceiling (17:10:34 to ~18:08 UTC). New downloads ~3.0 MB of the 10 GB ceiling (PRF FITS 2.76 MB, catalogue CSVs 0.19 MB, transit-diffImage source 0.06 MB). Single process, numerical threads 1. No workers left running.

## 3. Event-count and ephemeris reconciliation

| Item | Finding |
|---|---|
| Observed events (Stage A, survey ephemeris) | 4: E00 (s57), E32 (s79), E33 (s80), E39 (s84). E29 (s77, BTJD 3413.56) falls in a data gap: zero TESScut frames in its window. |
| Retained | E00, E32, E33 ("K10 kept sectors 57, 79, 80"). |
| Excluded | E39 (s84): 50% of in-event cadences carry the scattered-light flag, and the corrected flux has a PDC gap 0.00 d away. |
| Packet fit "4 transits" | **Resolved: it reintroduces the excluded E39.** `scripts/audit_p5.py::fit_step` (lines 1074–1078) windows every light-curve point within ±max(3 × duration, 0.4 d) of each predicted transit in all sectors and never reads Stage A's keep/exclude list. `fit.json` data.sectors = [57, 79, 80, 84]. |
| Primary ephemeris (adopted) | E_A = Stage A survey ephemeris, under which the three events were accepted: P = 18.748084871649127 d, T0 = 2869.8700663100585 BTJD (TDB), duration 2.228 h. |
| Sensitivity ephemeris | E_F = packet fit: P = 18.748273038412 d, T0 = 2869.852493755 BTJD, T14 1.93 h. Its predicted centres are 25.3, 16.6, 16.4, 14.7 min earlier for E00/E32/E33/E39. It is partly informed by E39. |
| Time scale | Packet epoch 2459869.852493756 BJD = BTJD 2869.852493756 (BJDREFI = 2457000 in every product). TIMESYS TDB, TIMEREF SOLARSYSTEM throughout. |
| Pixel/LC timing | Every TESScut frame matches exactly one TESS-SPOC cadence. TESScut − SPOC offsets: s57 +35…+52 s, s79 −46…−34 s, s80 +14…+27 s, s84 +35…+50 s. This fits a barycentric-correction-position convention and is well below the 200-s cadence. Frames use the matched TESS-SPOC (target-barycentric) TIME. |
| Sector 80 | The P11/P12 exclusion is of **QLP** s80 (166–206 s offsets against TESS-SPOC). The SPOC-FFI TESScut s80 cube agrees with TESS-SPOC s80 to +14…+27 s, so the QLP problem does not carry over to these pixels. Note that TESScut and TESS-SPOC share the SPOC FFI clock, so this is a consistency check, not an independent absolute-time check. |
| Unresolved | None material to localisation. The 15–25 min E_A/E_F centre difference is covered by the 1-h guard; the E_F sensitivity run gives the same picture (§10). |

## 4. Inputs and conventions (new measurements unless marked inherited)

- **Pixels**: cached TESScut 21×21 SPOC-FFI cubes. s57 cam4/ccd4, s79 cam2/ccd2, s80 cam3/ccd4, s84 cam4/ccd4 (s77, s78 cam2/ccd1 for coverage only). 200-s cadence, 158.4-s effective exposure. Calibrated e⁻/s, **not background subtracted** (FLUX_BKG ≡ 0), so no background was subtracted and none was double-subtracted. FLUX_ERR is not used; noise is measured empirically. Paths, hashes, origins, WCS and quality bits: `inputs/pixel_inputs.csv`, `inputs/fits_metadata.json`.
- **Frame quality**: TESScut QUALITY = 0 and TESS-SPOC QUALITY & 191 = 0 (attitude tweak, safe mode, coarse/Earth point, Argabrightening, desaturation, manual exclude). Scattered-light flags are recorded, not used. No momentum dump falls in any primary event's window.
- **Windows**: in-event |t − t_c| ≤ 1.114 h (E_A), 1-h guard, 5-h reference on each side. Primary events have 40–41 in-event frames and 90 + 90 reference frames.
- **Scene**: Gaia DR3 cone of 600″ (580 sources) and TIC v8.2 cone of 400″ (248 rows), each queried once with provenance (`inputs/`). Target cross-match TIC 332366289 ↔ Gaia DR3 1415338513130475136 is confirmed (TIC GAIA column; 1.68″ J2000→J2016 offset equals the proper motion). Positions propagated to each event epoch. TESS magnitudes from TIC v8.2 (all hosts have one), with adopted uncertainty max(e_Tmag, 0.2) mag. The target's flux is fitted. Zero point per sector is 20.54–20.56 from 12–14 stars with T ≤ 15.5.
- **Scene completeness**: within 3.6 px, the old 63″ list missed three sources, which are added as hosts. Gaia DR3 1415338478770171264 (60″, T 20.8), 1415338543194431616 (68″, T 19.0) and 1415338543194435712 (74″, T 16.1, 61 e⁻/s). The nearest T ≤ 13 star outside the cutout is 262″ away, at least 2 px beyond the edge and ≥ 7 px from the fit box. The scene fit shows no gradient that would indicate a bright external contributor.
- **Registration**: an out-of-event scene fit (Gaia × PRF, free fluxes for T ≤ 16, plane, global offset) gives offsets (+0.008, −0.025), (+0.073, −0.067), (+0.006, −0.031), (+0.006, −0.050) px for E00/E32/E33/E39, with ≈0.01 px statistical error. An adopted σ_reg ≈ 0.10 px per axis (floor) is propagated by Monte Carlo. The blended scene's photocentre is never used as the target position.
- **PRF**: official TESS PRF (MAST `start_s0004`, VERSION UPDATED_2.0), bilinear between the 4 bracketing CCD grid PRFs at the target's CCD position. Header conventions are verified: zero offset at sample 58, 1/9 px sampling, [row, col]. The scene fit prefers the nominal width (width scan minimum at 0.95–1.0). An integrated Gaussian (σ 0.7–0.8 px, fitted on the scene) is a sensitivity variant only.
- **transit-diffImage** (commit 2b13199132ce, inspected, not used): its `tessprfmodel.py` 5×5 grid loop writes `prfn[i]` with the row index only. Only the five col-2092 PRFs survive, and they are combined by inverse distance rather than bilinearly. It also flips image rows (`[::-1]`), uses mean out-of-transit rings without a trend model, and needs tess-point, which is broken in this venv. Its difference sign (out − in) matches this work.

## 5. Method (adopted follow-up choices; full list in `config.json`)

- **Difference image** per event: D = (per-pixel baseline at in-event times) − (observed in-event image), averaged over good in-event frames, in e⁻/s per pixel. Positive means lost. D is signed, unclipped, never divided by total flux and never aligned on a centroid. The baseline is fitted to both reference sides only.
- **Revision R1** (disclosed; chosen on calibration-half null windows **before any event fit**): the baseline is per-pixel linear-in-time **plus a per-frame background-level regressor** (mean of the faintest 20% of cutout pixels), with **point-to-point** noise. The original linear/MAD recipe gave null reduced χ² medians of 0.41–0.79 in s79/s80/s84, with p10 as low as 0.02, because smooth scattered-light residuals inflated the errors. The selection rule was stated in code before running. The first selection code mis-implemented the tie rule (it printed V3) and was corrected to the stated rule (V2) before any event fit. The original recipe is kept as a sensitivity run. After R1, κ = 1.04/1.00/1.04/1.00 (s57/79/80/84).
- **Models** per difference image (11×11 box around the target; the same plane nuisance in every model): M0 (plane only); M_T (target); M_h (each of 8 catalogue hosts); M_free on a 0.05-px grid within 4.5 px. Amplitude A is the missing flux in e⁻/s of a unit-total-flux PRF. This is the source position estimate directly, never divided by depth.
- **Revision R2** (disclosed; made **after** seeing the first real-event output): free-position localisation of the *dimming* source uses the zero-amplitude boundary (profile χ² with A ≥ 0). The signed fit in E32 locked onto a −15σ *brightening* at the box edge, which is not missing light. Signed results are still reported (`results/joint.json` "signed") and both versions ran identically on nulls and injections. R2 does not favour the target. Under it, the joint best still lies off-target.
- **Joint fit**: a common sky grid (±85″, 1″ step) mapped into each event's own WCS + registration + PRF, with event-specific amplitude and plane. Arrays are never stacked. Leave-one-out fits and a registration Monte Carlo (200 draws) were run. Contours use 2-dof Δχ² = 2.30/6.18/11.83. They are formal model contours; their empirical coverage is in §9.
- **Decision rules** were fixed in `config.json` before fitting. The formal χ²(4) consistency p-value was predeclared but proved invalid for look-elsewhere free fits (null median Q 11.8 against 3.4 for χ²(4)). The calibrated null fraction is used and both are reported.

## 6. Per-event and joint results

| Event | Sector (cam/ccd) | Stage A | E_A centre (BTJD) | in / ref frames | kappa | target A (e-/s) | target S/N | pixel deficit at target (ppt) | Stage A PDCSAP / SAP depth (ppt) | dimming free best: offset, S/N, look-elsewhere null p | 95.45% region | target in 95.45%? (dchi2) | quality notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E00 | 57 (4/4) | kept | 2869.8701 | 41 / 180 | 1.042 | 1.73 +/- 0.67 | 2.59 | 4.2 +/- 1.6 | 8.1+/-1.7 / 6.8+/-1.7 | 5.30 px (97"), 3.69, 0.023 (3/130) | 1.55 px^2 (touches grid edge) | no (6.87) | free best at fit-box edge beside the T~11.7 star residual; target inside 99.73% |
| E32 | 79 (2/2) | kept | 3469.8088 | 40 / 180 | 0.997 | 0.99 +/- 0.59 | 1.67 | 2.1 +/- 1.3 | 6.1+/-1.2 / 1.7+/-1.2 | 2.70 px (57"), 5.82, 0.008 (1/130) | 0.35 px^2 | no (31.09) | full-width row/column stripe structure in D (null fraction >= real 5.0% rows / 2.1% cols); signed fit finds a -15 sigma brightening at the box edge; dip present in PDCSAP only weakly in SAP |
| E33 | 80 (3/4) | kept | 3488.5569 | 40 / 180 | 1.042 | 1.94 +/- 0.83 | 2.35 | 4.6 +/- 2.0 | 5.8+/-1.6 / 4.5+/-1.6 | 0.11 px (2"), 2.36, 0.708 (92/130) | 81.90 px^2 (touches grid edge) | yes (0.07) | event on a steep background ramp (~122 to 165 e-/s/px); baseline adequacy normal (MAD/p2p 1.00) |
| E39 | 84 (4/4) | excluded | 3601.0454 | 40 / 180 | 0.998 | 0.42 +/- 0.76 | 0.54 | 1.0 +/- 1.8 | 6.9+/-2.2 / 3.9+/-1.6 | 5.06 px (93"), 2.88, n/a (s84 nulls not run) | 4.57 px^2 (touches grid edge) | no (7.98) | Stage A excluded (scattered-light flag 50%, PDC gap 0.00 d); diagnostic only, never pooled |

Pixel deficit = A_target / f_target (f_target from the scene fit, 409–463 e⁻/s). Stage A depths are inherited. PDCSAP is crowding-corrected; SAP is diluted by 2–4% (CROWDSAP 0.96–0.98). Motion diagnostics (in − out pointing shift through the scene gradient) are ≤ 0.0006 ± 0.0006 px in every event. Baseline adequacy (MAD/p2p of reference residuals) is 0.99–1.01 for all events, typical of the nulls.

| Fit (dimming-only, A >= 0) | events | free best (xi, eta) arcsec | free improvement vs null | consistency Q (formal p) | target A (e-/s) | target S/N | target dchi2 vs free | best catalogue host (target dchi2 vs it) | 95.45% area (arcsec^2) |
|---|---|---|---|---|---|---|---|---|---|
| joint | E00, E32, E33 | (-9, -56) | 33.83 | 19.23 (0.0007) | 1.46 +/- 0.39 | 3.73 | 18.79 | 1415338405755460480 (0.66) | 168 |
| LOO without E00 | E32, E33 | (-9, -56) | 33.83 | 5.64 (0.0596) | 1.32 +/- 0.48 | 2.73 | 25.51 | 1415338405755460480 (7.38) | 158 |
| LOO without E32 | E00, E33 | (-44, -85) grid edge | 13.29 | 5.88 (0.0529) | 1.82 +/- 0.52 | 3.49 | 1.06 | 1415338513130475136 (0.00) | 1192 |
| LOO without E33 | E00, E32 | (-9, -56) | 33.83 | 13.66 (0.0011) | 1.32 +/- 0.44 | 2.97 | 24.30 | 1415338405755460480 (4.80) | 168 |

Registration Monte Carlo (200 draws, per-sector sigma_reg ~0.10 px/axis): best-position scatter 2.3" (xi) x 2.4" (eta); registration-marginalised 68.27/95.45/99.73% areas 98 / 291 / 949 arcsec^2 (statistical-only 48 / 168 / 579). Joint best RA, Dec = 257.21814, 50.47285 (deg).

**Independent-event support.** The joint off-target best comes entirely from E32: E32 alone puts its best at the same (−9″, −56″), and dropping E32 moves the joint best to the grid edge. E00 and E33 alone favour positions near the target, but only weakly (E33 S/N 2.4; its 95% region covers 82 px², so every host is inside). No position is supported by more than one event. Calibrated per-event detections (look-elsewhere null p < 0.01): E32 only (p = 0.008), at a stripe-dominated off-target location. E00's box-edge feature has p = 0.023 and E33's has p = 0.71. The predeclared `INCONSISTENT_EVENTS` rule fires with the textbook p-value but not with the calibrated one: null fraction 0.085 with Q ≥ 19.2, and only one calibrated detection.

## 7. Neighbour and host assessment

Spatial compatibility and lost-flux feasibility are reported separately. "Pixel missing flux" is the joint (inverse-variance) amplitude fitted at the host's own registered position. "LC-matched" is the missing flux that host would need to produce the observed light-curve dip in the TESS-SPOC optimal aperture, using that aperture's PRF throughput for the host (per sector), the Stage A kept depth (PDCSAP 6.5 ± 0.86 ppt or SAP 3.76 ± 0.84 ppt), a 15% throughput systematic and max(e_Tmag, 0.2) mag. The predeclared flux rule uses the pixel amplitude. The LC-matched columns are an added interpretive check (§8).

| Gaia DR3 source_id | role | sep (") | T (source) | flux (e-/s) | joint dchi2 vs best catalogue host | LOO dchi2 (w/o E00, E32, E33) | spatially excluded? | pixel missing flux at host (e-/s) | eclipse fraction implied by pixels | LC-matched eclipse fraction PDCSAP / SAP | pixel vs LC tension (sigma) PDCSAP / SAP | assessment |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1415338513130475136 | target | 0.0 | 13.83 (TIC v8.2) | 431.89 | 0.66 | 7.4, 0.0, 4.8 | no | 1.46 +/- 0.39 | 0.003 | 0.01+/-0.00 / 0.00+/-0.00 | 2.6 / 0.3 | spatially compatible; pixel deficit = SAP-like depth (PDCSAP 2.6 sigma higher) |
| 1415338306971353600 | listed neighbour | 27.0 | 19.57 (TIC v8.2) | 2.46 | 6.19 | 9.1, 5.5, 8.7 | no | 1.05 +/- 0.35 | 0.425 | 2.38+/-0.52 / 1.38+/-0.34 | 6.2 / 3.6 | NOT spatially excluded; pixel-amplitude feasible; making the light-curve dip would need 2.4x (PDCSAP) / 1.4x (SAP) its total flux and contradicts its pixel flux |
| 1415338337035983488 | listed neighbour | 34.9 | 19.08 (TIC v8.2) | 3.86 | 9.24 | 11.0, 6.5, 11.9 | yes | 0.75 +/- 0.33 | 0.194 | 2.53+/-0.56 / 1.46+/-0.36 | 7.2 / 4.9 | spatially excluded (dchi2 >= 9 and LOO); also cannot make the LC dip consistently with its pixel flux |
| 1415338337035990528 | listed neighbour | 39.5 | 18.43 (TIC v8.2) | 7.06 | 15.14 | 15.5, 11.7, 14.0 | yes | -0.16 +/- 0.33 | -0.022 | 1.78+/-0.39 / 1.03+/-0.26 | 8.0 / 5.9 | spatially excluded (dchi2 >= 9 and LOO); also cannot make the LC dip consistently with its pixel flux |
| 1415338405755460480 | listed neighbour | 47.4 | 18.07 (TIC v8.2) | 9.83 | 0.00 | 0.0, 10.9, 0.0 | no | 0.94 +/- 0.33 | 0.096 | 2.27+/-0.51 / 1.31+/-0.33 | 7.5 / 5.4 | NOT spatially excluded; pixel-amplitude feasible; making the light-curve dip would need 2.3x (PDCSAP) / 1.3x (SAP) its total flux and contradicts its pixel flux |
| 1415338478770171264 | additional catalogue source (<=3.6 px) | 59.7 | 20.78 (TIC v8.2) | 0.80 | 13.70 | 13.7, 10.4, 14.2 | yes | 0.08 +/- 0.31 | 0.102 | 107.49+/-60.81 / 62.10+/-35.77 | 8.2 / 6.1 | spatially excluded (dchi2 >= 9 and LOO); also cannot make the LC dip consistently with its pixel flux |
| 1415338543194431616 | additional catalogue source (<=3.6 px) | 67.9 | 19.00 (TIC v8.2) | 4.16 | 15.64 | 15.7, 12.2, 14.3 | yes | -0.20 +/- 0.34 | -0.048 | 71.19+/-15.57 / 41.13+/-10.00 | 8.5 / 6.3 | spatially excluded (dchi2 >= 9 and LOO); also cannot make the LC dip consistently with its pixel flux |
| 1415338543194435712 | additional catalogue source (<=3.6 px) | 74.2 | 16.08 (TIC v8.2) | 61.32 | 13.57 | 15.0, 10.1, 12.9 | yes | 0.25 +/- 0.36 | 0.004 | 6.72+/-1.46 / 3.88+/-0.94 | 8.6 / 6.4 | spatially excluded (dchi2 >= 9 and LOO); also cannot make the LC dip consistently with its pixel flux |

No source is flux-infeasible under the predeclared pixel-amplitude rule, because the pixel amplitudes are small. Spatially excluded (joint Δχ² ≥ 9 and ≥ 2/3 LOO ≥ 4): 1415338337035983488 (35″, borderline 9.2), 1415338337035990528 (40″), and the three extra sources. **Not excluded: 1415338306971353600 (27″) and 1415338405755460480 (47″).** Untested: unresolved companions within ~1″ of the target (no TESS sensitivity), and sources fainter than Gaia's limit.

## 8. Interpretation, kept separate from the measurements

1. **The pixel deficit matches SAP, not PDCSAP.** Per event and jointly, the target-position missing flux equals the SAP-depth expectation: LC-matched for the target at SAP depth 1.61 ± 0.25 e⁻/s against 1.46 ± 0.39 measured (0.3σ). PDCSAP needs 2.79 ± 0.32 e⁻/s, 2.6σ higher. In 97/100 target-hosted injections at the PDCSAP-matched amplitude, the joint target S/N exceeded the observed 3.73 (median 6.5). So the pixels hold only about half the dimming that PDCSAP implies, and the E32 (s79) dip is mostly a PDCSAP feature: pixel 2.1 ± 1.3 ppt, SAP 1.7 ± 1.2, PDCSAP 6.1 ± 1.2. This matches the inherited P12 eb_screen net fixed-aperture depth of −0.58 ± 1.41 ppt in s79. It weakens the case that three independent events exist. It does not by itself make the signal an artefact. E00 shows a dip in TESScut, SAP and PDCSAP alike (`figures/fig3_lightcurves_masks.png`).
2. **The listed neighbours do not fit the light curve.** If the dip is real, a listed neighbour can make it only with an eclipse of 1.03–1.46× its total flux (SAP) or 1.78–2.53× (PDCSAP). It would then also have to show 3.4–22 e⁻/s of missing flux at its own position, where the pixels measure −0.16 to 1.05 e⁻/s (tension 3.6–5.9σ at SAP depth, 6.2–8.0σ at PDCSAP depth). The 40″ star (T 18.4) needs only 1.03 ± 0.26× its flux at SAP depth, so it is excluded by the pixel-consistency tension (5.9σ), not by flux. The most compatible alternative is the 27″ star (T 19.6). It would need 1.4 ± 0.3× its flux at SAP depth, which is not a 2σ infeasibility, and it is 3.6σ in tension. Its exclusion therefore rests on the light-curve depth and the aperture-throughput model, not on localisation.
3. **What the null implies.** The joint target S/N of 3.73 would arise from noise alone in fewer than 1/130 window combinations. So it is likely some missing light comes from at or near the target pixel. But the predeclared rule, which includes the look-elsewhere search, was not met, and an unresolved source within ~1 px (≈ 21″) is not tested.
4. No relative likelihood here is a host probability, and none is a planet probability.

## 9. Recovery and null tests (actual sample sizes)

Controls are out-of-event windows on a 4-h grid in the same sectors, never overlapping any predicted event window under either ephemeris. There are 130 per sector, of which only 34–35 are mutually independent. Joint realisations pair one window per sector. Only 11 of the 130 joint null combinations use independent windows in all three sectors. Injections reuse those windows, so effective independent sample sizes are about 35 per sector, not 100. Only the host's modelled PRF contribution is subtracted (trapezoid, 10-min ingress, integrated over each 200-s cadence). Odd-numbered realisations use a perturbed injected PRF (width × U(0.9, 1.1), position N(0, 0.1 px)), while the fit always uses the nominal PRF. Neighbour amplitudes that would exceed the host's total flux are capped at 100% eclipse and marked "capped". Those hosts **cannot** reproduce the light-curve dip.

| Null quantity | value |
|---|---|
| null windows per sector (all / independent) | 57: 130/35, 79: 130/34, 80: 130/34 |
| joint null combinations (all-independent) | 130 (11) |
| kappa (calibration half, V2 recipe) | s57 1.042, s79 0.997, s80 1.042, s84 0.998 |
| joint target S/N under the null: mean, std | 0.13, 1.07 |
| null fraction with joint target S/N >= 3 / >= 3.73 (real) | 0.008 / 0.000 (of 130) |
| joint free improvement Lambda: p50 / p90 / p95 / p99 | 10.8 / 16.6 / 18.1 / 56.3 (real 33.8; null fraction >= real 0.023) |
| consistency Q: p50 / p90 / p95 / p99 | 11.8 / 18.4 / 20.8 / 40.4 (real 19.2; null fraction >= real 0.085; textbook chi2(4) p 7.1e-04) |
| per-event max dimming S/N over the box, null p95 / p99 | s57 3.46 / 3.86; s79 4.00 / 4.78; s80 3.95 / 9.60 |
| pixel-detection rule fired on joint nulls | 0.000 |
| best catalogue host under the null (joint) | 475136: 27, 353600: 11, 983488: 9, 990528: 8, 460480: 24, 171264: 21, 431616: 14, 435712: 16 |

| Injection config (host; amplitude) | A injected s57/s79/s80 (e-/s) | capped? | coverage of 95.45% region | best catalogue host = true host | all other hosts excluded (dchi2 >= 9) | assigned to target | pixel-detection rule fired | median offset of joint best from true host | median joint target S/N |
|---|---|---|---|---|---|---|---|---|---|
| target_LC (475136; LC-matched (PDCSAP 6.5 ppt)) | 2.66 / 3.01 / 2.76 | no | 86/100 (86%; 78-91%) | 98/100 (98%; 93-99%) | 94/100 (94%; 88-97%) | 98/100 (98%; 93-99%) | 35/100 (35%; 26-45%) | 4.1" | 6.46 |
| target_PIX (475136; pixel-matched (1.459 e-/s)) | 1.46 / 1.46 / 1.46 | no | 78/100 (78%; 69-85%) | 89/100 (89%; 81-94%) | 49/100 (49%; 39-59%) | 89/100 (89%; 81-94%) | 1/100 (1%; 0-5%) | 10.4" | 3.48 |
| nb353600_LC (353600; LC-matched in the SPOC aperture, capped at host flux) | 2.45 / 2.49 / 2.43 | yes (needs 1.89/3.63/2.76 x host flux) | 89/100 (89%; 81-94%) | 87/100 (87%; 79-92%) | 34/100 (34%; 25-44%) | 0/100 (0%; 0-4%) | 18/100 (18%; 12-27%) | 3.9" | 2.60 |
| nb353600_PIX (353600; pixel-matched (1.459 e-/s), capped) | 1.46 / 1.46 / 1.46 | no | 83/100 (83%; 74-89%) | 74/100 (74%; 65-82%) | 1/100 (1%; 0-5%) | 4/100 (4%; 2-10%) | 0/100 (0%; 0-4%) | 7.7" | 1.58 |
| nb983488_LC (983488; LC-matched in the SPOC aperture, capped at host flux) | 3.85 / 3.92 / 3.82 | yes (needs 1.92/5.09/3.25 x host flux) | 90/100 (90%; 83-94%) | 95/100 (95%; 89-98%) | 65/100 (65%; 55-74%) | 0/100 (0%; 0-4%) | 25/100 (25%; 18-34%) | 2.4" | 2.37 |
| nb983488_PIX (983488; pixel-matched (1.459 e-/s), capped) | 1.46 / 1.46 / 1.46 | no | 85/100 (85%; 77-91%) | 66/100 (66%; 56-75%) | 2/100 (2%; 1-7%) | 2/100 (2%; 1-7%) | 0/100 (0%; 0-4%) | 6.9" | 0.99 |
| nb990528_LC (990528; LC-matched in the SPOC aperture, capped at host flux) | 7.04 / 7.16 / 6.98 | yes (needs 1.40/4.10/2.05 x host flux) | 89/100 (89%; 81-94%) | 100/100 (100%; 96-100%) | 100/100 (100%; 96-100%) | 0/100 (0%; 0-4%) | 54/100 (54%; 44-63%) | 1.4" | 3.16 |
| nb990528_PIX (990528; pixel-matched (1.459 e-/s), capped) | 1.46 / 1.46 / 1.46 | no | 79/100 (79%; 70-86%) | 89/100 (89%; 81-94%) | 48/100 (48%; 38-58%) | 1/100 (1%; 0-5%) | 0/100 (0%; 0-4%) | 8.1" | 0.71 |
| nb460480_LC (460480; LC-matched in the SPOC aperture, capped at host flux) | 9.80 / 9.97 / 9.71 | yes (needs 3.35/4.85/1.71 x host flux) | 73/100 (73%; 64-81%) | 100/100 (100%; 96-100%) | 100/100 (100%; 96-100%) | 0/100 (0%; 0-4%) | 5/100 (5%; 2-11%) | 1.0" | 1.65 |
| nb460480_PIX (460480; pixel-matched (1.459 e-/s), capped) | 1.46 / 1.46 / 1.46 | no | 83/100 (83%; 74-89%) | 97/100 (97%; 92-99%) | 71/100 (71%; 61-79%) | 0/100 (0%; 0-4%) | 0/100 (0%; 0-4%) | 6.8" | 0.33 |
| nb435712_LC (435712; LC-matched, capped) | 61.15 / 62.20 / 60.62 | yes (needs 7.30/5.69/7.93 x host flux) | 57/100 (57%; 47-66%) | 100/100 (100%; 96-100%) | 100/100 (100%; 96-100%) | 0/100 (0%; 0-4%) | 0/100 (0%; 0-4%) | 0.6" | -8.92 |

Perturbed-PRF half vs unperturbed half, coverage of the 95.45% region: target_LC: 0.80 vs 0.92; target_PIX: 0.76 vs 0.80; nb353600_LC: 0.84 vs 0.94; nb353600_PIX: 0.78 vs 0.88; nb983488_LC: 0.84 vs 0.96; nb983488_PIX: 0.84 vs 0.86; nb990528_LC: 0.82 vs 0.96; nb990528_PIX: 0.80 vs 0.78; nb460480_LC: 0.50 vs 0.96; nb460480_PIX: 0.80 vs 0.86; nb435712_LC: 0.14 vs 1.00.

Summary of the calibration. At the PDCSAP-matched amplitude (2.66–3.01 e⁻/s), a target-hosted signal would have been localised: 98% assigned to the target, 94% with every other host excluded, 86% coverage. At the measured 1.46 e⁻/s, it would not: 89% assigned to the target, 49% with every other host excluded, 78% coverage. Neighbour-hosted signals of the same 1.46 e⁻/s are rarely assigned to the target (0–4%), but they exclude the target at Δχ² ≥ 9 in only 66–79%. PRF mismatch matters. When the injected PRF is perturbed (width ±10%, 0.1-px offset) but fitted with the nominal PRF, coverage drops: 0.80 vs 0.92 for target_LC, and 0.14–0.50 vs 0.96–1.00 for the bright full-eclipse neighbour cases. So the formal contours understate the true uncertainty whenever the PRF is imperfect, most of all at high S/N. At the observed amplitude the drop is small (0.76 vs 0.80), because noise and unrelated structure dominate there. These are empirical frequencies from ~35 independent windows per sector. They do not demonstrate a 3σ tail or 99.9% reliability.

## 10. Sensitivity (small, predeclared)

| Variant | joint free best (xi, eta) | free improvement | Q | target A (e-/s) | target S/N | target dchi2 vs free | best catalogue host | per-event target S/N (E00, E32, E33, E39) |
|---|---|---|---|---|---|---|---|---|
| primary (E_A, V2 baseline, TESS PRF) | (-9, -56) | 33.8 | 19.2 | 1.46 +/- 0.39 | 3.73 | 18.8 | 460480 | 2.59, 1.67, 2.35, 0.54 |
| S_EF_windows | (-10, -55) | 35.3 | 19.2 | 1.55 +/- 0.42 | 3.67 | 21.1 | 460480 | 2.54, 1.70, 2.20, 1.04 |
| S_quadratic_baseline | (-6, -61) | 24.0 | 17.2 | 1.72 +/- 0.50 | 3.43 | 10.7 | 475136 | 2.39, 1.22, 2.47, -0.85 |
| S_V0_original_recipe | (-9, -57) | 18.8 | 14.5 | 1.31 +/- 0.50 | 2.63 | 11.3 | 475136 | 2.43, 1.22, 0.36, 0.54 |
| S_gaussian_prf | (-9, -53) | 28.3 | 18.7 | 1.40 +/- 0.36 | 3.92 | 12.3 | 460480 | 2.53, 2.00, 2.36, 0.76 |

Across variants the joint target S/N is 2.6–3.9, and the free best stays at the E32-driven location. The best catalogue host alternates between the target and 1415338405755460480, which is itself evidence that the hosts are not separated. The sector 84 diagnostic (E39, never pooled) shows no deficit at the target (0.42 ± 0.76 e⁻/s) and a weak (S/N ~2.5) bump near the 27–35″ neighbours.

## 11. Inherited facts, new measurements, adopted assumptions

- **Inherited (P12 records, unverified physics)**: Stage A events, depths, keep/exclude decisions and the survey ephemeris; the packet fit; P12 centroid shifts and F5/K7/K9 records; TRICERATOPS FPP 0.049 (computed on sectors 57/77/78, two of which contain no transit); the tier-2 label.
- **Verified provenance claim**: `rules_p12.py::centroid_support` (lines 209–221) uses r3 = 3 × `shift_err_px`. That is the error of the blended-light *centroid displacement* from `centroid.py` (lines 173–177: MAD of out-of-transit centroids / √N_in). It is used as a source-position region and compared with neighbour separations (`sep_px − tot ≤ r3`). The depth fraction 0.0066 enters only the "capable neighbour" selection. A source-position error from that route would be about shift_err/depth, roughly 0.6 px per sector, not the 0.004–0.009 px used. The frozen implementation was not patched or executed, and its verdict is not used as evidence.
- **New measurements**: everything in §§3–10 marked as fitted or measured.
- **Adopted assumptions**: TIC v8.2 magnitudes (±0.2 mag) for neighbours; official PRF accuracy at the 1–5% level (README) plus a 15% throughput systematic in the LC-matched check; σ_reg floor 0.1 px; no proper motion for a hypothetical uncatalogued source; the Stage A kept depths as "the observed signal".
- **Unresolved companions**: target RUWE 1.10, ipd_frac_multi_peak 0, astrometric_excess_noise_sig 2.2. A companion within ~0.5″, or fainter than ΔG ≈ 4 within ~1″, is not excluded by anything here.

## 12. Limitations, integrity and reproduction

- Weak signal: per-event target S/N is 1.7–2.6. The free search over the 11×11 box is limited by unrelated structure, such as residuals of the T≈11.7 star in s57 and the stripe pattern in s79. The fit box and 4.5-px grid were predeclared and not tuned.
- Two method revisions (R1 before any event fit; R2 after first sight) are disclosed above and applied identically to real, null and injected data.
- Joint null and injection realisations reuse overlapping windows: about 35 independent per sector, and only 11 fully independent joint null combinations.
- s77/s78 contain no in-transit data. s84 is diagnostic only.
- **Integrity**: `inputs/integrity_before.json` and `inputs/integrity_after.json` cover exactly the 48 historical files read: packet, case records, 6 TESScut cubes, 6 TESS-SPOC light curves, `centroid.py`, `rules_p12.py`, and the sector policy. Result: see `inputs/integrity_compare.json` (0 changed, 0 missing). No P1–P12 file was written. No git operation was performed. No automation was enabled. Nothing was submitted.

Reproduce (Git Bash, from `followup/tic332366289_localisation_v1/code`, with `PYTHONDONTWRITEBYTECODE=1` and the venv python `C:/Users/seanj/Downloads/tesshunter_venv/Scripts/python.exe`):

```
python -B integrity.py before
python -B fetch_inputs.py all          # PRF grid files, Gaia DR3 cone, TIC cone (bounded, 1 retry)
python -B inspect_inputs.py            # FITS metadata + TESScut/TESS-SPOC time cross-check
python -B events.py                    # events.csv, masks, control windows
python -B run_scene.py                 # scene, registration, neighbours (pre-assessment)
python -B run_kappa.py                 # kappa (calibration half) -- original recipe
python -B run_noise_diag.py            # R1 selection on calibration-half nulls
python -B run_kappa.py                 # kappa with the R1 recipe
python -B run_real.py                  # per-event, joint, LOO, registration MC, sensitivity
python -B run_controls.py smoke        # 5 per configuration
python -B run_controls.py full         # 130 nulls/sector, 100 joint injections per configuration
python -B decide.py                    # predeclared decision + host assessment + neighbours.csv
python -B diagnostics.py               # stripe / baseline-adequacy / per-event depth diagnostics
python -B figures.py                   # figures/
python -B provenance.py                # versions, pixel_inputs.csv, compact arrays
python -B make_tables.py               # fills this report from the result JSONs
python -B integrity.py after
python -B -m pytest -p no:cacheprovider -q ../tests/test_localisation.py
```

Completed: every step of the prompt for the primary sectors. Not done: injections in s84, which is diagnostic only. No probabilistic host model was built, as the prompt does not require one. TRICERATOPS and population work were not rerun, by design.

**Next decisive measurement.** Seeing-limited ground-based time-series photometry at predicted transit times, with an aperture well under 20″ around the target. The 25–48″ neighbours separate trivially. It needs about 1–2 ppt precision per 10–15 min on the target (G 15.1, an M dwarf; observe in I/z), and it can watch the four neighbours for deep eclipses in the same frames. For cycles 78–97 (BTJD 4332–4688, late 2026 to 2027) the E_A and E_F centres agree within 5 min, and the packet-fit 1σ timing uncertainty is 22–27 min (P ± 0.00019 d, T0 ± 0.0054 d), so windows should cover about ±1.5 h around the predicted centre. A complementary step is a fresh TESS sector with the same pixel recipe, which would add an independent event at no cost. Also, if a future pass revisits P12, the SAP/PDCSAP depth disagreement (E32 especially) should be examined at the light-curve level first.

## 13. Files

`PLAN.md`, `config.json`, `events.csv`, `neighbours.csv`, `LOCALISATION_REPORT.md`; `inputs/` (hashes, provenance, versions, catalogue queries, pixel inputs); `results/` (`events.json`, `masks/`, `controls.csv`, `scene.json`, `kappa.json`, `noise_model_revision.json`, `real_events.json`, `joint.json`, `sensitivity.json`, `controls_full*/`, `decision.json`, `host_assessment.json`, `diagnostics.json`, `arrays_compact/`); `figures/` (fig1 scene, fig2 per-event signed difference / model / residual images, fig3 local light curves with masks, fig4 common sky map, fig5 controls, fig6 hosts; `quicklook_diffimages.png` is the first inspection figure of the signed fits, kept because it is what prompted revision R2); `code/`, `tests/`, `logs/`. Large arrays live at `D:\tesshunter_followup\tic332366289_localisation_v1\` (9.9 MB) and are excluded from the bundle.
