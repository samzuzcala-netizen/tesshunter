# HANDOFF P8.5: prompt 8, Part 1 done through the runs; the rest of prompt 8 for a fresh session

Date: 2026-09-04/05. Branch `improve/recovery`. Environment as in `PROMPT_P8.md` (double-nested
repo, `tesshunter_venv` Python 3.13, 24 cores). This session stopped, on the user's instruction, at
the end of the long Part 1e runs. Everything below the line "RESUME HERE" is what a new session does,
in order, to finish prompt 8; everything above it is what this session shipped, measured and found.
`PROMPT_P8.md` is still the specification; this file only says where it stands.

Evidence tags: [M] measured this session, [Pn] taken from prompt n, [A] adopted. No candidate has
been given a verdict; nothing was submitted anywhere. The pipeline finds candidates.

RESUME HERE (fresh session): read this file, then `PROMPT_P8.md`, then run the step list in
section 6 from step 1 (steps 2-collect and 4 are already done). Do not re-run anything in section 1: the population, the neighbour records,
the raw product store, the injection / false-alarm / 600-second runs and the prompt-6/adversarial
half of the Part 3 instrument are on disk and committed.

---------------------------------------------------------------------

## 1. What shipped (all committed; latest commit at the top of `git log`)

### Population (Part 1a) [M]

`scripts/build_p8_population.py all --seed 20260904` -> `data/survey/targets_p8.csv` (2,000 rows),
`targets_p8.meta.json`, `population_p8.json`, `catalog_versions_p8.json`; memo
`docs/POPULATION_P8.md` (`scripts/write_population_p8_memo.py`, rerun it whenever the JSONs change).

| cut, in order | stars |
|---|---:|
| TIC query envelope, 36 declination strips of 5 deg (Tmag 12.5-14.5, Teff 2000-3600, R <= 0.50, objType STAR) | 182,423 |
| \|b\| >= 20 | 117,171 |
| Teff < 3600 K | 116,935 |
| radius < 0.45 Rsun | 91,064 |
| lumclass DWARF or missing (0 missing) | 91,064 |
| Tmag 12.5-14.0 | 43,772 |
| Gaia dwarf check pass (no_parallax 3,251; overluminous 243; underluminous 62) | 40,216 |
| >= 3 sectors at 200 s with a QLP or TESS-SPOC light curve | 11,069 |
| FFI-only, minority rule (zero 2-min sectors: 9,285) | 10,512 |
| hard stop CLEAN (REJECT 493, FLAG 30; catalogs downloaded 2026-09-04 18:48 UTC) | **9,989** |
| ranked by the prompt-1 model score and cut | **2,000** |

Sectors: tess-point capped at sector 105 (the latest with a public QLP target list on
2026-09-04; TESS-SPOC lists end at sector 85, QLP covers 1-105; MIT 2-minute lists 1-105 all
present). No relaxation was needed; the pre-registered ceiling-extension condition (coverage
14.0-14.5 >= 0.8 x coverage 13.5-14.0) was met (0.272 against 0.273, ratio 0.997) but not used.
The target list: Tmag p50 13.29, Teff p50 3374 K, radius p50 0.337 Rsun, 200-s sectors with a
light curve p10/p50/p90 = 4/8/18, 600-s sectors 1/5/12, 2-minute sectors among the search sectors
p50 = 0 (1,374 stars have none), 1,948 have at least one 600-s sector, 764 north; a 1 R_earth
planet is 0.74 ppt and a 2 R_earth planet 2.97 ppt on the median star. The prompt-1 model score
(ranking only) sums to 18.35 at mid priors. The ranking favours continuous-viewing-zone stars
(dec p10/p90 = -73 / +74), which are the expensive ones to search (below).

### Gaia, SIMBAD, VSX for every star (Part 1b) [M]

`scripts/p8_neighbours.py bulk` then `stars --workers 2`: 2,000 of 2,000 complete in 16.5 min
(records `data/survey/p8/neighbours/tic<id>.json`, the layout `star_vet.gaia_flag_digest` and
`ranking.gaia_penalty_flags` read; summary `data/survey/p8/neighbours_p8.json`). SIMBAD is fetched
in bulk (one `query_region` per 100 coordinates, 40 s each; a single-star query costs 32 s) and VSX
in bulk (500 coordinates, 3 s); only the Gaia cone is per star (1.7 s). Target match: TIC Gaia id
635, nearest within 5 arcsec 1,252, nearest within 5 arcsec after propagating the TIC proper motion
to 2016 113 (these nearby M dwarfs move arcseconds; without the propagation they had no match).
Target flags: RUWE > 1.4 132, ipd_frac_multi_peak > 10 13, astrometric_excess_noise_sig > 2 749,
non_single_star 35, phot_variable 171; VSX entry within 1 arcmin 302; a neighbour within 3 px bright
enough to make a 1 ppt dip if totally eclipsed 1,874 of 2,000 (the 1-ppt criterion is met by
almost any neighbour at these depths; the per-candidate depth test is the one Stage B uses).

### Raw products for every star (Part 1c) [M]

`scripts/p8_download.py 4` (`audit_p5.download` with `sector_min=27`; sectors 1-26 are never
searched under prompt 8 and are not fetched): the 300-star sample first (299 stars, 1.45 GB, 46 min,
4.85 MB per star), then the rest. Totals at the end of this session are in section 3. Also in the
store now: the 40 adversarial EBs and blends (`scripts/p8_adversarial_download.py`, every sector)
and TOI-270 (TIC 259377017, every sector) for the Part 4 exercise.

### The native-cadence search (Part 1d) [M]

* `SurveyConfig` fields `source`, `sector_min`, `preprocess`, `audit_window_days`,
  `rotation_proxy`, `event_completeness_noise`; they enter the ingest key only when set, so every
  `survey_v1` cache file keeps its key (`50c453a40c`).
* Presets `survey_p8` (audit store, sectors >= 56, prompt-6 preprocessing, native 200 s,
  `bin_minutes=None`, 0.5-30 d, durations 0.02-0.20 d, chunked plan unchanged, time budget 900 s,
  `event_completeness_noise="mean"`) and `survey_p8_600s` (sectors >= 27, everything binned to
  600 s, otherwise the same).
* `src/tesshunter/survey_p8.py`: products from the audit store (one per sector, SPOC > TESS-SPOC >
  QLP), the cadence rule (bin finer, drop coarser, ratio 1.5), injection into `flux` AND `sap_flux`
  per product with each product's own exposure, `audit_prep.clean_and_detrend` + a 10-MAD deep clip
  as the search series, the rotation proxy (Lomb-Scargle 0.1-30 d on the normalised corrected
  flux), the stitched-cache write. `survey.run_job` dispatches on `cfg.source`; the search runs with
  its own flatten off (`do_flatten=False`, `two_pass_flatten=False`) and `confirm_on_stitch` too.
* `preprocessing.bin_lightcurve(bin_minutes=None)` is a no-op.
* `scripts/p8_smoke_v1.py`: the `survey_v1` path on TIC 100196477 against its stored prompt-4
  record: same ingest key, 4 candidates, **0 differences at relative 1e-9** [M], run after every
  code change of this session.
* `scripts/make_injection_spec.py --period-bins lo,hi,n --rp-earth-min/--rp-earth-max`.

### The rule-set options for Part 3 (`tesshunter.audit_rules.RuleSet`) [M]

New fields with p7.0-equivalent defaults, so `p6.2` and `p7.0` records are untouched
(`tests/test_audit_fixtures.py` 23 passed): `secondary_gate` in {bound, quiet_bound, quiet_zero,
quiet_bound_hold} with `secondary_quiet_max_dips`; `depth_consistency_errors` in {white, inflated};
`depth_consistency_p_min`; `beta_max`; `exact_t14_record` (prompt-7 finding 7: the Stage B record
stores `t14_hours` and `window_days` unrounded). `audit_rules.P8_RULES` is **None** until Part 3
decides it; `version` returns `p8.0` only for a set equal to `P8_RULES`, `p8.0-partial` for any
other set with a prompt-8 field changed. `secondary.apply_gate` evaluates every variant from one
scan and every scan records `gate_by_mode`; `event_vet.kept_event_stats(gate_errors=)`,
`sector_beta(beta_max=)`, `stagea_criteria(p_min=)`, `star_vet.phase_independent_test(exact=)`.
The drivers read them from the rule set in force.

### Drivers (all new, all in `scripts/`)

| script | what |
|---|---|
| `build_p8_population.py` | Part 1a |
| `p8_neighbours.py` | Part 1b |
| `p8_download.py`, `p8_adversarial_download.py` | Part 1c and the adversarial store |
| `p8_run_1e.cmd <concurrency>` | injections -> false alarms -> 600-s subset, checkpointed |
| `p8_completeness.py funnel / analyze / report` | Part 1e: the injection funnel (Stage A + secondary per recovered injection under its own root, products re-injected in memory), the tables, `docs/COMPLETENESS_P8.md` |
| `p8_600s_decision.py` | the paired 200 s / 600 s comparison and its pre-registered rule |
| `p8_expected_yield.py` | Part 1f: the expectation from the measured curve and the stop rule |
| `p8_funnel.py --root R --rules V collect / stageA / secondary / stageB / stageC / stageD / funnel / census / verdict` | Part 2 steps 1-4 over any candidate table (`--inject` installs an injection model for the Part 4 exercise) |
| `p8_decisions.py run --sets inj,p7,adv / tables` | Part 3 instrument and the pre-registered decisions |
| `p8_run_search.cmd <concurrency> <config>` | Part 2 search (prefetch, search, retry pass) |
| `p8_per_target_log.py` | the per-star log and run summary of the search |
| `write_population_p8_memo.py` | `docs/POPULATION_P8.md` |
| `p8_smoke_v1.py` | the prompt-4 reproduction check |

`audit_p5.py` and `revet_p6.py` gained `set_population(...)` (candidate table, accepted-candidate
table, packet directory, output root) with the prompt-4 defaults unchanged, root-aware output names
(`funnel_<root>.json`, `census_<root>.json`), `download(sector_min=)`, bulk-prefetched SIMBAD/VSX,
the proper-motion target match, and the `p8.0` name in `set_rules`.

### Part 4's never-run code, exercised [M]

`fit_step`, `write_ctoi_fields` and `revet_p6.py verdict` ran to completion on the prompt-3
demonstration target TOI-270 c (root `data/survey/p8/demo_toi270`, rules p7.0): Stage A PASS (28
kept events, SNR 86.9, depth 0.78 x the packet depth, p_const 0.67), secondary gate PASS (two 5.5-5.8
sigma dips at phases 0.44 and 0.70, within the bound), Stage B PASS with three flags
(astrometric_excess_noise_sig 23.4, one neighbour within 3 px, VSX EP+BY), Stage C PASS (blind TLS
5.66049 d at SDE 215), Stage D provisional KILL on the hard stop (a known TOI, as it should). The
all-transit fit: 34 transits, Rp/R* 0.0569 +/- 0.0007 (2.32 R_earth), a/R* 22.7, b 0.54, T14 1.73 h,
density prior adopted, beta 1.99, odd/even 0.12 sigma. The verdict stamp wrote
`docs/packets/audit_demo_toi270/tic259377017_P5.6602/ctoi_fields.json` (a DEMO of the writer on a
known planet, labelled as such in its note; not a candidate). `tests/test_audit_fit_ctoi.py` runs the
same chain on a synthetic star (6 s). Two path defects in that code were fixed on the way
(`relative_to(REPO)` in `prepare_step` and `stamp_verdict`; the packet directory of
`write_ctoi_fields` when the root is outside the repo). **Still to do:** the same exercise on one
recovered P8 injection (section 6, step 9).

### Tests

`tests/test_survey_p8.py` (34) and `tests/test_audit_fit_ctoi.py` (1) are new. The suite at the
end of this session: section 3.

## 2. What was refuted, and the defects measurement found [M]

1. **The alias resolver's event-completeness test used one PER-CADENCE noise unit as the dip
   threshold.** At 200 s the per-cadence scatter (4.5 ppt on TIC 5655186, Tmag 13.5) exceeds every
   transit this survey looks for, so a real 2.4-ppt dip with 15 cadences per event counted as "no
   dip" in most events, the composite score collapsed at the true period, and a 15-sigma 1.047-d
   injection (recovered by the BLS itself at SNR 10.4, SDE 35) was resolved to 4P and killed at gate
   3 (event completeness 0.25). Fixed: `bls_search.EVENT_COMPLETENESS_NOISE = "mean"` (one sigma
   of the in-transit MEAN), set from `SurveyConfig.event_completeness_noise`, on the prompt-8 presets
   only; `survey_v1` keeps "cadence" and still reproduces prompt 4 to 0 differences.
2. **The secondary scan read the primary transit's own shoulders as secondaries.** A coarse dip
   just outside the 0.02 merge distance is refined INTO the transit (phase 0.01 on a 1-d period is
   14 min from mid-transit) and only the deepest dip inside the 0.03 primary tolerance was taken as
   the primary, so on high-SNR injected planets the p7.0 gate saw a "100-sigma secondary" at phase
   0.01 and FAILED every one of the first four (SNR 100-190, 250-920 kept events). Fixed:
   `secondary.split_primary_shoulders` attributes every dip within max(0.03, 1.5 box widths in
   phase) of the primary to the primary (recorded as `primary_shoulder_dips`, never gated on, not
   counted toward the variability flag). Re-judging the stored scans: the p7.0 gate's kills on the
   405 go from 156 to 152 and on the adversarial set from 33 to 26 (7 blend kills were shoulders;
   17 of 18 EBs still killed). The prompt-7 option records in `data/survey/p7/options/` were made
   with the old split and are re-split when read by `p8_decisions.py`; they are not rewritten.
3. **The vendored tess-point grows its output with `np.append` inside its star loop**, quadratic in
   the number of output rows: on 117k stars it never finishes. `build_p8_population.py` calls it in
   2,000-star chunks (identical result, 25 min).
4. The `--tics`-filtered phase-1 injection orchestrator was killed on purpose and the full spec
   resumed; `--resume` reaped 14 orphaned workers and skipped the 74 finished jobs, as designed in
   prompt 2.
5. The population-level Gaia target match by nearest-within-5-arcsec fails for 113 of 2,000 (high
   proper motion); the proper-motion-propagated match finds all 113.
6. Refuted assumption from the plan: per-star SIMBAD queries (32 s each) would have taken 18 h;
   bulk queries took 13 min for 2,000 stars.

## 3. The runs of Part 1e, finished [M]

All three runs of `scripts/p8_run_1e.cmd` completed with every job `ok` (the sequence was
restarted once with `--resume` to raise the concurrency from 18 to 24; 913 finished jobs were kept
and 16 orphaned workers reaped). Results are under `data/survey/runs/` (git-ignored) with a
`summary.csv` each.

| run | config | jobs | status | wall per job median / p90 / max (s) | CPU hours | detection-budget stops |
|---|---|---:|---|---|---:|---:|
| `inj_p8` (2,100 injections, 300 stars) | `survey_p8` | 2,100 | 2,100 ok | 171 / 450 / 655 | 138.1 | 773 (37%) |
| `fa_p8` (the same 300 stars, no injection) | `survey_p8` | 300 | 300 ok | 150 / 436 / 518 | 18.6 | 105 |
| `inj_p8_600s` (100-star subset, 700 injections) | `survey_p8_600s` | 700 | 700 ok | 99 / 220 / 318 | 23.0 | 26 |

**Search-only recovery (prompt-2 rule, no gates yet)**: 1,163 recovered (55.4%), 82 alias
(3.9%), 855 missed (40.7%) of 2,100 [prompt 2 on the G/K sample: 44% / 6% / 51%]. By period bin
(0.5-1.39 / 1.39-3.87 / 3.87-10.8 / 10.8-30 d): 320/525 (61%), 303/525 (58%), 279/525 (53%),
261/525 (50%). By radius (R_earth 1-1.41 / 1.41-2 / 2-2.83 / 2.83-4): 34/513 (7%), 202/513 (39%),
445/545 (82%), 482/529 (91%). By Tmag (12.5-13 / 13-13.5 / 13.5-14): 401/679 (59%), 453/819 (55%),
309/602 (51%). The SNR axis (matched-filter SNR on the un-injected prepared series), SNR50 / SNR90
and the through-the-gates levels are NOT yet computed: they need the injection funnel (section 6,
steps 1-3). The 37% budget-stop rate is real cost inside the completeness: on 17-18-sector stars the
900-s detection budget ends the search after one or two passes.

**The pre-gate on the recovered injections** [M]: 1,118 of 1,163 pass at stitch SNR >= 7.1
(96.1%); 1,075 (92.4%) at >= 9.0; 978 (84.1%) at >= 12.0.

**False alarms** (`data/survey/p8/fa_funnel/candidates.csv`, from `p8_funnel.py collect`): 2,097
accepted candidates on 300 stars (6.99 per star; prompt 2: 7.9), of which 1,813 at 10.8-30 d (the
long-period stitch search, as in prompt 2), 240 at 3.9-10.8 d, 22 + 22 below 3.9 d. Past the pre-gate:
586 (1.95 per star) on 211 stars, 536 of them at 10.8-30 d; at stitch SNR >= 9.0 the pre-gate would
pass 357 (1.19 per star), at >= 12.0 208 (0.69 per star). Stage A and the secondary scan on these
586 have NOT been run (section 6, step 2). For the 2,000-star population this pre-gate implies
about 3,900 Stage A candidates (section 6, step 10, wall clock).

**The 600-second decision** (`data/survey/p8/decision_600s.json`, rule applied as pre-registered):
on the same 700 injections, both recovered 276, only at 200 s (a) 127, only at 600 s (b) 26,
neither 271; recovered 403 at 200 s against 302 at 600 s; b - a = -101 against the threshold
+24.7. **The 600-second sectors do not enter the search; the search config is `survey_p8`.** The
loss at 600 s is largest at long periods (10.8-30 d: 96 against 49) and smallest at 1.39-3.87 d
(106 against 91); the 600-s jobs were 40% cheaper (median 99 s against 167 s on the subset).

**The raw product store** [M]: 2,000 of 2,000 targets, 58,267 products (sectors >= 27), 0 failed
products, 10.2 GB for the 1,989 stars downloaded this session (5.1 MB per star), 265 + 46 min at
4 workers. A network outage at 21:58 local (DNS failure for mast.stsci.edu) failed 1,005 stars in
minutes and left two truncated FITS files in `data/cache/audit_lightkurve`; the rerun skipped the
994 stars already stored, and the two stars whose one product could not be read were re-fetched
with `force=True` after deleting the truncated files. Free disk at the end: 164.8 GB.

**The suite at the end**: `pytest tests/ -q` **482 passed, 1 skipped**, 120 s; `git status` clean
after the final commit; 30,660 files in `data/cache/lightkurve` (unchanged: prompt 8 never used
that cache); `scripts/p8_smoke_v1.py` 0 differences.

## 4. Part 3 instrument, the half that is done [M]

`scripts/p8_decisions.py run --sets p7,adv --slices 4` (445 candidates, 10 min): every prompt-6
candidate under its prompt-6 ephemeris and the 18 EBs + 22 blends under their catalogued
ephemerides, unmasked and masked detrends, betas capped at 5 (caps 3 and 2 by re-clipping), every
depth-consistency variant and every secondary-gate variant. Records
`data/survey/p8/decisions/{p7,adv}/`. The injection set (`--sets inj`) needs the injection funnel
first (section 6, step 1). `tables` currently reads:

Decision 1 (p7.0 `bound` kills 26 of the 40 adversarial stars: 17/18 EBs, 9/22 blends; 152 of
the 405): the quiet variants retain 4 to 9 of the 26 kills (EBs killed: 0/18 under quiet_bound,
quiet_zero N=2, N=3 and quiet_bound_hold; 3/18 under quiet_zero N=5) because the phase scan of a
real eclipsing binary is never quiet (ellipsoidal and reflection variation put 5-sigma box dips at
many phases; median dips on the EBs well above 5). Under the pre-registered rule (retain >= 90% of
the p7.0 adversarial kills) **only `bound` is eligible**, whatever the injection completeness says.
The 405 under each variant: FAIL 152 / 45 / 45 / 63 / 80 / 45, HOLD 0 / 0 / 0 / 0 / 0 / 86.

Decisions 2 and 3 (reference kill set 58 = the 18 prompt-6 depth-consistency-only failures + the
40 adversarial; p7.0 masked/cap5/1e-3 fails 40 of them on depth consistency, p6.2 unmasked/white
fails 52): retained p7.0 kills by variant, unmasked: white 1e-3 95%, 1e-4 93%, 1e-5 93%, cap2 82%,
cap3 78%, cap5 75%; masked: white 100% / 100% / 97%, cap2 100%, cap3 100%, cap5 100%. Eligible
(>= 90%): the three unmasked-white variants and all six masked variants; the injection completeness
(all six Stage A criteria) decides among them. On the 405, "all six pass" runs from 4 (masked,
white, 1e-3) to 17 (unmasked, cap5); adversarial EBs failing depth consistency 11-18 of 18.

## 5. Pre-registered rules (unchanged, verbatim from the earlier `HANDOFF_P8.md` section 0 and
`scripts/p8_decisions.py`, commit b3ba6a2, all written before the measurements they judge)

* The 600-second decision: with a = injections recovered only at 200 s and b = only at 600 s on
  the 700-injection subset, the 600-s sectors enter the search only if b - a > 2 sqrt(a + b).
* The stop rule: if the mid-prior expected number of new signals through the funnel is below 3.0,
  the search does not run; the high-prior number is reported next to it, and if it is below 1.0
  the handoff says so in its first line.
* The pre-gate [A]: epoch-consistent, stitch SNR >= 7.1, >= 3 transits; its cost is measured on
  the recovered injections (recorded, not applied, in the injection funnel).
* Part 3, X = 90 percent: Decision 1 = highest injection completeness (Stage A passers whose gate
  is not FAIL) among variants retaining >= X of the p7.0 gate kills on the adversarial EBs and
  blends; ties to more kills, then p7.0. Decisions 2+3 together = highest all-six Stage A
  completeness on the recovered injections among (mask x errors x threshold) combinations retaining
  >= X of the p7.0 depth-consistency kills on the reference set; ties to more kills, then p7.0.
  The 405 are reported under every variant, never used in a rule.

---------------------------------------------------------------------

## 6. RESUME HERE: the rest of prompt 8, step by step

Every command below is run from the repo root with the venv Python
(`C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe`), `LIGHTKURVE_CACHE` and
`PYTHONIOENCODING=utf-8` set. Wall-clock estimates are [M] from this session's rates on this
machine (24 cores) unless marked [A].

0. First action: `git status` (expect clean apart from anything listed in section 3), count
   `data/cache/lightkurve` files, `pytest tests/ -q` (expect the count in section 3), check free
   disk. Do not trust this file's claim that the tree is healthy; measure it.

1. **The injection funnel** (Part 1e, ~1 h at 16 slices [A: 60-170 s per candidate measured,
   ~1,200 recovered injections expected):
   `python scripts/p8_completeness.py funnel --slices 16 --rules p7.0`
   Idempotent (settled records short-circuit); slice logs in `data/survey/p8/logs/inj_funnel_slice*.log`.
   Roots `data/survey/p8/inj_funnel/<job_id>/` (stageA, secondary, prep, tls, events).

2. **The false-alarm funnel** (same 300 stars, no injection; `collect` is DONE, 586 pre-gate
   passers on 211 stars; Stage A ~586 x 60-170 s / 16 slices = ~1 h [A]):
   `python scripts/p8_funnel.py --root data/survey/p8/fa_funnel --rules p7.0 stageA --slices 16`
   `python scripts/p8_funnel.py --root data/survey/p8/fa_funnel --rules p7.0 secondary --slices 16`
   (`collect` was run with `--run data/survey/runs/fa_p8 --targets data/survey/completeness_sample_p8.csv`;
   rerun it only if `candidates.csv` under the root is missing.)

3. **Completeness tables and the report**: `python scripts/p8_completeness.py analyze --rules p7.0`
   -> `data/survey/p8/completeness_p8.json`, `injection_outcomes_p8.csv`, `docs/COMPLETENESS_P8.md`
   (the expected-SNR cache `expected_snr_p8.json` is written on the first run; delete it if the
   prepared cache changes). Check the five levels and SNR50/SNR90, the by-period / by-radius /
   by-Tmag / by-rotation tables, the Stage A criteria failing on recovered injections, the
   secondary gate by mode, and the depth-consistency p-value distribution (uniform if the errors are
   right; the fraction below 1e-3 is the white gate's false-kill rate).

4. **The 600-second decision**: DONE (section 3): the search config is `survey_p8`. Quote
   `data/survey/p8/decision_600s.json` in `HANDOFF_P8.md`.

5. **The expectation and the stop rule** (Part 1f): `python scripts/p8_expected_yield.py`
   -> `data/survey/p8/expected_yield_p8.json` (needs the prepared cache for every target: it
   builds it from the store on first use, ~2,000 x 3 s [A], no MAST). Then
   `python scripts/write_population_p8_memo.py` to put sections 6 and 7 into `docs/POPULATION_P8.md`.
   **If the mid-prior expectation through the funnel is below 3.0: stop.** Write `HANDOFF_P8.md`
   (population, completeness map, false-alarm budget, expectation; first line says it stopped, and
   if the high-prior number is below 1.0 say that in the first line too), run steps 10-12 for the
   parts that still apply (p8.0 can be decided from the injections alone; the fit exercise on an
   injection; the suite), commit, and report that the search is not worth running on this population.

6. **The search** (Part 2, only if the expectation is 3.0 or more; ~6 h at 20 workers [A: the
   injection jobs ran at a median 65 s / p90 430 s on the same stars]): `scripts\p8_run_search.cmd 20 survey_p8`
   (or `survey_p8_600s` per step 4). It prefetches the prepared cache at 8 workers, searches with
   `--resume`, then makes a retry pass. Then `python scripts/p8_per_target_log.py` ->
   `data/survey/p8/per_target_log.csv`, `run_summary_p8.json` (timing, products, sectors, cadence
   notes and fallbacks, budget stops, errors). Any star that errors twice is listed in the handoff.
   **Do not look at the candidate list until step 8 has committed p8.0.**

7. **Part 3, the injection half and the decision**: `python scripts/p8_decisions.py run --sets inj --slices 16`
   (needs step 1; ~10 min), then `python scripts/p8_decisions.py tables` -> `data/survey/p8/decisions_p8.json`
   and the `docs/RULES.md` section-8 text on stdout. Apply the two rules exactly as pre-registered.

8. **Ship p8.0**: in `src/tesshunter/audit_rules.py` set
   `P8_RULES = RuleSet(secondary_scan=True, inflated_depth_consistency=True, long_period_window_test=True,
   transit_masked_detrend=<True if the decision-2/3 mask is "masked" else False>,
   secondary_gate=<decision 1>, secondary_quiet_max_dips=<its N, 2 if bound>,
   depth_consistency_errors=<"white" or "inflated">, depth_consistency_p_min=<threshold>,
   beta_max=<2, 3 or 5>, exact_t14_record=True)` (keep `inflated_depth_consistency=True` even when
   the gate reads white errors, so both p-values stay on every record). Add tests in the pattern of
   `tests/test_event_vet.py` / `tests/test_secondary.py` for each p8.0 threshold fired and
   just-not-fired (the variant tests in `tests/test_survey_p8.py` cover the mechanisms; add one per
   chosen threshold), a `version == "p8.0"` test, and the `docs/RULES.md` section 8 (paste the
   `tables` output) plus a `p8.0` row in its section 0 table. Run
   `python scripts/p7_reproduce.py all --slices 16` and quote its 0/0/0.0 line (nothing here touches
   the p6.2 path, but it must be run). Commit ("p8.0").

9. **The Part 4 exercise on one recovered injection** (before any real candidate reaches Stage D):
   pick one recovered injection root `data/survey/p8/inj_funnel/<job_id>/` whose Stage A passed,
   write `<root>/inject.json` with its `inj_*` fields (they are the columns of its `survivors.csv`),
   then `python scripts/p8_funnel.py --root <root> --rules p8.0 --inject <root>/inject.json stageB --slices 1`,
   `... stageC --slices 1 --threads 16`, `... stageD --no-refresh`, and
   `... verdict --tic <tic> --period <period> --verdict SUBMIT --reason "EXERCISE on an injection" --note "EXERCISE: injected signal, not a candidate"`.
   The TOI-270 c half is done (section 1). Report the fit (density prior, grazing rail) for both.

10. **The real funnel under p8.0** (Part 2 steps 1-4):
    `python scripts/p8_funnel.py --rules p8.0 collect` (reads `data/survey/runs/survey_p8`, applies the
    pre-gate, writes `data/survey/p8/candidates.csv` and `survivors.csv`; report the counts),
    then `stageA --slices 16` (~1 h per 1,500 candidates [A]), `secondary --slices 16` (Stage A
    passers + a seeded 10% of the failures), `stageB --slices 8`, `stageC --slices 16 --threads 1`
    (blind TLS 0.5-110 d; the prompt-5 masks and SDE >= 9 are in `audit_p5.tls_step`), `stageD`
    (re-downloads the six catalogs; the all-transit fit; Gaia/SIMBAD/VSX from the prompt-8 records;
    `ctoi_fields.json` on SUBMIT via `verdict`), `funnel` -> `data/survey/p8/funnel_p8.json`,
    `census` -> `census_p8.json` (the eight artefact classes; compare with prompt 6's census in
    `docs/REVET.md`). TRICERATOPS and the TESScut centroid for Stage D survivors: use
    `scripts/survivor_packets.py` patterns (`--expensive`, `--tesscut-only`, 4 workers, binned fold,
    `fpp_uniform` flagged) — they read the prompt-4 survivor table and will need the same
    `set_population`-style re-pointing; do it only for the Stage C survivors (minutes each).
    Ranking: `ranking.score_v2` with the Gaia term from `data/survey/p8/neighbours/` (all 2,000 have
    a record; state the count); no verdict depends on rank.

11. **`docs/AUDIT_P8.md`**: per Stage C survivor SUBMIT / HOLD (what would change it) / KILL (why),
    the ordered submit list with the two-sentence ExoFOP note each, the artefact census against
    prompt 6's, the expectations carried in (flares, rotation, QLP noise at Tmag 13-14, PDC-made
    dips in cameras 3-4), and uncatalogued EBs the funnel killed (an EB report in the pattern of
    `docs/eb_reports/` if clean). A clean null is a legitimate outcome and is reported plainly.

12. **Close**: `pytest tests/ -q`, `HANDOFF_P8.md` (what shipped, measured with sample sizes,
    refuted, still open; evidence tags; assumptions in their own section; the funnel table
    candidates / pre-gate / A / secondary / B / C / D), `docs/POPULATION_P8.md` regenerated, commit on
    `improve/recovery` naming prompt 8. Do not push.

## 7. Gotchas learned this session (binding, in addition to the shared preamble)

1. The Bash tool truncates near 8 kB: a long heredoc dies with "unexpected EOF"; write patch
   scripts to files and run them. A Python script fed on stdin cannot spawn a
   `ProcessPoolExecutor` on Windows; write it to a file.
2. Per-star SIMBAD region queries cost 32 s each; use `Simbad.query_region` with a SkyCoord array
   (100 per query, 40 s) and Vizier `query_region` with an array for VSX (`_q` is the input index).
3. The vendored tess-point is quadratic in the output size: call it in chunks of ~2,000 stars.
4. `run_survey.py --resume` treats `no_data` as final: never start a survey run before the audit
   store holds every star it needs, or filter with `--tics`.
5. At native cadence the heavy stars (17-18 sectors, 150k cadences) take 7 min per job and hit the
   detection budget; the 2,100-injection run took 138 CPU-hours (7.5 h of wall clock at 18 then 24
   workers), so a 2,000-star search is ~130 CPU-hours, ~6 h at 24 workers. Throughput is bounded by
   the 7-minute jobs (24 workers give at most ~3.4 such jobs a minute), not by the mean.
8. A MAST/DNS outage fails downloads in seconds and can leave truncated FITS files in the audit
   lightkurve cache (a product that fails to read: delete its `mastDownload/HLSP/<product>` directory
   and re-download the star with `force=True`); `audit_p5.download` records failed products in
   `index.json` (`n_failed`), so a store is complete only when every index has `n_failed` 0.
6. A settled stage record short-circuits on `rules_version`; after a rule or scan change delete the
   affected records (this session deleted the secondary records made before the shoulder fix) or run
   with `--force`.
7. `event_completeness` and any other cadence-count statistic must be checked when the cadence
   changes by 9x: two of the three defects of section 2 were of that kind.

## 8. Files (this session)

* Code: `src/tesshunter/{survey_p8,survey,preprocessing,bls_search,audit_rules,event_vet,secondary,star_vet}.py`;
  `scripts/{build_p8_population,p8_neighbours,p8_download,p8_adversarial_download,p8_funnel,p8_completeness,
  p8_decisions,p8_expected_yield,p8_600s_decision,p8_per_target_log,p8_smoke_v1,write_population_p8_memo,
  make_injection_spec,audit_p5,revet_p6}.py`, `scripts/{p8_run_1e,p8_run_search}.cmd`;
  `tests/{test_survey_p8,test_audit_fit_ctoi}.py`.
* Data, committed: `data/survey/targets_p8.csv` (+ `.meta.json`), `population_p8.json`,
  `catalog_versions_p8.json`, `completeness_sample_p8.csv`, `injections_p8.csv`,
  `injections_p8_600s_subset.csv`, `data/survey/p8/{neighbours_p8.json,decisions_p8.json,decision_600s.json,
  download_p8.json,adversarial_download.json}`, `docs/POPULATION_P8.md`,
  `docs/packets/audit_demo_toi270/`.
* Data, git-ignored (on disk, needed): `data/survey/audit_lc/` (the store), `data/survey/runs/{inj_p8,fa_p8,inj_p8_600s}/`,
  `data/survey/p8/{neighbours,neighbours_bulk,decisions,inj_funnel,demo_toi270,logs}/`,
  `data/survey/cache/{p8,target_lists,twomin_lists}/`, `data/cache/stitched/tic*_3d160359ad.npz` (the
  `survey_p8` prepared cache) and `tic*_1c317946e0.npz` (`survey_p8_600s`).
