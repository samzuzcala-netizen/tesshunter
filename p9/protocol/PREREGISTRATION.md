# P9 external validation protocol, version 1

Written before any P9 search or vetting outcome. Baseline: the exact Git commit in
`../baseline/commit.txt`; an archived copy of implementation, configuration and
dependency versions is hashed in `../baseline/`. P8 and pre-existing follow-ups
are historical evidence and will not be edited. No external submission is allowed.

## Estimand and sampling

The primary estimand is correct-signal retention under `survey_p8` and `p8.0`,
including the actual pre-gate and all permitted downstream stages. A known object
has zero discovery/submission eligibility; scientific SUBMIT-equivalent is separate.

The frame uses the fetched NASA PS default transiting-planet rows (controversy flag
zero), ExoFOP TOIs/CTOIs, and the independently curated MAST TESS EB catalogue.
Period 0.5–30 d, duration 0.48–4.8 h, at least three delivered FFI sectors from
the same 56–105 target-list coverage inventory as P8. Broad positive frame:
stellar radius <=1 Rsun, Teff <=6000 K, Tmag <=14.5. These stellar bounds define
the scope of this study, not a claim that the production search cannot run elsewhere.
Missing timing/duration and controversial labels are tabulated outside the frame.
TOI PCs and FP labels without independently verified subtype remain uncertain.
The EB catalogue supports binary-signal truth, not necessarily localization on
the named TIC; that distinction remains in the results. No instrumental negative
control will be relabelled from a pipeline rejection.

Sampling is by HOST with seed 20260907 and SHA256-derived order, before downloads
or outcomes. All 13 hosts in the catalogue-based P8 proxy cell are prioritized
(Teff <3600, Rstar <0.45, Tmag 12.5–14, minority 2-minute coverage). This is a
census of that frame cell, not an arbitrary easy-planet sample. Other disjoint
positive strata are 1–4 Re / P>=10 d, 1–4 Re / P<10 d, and other radii. Host
assignment priority follows that order; all frame-eligible planets on selected
hosts enter the truth manifest. Within these cells no SNR/recovery-based selection.
Strict P8 overlap additionally uses ordinary TIC stellar data, Galactic latitude,
Gaia dwarf criterion and actual selected products; it is reported separately.

The runtime pilot consists of the first two P8-proxy hosts and the first host
of small-long, small-short, detached-EB and uncertain-PC strata. These are baseline
controls, not tuning controls. Their outcomes are locked without scoring.
The final sample is selected ONLY from runtime measurements: default quotas are
all P8 proxies + 6 small-long + 6 small-short + 3 other-positive hosts,
6 detached EB + 6 contact EB + 4 uncertain PC. If median completed search+A cost
per pilot host exceeds 1800 s, or a pilot C job exceeds 7200 s, reduce the three
non-proxy positive quotas to 3,3,2 and EB quotas to 4,4; uncertain stays four.
If no pilot C is eligible the C runtime condition is unavailable, not zero.
The resulting ~22–35 positive signals gives about ±17–21 percentage points at
worst-case 95% binomial precision before clustering. This is a diagnostic study;
small cells cannot support precision claims. No outcome-based expansion/replacement.

Before search, raw timestamps and truth ephemerides determine >=3 observed
opportunities using >=50% in-window exposure coverage and >=10 local baseline
cadences. Missing data, insufficient opportunities, and ephemeris uncertainty
are separate flags. Missing downloads are not quiet exclusions: every selected
host has a preparation receipt. No control is removed because it fails a gate.

## Isolation, execution, gates and operational policy

Preparation can read truth. Execution receives only TIC IDs, whitelisted ordinary
TIC stellar fields, selected raw products and permitted neighbour measurements.
No published timing, planet radius, name, disposition, old packet, known-period
seed or historical candidate result is permitted. Packet directories start empty.
The original catalogue check is performed in preparation and its full outcome
is saved on the truth side. Execution receives only whether exclusion was bypassed;
known status never supplies a scientific pass. Positions, brightness, crowding,
astrometric anomalies, generic variability and source counts remain available.
Answer-bearing catalogue names, classification labels and orbital solutions are
redacted from review inputs, with a field-level log; generic flags remain unchanged.
Automated execution is ephemeris-blind. This investigating session has read truth
labels and historical examples, so any manual adjudication is explicitly UNBLINDED.
This is a process/input boundary, not an OS-security sandbox against a malicious runner.

Use frozen search -> pre-gate -> A -> secondary -> B -> C -> D in that order.
Run ALL accepted signals, not just truth matches; preserve all measurements.
Production native 200-second harmonization, product preference SPOC > TESS-SPOC >
QLP, sector_min=56, search configuration and scientific thresholds are unchanged.
Stage C spans 0.5–110 d at oversampling 3 and checks its strongest peak. No
counterfactual stage run enters primary counts. Forced/narrow TLS in A is allowed
only around the blind search period, exactly as in production.

Up to four independent preparation downloads; search/A up to four processes,
TLS only in top-level subprocesses, one internal thread for A and eight for C,
at most two C processes. Set numerical-library threads to one and record seeds.
Outer execution limits: search 1800 s; A per signal 3600 s; S/B 900 s; C per signal
36000 s; D per signal 14400 s. These are operational safeguards, not scientific
rejections. One retry for execution exceptions/data failures, with the same
inputs. Do not retry a scientific FAIL. Every interrupted attempt remains logged.
Runtime budget stops inside the unchanged search count as measured sensitivity.
Repairs are versioned; rerun all affected controls consistently before locking.

D requires the accepted-C-ephemeris all-transit physical fit, FPP with 100000 draws,
native pixel/centroid/source assessment and a final review. Provisional `SUBMIT`
from `revet_p6` alone is not final scientific SUBMIT-equivalent. Preserve Stage B
HOLD caps, fit uncertainty flags, FPP limitations and unresolved source evidence.
KILL requires measured contrary evidence; missing tools/data/timeout is operational
incomplete. A legitimate useful HOLD requires a recovered coherent transit with
no demonstrated nonplanetary cause and a specific resolvable limitation such as
uncertain geometry or source. Generic unresolved status, high FPP without a
defensible localized transit, or an execution failure is not successful retention.

## Locking and scoring

Each host's blind search, stage measurements, final verdicts and file hashes are
locked before a scoring process opens truth. The final selected manifests and
protocol/code hashes are saved before nonpilot execution. Host assignment to a
development/holdout flag is deterministic (25% development, 75% holdout); no
threshold tuning is planned. If any exploratory variant is measured, it must
report positive retention AND negative survival, and holdout is used only once.

Primary match: abs(Pfound/Ptruth - 1)<=0.01 AND a one-to-one transit-center
match within half the sum of fitted/truth durations at >=50% of truth opportunities
AND >=50% of predicted found opportunities in the selected timestamps. At least
three matched observed centers. This prevents a host-level artifact or another
planet being credited and penalizes period drift across long baselines. Choose
the candidate with most matched events, then least normalized timing residual,
then blind candidate number; never select using downstream survival. At each
gate also recheck the accepted ephemeris: switching signals stops correct recovery.
Ratios 1/2,2,1/3,3 (1% tolerance) are separately scored aliases and never credited
as exact primary recovery. EB half-period recovery is separately reported so a
binary's secondary eclipse does not masquerade as a different target.

Report direct unconditional and conditional nested counts at search, pre, A, S,
B, C and D (submit and useful) with denominators. Verify the conditional product
equals direct end-to-end completeness wherever all conditional denominators are
nonzero. 0/0 is undefined. Unavailable/timeout/error remains in an operational
completion table; intention-to-run lower bounds and completed-only counts are
distinct. Negative controls track their labelled binary signal at every gate;
unrelated surviving signals have unknown truth, not automatically false positives.

Use Wilson 95% intervals for marginal binomial counts and 5000 whole-host bootstrap
resamples within sampling strata, seed 20260907, for dependence-aware intervals.
For zero/complete samples bootstrap degeneracy is not certainty: also report a
conservative exact host-level bound and the number of independent hosts. Unweighted
sample results, strict P8 overlap, and broad proxy results are separate.
No multivariate fit; tabulate prespecified radius (1–2,2–4,other), period (0.5–10,
10–30), expected SNR (<12,12–20,20–50,>=50), duration, opportunities, Tmag, Teff,
radius, rotation/amplitude, correlated noise, crowding, cadence/products, sectors,
and TTV flags including missing values. Truth-informed SNR is post-lock diagnostic.
Weighting is permitted only with >=5 positive hosts per supported coarse cell,
both populations represented, weights <=5, and ESS>=10. Otherwise state unsupported.

## Comparisons, autopsies and yield

After scoring, compare P8 analytic injections only within overlapping SNR/period/
radius/stellar/product/coverage strata. Their existing calibration stops at S;
never infer B/C/D or pixel completeness from it. An unmatched comparison is
descriptive, not an estimate of analytic optimism. Optional paired injections
on selected noise hosts must carry their own preregistration and preserve exposure,
dilution and flux-column consistency. Do not transplant raw donor noise or claim
pixel validation from a changed light curve. If transplantation cannot be
validated, document the limitation and complete the real study.

Autopsy every missed/rejected positive after its lock, reporting first termination
separately from contributing causes, truth-period folds, transit opportunities,
timing/alias drift, event removals, S and C evidence. A diagnostic rescue never
replaces a blind result. Known ephemerides only enter these diagnostic files.

P8 early-S yield 8.087/11.675/14.924 under high/mid/low incumbent completeness is
historical model output, not final submissions. Apply only supported conditional
B/C/D efficiencies to this early yield, or rebuild with external end-to-end
efficiency from pre-detection counts; never stack both. Without supported overlap,
report scenarios/bounds (late retention 0,0.05,0.1,0.25,0.5,1), with Poisson zero
probabilities conditional on each scenario. Occurrence, geometry, novelty and
calibration uncertainty remain separate. Scenarios are not a calibrated posterior.
