# TIC 9066956: evidence vetting and remaining ambiguities

Claude session, 2026-10-06 (checks run 15:40-16:00 local / ~19:40-20:00 UTC). Read-only on every earlier artifact; no pipeline label changed, nothing submitted.

## Inputs reviewed

| Source | Location | What it is |
| --- | --- | --- |
| Survey (10/5, Codex) | `D:\tesshunter_surveys\20261005_survey2000` (report zip in `reports/`), workspace `C:\Users\seanj\Documents\Codex\2026-10-05\review-my-tesshunter-p12-project-history` | Frozen-P12 search; candidate `tic9066956_p01`, supplement batch (446 stars), the only SUBMIT with D complete (tier 2, "unlocalised") |
| Follow-up (10/5-10/6, Codex) | `C:\Users\seanj\Documents\Codex\2026-10-05\can-you-look-at-all-the` | Earlier-sector recurrence, ZTF, PRF localisation (`host906/`), physical classification (`class906/`), FPP reruns, XP, DSS/PS1 imaging, triple fits, activity (`class906v2/`, `TIC9066956_Existing_Data_Update.txt`) |

## Candidate

P = 0.71344765117 ± 0.00000060 d, T0 = 3182.8243523 ± 0.0006 BTJD (six-sector refit; formal errors). Depth ~5.6 ppt, duration 0.72 h, b ~0.65. Host: Gaia DR3 2432763248476007296, 89.4 pc, G 15.12, Tmag 13.86, BP-RP 2.76, M_G 10.36, RUWE 1.095. Rp 2.87 ± 0.31 R⊕ (pipeline, R* 0.365); 2.6-3.4 R⊕ across every planet-host architecture tested. Insolation ~125 S⊕, Teq ~930 K.

## What I checked independently (new in this session)

1. **Recurrence, my own code on the archival FITS** (`scripts/recur.py`, `results/recur.json`). wotan biweight 0.5 d, exposure-integrated fixed-duration box, 300 random-phase nulls per sector. Ephemeris = the survey's, which was derived from sectors 69/70/92 only, so sectors 2/29/42 are a retrodiction ~2,560 cycles back.

   | Sector (product, cadence) | Box depth (ppt) | Null-calibrated SNR |
   | --- | --- | --- |
   | 2 (TESS-SPOC, 1800 s) | 3.45 ± 0.47 | 7.4 |
   | 29 (TESS-SPOC, 600 s) | 4.13 ± 0.55 | 8.8 |
   | 42 (TESS-SPOC, 600 s) | 4.26 ± 0.56 | 10.9 |
   | 69 (TESS-SPOC, 200 s) | 4.35 ± 0.52 | 13.8 |
   | 70 (TESS-SPOC, 200 s) | 4.48 ± 0.52 | 7.6 |
   | 92 (QLP, 200 s) | 3.66 ± 0.92 | 3.7 |

   0/300 nulls reached the observed depth in any sector. Combined: depth 4.07 ± 0.23 ppt, sector-to-sector chi2 2.96/5 (stable over 2018-2025). Early-only (prospective) 3.89 ± 0.30 ppt. Odd 4.24 ± 0.32 vs even 3.91 ± 0.32 (0.7 sigma). Phase 0.5: -0.20 ± 0.23 ppt (no secondary; 3-sigma upper limit ~0.5 ppt). Box depths sit below the fitted 5.6 ppt because a full-duration box averages over ingress/egress. This reproduces the Codex recurrence (4.77 ± 0.40 ppt, 98 windows) with a different detrender and estimator.
   - **Resolves the survey caution about sector 69** (fixed-aperture 0.85 ± 0.72 ppt): TESS-SPOC s69 gives 4.35 ± 0.52 ppt, so the low value came from the extreme positive excursions in that aperture series, not from a missing signal.

2. **Unused-data check.** MAST lists no 2-min data and no K2 data; the EPIC entry is catalogue-only. TESScut lists **sector 96** (Aug-Sep 2025), but the cutout shows the star ~10 px outside the science array: the cutout's first column is CCD column 22, the star falls at about column 35, and science pixels start at about 45. The flux there is zero, and no QLP, TESS-SPOC or TARS product exists for s96 (`results/s96_result.json`; its depth numbers are meaningless and should not be read). **The six sectors 2/29/42/69/70/92 are the complete TESS record.** The memory gotcha "Tesscut.get_sectors off-array" applies again.

3. **Novelty, live.** ExoFOP TOI list (8,148 rows, modified 2026-10-06 19:33 UTC) and CTOI list (5,137 rows) have no entry for TIC 9066956 and no period-alias candidate within 1°. The nearest TOIs (373.01 / 6731.01, P 1.632 d) are on different stars. No literature hits for the TIC, Gaia or 2MASS IDs. The VizieR cone (3") finds no variable-star, EB or planet-candidate catalogue (`results/cats.txt`).

4. **Overluminosity explanations** (`results/context.json`, `results/cats.txt`). The 0.45-0.72 mag CMD excess (Codex) needs youth, high metallicity or multiplicity.
   - Kinematics: UVW_LSR = (12.7, -41.3, -3.0) km/s, thin disk (TD/D 0.03) but lagging by ~40 km/s. Kinematically old; not a young moving-group velocity.
   - Gaia ESP-ELS Hα pseudo-EW +0.10 ± 0.07 Å: no emission, so not an active young M dwarf.
   - Metallicity from three XP-based estimates: [Fe/H] -0.03 (J/ApJ/984/58), StarHorse -0.08 / -0.17 ± 0.11, Gaia MSC -0.07. Roughly solar, not the ~+0.4 needed to raise the locus 0.6 mag. All three are XP pipelines with known M-dwarf systematics, so this is supporting, not decisive.
   - Net: an unresolved near-equal binary is the leading single explanation. It is still not demonstrated: the excess is ~1.5x the field-locus scatter, the Teff scale moves it (R(Teff) 0.285 at 3300 K vs 0.337 at 3400 K, against R(M_K) 0.364), and RUWE is blind to near-equal pairs, whose photocentre barely moves.
   - Gaia DR3 three-band dispersion (J/A+A/677/A137): ~14 mmag intrinsic G scatter, flagged variable in G/BP/RP. Consistent with slow spot modulation on an old M dwarf; not explained, not a transit effect.

5. **The surviving stellar alternative, inspected** (`class906v2/results/continuous_models.json`). Best diluted triple: chi2 380.80 vs planet 370.09.
   - Inner pair: 0.085 + 0.085 M☉, P_in = 1.427 d, b = 1.09 (grazing). R = 0.158 R☉ against the model 0.114 (x1.39) and Teff 2268 K against the model 2570 (-12%). Inflation, cooling and mass are free, not at bounds; only the mass ratio sits at its bound of 1.0.
   - Measured inflation in low-mass EBs is typically ~5-15%, and the host is kinematically old, so this solution leans on an extreme activity term.
   - Without the cooling freedom it is chi2 386.48 (+16.4 vs planet) and still needs x1.31 inflation.
   - **Predicted transit depth by band** (from the saved models):

     | Band | Planet | Best triple | No-cooling triple |
     | --- | --- | --- | --- |
     | g | 5.67 ppt | 0.67 | 0.71 |
     | r | 5.64 | 1.24 | 1.27 |
     | i | 5.62 | 3.92 | 4.13 |
     | T | 5.61 | 6.33 | 6.70 |
     | K | 5.40 | 18.1 | 19.2 |

     **A single ground-based transit in r' (or g'/r'/i'/z' simultaneously) separates these by ~4.4 ppt.** That is the cheapest decisive test of the main false-positive loophole.

6. **Population context** (NASA Exoplanet Archive pscomppars, `scripts/pop.py`). There are 34 confirmed planets with P < 1 d around hosts with Teff < 4000 K, and **0 have Rp > 2.5 R⊕**. K2-22 b (2.3 R⊕, 0.38 d) is a disintegrating dust-tail object. In insolation the closest analogs exist: TOI-756 b (2.81 R⊕, 1.24 d, 127 S⊕) and TOI-4479 b (2.82 R⊕, 1.16 d, 93 S⊕). If it is a planet, it would be the shortest-period >2.5 R⊕ planet known around an M dwarf. That lowers its prior, as the Codex FPP sensitivity runs show (flat radius prior 9.8%), and raises its value if real. The orbit lies outside the Roche limit for sub-Neptune densities: a/R* 6.3 against ~4.4-5.5 for ρ_p 1.6-0.8 g/cc.

## Audit of the earlier evidence (what holds, what is soft)

**Holds:**
- Astrophysical, strictly periodic signal over 7 years.
- Earlier-sector retrodiction, reproduced here.
- No secondary eclipse.
- Odd and even depths consistent.
- Known neighbours excluded: PRF localisation prefers the target in all 14 configurations, and injected neighbour hosts are recovered at the neighbour 1600/1600 times. ZTF also independently excludes the ~32% eclipse the 12.8" neighbour would need, at 2 epochs.
- Ordinary EB, 2P EB and compact brown dwarf disfavoured by shape and SED (Δscore +25 to +55 across sensitivity refits).
- 1953 POSS plate: nothing at the current position to r ≈ 20.7.

**Soft or conditional:**
- FPP 1.79% (refit) / 2.39% (pipeline) is almost entirely "planet on an unresolved companion", which is still a planet. The stellar-eclipse share inside TRICERATOPS is 0.03%. But TRICERATOPS cannot sample companions < 0.1 M☉, so the surviving triple is outside its model.
- Fit-score differences are not posterior odds.
- XP SED fit: single and two-star fits are equal, and equal-temperature multiplicity is exactly degenerate.
- APOGEE: 2 visits with S/N < 1 and no velocities. The Gaia RV (-9.4 ± 4.0 km/s) is not an amplitude constraint.

**Minor documentation inconsistencies (no effect on conclusions):**
- `evidence/history/12_SURVEY_PLAN.txt` describes a "300-star" search, but the supplement selected 446 and the bundle is titled 1,998 stars.
- The host906 assessment notes two depth-capable Gaia neighbours behind a zero summary count; both are in the FPP scene.

## Remaining ambiguities, ranked

1. **Planet vs. a bound, diluted eclipsing pair (hierarchical triple).** Disfavoured (Δchi2 +10.7, physically strained, low prior), but not excluded by any existing data or by TRICERATOPS. *Test:* one transit in r' and/or g' (planet 5.6 ppt, triple ≤ 1.3 ppt); MuSCAT-style g'/r'/i'/z_s is ideal. NIR (J/K) also separates them (5.4 vs ~18 ppt).
2. **Host multiplicity and which star hosts the transit.** Overluminous by ~0.6 mag with old kinematics, solar-ish XP metallicity and no Hα, so a near-equal binary is plausible. This changes Rp (2.6 → 3.4 R⊕) and the host assignment, not the planetary nature. *Test:* AO/speckle (≥ 0.05-0.1", i.e. 4.5-9 au) plus a high-resolution spectrum (SB2 search). A contrast curve would also likely push the TRICERATOPS FPP below the 1.5% validation line, since FPP here is mostly the companion-host scenario.
3. **Unresolved background source within ~1".** Constrained by the 1953 plate (r < 20.7 at the current position), Gaia (≥ ~1"), PS1 (Δmag ~4 at 3") and b = -68°. Residual space: very red, faint backgrounds at r ≳ 20.7 within ~1". *Test:* the same ground transit, seeing-limited, plus AO.
4. **Mass and composition.** None measured. For 10 M⊕, K ≈ 14 m/s (J = 12.2); feasible on a red-optical/NIR precision RV instrument but expensive. RV of the bright star alone cannot exclude the faint-triple scenario.
5. **Prior and rarity.** No known >2.5 R⊕ planet at P < 1 d around an M dwarf, so FPP is prior-sensitive (1.8% → 9.8% with a flat radius prior). This is an interpretive ambiguity, not a data gap.

**Not ambiguous any more:**
- Signal reality and periodicity.
- The sector-69 weakness.
- Missing TESS data (s96 is off-silicon).
- The known neighbours as the source.
- Current novelty (not a TOI/CTOI as of 2026-10-06 19:58 UTC).

## Ephemeris for scheduling

P = 0.71344765117 d, T0 = 2460182.8243523 BJD_TDB. Projected 1σ timing uncertainty is ~1.6 min in late 2026 and ~2 min by mid-2027 (formal covariance; add margin for template systematics). The 43-min transit needs ≥ 2 h windows.

## Reproduce

Python: `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe`. Scripts are in `scripts/`. `recur.py` reads the FITS under the Codex follow-up `new_data/earlier/.../mast_cache` and the survey's `D:` acquisition folder. `s96.py` downloads a 25x25 TESScut cube (136 MB, left in the session scratchpad, not copied here).
