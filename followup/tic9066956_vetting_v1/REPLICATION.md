# Replicating the TIC 9066956 vetting (2026-10-06)

This guide lists where an agent needs to look, in order, to reproduce `VETTING_REPORT.md`. Every source is read-only: do not edit the survey, the Codex workspaces or any `D:` data. `<repo>` = `C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter`. `<fu>` = `C:\Users\seanj\Documents\Codex\2026-10-05\can-you-look-at-all-the`.

## 0. Environment

- Python: `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe` (3.13). It has numpy, astropy, astroquery, wotan and requests installed; nothing to install. Set `PYTHONIOENCODING=utf-8`.
- Search narrow directories. A ripgrep over the whole repo or `D:` times out, and the TIC appears only as a substring inside other numbers in p9-p12.
- Write scripts to files, not long `-c` strings (the Bash tool has a ~8 kB command limit).

## 1. The candidate as the pipeline found it (10/5 survey, run by Codex after P12)

| What | Path |
| --- | --- |
| Survey report bundle (unzip it) | `D:\tesshunter_surveys\20261005_survey2000\reports\TessHunter_P12_1998_stars_20261006T025626Z.zip` |
| Candidate row | `candidates.csv` and `interesting_signals.csv` in the zip, `candidate_key = tic9066956_p01` (review notes and cautions are in the latter) |
| Survey's manual review | zip: `evidence/audit/supplement_scientific_review_notes.json` |
| Figures | zip: `figures/tic9066956_p01_{packet,pixels,stage_c}.png` |
| Full funnel case (A, S, B, C, D, TLS, fit, FPP, pixels) | `D:\tesshunter_surveys\20261005_survey2000\supplement\p12\funnel\survey2000_supplement_20261005\cases\tic9066956_p01\` |
| Search result and traces | `D:\tesshunter_surveys\20261005_survey2000\supplement\p12\survey2000_supplement_20261005\search\{results\tic9066956.json,traces\tic9066956.jsonl}` |
| Recent-sector FITS (QLP s69/70/92, TESS-SPOC s69/70) | `D:\tesshunter_surveys\20261005_survey2000\supplement\p12\lightkurve\acquisition\tic9066956\attempt1\mastDownload\HLSP\` |
| Survey workspace (plan, resume log, frozen pipeline copy) | `C:\Users\seanj\Documents\Codex\2026-10-05\review-my-tesshunter-p12-project-history\` (`SURVEY_PLAN.txt`, `RESUME_SURVEY.txt`) |

## 2. Earlier Codex follow-up being vetted (`<fu>`)

Read these newest first:

| What | Path under `<fu>` |
| --- | --- |
| Latest summary: FPP reruns, XP, 1953 plate, triple fits, activity | `TIC9066956_Existing_Data_Update.txt`; detail in `class906v2/page_update_staging.md` and `class906v2/results/` (`fpp_summary.json`, `xp_summary.json`, `dss_limit.json`, `imaging_summary.json`, `activity.json`) |
| Physical classification: CMD excess, APOGEE audit, 79 models, secondary scan, ephemeris | `class906/page_update_staging.md`, `class906/results/` (`adopted_ephemeris.json`, `physical_models.json`, `secondary_phase_scan.json`, `spectroscopy_audit.json`, `observing_predictions.json`), `class906_context.log` |
| Continuous triple fits (the surviving false positive) | `class906v2/results/continuous_models.json`, `triple_no_cooling.json`, `triple_ratio_profile.json`. Bounds are in `class906v2_triples.py` (the `lo`/`hi` arrays in `fit()`); radius-cooling coupling is in `class906_physical.py` line 24 (`f = inflate/(1-supp)**2`) |
| PRF host localisation | `host906/summary.json`, `host906/previous_tic9066956_assessment.json`, `TIC9066956_Host_Localization.html` |
| Earlier-sector recurrence (their version) | `outputs/earlier/tic9066956_p01.json`, `earlier_final.log` (line 1) |
| Earlier-sector FITS (TESS-SPOC s2/29/42) | `new_data/earlier/tic9066956_p01/mast_cache/mastDownload/HLSP/` |
| ZTF | `outputs/ztf_analysis.json` |
| ExoFOP novelty check at 05:42 UTC | `class906/ctoi_check/` (`match_summary.json`, receipts) |
| Overview of all 30 signals | `README_Followup.txt`, `candidate_assessments.json` |

## 3. Independent checks (scripts in `scripts/`, outputs in `results/`)

Run them in this order. The network column says which need internet.

| Step | Script | Network | Reproduces |
| --- | --- | --- | --- |
| Per-sector recurrence, nulls, odd/even, phase 0.5 | `recur.py results/recur.json` | no | Sector table; survey ephemeris predicting s2/29/42 at 7-11σ |
| Combine sectors | `combine_sectors.py ../results/recur.json` | no | 4.07 ± 0.23 ppt, chi2 2.96/5; odd/even; phase 0.5 at -0.20 ± 0.23 |
| Every MAST product for the star | `mastq.py` | yes | No 2-min data, no K2; s96 has only SPOC/TICA FFIs |
| Sector coverage, Gaia, kinematics, XP-metallicity tries, VizieR cone | `context.py out.json` | yes | TESScut lists s96; UVW_LSR (12.7, -41.3, -3.0); TD/D 0.03 |
| Rows from each VizieR hit | `cats.py` | yes | XP [Fe/H] ≈ 0 (J/ApJ/984/58, V/160 StarHorse, Gaia MSC); Hα; Gaia dispersion; no EB/variable/planet catalogue (`results/cats.txt`) |
| s96 forward test | `s96.py` (downloads a 136 MB cutout into `scripts/s96/`) | yes | **Expected outcome: no usable data.** Its depth output is meaningless |
| Show why s96 is empty | `inspect_s96_cutout.py <cutout.fits>` | no | Median image is zero except the last two columns; header `1CRV4P = 22` puts the star ~10 px off the science array |
| Triple vs planet parameters and band depths | `triple_extract.py` | no | Triple: inflation x1.39, -300 K, b = 1.09, depths g 0.67 / r 1.24 / K 18.1 ppt; no-cooling chi2 386.48 |
| Population context | `pop.py` | yes | 34 planets with P < 1 d and Teff < 4000 K; none with Rp > 2.5 R⊕ |
| Live novelty | `novelty.py` | yes | No TOI or CTOI hit (repeat to update; results depend on the date) |

External services touched (all read-only):
- MAST TESScut sector API
- `astroquery.mast` Observations
- VizieR: `I/355/gaiadr3`, `I/355/paramp`, `J/ApJ/984/58`, `V/160`, `J/A+A/677/A137`, plus a 3" cone
- NASA Exoplanet Archive TAP (`pscomppars`)
- ExoFOP `tois.csv`, `ctois.csv` and `target.php?id=9066956`

## 4. Pitfalls to expect

- **TESScut lists sectors where the star is off silicon** (s96 here; same as TIC 332366289). Always look at the cutout image before trusting a light curve.
- **The pipeline's sector-69 fixed-aperture depth (0.85 ppt) is corrupted by outliers.** Use TESS-SPOC s69 PDCSAP instead (4.35 ± 0.52 ppt).
- **Box depths (~4 ppt) are expected to be smaller than the fitted 5.6 ppt.** A full-duration box averages over ingress and egress.
- **Pick the right ephemeris for the test.** Use the survey ephemeris (P 0.7134493373, T0 3182.8240173) for the prospective early-sector test; it was fitted to s69/70/92 only. The six-sector ephemeris (P 0.71344765117, T0 3182.8243523) includes those sectors, so it cannot test them.
- **Don't misread the FPP.** The 1.79% / 2.39% is almost entirely "planet on a companion". TRICERATOPS cannot sample companions below 0.1 M☉, so it says nothing about the triple.
- **The catalogue XP metallicities are ML estimates with M-dwarf systematics.** Treat them as supporting evidence only.
