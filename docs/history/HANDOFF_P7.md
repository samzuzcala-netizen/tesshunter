# HANDOFF P7: the audit rules consolidated into the package, with tests

Date: 2026-09-03. Branch `improve/recovery`. Environment as in `HANDOFF_P6.md`
(double-nested repo, `tesshunter_venv` Python 3.13, lightkurve 2.6.0,
transitleastsquares 1.32, wotan 1.10). No package was added. No MAST, Gaia,
SIMBAD or VSX query was made in this prompt: every external record used was
already cached.

Session start state, measured [M]: `git status` clean on d2356dd; 30,660 files
in `data/cache/lightkurve`; `data/survey/audit_lc/` present with 261 stars;
`pytest tests/ -q` **305 passed, 1 skipped**, 109 s. End state: **447 passed,
1 skipped**, 187 s. **No existing test or source file was modified**
(`git status --short tests/ src/` shows no ` M` line); the 305 are the same 305.

Evidence tags: [M] measured this session, [P5]/[P6] taken from those prompts,
[A] an adopted threshold or assumption. **No verdict is produced for any
candidate anywhere in this prompt.** The pipeline finds candidates; nothing here
is a detection and nothing was submitted anywhere.

## Result in one line

**The rules are in the package with 142 tests, and they reproduce prompts 5 and 6
exactly: 823 records re-derived through the wrappers, 0 field differences, 0
decision differences, largest relative difference 0.0 — the prepared arrays are
bitwise identical.** The four measured options are implemented and are the new
default `p7.0`; over the 405 they move Stage A from 7 PASS to 1 PASS, all six
changes PASS -> FAIL and all six on the secondary gate, none FAIL -> PASS.

## 1. What shipped

### New package modules (`src/tesshunter/`)

* `audit_rules.py` — every threshold once, with a one-line origin comment and an
  evidence tag; `RuleSet` (the four prompt-7 options), `LEGACY_RULES` (`p6.2`),
  `DEFAULT_RULES` (`p7.0`), and `thresholds(rules)` returning the whole set as a
  dict for stamping into records.
* `audit_prep.py` — `product_bitmask` (including QLP's low-precision flag),
  `expected_t14_hours`, `detrend_window_days`, `transit_mask`,
  `clean_and_detrend`, `bin_lc`, `clip_binned`, `prepare_series`. Exactly
  `prepare` in `audit_p5.py`.
* `event_vet.py` — `predicted_epochs`, `measure_event`, `removal_reasons`,
  `event_table`, `weighted_mean`, `kept_event_stats`, `sector_beta`,
  `advisory_flags`, `summarise_events`, `stagea_criteria`, `ARTEFACT_CLASSES`,
  `classes_of`. Exactly `events_step` plus the Stage A criteria.
* `star_vet.py` — `deepest_window`, `phase_independent_test`,
  `long_period_window_test` (new), `deep_event_hosts`, `gaia_flag_digest`.
* `secondary.py` (new) — `box_depth`, `phase_scan`, `planet_secondary_bound`,
  `secondary_scan`, from `secondary_scan.py` and `rank16_analysis.py`, using the
  period-aware bound already in `vetting.planetary_secondary_bound_ppt`.
* `ranking.py` (new) — `independent_sectors`, `gaia_penalty_flags`, `score_v2`.

All of it is pure: arrays and already-fetched records in, dicts out. No MAST, no
file paths, no globals inside the rule code.

### The scripts are now wrappers

* `scripts/audit_p5.py` — the four preprocessing functions, `_weighted` and the
  whole body of `events_step` are gone and delegate to the package. What remains
  is the driver: downloads, the private lightkurve cache, the TLS calls, the file
  layout, the CLI. **Command lines and output layouts are unchanged**, plus one
  new optional flag `--rules {p6.2,p7.0}` (default `p6.2`).
* `scripts/revet_p6.py` — `deepest_window`, `phase_independent`, `gaia_flags`,
  `deep_candidates`, `stagea_criteria`, `ARTEFACT_CLASSES` and `classes_of`
  delegate to the package; the module constants are re-exported from
  `audit_rules` so the report code still resolves them. Same `--rules` flag,
  carried through to the slice subprocesses.
* `scripts/rank_survivors.py` — a new **separate** mode `--score v2`. It does not
  re-run the survey and writes no frozen artefact.

### New scripts

* `scripts/p7_reproduce.py` — the Part A acceptance test (below).
* `scripts/p7_options.py` — the Part B measurement over all 405, report-only.
* `scripts/build_audit_fixtures.py` — builds `tests/fixtures/audit/`.

### Tests: 142 new (`pytest tests/ -q` 447 passed, 1 skipped)

| file | tests | what |
|---|---:|---|
| `tests/test_audit_prep.py` | 25 | one per preprocessing rule, on synthetic light curves |
| `tests/test_event_vet.py` | 37 | one per removal rule, each fired **and** just-not-fired |
| `tests/test_star_vet.py` | 28 | the window test, the long-period test, deep hosts, Gaia flags |
| `tests/test_secondary.py` | 15 | the phase scan, the planetary bound, the gate |
| `tests/test_ranking_v2.py` | 14 | the v2 score terms and penalties |
| `tests/test_audit_fixtures.py` | 23 | the committed fixtures reproduce the P5/P6 records |

`tests/fixtures/audit/` (11.9 MB, under the 30 MB budget) holds the per-product
arrays of three real stars — TIC 334678787 (P5 rank 4), TIC 212261364 (P5 rank
2), TIC 233007823 (P6 rank 16, a Stage A PASS) — with one product per sector,
exactly what `choose_per_sector` keeps, plus their stellar parameters, survivor
and candidate rows, and the records they must reproduce. The fixture tests are
offline and need nothing from the git-ignored caches.

### Docs

`docs/RULES.md` (new): every rule, its threshold, its origin and its measured
effect on the 405. `docs/RANKING_SCORE.md` section 5 (new): the v2 score;
sections 1-4 are untouched.

## 2. Part A: the reproduction [M]

`scripts/p7_reproduce.py all --slices 16`, 3.4 minutes.
Record: `data/survey/p7/reproduce_p7.json`.

The reproduction runs in `data/survey/p7/reproduce/`, whose `tls/*_lc.npz`,
`tls/*_forced.json`, `prep/*.json` and `neighbours/*.json` are **hard links** to
the prompt-6 files, so the ephemerides are the ones prompt 6 used and only the
rules are re-run. **Nothing under `data/survey/p6/` was written** (`git status`
on `data/survey/p4 p5 p6` is empty).

| part | records | field differences | decision differences | worst relative difference |
|---|---:|---:|---:|---:|
| prepare (detrend, bin, clip) | 405 | 0 | - | 0.0 |
| Stage A | 405 | 0 | 0 | 0.0 |
| Stage B | 7 | 0 | 0 | 0.0 |
| Stage C (forced TLS + decision replay) | 6 | 0 | 0 | 0.0 |
| **total** | **823** | **0** | **0** | **0.0** |

**Tolerance, stated:** strings, booleans, integers and decisions must be equal
exactly; a float pair counts as equal when `|a - b| <= 1e-12 * max(1, |b|)`. The
largest relative difference actually observed was **0.0** — every number is
bit-identical. Excluded by name: `generated_utc`, `seconds`, `timing_s`,
`prepare_generated_utc`, `lc_npz`, `downloaded_utc`, `verdict_stamped_utc`.

The prepare part additionally re-derived all seven arrays of each candidate's
`_lc.npz` from `data/survey/audit_lc/` and compared them with
`np.array_equal`: **bitwise identical for all 405**, so the port did not change
the detrend, the clips or the binning at the level of a single float.

Notes on scope, as instructed: Stage C re-ran the **forced narrow TLS** and
replayed the Stage C decision on the stored blind-search block; the blind search
itself (29 CPU-minutes in prompt 6) is an input, not a rule, and was not
repeated. Stage B has **7** records (7 entered, 6 passed); all 7 were reproduced,
not only the 6 passers.

## 3. Part B: the four options, measured over all 405 [M]

`scripts/p7_options.py run --slices 16`, 7.5 minutes (the longest slice); 405 records in
`data/survey/p7/options/`, aggregate in `data/survey/p7/options_p7.json`,
0 errors. Report-only: **no candidate is given a verdict**, no blind TLS was run,
the survey was not run. Each candidate is measured under the ephemeris prompt 6
chose for it. Baseline: 7 Stage A PASS, 398 FAIL.

### Option 1 — the full-phase secondary scan

| quantity | value |
|---|---:|
| candidates scanned | 405 |
| dips above 5 sigma: median / p90 / max | 2 / 17.6 / 45 |
| no dip at phase 0 (never gated) | 106 (59 of them have dips elsewhere) |
| clean scans (a primary and nothing else) | 65 |
| reach the gate (a primary and another dip) | 234 |
| **gate FAIL** | **156** of the 234 |
| of those, variability-flagged (> 5 dips) | 78 |
| of those, quiet scans (<= 2 dips) | 41 |
| **gate FAIL among the 7 Stage A passers** | **6** |
| gate measured in SAP / in the detrended flux | 234 / 0 |

Per-passer detail is in `docs/RULES.md` section 6. The scan **independently
reproduces the prompt-6 rank-16 re-analysis**: TIC 233007823, exactly two dips,
primary 2.637 ppt at phase 0.9996 (55.4 sigma), secondary 2.505 ppt at phase
0.6048 (52.0 sigma), 0.95 x the primary, 2.547 +/- 0.047 ppt in SAP, a/R* 27.02,
T_eq 780 K, bound 1.09e-3 ppt, 2,346 x the bound (`docs/REVET.md` section 10 has
2.637/2.505 ppt, 55.4/52.0 sigma, 0.950, 2.516 ppt in SAP, a/R* 27.0, T_eq 780 K,
2,312 x — the small differences are the folded-box SAP measurement here against
the per-event one there).

Rank 98 is the one Stage A passer the gate keeps, and for the right reason: its
second dip is 0.719 ppt in the corrected flux and only 0.281 +/- 0.128 ppt in
SAP, 2.2 sigma over the bound, under the 3-sigma threshold.

### Option 2 — red-noise-inflated depth consistency

| quantity | value |
|---|---:|
| per-sector beta, median over candidates: p25 / median / p75 | 1.045 / 1.083 / 1.184 |
| worst sector's beta: median / p90 / max | 1.959 / 4.581 / 5.0 |
| candidates with a sector at the cap of 5 | 31 |
| depth consistency changes fail -> pass | 34 |
| of those, then pass all six | 10 |
| Stage A PASS under this option alone (vs 7) | 17 |
| the 7 prompt-6 passers that still pass | 7 |

Of the 18 candidates that fail **only** depth consistency, 10 now pass it. The
ones that flip are the ones with large beta; the ones that do not are the deep
eclipsing binaries the rule exists to catch (rank 9, TIC 167304394,
`9.2e-68 -> 8.5e-15`; rank 13, `0 -> 1e-184`; rank 7, `2.5e-199 -> 6.2e-37`).

### Option 3 — the transit-masked detrend

| population | measure | unmasked | masked | ratio |
|---|---|---:|---:|---:|
| the 24 near misses (5 of 6 criteria) | depth / survey depth, p10 | 0.535 | 0.621 | |
| | **median** | **0.667** | **0.830** | **1.224** |
| | p90 | 0.779 | 1.257 | 1.899 |
| kept SNR >= 7 (60 candidates) | median | 0.611 | 0.806 | 1.323 |
| | inside the 0.5-2.0 window | 35 | 40 | |
| kept SNR >= 20 (24) | median | 0.596 | 0.778 | 1.340 |
| all 405 | median | 0.046 | 0.058 | 1.211 |
| | ratio increased / decreased | | | 304 / 93 |

Over the 405 the depth criterion is gained by 14 candidates and lost by 4, and 4
pass all six under this option alone. The whole-population medians are near zero
because most of the 405 have no depth in clean events at all — that is prompt 6's
null, not a property of the detrend.

### Option 4 — the long-period window test

| quantity | value |
|---|---:|
| applies (no sector spans 1.5 periods) | 295 of 405 |
| does not apply | 110 |
| median survey period, applies / does not | 72.2 d / 12.2 d |
| sectors with an observed epoch, where it applies: median / p90 | 7 / 15 |
| fraction of sectors fully removed: median / p75 / p90 | 0.40 / 0.50 / 0.667 |
| **flagged** (> 0.5) | **72** |
| flagged among the 7 Stage A passers / the 398 failures | 1 / 71 |

### All four together (`p7.0`)

| | `p6.2` | `p7.0` |
|---|---:|---:|
| Stage A PASS | 7 | **1** |

Six change, **all PASS -> FAIL, all six on the secondary gate** (ranks 16, 250,
279, 289, 325, 398). **None changes FAIL -> PASS.** 152 keep their decision and
gain a variability or long-period flag. Per-criterion movement over all 405:

| criterion | failing under p6.2 | failing under p7.0 | gained | lost |
|---|---:|---:|---:|---:|
| kept events >= 3 | 52 | 62 | 0 | 10 |
| kept SNR >= 7 | 345 | 337 | 9 | 1 |
| top share <= 50% | 251 | 281 | 12 | 42 |
| SNR without top >= 5 | 356 | 351 | 5 | 0 |
| depth 0.5-2x survey | 359 | 349 | 14 | 4 |
| depths consistent | 75 | 104 | 13 | 42 |

The six PASS -> FAIL agree, one for one, with what prompt 6 concluded about those
same candidates on independent evidence (`docs/REVET.md` section 5): a catalogued
contact eclipsing binary, an eccentric eclipsing binary, and two stars whose Gaia
astrometry is not that of a single object. The one survivor, rank 98
(TIC 201247574), is the catalogued rotational variable, so it is not a new
candidate either.

### The v2 ranking score

`scripts/rank_survivors.py --score v2`, 405 rows, written to
`data/survey/p4/survivors_score_v2.csv` and `score_v2.json`. **`survivors.csv`
and the frozen score are untouched.**

| quantity | value |
|---|---:|
| Spearman rho, frozen rank vs v2 rank | **-0.0063 (p = 0.90)** |
| zeroed by the secondary gate | 156 |
| score exactly zero | 221 |
| with a deep-host penalty | 109 |
| with a cached Gaia record | **36 of 405** |
| with a Gaia penalty (of those 36) | 13 |
| score: p90 / max (of 2) | 0.717 / 1.735 |

## 4. What was refuted or newly found [M]

1. **The secondary gate, as specified, is not a secondary-eclipse test in this
   population — it is a "second dip measurable in SAP" test.** At these periods
   the deepest secondary a planet could produce is 3e-5 to 2e-3 ppt, thousands of
   times below the measurement precision, so "more than 3 sigma above the
   planetary bound" reduces to "the SAP depth at the deepest off-phase dip is
   more than 3 sigma from zero". That is correct physics and it is why the gate
   is decisive on rank 16, but it is why the gate fails 156 of 405 rather than a
   handful. The `variability_flag` separates the cases: 78 of the 156 failures
   are variability, and 41 have quiet scans of at most two dips, which are the
   genuine secondary detections. **The threshold is not changed here** (rules
   frozen per the prompt); a second pass should decide whether the gate should
   also require a quiet scan.
2. **The red-noise inflation is far more powerful than its description
   suggests.** A per-sector beta clipped at 5 turns `p = 1.2e-24` into `p = 0.97`
   (rank 234), `1.4e-35` into `0.65` (rank 27), `2e-48` into `0.50` (rank 29) and
   `8.4e-80` into `0.39` (rank 32). 31 candidates have a sector at the cap. The
   white p-value is kept on every record so the size of the correction is always
   visible, but a gate on the inflated p-value is a much weaker gate than the
   same number on white errors, and that should be stated wherever it is used.
3. **Options 2 and 3 pull in opposite directions on depth consistency.** The
   inflation alone moves 34 candidates from fail to pass; the masked detrend, by
   recovering more depth, makes depth *variation* more significant. Under all
   four together the criterion is gained by 13 and lost by 42, net **worse**
   (75 -> 104 failing). The same happens to the top-event share (251 -> 281),
   because the masked detrend raises the strongest event more than the others.
   Neither option is wrong; the interaction was not anticipated and is measured
   here for the first time.
4. **P6's "the wotan window absorbs part of the transit, 0.5-0.9" is confirmed
   and quantified.** On the 24 candidates that carry a real dip the unmasked
   depth is 0.535 to 0.779 of the survey depth (p10-p90, median 0.667); masking
   the transits moves the median to 0.830 and a median ratio of 1.224. The Stage
   A window of 0.5-2.0 is indeed generous on one side and tight on the other.
5. **The frozen ranking and the v2 ranking are unrelated**, Spearman
   rho = -0.0063, p = 0.90, n = 405. Prompt 6 found the frozen rank uncorrelated
   with the kept-event SNR (rho = -0.065, p = 0.19); the full v2 score, which adds
   the sector count and the star-level penalties, is not merely uncorrelated with
   the kept-event SNR but with the frozen order itself.
6. **The v2 Gaia penalty can be evaluated for only 36 of 405 candidates**, because
   Gaia DR3 was queried in prompts 5 and 6 only for the stars that reached Stage B
   and this prompt queries nothing. Every row records `gaia_record_available`, so
   the restriction is visible rather than silent, but the Gaia term is currently
   decorative for 91% of the list.
7. **A record-shape defect, minor:** the Stage B `phase_independent` block stores
   `t14_hours` rounded to 3 decimal places, and the window it used is derived from
   the unrounded value. A Stage B record therefore cannot be replayed exactly from
   its own stored fields (the derived `window_days` differs in the 5th decimal).
   Found because a fixture test tried to do exactly that. **Not changed here.**
8. **`secondary_over_planet_bound` is negative for 34 candidates**: the deepest
   off-phase dip in the corrected flux is a *bump* in raw SAP. This is not a
   defect — it is the SAP re-measurement doing its job, and those candidates
   correctly pass the gate.
9. **Not refuted:** every rule and threshold of prompts 5 and 6 reproduces
   exactly. Nothing in the port changed a decision or a number.

## 5. Assumptions [A]

1. **The drivers default to `p6.2`, the package defaults to `p7.0`.** The prompt
   requires `audit_p5.py` and `revet_p6.py` to keep their command lines and output
   layouts and requires the P6 records to reproduce; it also requires the new
   default to be `p7.0`. Both are satisfied by making `LEGACY_RULES` the default
   of the two frozen drivers (with `--rules p7.0` to opt in) and `DEFAULT_RULES`
   the package default, which every new record (`p7_options`, `score_v2`) carries.
2. **The mask ephemeris for option 3** is the ephemeris prompt 6 chose for that
   candidate, and one prepare is run per candidate, not one per ephemeris. This
   makes the masked and unmasked depths a like-for-like comparison on the same
   events.
3. **The secondary gate is measured on the SAP flux detrended with the same
   biweight**, not on per-event SAP measurements as `rank16_analysis.py` did. The
   biweight can only under-measure a dip, so this is conservative in the direction
   that matters: the gate can fail a candidate only on a dip that is really there.
4. **`teff` for the planetary bound** comes from the cached TIC record; where the
   TIC has none, 5500 K is used (the same fallback `secondary_scan.py` used).
5. **The v2 `astrometric_excess_noise_sig` penalty is at 100**, as the prompt
   specifies, not Stage B's flag threshold of 2. At 2 the penalty would fire on
   most bright stars and move the whole list down together.
6. The reproduction's float tolerance is `1e-12` relative; the observed maximum
   was 0.0.

## 6. Still open

1. **The secondary gate's threshold** (finding 1). Whether it should require a
   quiet scan, and whether "3 sigma above a bound that is 1e-3 ppt" should instead
   be "3 sigma above zero **and** a scan with at most N dips", is a decision for a
   second pass with its own measurement.
2. **Whether the inflated p-value should be the gate at all** (finding 2), or
   whether the record should carry both and the gate stay on white errors with the
   beta reported. This prompt implements the prompt's instruction; it does not
   defend it.
3. **The interaction between options 2 and 3** (finding 3) means `p7.0` is not
   simply "p6.2 plus four improvements". If a future pass wants the depth
   criterion to behave as prompt 6 intended, the two need to be re-derived
   together rather than stacked.
4. **Gaia for the other 369 candidates** (finding 6). One 1-arcmin cone per star
   over 261 stars would make the v2 penalty real; it needs a prompt that permits
   the queries.
5. **The Stage B t14 rounding** (finding 7).
6. **`fit_step`, `write_ctoi_fields` and `revet_p6.py verdict` are still
   untested code.** Nothing reached a verdict that needs them, in this prompt
   either. They were not ported and are unchanged.
7. **Prompt 8's long-period search** is what this was built for. `p7.0` is
   available as `--rules p7.0` on both drivers, and `tesshunter.secondary` is a
   cheap gate (about 10 s per candidate including the SAP detrend) to put ahead of
   the expensive stage, which is what the rank-16 blind spot argued for.

## 7. Files

* New: `src/tesshunter/{audit_rules,audit_prep,event_vet,star_vet,secondary,ranking}.py`;
  `scripts/{p7_reproduce,p7_options,build_audit_fixtures}.py`;
  `tests/{test_audit_prep,test_event_vet,test_star_vet,test_secondary,test_ranking_v2,test_audit_fixtures}.py`;
  `tests/fixtures/audit/` (11.9 MB); `docs/RULES.md`; this file.
* Modified: `scripts/audit_p5.py`, `scripts/revet_p6.py` (wrappers, `--rules`),
  `scripts/rank_survivors.py` (`--score v2`), `docs/RANKING_SCORE.md` (section 5),
  `.gitignore`.
* Data, committed: `data/survey/p7/reproduce_p7.json`,
  `data/survey/p7/options_p7.json`, `data/survey/p7/options/` (405 records,
  5.3 MB), `data/survey/p4/survivors_score_v2.csv`, `data/survey/p4/score_v2.json`.
* Data, git-ignored: `data/survey/p7/{reproduce,reproduce_tls,slices,logs}/` —
  the reproduction scratch roots are hard links to the prompt-6 inputs and the
  slices and logs are per-run bookkeeping.
* **Unchanged:** everything under `data/survey/p4`, `p5` and `p6`, and every file
  under `src/` and `tests/` that existed before this prompt.

## 8. Re-running

```
py = C:/Users/seanj/Downloads/tesshunter_venv/Scripts/python.exe
$py -m pytest tests/ -q                                  # 447 passed, 1 skipped, ~3 min
$py scripts/build_audit_fixtures.py                      # rebuild tests/fixtures/audit/
$py scripts/p7_reproduce.py all --slices 16              # Part A, ~3.4 min
$py scripts/p7_options.py run --slices 16                # Part B, ~7.5 min
$py scripts/p7_options.py tables                         # the aggregate tables alone
$py scripts/rank_survivors.py --score v2                 # the v2 order, frozen score untouched
$py scripts/revet_p6.py --rules p7.0 stageA --slices 16  # the p7.0 funnel, if a pass wants it
```

`p7_reproduce.py` and `p7_options.py` are idempotent: a settled record with the
right `rules_version` short-circuits, and `--force` re-runs it.
