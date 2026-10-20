# Scoring implementation notes

Primary positive/negative recovery uses the fixed candidate-choice and ephemeris
rules in PREREGISTRATION.md. No threshold variant is evaluated. Additional negative
family tables follow every exact or registered alias match, reporting whether any
of those matching signals survives. Unrelated signals on the host are excluded.
The alias diagnostics retain the registered >=50% event fractions; factors three
therefore usually fail that conservative event rule even when their periods match.
They are not silently credited using a weaker phase-only test.

`scoring.py --locked-only` permits diagnostics for settled, individually hashed
hosts while other controls are running. It skips every unlocked host and writes
separate `*_partial` files with the pending IDs. This implements the per-host lock
boundary in the protocol. Final scoring still refuses to proceed until every
selected host has an outcome lock. Partial tables are not final performance estimates.
Truth-informed diagnostics run in separate directories and cannot update blind
outputs. Manual adjudication remains explicitly unblinded.

Operational settlement additionally requires a completed operation receipt or both
registered failed attempts. A missing native JSON after exhausted attempts can be
locked and scored as unavailable; it cannot disappear from the denominator. This
checkpoint handling was implemented while remaining stages ran; no such exhausted
failure had occurred at implementation. It changes no scientific gate or rerun rule.

Depth stratification uses <1000, 1000–5000 and >=5000 ppm. These display cutpoints
were specified during implementation after some individually locked hosts had been
scored, so the depth table is exploratory. Continuous depths are retained. All
preregistered radius, period and SNR cutpoints are unchanged.

While the primary A batch ran, `dispatch.py` was added to advance completed hosts
through S/B/C/D without waiting for unrelated hosts. It reads blind predecessor
records and operation receipts, recognizes already running jobs, and retains the
registered limits (four shared S/B workers, two C workers, two D workers, alongside
the existing maximum four A workers). This is scheduling code only; `runner.py`
remains byte-identical to the final-sampling freeze. Dispatcher events and its code
hash are retained in `results/dispatch_status.json`. Competing new batches must not
be launched while the dispatcher is active.

The optional native fixed-aperture review failed with `Insufficient aperture or
background pixels` for TICs 243641947 and 102734241 after their native difference
images, centroid and FPP measurements completed. `aperture_review.py` adds error
reporting per sector and preserves the extractor and its sixteen-clean-sky-pixel
requirement. It records unavailable measurements rather than relaxing the mask.
This repairs the presentation wrapper, not the scientific measurement. The failed
attempts and successful difference images remain documented. Final review may use
the existing pixel evidence but must explicitly assess whether it supports a
defensible transit/source HOLD; the published label cannot fill missing evidence.

The same fixed-annulus limitation also affected TIC 389900760. Its sector 85 had
available pixels but a zero reported centroid error, so the native weighted
centroid combination omitted it. The initial pixel presentation followed only
`sectors_used` and omitted this otherwise available sector. Before that host's
verdict or truth score, preserve the three-sector images in `reviews/pixel_history/`
and repair the presentation to review **all available pixel sectors**, including
ones excluded from centroid averaging. The original native centroid measurement
is unchanged and its zero-error entry is not treated as a precise no-motion result.
The four already adjudicated hosts had no such omitted sector, as recorded in
`reviews/pixel_sector_coverage_audit.json`; their locked outputs remain unchanged.
The previous pixel adapter is archived in `baseline/adapters/`.

Operational-unknown tables implement the preregistered distinction between
intention-to-run and completed-only results. The observed survival count is a
lower endpoint when a path has timed out or failed. Logical upper endpoints allow
those unresolved paths to survive; Wilson and host-bootstrap envelopes span both
endpoints. Negative alias families inherit an unresolved stage from any matching
path, without relabelling unrelated host signals. Both exact and family
completed-only negative cohorts are separate. The synthetic timeout unit test
checks this distinction. No failed execution is counted as a measured scientific
rejection, and ordinary observed-count intervals must not be interpreted as full
scientific-efficiency intervals when an operationally unresolved path exists.

`pixel_pages.py` paginates saved native difference-image arrays for long-sector
reviews, using the same reference normalization, symmetric difference scale and
Gaia markers as the archived pixel plotting code. Each page covers at most three
sectors and has a receipt linking the unchanged native arrays and metadata.
This is a presentation step before adjudication/lock, not a new extraction,
localization measurement, altered image contrast rule or scientific gate.
`aperture_pages.py` similarly paginates saved target-aperture/background arrays
and explicit unavailable-sector panels using the existing sampling, binning and
axis-limit rules. Full original figures and numerical source hashes are retained.

After individually locked negatives exposed near-period candidates with failed
event alignment, `negative_audit.py` was added as a post-lock diagnostic. It
shows event fractions and larger integer harmonic proximity without changing
the registered primary match. A separate union over every accepted candidate
on each negative-control host supplies a conservative upper bound on possible
labelled-signal escape, including operationally unresolved paths. Unrelated
candidates retain unknown truth; they are not relabelled as false positives.
This sensitivity/identification check is not a tuned gate, additional primary
cohort or evidence of perfect specificity.

That audit also recovers period/epoch error columns from the frozen MAST EB
catalogue, which the original negative truth-manifest builder had omitted.
These errors are propagated only in the post-lock diagnostic using independent
period/epoch errors, with no covariance or eclipse-timing-variation model.
The nominal truth manifest, eligibility, primary match and verdicts remain
unchanged. The omission and resulting timing limitations are explicit in the
negative audit; the extra columns never enter execution.

Inspection of the locked LP 791-18 b search miss exposed a diagnostic-reader
column error: `autopsies.py` looked for `period` in saved BLS rows, which actually
use `period_days`. The blind trace had recorded the rows correctly throughout.
The derived pre-repair cards are preserved in `results/diagnostic_history/`.
The reader now uses the native period/epoch/duration/depth columns, records JSONL
line numbers and regenerates every positive card consistently. Search outputs,
locks, primary match scoring and all verdicts are unchanged. The trace event name
`broad_bls` includes both broad and refinement calls intercepted by the wrapper;
the cards therefore call them BLS/refinement rows, not distinct search detections.

`failure_figures.py` was added after TOI-1470 c's host lock to present saved native
C periodograms for positive paths terminated at C. It uses the original spectrum,
blind survey seed, peak rank and threshold, with source hashes. No second planet
is masked, no TLS is rerun and no failed candidate advances to D. Truth names are
post-lock plot labels only; the figure and narrative do not alter recovery.

After HIP 97166 b's locked C failure, `spectrum_audit.py` measures the contribution
of each saved native power ordinate to the spectrum's variance for every locked
C spectrum. It archives the installed TLS statistic implementation. This is a
descriptive decomposition: no ordinate is removed, no alternative SDE or pass
is computed, and no failed path advances. The raw trial chi-square residuals
were not saved, limiting diagnosis of the upstream cause. C autopsy tags now
distinguish an SDE-threshold failure from strongest-period disagreement using
the existing recorded threshold and match fields. Primary outcomes are unchanged.
