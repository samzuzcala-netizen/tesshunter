# Prompt 10.3 preregistration

Registered 2026-09-14 before any Part 3 population calculation, acquisition,
blind search, matching, forced fit or funnel measurement. The supplied
`PROMPT_P10_3.md` is the execution specification; its exact bytes and SHA256 are
preserved by the registration receipt. Historical outcomes are prior evidence,
not new results. No scientific threshold is retuned.

## Assumptions and adopted rules [A]

### Population and inputs

Reproduce the incumbent domain on the 117,171-row pool: Teff < 3600 K,
rad < 0.45 solar radii, 12.5 <= Tmag <= 14.0, abs(gallat) >= 20 degrees,
n_sectors_200s >= 3 and the pool n_sectors_2min_in_search < n_sectors_200s/2.
Select only REJECT with xmatch_tic_sources exactly spoc_tce. Expected original
population: 531; the exact identity manifest retains every exclusion.
Sequential input cuts are Gaia dwarf pass, corrected strict minority of
two-minute sectors intersecting delivered FFI sectors, and >= 3 verified usable
sectors. Input failures are INPUT_INELIGIBLE, never scientific misses.

Freeze sectors 56 through 105 inclusive, author preference SPOC, TESS-SPOC,
QLP. Exclude QLP 80, 83, 85 and 99 through 104. No exceptions are sought in this
run. QLP 74 through 79 requires saved corrected-v02 source comparison. Every
used raw product must have exact TIME, flux, SAP and quality identity against
its FITS source; no transit-based timing correction. Prepared series use the
unchanged native 200-second P10 ingestion and quality policy. Mixed cadence
is not stitched. Products outside the frozen window do not enter the search.

The ephemeris sidecar carries all raw rows for all pool TICs, preserving run
duplicates. Required raw header columns: tceid, ticid, tce_plnt_num, sectors,
tce_period, tce_period_err, tce_time0bt, tce_time0bt_err, tce_duration,
tce_duration_err, tce_depth, tce_depth_err, tce_model_snr, tce_num_transits,
tce_ntoi, plus source filename. Period/epoch units are days/BTJD, duration is
hours and depth is ppm; source headers are checked before conversion. Existing
normalized catalogue files and digests stay byte-identical. TCE runs ending
at sector <= 55 are INDEPENDENT; runs containing any sector >= 56 are
OVERLAPPING. Every retention table reports each stratum and the union.

The separately selected hard_stop_p10 maps a TIC match only in spoc_tce to
FLAG with ephemeris. Every other direct-source REJECT, promoted TOI/CTOI,
and the existing 21-arcsecond neighbour FLAG remains unchanged. The old
hard_stop function is untouched. No verdict function is run.

### Ordering, search and blinding

Seeds are NumPy PCG64 2026091401 for 10,000 paired whole-host bootstrap draws
and 2026091402 for engineering synthetic tests. Report percentile 95% intervals
(2.5%, 97.5%) on fractions; an empty denominator is unmeasured, never zero.
The nested development order uses SHA256 of
20260914:p10_3:development:<integer TIC> within Tmag bands [12.5,13),
[13,13.5),[13.5,14] crossed with usable-sector counts 3-5, 6-10, >10.
Weighted deficit round-robin assigns the next slot to the stratum furthest
below its population-proportional allocation, with lexical stratum tie-breaks.
Levels are all eligible, 400, 300, 200, without duplicate or oversized levels.

The timing pilot selects two stars from each native-point-count tercile by
SHA256 of 20260914:p10_3:timing:<TIC>, with TIC as the point-count tie-break.
Both survey_p10 and survey_p8 run on identical stitched inputs with traces.
No pilot outcome is opened to choose the evaluation size. Only timings, counts,
operational statuses and Stage A timing are used for the forecast. Forecasts
use distributions, the historical tails, production worker layout and a 25%
margin. Historical search median/p90/max are 444/1284/1682 seconds; Stage A
median/p90 are 100/517 seconds. C uses the 3.4-hour tail. Freeze the largest
affordable level before outcome access. Declare the paired P8 cut before its
launch; P8 is the first optional allocation removed.

Keep survey_p10, its 2700-second detector budget, survey_p8, p10.0 bound S,
strongest-peak C with conditional robust fallback, and one-cadence duration
floor unchanged. Search deadline is 3600 seconds per star/preset with one
attempt. Timed-out searches are OPERATIONAL_UNKNOWN and are not retried for
an outcome. Detector budget exhaustion is recorded even when status is ok.
Prediction manifests include every accepted period, epoch, duration, depth,
stitch SNR, partition and budget flag, and are locked per preset before Part F.
Search workers record opened file paths and fail if the sidecar is opened.
Ephemerides are used only for upstream input census and subsequent Part F;
they are never supplied to a blind search worker.

### Matching, forced fits and calibration

Exact matches have relative period error < 0.01. Aliases at 2, 3, 1/2 and
1/3 count as recovered associations but are reported separately from exact
matches. The extra 3/2 and 2/3 ratios present in the legacy helper are not
adopted: the current prompt explicitly enumerates four aliases. Epoch is
checked only when sigma_P * abs((data_midpoint - TCE_epoch)/TCE_period)
< T14/2; a checked match also needs propagated modulo-period agreement
within T14/2. Noncheckable matches are labelled period-only.

Within a host, sort by period and stable source/row identity; each new family
uses the lowest unassigned period as its anchor, grouping subsequent periods
within 1% of that anchor. No transitive chaining beyond the 1% anchor tolerance.
Report raw rows as well as families. A stratum's family has members from that
stratum; the union deduplicates cross-stratum families once. Representative
ephemerides are chosen by highest model SNR, then source filename and row ID,
before outcomes; no outcome-based representative is chosen. The likely-periodic
subset requires a member with model SNR >= 12 and >= 3 transits.

Expected SNR = (depth/sigma) * sqrt(n_cad * T14/P), with consistently converted
depth/noise and duration/period units and measured prepared-data per-cadence
noise. TCE model SNR bins are <9, [9,12), [12,20), >=20. Expected SNR bins are
[0,7), [7,10), [10,15), [15,20), [20,30), >=30. Period bands are [0.5,1),
[1,2), [2,5), [5,10), [10,20), [20,30], >30; periods <0.5 are also reported
outside domain. Out-of-domain TCEs never count as search misses.

Only after both prediction locks, every evaluated family gets a forced box fit
at its representative period in prepared sector-56-and-later data, with duration
floored at one cadence. Fix phase when epoch is checkable, otherwise optimize
phase. Positive fitted depth >= 3 times its positive finite standard error is
present; smaller measured depths are absent. Failed fits are operational
unknowns. Report recovered/missed versus present/absent separately by stratum.
The present-and-missed cell measures retention loss; an absent signal is not
a pipeline miss. Period recovery of an eclipsing binary is a valid periodic
signal recovery; its funnel rejection is not called a planet loss.

For INDEPENDENT, likely-periodic, in-band, forced-present families, fit the
historical logistic form sigmoid(a + b*log(SNR)) for each preset. Compare
SNR50 to 11.58 for survey_p10 and 13.15 for survey_p8. A value strictly > 1.30
times the corresponding baseline fires the optimistic-calibration rule. Fewer
than 40 qualifying families means diagnostic only and rule not powered.
Report host-bootstrap SNR50 intervals and unidentified fits explicitly.
If the rule fires, autopsy the five highest-expected-SNR present misses using
event-removal census, ranking witnesses, aliases and budget flags. One mechanism
in >=3/5 permits at most one p10.1 iteration only if remaining measured budget
covers (13.75 hours + the Part E rerun forecast)*1.25. Otherwise provide an exact
costed next step; no locked prediction changes.

### Funnel and resources

Route every survey_p10 accepted candidate through collect and pre-gate, and each
survivor sequentially through A, bound S and B with the unchanged p10.0 rules.
The isolated adapter uses p10/protocol/p10_funnel_calibration.py with all roots
redirected to data/survey/p10/part3/funnel. Stage A deadline 1200 seconds,
S/B 300 seconds each, one attempt; operational failures remain unknown.
No TCE filtering occurs before B. Report sequential retention, A criteria and
S modes, natural candidate load per host and unknowns at each stage, alongside
the historical injection comparison at the same expected SNR. The historical
accepted/pre-gate/A/S load is 11.65/2.36/0.150/0.0067 per control star.

C is only for TCE-matched likely-periodic B survivors in descending expected
SNR, with N_C fixed from remaining budget before launch using 3.4 hours per
run and at most three concurrent top-level processes. Report excluded C work
and unmatched B survivors. No D, verdict tiers, packets, CTOI fields, submissions,
push, repack, full survey or unconditional injection rerun. A carried record
is unverdicted and carries its F7 SPOC run/planet-number/period association.

Maximum new union scientific-job time: 31.98 hours, including failed attempts
and stalls, cumulatively within 48 hours with the P11/P11.5 carry of 16.0198
hours. Cumulative acquisition cap: 15,000,000,000 bytes; prior used 85,401,427.
Disk floor C: 25,000,000,000 bytes. Forecast acquisition from first 50 stars.
If necessary relocate only the regenerable TESScut cache to the specified D:
path, record counts/bytes and leave a junction. No historical deletion.
Maximum 24 active cores, single-thread BLAS; maximum four download workers,
one lightcurve search per star. One owner per phase, bound by PID, creation
time and command. Never edit worker-loaded code while that owner is alive.

Phases forecast over 30 minutes use detached owners with per-case checkpoints
and progress.json. Exactly one 60-minute check-in routine, one early check at
about 10 minutes, and a shortened final interval only when completion is forecast
within the hour. Check-ins read only progress, process identity, last 50 log
lines, disk and worker CPU deltas, and write dated resume and JSONL receipts.
No per-case science reads or recalculation at routine check-ins. Stop/action
triggers: owner gone without closure, stalled worker CPU, disk within 3 GB of
floor, rising errors, or a stop rule. Mechanical phase transitions require
owner/disk/budget/hash preflight. Level/P8 allocation, N_C, Part H, every stop
and final delivery return to the main session for recorded decisions. The old
two-hour P10 heartbeat remains paused. At endpoint verify all owners closed
and the new routine disabled before final decision.

STOP-1: after D, fewer than 60 INDEPENDENT likely-periodic in-band eligible
families. STOP-2: storage floor cannot be restored by permitted relocation.
STOP-3: pilot forecast for 200 stars, P10 only, N_C=0 exceeds remaining budget.
STOP-4: changed historical seal or sidecar access by a search worker. Stop,
restore an owned accidental change if applicable, and report without changing
unknowns into misses. Final state is INPUT_LIMITED if a stop occurs before paired
search completion, otherwise RETENTION_MEASURED or
RETENTION_MEASURED_CALIBRATION_OPTIMISTIC as the Part H rule determines.

## Amendments from HANDOFF_P10.md 0.6 [A]

| Amendment | Reason |
|---|---|
| Standalone authorization and cumulative remaining budgets | P10 previously stopped at Part 2d; this prompt independently authorizes only the bounded experiment. |
| Frozen QLP sector exclusions and source identity | Carry the P11 input audit into this timing-sensitive measurement. |
| INDEPENDENT/OVERLAPPING strata | Separate prior-epoch information from same-epoch pipeline comparison. |
| Part G early funnel through B | Adds real-signal sequential retention and natural-load measurement. |
| Prospective C cap | Bounds the expensive tail; never changes C thresholds. |
| Conditional, budgeted p10.1 iteration | No iteration is run without its registered remaining-cost test. |
| Nested size and timing pilot; one-attempt operational accounting | Make the standalone allocation prospectively bounded and auditable. |
| Power stop >=60 and interpretation minimum >=40 | Explicit rules in the current prompt. |
| Isolated catalogue adapter | src/tesshunter/catalog_crossmatch.py is in the historical P11 source seal. Add the P10 parser and named rule in Part 3, install them explicitly into that module's process namespace, and preserve sealed bytes. |
| Correct MIT cache directory to data/survey/cache/twomin_lists | File-level inspection and p9/data_prepare.py show sNNN.npy here; target_lists contains FFI lists and no sNNN.npy files. The algorithm is unchanged. |
| Redirect integrity receipts into Part 3 | Both named legacy verification entry points otherwise write into sealed historical directories. |
| Restrict aliases to current prompt's explicit four ratios | Legacy _match additionally contains 3:2 and 2:3; those were not enumerated here. |
| Specify 95% intervals, family anchor and deterministic tie-breaks | Computational conventions absent from section 0.6, fixed before measurement. |

## Evidence and delivery contract

Use [M] only for measurements in this run, [Pn] for historical evidence,
[A] for adopted choices and [I] for interpretations. Every report has a separate
assumptions section. Deliver original/input-eligible/evaluated populations,
exact missing measurements, costs, seals and local commits. The 531 are marked
development-exposed from Part F and can never be a holdout afterwards.
Carry forward the unretuned TOI-762 A b / TOI-122 b rejection risks and
TIC 144277542 rescoring change. Nothing supports an endpoint claim or a Part 5
survey authorization. Commit explicit new files locally on improve/recovery
with prompt 10.3 in each phase message.

## Dated acquisition amendments D1-D4 [A]

Registered by the user's authorized Claude session before its acquisition launches on 2026-09-14; incorporated into this table at 2026-09-15T02:51:31.134294+00:00, after acquisition and before any Part E search. This incorporation does not claim a new prospective registration date. The original preregistration bytes are preserved in `manifests/PREREGISTRATION_P10_3.original.md`; the original registration seal is unchanged. The amendment-chain receipt pins both that original and this effective document.

| Id | Adopted amendment | Reason and provenance |
|---|---|---|
| D1 | Acquire only sectors 56-105 using `download_star_v2.py`; preserve v1 and all pilot receipts. | The measured sector-27 superset forecast exceeded the acquisition cap. The frozen science window and quality exclusions are unchanged. |
| D2 | Download deadline 600 s, passed as a controller CLI argument; original config retained. | Healthy pilot stars took 12-94 s; longer transport stalls consumed budget without adding information. |
| D3 | One recorded transport/product-failure retry, at most two acquisition attempts per star; force re-index preserves old/new index hashes. | Transport and input failures are operational events. The builder covered v2 batches; three pilot product failures used the separately recorded `download_v2_retry_pilot_plan.json`. No scientific outcome retry is authorized. |
| D4 | Fixed ascending-TIC batches of 100 for the remaining acquisition. | Bounded storage and transfer checkpoints without TCE ranking. |

The full amendment wording and nine prelaunch source/plan hashes remain in `AMENDMENTS_D1_D4_20260914.md`. Its supervision wording differs from this run's registered cadence; going forward the original hourly cadence governs, with only the specified early and final exceptions. The eight external-session checks are retained and accounted for.

The user also explicitly authorized the completed environment-only Git maintenance and relocation of both `stitched` and `lightkurve/tesscut` behind junctions. The original prompt named only TESScut. Record the stitched relocation as an additional user-authorized storage action, without broadening permission to move sealed evidence. Both relocation receipts are preserved.
