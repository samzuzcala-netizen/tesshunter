# tesshunter: five prompts to a submission-grade CTOI

Run these in order, one per fresh session. Each prompt is self-contained.
Each ends with a written handoff that the next prompt reads first.
Goal of the whole sequence: at least one candidate that survives an
adversarial audit and is ready to submit to ExoFOP-TESS as a CTOI
(community TESS Object of Interest), with the human, not the agent,
pressing submit.

Design principle: every prompt spends its effort where it changes the
odds of a real, new, defensible candidate. Nothing is built for
elegance. Anything that does not move that probability is out of scope.

---------------------------------------------------------------------

## SHARED PREAMBLE (paste at the top of every prompt)

Environment facts, verified on 2026-09-01:

- Repo: `C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter`
  (note the double-nested directory). Branch `improve/recovery`.
- Benchmark harness (frozen, do not edit `score.py`):
  `C:\Users\seanj\Downloads\tesshunter_benchmark\tesshunter_benchmark`
- Python: `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe`
  (3.13, lightkurve 2.6.0). Global Python has no scientific stack.
- Before anything imports tesshunter set
  `LIGHTKURVE_CACHE=<repo>\data\cache\lightkurve` and `PYTHONIOENCODING=utf-8`.
- Never call `logging.getLogger("astropy")` before astropy is imported.
- Synthetic light-curve helpers in `tests/test_injection_recovery.py` and
  `tests/test_vetting.py` store time as BTJD + 2457000;
  `tests/test_pipeline.py` uses plain BTJD. Match the frame of the helper you call.
- The working tree and the light-curve cache have arrived EMPTY before.
  First action of every session: `git status`, count files under
  `data/cache/lightkurve`, run `pytest tests/ -q`. If source is missing,
  `git checkout HEAD -- src tests`. Do not trust the previous handoff's
  claim that the tree is healthy. Measure it.
- Read `IMPROVEMENT_REPORT.md` sections 4 and 5 (known weaknesses,
  remaining work) before changing detection or vetting code.
- Machine: 24 cores. Per-target work is single-threaded.

Rules for every prompt:

1. Commit at the end of each prompt on `improve/recovery` with a message
   naming the prompt number. Do not push unless told.
2. Write `HANDOFF_P<n>.md` in the repo root: what shipped, what was
   measured (with sample sizes), what was refuted, what is still open.
   Evidence-tagged and objective. Assumptions kept out of the results.
3. Never write "discovered", "planet found", or "confirmed" anywhere.
   The pipeline finds candidates.
4. The agent never submits anything to ExoFOP, MAST, or any external
   service. It prepares packets; the human submits.
5. If a lead is refuted by measurement, say so and do not build it.

---------------------------------------------------------------------

## PROMPT 1: Hard-stop cross-match and the survey population

You are turning a known-planet benchmark pipeline into a discovery
survey. This prompt decides WHERE to look and guarantees we cannot
rediscover something already claimed. Both are worth more than any
detection improvement.

### Part A: cross-match becomes a hard stop

`src/tesshunter/catalog_crossmatch.py` currently checks the ExoFOP TOI
list and the NASA Exoplanet Archive confirmed planets. Extend it so a
target is rejected before search if it appears in ANY of:

- ExoFOP TOI list (existing)
- ExoFOP CTOI list (`download_ctoi.php`)
- NASA Exoplanet Archive confirmed planets (existing) and the
  Planetary Systems composite table
- TESS Eclipsing Binary catalog (Prsa et al. 2022, on MAST as an HLSP)
- SPOC threshold-crossing-event (TCE) lists for every sector and
  multi-sector run (MAST bulk downloads), and the QLP TCE and
  faint-star search lists where public
- Any match by TIC ID, and any match by coordinates within 21 arcsec
  (one TESS pixel) raised as a flag, since a blended neighbour TOI is
  the most common way a "new" candidate turns out to be known

Cache each catalog to disk with a 7-day refresh and a version stamp in
the target manifest. A catalog fetch failure must fail the run loudly,
never degrade to "no match". Add tests for each source with recorded
fixtures.

### Part B: choose the population with a yield model, not a hunch

Bright 2-minute targets are exhausted. Write a short quantitative memo
(`docs/POPULATION.md`) comparing at least these strata:

1. Full-frame-image (FFI) stars Tmag 10.5 to 13.5 with 4 or more
   sectors (QLP and TESS-SPOC light curves) and no TOI, CTOI, or TCE match
2. Fainter FFI stars Tmag 13.5 to 15, especially M dwarfs, using
   QLP faint-star products, TESS-SPOC, or TGLC light curves
3. Multi-sector stitched searches for shallow, long-period, or
   duo-transit signals on stars whose single-sector searches were clean
4. Additional planets in known TOI systems (easy to find, lower
   value; include only as a fallback)

For each stratum estimate: how many targets exist after the hard-stop
filter (query the TIC via astroquery with a reproducible script), what
fraction of TESS-detectable planets prior pipelines are believed to
have already caught, and the expected number of NEW detectable signals
using published occurrence rates (Kunimoto and Matthews 2020, or
Dressing and Charbonneau 2015 for M dwarfs) times geometric transit
probability times a rough detection efficiency. State every input.

Pick ONE primary stratum and one fallback. Justify with the numbers.
Then generate `data/survey/targets_v1.csv`: TIC ID, RA, Dec, Tmag,
Teff, radius, contamination ratio, sectors available, light-curve
products available, cross-match status, and the catalog versions used.
Target size: whatever the yield model says gives an expected 2 to 5
new detectable signals, capped at roughly 20,000 stars.

### Acceptance

- Hard-stop cross-match rejects a hand-picked list of 20 known TOIs,
  20 CTOIs, 10 TESS EBs, and 10 TCE-only stars, and passes 20 clean stars.
- `targets_v1.csv` exists, is reproducible from a single script, and
  `docs/POPULATION.md` contains the yield model with all inputs.
- Suite green. Commit. Write `HANDOFF_P1.md`.

---------------------------------------------------------------------

## PROMPT 2: Survey-scale search engine with measured completeness

Read `HANDOFF_P1.md` and `docs/POPULATION.md` first. The population is
fixed; do not reopen it.

The pipeline currently takes up to 20 minutes per target on 2-minute
SPOC data and downloads target pixel files during search. That kills a
survey. This prompt makes it fast enough to run the whole population
and, more importantly, MEASURES what it can and cannot find on that
population.

### Part A: FFI ingestion and stitching

- `download.py` already ranks SPOC above TESS-SPOC above QLP. Make the
  QLP and TESS-SPOC path first-class for the chosen stratum: correct
  flux column per product (QLP `KSPSAP_FLUX` versus `SAP_FLUX`,
  TESS-SPOC PDCSAP), quality masks per author, per-sector
  normalisation, and stitching that does not manufacture edge dips.
  If the population uses TGLC or QLP faint products, add those readers.
- Stitch all available sectors per target and search the stitched
  curve. Long-period and duo-transit signals only exist in the stitch.

### Part B: speed

Target: median 1 to 2 minutes per target, worst case under 5, with no
sensitivity loss on the benchmark. Levers in expected order of value:
period grid sized to the FFI cadence and baseline (not the 2-minute
grid), binning before BLS, no target-pixel or centroid work during
search (defer to survivors), cached stitched curves on disk, and a
checkpointed batch orchestrator with `--resume` that survives process
kills (this desktop has had unexplained process-tree kills before).
Run at 15 to 20 concurrency.

Prove no sensitivity loss: rerun the frozen dev and holdout benchmarks
via `score_any.py` and show recovered, alias, missed, and FP counts are
equal or better than the `IMPROVEMENT_REPORT.md` numbers. If a speed
lever costs a recovery, drop the lever and say so.

### Part C: completeness on the REAL population

This is the deliverable that makes any later candidate believable.
Take a random 300-star sample from `targets_v1.csv`. Inject
limb-darkened transits (batman) across a grid of period (1 to 40 d),
radius ratio, and impact parameter, at least 2,000 injections. Run the
full search. Produce a completeness map (`docs/COMPLETENESS.md` plus
a figure) and a false-alarm rate from the same 300 stars searched
without injections. Record the SNR at which recovery crosses 50
percent and 90 percent. These numbers get quoted in the packet.

### Acceptance

- Benchmark scores equal or better than before, shown side by side.
- Median per-target wall clock under 2 minutes on 100 real population
  stars, with the timing table in the handoff.
- Completeness map and false-alarm rate exist with sample sizes.
- Orchestrator resume tested by killing it mid-run.
- Suite green. Commit. Write `HANDOFF_P2.md`.

---------------------------------------------------------------------

## PROMPT 3: Submission-grade vetting

Read `HANDOFF_P1.md`, `HANDOFF_P2.md`, and `IMPROVEMENT_REPORT.md`
section 4. This prompt turns "the BLS says so" into the artifacts the
TESS TOI team looks for, and closes the known weaknesses that produce
embarrassing candidates.

### Part A: physical transit fit

Replace the flat-bottom depth estimator (weakness 3) with a proper
limb-darkened transit fit (batman, quadratic coefficients from Claret
tables by Teff and logg) using MCMC or at least a bounded
least-squares fit with uncertainties on period, epoch, duration,
depth, Rp/Rs, impact parameter, and a/R*. Report Rp in Earth and
Jupiter radii using the TIC stellar radius and its uncertainty.
Compare fitted a/R* to the value implied by stellar density; a large
disagreement is a strong eclipsing-binary or blend indicator and
becomes a vetting flag.

### Part B: false-positive probability

Integrate TRICERATOPS. For each survivor compute the false-positive
probability (FPP) and nearby-false-positive probability using the real
Gaia neighbours. Keep raw outputs. A candidate with FPP above 0.5 does
not proceed to a packet.

### Part C: close the weaknesses that matter for submission

From `IMPROVEMENT_REPORT.md` section 4, address in this order:

1. Weaknesses 4 and 5 (secondary-eclipse exemption, alias resolver
   halving EB periods): build the period-aware secondary test the
   report describes (the secondary an irradiated planet could produce
   at the fitted a/R*), and make the alias resolver test both P and 2P
   for odd-even depth difference with the new fit before choosing.
2. Weakness 1 (exclusion zone anchored on a false positive): a
   candidate whose fit implies Rp/Rs above 0.2, or a/R* inconsistent
   with the star, may not carve an exclusion zone.
3. Weakness 2 (gate 7): require the second condition the report
   proposes.

Every change is measured against the frozen benchmark and must not
lose a recovery.

### Part D: the packet

Extend `reporting.py` to produce a one-page data-validation style
summary per survivor: full light curve with transits marked, folded
curve with fit, odd-even overlay, secondary-eclipse window, per-sector
folds, centroid offset plot, nearby stars within 1 arcmin with Gaia
magnitudes and the TIC contamination ratio, fitted parameters with
uncertainties, FPP, completeness at this SNR from `COMPLETENESS.md`,
and the cross-match result with catalog versions. Also emit a
`ctoi_fields.json` with exactly the fields the ExoFOP CTOI form asks
for (TIC, period, epoch, duration, depth, notes, tag) so the human can
fill the form without transcription.

### Part E: adversarial check

Run the full vetting stack on: 15 known TOIs that are planets, 15
known TESS EBs, and 10 known blended false positives from ExoFOP
(disposition FP with reason). Report the confusion matrix. If more
than 2 EBs or blends reach "promising", stop and fix before finishing.

### Acceptance

- Benchmark unchanged or better. Confusion matrix in the handoff.
- A full packet generated for one known TOI as a demonstration.
- Suite green. Commit. Write `HANDOFF_P3.md`.

---------------------------------------------------------------------

## PROMPT 4: Run the survey and build the candidate packets

Read all three handoffs. Nothing in detection or vetting changes in
this prompt unless the run exposes a crash. This is execution and
triage.

1. Run the full `targets_v1.csv` population through the orchestrator
   at 15 to 20 concurrency with checkpoints. Expect roughly 10 to 30
   hours. Log per-target timing, product used, sectors used, and any
   fallback events. Any target that errors is retried once, then
   listed in the handoff.
2. Rank every signal that survives the automated gates by a single
   frozen score (SNR, number of transits, FPP, and consistency of
   fitted a/R* with the star). Write the score down before the run
   finishes and do not tune it after seeing results.
3. Re-run the hard-stop cross-match on every survivor with freshly
   downloaded catalogs. New TOIs appear weekly.
4. For the top 30 survivors run the deferred expensive steps: centroid
   from target pixel files across all sectors, TRICERATOPS with real
   neighbours, and the full packet.
5. Produce `docs/SURVEY_RESULTS.md`: number of targets searched,
   number of signals, number after each gate, the ranked table of
   survivors with the key numbers, and a plain statement of the
   false-alarm expectation from `COMPLETENESS.md` for this population
   size, so the reader knows how many of these are expected to be noise.
6. For each of the top 10, write a half-page case file: why it is
   likely real, what would kill it, and what follow-up would settle
   it (ground photometry, radial velocity, high-resolution imaging).

Do not submit anything. Do not rank by how exciting a planet would be.

### Acceptance

- The full population ran, or the handoff explains exactly which
  targets did not and why.
- Packets and case files exist for the top 10.
- Commit. Write `HANDOFF_P4.md`.

---------------------------------------------------------------------

## PROMPT 5: Independent audit, then go or no-go

Read `HANDOFF_P4.md` and `docs/SURVEY_RESULTS.md`. Your job is to try
to kill the top 10 candidates. You are not the team that found them.
Assume each one is a false positive until you fail to prove it.

For each candidate, independently:

1. Re-download the light curves from MAST with a fresh cache and
   re-detect the signal with a DIFFERENT method: Transit Least Squares
   (the `transitleastsquares` package) on your own detrending (wotan
   biweight). If TLS on a different detrend does not find the same
   period within 1 percent, the candidate is downgraded.
2. Re-examine the raw SAP flux, not the corrected flux, for each
   individual transit event. Any event that coincides with a momentum
   dump, a sector edge, a scattered-light ramp, or a quality-flagged
   cadence is removed and the SNR recomputed without it.
3. Check every individual transit for depth consistency; a signal
   carried by one deep event is a downgrade.
4. Search Gaia DR3 for neighbours within 1 arcmin, check RUWE and
   Gaia variability flags on the target, and search SIMBAD and VSX
   for known variability or binarity. Check whether any neighbour
   could produce the depth when diluted.
5. Re-run the hard-stop cross-match one more time with fresh catalogs.
6. Read the previous prompt's case file last, and state where you
   agree and disagree.

Output `docs/AUDIT.md` with, per candidate, a verdict of SUBMIT,
HOLD (state what would change the verdict), or KILL (state the
reason). Then a final section: the ordered list to submit, with the
filled `ctoi_fields.json` for each and a two-sentence note the human
can paste into the ExoFOP notes field.

If nothing survives, say so plainly and list the three most valuable
changes to the population or the pipeline for a second survey pass.
A clean null result is a legitimate outcome of this prompt.

### Acceptance

- Every top-10 candidate has an independent TLS re-detection result
  recorded, pass or fail.
- `docs/AUDIT.md` exists with verdicts and reasons.
- Commit. Write `HANDOFF_P5.md`.

The human then reads `AUDIT.md`, opens every packet, and submits
only the SUBMIT verdicts, by hand, on exofop.ipac.caltech.edu.
