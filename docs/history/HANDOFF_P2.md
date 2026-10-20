# HANDOFF P2: survey-scale search engine with measured completeness

Date: 2026-09-01 to 2026-09-02. Branch `improve/recovery`. Environment as in
`CTOI_PROMPTS.md` (double-nested repo path, `tesshunter_venv` Python 3.13,
lightkurve 2.6.0, numpy 2.5.1).

Session start state, measured [M]: `git status` clean; 121 files in
`data/cache/lightkurve` (234 MB); `pytest tests/ -q` 222 passed, 1 skipped,
233 s. The tree was healthy.

Evidence tags: [M] measured in this session, [A] adopted assumption,
[R] refuted or unavailable. The pipeline finds candidates; nothing in this
document is a detection.

## Summary

| item | before | after |
|---|---|---|
| dev benchmark (24 planets), recovered / alias / missed / FP | 17 / 2 / 5 / 12 | 17 / 2 / 5 / 12 (identical) |
| dev mean depth error | 13.0197% | 13.0197% (identical to every printed digit) |
| holdout (6 planets), recovered / alias / missed / FP | 4 / 0 / 2 / 7 | 4 / 0 / 2 / 8 (see attribution below) |
| dev worst target wall clock | 1181 s | 545 s |
| dev total wall clock | 1557 s at concurrency 5 | 545 s at concurrency 10 |
| survey search, one 5-unit star over a 2826-day baseline | 338 s (before the kernel) | 35 s |
| test suite | 222 passed, 1 skipped, 233 s | 265 passed, 1 skipped, 79 s |

Part C headline [M], 2,100 batman injections on 300 random population stars,
searched with the survey preset, no job errored or timed out: 923 recovered
(44%), 116 at a harmonic (6%), 1,061 missed; recovery crosses 50% at a
matched-filter SNR of 26.5 (16-84%: 25.5-27.6) and 90% at 97.6 (89-107).
Recovery by expected SNR: 0% below 7.1, 6% at 7.1-9, 14% at 9-12, 37% at
12-20, 64% at 20-50, 89% at 50 and above. False alarms on the same 300 stars
without injection: 7.9 accepted candidates per star raw; 2.97 per star at
SNR >= 9 with a non-FP verdict; 1.07 per star when also re-measured on the
whole stitch at SNR >= 9 with a consistent epoch; 0.38 per star when three
or more transits are also required. Search wall clock on the 300 stars
(cached curves): median 60 s, 90th percentile 196 s, max 291 s.

The single most consequential measurement: at the SNR 7.1 to 12 the P1 yield
model treated as detectable with pipeline efficiencies of 0.4 to 0.8, this
search recovers 6 to 14%. Those efficiencies are refuted for near-threshold
signals; the population's expected new-signal count must be recomputed
with the measured curve before prompt 4 promises anything.

## Part A: FFI ingestion and stitching

### What shipped

`src/tesshunter/ffi.py` (new), used only by the survey path; `search_target`
and the benchmark harness never touch it.

* **Flux column per author.** QLP: `sap_flux` or the spline-detrended column
  (`kspsap_flux` in sectors 1-55, `det_flux` from sector 56), selected by
  config and recorded per product; the matching QLP error column is used.
  TESS-SPOC and SPOC: PDCSAP. Any other author (TASOC, CDIPS, TGLC, eleanor,
  T16 and the rest that MAST returns for these stars) is dropped with a
  provenance note. No TGLC or QLP faint-star reader was added: every star of
  the chosen stratum (Tmag 10.5 to 13.5) has a QLP light curve and 91% of the
  target list also has TESS-SPOC [M, `targets_v1.csv`: 745 of 819 rows
  `qlp;tess-spoc`, 74 `qlp`].
* **Quality per author.** lightkurve applies the TESS default bitmask at read
  time for every author. QLP additionally marks low-precision cadences (bit
  13 in sectors 1-55, bit 31 from sector 56) which the default mask keeps;
  the survey removes them (config `qlp_low_precision_mask`). On the first
  star inspected, sector 1, that bit was set on 17.6% of the cadences [M].
* **Usable errors.** QLP products from sector 56 on carry an all-NaN
  `det_flux_err` column [M: TIC 44578128 sectors 95 and 102]. Missing or
  non-positive errors are filled with the robust point-to-point scatter at
  ingestion and the fill is recorded.
* **Edge trimming at real gaps** (config `edge_trim_minutes`, 120 in the
  preset): the first and last N minutes of each product and of each run
  bordering a gap longer than 0.5 d are removed (scattered-light ramps live
  at orbit starts and ends); short holes cut by the quality mask inside an
  orbit are not trimmed. Runs shorter than three times the trim between two
  real gaps are removed whole. Measured in the ingestion A/B below.
* **Common cadence.** Products finer than `target_cadence_minutes` (30) are
  binned to it before stitching; native 30-minute products are left as they
  are. The stitch refuses products whose cadences differ by more than a
  factor 1.5.
* **Dedupe, normalisation, stitching** reuse `download.dedupe_collection`
  (SPOC > TESS-SPOC > QLP per sector) and `download.stitch_collection`
  (per-product median normalisation). The stitched curve carries the
  per-product ingestion record in `meta["TESSHUNTER_INGEST"]`.
* **Stitched-curve cache** (`tesshunter.survey`): `data/cache/stitched/tic<id>_<key>.npz`
  plus a JSON sidecar with the full provenance. The key hashes the ingestion
  fields and an `INGEST_VERSION` constant, so an ingestion code change never
  serves an old curve. `--offline` rebuilds a star from the local FITS cache
  without a MAST query.

### A defect the survey path exposed [M]

The first end-to-end run on TIC 44578128 stitched two unbinned 200-second QLP
sectors next to three 30-minute-binned sectors. `preprocessing.bin_lightcurve`
had silently returned the unbinned curve because the QLP error column was NaN
(weakness 7 of `IMPROVEMENT_REPORT.md`), and the flatten, whose window and
segment split are counted in cadences of the global median cadence, then cut
the 30-minute sectors into 3,229 single-cadence segments and median-divided
each to exactly 1.0. The transit-free "candidates" that run produced sat in
the unbinned sectors. Fixed by the error fill, the binned-or-dropped rule and
the cadence check above; `tests/test_ffi.py` holds regression tests for all
three.

### Ingestion A/B on 40 prefetched stars [M]

The first 40 stars of the completeness sample, searched with the final
survey design (chunked search, stitch re-measurement not yet added) under four
ingestion variants: QLP raw aperture flux (`sap`) or QLP's own
spline-detrended flux (`kspsap` / `det`), each with and without a
120-minute trim at every segment edge. Same 40 stars searched without an
injection (false alarms) and with 2 injections each (80 jobs). "FA" counts
every accepted candidate over all sub-searches (up to 3 per sub-search);
"not-FP" means the automated verdict is not "likely false positive".

| variant | FA candidates | SNR >= 9 | SNR >= 9, not-FP | SNR >= 9, >= 3 transits | deeper than 10 ppt | median wall (s) | p90 wall (s) | injections recovered / 80 | alias |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sap, no trim | 347 | 206 | 162 | 66 | 72 | 54 | 176 | 29 | 6 |
| sap, trim 120 | 340 | 197 | 166 | 58 | 76 | 42 | 144 | 30 | 5 |
| kspsap, no trim | 350 | 160 | 150 | 55 | 35 | 49 | 179 | 30 | 6 |
| kspsap, trim 120 | 338 | 136 | 130 | 45 | 21 | 46 | 158 | 28 | 8 |

Reading: the detrended QLP flux halves the deep (> 10 ppt) artifacts and
removes about a fifth of the SNR >= 9 false alarms at equal injection
recovery (30 against 29 to 30 of 80), so the survey searches `kspsap` /
`det`. Recovery by injected depth is the same across variants except at the
deep end (12 to 15 of 16 to 18 above 4,000 ppm), where the 2-injection-
per-star subset cannot separate them. Before this A/B the candidate events
of the `sap` run were measured against segment edges: 67% of them sat
within 0.25 d of an edge against 7% of all cadences (n = 9 events on the
stars then cached), which is the edge-dip signature the trim targets. The
120-minute trim as first written removed the edges of EVERY segment,
including the short holes cut by the quality mask inside an orbit where no
scattered-light ramp exists, and discarded 4.3% of all cadences; it was
rewritten to trim only at product ends and either side of gaps longer than
0.5 d, and rerun on the same 40 stars (this run also carried the stitch
re-measurement of the section below):

| variant | FA candidates | SNR >= 9, not-FP | deeper than 10 ppt | cadences discarded | recovered / 80 | alias | stitch SNR >= 9, consistent epoch, not-FP | of which >= 3 transits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kspsap, no trim | 350 | 150 | 35 | 0% | 30 | 6 | (run predates the stitch re-measurement) | |
| kspsap, trim 120 at every segment | 338 | 130 | 21 | 4.3% | 28 | 8 | (same) | |
| kspsap, trim 120 at real gaps only | 337 | 133 | 26 | 1.2% | 26 | 9 | 69 (1.7 per star) | 20 (0.5 per star) |

Per-injection comparison of "no trim" against "trim at real gaps": 9 of 80
outcomes differ, in both directions (4 recovered to alias or missed, 2
missed to recovered or alias, 1 alias to recovered, 2 recovered to alias),
all at matched SNR 7 to 57 where the alias resolver's choice between P and a
harmonic is marginal; one 37-day, 3-transit injection lost a transit to the
trim. The recovery difference (26 against 30 of 80) is inside the binomial
scatter of the subset (sd about 4) and not one-directional in kind.
**Adopted: `kspsap` with the gap-aware 120-minute trim** (`survey_v1`
preset). The trade is stated, not hidden: about 11% fewer SNR >= 9 false
alarms and 26% fewer deep artifacts for 1.2% of the cadences and a
recovery difference the subset cannot resolve; the 2,100-injection run
below measures completeness under exactly this configuration.

## Part B: speed

### What was measured first

`cProfile` of `search_target` on WASP-18 with the benchmark parameters
(3 SPOC sectors spanning years, 49,766 cadences) [M]: 1,049 s under the
profiler, 96% of it inside the one-period-at-a-time BLS loop; 105 `run_bls`
calls evaluating 1.65 million trial periods, of which 994 s came from alias
refinement (up to 9 trials x 20 candidates x a 20,000-point local grid per
pass; the local windows want 55,000 points by the frequency criterion and
the broad grid wants 555,882, both capped at 20,000).

### Levers, in the order they were tried

1. **Vectorised transit-epoch helpers** (`_transit_times`,
   `_count_observed_transits`, `event_completeness`,
   `alternating_event_consistency`, `transit_window_overlap_fraction`): the
   O(n_transits x n_cadences) mask loops became one nearest-transit
   assignment per cadence; per-epoch means are still computed on exactly the
   same elements in the same order, so the outputs are bit-identical.
   Windows wider than half a period fall back to the loop form.
2. **Vectorised binning** (`preprocessing.bin_lightcurve`): `searchsorted`
   plus `bincount`. Bit-identical for bins holding fewer than eight cadences
   (numpy sums those sequentially); bins of eight or more differ only in
   float summation order (last bit or two). The benchmark bins 2-minute data
   in 10-minute bins (5 per bin); TRAPPIST-1's K2 1-minute data is the one
   benchmark case above eight per bin and shows the effect: its SNRs differ
   from the reference in the 14th significant digit, every period, epoch,
   duration and depth identical [M].
3. **Batching the BLS loop over periods in numpy** [R]: written, proved
   bit-identical, and measured 0.4 to 0.8 times the speed of the loop on the
   WASP-18-like curve (the cost is inline float arithmetic over the phase
   bins, not Python call overhead; the batched gathers added work). Removed.
4. **Compiled kernel.** `numba` 0.67 installs and jits under numpy 2.5.1
   [M]. `_numpy_bls` now runs the reference loop as a numba kernel written
   scalar by scalar (same `fmod` fold, same truncating bin index, weights
   accumulated in data order, one sequential cumulative sum over the doubled
   bins, strict first-maximum update duration by duration); the numpy loop
   is kept as `_numpy_bls_loop` and is the fallback when numba is absent or
   `TESSHUNTER_NO_NUMBA=1`. `tests/test_speed_equivalence.py` asserts
   bit-identity on random gapped multi-sector curves with phase-bin counts
   from the 64 floor to the 5,000 cap and duration grids that trip every
   skip branch. Micro-benchmark, 20,000 periods, 10 durations [M]:

   | light curve | cadences | kernel | numpy loop (extrapolated) | ratio |
   |---|---:|---:|---:|---:|
   | WASP-18-like, 3 sectors, 10-min bins, local window at 0.94 d | 11,066 | 2.5 s | 15 s | 6x |
   | same, broad 0.5-6 d | 11,109 | 2.7 s | 15 s | 6x |
   | CVZ-like, 40 sectors, 30-min bins, broad 1-100 d, dmin 0.04 d | 49,292 | 10.3 s | 38 s | 4x |

5. **Grid caps as parameters.** `run_bls(n_max=)`,
   `resolve_aliases_for_candidate(local_n_max=)`, and `search_target` /
   `search_light_curve(grid_cap=, local_grid_cap=)`. Defaults are None, which
   keeps the 20,000 cap on both, so the benchmark path is unchanged. The
   survey preset caps the alias-refinement windows at 1,500 points and
   examines 8 candidates per pass instead of 20.
6. **The search plan for multi-year stitches** (`survey.plan_searches`),
   forced by the first injection results [M]: on the first 40-star
   injection subset, deep short-period injections on multi-year stars were
   missed outright (7,183 ppm at 2.57 d with 177 transits in the data;
   6,148 ppm at 1.35 d with 603 transits; 4,128 ppm at 4.79 d with 165).
   The BLS frequency step must be about duration_min / (4 x baseline) for a
   transit to stay phase-coherent over the baseline, and that step is the
   same at every period, so the grid a period range needs is proportional to
   its width in frequency: [1, 10] d spans 0.9 per day and wants about
   240,000 points on a 2,700-day stitch, while [10, 100] d spans 0.09 per
   day and wants 24,000. A 20,000-point cap on the whole range smears every
   short-period peak on a long baseline. The survey therefore searches
   short periods on each contiguous chunk of sectors (gaps longer than 60 d
   split chunks; a chunk is searched from 1 d to half its own span at full
   resolution under a 40,000-point cap) and periods of 10 to 100 d on the
   whole stitch, then merges the candidate lists (same period within 1%
   keeps the higher SNR). Re-run on the three missed injections above: the
   2.57 d signal is found independently in all nine chunks of its star
   (merged SNR 49) [M]. The other two sit on a star with a 79-day, 55%-deep
   eclipse at SNR 586 and a second eclipse at 41.6 d (an eclipsing binary
   that no hard-stop catalog covers: the TESS EB catalog stops at sector 26
   and an FFI-only star has no SPOC TCE); the eclipses take the detection
   slots, and the 1.35 d injection, found at SNR 34 in the third pass, was
   vetoed by gate 7 because the survey's 0.04 d duration floor was below two
   30-minute cadences. The floor is now 0.045 d, which disarms gate 7 on
   30-minute data while still fitting one-hour transits, and the merge no
   longer caps the candidate list at 5 (it had dropped a genuine 4.79 d
   recovery at SNR 16 in favour of five eclipse harmonics).
7. **Time budget per sub-search**: the 600 s per-star budget is split in
   proportion to cadence count, with a 60 s floor per sub-search; the
   existing wall-clock guard in `_detect_planets` stops a sub-search before
   a pass that would not fit.
7b. **Stitch re-measurement** (`survey.confirm_on_stitch`). The chunked plan
   raised the raw candidate count to about 8.5 per star on the A/B stars,
   most of them chunk-local: up to 3 candidates per sub-search and up to
   ten sub-searches. A real periodic signal folds coherently across every
   chunk (the 2.57 d injection above was found in all nine chunks of its
   star), a chunk artifact does not. So every merged candidate is
   re-measured on the whole stitched curve with a local BLS in a +/-1%
   period window at full frequency resolution (cheap because the window is
   narrow: a few thousand points), and the stitch SNR, depth, transit count,
   epoch and an epoch-consistency flag (stitch epoch within one duration of
   the chunk epoch, modulo the period) are written on the candidate as
   `stitch_*` fields. Nothing is removed by P2; the false-alarm and
   completeness tables report both quantities at several thresholds so the
   cut can be chosen with its cost in view. On the 40 A/B stars under the
   adopted ingestion: 337 raw candidates, 69 with stitch SNR >= 9 and a
   consistent epoch and a verdict other than false positive (1.7 per star),
   20 of those with three or more transits (0.5 per star) [M]. Cost: one
   extra flatten of the stitch plus about 1 to 3 s per candidate.
8. **No target-pixel or centroid work during search**: `search_target` never
   called `centroid.py` or `contamination.py`; verified by reading the
   pipeline, nothing to remove. The survey calls neither.
9. **Cached stitched curves on disk** and a **checkpointed orchestrator with
   `--resume`** (Part A above and the orchestrator section below).

### Benchmark, frozen scorer, side by side [M]

Dev set (`results/improved_final` reference from `IMPROVEMENT_REPORT.md`
against `results/p2_speed`, same cache, same harness, concurrency 10):

| metric | reference | P2 |
|---|---|---|
| recovered | 17 | 17 |
| alias | 2 | 2 |
| missed | 5 | 5 |
| false positives | 12 | 12 |
| verdict mislabels | 0 | 0 |
| mean depth error | 0.13019711939872125 | 0.13019711939872125 |

Per-planet statuses and depth errors identical on all 24 planets
(`compare_any.py --a improved_final --b p2_speed`: 0 of 17 paired depths
changed). Planet tables (period, epoch, duration, SNR, depth) bit-identical
on 9 of 10 targets; TRAPPIST-1 as described under lever 2.

| target | wall before (s) | wall after (s) | ratio |
|---|---:|---:|---:|
| HD 108236 | 1181 | 545 | 2.2 |
| HD 63433 | 713 | 328 | 2.2 |
| L 98-59 | 412 | 215 | 1.9 |
| LHS 3844 | 784 | 357 | 2.2 |
| Pi Mensae | 183 | 100 | 1.8 |
| TOI-270 | 125 | 80 | 1.6 |
| TOI-700 | 110 | 68 | 1.6 |
| TRAPPIST-1 | 307 | 165 | 1.9 |
| WASP-126 | 155 | 92 | 1.7 |
| WASP-18 | 376 | 189 | 2.0 |

The benchmark keeps `top_n=20` and the 20,000-point local grids, so it sees
only the kernel and the vectorised helpers; the survey's grid caps are not
applied to it.

Holdout (`results/holdout_improved` against `results/holdout_p2_speed`,
concurrency 5):

| metric | reference | P2 |
|---|---|---|
| recovered | 4 | 4 |
| alias | 0 | 0 |
| missed | 2 | 2 |
| false positives | 7 | 8 |
| verdict mislabels | 1 | 1 |
| mean depth error | 10.86% | 10.83% |

| holdout target | wall before (s) | wall after (s) | ratio |
|---|---:|---:|---:|
| AU Mic | 1618 | 453 | 3.6 |
| GJ 357 | 1344 | 628 (one more detection pass than before) | 2.1 |
| HD 21749 | 152 | 88 | 1.7 |
| TOI-125 | 1722 | 450 | 3.8 |
| WASP-121 | 412 | 199 | 2.1 |

The extra false positive is GJ 357's third candidate (12.4946 d, SNR 6.2,
268 ppm). Same inputs in both runs (sectors 8, 35, 62; 45,448 cadences;
identical products). The reference run's own notes say it stopped before its
third detection pass because "another pass (~1092 s) would not fit the
2027 s detection budget"; the faster code finished that pass inside the
budget and accepted the candidate. To attribute this rather than argue it,
the reference commit `a401494` was checked out into a git worktree and its
own code was run on GJ 357 with the benchmark parameters and
`time_budget_s=None` [M]: 3,568 s wall (3,510 s in detection), and it
accepted exactly the same three candidates as the kernel run: 3.93060 d
(SNR 39.67, 1.070 ppt, epoch 1518.0005), 9.23812 d (15.77, 0.236 ppt,
1525.9027) and 12.49461 d (6.17, 0.268 ppt, 1529.5679), identical to every
printed digit. The reference run's 7 false positives were therefore 7 only
because its clock ran out; the pipeline's behaviour is unchanged and the
scorer counts the candidate it now has time to reach. Under the frozen
priority order (recovered above missed above FP) nothing moved in the first
two tiers on either set.

### Survey wall clock [M]

Download, done once per star (`run_survey.py --prefetch`, 8 workers against
MAST): all 300 sampled stars succeeded; MAST search plus download of every
SPOC / TESS-SPOC / QLP product, median 43 s, 90th percentile 102 s, maximum
152 s per star; 11,536 FITS files, 6.0 GB, in `data/cache/lightkurve`
afterwards. Median 14.5 units per star, median 17,275 stitched 30-minute
cadences, median baseline 2,193 days.

Search, 300 stars from cached stitched curves, 18 workers on the 24-core
box, survey preset (`fa_v1` run, `data/survey/p2_runs/fa_v1_summary.csv`):

| stars | median search (s) | 75th | 90th | max | under 120 s | under 300 s | budget stops |
|---|---:|---:|---:|---:|---:|---:|---:|
| all 300 | 60 | 152 | 196 | 291 | 191 | 300 | 1 |

| units per star | stars | median stitched cadences | median search (s) | 90th | max |
|---|---:|---:|---:|---:|---:|
| 1-8 | 112 | 6,069 | 27 | 41 | 54 |
| 9-16 | 44 | 11,694 | 43 | 65 | 120 |
| 17-30 | 25 | 23,315 | 97 | 142 | 185 |
| 31-50 | 119 | 43,955 | 166 | 214 | 291 |

Preprocess median 6 s (max 34), detection median 52 s (max 266), stitch
re-measurement median 0.9 s (90th percentile 3.4 s). The injection run (2,100
jobs, same stars, one injected signal each): median 43 s, 90th percentile
134 s, max 199 s, 0 budget stops. The acceptance target (median under 2
minutes on 100 real population stars, worst case under 5) is met on 300;
the continuous-viewing-zone quartile (31 to 50 units, 40% of the sample by
the ranking's construction) sits at a median of 166 s.

### Orchestrator and the kill test [M]

`scripts/run_survey.py` runs one `scripts/survey_worker.py` subprocess per
job, N at a time, each pinned to one BLAS/OpenMP thread. Every job writes its
own result JSON through a temp file and `os.replace`, and `progress.jsonl`
gets one appended line per finished attempt; the results directory is the
checkpoint, `--resume` rescans it, reruns whatever is missing or still
eligible for a retry (`--retries 1` by default), and terminates any worker a
dead orchestrator left behind (pid files under `jobs/`). Sleep is inhibited
for the life of the orchestrator process only.

Kill test, run twice on 6 cached stars at concurrency 2 (PowerShell starts
the orchestrator, sleeps 75 s, stops every descendant process and then the
orchestrator, checks for surviving workers, and resumes):

* First run (before pid files): 1 of 6 results on disk at the kill, but 3
  workers spawned between the process snapshot and the kill survived as
  orphans and kept computing; the resume reran the 5 unfinished jobs and
  the orphans' late results were overwritten by the resumed attempts through
  the atomic replace. No corrupt or duplicate result file, but wasted work
  and a race. Fixed: the orchestrator records each worker's pid and a resume
  terminates any pid that is still alive before rerunning its job.
* Second run (with pid files): 1 result before the kill, 0 worker processes
  left after the tree kill, resume reports "5 to run, 1 skipped", all 5
  complete, `progress.jsonl` holds exactly one line per job, `summary.csv`
  shows `attempts=1` for all 6. Walls 35 to 78 s per star while the machine
  was also running the A/B, the prefetch and a benchmark.

## Part C: completeness on the real population

Everything in this part is generated by `scripts/analyze_completeness.py`
from the two runs and is written out in full, with every table, in
`docs/COMPLETENESS.md` (numbers in `data/survey/completeness_v1.json`,
figure `docs/figures/completeness_v1.png`, per-injection outcomes in
`data/survey/p2_runs/injection_outcomes_v1.csv`, false-alarm candidates in
`data/survey/p2_runs/false_alarm_candidates_v1.csv`).

### Design [M for the counts, A for the model choices]

* Sample: 300 stars drawn at random (seed 20260902) from the 819-star
  `targets_v1.csv`; median 14.5 units, median Tmag 12.0, quartiles of units
  7 / 14.5 / 38 (the ranking favours the continuous viewing zones).
* Injections: 2,100 (7 per star), period log-uniform 1 to 40 d in four
  equally populated log bins, Rp/R* log-uniform 0.01 to 0.12 (depth 176 to
  9,047 ppm at the 10th/90th percentiles), impact parameter uniform 0 to 0.9,
  random phase, quadratic limb darkening by Teff, a/R* from the TIC mass and
  radius, circular orbits, batman with 30-minute exposure integration.
  Injected into the cached stitched curve BEFORE detrending so the flatten,
  the two-pass masking, the chunk split and the alias resolver act on the
  injected signal exactly as on a real one.
* Recovery rule, fixed before the run: an accepted candidate with period
  within 1% of the injected period and transit windows overlapping the
  injected ones; ratios 2, 3, 1/2, 1/3 are `alias` and never credited.
* Expected SNR: the matched-filter SNR of the injected model on the same
  star's own detrended, 30-minute-binned, un-injected curve (sigma =
  1.4826 x MAD per bin), so the real gaps, noise and detrending are in it.
  519 of the 2,100 injections have expected SNR below 5 by construction (the
  grid deliberately extends below threshold).
* False alarms: the same 300 stars searched without an injection.

### Injection outcomes [M]

| outcome | n | share |
|---|---:|---:|
| recovered | 923 | 44% |
| alias (2P, 3P, P/2, P/3) | 116 | 6% |
| missed | 1,061 | 51% |
| recovered with a verdict other than "likely false positive" | 918 | 44% |

| recovery crosses | any verdict (n = 2,099) | verdict not FP | injections with >= 3 transits in data (n = 2,075) |
|---|---|---|---|
| 50% at expected SNR | 26.5 (25.5-27.6) | 26.9 (25.8-28.0) | 26.3 (25.3-27.4) |
| 90% at expected SNR | 97.6 (89.0-107.1) | 100.3 (91.3-110.0) | 96.8 (88.5-105.5) |

(intervals: 16th-84th percentile of 1,000 bootstrap resamples.)

| expected SNR | 0-5 | 5-7.1 | 7.1-9 | 9-12 | 12-20 | 20-50 | >= 50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| injections | 519 | 131 | 96 | 120 | 207 | 368 | 658 |
| recovered | 0% | 0% | 6% | 14% | 37% | 64% | 89% |

| period (d) | 1-2.5 | 2.5-6.3 | 6.3-16 | 16-40 |
|---|---:|---:|---:|---:|
| recovered (525 each) | 42% | 44% | 47% | 42% |
| recovered at expected SNR >= 50 | 84% | 86% | 93% | 98% |

| Rp/R* | 0.01-0.02 | 0.02-0.04 | 0.04-0.07 | 0.07-0.12 |
|---|---:|---:|---:|---:|
| recovered | 1% (6/544) | 32% (198/624) | 69% (306/441) | 84% (413/491) |

Impact parameter makes little difference (45% / 45% / 41% for b in 0-0.3 /
0.3-0.6 / 0.6-0.9). Injections with only 2 transits in the data: 2 of 21
recovered; 3-5 transits: 33 of 107; 6-19: 152 of 381; 20 or more: 736 of
1,587. Requiring the stitch re-measurement of the recovered candidate at SNR >= 9
keeps 894 of the 923 (SNR50 moves from 26.5 to 28.5); at >= 12, 867 (30.5).
The full period x Rp/R* and period x SNR maps are in the memo.

What the curve says: the search is near-complete only above a matched-filter
SNR of about 50 and half-complete near 26. Two causes are visible in the
tables. Short periods pay for the chunked plan: each chunk sees a fraction
of the transits, so a signal at total SNR S is searched at S / sqrt(n_chunks)
per chunk below 10 d, which is why the 1-2.5 d row is the weakest at high
SNR (84% against 98% at 16-40 d) even though the 30-minute binning also
smears its one-hour transits. And the ranking competes with what the stars
already contain: the detection loop accepts at most three candidates per
sub-search, and 296 of the 300 stars produce candidates without any
injection (next section).

### False-alarm rate, same 300 stars, no injection [M]

2,377 accepted candidates on 296 stars (7.92 per star); 1,492 of them at
40-100 d, 474 at 16-40 d, 361 at 6.3-16 d, 50 below 6.3 d. One search hit
its time budget.

| SNR threshold | candidates | per star | verdict not FP | per star | expected in the 819-star population |
|---|---:|---:|---:|---:|---:|
| >= 7.1 | 1,393 | 4.64 | 1,328 | 4.43 | 3,625 |
| >= 9 | 946 | 3.15 | 890 | 2.97 | 2,430 |
| >= 12 | 611 | 2.04 | 562 | 1.87 | 1,534 |
| >= 20 | 275 | 0.92 | 245 | 0.82 | 669 |

| stitch SNR >= (epoch-consistent) | not-FP candidates | per star | expected in population | of which >= 3 transits | per star | expected in population |
|---|---:|---:|---:|---:|---:|---:|
| 7.1 | 464 | 1.55 | 1,267 | 170 | 0.57 | 464 |
| 9 | 321 | 1.07 | 876 | 114 | 0.38 | 311 |
| 12 | 220 | 0.73 | 601 | 81 | 0.27 | 221 |
| 20 | 99 | 0.33 | 270 | 41 | 0.14 | 112 |

Two-transit candidates: 1,256 of the 2,377 (567 at SNR >= 9, not FP);
three or more: 1,121 (323). The candidate list is a mix of systematics and
whatever real variability these stars have (eclipsing binaries that no hard
stop catalog covers, see "Still open"); no per-candidate classification was
attempted in P2. Read against the completeness table: a cut at stitch
SNR >= 9 plus three transits leaves 311 expected false alarms across the
population at a 3% cost in recovered injections, and every real signal it
keeps has, by construction, an expected SNR the curve says is recoverable
only 14% of the time at 9-12 and 37% at 12-20.

### Consequence for the P1 yield model [M against A]

P1 adopted pipeline efficiencies of 0.8 (class A, single-sector SNR >= 9),
0.7 (class B, stitched SNR >= 9) and 0.4 (class C, stitched 7.1-9) and
promised 5.0 expected new signals from `targets_v1.csv` at mid priors. The
measured recovery at expected SNR 7.1-9 is 6% and at 9-12 is 14%. The
matched-filter SNR here is not identical to P1's photon-model SNR (it is
measured on this pipeline's binned, detrended data and is if anything the
more optimistic of the two), so the comparison is not exact, but the
direction is not in doubt: the class C efficiency is refuted by a factor of
about 7 and class B's by a factor of 2 to 5 near threshold. P2 does not
re-run the yield model (the population is fixed by the P1 rule); prompt 4
should compute the expectation from the measured curve before ranking, and
prompt 3's vetting will see far more false alarms than real signals at the
thresholds the design counted on.

## What was refuted or changed by measurement

* Batching the numpy BLS over periods: bit-identical and slower (0.4 to
  0.8x). Dropped for a compiled kernel of the same arithmetic.
* The silent unbinned return of `bin_lightcurve` reached the survey through
  QLP's NaN error columns; the survey path no longer tolerates it.
* QLP raw aperture flux (`sap_flux`, lightkurve's default) as the search
  column: on 40 stars it produced 72 to 76 candidates deeper than 10 ppt
  against 21 to 35 for QLP's detrended column, at equal injection
  recovery. Dropped.
* One search of the whole multi-year stitch under a 20,000-point grid: deep
  short-period injections with hundreds of transits were missed outright.
  Replaced by the chunked plan (Part B, lever 6).
* A 0.04 d duration floor on 30-minute data: it armed gate 7 and vetoed a
  6,800 ppm injection found at SNR 34. The floor is 0.045 d.
* Trimming every segment edge: 4.3% of all cadences gone, most of it at
  quality-mask holes with no scattered-light ramp. Replaced by trimming at
  real gaps only (1.2%).
* Capping the merged candidate list at 5 per star: it dropped a genuine
  recovery at SNR 16 ranked below five eclipse harmonics. The list is not
  capped below 12.

## Assumptions the results rest on [A]

* Injected transits use quadratic limb darkening from a nine-point Teff
  table (`survey.LD_ANCHORS_TESS`, approximate TESS-band values in the range
  of Claret 2017) and a/R* from the TIC mass and radius (mass set equal to
  the radius in solar units where the TIC has none). Circular orbits.
* The expected SNR used for the completeness curve is the matched-filter SNR
  on this pipeline's own detrended, 30-minute-binned data; a different
  detrending gives a different number for the same injection.
* Completeness is measured inside the injected grid only (1 to 40 d,
  Rp/R* 0.01 to 0.12, b < 0.9); the survey searches to 100 d.

## Still open

1. **Long-period two-event pairings.** With sectors years apart, any two
   dips can be matched by some period between 10 and 100 d, and the stitch
   search accepts them with `min_transits=2`. The stitch-SNR, epoch-consistency
   and transit-count fields are recorded on every candidate and the tables
   in `docs/COMPLETENESS.md` give the false-alarm rate and the completeness
   at each threshold; the threshold itself is not enforced by P2. Prompt 4's
   frozen ranking score should be written against those tables.
2. **Objects the hard stop cannot see.** TIC 233204536 in the sample carries
   a 79-day, 55%-deep eclipse (SNR 586) and is CLEAN in all six catalogs;
   vetting will call it a false positive, but it shows that P1's open item 4
   (EBs after sector 26, QLP TCEs never promoted) is real in this population.
3. **Completeness is measured to 40 d; the search runs to 100 d.** Nothing
   in P2 measures recovery between 40 and 100 d.
4. **Chunk searches give up the multi-year coherent SNR** of a short-period
   signal (each chunk sees a quarter of a CVZ star's transits); the stitch
   re-measurement recovers the SNR only for candidates a chunk already found.
   A full-resolution search of the whole stitch below 10 d costs about
   240,000 grid points, which the kernel does at about 0.5 ms per point on
   50,000 cadences (2 minutes per pass); affordable as a targeted step on
   survivors in prompt 4, not for the whole population.
5. **Alias flips at marginal SNR.** On 30-minute data the resolver's choice
   between P and a harmonic changes with small perturbations of the data
   (9 of 80 outcomes moved between "recovered" and "alias" when 1.2% of the
   cadences were trimmed). The completeness tables report `alias`
   separately; prompt 3's odd-even fit on both P and 2P is the fix.
6. **Cost-driven search parameters** (`top_n=8`, `local_grid_cap=1500`,
   60-day chunk gap, 3 planets per sub-search, 600 s per star) were chosen
   for wall clock, and their sensitivity cost is inside the measured
   completeness, not separated from it.
7. **The ingest hash formats `120` and `120.0` differently** (JSON), so an
   override passed as an integer names a different cache file than the
   preset's float; harmless (the curve is rebuilt from the FITS cache) but
   worth normalising when no run is in flight.
8. **numba is optional.** Without it `_numpy_bls` falls back to the numpy
   loop, 4 to 6 times slower, with identical results.
9. Stitched caches from the first (buggy) ingestion and from the A/B
   variants remain under `data/cache/stitched` with their own keys; they are
   never served for the preset and can be deleted.

## Files

* `src/tesshunter/ffi.py`, `src/tesshunter/survey.py`: ingestion, config
  presets, stitched cache, injection, one-job worker.
* `src/tesshunter/pipeline.py`: `search_light_curve` (stages 2-5 on a held
  light curve), `grid_cap` / `local_grid_cap`; `search_target` unchanged in
  behaviour.
* `src/tesshunter/bls_search.py`: numba kernel plus numpy fallback,
  vectorised epoch helpers, `n_max` / `local_n_max`.
* `src/tesshunter/preprocessing.py`: vectorised `bin_lightcurve`.
* `scripts/run_survey.py`, `scripts/survey_worker.py`,
  `scripts/make_injection_spec.py`, `scripts/analyze_completeness.py`,
  `scripts/summarize_ab.py`.
* `data/survey/completeness_sample_v1.csv` (300 stars, seed 20260902),
  `data/survey/injections_v1.csv` (2,100 injections),
  `data/survey/completeness_v1.json`, `docs/COMPLETENESS.md`,
  `docs/figures/completeness_v1.png`.
* `tests/test_speed_equivalence.py`, `tests/test_ffi.py`, `tests/test_survey.py`.
* Benchmark result sets: `results/p2_speed`, `results/holdout_p2_speed` in the
  harness directory; the reference sets are untouched.
