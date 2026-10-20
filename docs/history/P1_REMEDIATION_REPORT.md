# P1 remediation report

Date: 2026-09-01 (later session than the P1 handoff). Branch `improve/recovery`.
Scope: the six review findings on Prompt 1 (hard-stop cross-match and survey
population). No detection or vetting code was touched. Nothing was pushed or
submitted anywhere. The pipeline finds candidates; nothing here is a detection.

Session start, measured: `git status` clean at commit 8104345; 121 light-curve
cache files; six catalog caches present; `pytest tests/ -q` 205 passed, 1 skipped.

Evidence tags: [M] measured, [A] adopted assumption, [R] refuted or not possible.
The verdict labels requested by the review (confirmed / partially confirmed /
refuted) describe whether a finding was borne out; the word is used in no other
sense in this repository.

## Summary table

| # | finding | verdict | fix | before -> after |
|---|---|---|---|---|
| 1 | batch acceptance test covered 50 of 80 objects; handoff said "30 known-by-TIC" | confirmed | batch test over all 80 with category-specific source assertions; wording corrected | 50 -> 80 objects in the batch path; 60 rejects (50 catalog-known + 10 TCE-only) and 20 clean, offline and live [M] |
| 2 | TCE neighbours only catchable through the Tmag<=17, objType=STAR tile list | confirmed | every TCE host TIC ID resolved to TIC coordinates in bulk, cached with provenance, placed in the coordinate tree; loud failure policy; four fixture tests | 68,232 / 68,232 TCE hosts resolved, 3,160 of them fainter than Tmag 17 and 5 non-STAR (holes in P1); rebuilt hard stop: 0 status changes among the 20,958 P1 pool stars and the 2,834 P1 targets [M] |
| 3 | missing contamination ratio treated as 0 | confirmed | NaN preserved; `contamination_ratio_missing` / `_used` / `_policy` columns; explicit fill policy (central: measured median), p90 and zero variants; NaN without a policy raises | S3 new per 1,000: zero 1.009, median 1.006, p90 0.975; target membership changes 0 to 2 IDs across policies [M] |
| 4 | S2-vs-S3 comparison depended on the 120-tile stopping point and on rules changed after seeing results | confirmed | rule v4 fixed before the extended sample; tiles extended to 240 (prefix-stable); both strata clear the 2-signal floor from 162 tiles; exact prefix scan and tile bootstrap | S3 remains primary under the central model (ratio 1.44, inside the 1.5 margin; secondary criteria decide); S2 would be primary at the P1 giant rate of 0.02 [M] |
| 5 | Kunimoto & Matthews 2020 requested, not used | confirmed | K&M 2020 FGK grid and DC15 M-dwarf grid transcribed with provenance and cross-checked; both models run | K&M lowers S3 from 1.26 to 1.01 new per 1,000; DC15 grid moves S2 from 1.52 to 1.45 (with the giant rate re-anchored); decision unchanged under the central model [M] |
| 6 | A/B/C classes need proof of exclusivity | partially confirmed (code was correct, docs abbreviated) | unit test: A+B+C = stitched SNR>=7.1 expectation, A+B = stitched SNR>=9; docs clarified | test passes for all four occurrence models [M] |

Suite after remediation [M]: `pytest tests/ -q` 222 passed, 1 skipped (the opt-in live-catalog
acceptance test, which passed separately with `TESSHUNTER_LIVE_CATALOGS=1`), 223 s;
`tests/test_catalog_crossmatch.py` 35 passed, `tests/test_survey_yield.py` 11 passed.

## Finding 1: the 80-object acceptance test

Confirmed. `_run_acceptance` in `tests/test_catalog_crossmatch.py` checked all
80 objects through `check()` but pushed only TOIs, TCE-only stars and clean
controls (50 rows) through `check_many()`.

Fix [M]: the batch frame now holds all 80 rows (20 TOI, 20 CTOI, 10 TESS EB,
10 TCE-only, 20 clean; the category counts are asserted). For every row the
batch status must equal the single-target status, the set of matched sources
must equal the single-target set, a TOI/CTOI/EB row must carry its own catalog
among the sources, a TCE-only row must carry exactly `{spoc_tce}`, a clean row
must carry none; the final tally is asserted as 60 REJECT and 20 CLEAN.
Result: offline fixtures pass; the same test against the live cache
(`TESSHUNTER_LIVE_CATALOGS=1`) passes [M]. `HANDOFF_P1.md` now states "50
catalog-known rows plus 10 TCE-only rows, 60 rejects, 20 clean"; the "30
known-by-TIC" sentence is gone.

## Finding 2: SPOC TCE neighbour matching

Confirmed. In P1 a TCE host could only flag a target if the host appeared in
the target's own tile table (radius 0.75 deg, Tmag <= 17, objType STAR). A host
across the tile boundary, fainter than 17, or not typed STAR was invisible to
the neighbour check.

Fix [M]: `catalog_crossmatch.resolve_tic_coordinates()` resolves every unique
TIC ID of a coordinate-less source through `Catalogs.query_criteria(catalog=
"Tic", ID=chunk)` in chunks of 3,000, caches the result in
`data/cache/catalogs/spoc_tce/tic_coords.csv` with a `tic_coords.meta.json`
stamp (provenance string, chunk size, requested / resolved / unresolved counts,
the unresolved IDs, fetch time, sha256 of the cache, counts fainter than Tmag
17 and not typed STAR), and merges the coordinates into the normalized TCE
table, so TCE hosts enter the same 21-arcsec cKDTree as every other source.
TIC coordinates do not change for a fixed TIC version, so the cache never
expires; only IDs absent from it are queried. The normalized schema version
was bumped to 2 so old caches are rebuilt.

Live resolution [M]: 68,232 unique TCE host IDs requested, 68,232 resolved,
0 unresolved; 23 chunks; the full catalog reload including this step took 423 s
(the resolution itself about 4 min). Of the hosts, 3,160 (4.6%) are fainter
than Tmag 17 and 5 are typed EXTENDED: exactly the objects the P1 tile query
could not have seen. `catalog_versions_v1.json` carries the coordinate stamp.

Failure policy (documented in the module docstring and enforced by tests): a
TIC query failure raises `CatalogFetchError` (three retries with backoff); an
ID the TIC does not return is recorded in the stamp and also raises unless
`allow_partial_coords=True` is passed, in which case the version string
carries `!partialcoords`, `KnownObjectCatalog.any_partial_coords()` is True,
and the unresolved host still rejects by TIC ID but has no position; a cached
table with unresolved rows is refused again on the next default load. Nothing
degrades to CLEAN silently.

Tests added (recorded fixtures: `tests/fixtures/catalogs/spoc_tce_tic_coords.csv`,
251 hosts cut from the live cache, plus two recorded edge cases in
`acceptance_ids.json`): a TCE-only host across a tile boundary (TIC 242548962,
target 10 arcsec away, empty neighbour table) is flagged through the coordinate
tree; a TCE-only host at Tmag 17.5 (TIC 1972864999, target 8 arcsec away,
neighbour table without the host) is flagged; batch and single-target paths
agree on four constructed targets (two inside 21 arcsec, two outside); a TIC
outage raises; one dropped ID raises by default, loads with `!partialcoords`
when allowed, and the cached partial table is refused afterwards.

Rebuilt hard stop [M]: on the 120-tile P1 pool the status of every one of the
20,958 stars is unchanged (CLEAN 20,859, FLAG 7, REJECT 92 both before and
after); all 1,718 stars of the P1 `targets_v1.csv` and all 1,116 of the P1
fallback remain CLEAN. On the 240-tile pool: 42,226 stars, REJECT 204 (TCE
only 135, CTOI 20, TCE+TOI 17, TCE+EB 12, others 20), FLAG 19 (13 through a
TCE neighbour, 3 TCE+TOI, 1 archive, 1 CTOI+TCE+TOI, 1 TCE+EB), CLEAN 42,003.
No FLAG in either pool arose from a host that the tile list lacked, so the
residual risk was real but did not materialize in the surveyed sky.

Completeness claims: the README paragraph and the memo now say the stop covers
what its catalogs contain and name what it does not (QLP TCEs that never
became TOIs; eclipsing binaries found after the Prsa 2022 release that are in
no other list; TESS-SPOC product lists after sector 85 are not on MAST yet).
The phrase "guarantees we cannot rediscover" occurs only in `CTOI_PROMPTS.md`,
which is the prompt text itself and was left as written.

## Finding 3: missing contamination ratios

Confirmed. `yield_for_stars` used `np.nan_to_num(contratio, nan=0.0)`;
37.3% of the bright dwarfs and 1.8% of the faint M dwarfs have no TIC ratio,
and the missing stars are fainter (median Tmag 13.27 against 12.41 for measured
stars) [M], so the missingness is not random. The TIC computes the ratio only
for Candidate Target List members, and CTL membership favours isolated stars;
"missing" therefore means "not evaluated", and the measured sample is if
anything biased low.

Fix [M]: `select_pool` keeps NaN and adds `contamination_ratio_missing`;
`survey_yield.per_star_yield` requires an explicit `contam_fill` whenever NaN
is present and raises otherwise (tests: `test_missing_contamination_without_policy_raises`,
`test_explicit_fill_is_applied_and_is_not_the_most_favourable_by_default`,
`test_measured_values_are_used_even_when_a_fill_is_given`). Policy
(`survey_yield.CONTAMINATION_POLICY`): central = measured median of the same
pool's CLEAN stars (bright 0.0163, faint M 0.0146); conservative = measured 90th
percentile (0.220, 0.255); zero kept only to reproduce P1. Target files carry
`contamination_ratio` (NaN preserved), `contamination_ratio_missing`,
`contamination_ratio_used`, `contamination_policy`; the metadata records the
policy, fill value, counts and all three fills. Every variant re-scores every
star and re-cuts the list.

Sensitivity, central occurrence model, 240 tiles, expected new signals per
1,000 stars at mid priors and the stratum-3 list cut at 5.0 [M]:

| policy | S2 | S3 | S3 list size | IDs changed vs central | S3 stars for 2 / 3 / 5 |
|---|---:|---:|---:|---|---|
| zero (P1 behaviour) | 1.452 | 1.009 | 819 | 0 in, 0 out | 1,982 / 2,973 / 4,956 |
| measured median (central) | 1.451 | 1.006 | 819 | - | 1,989 / 2,983 / 4,972 |
| measured p90 | 1.446 | 0.975 | 819 | 1 in, 1 out | 2,052 / 3,077 / 5,129 |

The per-star ranking barely moves because only 3 of the 819 listed stars lack a
ratio; the population-level yield falls 3% under the p90 bound. The stratum-2
list is the full eligible set (2,450 stars, 49 imputed) in every variant.

## Finding 4: the stopping point

Confirmed. Versions 2 and 3 of the rule were written after the 60- and 120-tile
results were seen, and version 2 made the outcome depend on how many tiles had
been drawn.

Fix [M]: rule version 4 (`SELECTION_RULE` in the script, with versions 1 to 3
verbatim in `history`) was written into the script before the extended sample
was examined: extend the prefix-stable sequence until both candidates deliver
at least 2.0 expected new signals under the central model; rank by expected new
signals per 1,000 eligible stars at mid priors; a ratio at or above 1.5 decides;
below it the operational secondary criteria decide (fraction of the eligible
pool with 4+ sectors of light curves, then median Tmag). Deliverability is no
longer a criterion. The tile sequence was extended from 120 to 240 (704,096 TIC
stars, pool 42,226 unique, 237 duplicates dropped, union area 420.0 deg^2, all-sky
scale 64.6); the QLP and TESS-SPOC target lists were re-streamed for the larger
pool.

Prefix scan (exact: per-star scores do not depend on the number of tiles) [M]:
stratum 3 clears the floor at 27 tiles, stratum 2 at 162 (147 under the P1
giant rate of 0.02), both at 162; the ratio of densities is a property of the
stars, not of the prefix. Tile bootstrap (1,000 draws over tiles): stratum 2
density 16/50/84th percentiles 1.38 / 1.44 / 1.51 per 1,000 against stratum 3
0.96 / 1.01 / 1.06; ratio 1.38 / 1.44 / 1.51; probability that the ratio lies
outside the 1.5 margin 0.20.

| quantity | P1 (120 tiles, legacy model, zero contamination) | remediated (240 tiles, central model) |
|---|---|---|
| eligible sampled, S2 / S3 | 1,116 / 9,394 | 2,450 / 20,636 |
| all-sky estimate, S2 / S3 | 143,994 / 1,212,077 | 158,345 / 1,333,719 |
| 4+ light-curve-sector coverage, S2 / S3 | 33% / 54% | 36% / 59% |
| new per 1,000 (mid), S2 / S3 | 1.464 / 1.212 | 1.451 / 1.006 |
| deliverable from sample (mid), S2 / S3 | 1.63 / 11.38 | 3.56 / 20.75 |
| ratio | 1.21 | 1.44 |
| primary / fallback | 3 / 2 (v3 tie-breakers incl. deliverability) | 3 / 2 (v4 secondary criteria: coverage 59% vs 36%, Tmag 12.8 vs 14.6) |
| targets_v1.csv | 1,718 stars (S3), 5.0 expected | 819 stars (S3), 5.0 expected |
| fallback list | 1,116 stars (S2), 1.63 expected | 2,450 stars (S2), 3.56 expected |

Stratum 3 remains primary. The larger sample and the new model reach 5.0
expected new signals with fewer, better-ranked stars (median 12 sectors with a
light curve against 9). Membership: 343 of the new 819 come from the first 120
tiles and all 343 were in the P1 list; 476 come from tiles 120 to 239; 1,375 P1
stars are no longer needed to reach the 5.0 cut. The stratum-2 list contains
all 1,116 P1 fallback stars plus 1,334 from the new tiles.

The decision is not robust to one adopted input, disclosed in full: the
occurrence of 4 to 20 Earth-radius planets around M dwarfs, which lies outside
DC15. P1 used 0.02 per star without a citation. The sensitivity scan (run before
the central value was changed) gave a ratio of 1.29 at 0, 1.44 at 0.01 and 1.59
at 0.02; at 0.02 the rule picks stratum 2. The central value was then anchored
to published rates (hot Jupiters 0.19% and 0.27%, Bryant+2023 and Gan+2023,
plus an allowance for 4-8 Re) at 0.01, and this revision is recorded in
`occurrence_grids.DC15_M_GIANTS_ADOPTED["revision"]`, in the JSON and in the
memo, with the decision shown at all three values. With the faint-end noise
variant (x1.4 for Tmag > 13.5) stratum 3 is primary at every giant rate.

## Finding 5: Kunimoto & Matthews 2020

Confirmed. Implemented in `src/tesshunter/occurrence_grids.py`: the baseline
FGK grid (9 period bins 0.78 to 400 d, factor 2; 10 radius bins 0.5 to 16 Re)
transcribed cell by cell from the figure in the arXiv:2004.05296 source
(`FGK_occurrence.png`; Vizier holds no table for this paper), with the quoted
uncertainties and the 84.1th-percentile upper limits of the empty cells kept
alongside. Cross-check against the paper's own marginalized table [M]: 2-2.83
Re P<50 d 18.60% (paper 18.6), 2-4 Re P<50 d 25.12% (25.2), 1-2 Re P<50 d
16.06% (16.2), 4-8 Re 1.49% (1.6), 8-16 Re 1.48% (1.6), 2-4 Re P<100 d 35.26%
(35.4), 1-2 Re P<100 d 17.89% (18.1); the residuals are the empty cells taken
as zero. The grid covers P <= 100 d without extrapolation. Dressing &
Charbonneau 2015 was likewise transcribed as a grid from its Table 3 (arXiv
source) and checked against Table 4 (1-1.5 Re P<50 d 56.25%, 1.5-2 Re 46.6%
against 45.95, 1-4 Re P<200 d 2.49 against the abstract's 2.5). The P1 M-dwarf
class model had 0.25 for 2-4 Re at P<50 d; the grid gives 0.61.

Both models run on the 240-tile sample (mid priors, central contamination) [M]:

| model | S2 new /1000 | S3 new /1000 | ratio | deliverable S2 / S3 | S2 stars for 2 / 3 / 5 | S3 stars for 2 / 3 / 5 | primary |
|---|---:|---:|---:|---|---|---|---|
| K&M 2020 FGK + DC15 grid (final) | 1.451 | 1.006 | 1.44 | 3.56 / 20.75 | 1,378 / 2,067 / 3,445 | 1,989 / 2,983 / 4,972 | 3 (secondary criteria) |
| legacy FGK + legacy M classes (P1) | 1.523 | 1.255 | 1.21 | 3.73 / 25.91 | 1,313 / 1,969 / 3,282 | 1,593 / 2,390 / 3,983 | 3 |
| K&M 2020 FGK + legacy M classes | 1.523 | 0.977 | 1.56 | 3.73 / 20.16 | 1,313 / 1,969 / 3,282 | 2,047 / 3,071 / 5,118 | 2 |
| legacy FGK + DC15 grid | 1.451 | 1.284 | 1.13 | 3.56 / 26.50 | 1,378 / 2,067 / 3,445 | 1,558 / 2,336 / 3,894 | 3 |

No incompatibility was found, so the K&M grid is the final FGK basis and the
legacy model stays as an explicit sensitivity. The mixed row (K&M FGK with the
P1 M-dwarf classes, which carry the uncited 0.02 giant rate) is the one that
would choose stratum 2.

## Finding 6: classes A, B, C

Partially confirmed: the subtraction implementation was correct; the handoff
wording was abbreviated. `tests/test_survey_yield.py::test_classes_partition_the_stitched_expectation`
now proves, for all four occurrence models, that A + B + C equals the stitched
SNR >= 7.1 expectation and A + B equals the stitched SNR >= 9 expectation per
star (to 1e-9 relative), that B and C are non-negative, and that adding sectors
never changes A. The definitions are stated in `survey_yield.py`, in the memo
(section 4) and in the handoff remediation section.

## Files changed

* `src/tesshunter/catalog_crossmatch.py`: TIC coordinate resolution, cache, stamps, failure policy, schema v2.
* `src/tesshunter/occurrence_grids.py` (new): K&M 2020 and DC15 grids with provenance.
* `src/tesshunter/survey_yield.py` (new): the yield model as an importable module.
* `scripts/build_survey_population.py`: grid-based yield, contamination policy, rule v4, prefix scan, bootstrap, variants, fallback file; default 240 tiles.
* `scripts/write_population_memo.py`: regenerated memo with the new sections.
* `scripts/build_crossmatch_fixtures.py`: coordinate fixture and recorded edge cases.
* `tests/test_catalog_crossmatch.py` (35 tests), `tests/test_survey_yield.py` (11 tests, new).
* `data/survey/`: regenerated `yield_model_v1.json`, `targets_v1.csv` (819), `targets_v1_fallback.csv` (2,450), both `.meta.json`, `catalog_versions_v1.json`.
* `docs/POPULATION.md`, `HANDOFF_P1.md` (remediation section appended; P1 text preserved), `README.md`.

## Remaining limitations

* The hard stop covers its six catalogs. QLP TCEs that never became TOIs have
  no public list; the TESS EB source is the sectors 1-26 release; TESS-SPOC
  product lists after sector 85 are not on MAST.
* The yield model's prior completeness, pipeline efficiency and noise model are
  adopted; prompt 2's injection test replaces the efficiency with a measurement.
* The stratum ranking sits inside the model's uncertainty: the K&M-versus-legacy
  FGK choice, the M-dwarf giant rate, and the faint-end noise each move the
  ratio across the 1.5 margin in one direction or the other. Both lists are
  delivered so prompt 2 can measure completeness on both.
* The stratum-2 list is the full eligible set (3.56 expected signals, below the
  5.0 cut), so it includes stars with very high measured contamination; the
  per-star score column lets prompt 2 prioritize.
* The occurrence grids are transcriptions of published posteriors; upper-limit
  cells are zero in the central model.

## Commands used

```bash
# start state
git status && git log --oneline -3
python -m pytest tests/ -q
# extend the seeded tile sample (prefix-stable) and stream the product lists
python scripts/build_survey_population.py tiles --n-tiles 240
python scripts/build_survey_population.py tiles sectors products --n-tiles 240 --product-workers 4
# resolve TCE host coordinates (refresh of the spoc_tce source), then the full chain
python -c "from tesshunter import catalog_crossmatch as cx; cx.load_source('spoc_tce', refresh=True)"
python scripts/build_survey_population.py tiles sectors products xmatch yield targets --n-tiles 240
python scripts/write_population_memo.py
# fixtures and tests
python scripts/build_crossmatch_fixtures.py
TESSHUNTER_LIVE_CATALOGS=1 python -m pytest tests/test_catalog_crossmatch.py -q
python -m pytest tests/test_survey_yield.py -q
python -m pytest tests/ -q
```

(Python is `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe` with
`LIGHTKURVE_CACHE=<repo>\data\cache\lightkurve` and `PYTHONIOENCODING=utf-8`.)
