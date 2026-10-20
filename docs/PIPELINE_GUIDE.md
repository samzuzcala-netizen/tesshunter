# tess-exoplanet-candidate-hunter

A Python pipeline for searching NASA TESS photometric data for candidate exoplanet transit signals. Built for reproducibility and scientific caution.

> **Scope and caveats:** This pipeline finds *candidate transit-like events*. It cannot confirm planets. Every signal is treated as a false positive until follow-up observations demonstrate otherwise. The words "discovered planet" do not appear in this codebase.

---

## What is a transit?

When a planet passes in front of its host star from our line of sight, it blocks a small fraction of the star's light. TESS measures stellar brightness over time. A transiting planet produces a periodic dip (a "transit") in that brightness record.

Key facts:
- A Jupiter-sized planet around a Sun-like star blocks ~1% of the light (~10 ppt)
- An Earth-sized planet blocks ~0.01% (~0.1 ppt)
- Most transit signals are contaminated by noise, stellar variability, or instrumental artifacts
- Many transit-like signals are **eclipsing binaries** (two stars, not a planet)
- Confirmation requires spectroscopy, centroid analysis, and often ground-based photometry

---

## Scientific caveats

Before interpreting any output from this pipeline, understand these false-positive sources:

| Source | Description |
|--------|-------------|
| **Eclipsing binaries (EBs)** | Two stars eclipsing each other can produce deep, periodic dips identical to planet transits at first glance |
| **Background EBs** | A binary blended within the TESS aperture (21 arcsec pixels) that creates diluted eclipse signals |
| **Stellar variability** | Starspots, pulsations, and rotation can create quasi-periodic signals |
| **Instrumental systematics** | TESS momentum dumps, thermal settle events, and scattered light produce artifacts |
| **Single-sector events** | A signal seen in only one sector has not been confirmed to repeat |
| **V-shaped dips** | May indicate grazing eclipses, not central transits |
| **Contamination** | Bright nearby stars dilute the measured depth, biasing radius estimates |

---

## Setup

### Prerequisites

- Python 3.10+
- pip

### Install

```bash
git clone https://github.com/your-username/tess-exoplanet-candidate-hunter
cd tess-exoplanet-candidate-hunter
pip install -e ".[dev]"
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

Both routes install the full runtime stack, including `pyyaml` (batch configuration files) and `tabulate` (markdown tables in reports; report generation falls back to plain text if it is missing).

### Verify the installation

```bash
pytest tests/ -q
```

All tests run without network access using synthetic data.

---

## Usage

### The canonical entry point: `tesshunter.pipeline.search_target()`

`src/tesshunter/pipeline.py` ties the whole flow together: download with corrected product selection, preprocess, iterative BLS detection with quality gates, per-planet vetting, and optional report generation. The notebooks are interactive walkthroughs of the same stages; for scripted or batch work, call the pipeline directly.

```python
from tesshunter.pipeline import search_target

result = search_target(
    259377017,                 # TIC ID (int), or e.g. "EPIC 200164267" for K2
    mission="TESS",
    author="SPOC",
    period_min=1.0,
    period_max=13.0,           # days
    duration_min=0.01,
    duration_max=0.15,         # days
    max_planets=4,
    stellar_radius_rsun=0.374, # enables the radius-aware depth veto
    generate_report=True,      # markdown report + candidate_summary.csv upsert
)

for planet in result.planets:
    print(planet["planet_num"], planet["period_days"], planet["snr"], planet["verdict"])
print(result.provenance["products"])   # exactly which data products were used
print(result.timings)                  # seconds per stage
```

It returns a `SearchTargetResult` with accepted planets, a vetting record per planet, data provenance (products, observing units, any fallback events), the preprocessing record, and per-stage timings. `result.to_dict()` gives a JSON-serialisable version.

### Step 0: Validate the pipeline (required before searching unknown targets)

Open and run `notebooks/01_recover_known_planet.ipynb`.

This notebook downloads TESS data for WASP-126 b (a confirmed hot Jupiter) and verifies the pipeline recovers the known transit period within 2% tolerance. **Do not search unknown targets until this notebook passes.**

### Step 1: Search a single target

Open `notebooks/02_single_target_search.ipynb`, set your TIC ID, and run all cells. The notebook produces:
- Diagnostic plots in `outputs/plots/TIC_<ID>/`
- A markdown vetting report in `outputs/reports/TIC_<ID>/`
- A row in `outputs/candidates/candidate_summary.csv`

Finding a TIC ID: search [ExoFOP-TESS](https://exofop.ipac.caltech.edu/tess/) or [MAST](https://mast.stsci.edu/) by object name.

### Step 2: Batch search

Edit `configs/search_targets.yaml` with your target list, then either run `notebooks/03_batch_candidate_search.ipynb` or call the pipeline:

```python
from tesshunter.pipeline import search_targets_from_config

results = search_targets_from_config()  # reads configs/search_targets.yaml
# or: search_targets_from_config("my_targets.yaml", generate_report=True)
```

One failed target does not abort the batch; failures come back as results with an ERROR note. With `generate_report=True`, rows land in `outputs/candidates/candidate_summary.csv`, which is kept sorted by BLS SNR descending. Rows are upserted (keyed on TIC ID plus period within 1%), so re-running a target replaces its rows instead of duplicating them.

### Step 3: Deep vetting

Run `notebooks/04_candidate_vetting_report.ipynb` on any promising candidate from the summary. This notebook performs the additional false-positive checks that need extra downloads (centroid shift via target pixel files, nearby-star contamination via a TIC cone search) and produces a final markdown report.

---

## How the pipeline behaves

Details that matter when interpreting results:

- **Data selection is cadence-aware.** `author="SPOC"` implies 120 s cadence; otherwise all cadences are searched and the best product per observing unit is chosen. A user-specified author is never dropped silently: any fallback retry logs a WARNING and is recorded in `result.provenance["fallback_events"]`.
- **One product per observing unit.** Before stitching, duplicate copies of the same sector/campaign/quarter from different pipelines are deduplicated with an author priority (SPOC 2-min, then TESS-SPOC, then QLP, then other HLSPs; for K2: K2, then EVEREST, then K2SFF). Unit caps count distinct units, not raw search rows. Per-product sectors, authors, and cadences are preserved in the stitched light curve's metadata.
- **Detrending windows are in days.** The Savitzky-Golay window is specified in days (default 1.0), converted to cadences via the measured median cadence, and clamped per contiguous segment to at most half the shortest segment. If detrending fails, the record honestly says `flattened=False` with a warning note. The pipeline also does an optional two-pass flatten: the strongest first-pass candidate is masked before re-fitting the trend so shallow transits are not absorbed into it.
- **Detection statistics are measured, not assumed.** BLS SNR is computed from the robust scatter (1.4826 x MAD) of out-of-transit residuals at the candidate ephemeris, not from reported flux errors. Each candidate also carries an `sde` column (signal detection efficiency: peak power minus median power, over the MAD-scaled spread of the power spectrum). The auto period grid follows the standard frequency-resolution criterion (oversample 4, floor 500, cap 20000 with a logged warning).
- **Two transits minimum.** Acceptance requires `n_transits_observed >= 2` by default (`min_transits` kwarg). Single deep dips are reported with `single_event=True` but not accepted as candidates.
- **Every accepted planet is vetted.** The pipeline runs the full vetting battery per planet, with the measured SNR and catalog-crossmatch status actually passed in, and writes each planet's real verdict to the summary CSV (no hardcoded verdicts for planets 2+).
- **The depth veto is radius-aware.** When `stellar_radius_rsun` is provided, the hard veto triggers on an implied companion radius above 2.5 R_Jup (stellar-companion regime) rather than on absolute depth, and 1.5 to 2.5 R_Jup flags high risk. A Jupiter-depth transit around an M dwarf is therefore not auto-rejected. Without a stellar radius, absolute-depth thresholds apply as a fallback.

---

## Known-object hard stop and the survey population

`catalog_crossmatch.py` is a hard stop, not a courtesy lookup. Before any light
curve is downloaded, a TESS target is rejected if its TIC ID appears in the
ExoFOP TOI or CTOI lists, the NASA Exoplanet Archive `ps` or `pscomppars`
tables, the TESS Eclipsing Binary catalog (Prsa et al. 2022), or any SPOC
threshold-crossing-event list on MAST (every sector and multi-sector run). A
known object within 21 arcsec (one TESS pixel) under a different TIC ID raises
a FLAG; SPOC TCE hosts, which have no coordinates in the TCE files, are placed
in the same coordinate tree through a bulk TIC resolution of every TCE TIC ID
(cached with provenance; any unresolved ID is a loud failure). Catalogs are
cached under `data/cache/catalogs/` with version stamps and refreshed weekly;
a fetch failure raises `CatalogFetchError` and stops the run rather than
degrading to "no match". The stop covers what its catalogs contain: QLP TCEs
that never became TOIs have no public list and are not covered.

```python
from tesshunter import catalog_crossmatch as cx
res = cx.hard_stop(150428135)          # -> HardStopResult(status="REJECT", ...)
print(res.summary())
```

`search_target(..., do_crossmatch=True)` applies the stop automatically.

The survey population is built by `scripts/build_survey_population.py`
(seeded sky tiles, TIC cone queries, tess-point sector prediction, streamed
QLP and TESS-SPOC target lists, the hard stop, and a yield model) and
documented in `docs/POPULATION.md`; the target list is
`data/survey/targets_v1.csv`.

## Output organisation

```
outputs/
  plots/
    TIC_<ID>/
      raw_lightcurve.png
      cleaned_lightcurve.png
      bls_periodogram.png
      folded_P<period>d.png
      transit_zoom.png
  reports/
    TIC_<ID>/
      candidate_report_TIC_<ID>.md
  candidates/
    candidate_summary.csv
```

---

## Configuring your search

`configs/search_targets.yaml` is read by `tesshunter.pipeline.load_search_config()` and drives `search_targets_from_config()`. The `search:` block sets shared parameters (`period_min_days`, `period_max_days`, `duration_min_hours`, `duration_max_hours`, `top_n_candidates`; hour-valued durations are converted to days). Each entry under `targets:` needs a `tic_id` (or a `target` string such as `"EPIC 200164267"`). Any key in either block that matches a `search_target()` parameter name is passed through, so per-target overrides like `mission`, `author`, `max_planets`, or `stellar_radius_rsun` work without code changes. A per-target `known_period_days` is used as a diagnostic: after each accepted planet is masked, the pipeline logs whether that period remains in the residual.

`configs/known_planet_targets.yaml` is a reference list of validation targets for the recovery notebook; it is not read by the pipeline code.

Key defaults live in `src/tesshunter/config.py` (some modules define the same values locally to avoid circular imports; the search-related ones are also exposed as `search_target()` keyword arguments):

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `BLS_PERIOD_MIN` | 0.5 d | Shortest period searched |
| `BLS_PERIOD_MAX` | 20.0 d | Longest period searched |
| `BLS_DURATION_MIN` | 0.02 d | Shortest transit duration searched |
| `BLS_DURATION_MAX` | 0.5 d | Longest transit duration searched |
| `SIGMA_CLIP_SIGMA` | 4.0 | Outlier rejection threshold |
| `FLATTEN_WINDOW_DAYS` | 1.0 d | Detrending window, in days (replaces the deprecated `FLATTEN_WINDOW_LENGTH`) |
| `BLS_MAX_FREQUENCIES` | 20000 | Cap on the auto frequency grid (warning logged when hit) |
| `MIN_TRANSITS_DEFAULT` | 2 | Minimum observed transits for acceptance |
| `SDE_MIN` | 7.0 | Advisory SDE guidance (reported, not gated on) |
| `MAX_DEPTH_PPT` | 50.0 | Unused legacy constant; the real no-radius thresholds are 30 ppt (high-risk flag) and 100 ppt (hard veto) in `vetting.py` |

---

## What this pipeline does NOT do

- It does not confirm that a signal is on-target beyond the centroid check described below. The centroid check (`centroid.py`) measures the in-transit shift of the flux-weighted centroid from up to two sectors of target pixel files (SPOC TPFs preferred) and flags shifts above 0.5 px or 3 sigma, but it is not PSF fitting or difference imaging; a clean result is evidence, not proof.
- It does not query Gaia DR3 directly. The contamination check (`contamination.py`) cone-searches the TESS Input Catalog for neighbours within 126 arcsec and up to 8 magnitudes fainter, estimates the photometric aperture radius from the target's Tmag (1.5 to 2.5 px), and computes leakage-corrected depths with a deliberately broad Gaussian PRF model (sigma 1.5 px). Neighbours within the aperture plus 1 px are never ruled out. It is a screening tool, not a substitute for high-resolution imaging.
- Centroid and contamination checks are not run automatically by `search_target()` (they need extra downloads and network queries). Run them from notebook 04 or call `centroid.run_centroid_check()` / `contamination.run_contamination_check()` yourself, then merge their flags into a verdict with `vetting.recompute_verdict()`.
- It does not fit a limb-darkening model or a physical transit shape. The vetting includes a trapezoid-based V-shape metric (grazing-EB signature), which is a shape heuristic, not a transit model fit.
- It does not compute orbital parameters beyond period and rough radius.
- It does not provide confirmation; that requires follow-up observations.

---

## Next steps after finding a candidate signal

1. Check TESS Data Validation Reports (DVR) from the SPOC pipeline on ExoFOP
2. Inspect the target pixel file (TPF) for centroid shifts during transit (notebook 04 automates a first pass)
3. Search Gaia DR3 for nearby stars within the TESS aperture
4. Look for the transit in ground-based photometry archives (LCOGT, SPECULOOS, etc.)
5. If the signal survives, submit to ExoFOP for community vetting

---

## Module reference

| Module | Purpose |
|--------|---------|
| `pipeline.py` | Canonical entry point: `search_target()`, `search_targets_from_config()` |
| `download.py` | MAST queries, per-unit deduplication, unit-aware normalisation, caching |
| `preprocessing.py` | NaN removal, sigma clipping, quality masking, window-in-days detrending |
| `bls_search.py` | Box Least Squares period search, alias resolution, SNR and SDE statistics |
| `plotting.py` | All diagnostic plots |
| `vetting.py` | False-positive checks (radius-aware depth veto, odd/even, secondary, V-shape) and verdict assignment |
| `centroid.py` | In-transit centroid-shift check from target pixel files |
| `contamination.py` | Nearby-star contamination screening via TIC cone search |
| `catalog_crossmatch.py` | Known-object hard stop: TOI, CTOI, NASA archive, TESS EB, SPOC TCE lists, 21-arcsec neighbour flag |
| `reporting.py` | Markdown report generation and candidate summary CSV upsert |
| `utils.py` | Shared utilities and synthetic data generation |
| `config.py` | Central configuration constants |

---

## Dependencies

- [Lightkurve](https://docs.lightkurve.org/) for TESS data access and light curve tools
- [astropy](https://www.astropy.org/) for time series, BLS, units
- [astroquery](https://astroquery.readthedocs.io/) for MAST and archive queries
- numpy, pandas, scipy, matplotlib for the scientific computing stack
- pyyaml for configuration files, tqdm for progress tracking
- tabulate for markdown tables in reports (plain-text fallback if absent)
