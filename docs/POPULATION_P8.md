# The prompt-8 population: mid-to-late M dwarfs at 200-second cadence

Generated 2026-09-04T23:32:22Z by `scripts/build_p8_population.py all --seed 20260904` (this memo: `scripts/write_population_p8_memo.py`). Population counts come from `data/survey/population_p8.json`; the later sections name their neighbour, completeness and yield records. [M] measured in prompt 8, [A] adopted, [P1] taken from prompt 1. The pipeline finds candidates; nothing here is a detection.

## 1. Definition [A]

* Stars: TIC Teff below 3600 K, TIC radius below 0.45 Rsun, TIC luminosity class dwarf where given, and the Gaia-based main-sequence check of section 3.
* Brightness: Tmag 12.5 to 14.0 (ceiling extension to 14.5 only on the coverage measurement of section 4).
* Sky: |b| >= 20 deg.
* Sectors: at least 3 sectors at 200-s cadence (sector 56 onward) with a QLP or TESS-SPOC light curve; sectors 27-55 (600 s) and 1-26 (1800 s) recorded per star, not counted.
* FFI-only: n_2min_sectors_in_search < n_search_sectors / 2 (strict minority); search sectors = sectors >= 56 with a QLP or TESS-SPOC light curve.
* Hard stop: CLEAN under the prompt-1 cross-match with freshly downloaded catalogs; FLAG excluded.
* Size: 1000 to 2000; if more qualify, per-star expected new signals under the prompt-1 model (survey_yield: DC15 grid, 0.5-30 d, faint_m priors mid, photon-noise model), sectors = 200-s sectors with a light curve.

## 2. The query and the counts [M]

The TIC was queried over the whole sky in 36 declination strips of 5 deg on Tmag [12.5, 14.5], Teff [2000.0, 3600.0] K, radius [0.01, 0.5] Rsun, objType STAR (2026-09-04T22:12:47Z): 182,423 rows, 182,423 unique, 117,171 at |b| >= 20. Sectors per star come from the vendored tess-point, capped at sector 105 (the latest with a public QLP target list on 2026-09-04). Light-curve presence per sector comes from the QLP and TESS-SPOC per-sector target lists (missing lists: {'qlp': [], 'tess-spoc': [86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105]}); SPOC 2-minute presence from MIT per-sector 2-minute target lists (tess.mit.edu/public/target_lists) (sectors without a list: none).

| cut, in order | stars left |
|---|---:|
| query_pool_abs_b | 117,171 |
| teff_lt_3600 | 116,935 |
| radius_lt_0.45 | 91,064 |
| lumclass_dwarf_or_missing | 91,064 |
| lumclass_missing_kept | 0 |
| tmag_12.5_to_14 | 43,772 |
| gaia_dwarf_pass | 40,216 |
| ge_3_sectors_200s_with_lc | 11,069 |
| zero_2min_sectors_in_search | 9,285 |
| minority_2min_sectors_in_search | 10,512 |
| ffi_only_minority | 10,512 |
| hard_stop_clean | 9,989 |

Gaia dwarf-check outcomes on the stars reaching that cut: pass 40,216, no_parallax 3,251, overluminous_for_colour 243, underluminous_for_colour 62.
Hard-stop status on the stars reaching that cut: CLEAN 9,989, REJECT 493, FLAG 30. Catalog stamp `ctoi=2026-09-04:f6964541;nasa_ps=2026-09-04:a77e0fbc;nasa_pscomppars=2026-09-04:0ade67b2;spoc_tce=2026-09-04:e580dde7;tess_eb=2026-09-04:43555226;toi=2026-09-04:869a3c23`; rows per source {'ctoi': 5137, 'nasa_ps': 39312, 'nasa_pscomppars': 6060, 'spoc_tce': 342918, 'tess_eb': 4584, 'toi': 8148}.

The 2-minute check at zero: 9,285 stars have no SPOC 2-minute sector among their search sectors; at minority: 10,512. The definition uses minority.

Qualified: **9,989**. Ranked and cut at 2000: True. Relaxations applied: none. Target list: **2,000 stars** (`data/survey/targets_p8.csv`).

## 3. The Gaia dwarf check [A, applied M]

From the TIC's own Gaia columns (TIC v8 Gaia DR2 columns GAIAmag, gaiabp, gaiarp, plx, e_plx; no extinction correction): parallax signal-to-noise >= 5.0, BP-RP >= 1.6, and |M_G - (M_G = 2.5 + 3.0 * (BP-RP))| <= 1.25 mag. Written before the pool was examined. Outcomes over the definition band (Teff, radius, Tmag cuts only): pass 40,216, no_parallax 3,251, overluminous_for_colour 243, underluminous_for_colour 62.

## 4. Light-curve coverage by Tmag, and the ceiling [M]

| Tmag | stars (TIC cuts, absolute latitude cut) | with >= 3 predicted 200-s sectors | with >= 3 delivered 200-s light curves | fraction |
|---|---:|---:|---:|---:|
| 12.5-13.0 | 6,427 | 1,841 | 1,775 | 28% |
| 13.0-13.5 | 12,900 | 3,775 | 3,667 | 28% |
| 13.5-14.0 | 24,445 | 6,927 | 6,674 | 27% |
| 14.0-14.5 | 47,280 | 13,510 | 12,873 | 27% |

Ratio of the 14.0-14.5 fraction to the 13.5-14.0 fraction: 0.997; the pre-registered condition for extending the ceiling is >= 0.8: **met**. Ceiling used: 14.0. Radius cut used: 0.45 Rsun.

## 5. The target list [M]

| quantity | p10 / p25 / p50 / p75 / p90 |
|---|---|
| Tmag | 12.69 / 12.95 / 13.29 / 13.60 / 13.80 |
| Teff (K) | 3189.90 / 3284.00 / 3373.50 / 3454.00 / 3525.00 |
| radius (Rsun) | 0.23 / 0.28 / 0.34 / 0.39 / 0.42 |
| mass (Msun) | 0.20 / 0.25 / 0.32 / 0.38 / 0.42 |
| 200-s sectors with a light curve | 4.00 / 5.00 / 8.00 / 17.00 / 18.00 |
| 600-s sectors with a light curve | 1.00 / 2.00 / 5.00 / 10.00 / 12.00 |
| 2-minute sectors among the search sectors | 0.00 / 0.00 / 0.00 / 1.00 / 3.00 |
| Absolute galactic latitude (deg) | 22.60 / 26.20 / 32.48 / 41.52 / 57.40 |

1,374 of 2,000 stars have no 2-minute sector among their search sectors; 1,948 have at least one 600-s sector; 1,856 have a TESS-SPOC light curve somewhere and 234 are QLP-only in every 200-s sector; 764 are north of the equator. Contamination ratio missing for 1% (median measured 0.0098; policy measured_median, fill 0.0107). A 1 R_earth planet is 0.74 ppt and a 2 R_earth planet 2.97 ppt on the median star.

The prompt-1 model score used only for ranking (photon-noise model, adopted efficiencies, 29 DC15 cells over [0.5, 30.0] d) sums to 18.35 expected new signals at mid priors (23.96 low, 12.43 high). It is not the expectation of this prompt; section 7 is.

## 6. Gaia, SIMBAD and VSX for every star [M]

`scripts/p8_neighbours.py` (2026-09-04T23:33:44Z): 2,000 of 2,000 stars have a complete record (Gaia errors 0, SIMBAD errors 0, VSX errors 0, missing files 0). Target match: {'nearest_5arcsec': 1252, 'tic_gaia_id': 635, 'nearest_5arcsec_after_proper_motion': 113}. Gaia sources within 1 arcmin, p10/p50/p90: [4.0, 8.0, 19.0]. Target flags: {'ruwe_gt_1.4': 138, 'ipd_multi_peak_gt_10': 14, 'aen_sig_gt_2': 813, 'non_single_star': 36, 'phot_variable': 181, 'no_target_match': 0}. Stars with a neighbour within 3 px bright enough to make a 1 ppt dip if totally eclipsed: 1,986; with a VSX entry within 1 arcmin: 302; with a SIMBAD entry: 1,684.

## 7. Completeness, false alarms and the expectation [M]

`scripts/p8_completeness.py` (2026-09-05T23:24:44Z, rules p7.0): 2,100 injections on 300 stars, outcomes {'recovered': 1163, 'missed': 855, 'alias': 82}.

| level | through / injected | fraction | SNR50 (16-84%) | SNR90 (16-84%) |
|---|---:|---:|---|---|
| search only | 1,163 / 2,100 | 55% | 13.2 (12.9-13.5) | 31.6 (30.1-33.3) |
| search + pre-gate | 1,121 / 2,100 | 53% | 14.1 (13.8-14.4) | 31.4 (29.9-33.0) |
| search + Stage A | 1,093 / 2,100 | 52% | 14.6 (14.3-15.0) | 36.7 (34.7-38.7) |
| search + Stage A + secondary gate | 904 / 2,100 | 43% | 20.2 (19.6-21.0) | 75.2 (69.7-81.9) |
| the whole funnel (pre-gate, A, secondary) | 896 / 2,100 | 43% | 20.4 (19.8-21.2) | 74.0 (68.6-80.3) |

False alarms on the same 300 stars with no injection: 2,097 accepted candidates (6.99 per star), 586 past the pre-gate (1.953 per star), 36 past Stage A (0.1200 per star), 2 past the secondary gate (0.0067 per star).

### Yield model and assumptions [A, P1]

The central model uses the [Dressing & Charbonneau (2015) occurrence grid](https://arxiv.org/abs/1501.01623), with the adopted giant-planet component from prompt 1. The faint-M incumbent-search priors are adopted: a higher prior means that more detectable objects are already known, hence fewer expected new signals. The calibration ends after the pre-gate, Stage A and secondary scan. Later vetting can only reduce this yield.

The sensitivity uses [Hardegree-Ullman et al. (2019)](https://arxiv.org/abs/1905.05900): 1.19 (+0.7/-0.49) planets per star over 0.5-2.5 Earth radii and 0.5-10.0 days. rescale the DC15-supported portion of 0.5-2.5 Re x 0.5-10 d, including partial cells uniformly in log P and log R; DC15 starts at 1 Re, so the HU19 total is assigned to 1-2.5 Re. This is a sensitivity proxy, not a transcription of a radius-period distribution.

* The SNR-marginal logistic calibration is applied to each occurrence cell and each star.
* Occurrence cells use representative radius and geometric-midpoint period; phase-averaged transit coverage uses the measured cadence count.
* Impact parameters have equal weights on the recorded grid; the SNR shape calculation uses an instantaneous limb-darkened model.
* The 1-4 Earth-radius injection calibration is extrapolated in SNR to the adopted giant-planet component.
* Uninjected control passers are treated as the false-alarm budget and extrapolated at a constant rate per star.
* Later Stage B, blind TLS and Stage D losses are uncalibrated and can only reduce the final candidate yield.

### Expected signals under that model

`scripts/p8_expected_yield.py` (2026-09-05T23:27:50Z): on 2,000 stars with a prepared curve, detectable planets through the funnel 19.00 (search only 25.29).

| prior completeness | expected NEW signals through the funnel | with the HU19 rescaling | search only |
|---|---:|---:|---:|
| low | 14.92 | 19.64 | 19.77 |
| mid | 11.67 | 15.48 | 15.30 |
| high | 8.09 | 10.85 | 10.47 |

Expected funnel-passing false alarms in the population: 13.3; ratio of expected signals to false alarms at mid priors: 0.876.

**Stop rule** (PROMPT_P8.md Part 1f, before any measurement): mid-prior expectation 11.67 against the threshold 3.0; high-prior 8.09. **PROCEED: the mid-prior expectation through the funnel is 3.0 or more**

## 8. Files

* `data/survey/targets_p8.csv`, `targets_p8.meta.json`, `population_p8.json`, `catalog_versions_p8.json`.
* `data/survey/cache/p8/` (strips, pool tables), `data/survey/cache/target_lists/`, `data/survey/cache/twomin_lists/` (git-ignored).
* `data/survey/p8/neighbours/` (one JSON per star), `neighbours_p8.json`, `completeness_p8.json`, `expected_yield_p8.json`.

## 9. Search input reconciliation [M]

The completed search used 20,924 product arrays harmonised to 200 s. They cover standard sectors 56-105 and include 13 TESS-SPOC products from the special sector 1751. [The mission release notes](https://heasarc.gsfc.nasa.gov/docs/tess/sector1751_summary.html) identify that sector as the January 2026 comet pointing. The source metadata and native timestamps agree; the existing cadence selection retained these products.

The special sector was not counted for the population's three-sector minimum. It appears on 13 selected stars and on 0 injection-sample hosts. The calibration therefore does not separately measure its unusual window. [search_validation_p8.json](../data/survey/p8/search_validation_p8.json) records every affected star, its qualifying standard sectors, the source metadata and the completed search hashes.
