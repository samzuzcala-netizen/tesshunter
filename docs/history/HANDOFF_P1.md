# HANDOFF P1: hard-stop cross-match and the survey population

Date: 2026-09-01. Branch `improve/recovery`. Environment as in `CTOI_PROMPTS.md`
(double-nested repo path, `tesshunter_venv` Python 3.13).

Session start state, measured: `git status` clean apart from the untracked
`CTOI_PROMPTS.md`; 121 files in `data/cache/lightkurve`; `pytest tests/ -q`
177 passed in 175 s. The tree was healthy this time.

Evidence tags: [M] measured in this session, [A] adopted assumption, [R] refuted
or unavailable.

## Part A: the hard stop

### What shipped

`src/tesshunter/catalog_crossmatch.py` was rewritten. A target is REJECTED before
any download if its TIC ID appears in any of six sources, and FLAGGED if a known
object sits within 21 arcsec (one TESS pixel) under a different TIC ID:

| source | what | rows [M] | unique TIC [M] | coordinates |
|---|---|---:|---:|---|
| `toi` | ExoFOP TOI list (`download_toi.php`) | 8,148 | 7,826 | sexagesimal, converted |
| `ctoi` | ExoFOP CTOI list (`download_ctoi.php`) | 5,137 | 4,934 | decimal degrees |
| `nasa_ps` | NASA Exoplanet Archive `ps`, every reference row, via TAP | 39,278 | 4,478 | yes |
| `nasa_pscomppars` | NASA Exoplanet Archive composite table via TAP | 6,057 | 4,478 | yes |
| `tess_eb` | TESS EB catalog, Prsa et al. 2022, MAST HLSP `tess-ebs` v1.0 (sectors 1-26) | 4,584 | 4,578 | yes |
| `spoc_tce` | SPOC DV `tcestats` files: 105 single-sector runs (s0001-s0105) + 27 multi-sector runs + `new_versions/` re-deliveries, 132 files, 551 MB | 342,918 | 68,232 | none in the files |

Union: 75,474 unique known TIC IDs [M]. First live load of all six: 206 s [M];
warm-cache load 0.4 s, one offline check 1.7 ms, one check with a live TIC
neighbour cone query 0.4 to 3 s [M].

Mechanics:

* Cache: `data/cache/catalogs/<source>/` holds the raw download(s), a normalized
  CSV (`source, tic_id, ra, dec, label, detail`) and a `.meta.json` stamp with
  URLs, fetch time, byte count, per-file sha256 and row count. Refresh after 7
  days. TCE files are immutable, so cached raw files are reused and only the
  index listing is re-read.
* Failure policy: any fetch or parse failure, or a parse yielding zero rows,
  raises `CatalogFetchError`. `allow_stale=True` is the only way to fall back to
  an old copy, and the stamp then carries `stale=True` and the version string
  carries `!stale`. `offline=True` serves the cache and stamps it stale when old.
* Version stamp: `KnownObjectCatalog.stamp()` gives an order-stable string such
  as `ctoi=2026-09-01:f6964541;...;toi=2026-09-01:f4411f40`; it is written into
  every `check_many` row (`catalog_versions`), into `targets_v1.csv`, and into
  `data/survey/catalog_versions_v1.json` (the manifest).
* Matching: TIC ID sets per source; a cKDTree over unit vectors for every row
  with coordinates (21 arcsec chord); a second tree over caller-supplied TIC
  neighbours (the survey builder passes every TIC star in the tile, so a TCE on
  a neighbour, which has no coordinates in the TCE files, is still caught by
  TIC ID). The single-target path resolves neighbours with one astroquery TIC
  cone query when `resolve_neighbours=True`.
* Pipeline: `search_target(do_crossmatch=True, hard_stop=True)` now runs the
  cross-match as Stage 0, before download. REJECT returns a result with a
  `HARD STOP` note and no search; FLAG adds a note and searches; a catalog
  failure propagates as `CatalogFetchError`. `SearchTargetResult.crossmatch`
  and `to_dict()["crossmatch"]` carry status, summary, versions and the full
  `HardStopResult`. The benchmark harness never sets `do_crossmatch`, so the
  frozen scores are untouched [M: grep of the harness].
* Legacy names kept: `crossmatch()`, `query_toi_catalog()` (TIC metadata, still
  non-fatal, now also returns `contamination_ratio`), `query_exofop_toi()`,
  `query_confirmed_planet_archive()`. `crossmatch()` now raises on failure and
  returns `any_query_failed=False` always.

### Sources probed and not included [R]

* QLP TCE lists and QLP faint-star TCE lists: no bulk product exists on MAST
  (the QLP HLSP directory holds light curves, target lists and a readme with no
  TCE mention; probed 2026-09-01). QLP-derived TOIs are in the ExoFOP TOI list,
  which is included.
* The live Villanova TESS EB catalog (tessebs.villanova.edu) has no CSV export
  (46 HTML pages; `/catalog.csv`, `/api/`, `/download`, `?format=csv` all 404).
  The Prsa 2022 MAST release is what the prompt asked for and is included.
* Vizier TAP counts on TIC 8.2 for all-sky stratum sizes time out after 170 s;
  all-sky counts are tile-sampled and area-scaled instead (Part B).

### Acceptance [M]

`tests/test_catalog_crossmatch.py`, 29 tests, all offline against recorded
fixtures in `tests/fixtures/catalogs/` (trimmed copies of the real downloads,
545 kB, cut by `scripts/build_crossmatch_fixtures.py`; the catalog stamp they
came from is inside `acceptance_ids.json`):

* per-source parse of the recorded fixture (6 tests), TOI sexagesimal
  conversion checked on TOI-101, TCE run labelling and raw-file reuse;
* per-source REJECT by TIC ID (6 tests);
* FLAG at 10 arcsec from a TOI under another TIC, CLEAN at 30 arcsec; a
  TCE-only neighbour caught by TIC ID; three real recorded neighbour cases
  (TIC stars 9 to 15 arcsec from TOI-101, TOI-102, TOI-103);
* fetch failure raises with no cache, one unreachable source fails the whole
  load, header-only body is a failure, fresh cache makes no network call,
  8-day-old stamp refetches, stale cache plus outage raises unless
  `allow_stale`, stamp fields and digests, manifest coverage;
* the acceptance lists: 20 hand-picked TOIs (TOI-700, Pi Men, LHS 3844,
  TOI-270, WASP-18, L 98-59, LTT 1445A, TOI-1338, TOI-101, TOI-125, TOI-431,
  TOI-178, AU Mic, TOI-1130, TOI-561, WASP-62, TOI-1136, TOI-1266, TOI-1246,
  TOI-1695), 20 CTOIs never promoted to TOI, 10 TESS EBs absent from TOI and
  CTOI, 10 TCE-only stars (in a TCE list and in no other source; that pool has
  56,396 stars), and 20 clean stars from a real TIC cone at (60, -55) with
  real neighbours: all 50 catalog-known rows (20 TOI, 20 CTOI, 10 EB) REJECT
  with their own catalog among the matched sources, all 10 TCE-only rows
  REJECT with `spoc_tce` as the only source (60 rejects in total), all 20
  clean rows CLEAN, and `check_many` agrees with `check` row for row on all
  80 (the P1 version of this batch test covered only 50 of the 80; corrected
  in the remediation, see the section at the end). The same lists pass
  against the live cache (`TESSHUNTER_LIVE_CATALOGS=1`, run once here;
  skipped by default);
* pipeline: a REJECT returns before `search_and_download_lc` is called; a
  `CatalogFetchError` propagates out of `search_target`.

Full suite: 205 passed, 1 skipped (the live test), 117 s [M].

## Part B: the population

### What shipped

* `scripts/build_survey_population.py`: one command rebuilds everything from
  seed 20260901 (`all --n-tiles 120`). Stages, each cached under
  `data/survey/cache/` (git-ignored): seeded sky tiles; TIC cone queries
  (every star Tmag <= 17 per tile, so the tile table doubles as the neighbour
  list); sector prediction with the vendored tess-point; light-curve
  availability by streaming the QLP and TESS-SPOC per-sector target lists from
  MAST; the hard stop; the yield model; the target list. Design constants and
  every model input are written to `data/survey/yield_model_v1.json`.
* `scripts/write_population_memo.py` renders `docs/POPULATION.md` from that
  JSON, so no number in the memo is typed by hand.
* `data/survey/targets_v1.csv` (1,718 rows), `targets_v1_fallback.csv`
  (1,116 rows), their `.meta.json`, `catalog_versions_v1.json`,
  `yield_model_v1.json`.
* `src/tesshunter/_vendor/tess_stars2px.py`: tess-point 0.9.5 with the
  upstream missing-comma fix (the PyPI release does not import on Python
  3.13; 0.9.4 imports but its pointing table stops at sector 96) [M].

### What was measured [M]

Sampling: 120 tiles of radius 0.75 deg at |b| >= 20 deg, union area 210.4 deg^2
(0.8% tile overlap by Monte Carlo), 1/129 of the 27,144 deg^2 at |b| >= 20.
350,546 TIC stars Tmag <= 17 in the tiles (7 s per tile). Pool of candidate
survey stars 20,958 unique (72 duplicate rows from overlapping tiles dropped):
17,584 dwarfs at Tmag 10.5 to 13.5 (radius <= 1.5 Rsun, Teff 2700 to 7200 K)
and 3,374 M dwarfs at Tmag 13.5 to 15 (Teff <= 4000 K, radius <= 0.6 Rsun).

Hard stop on the pool (tile neighbours supplied): CLEAN 20,859, REJECT 92
(0.44%), FLAG 7. Rejections by source: TCE only 55, CTOI only 11, TCE+TOI 8,
TCE+EB 7, CTOI+TCE 4, TOI only 3, CTOI+TCE+TOI 2, NASA archive 1, archive+TCE
1. Flags: TCE neighbour 4, TCE+TOI neighbour 2, archive neighbour 1; the
vectorised check over 20,958 targets and 350,546 neighbours took 0.1 s.

Light-curve availability (exact, from the MAST target lists; 105 QLP lists and
85 TESS-SPOC lists streamed, about 5 GB per pass): every pool star at
Tmag < 13.5 has at least one QLP light curve; 49% have at least one TESS-SPOC
light curve; TESS-SPOC lists exist only through sector 85 (sectors 86 to 105
return 404, so TESS-SPOC coverage of the last 20 sectors is unknown, not
absent). Predicted sectors are capped at 105, the last sector with public
data: the tess-point table runs on into planned sectors and, uncapped, gave a
south-CVZ star 50 "sectors". Of clean bright dwarfs 54% have 4 or more sectors
with a light curve (median 6); of clean faint M dwarfs 33% (median 5), because
the QLP faint-star extension does not cover every sector.

Yield model results (inputs in `docs/POPULATION.md` section 4; new = model
detectable x (1 - prior completeness) x pipeline efficiency, per class A single
sector SNR >= 9, B stitched SNR >= 9, C stitched SNR 7.1 to 9):

| stratum | eligible in sample | all-sky est. | model-detectable per 1000 (A / B / C) | new per 1000, prior high / mid / low | stars for 3 new (mid) |
|---|---:|---:|---|---|---:|
| 1 FFI dwarfs 10.5-13.5, P <= 50 d | 9,394 | 1,212,077 | 1.15 / 2.49 / 1.05 | 0.689 / 1.192 / 1.721 | 2,516 |
| 2 faint M dwarfs 13.5-15 | 1,116 | 143,994 | 0.59 / 2.00 / 1.21 | 1.017 / 1.464 / 1.873 | 2,049 |
| 3 stitched search, P <= 100 d | 9,394 | 1,212,077 | 1.15 / 2.54 / 1.07 | 0.700 / 1.212 / 1.748 | 2,476 |
| 4 additional planets in TOI systems | 7,826 hosts | 7,826 | not searchable: the hard stop rejects the host | 54.8 / 137 / 219 over the whole TOI list under adopted inputs [A] | excluded |

Stratum 3's new signals at mid priors, by class, per 9,394 stars: A 1.30,
B 6.68, C 3.41; dominant bins are 2-4 Re at 1 to 16 d and 8-20 Re at 1 to 2 d.

Sensitivity of the stratum-2 to stratum-3 ratio of new signals per 1,000
stars (mid priors): as modelled 1.21; class C dropped 1.21; noise x1.4 for
Tmag > 13.5 (red noise at the faint end) 0.72, which reverses the ranking;
high priors 1.45; low priors 1.07.

Selection (rule version 3, recorded with its full history in the JSON):
ratio 1.21 is below the 1.5 tie margin, so the tie-breakers decide in order:
deliverability from the sample (stratum 3 gives 11.4 expected new signals,
stratum 2 gives 1.63 and would need about 147 tiles to reach the 2.0 floor),
light-curve coverage (54% against 33% with 4+ sectors), median Tmag (12.8
against about 14.3). **Primary: stratum 3. Fallback: stratum 2.**

`targets_v1.csv`: the 9,394 clean stratum-3 stars ranked by each star's own
expected new signals, cut where the running sum reaches 5.0 at mid priors:
1,718 stars (2.9 expected at high priors, 7.2 at low). Tmag quartiles 11.2 /
11.9 / 12.7; Teff 4491 / 5475 / 5916 K; radius 0.71 / 0.94 / 1.15 Rsun; sectors
with a light curve 6 / 9 / 31 (the ranking favours the continuous viewing
zones); 1,382 stars have both QLP and TESS-SPOC light curves, 336 QLP only;
147 have no TIC contamination ratio (treated as 0). Columns: `tic_id`,
`ra_deg`, `dec_deg`, `tmag`, `teff_k`, `radius_rsun`, `mass_msun`,
`contamination_ratio`, `galactic_lat_deg`, `n_sectors_predicted`,
`sectors_predicted`, `n_sectors_with_lc`, `sectors_qlp`, `sectors_tess_spoc`,
`lc_products_available`, `crossmatch_status`,
`nearest_known_object_sep_arcsec`, `expected_new_signals_mid`, `tile`,
`stratum`, `catalog_versions`. The fallback file has the same columns for the
1,116 clean faint M dwarfs (1.63 expected new signals at mid priors).

Timing [M]: TIC tile queries about 7 s each (14 min for 120); first product
stream about 25 min for a 10.6k pool and about 10 min on a warm MAST cache;
sectors, hard stop, yield and ranking under 1 min together.

### What was refuted or changed by measurement

* Uniform-in-log-period occurrence put 18% of sub-Neptunes at 1 to 2 d and
  inflated every yield by about 3x; replaced by the rising-then-flat shape
  (break at 10 d) from Howard+2012 and Petigura+2018 [M on the synthetic
  check: T=11 solar star, 10 sectors, stitched yield 2.6e-2 -> 1.2e-2].
* The first selection rule (yield per 1,000 stars alone) chose stratum 2 on the
  60-tile run and produced a 594-star list worth 0.83 expected signals, below
  the required size; the second rule (add a deliverability floor) would have
  flipped with about 27 more tiles. The third rule treats a ratio inside the
  model's uncertainty as a tie and breaks it by stated criteria. All three are
  in `yield_model_v1.json` under `selection.rule.history`.
* tess-point predictions must be capped at the last public sector [M].
* Overlapping tiles duplicate stars and inflate pool counts by 0.3% [M]; the
  pool is now de-duplicated and the sky scale uses the union area.

### Assumptions the results rest on [A]

Prior completeness per class and population (section 4 of the memo), the
pipeline efficiencies 0.8 / 0.7 / 0.4 per class, the photon-plus-floor noise
model scaled by 1.5 to QLP's published scatter, the four-class occurrence
table (Howard+2012, Petigura+2013, Dressing & Charbonneau 2015; not the fine
grid of Kunimoto & Matthews 2020), and the treatment of missing contamination
ratios (38% of bright dwarfs) as zero. Prompt 2's injection test replaces the
efficiencies with measurements.

### Still open

1. `targets_v1.csv` is sized to 5.0 expected new signals at mid priors. The
   clean stratum-3 pool holds 9,394 stars (11.4 expected); the list extends by
   re-running with a larger `--expected-new`, and the design extends by more
   tiles from the same seed (prefix-stable). The 20k cap was never binding.
2. TESS-SPOC lists after sector 85 are not on MAST yet; when they appear the
   products stage picks them up on the next run (the missing sectors are
   recorded in `data/survey/cache/products/summary.json`).
3. The TESS EB source is the sectors 1-26 release; later EBs enter the hard
   stop only through TOI, CTOI, or TCE lists.
4. QLP TCEs are not public; a QLP TCE that never became a TOI will not be
   rejected. The CTOI process tolerates that, and prompt 4 re-runs the hard
   stop with fresh catalogs on every survivor.
5. Stratum 4 needs a per-signal (period-based) rejection to be usable; the
   per-star hard stop excludes it by construction.
6. The per-target `resolve_neighbours` path costs one TIC cone query
   (0.4 to 3 s); the survey builder avoids it by passing tile neighbours, and
   prompt 4's survivor re-check should do the same or accept the cost.

## Remediation (2026-09-01, later session): results that supersede Part B

The P1 text above is preserved as written. A review found six issues; the
fixes, measurements and the exact before/after numbers are in
`P1_REMEDIATION_REPORT.md`. What a reader of this handoff needs to know:

* **Acceptance test.** The batch (`check_many`) path now covers all 80 objects
  with category-specific assertions: 20 TOI, 20 CTOI and 10 TESS EB rows reject
  with their own catalog among the sources (50 catalog-known rows), 10 TCE-only
  rows reject with `spoc_tce` as the only source, 20 clean controls pass; 60
  rejects and 20 clean in total, offline and against the live cache [M].
* **TCE neighbours are complete.** Every SPOC TCE host TIC ID (68,232) now has
  TIC coordinates resolved in bulk, cached with provenance, and sits in the
  21-arcsec coordinate tree; 3,160 of those hosts are fainter than Tmag 17 and
  5 are not typed STAR, which the P1 tile-based check could not see. Any
  unresolved ID or query failure is a loud `CatalogFetchError` unless
  `allow_partial_coords=True` is passed (stamped `!partialcoords`). Rebuilding
  the hard stop changed no status among the 20,958 P1 pool stars or the 2,834
  P1 targets [M]. The stop covers what its six catalogs contain; QLP TCEs that
  never became TOIs are not covered (no public list).
* **Contamination.** Missing TIC ratios are no longer zero: they stay NaN in the
  target files with `contamination_ratio_missing`, `contamination_ratio_used`
  and `contamination_policy` beside them; the central policy imputes the
  measured median of the pool (bright dwarfs 0.0163, faint M dwarfs 0.0146),
  the 90th percentile bounds the yield (0.220 / 0.255), and NaN without an
  explicit policy raises. The effect on the stratum-3 list membership is 0 to 2
  IDs; the p90 bound lowers its yield by 3% [M].
* **Occurrence model.** FGK occurrence now comes from the Kunimoto & Matthews
  2020 baseline grid and M-dwarf occurrence from the Dressing & Charbonneau 2015
  Table 3 grid, both transcribed with provenance and cross-checked against the
  papers' marginalized tables (`src/tesshunter/occurrence_grids.py`). The P1
  class model is kept as a named sensitivity. Classes A (single-sector SNR>=9),
  B (stitched SNR>=9, not A) and C (stitched 7.1<=SNR<9) are mutually exclusive
  and sum to the stitched SNR>=7.1 expectation; a unit test proves it.
* **Sample and rule.** The tile sequence was extended (prefix-stable) from 120
  to 240 tiles so that both candidate strata clear a 2.0-expected-signal floor
  (both do from 162 tiles). Selection rule v4, written before the extended sample
  was examined: rank by expected new signals per 1,000 eligible stars under the
  central model; a ratio of at least 1.5 decides; below it the operational
  criteria (light-curve coverage, then brightness) decide. Result: stratum 2
  1.451 against stratum 3 1.006 per 1,000 stars, ratio 1.44 (tile bootstrap 1.38
  to 1.51), inside the margin; coverage 59% against 36% and median Tmag 12.8
  against 14.6 keep **stratum 3 primary, stratum 2 fallback** [M]. The ranking
  is not robust to one adopted input: at the P1 M-dwarf giant rate of 0.02 the
  ratio is 1.59 and stratum 2 wins; the central value was re-anchored to cited
  hot-Jupiter rates (0.01) after that sensitivity was seen, and the decision is
  reported at 0, 0.01 and 0.02 in the memo.
* **Deliverables.** `data/survey/targets_v1.csv`: 819 stratum-3 stars, 5.00
  expected new signals at mid priors (median 12 light-curve sectors; 343 of them
  were in the P1 list of 1,718, 476 come from the new tiles). `targets_v1_fallback.csv`:
  all 2,450 eligible faint M dwarfs, 3.56 expected. Columns as before plus
  `contamination_ratio_missing`, `contamination_ratio_used`,
  `contamination_policy`, `class_A_detectable`, `class_B_detectable`,
  `class_C_detectable`, `occurrence_model`. `yield_model_v1.json` holds every
  input, the twelve model-by-contamination variants with their membership
  changes, the giant-rate and noise variants, the prefix scan, the bootstrap and
  the rule with its four-version history.
