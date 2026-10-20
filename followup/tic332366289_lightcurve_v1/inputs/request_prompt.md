# Candidate-only light-curve check: TIC 332366289 (is the dip real, and is the period real?)

## Objective

Determine, at the light-curve level, (1) whether the ~18.748-d dimming attributed to TIC 332366289 is present in **raw** photometry (TESS-SPOC SAP and background-subtracted TESScut pixel photometry) at a consistent depth in each retained event, or whether it depends on the PDCSAP correction; and (2) whether the 18.748-d period is supported once each event is judged on raw data, using all TESS sectors that cover the star, including the 8 pre-sector-56 sectors P12 never used.

Implement, test and run this. Do not stop at a plan. An inconclusive result is valid. Do not tune anything to restore or to kill the candidate.

This is NEW post-P12 follow-up on an already-examined candidate. It is not a continuation of the frozen P12 search, not a rerun of the funnel, and not a planet validation. It changes no P12 verdict or tier.

## Inherited context (verify against the local records; facts may be stale)

- Repo: `C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter`. Interpreter: `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe` (python is not on PATH).
- Candidate packet: `docs/packets/audit_p12/tic332366289_p02/tic332366289_P18.7481/`. Case records: `data/survey/p12/funnel/final/cases/tic332366289_p02/` (a junction to `D:\tesshunter_data\survey_p12\...`).
- **Previous follow-up (treat as historical, read-only):** `followup/tic332366289_localisation_v1/`. Read `LOCALISATION_REPORT.md` first. Its status was UNRESOLVED. Its findings, which you should verify rather than assume:
  - joint pixel deficit at the target was 1.46 ± 0.39 e⁻/s (S/N 3.7), about half the PDCSAP-implied depth;
  - per-event pixel deficits were 4.2 ± 1.6 / 2.1 ± 1.3 / 4.6 ± 2.0 ppt (s57/s79/s80), tracking SAP (6.8/1.7/4.5) rather than PDCSAP (8.1/6.1/5.8);
  - the s79 dip was nearly absent in raw pixels.
  - Its `code/data.py` shows how TESScut frames were matched one-to-one to TESS-SPOC cadences by time, and how the SPOC optimal aperture was mapped onto the cutout. Its `events.csv`, `results/masks/` and `results/controls.csv` hold the event windows and out-of-event control windows. Reuse by copying into the new workspace, never by editing v1.
- Stage A (`stageA.json`, survey ephemeris): 4 observed events. E00 s57, E32 s79 and E33 s80 were kept. E39 s84 was excluded (scattered-light flag on 50% of cadences, PDC gap 0.00 d). Kept PDCSAP depth 6.50 ± 0.86 ppt (SNR 7.57). Kept SAP depth 3.76 ± 0.84 ppt (SNR 4.48, below Stage A's kept-SNR threshold of 7). The packet fit's "4 transits" re-include the excluded E39.
- Ephemerides:
  - E_A (Stage A, primary): P = 18.748084871649127 d, T0 = 2869.8700663100585 BTJD, duration 0.0928318 d.
  - E_F (packet fit, sensitivity): P = 18.748273038412 ± 0.000186 d, T0 = 2869.852494 ± 0.0054 BTJD, T14 1.93 h.
  - They differ by 15–25 min in sectors 57–84 and by roughly 40 min when back-projected to 2020. Do not treat them as interchangeable.
- Cached products (sectors ≥ 56 only):
  - TESS-SPOC 200-s LCs s57, 77, 78, 79, 80, 84 under `D:\tesshunter_data\survey_p12\lightkurve\acquisition\tic332366289\attempt1\mastDownload\HLSP\`;
  - QLP s57, 77, 78, 79, 84 (QLP s80 is excluded: 166–206 s timing offsets);
  - TESScut 21×21 cubes `D:\tesshunter_data\survey_p12\lightkurve\tesscut\tess-s00NN-*_257.222579_50.487785_21x21_astrocut.fits`. These are NOT background subtracted (FLUX_BKG ≡ 0).
- **TESScut sector inventory (queried 2026-10-01):** 24 (cam2/ccd1), 25 (2/3), 26 (2/2), 40 (2/2), 50 (3/3), 51 (3/3), 52 (2/3), 53 (2/2), 57 (4/4), 77, 78 (2/1), 79 (2/2), 80 (3/4), 84 (4/4). Sectors 24–26 are 1800-s FFIs, 40–53 are 600-s, and 56+ are 200-s. Nothing before sector 56 is cached for this star.

## Scope, preservation, resource limits

- New workspace `followup/tic332366289_lightcurve_v1/`, and `D:\tesshunter_followup\tic332366289_lightcurve_v1\` for downloads and arrays. Verify paths, free space, interpreter, installed packages and active jobs first.
- Do not modify any P1–P12 code, record, packet, manifest, cache or source file, nor `localisation_v1`. Record sha256 / size / mtime of every historical file you read, before and after, and state the scope.
- Set `PYTHONDONTWRITEBYTECODE=1`. Redirect matplotlib, astropy and lightkurve caches to the new D: directory (`LIGHTKURVE_CACHE`, `MPLCONFIGDIR`, `XDG_CACHE_HOME`). Never write into `data/cache`.
- No git reset, commit or push. No external submission. No automations.
- Do not rerun BLS/TLS population searches, the A–D funnel, TRICERATOPS or calibration work. Do not expand to other stars.
- At most two workers, numerical threads 1, a 3-hour wall ceiling, and a 5 GB new-download ceiling. Bounded network calls with at most one transport retry. One MAST product search for the star, then per-product downloads; never issue per-sector searches from many workers. Checkpoint and stop before exceeding a limit. No orphaned workers.
- Ask only for genuine blockers.
- Known environment gotchas:
  - QLP sectors ≥ 56 have all-NaN `det_flux_err`, and their low-precision quality bit is 2^30 (2^12 before sector 56).
  - Never stitch mixed cadences for detrending; work per sector.
  - The venv's `tess_stars2px` is broken.
  - There is a ~8 kB Bash command limit; write scripts to files.
  - Heredocs containing Python triple quotes break.
  - `taskkill` is blocked; use `Stop-Process`.

## 1. Inputs and identity

- Map every predicted E_A/E_F transit (all cycles) onto every sector above, using the TESScut / TESS-SPOC time ranges.
- Fetch only what is needed for this star:
  - TESS-SPOC or QLP light curves for sectors 24–53 (record author, version, cadence, hashes);
  - TESScut cubes for pre-56 sectors only if a predicted epoch is covered and a pixel-level light curve is required.
- Verify TIME, time scale (BTJD TDB), exposure and cadence identity per product. Match masks by time, never by array index.
- Write `events.csv` covering every covered predicted epoch: cycle, sector, cadence, products, coverage, quality, distance to data edges / PDC gaps / momentum dumps, scattered-light flags.
- Write `PLAN.md` and `config.json` **before measuring any depth**. They must record predeclared detrending, windows, depth estimator, error model, decision rules and seeds. Label these as adopted follow-up choices, not P12 rules.

## 2. Per-event depths in several photometries (same recipe for all)

For each covered event, measure the depth with one predeclared local recipe applied identically to:
- (a) TESS-SPOC PDCSAP;
- (b) TESS-SPOC SAP;
- (c) background-subtracted TESScut photometry in the SPOC optimal aperture (aperture sum minus n_pix × per-frame background);
- (d) a small aperture (target pixel or 3×3) from TESScut;
- (e) QLP where it is valid.

Recipe: local linear or quadratic baseline fitted to out-of-event windows on both sides, with a guard covering ingress/egress and the E_A/E_F timing difference, never bridging gaps or momentum dumps; box or fixed-shape depth over the in-event window. Compare depths on a common footing: state each product's crowding / flux-fraction normalisation (PDCSAP is CROWDSAP/FLFRCSAP-corrected; SAP is not).

Calibrate errors empirically with the same recipe on out-of-event control windows from the same sector. Red noise matters, and white-noise errors are not enough. Run injection-recovery into the raw SAP and pixel light curves at the PDCSAP and SAP depths, so that depth biases from the recipe are measured. Run the same recipe on E39 (s84) as a diagnostic, never pooled.

## 3. Is PDCSAP making or deepening the dip?

Per event, compare PDCSAP and SAP depths and their difference with calibrated errors. Inspect the PDC correction itself around each event: PDCSAP minus scaled SAP, proximity to PDC gaps, scattered-light flags, background ramps, momentum dumps. Also read what the inherited P12 K9a correlation (s79 r = 0.88, s80 0.999, s84 0.998) actually correlates; find it in `p12/protocol` or `src`, read-only. This project's dominant historical false-positive class was dips made or deepened by PDC. Test for it directly; do not assume it.

## 4. Is the period real?

- **Back-projection.** For E_A and E_F, predict every epoch in sectors 24–53 and in 77/78. Measure depth at each covered epoch with the same recipe. Because timing uncertainty grows backwards, also build a joint (P, T0) box-likelihood map over a bounded region around the ephemerides, in the spirit of a joint period-phase map rather than a single back-projected ephemeris. Report per-epoch depths, the joint depth, and the map.
- **Alias test.** Using only events that are individually supported in raw photometry, enumerate the periods those events allow (for s57+s80 alone, P = Δt/n). For each candidate period in a bounded range (e.g. 1–100 d), test its predicted epochs in all covered data, including s79, s84, 77/78 and pre-56 sectors. Report which periods survive, using a predeclared rule (e.g. a candidate period is disfavoured if covered predicted epochs give a joint depth inconsistent with the event depth at ≥ 3σ, with calibrated errors).
- Handle 1800-s and 600-s cadences per sector. Do not stitch.

## 5. Decide (one primary status plus flags; criteria fixed in PLAN.md first)

- `RAW_SIGNAL_CONSISTENT`: the dip is present in raw photometry in ≥ 2 independent events with consistent depth, and 18.748 d is supported (aliases excluded or strongly disfavoured, pre-56 epochs consistent).
- `PDC_DEPENDENT`: one or more events hold in PDCSAP but not in raw photometry, materially reducing the independent-event support. State how many events remain.
- `PERIOD_AMBIGUOUS`: raw events are real, but several periods survive.
- `PERIOD_REFUTED`: covered predicted epochs exclude 18.748 d at the measured depth.
- `NOT_SUPPORTED`: no significant joint dip in raw photometry.
- `OPERATIONAL_BLOCKED`: a needed input or step could not be completed.

Report independent-event support explicitly. A joint result carried by one event is not repeated detection. No result here is a planet probability.

## 6. Deliverables

`LIGHTCURVE_REPORT.md` must cover:
- the primary status and direct answers to "is the dip real in raw data?", "is PDCSAP inflating it, where and why?", "how many events independently support it?" and "is 18.748 d the period, or which periods survive?";
- per-event depth tables for every photometry;
- the PDC diagnostics;
- back-projection and alias results;
- control and injection sample sizes and limitations;
- inherited facts, new measurements, assumptions and interpretations kept separate;
- what this means for whether ground-based follow-up is worth doing, with predicted windows if so;
- reproduction commands; completed and unfinished work.

Also deliver: `PLAN.md`, `config.json`, `events.csv`, depth and alias CSV/JSON, focused tests (time and mask alignment, aperture mapping, background-subtraction sign, depth recipe on synthetic injections, alias enumeration), and readable PNGs:
- per-event light curves for every photometry, binned, with masks;
- PDCSAP-minus-SAP around each event;
- back-projected epochs;
- the alias / joint (P, T0) map.

Inspect every figure for sign, time-axis and alignment errors. Record before/after integrity checks, then build `review_bundle.zip` (report, config, code/tests, compact results, figures; no raw cubes or caches).

In the final response, state what was executed, the status and its evidence, the limits, and the report and bundle paths.
