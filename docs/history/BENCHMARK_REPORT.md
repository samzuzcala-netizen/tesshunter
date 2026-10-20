# tesshunter fix and recovery benchmark report

Date: 2026-08-05. All fixes and both benchmark runs were produced by the
process specified in `tesshunter_ultracode_fix_prompt.md` (41-agent audit of
2026-08-03, fixes applied 2026-08-04/05).

## Summary

All 28 confirmed defects (D1-D7, P1-P4, B1-B5, V1-V6, R1-R3, C1, C2, T1) were
fixed, each adversarially verified against the pre-fix snapshot. The test
suite grew from 42 to 124 tests, all green. A new canonical entry point,
`tesshunter.pipeline.search_target()`, now runs the full search with
per-planet vetting.

On the frozen 10-target benchmark (24 known planets in range):

| Metric | Shipped (baseline) | Fixed |
|---|---|---|
| Recovered (period within 2%) | 13 | **15** |
| Alias credit (P/2, 2P, P/3, 3P) | 0 | **3** |
| Missed | 11 | **6** |
| False positives | 17 | **14** |
| Pipeline crashes | 1 (WASP-18) | **0** |
| Silent author-drop (grab-bag FFI data) | 9 of 9 TESS targets | **0** |
| Planets receiving a vetting verdict | planet 1 only | **every accepted planet** |
| Recovered planets mislabeled "false positive" | 0 | 1 (WASP-18 b, discussed below) |
| Mean depth error over recovered planets | 20.9% (n=13) | 25.9% (n=15) |

The fixed pipeline finds more real planets with fewer false positives and no
crashes, on the data products it was actually asked for. It is not better on
every axis: measured depths are on average worse (explained below), TRAPPIST-1
regressed, and one genuine planet is now mislabeled as a false positive by an
astrophysically defensible vetting rule. Details below, no spin.

## Methodology

- Baseline: the shipped code (snapshot at `tesshunter_baseline_snapshot/`,
  commit `8080cbe`) run exactly as the notebooks run it, bugs included: default
  `exptime='long'`, silent author-drop retry, `lcc[:3]` product trim, dead
  flatten, notebook-02 vetting of planet 1 only. Detection loop ported verbatim
  from `scripts/_cell_loop_src.py`.
- Fixed: the repaired code (commit `761f0af`) through
  `tesshunter.pipeline.search_target()` with per-planet vetting and the
  corrected auto period grid (capped at 20000 with local alias refinement).
- Shared frozen parameters for both runs: max 3 observing units,
  bin_minutes=10, top_n=20, snr_min=5, snr_min_resolved=5,
  min_event_completeness=0.5, min_composite_score=3.0, sigma_clip=4,
  mask width_factor=7, per-target subprocess timeout 2400 s, concurrency 3.
  Baseline used n_periods=5000 and flatten_window=0.5 (shipped defaults);
  the fixed run used its corrected auto grid and window logic, as the
  specification permits. No thresholds were tuned against the benchmark.
- Scoring: identical code for both runs (`tesshunter_benchmark/score.py`),
  2% period tolerance, alias partial credit, each candidate matches at most
  one known planet, out-of-range planets score as bonus only.

Two process notes, disclosed for reproducibility:

1. The first fixed-benchmark run exposed an implementation bug in the P1 fix:
   a single ~0.5 day data fragment could bound the global detrending window at
   half its own span, collapsing every target's window to 0.19-0.69 d
   (1.3-2.2x the transit duration, below the specified floor of 3x). This
   attenuated shallow transits and cost Pi Men c entirely. The one-line
   conformance fix (commit `761f0af`: a segment may only constrain the window
   if half its span fits a transit-safe window) was applied and the ENTIRE
   fixed benchmark rerun from scratch. The interim results are archived in
   `tesshunter_benchmark/results/fixed_prewindowfix/`. No thresholds changed.
2. The first fixed run was also interrupted by a machine sleep that suspended
   three target subprocesses overnight; those targets were rerun fresh. All
   final fixed-run results come from clean uninterrupted subprocesses.
   In the baseline run, WASP-18 crashed mid-loop (a real shipped bug, see
   below); the harness was patched to record planets accepted before a crash
   and WASP-18 was rerun. The crash still occurred, identically, and is
   scored as shipped behavior.

## Per-target, per-planet before/after

| Target | Planet | True P (d) | Baseline | Fixed | Baseline depth err | Fixed depth err |
|---|---|---|---|---|---|---|
| WASP-18 | b | 0.94145 | recovered* | recovered | 24.5% | 22.0% |
| WASP-126 | b | 3.28879 | recovered | recovered | 8.0% | 7.6% |
| LHS 3844 | b | 0.46293 | recovered | recovered | 23.4% | 16.5% |
| TOI-270 | b | 3.36017 | recovered | alias:2P | 4.7% | - |
|  | c | 5.66048 | recovered | recovered | 1.9% | 0.6% |
|  | d | 11.37970 | recovered | recovered | 5.0% | 18.6% |
| L 98-59 | b | 2.25311 | recovered | recovered | 24.5% | 21.8% |
|  | c | 3.69068 | recovered | recovered | 11.2% | 4.2% |
|  | d | 7.45073 | missed | recovered | - | 4.8% |
| Pi Mensae | c | 6.26783 | recovered | recovered | 17.6% | 57.5% |
| HD 63433 | b | 7.10793 | missed | missed | - | - |
|  | c | 20.54382 | missed | recovered | - | 101.2% |
| TOI-700 | b | 9.97727 | missed | missed | - | - |
|  | c | 16.05111 | missed | recovered | - | 3.8% |
| HD 108236 | b | 3.79589 | missed | alias:3P | - | - |
|  | c | 6.20362 | recovered | recovered | 15.3% | 46.5% |
|  | d | 14.17589 | missed | recovered | - | 54.3% |
|  | e | 19.59016 | recovered | recovered | 26.1% | 21.6% |
| TRAPPIST-1 | b | 1.51087 | missed | recovered | - | 8.2% |
|  | c | 2.42182 | recovered | alias:3P | 67.1% | - |
|  | d | 4.04961 | missed | missed | - | - |
|  | e | 6.09962 | missed | missed | - | - |
|  | f | 9.20669 | recovered | missed | 43.1% | - |
|  | g | 12.35294 | missed | missed | - | - |

*Baseline WASP-18: the planet was accepted, then the pipeline crashed before
vetting (see "Crash class"), so it never received a verdict.

TOI-700 d (37.4 d) and HD 108236 f (29.5 d) lie outside the searched ranges
and were not detected by either run (no bonus, no penalty). TRAPPIST-1 h
likewise.

## False positives, runtime, provenance

| Target | FPs before | FPs after | Wall before (s) | Wall after (s) | Author-drop before | Author-drop after | Crash before | Crash after |
|---|---|---|---|---|---|---|---|---|
| WASP-18 | 0 | 0 | 174 | 636 | yes | no | yes | no |
| WASP-126 | 1 | 1 | 125 | 286 | yes | no | no | no |
| LHS 3844 | 0 | 1 | 437 | 1313 | yes | no | no | no |
| TOI-270 | 0 | 1 | 178 | 228 | yes | no | no | no |
| L 98-59 | 2 | 1 | 231 | 696 | yes | no | no | no |
| Pi Mensae | 1 | 1 | 139 | 313 | yes | no | no | no |
| HD 63433 | 3 | 2 | 470 | 1094 | yes | no | no | no |
| TOI-700 | 3 | 2 | 208 | 224 | yes | no | no | no |
| HD 108236 | 2 | 0 | 480 | 1552 | yes | no | no | no |
| TRAPPIST-1 | 5 | 5 | 413 | 407 | no | no | no | no |

Every baseline TESS target silently fell back to a grab-bag of FFI pipelines
(TESS-SPOC 10/30-min products, duplicated sectors double-counted by the
product trim). Every fixed-run TESS target used deduplicated SPOC 2-min
products, which is what `author='SPOC'` asked for all along. That is also why
the fixed run is slower (roughly 6x the cadences plus a 2-4x finer period
grid); every target still finished well inside the frozen 2400 s budget
(worst: HD 108236 at 1552 s). Fixed batch wall clock: 2872 s at concurrency 3.
The baseline batch took 1071 s (recorded from the original run's output; its
_run_summary.json was later overwritten by the single-target WASP-18 rerun,
so the surviving primary data are the per-target walls, which sum to 2855 s
serial).

## Which fixes drove which changes

- WASP-18 recovered end to end: the shipped code crashed after accepting
  planet 1 (the mask half-width, 7 x the fitted 0.0822 d duration = 0.575 d,
  exceeds half the 0.94 d period, emptying the light curve; the post-mask BLS
  then dies on a zero-size array). The pipeline
  robustness work (pipeline.py, sanctioned addition to the ported loop) stops
  cleanly instead. This was a 100%-reproducible shipped crash on a
  Jupiter-class planet.
- HD 63433 c and TOI-700 c, newly recovered: driven by P1 (flatten actually
  detrending; the shipped window math meant stellar variability was never
  removed, and young active HD 63433 produced only 5000 ppm junk in the
  baseline) plus D1/D2 (2-min SPOC data instead of FFI mixtures).
- L 98-59 d, TOI-270 d retained, HD 108236 c/d/e: B1 (the auto grid at proper
  resolution; the shipped auto grid had ~526 points and even n_periods=5000
  undersamples 5-13 d multi-transit periods on multi-sector baselines) plus
  the honest B2 SNR keeping real signals above gates.
- False positives 17 to 14 with much better verdict coverage: B4
  (n_transits_observed >= 2 acceptance gate, no completeness free pass for
  single dips) plus per-planet vetting (every accepted candidate now carries a
  verdict; the baseline vetted planet 1 only and hardcoded 'candidate' for the
  rest in the summary CSV).
- Depth accuracy on quiet bright stars improved slightly where the same planet
  was recovered by both runs at full quality (WASP-126, LHS 3844, L 98-59 c,
  TOI-270 c). See limitations for where it got worse.

## Verdict sanity

The specification counts a recovered planet labeled "likely false positive" as
a mislabel. The fixed run has exactly one: WASP-18 b, recovered at
0.9414508 d (period error 0.0002%) with SNR 733, labeled likely false
positive by the vetting stack. The flags are individually defensible for an
ultra-hot Jupiter: SNR far above the stellar-activity threshold plus a real,
detectable secondary eclipse (WASP-18 b genuinely shows one in TESS
photometry; an EB-style secondary is the single strongest false-positive
indicator the vetter has). The radius-aware V1 fix correctly reports the
implied companion radius (about 1.2 R_Jup) as planet-regime; the verdict
logic nevertheless lands on likely-FP because secondary-eclipse plus
extreme-SNR flags stack. The baseline scored zero mislabels only because its
planet-1 vetting never ran on WASP-18 (it crashed first) and its verdicts
covered 9 planets instead of 18. This is a real, known limitation of
photometry-only vetting for phase-curve planets and is reported as such.

## Remaining limitations and honest misses

1. Depth attenuation for planets not protected by the two-pass flatten. P4's
   two-pass detrending masks only the pass-1 top candidate before re-fitting
   the trend. Later planets in multi-planet systems are partially absorbed by
   the trend fit, which is why paired depth error (10 planets recovered by
   both runs) worsened from 15.7% (baseline, whose dead flatten never touched
   any transit) to 21.7%, with Pi Men c (57.5%) and HD 108236 c (46.5%) the
   worst cases. The fix direction is clear: iteratively re-flatten masking ALL
   accepted candidates. Not done here; it is beyond the audited defect list.
2. TRAPPIST-1 regressed: baseline recovered c and f (with 43-67% depth
   errors); the fixed run recovers b cleanly (8.2% depth error), catches c
   only as a 3P alias, and misses d-g, with 5 false positives whose fitted
   depths (1.5-9.6%) are physically absurd for this star. One campaign of K2
   30-min data on an M8 dwarf, with roll systematics the 1.0 d artifact
   suppression only partly covers, remains beyond this pipeline's reach; the
   honest SNR and completeness gates now let residual-systematic peaks through
   where the old inflated SNR happened to favor two true periods. A dedicated
   K2 systematics model (SFF/EVEREST-style) would be required to do this
   target justice.
3. Alias captures: TOI-270 b (2P) and HD 108236 b (3P) were found at
   harmonics. The alias resolver considers P/2, 2P, P/3, 3P trial periods, but
   composite scoring preferred the harmonic in these two cases. Partial
   credit under the frozen scheme.
4. Still missed outright: HD 63433 b (502 ppm under heavy activity residual),
   TOI-700 b (460 ppm, the shallowest TESS planet in the set), TRAPPIST-1
   d/e/g. No parameters were tuned to chase them.
5. False positives are not zero (14). Notably TOI-700's two FPs at 15.5-15.6 d
   sit near c's 16.05 d period (residual ringing after masking), and Pi
   Mensae's 10.34 d FP carries SNR 67. The per-planet verdicts mark 5 of the
   14 as ambiguous rather than promising; 8 are labeled promising
   (over-optimistic), 1 as likely-FP.
6. WASP-18 b's measured depth remains 22% low: a 0.94 d period leaves little
   out-of-transit baseline, 10-min binning smears the 2.05 h transit, and the
   box model underestimates limb-darkened depth. Both runs show this.

## Defect fix status

All fixed and adversarially verified (fix agent, then independent verifier
reproducing the old bug on the snapshot and proving the new behavior, per
module): D1-D7 (download), P1-P4 (preprocessing; P1 required the follow-up
window-bound conformance fix `761f0af` described in Methodology), B1-B5 (BLS),
V1-V6 (vetting/centroid/contamination), R1-R3 (reporting), C1 (config),
C2 (README rewritten, stale 03_batch_search notebook deleted), T1 (tests,
including the flagship end-to-end injection-recovery test on gapped variable
data through flatten, which fails on the shipped code). New module:
`src/tesshunter/pipeline.py`. Nothing was skipped.

Commits: `8080cbe` shipped state, `9120dea` wave 1 (module fixes), `7b0a688`
wave 2 (pipeline.py, config, phase-binned BLS engine for an 8x speedup),
`73a409a` wave 3 (tests + README), `761f0af` window-bound conformance.
Suite: 124 passed.

## Reproducibility

- Baseline snapshot: `C:\Users\samzu\Downloads\tesshunter_baseline_snapshot\`
- Harness, per-target JSON results, logs, and scores:
  `C:\Users\samzu\Downloads\tesshunter_benchmark\` (`results/baseline/`,
  `results/fixed/`, `results/fixed_prewindowfix/` (interim archive),
  `results/*_scores.json`, `logs/`)
- Rerun: `python orchestrate.py --mode baseline|fixed`, then
  `python score.py --mode baseline|fixed`, then `python compare.py`.
- Light-curve cache shared by both runs: `data/cache/lightkurve` (919+ FITS).
  A live MAST search still precedes cache hits, so network is required.
