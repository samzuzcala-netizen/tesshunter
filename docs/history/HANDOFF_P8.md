# HANDOFF P8: completed small-star survey and audit

P8 is complete: 0 SUBMIT, 2 HOLD and 4 KILL among 6 Stage C survivors [M]. The ordered submission list is empty. All search and funnel measurements, local reviews, packets, the artefact census and required checks are finished. The scientific follow-up conditions for unresolved or rejected signals remain in each review; there is no unfinished pipeline job. Nothing was submitted externally. Branch: `improve/recovery`.

Evidence: [M] measured in this run; [Pn] inherited from prompt n; [A] adopted
assumption. Nothing was submitted externally. The review entry point will be
[AUDIT_P8.md](docs/AUDIT_P8.md), with its ordered local packet list.

## Population and cadence

The seeded population command is `python scripts/build_p8_population.py all --seed
20260904`; `python scripts/write_population_p8_memo.py` regenerates the memo from
the saved records. The final list contains 2,000 stars selected from 9,989 qualified
objects [M]. All 2,000 have complete Gaia, SIMBAD and VSX record files with a Gaia
target match [M]. The selection uses Teff < 3600 K, radius < 0.45 solar radii,
Tmag 12.5–14.0, absolute Galactic latitude >= 20 degrees, the adopted Gaia dwarf
check, at least three delivered 200-second sectors, and a strict minority of
2-minute sectors [A, applied M]. No population relaxation was needed.

The zero-2-minute cut leaves 9,285 objects and the adopted minority cut leaves
10,512 before the hard stop; 1,374 selected targets have zero 2-minute search
sectors [M]. Delivered-coverage fractions at Tmag 13.5–14.0 and 14.0–14.5 are both
about 27%; their ratio is 0.997 [M]. An extension was permitted by the rule but
unnecessary to fill the population. Every cut, Gaia outcome and coverage bin is in
[POPULATION_P8.md](docs/POPULATION_P8.md).

The paired 600-second experiment compared 700 injections on 100 stars, with no
missing pair [M]. The 200-second run recovered 403; the 600-second run recovered
302. There were 127 recoveries unique to 200 s and 26 unique to 600 s. The
pre-registered admission statistic was -101 versus a required value above 24.739;
600-second sectors were excluded. See
[decision_600s.json](data/survey/p8/decision_600s.json).

## Calibration and the decision to search

There were 2,100 injections on a seeded 300-star sample: 1,163 recovered, 855
missed and 82 aliases [M]. All recovered injections have settled A and secondary
records. The search-through-secondary calibration uses p7.0; the chosen p8.0 A/secondary rules
are identical, with exact Stage B duration/window metadata added.

| Calibration level [M] | Through / 2,100 | SNR50 | SNR90 |
|---|---:|---:|---:|
| Search | 1,163 | 13.15 | 31.65 |
| Search + pre-gate | 1,121 | 14.08 | 31.44 |
| Search + A | 1,093 | 14.65 | 36.66 |
| Search + A + secondary | 904 | 20.19 | 75.18 |
| Search + pre-gate + A + secondary | 896 | 20.44 | 73.98 |

The same 300 stars without injections produced 2,097 accepted signals, 586
pre-gate passers, 36 A passers and two secondary passers [M]. This projects 13.33
early-funnel survivors over 2,000 stars. It is a surviving-signal rate, not an
isolated instrumental false-alarm probability. The expected new-signal counts
are 14.924, 11.675 and 8.087 for low, mid and high incumbent-search completeness
priors [M under adopted model assumptions]. Higher incumbent completeness leaves
fewer new signals. The mid-prior expectation passed the pre-registered 3.0 stop
threshold. Its ratio to the projected control survivors is 0.876. B/C/D losses
were not calibrated; these numbers do not predict the final submission count.

[COMPLETENESS_P8.md](docs/COMPLETENESS_P8.md) preserves sample sizes, maps and
bootstrap intervals. The period, radius, magnitude and rotation dependence must
not be replaced by a single fitted SNR threshold.

## Frozen rules and fit exercises

The rules were committed as p8.0 in `2aecc0e` before the real candidate list was
inspected or any real candidate entered A [M]. Decision 1 selected `bound`:
901/1,089 instrument A passers retained, with all 26 reference adversarial
secondary kills retained. Decisions 2/3 selected `masked|cap5|0.001`: 1,089/1,163
injections passed all six criteria, with all 40 reference depth-consistency kills
retained. The required retention floor was 90%, fixed before measurement.

Cap 2 and cap 3 each passed 1,088 injections. The one-injection margin selects
cap 5 under the registered rule; it does not establish statistical superiority.
Four differences between the fixed-ephemeris instrument and the 1,093 full-A
passers were explained by exact survey-mask replays. All 1,163 comparison
records were validated, with no remaining secondary difference. Both white and
inflated depth p-values remain in each record. Neither distribution is uniform
on constant-depth recovered injections; p < 0.001 occurs for 10.7% with white
errors and 2.9% with inflated errors [M].

The full variant tables and implementation are in [RULES.md](docs/RULES.md).
The original pre-registration is preserved verbatim below and in Git history.
The required `p7_reproduce.py all --slices 16` run re-derived 823 historical
records: **0 field differences, 0 decision differences, 0.0 worst relative
difference** [M]. The replayed set is p6.2; P7 option records were retained
unchanged. See [reproduce_p7_p8.json](data/survey/p8/reproduce_p7_p8.json).

The previously unexercised all-transit fit, CTOI writer and verdict path completed
on both non-candidate controls [M]. TOI-270 c used 34 transits and gave
2.324 +/- 0.077 Earth radii. The recovered injection used nine transits and gave
3.890 +/- 0.390 Earth radii, versus injected 3.9021. Both adopted the density
prior and avoided a grazing rail. The injection also completed the p8.0 A/S/B/C
and fit/writer/verdict exercise; its explicit EXERCISE stamp is excluded from
the real funnel. [fit_exercises_p8.json](data/survey/p8/fit_exercises_p8.json)
preserves fits, earlier attempts, measured flags and source hashes.

## Real search and funnel

All 2,000 targets succeeded on their first attempt; none was missing or failed
after the retry check [M]. The search accepted 13,252 signals on 1,998 hosts;
3,688 passed the pre-gate on 1,396 hosts. The search budget stopped further
sub-searches on 745 targets, which retain successful result records.

Prefetch took 821.15 s. The search ran from 19:43:43 EDT on September 5 to
02:51:40 EDT on September 6, 2026, taking 25,676.56 s; the retry check took
2.35 s [M]. Per-job wall time was median 204.1 s, p90 466.14 s and maximum
683.5 s, summing to 139.36 job-wall hours. These are not CPU-time measurements.
[per_target_log.csv](data/survey/p8/per_target_log.csv) preserves each target's
products, sectors, timing, fallback and budget stops.

| Stage | Entered [M] | Result [M] |
|---|---:|---|
| Accepted by search | 13,252 | 13,252 |
| Pre-gate | 13,252 | 3,688 |
| A | 3,688 | 189 PASS, 3,499 FAIL |
| Secondary on A passers | 189 | 19 PASS, 170 FAIL |
| B | 19 | 19 PASS |
| C | 19 | 6 PASS, 13 FAIL |
| D | 6 | 0 SUBMIT, 2 HOLD, 4 KILL |

The seeded 10% A-failure sample contains 350 candidates, with secondary outcomes {'PASS': 172, 'FAIL': 178, 'HOLD': 0, 'ERROR': 0} [M]. It uses seed 20260904 and sampling without replacement from the final A-failure pool. [The saved sample and hashes](data/survey/p8/secondary_failure_sample_p8.json) reproduce the selection. The final A/S/B/C eligibility checks have no missing, stale or errored record. [funnel_p8.json](data/survey/p8/funnel_p8.json) preserves all denominators.

Across all 3,688 A records, per-candidate wall time was median 88.15 s, p90 549.59 s and maximum 1585.6 s, summing to 221.251 job-wall hours [M]. The A coordinator took 42068.3 s [M]. The 19 completed C attempts took a median 6580.8 s and maximum 30425.9 s [M]. Three runtime restarts retained 7.985 CPU hours from their stopped attempts separately [M]. Concurrent job-wall totals are not elapsed duration or CPU time. The main coordinator completed measurements and packets at 2026-09-06T20:56:23Z [M]. [funnel_timing_p8.json](data/survey/p8/funnel_timing_p8.json) records the timing definitions and attempt history.

The input reconciliation found no duplicate audit key or out-of-band survey
period, and verified all 20,924 products at the common 200-second cadence [M].
Thirteen TESS-SPOC products are from special sector 1751; their metadata matches
the [mission notes](https://heasarc.gsfc.nasa.gov/docs/tess/sector1751_summary.html).
All 13 hosts satisfy the minimum coverage using ordinary sectors. None is in
the calibration sample, so this extra pointing is not separately calibrated.
[search_validation_p8.json](data/survey/p8/search_validation_p8.json) preserves
source hashes and metadata. No raw light-curve archive was removed during P8.

## Reviewed Stage C survivors

| V2 rank [M] | Candidate and packet | Fitted P (d) [M] | FPP / NFPP [M] | Verdict [M] |
|---:|---|---:|---|---|
| 1 | [TIC 230120862](docs/packets/audit_p8/tic230120862_P16.7959/packet.md) | 16.789504153 | 1 / 0.945597 | KILL |
| 2 | [TIC 80256158](docs/packets/audit_p8/tic80256158_P10.8184/packet.md) | 10.818393943 | 0.21122 / 0.0345335 | KILL |
| 3 | [TIC 154566869](docs/packets/audit_p8/tic154566869_P8.9053/packet.md) | 8.885255332 | 0.988154 / 0.918773 | HOLD |
| 4 | [TIC 404927114](docs/packets/audit_p8/tic404927114_P27.5436/packet.md) | 27.543390053 | 0.201585 / 0.169895 | HOLD |
| 5 | [TIC 144277542](docs/packets/audit_p8/tic144277542_P12.9812/packet.md) | 12.981388999 | 0.0472098 / 0 | KILL |
| 6 | [TIC 155895971](docs/packets/audit_p8/tic155895971_P13.1279/packet.md) | 13.128105649 | 0.000658965 / 5.53027e-06 | KILL |

Every survivor has a fresh six-catalogue hard stop, an all-transit physical fit, TESScut centroid, non-uniform TRICERATOPS result, packet and CTOI fields [M]. The fitted geometry is often weakly constrained; a non-grazing best fit is not proof of a measured impact parameter. The accepted C ephemeris and its hash seed every fit.

TIC 230120862: **KILL**. Background/correction artifact. Difference images are dominated by changing diffuse background at both the physical-fit and original Stage A ephemerides. At the original 4.8-hour Stage A window, fixed-aperture depths are -6.620 +/-1.397, 5.083 +/-0.699, 7.158 +/-1.110 and -3.283 +/-1.643 ppt in sectors 58, 79, 83 and 86 [M], with raw changes tracking sky ramps and no stable isolated transit. The physical fit reaches a grazing rail and has unusably large geometry uncertainties. Reconsideration condition: Independent photometry with a stable background must reproduce localized, repeated dimming at the candidate ephemeris and permit a constrained physical fit. Fixed-aperture depths remain diluted and their point-scatter errors omit correlated noise. The current measurements do not support a separate clean EB report.

TIC 80256158: **KILL**. Background/correction artifact. The fixed target-aperture depths change sign across sectors (1.012, -1.011, 6.578 and -5.333 ppt), with raw variations tracking sky ramps and broad steps [M]. Difference images do not repeat a stable dimming point source or the fitted shallow transit. Reconsideration condition: To reconsider: independent photometry must show repeated dimming localized to a stellar source, with a stable background and consistent depth and transit shape across sectors. Fixed-box errors use local point scatter and omit some correlated noise.

TIC 154566869: **HOLD**. Source unresolved. Target-aperture dimming varies across sectors and is mixed with background changes; the difference images do not isolate a unique eclipsing source. FPP is 0.988154 and NFPP is 0.918773 [M], so the current evidence does not support a planet interpretation. The density prior is rejected and transit geometry remains poorly constrained. Reconsideration condition: To reconsider: independently reproduce a repeated localized transit while fitting the variable sky/background and nearby sources, and obtain useful transit-geometry uncertainties.

TIC 404927114: **HOLD**. Source unresolved in a crowded variable-star field. The primary difference images are weak/mixed in sector 63 and dominated by diffuse background changes in sectors 90 and 98. The fixed sky annulus leaves only one usable pixel per sector, below the required 16, so a reliable target-aperture depth could not be extracted. FPP is 0.201585 and NFPP is 0.169895 [M]; source localization is inadequate for submission. Reconsideration condition: Source-resolving photometry or a validated crowded-field PSF/difference-image analysis must separate the target from neighbours and background, then show repeatable dimming near 27.5434 d with consistent depth. The present fixed-annulus method cannot supply that deblending. A satisfactory transit geometry alone does not resolve the contamination.

TIC 144277542: **KILL**. Background/correction artifact. Diffuse event difference images and raw-aperture changes tracking the sky do not reproduce the fitted shallow target dip: the fixed sky-subtracted depths in sectors 95 and 104 are 0.584 +/- 1.353 and -0.481 +/- 0.720 ppt, while sector 68 has a broad unstable 33.178 +/- 4.424-ppt change [M]. Reconsideration condition: To reconsider: independent photometry must show repeated dimming localized to a stellar source while the background remains stable. These box errors use local point scatter and are not a formal exclusion probability including correlated noise.

TIC 155895971: **KILL**. Background/correction artifact. Three primary-event difference images are dominated by whole-cutout background changes, and the fixed target aperture alternates between large brightening, a weak dip and unstable gap-adjacent structure instead of a repeatable transit [M]. FPP 0.000659 is conditional on astrophysical hypotheses and does not account for this instrumental evidence. Reconsideration condition: To reconsider: independent photometry must reproduce repeated dimming localized to a stellar source with stable background, including a consistent depth and transit shape across sectors. The fixed-box errors describe local point scatter and omit some correlated noise.

The census covers 3,688 A candidates; 3,170 are carried by at least one removal class [M]. The eight classes overlap. [AUDIT_P8.md](docs/AUDIT_P8.md) compares them with P6, and [census_p8.json](data/survey/p8/census_p8.json) preserves event, sector and detector counts.

## Rejected signals and the EB report


TIC 233127050 has regularly repeating dips in SAP and corrected flux at shorter hypotheses of 0.3936113 or 0.1968057 d [M]. Two inspected six-panel folds and fixed-box measurements in 16 sectors show no primary/secondary difference above 2.34 point-scatter sigma [M], with larger depth changes between sectors. Its source and orbital period remain unresolved; no additional clean EB classification or planet-funnel promotion follows from this diagnostic. The read-only cached six-catalogue cone check is not a fresh hard stop. See data/survey/p8/eb_screen/tic233127050_P3.9361_followup_review.json.

All 170 S rejections among the final A passers received an overview morphology review [M]. The selected sector-detail follow-up, two harmonic figures and five non-random depth-only A failures are documented separately. The 350 randomly sampled A failures received secondary scans, not a systematic visual EB search. This scope does not measure EB completeness. [eb_review_p8.json](data/survey/p8/eb_review_p8.json) links the source-validated assessments.

One local EB candidate report is supported at
[TIC 279426256](docs/eb_reports/tic279426256_vsx_fields.md), Gaia DR3
5484242473249094784, about 42.1 arcsec from searched TIC 279426252 [M]. Both
minima at P = 0.7470014478 d follow that neighbour's pixel position in sectors
61, 87 and 98. A separate aperture gives primary depths of 22.12, 28.01 and
19.13 ppt and secondary depths of 11.09, 17.52 and 7.79 ppt [M]. These are
diluted local box depths, without intrinsic magnitude ranges, a fitted binary
subtype or formal ephemeris uncertainty. The source's TIC Teff is 5053 K; it is
outside the selected small-star population. This measurement does not alter any
planet-funnel gate.

The six hard-stop catalogues were freshly downloaded on September 6 for this
source and return CLEAN; the wider VSX/SIMBAD queries have no positional match
[M]. All 132 SPOC TCE version files, 551.2 MB, were re-downloaded. The report
links the receipts, figures, binned measurements and source hashes. Uncatalogued
means absent from those checked catalogues on that date.

Two other sharp-eclipse sources match known neighbouring binaries: the signal
on TIC 294768511 matches the nearby Gaia EB, and that on TIC 135048134 matches
SSS_J121846.5-413525. Their neighbours can supply the depth, but no image centroid
was measured for these two associations. Repeated dips in the 11.9275-day alias
on TIC 278410520 instead repeat its already-searched 2.982-day signal; they do
not establish a secondary eclipse or a new binary classification.

## Implementation and validation

Stage B stores unrounded duration/window fields. P8 neighbour records acquired
the completed survivor-depth context for 1,396 hosts before B; 1,360 have a
neighbour capable of a survivor depth under the inherited per-star total-eclipse
test [M]. This is a HOLD flag and does not locate the source. A VSX display-unit
repair corrected 324 separations in 301 star records and four bulk caches,
changing no vetting flag. The original source values and repair hashes remain
available in the P8 evidence files.

The catalogue membership lookup now constructs an integer set once, preserving
exact output while removing quadratic work. P8 Stage D explicitly re-downloads
every TCE version file and requires the matching receipt. The expensive adapter
checks preceding gates and native inputs, fingerprints P8 FPP inputs, separates
pixel and FPP checkpoints, and produces local review packets. Legacy cache keys,
P6/P7 default rules and their default catalogue fetch policy remain unchanged.

Bounded helpers used the existing atomic A queue and stopped at at most 50
claims each. New A-resume and C drivers wait for earlier Windows workers before
reading eligibility and creating a fresh queue. The guard never terminates a
worker or modifies a measurement. Ten bounded A consumers across seven registered batches completed exactly 500 distinct audits [M]. Forty-two early S batches advanced 188 settled A passers while A continued; the final coordinator added one further A passer, which failed S [M]. The early C/D records were reused under the same rules. All helpers are finished.

The latest full suite passed **622 tests, with 1 skipped and 9 warnings, in
122.85 s** [M]. All five population tables and 42 rows were checked for consistent
Markdown columns. The EB overview leaves empty phase bins blank; 147 existing
plots were checked after that fix, one was affected, and its re-render was
visually verified. The packet guard also passed 14 focused tests [M].
P6/P7 record directories remain unchanged from baseline `cb21449a2123f073cc96c24123f642e7fda9bf54` [M]. Final packet source hashes, CTOI fields, local Markdown links and report table columns were checked after the final verdicts.
[adapter_validation_p8.json](data/survey/p8/adapter_validation_p8.json) contains
the log and source hashes. The final local commit on `improve/recovery` names Prompt 8; its hash is reported with the delivered audit. Nothing was pushed.

Concurrent final pixel downloads exposed an Astroquery temporary-ZIP collision:
three pairs of requests used the same one-second filename, leaving six sectors
unavailable [M]. Downloads now use private temporary directories and publish only
a completed file matching the requested target and sector. The repair passed
13 focused tests and the full suite above [M]. All six cutouts were recovered;
TIC 404927114 has pixels for all 12 requested sectors, with 11 usable centroids,
and TIC 230120862 has 18 of 18 usable centroids [M]. Their centroid measurements
were repeated; their completed FPP results were retained unchanged. Initial
measurements and the repair receipt are preserved in
[pixel_download_repair_p8.json](data/survey/p8/pixel_download_repair_p8.json).

The grazing-rail problem recurred for TIC 230120862: b is 1.099999 and T14 is
21.307 +/-28.634 h [M]. Its rejection also has independent pixel evidence at the
unchanged earlier Stage A ephemeris. TIC 404927114 has only one usable sky pixel
in each of its three reviewed fixed annuli, below the required 16 [M]; its
auxiliary target-aperture depth remains unavailable and crowding requires
scientific follow-up. Those limitations are recorded in the completed reviews.

## Assumptions and remaining limits [A]

The yield model uses DC15, an inherited giant-rate allowance, adopted incumbent
priors and phase-averaged coverage. Its SNR-only logistic curve approaches unit
completeness even though event vetoes can remove strong signals. Bootstrap
intervals resample injections individually and omit dependence within a host.
The HU19 calculation is a sensitivity proxy. B/C/D efficiency is uncalibrated.
No threshold was retuned on real P8 candidates.

The inherited physical-fit model assumes circular orbits and fixed quadratic
limb darkening. Its catalogue-density comparison fixes a/R* to the catalogue
value and adopts that fit when the increase in chi-squared is below 9 [P5, A].
When catalogue uncertainties are unavailable, the code uses 10% radius and 30%
density errors [A]. These are modelling assumptions, not independently measured
stellar uncertainties. A density mismatch alone does not establish a binary;
the instrumental rejections here rely on the pixel evidence.

Flares, rotation, noisy faint-star QLP photometry and correction-made dips were
anticipated. The census classes overlap; comparing P8 with P6 changes population,
cadence and rules together. Gaia neighbour flags do not identify which source
varies. Pixel source association does not exclude an unresolved companion.
TRICERATOPS uses the inherited aperture and a binned fold; uniform scenario
probabilities mean the likelihood calculation failed. Its astrophysical
hypotheses omit instrumental artifacts, so a low FPP cannot override an
instrumental rejection. Fixed target apertures remain diluted, with box errors
based on local point scatter rather than a complete correlated-noise model.
Centroid shifts can reflect background changes and are not fitted source
positions. Missing diagnostics remain explicit in the review.

The [implementation history](docs/P8_IMPLEMENTATION_HISTORY.md) preserves
interrupted calibration runs, repairs and prior checkpoint measurements. Its
pending-work statements are historical.

## 0. Pre-registered decision rules (written before the measurements they judge)

All written 2026-09-04 before any of the runs below started; none is changed afterwards.

* **The 600-second decision (Part 1e).** The same 700 injections (a seeded 100-star subset of the
  300-star sample, all 7 injections per star) are run under `survey_p8` (sectors >= 56 at native
  200 s) and under `survey_p8_600s` (sectors >= 27, everything binned to 600 s). With a = the
  number recovered only at 200 s and b = the number recovered only at 600 s (paired outcomes),
  the 600-second sectors enter the search only if b - a > 2 sqrt(a + b). Otherwise the search
  runs on the 200-second sectors alone.
* **The stop rule (Part 1f).** If the mid-prior expected number of new signals through the
  funnel is below 3.0, the search does not run. The high-prior number is reported next to it.
* **The pre-gate [A].** A candidate enters Stage A only if its whole-stitch re-measurement is
  epoch-consistent with stitch SNR >= 7.1 and >= 3 transits. The transit-count half is lossless
  with respect to the funnel (Stage A needs three kept events); the SNR half is the prompt-4 G2
  threshold lowered to the SPOC release floor. Its cost is measured on the recovered injections.
* **Part 3, X = 90 percent**, the three rules verbatim from `scripts/p8_decisions.py`
  (commit b3ba6a2):
  * Decision 1 (the secondary gate). Completeness = the fraction of recovered injections passing
    Stage A whose gate is not FAIL under the variant. Kills = the fraction of the adversarial EBs
    and blends that p7.0's gate FAILs which the variant still FAILs. Choose the variant with the
    highest completeness among those that retain at least X percent of the p7.0 kills; a tie goes
    to the variant retaining more kills, then to p7.0. Variants: (a) bound (p7.0); (b) quiet_bound
    with N=2; (c) quiet_zero with N in {2, 3, 5}; (d) quiet_bound_hold with N=2.
  * Decisions 2 and 3 (depth consistency and the masked detrend, together). Completeness = the
    fraction of recovered injections passing all six Stage A criteria under the variant (mask
    on/off x errors in {white, inflated cap 2, cap 3, cap 5} x threshold, moved only for white
    errors: 1e-3, 1e-4, 1e-5). Kills = the fraction of the reference kill set (the 18 prompt-6
    candidates that failed only depth consistency plus the adversarial EBs and blends) that p7.0
    (mask on, cap 5, 1e-3) FAILs on depth consistency which the variant still FAILs. Choose the
    combination with the highest completeness among those retaining at least X percent of the
    p7.0 kills; a tie goes to the combination retaining more kills, then to p7.0.
  * The 405 are reported under every variant, never used in a rule.

Fit initialization repair [M]: P8 physical fits and packet validation now require the exact current Stage C accepted ephemeris and its source hash. The survey-seeded first real fit could not reach the accepted period within its local bounds and is preserved as superseded diagnostic history in fit_seed_repair/. The repair was tested on shifted-period and factor-two synthetic cases, then on the recovered injection (nine transits, Rp=3.890 +/-0.390 REarth, density prior adopted, not grazing) before rerunning the real fit. No A/S/B/C threshold changed; P6/P7 behavior is retained. Final candidate assessments use the corrected fits.

## Pixel provenance and runtime history

Reviewed pixel follow-up uses the accepted physical-fit ephemeris, a fixed
one-pixel target aperture, a 5-to-9-pixel sky annulus, and identical Gaia masks
in every sector [A, applied M]. The first 90-arcsec Gaia cone did not cover the
full background annulus. All real-candidate diagnostics subsequently used
300-arcsec cones. Re-extracted depths for TIC 154566869 were 3.694, 2.076 and
5.740 ppt; those for TIC 144277542 were 33.178, 0.584 and -0.481 ppt [M].
Both assessments were unchanged. Original measurements are archived in
`early_D_results/batch2`; `eb_screen/background_mask_validation_p8.json`
records the comparison. No aperture or ephemeris was tuned to a verdict.

At 12:45 EDT on September 6, process-local affinity assigned the 16 active A
workers to 16 efficiency cores and long single-thread C jobs to the eight
performance cores [M]. That first placement change restarted no process.
`cpu_placement_p8.json` records the measured Windows topology and identities.

After A/S/B completed, a synthetic period-loop probe compared 384 sampled
periods on 150,012 native-cadence points [M]. Sorted period, residual, template
row and depth outputs were exactly equal with one, four and eight TLS workers.
The measured times were 28.008, 10.994 and 9.000 s, a 3.112-fold speedup with
eight workers [M]. A runtime rule written before the probe required exact
agreement and at least a twofold speedup before considering restarts.

The remaining C5/C14/C17 checks were then restarted as top-level subprocesses
with eight internal TLS workers each, 24 in total, with full processor affinity
[M]. This is a tested runtime exception to the attached prompt's one-thread
recommendation; period grids, duration grids, masks, cadence and scientific
gates were unchanged. Every stopped attempt, process identity, input hash and
log is retained in `C_attempt_history/`. The main coordinator waited for the
replacement processes and did not create duplicate jobs. The probe and
pre-written decision are in `logs/tls_thread_probe.json` and
`logs/runtime_followup_plan.json`. This engineering probe is not an additional
candidate search or a calibration measurement.
