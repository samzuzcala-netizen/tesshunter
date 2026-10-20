# Candidate packet: TIC 382302559, P = 83.80625 d

Generated 2026-09-03 07:17 UTC by tesshunter. This is a CANDIDATE. Nothing in this packet is a detection; the automated checks are necessary, not sufficient. The human reviews and submits.

**Automated verdict:** ambiguous / manual vetting required (light curve only: promising planet candidate)  
**FPP / NFPP (TRICERATOPS):** 1.0000 / 0.0000 — above 0.5, does not proceed to submission

## Fitted parameters (limb-darkened transit fit)

| parameter | value |
|---|---|
| period | 83.806247 +/- 0.001873 d |
| epoch | 1361.46540 +/- 0.03728 BTJD = 2458361.46540 BJD |
| duration T14 | 17.564 +/- 5.558 h |
| depth (model maximum) | 1.8523 +/- 1.2107 ppt (shape-degenerate error 0.6310 ppt) |
| depth (duration-averaged) | 1.5873 ppt |
| Rp/R* | 0.0398 +/- 0.0210 |
| a/R* | 36.19 +/- 95.56 (catalog density gives 89.02 +/- 6.40) |
| impact parameter | 0.31 +/- 7.75 ; inclination 89.51 deg |
| Rp | 3.87 +/- 2.05 R_Earth = 0.345 +/- 0.183 R_Jup (R* = 0.890 +/- 0.047 R_Sun) |
| stellar density | fit (free) 0.128 g/cc vs catalog 1.900 +/- 0.410 g/cc; ratio 0.07, profile delta chi2 199.0; prior adopted: False; inconsistent: False |
| limb darkening | u1 = 0.355, u2 = 0.249 (claret2017_atlas (Teff 5452 K, logg 4.52)) |
| fit | least_squares, 1376 points, 12 transits, reduced chi2 21.59, delta BIC vs flat 917 |
| BLS | SNR 56.8, box depth 3.142 ppt, 11 transits observed, alias label P |

## Vetting checks

| check | result |
|---|---|
| odd/even (median) | pass (1.1 sigma) |
| odd/even (fit template) | odd 5.282 +/- 3.867 ppt (3 events), even 0.909 +/- 1.401 ppt (9 events), difference 1.1 sigma, 141% of the mean |
| secondary at phase 0.5 | -0.0278 ppt measured; deepest planetary secondary at the fitted a/R* 0.0012 ppt; not detected |
| a/R* consistency | pass — free-fit a/R* = 36.19 (b = 0.31) against 89.02 +/- 6.40 from the catalog density (0.128 vs 1.900 g/cc, ratio 0.07; profile delta chi2 199.0 with a/R* held in the catalog range, 8.0 after the red-noise |
| V-shape | none (t_flat/t_total 0.95); fitted geometry grazing: False |
| per-unit depths | FLAG |
| centroid | shift 0.007 px, 8.2 sigma FLAG |
| contamination | flagged, 37 neighbours checked |
| FPP / NFPP | 1.0000 / 0.0000 (TRICERATOPS 1.1.0: FPP 1.0000, NFPP 0.0000 over 18 scenarios and 100 TIC stars within 10 px; aperture circular_from_tmag; 100000 draws; fold binned (150 points, error 709 ppm); sectors [1, 2, 3].) |

Flags: in-transit centroid shift 0.007 px (0.1 arcsec, 8.2 sigma) over 11 sector(s) — signal may sit on a neighbour; per-unit transit depths disagree by > 3σ across observing units

## Completeness at this SNR

Matched-filter SNR 35.8 on this star's detrended data binned to 30 min: the P2 completeness curve (`docs/COMPLETENESS.md`, 2100 injections on 300 stars, config survey_v1) recovers 0.62 of injected signals at this SNR (SNR50 = 26.5, SNR90 = 97.6; the 20-50 bin recovered 237/368). Curve measured in P2 with batman injections into the survey preset (survey_v1: FFI stitches binned to 30 min, periods 1-40 d, Rp/R* 0.01-0.12); the matched-filter SNR here is computed on this candidate's own detrended data with the same definition. Outside that regime the number is an extrapolation.

## Star and neighbours

TIC 382302559: Teff 5452 K, log g 4.52, R = 0.890 +/- 0.047 R_Sun, M = 0.950 +/- 0.118 M_Sun, Tmag 12.05, TIC contamination ratio 0.0056 (source tic; assumed errors: False).

| ID | dstArcSec | Tmag | GAIAmag | gaiabp | gaiarp | Teff | rad | contratio | disposition |
|---|---|---|---|---|---|---|---|---|---|
| 382302559 | 0.00 | 12.05 | 12.56 | 12.97 | 12.00 | 5452.00 | 0.89 | 0.01 | n/a |
| 734522109 | 14.47 | 18.45 | 18.95 | 19.30 | 18.33 | 5487.00 | n/a | n/a | n/a |
| 734522108 | 26.07 | 18.66 | 19.47 | 20.05 | 18.34 | n/a | n/a | n/a | n/a |
| 734522106 | 29.01 | 18.90 | 19.67 | 20.28 | 18.70 | n/a | n/a | n/a | n/a |
| 382302560 | 44.85 | 19.26 | 19.94 | 19.33 | 17.96 | n/a | n/a | n/a | n/a |
| 382302562 | 58.31 | 17.97 | 18.94 | 20.04 | 17.91 | 3796.00 | 0.47 | n/a | n/a |

## Cross-match

CLEAN: TIC 382302559 absent from all sources (neighbours checked)  
Catalog versions: `ctoi=2026-09-03:f6964541;nasa_ps=2026-09-03:85f3c196;nasa_pscomppars=2026-09-03:4843e49c;spoc_tce=2026-09-03:e580dde7;tess_eb=2026-09-03:43555226;toi=2026-09-03:4704bb7c`

## Data

Sectors [1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 61, 62, 63, 64, 65, 66, 67, 68, 69, 87, 88, 89, 90, 93, 94, 95, 96, 97, 98]; 48971 raw and 46934 cleaned cadences; products: TESS-SPOC s1, TESS-SPOC s2, TESS-SPOC s3, TESS-SPOC s4, TESS-SPOC s6, TESS-SPOC s7.

## Figure

![summary](summary.png)

## ExoFOP CTOI fields

```json
{
 "target": "TIC 382302559",
 "tic_id": 382302559,
 "discovery_source": "TESS",
 "period_days": 83.80624673157028,
 "period_err_days": 0.0018732785531390826,
 "epoch_bjd": 2458361.465398601,
 "epoch_err_days": 0.03728140290311984,
 "depth_ppm": 1852.3073277183498,
 "depth_err_ppm": 1210.7177822066276,
 "duration_hours": 17.56434714938843,
 "duration_err_hours": 5.557890921925445,
 "disposition": "PC",
 "tag": "FILL_ME: YYYYMMDD_username_tesshunter_NNN",
 "candidate_name": null,
 "paper_url": null,
 "notes": "Survey rank 7 (frozen score 3.5); survey stitch SNR 56.81797108204427, 11.0 transits."
}
```

_The pipeline finds candidates. It does not submit._
