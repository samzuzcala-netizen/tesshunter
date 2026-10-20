# PROMPT 10: the endpoint, the sensitivity, and the in-domain check

Run in a fresh session. Read first, in this order: `docs/AUDIT_P9.md`,
`HANDOFF_P9.md`, `docs/AUDIT_P8.md`, `HANDOFF_P8.md` (section 0 and
"Calibration and the decision to search"), the incumbent check at
`..\P9_SIDE_INCUMBENT_CHECKS_2026-09-07\INCUMBENT_CHECKS_P8_DOMAIN.md`
(outside the git tree until Part 0 moves it), `p9/protocol/PIPELINE_MAP.md`,
`docs/RULES.md` sections 0, 5 and 8, `PROMPT_P8.md` (its shared preamble and
nine gotchas all still bind), and the shared rules in `CTOI_PROMPTS.md`.

The pipeline finds candidates. Nothing in this prompt is a detection, a
discovery, or a confirmation. The agent never submits anything anywhere.

---------------------------------------------------------------------

## SHARED PREAMBLE (updated through prompt 9)

Environment facts, verified 2026-09-08:

- Repo: `C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter`
  (double-nested). Branch `improve/recovery`, HEAD `fbc68571` (prompt 8).
  Untracked and uncommitted: `HANDOFF_P9.md`, `docs/AUDIT_P9.md`,
  `docs/TIC404927114_FOLLOWUP.md`, `followups/`, `p9/`. Part 0 commits them
  before anything else is written.
- Python: `C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe`
  (3.13.3; exact package versions in `p9/baseline/environment.json`). The
  venv `python.exe` is a launcher plus a child interpreter: two processes per
  job with the same command line. `python` is not on PATH; use the full path.
- Before anything imports tesshunter set
  `LIGHTKURVE_CACHE=<repo>\data\cache\lightkurve` and `PYTHONIOENCODING=utf-8`.
  `TESSHUNTER_OFFLINE=1` (set by `tests/conftest.py`) stops TIC queries.
- First action of every session: `git status`, `pytest tests/ -q` (the P9
  baseline was 622 passed, 1 skipped; `p9/logs/baseline_pytest.log`), and
  `python p9/verify.py` (must report 397 passing checks and no pending hosts).
  Do not trust the previous handoff's claim that the tree is healthy. Measure
  it, and write the three numbers in the handoff.
- Machine: 24 cores. Disk on 2026-09-08: 120 GB free of 931 GB (88% used).
  The audit store already holds 58,267 products for the P8 stars. Check free
  space before the Part 3 download and write the number in the handoff.

Binding gotchas 1 to 9 are in `PROMPT_P8.md` and still apply (8 kB Bash
limit and heredoc breakage, MAST discipline, QLP bits, cadence mixing, TLS
from top-level slices only, the biweight depth ratio, gate 7, dips on
variable stars, checkpoints and `--resume`). Prompts 8 and 9 added these:

10. Stage C runtime tail: P8 C runs took 0.5 to 3.4 h each at 20 threads and
    one P9 primary C run exceeded 3 h [P9]. Budget C from these tails, one
    checkpoint per job, and never from the pilot median.
11. The search is wall-budget sensitive: identical inputs gave 6 and then 8
    accepted signals on TIC 177079323 across replays [P9]. Every search
    comparison in this prompt is paired on identical stitched inputs and
    records budget exhaustion per partition. An exhausted budget returns
    status `ok` [P8]; read the flag, not the status.
12. TLS reports sub-cadence durations (89.7 s at 200 s cadence on
    TOI-1450 A b) [P9]. Floor any reported duration at one cadence before it
    enters a matching or coverage rule; keep the raw value beside it.
13. TLS normalises its spectrum by the global standard deviation; one extreme
    negative ordinate carried 99.864% of the centred variance for
    HIP 97166 b [P9]. Every C run in this prompt saves the raw per-trial
    `chi2`, `SR` and `power_raw` arrays, not only the SDE.
14. The archive default ephemeris is not always the best transit predictor
    (TOI-849 b, 2.3 h off) [P9]. Truth ephemerides are chosen and their
    precision verified before any outcome is seen.
15. The P9 two-minute target-list parser missed `sNNN.npy` files [P9]. The
    corrected 50-sector inventory is under `p9/manifests`; use it, and never
    accept a zero count without a file-level check.
16. Per-sector fixed-aperture depths carry 0.7 to 1.6 ppt errors at
    Tmag 13 to 14 [P8]. A zero-error centroid entry is a missing measurement,
    not a measurement [P9]. Missing pixel evidence is never "no
    contamination".

Rules for this prompt, the shared six plus two:

1. Commit at the end on `improve/recovery` with a message naming prompt 10.
   Do not push unless told. Commit at the end of every part; this prompt is
   long and the desktop has had unexplained process-tree kills.
2. Write `HANDOFF_P10.md`: what shipped, what was measured (with sample
   sizes), what was refuted, what is still open. Evidence tags on every
   number: [M] measured this prompt, [Pn] taken from prompt n, [A] adopted.
   Assumptions in their own section, not in the results.
3. Never write "discovered", "planet found", or "confirmed".
4. The agent never submits to ExoFOP, MAST, or any external service.
5. If a lead is refuted by measurement, say so and do not build it.
6. Decision rules are written down before the measurement that they judge,
   and are not tuned after seeing the real candidates.
7. Every decision in this prompt has a pre-registered rule in
   `HANDOFF_P10.md` section 0 with its threshold written before the
   measurement runs. The thresholds given below are defaults. They may be
   changed only before the measurement, with the change and its reason
   written in section 0.
8. No real P8, P10 or Part 3 candidate is looked at while any rule is being
   decided. Development uses the injections, the P7 and P8 records that are
   already recorded and verdicted, the adversarial lists, the P9 development
   hosts, and the P9 hosts named in `docs/AUDIT_P9.md` (HIP 97166 b,
   TOI-1470 b/c, TOI-849 b, TOI-1450 A b, LP 791-18 b/c). Those five are
   development cases whatever their split label says.

---------------------------------------------------------------------

## Why this prompt exists

Three results, read together, say that the P8 zero is a property of the
pipeline and not of the sky:

- Novelty is refuted. In the 11,491-star P8 domain the incumbents and the
  community have claimed about 2 funnel-grade small planets against a
  modelled 79; QLP has alerted zero TOIs there [incumbent check]. With the
  claimed fraction near zero, the P8 early-funnel expectation is about 19,
  not 11.7.
- The frozen late stages give HOLD to validated planets. P9 put 31
  confirmed planets through the frozen funnel: 14 found by the search, 14 of
  14 through pre-gate, A, secondary and B, 11 of 14 through C, 0 of 11
  SUBMIT-equivalent [P9]. Stage B capped 18 of 18 candidates at HOLD, 17 of
  them through the 63-arcsec total-eclipse neighbour test, which also fires
  on 1,360 of 1,396 P8 hosts [P8, P9]. A test that fires on 97% of its
  inputs carries no information; its only effect is the cap. TOI-715 b,
  LP 791-18 c, TOI-4860 b and TOI-1680 b are HOLD under it. D then can kill
  (P8's four KILLs, with sign-flipping per-sector depths, are plausibly
  right) but cannot confirm a 3 to 4 ppt dip against 0.7 to 1.6 ppt
  per-sector aperture errors and background-dominated difference images.
  The reachable outputs are HOLD and KILL. The SUBMIT bar as written is a
  validation bar, which the field itself meets only with ground follow-up.
- Sensitivity is the largest yield loss. Injection SNR50 is 13.2 for the
  search alone, 14.7 through A and 20.2 through the secondary scan, against
  SPOC and QLP alert thresholds of 7.1 and 9 [P8]. Injected planets have no
  secondary eclipse, so every secondary rejection of an injection is a false
  kill by construction: 189 of 1,093 (17%) [P8]. On the real survey the
  scan removed 170 of 189 A passers [P8]. 745 of 2,000 search jobs exhausted
  their wall budget [P8]; LP 791-18 b passed every internal gate and lost
  its slot to a higher composite score [P9]; three C losses have specific
  mechanisms (strongest-peak competition, SDE normalisation, sub-cadence
  duration) [P9].

The arithmetic closes: at an early expectation of 19 the zero needs late
retention below roughly 10%, and P9 measured 0 of 11. So the order of work
is fixed by where the yield is lost: settle the endpoint, repair the
sensitivity on data already on disk, measure the repair in the actual P8
domain on the 531 stars the hard stop discarded, evaluate the frozen result
on held-out controls, and only then rerun the survey. Each step has a stop
rule. P9's transport limit stands: none of its numbers price a mechanism for
the P8 population, which is why Part 3 exists.

Two things this prompt does not do. It does not touch any P8 or P9 record;
they are the baseline every comparison is paired against. And it does not
treat a candidate-tier SUBMIT as a validation; the validation requirements
travel with every candidate as text.

The endpoint choice in Part 1 is the human's decision, adopted here as
written. If the human prefers to keep the validation bar, Part 1 becomes a
report-only re-derivation and Parts 2 to 4 stand unchanged; Part 5's
submission list is then expected to be empty and the product is the HOLD
list.

---------------------------------------------------------------------

## Part 0: housekeeping, baseline and the workspace

0a. Commit prompt 9 exactly as it stands (the five untracked paths above)
with a message naming prompt 9. Run `python p9/verify.py` before and after
and quote both counts. Then move
`..\P9_SIDE_INCUMBENT_CHECKS_2026-09-07\` (all six files) to
`docs/incumbent_checks_p8/`, change `REPO` in `incumbent_checks.py` to a
path relative to the repo root, re-run it with the frozen `toi_exofop.csv`
(do not re-fetch the TOI table) and diff the new output against
`incumbent_checks.out`; the numbers must match. Commit with a message naming
the prompt 9 side analysis.

0b. Baseline measurements: `pytest tests/ -q`; product count under
`data/survey/audit_lc/`; free disk. Write all three in the handoff.

0c. Workspace: all new evidence goes under `p10/` in the P9 layout
(`protocol/`, `results/`, `logs/`, `figures/`, `docs/`) and all run outputs
under `data/survey/p10/`. Nothing under `data/survey/p8/`, `data/survey/p9/`
or `p9/` is written by this prompt. `p8.0`, `p7.0` and `p6.2` are not edited;
every P8 funnel record must still replay byte-identical (checked in 2d).

0d. Write `HANDOFF_P10.md` section 0 now: every pre-registered rule of
Parts 1 to 5 with its threshold, in the P8 form ("choose the variant with
the highest X among those that retain at least Y% of Z", Y stated). Commit
it before the Part 1 re-derivation runs. Section 0 is never edited after a
measurement it judges has been seen.

---------------------------------------------------------------------

## Part 1: the endpoint

Principle: SUBMIT means a CTOI-grade candidate, the thing the human may
submit by hand on ExoFOP. It is what SPOC and QLP alert as a TOI: a clean
periodic transit with odd/even, secondary and pixel checks, on a star that
is not a catalogued eclipsing binary at that period. It is not a validated
planet. The validation bar (resolved source, localised repeated dimming,
low FPP) is retained as a mandatory `validation_status` text attached to
every SUBMIT, not as a gate. Stage B's flags remain measured and recorded
on every record, but under `p10.0` no flag caps the verdict; each flag is
either a KILL condition (evidence against), a HOLD condition (a specific
resolvable limitation) or a reported flag that travels with the candidate.

### 1a. The p10.0 verdict tiers [A, pre-registered]

A candidate reaching D is **KILL** when any of these holds:

- K1. Stage A fails (kept events < 3, kept SNR < 7, strongest-event share
  > 0.5, SNR without the strongest event < 5, depth outside 0.5 to 2 times
  the survey depth, constant-depth p < 1e-3). Unchanged from p8.0.
- K2. The repaired secondary gate of Part 2a fails.
- K3. Stage B's phase-independent sector non-detection rejects. Unchanged.
- K4. Stage C fails under the repaired C rule of Part 2c.
- K5. The period is an integer alias (the `_match` ratio list: 2:1, 1:2,
  3:1, 1:3, 3:2, 2:3, within 1%) of a deeper accepted signal on the same
  star (> 30 ppt or > 5 times the candidate depth), or of a catalogued VSX,
  TESS-EB, TOI or CTOI period within 1 arcmin.
- K6. Odd/even depth difference above 3 sigma on the all-transit template
  fit (`transit_fit`, the prompt-3 template odd/even with empirical errors).
- K7. Pixel evidence measures the dimming elsewhere or measures its
  absence: the difference image or fixed-aperture photometry places the
  dimming on a resolved neighbour at 3 sigma or more in at least two
  sectors, or the target aperture shows no dimming at 3 sigma when the
  fitted depth is at least 3 times the per-sector error in at least two
  sectors. An unmeasurable sector (error comparable to the depth, or no
  usable pixels) is neither.
- K8. The physical fit implies a stellar companion: fitted radius above
  1.5 Jupiter radii at the adopted stellar radius, or the density prior
  rejected above 3 sigma with a converged, non-grazing geometry. A grazing
  rail fit is H2, not K8.
- K9. Artefact-carried under D review: the raw-aperture and background
  evidence shows the events tracking sky ramps or corrections (the P8 KILL
  class). This is the one human judgment in the tiers. Its numeric criterion
  is written in section 0 before any review (default: the raw target
  aperture flux at the event epochs correlates with the background track at
  |r| > 0.7 in at least two sectors, and the sky-subtracted fixed-aperture
  depth disagrees with the fitted depth at more than 3 sigma in at least two
  sectors), and the reviewer records the numbers on the record.

Otherwise **HOLD** when any of these holds:

- H1. TRICERATOPS NFPP at or above 0.5 on the binned fold. A `fpp_uniform`
  result is an unavailable measurement, not a HOLD.
- H2. The all-transit fit is unconverged or on the grazing rail with
  unusable geometry uncertainties.
- H3. A D measurement (fit, FPP, or pixels) did not execute and can be
  re-run. Operational; must be cleared before the final list.
- H4. The target itself carries a VSX class EA, EB, EW or ELL within
  21 arcsec and the candidate period matches none of its aliases (a match
  is K5). Rotation and other classes are flags, not HOLDs.

Otherwise **SUBMIT**, always carrying this flag list on the record, in the
packet and in `ctoi_fields.json`:

- F1. Every neighbour within 63 arcsec that could produce the depth by
  total eclipse, with the dilution factor each would need (the existing
  Gaia depth-context calculation, now a list rather than a cap).
- F2. Gaia RUWE, `ipd_frac_multi_peak`, excess-noise significance,
  `non_single_star`, variability flag.
- F3. VSX and SIMBAD entries within 1 arcmin with class and separation.
- F4. FPP and NFPP with their caveats (binned fold, circular aperture,
  first three sectors, scenario-conditional).
- F5. Pixel localisation: on target, unlocalised, or not measurable, with
  the per-sector fixed-aperture depth and error for every reviewed sector
  and the centroid significance where measured.
- F6. Other accepted signals on the host.
- F7. SPOC TCE, TOI or CTOI association (Part 3g).
- F8. The artefact-class census of the kept events (the eight classes).
- F9. `validation_status`: the specific external evidence that would settle
  the source (the P8 "what would change this" text, now attached to a
  SUBMIT instead of replacing it).

The ordered submission list ranks SUBMITs by `ranking.score_v2`. No verdict
depends on rank. For controls, "SUBMIT-equivalent" means the same tiers
applied to the control's blind candidate, exactly as P9 defined it.

### 1b. Implementation

Add the tier rules to `tesshunter.audit_rules` as `RuleSet` `p10.0`, with
`p8.0`, `p7.0` and `p6.2` untouched and `KNOWN_RULES_VERSIONS` extended.
`star_vet.gaia_flag_digest` and `revet_p6.stageb_one` keep computing and
recording the P8 flags and `max_verdict`; under `p10.0` that field is stored
as `b_flag_cap_p8` and `provisional_verdict` reads the tiers instead. The D
packet tools (`scripts/p8_stage_d_packets.py`, `p8_target_aperture.py`,
`p8_eb_difference_image.py`) gain the F1 to F9 fields. Tests: every K and H
condition fired and just-not-fired, in the pattern of
`tests/test_p8_frozen_rules.py`; a test that `p8.0` records replay
unchanged. Add `docs/RULES.md` section 9 with the tier table.

### 1c. Re-derivation, not a rerun

Apply the tiers, from the saved records only, to the 19 P8 B passers
(`data/survey/p8/stageB`, `stageC`, `stageD`; a record without D evidence
gets "not permitted", never a verdict) and to the 16 P9 final candidates
(`p9/results/blind/<tic>/final/`). Write
`p10/results/tier_rederivation.csv` and a table in the handoff: key, p8.0
verdict, p10.0 verdict, the single condition that decided it. State the
expectation in section 0 before running so it is not mistaken for a
finding: the four P8 KILLs stay KILL under K9, the two P8 HOLDs turn on H1,
and most of the ten P9 useful HOLDs become SUBMIT-equivalent with flags.
Whatever the numbers are, they are recorded, not tuned. This is a
re-scoring of seen records under a pre-registered rule; say so where the
table appears.

---------------------------------------------------------------------

## Part 2: sensitivity repair on the injection set

The instruments are already on disk. Nothing in this part downloads
anything or reads a real P10 candidate.

- I1. `data/survey/injections_p8.csv` (2,100 on 300 stars), run
  `data/survey/runs/inj_p8`, funnel records `data/survey/p8/inj_funnel`,
  per-injection outcomes `data/survey/p8/injection_outcomes_p8.csv` (with
  `snr_expected`), and the level table in `completeness_p8.json`.
- I2. The false-alarm set: `data/survey/runs/fa_p8` (the same 300 stars
  uninjected), `fa_funnel`, `false_alarm_budget_p8.json`.
- I3. Negatives and recorded kills: the adversarial lists
  (`data/adversarial/targets_v1.csv`, 18 EBs and 22 blends, light curves
  cached), the P7 405 records (`data/survey/p7/options/`), TIC 233007823
  (the P6 eccentric EB, secondary at phase 0.605), the 170 P8 secondary
  rejections (`data/survey/p8/secondary/`, every one with a recorded EB
  screen review under `eb_screen/`), the 19 P8 C records
  (`data/survey/p8/stageC/`), the 18 P9 C records and their saved spectra
  (`p9/results/blind/<tic>/`, concentration diagnostics in
  `p9/results/spectrum_normalization_audit.json`).
- I4. The P9 development hosts (`split == development` in
  `p9/truth/final_truth.csv`: 9 hosts, 7 of them positive with 8 signals,
  2 negatives) plus the five audit-named hosts of rule 8.

Metrics, defined once and used throughout:

- SNR50_S: injection SNR50 through search, pre-gate, A and secondary, the
  `search_and_stageA_and_secondary` logistic of `p8_completeness.py analyze`
  (p8.0: 20.19).
- R_7_15 and R_15_30: fraction of injections with `snr_expected` in [7, 15)
  and [15, 30) recovered by the search under the P8 injection match. Report
  the P9 event-match rule as a second column; do not switch rules mid-prompt.
- FA_pre: false alarms per star past the pre-gate on the 300 FA stars
  (p8.0: 1.95). FA_S: per star through A and secondary (p8.0: 0.0067, from
  2 events; treat it as a count, not a rate).
- EBkill_S: fraction of the p8.0 secondary kills on the adversarial EB and
  blend set that a variant still makes.
- Wall: median per-star search wall time and the fraction of partitions
  that exhausted their budget.

### 2a. The secondary scan

Under p8.0 the `bound` gate fails when the deepest off-phase SAP dip exceeds
the planetary bound by 3 sigma using the box's white error; at these periods
the bound is about 1e-3 ppt, so the gate is "3 sigma from zero", and the
frozen rule applies even on busy scans of more than five dips
[P7, P8, P9 map]. Implement three new `GATE_MODES` in `tesshunter.secondary`
beside the existing four (which stay bit-identical; `p7_reproduce.py` is the
check):

- (a) `bound`: the p8.0 baseline.
- (b) `empirical_bound`: the dip's significance is measured against the
  scan's own off-phase scatter (the robust standard deviation of the box
  depth track at all phases outside the primary exclusion and outside the
  dip itself), not the white error. FAIL when depth exceeds bound plus 3
  times that scatter.
- (c) `recurrent_bound`: (b), and the dip must recur: the per-event box
  depth at that phase is at least 2 sigma (white) in at least half of the
  covered events, or the stacked depth is at least 2 sigma in each of two
  independent sector groups. A dip present in one sector or one event is a
  flag, not a FAIL.
- (d) `recurrent_bound_corr`: (c), and the dip must be present in both the
  SAP and the corrected flux. Dips made by PDC show in the corrected flux
  only [P5, P6]; an eclipse shows in both.

Measure every mode on: I1 (false-kill rate of injections reaching S; p8.0 is
189 of 1,093), I3 (EBkill_S on the adversarial set; TIC 233007823 must
FAIL; the P6/P7 EB-class kills retained), the 170 P8 secondary rejections
(descriptive only: how many would pass under each mode, cross-tabulated
with their recorded EB screen review class), and I4.

Decision rule [default Y = 90%]: choose the mode with the lowest injection
false-kill rate among those that retain at least 90% of the p8.0 kills on
the adversarial EB and blend set and that fail TIC 233007823. Ties go to
the simpler mode. Write Y in section 0 before running.

### 2b. Search capacity and ranking

New presets in `tesshunter.survey.PRESETS`; `survey_p8` is not edited:

- (a) `survey_p8`: budget 900 s, 3 planets per subsearch, 12 merged, top 8
  BLS candidates, composite score at least 3.0.
- (b) `survey_p10_budget`: budget 2,700 s, otherwise (a).
- (c) `survey_p10_slots`: 6 per subsearch, 24 merged, top 16, budget 900 s.
- (d) `survey_p10_rank`: (c), with candidate selection inside a subsearch
  ranked by resolved SNR rather than by composite score, composite 3.0
  retained as a floor.
- (e) `survey_p10_both`: (d) at 2,700 s.

Instrument first: save the rejected BLS and alias traces per partition and
a per-partition `budget_exhausted` flag (the P9 replay instrumentation in
`p9/` shows what to record; port it into `survey.py` behind a config flag
that defaults off so `survey_p8` output is unchanged). Then run, paired on
the same stitched cache: the injections with `snr_expected` in [6, 30)
(count them; expect roughly 900) and all 300 FA stars, under (a), (b) and
(c) first. Take the better of (b) and (c) by R_7_15 and run only (d) or
(e) accordingly. If the projected wall for the three-variant pass exceeds
16 h at 24 workers, subsample the injections to 600 with the seed and say
so; never subsample the FA stars, because the false-alarm cost of extra
slots is the thing being measured.

Report per variant: R_7_15, R_15_30, FA_pre, FA_S, Wall, the
budget-exhaustion fraction, and for every injection lost to ranking (passed
the internal gates in a trace and was not selected) the competing score.

Decision rule [defaults]: choose the variant with the highest R_7_15 among
those with FA_pre at most 1.5 times (a) and median wall at most 3 times
(a). If no variant improves R_7_15 by at least 5 percentage points over
(a), keep `survey_p8` and write that search capacity is not where the loss
is.

Report, from the existing injection funnel records and without a decision,
the loss of 10 to 30 d injections to the three-kept-events rule after
artefact removal, by period bin. It is a candidate mechanism for the next
prompt, not this one.

### 2c. Stage C

(i) The statistic. Extend `audit_p5.run_tls` to return `chi2`, `SR` and
`power_raw`, and `tls_step` to save them on every C record from now on.
Reproduce HIP 97166 b's C run from its locked P9 inputs with the arrays
saved, locate the extreme trial at 0.594628 d, and report whether its chi2
is legitimately extreme (which data points drive it) or a numerical or
statistical artefact. Then compute two statistics side by side on every
saved C spectrum (the 19 P8, the 18 P9, and the injection-C sample of
(iii)): the installed SDE, and `SDE_robust`, defined as the centred power
divided by 1.4826 times its median absolute deviation, no ordinate removed.
Rule [A, pre-registered]: C's threshold stays 9 on the installed SDE; the
robust statistic is consulted only when the largest single ordinate carries
more than 50% of the spectrum's centred variance (HIP 97166 b: 99.864%), and
then C passes if `SDE_robust` is at least 9 at the same peak. Report how
many of the 37 saved spectra trigger the fallback and whether any P8 or P9
negative-control or adversarial-EB decision changes. If any negative flips
to PASS, the fallback is withdrawn and the record becomes an H3 HOLD with
the concentration reported.

(ii) The strongest-peak rule. Implement in `revet_p6.stagec_one` beside the
p8.0 rule:

- (a) p8.0: the strongest peak within 1% of the survey period at SDE 9 or
  more, or an exact 2:1 or 1:2 alias with consistent depths.
- (b) `significant_peak`: the survey period has a local peak at SDE 9 or
  more within 1%, it is not an integer alias of a stronger peak (the
  `_match` list; the alias depth-consistency test is kept for 2:1 and 1:2),
  and if a stronger peak exists with at least 3 distinct transits the
  survey-period signal must persist at SDE 9 or more in a residual TLS run
  after masking that stronger signal's transits (`transit_mask`). A stronger
  peak with fewer than 3 transits (the P8 long-period one-or-two-event
  winners) does not block.

Measure on the 19 P8 C records (which of the 13 FAILs flip; their D
outcomes are already recorded, so this is development under rule 8), the
18 P9 C records (TOI-1470 c must flip; no alias case may), the 18
adversarial EBs' survey-period candidates (run C on them if no record
exists; the alias rule must still fail every half- and double-period case),
and the injection-C sample of (iii).

Decision rule: adopt (b) if it flips TOI-1470 c, flips no adversarial-EB or
negative-control alias case, and its injection-C pass rate is at least
(a)'s; otherwise keep (a) and record which condition failed.

(iii) C on injections, which has never been done. C at native cadence costs
hours per run, so first decide the input cadence for the calibration:
rerun C at 600-s binned input on the 37 saved P8 and P9 C records (if the
projected wall exceeds 12 h with the P8 C worker layout, on a seeded 12: six
PASS, six FAIL) and compare decisions with the native-cadence records. If
at least 35 of 37 (or 11 of 12) agree and every disagreement is explained,
the injection-C sample runs at 600 s and the handoff says so; otherwise it
runs at native cadence with 30 injections instead of 60. Then draw 60
recovered injections that passed S (seeded, 20 per `snr_expected` bin:
[7, 12), [12, 20), [20, 50)) and run C under (a) and (b) with the spectra
saved. Report C retention per bin. This is the project's first C-stage
completeness number; it feeds the yield calculation in 5e.

(iv) Duration floor: any reported TLS duration is floored at one cadence
before it enters a matching or coverage rule (the P9 scoring and this
prompt's); the raw value is kept beside it; one test.

### 2d. Freeze

Combine the chosen 2a mode, 2b preset and 2c rules with the Part 1 tiers as
`RuleSet` `p10.0` and preset `survey_p10` (created even where a field equals
`survey_p8`, so every record names it). Tests for each new threshold fired
and just-not-fired. `docs/RULES.md` section 9 with every measured table.
`scripts/p7_reproduce.py all --slices 16` must still report 0/0/0.0. Replay
20 seeded P8 records through `p8_funnel.py --rules p8.0` and diff against
the stored records: byte-identical. Then rerun S under `p10.0` on every
recovered injection (A is unchanged; S costs about 10 s per candidate) and
report SNR50_S(p10.0) with its bootstrap interval, and the full level table
beside the p8.0 one.

**Stop rule 1 [defaults]:** proceed to Parts 3 to 5 only if
SNR50_S(p10.0) is at most 14.0 (from 20.2) and the projected C load for the
Part 5 rerun (FA_S(p10.0) times 2,531 stars, plus the model's real signals
through S) is at most 150 runs. If either fails, write the handoff with the
repairs measured, the residual loss localised to a stage, and the reason
the rerun is not justified; commit; stop. Report the numbers either way.

---------------------------------------------------------------------

## Part 3: the 531 stars, the in-domain development set

P9 could not measure anything in the P8 domain: zero strict-overlap hosts.
The hard stop rejected 531 domain stars for a bare SPOC threshold-crossing
event and no other reason; they are the brightest and best-observed stars
in the domain (median Tmag 13.31 against 13.59, median 15 sectors at 200 s
against 4), 355 would rank inside the top 2,000, and they carry a modelled
5.1 funnel-grade planets [incumbent check]. Their TCEs come from SPOC
two-minute runs, largely in sectors 1 to 39; the P8 search reads FFI
products at sectors 56 and later. A TCE period recovered blind in
independent data on an independent pipeline is strong evidence of a real
periodic signal, and a miss with the signal present is a measured
sensitivity loss in exactly the domain P8 targets.

### 3a. The list and the TCE ephemerides

From `data/survey/cache/p8/pool_after_xmatch.csv`: rows with
`xmatch_status == REJECT` and `xmatch_tic_sources` exactly `spoc_tce`.
Reproduce the count (531). Apply the P8 Gaia dwarf check and the
FFI-majority rule from the corrected two-minute inventory (gotcha 15);
report the count after each.

`catalog_crossmatch._parse_spoc_tce` keeps only a label and a
"P=...d SNR=..." detail string. Extend it to also write a sidecar
`data/cache/catalogs/spoc_tce/spoc_tce.ephemerides.csv` with the ephemeris
columns present in the raw `*_dvr-tcestats.csv` headers (period, epoch,
duration, depth, model SNR, number of transits, and their errors where the
file has them; take the names from the header, do not guess them). The
normalised crossmatch table and every crossmatch digest stay byte-identical
(test). The search never reads the sidecar; assert that in the run manifest.

### 3b. The population rule [A, pre-registered]

Under `hard_stop_p10`, a TIC match in `spoc_tce` with no other source is
FLAG-with-ephemeris, not REJECT. Every other source's REJECT is unchanged
(TOI, CTOI, NASA archive, TESS-EB); the 21-arcsec neighbour FLAG is
unchanged; stars with a promoted TOI or CTOI remain REJECT for novelty. This
is a target-selection change, not a scientific threshold; its specificity
cost is measured in Part 4 on the negative controls like any other change.

### 3c. Acquisition

Raw products at sectors 56 and later into the audit store
(`scripts/p8_download.py 4 --targets <531 list>`, size estimate from
`--first 50`, disk check before continuing), Gaia, SIMBAD and VSX
(`scripts/p8_neighbours.py bulk` then `stars`), the noise record in the
`noise_p8` pattern, and the two-minute inventory from the corrected P9
parser. Gotcha 2 governs every MAST call.

### 3d. The blind search

Run `survey_p8` and `survey_p10` on all 531, paired on the same stitched
cache, `--resume`, per-partition budget flags recorded, TCE ephemerides
withheld (3a). Two presets because the paired difference on real signals in
the real domain is the measurement of the Part 2 search change that the
injections cannot give.

### 3e. Matching

A TCE is recovered when an accepted signal's period is within 1% of the TCE
period or of one of its `_match` aliases. The epoch is checked only where
the TCE period error propagated over the cycles to the P8 window is under
half the TCE duration; otherwise period-only, and say so per star. Report
recovery by TCE model SNR bin (below 9, 9 to 12, 12 to 20, 20 and above)
and by P8-condition expected SNR, computed from the TCE depth, duration and
period and the star's measured sectors-56-and-later noise (the incumbent
check's formula with the real sigma now available). Every TCE gets a forced
box fit at its period in the P8-window data (a truth-timed diagnostic,
allowed after the blind result is locked, as P9 did) so that "absent in
these data" is separated from "present and missed". Most TCEs are
systematics and will be absent; that is not a pipeline miss.

### 3f. Interpretation rule [A, pre-registered]

TCEs with model SNR at least 12 and at least 3 transits in their DV run
form the likely-periodic subset. Fit the recovery-versus-expected-SNR
logistic for that subset under each preset and compare its SNR50 with the
search-only injection SNR50 of the same preset. If the in-domain
real-signal SNR50 exceeds the injection SNR50 by more than 30%, the
injection calibration is optimistic in this domain: say so, autopsy the
five highest-expected-SNR misses whose forced fit shows the signal present
(P9's autopsy pattern: event removal census, ranking witness from the
traces, alias check, budget flag), and if one mechanism explains at least
three of the five, one bounded iteration of Part 2 is permitted for that
mechanism: re-measure on the injections, re-freeze as `p10.1`, rerun 3d
for the changed preset. At most one iteration. The autopsies never change a
locked blind result.

### 3g. Candidates wait

Every accepted signal on the 531 stars enters the `p10.0` funnel in Part 5,
not here. A TCE period match is carried on the record as flag F7 and into
the CTOI note ("SPOC TCE sNNNN-sNNNN pn N at P = ..., not promoted"). It is
an association, not a confirmation.

---------------------------------------------------------------------

## Part 4: held-out evaluation of p10.0

P9 froze the rule that any future gate experiment belongs in a separate
workspace with a fresh freeze and one use of the holdout. This part is that
experiment. It runs after Part 2's freeze and, in wall-clock terms, may run
while Part 5's search is in progress; no real candidate enters the Part 5
funnel until this part's numbers are in the handoff.

### 4a. The workspace

`p10/heldout/` in the P9 layout: a snapshot of the `p10.0` source under
`p10/heldout/baseline/source`, a copy of the P9 runner with only its source
root (`p9/common.py` `BASE`) and its output roots changed, the P9 frozen
truth, inputs and manifests reused read-only for the selected hosts, new
result, log and work directories. `p9/` is not modified. Hash the source
snapshot and the protocol before the first run.

### 4b. Hosts

The 39 P9 holdout hosts minus the three named in `docs/AUDIT_P9.md`
(HIP 97166, TOI-1470, TOI-849): 36 hosts, 18 positive hosts with 19
signals, 14 negatives, 4 uncertain TOIs. The three excluded hosts are run
too and reported separately as development cases; they do not enter the
held-out claim. Before any run, fix TOI-849 b's truth ephemeris to the
Armstrong et al. solution and write that in section 0 (gotcha 14).

### 4c. The run

Search, A, S, B, C and D under `p10.0` and `survey_p10`, ephemeris-blind
execution as in P9, C spectra saved with the raw arrays, D under the tiers
with every K and H condition recorded numerically and K9 applied by its
written criterion. Scoring uses the P9 rules unchanged (event match,
candidate choice, nested credit, alias family for negatives) except the
duration floor of 2c(iv).

### 4d. Metrics, paired against P9's frozen numbers for the same hosts

Nested positive counts per stage; SUBMIT-equivalent under the tiers; useful
HOLD; negative exact-or-alias-family survival per stage and
SUBMIT-equivalent; the uncertain TOIs descriptively. Wilson intervals and
the host bootstrap. A table of every host whose outcome changed and the
condition that changed it.

### 4e. New in-domain negatives

From the TESS Ten Thousand catalogue (Kostov et al. 2025, arXiv:2506.05631,
FFI eclipsing binaries; fetch the machine-readable table, record the URL,
date and hash) select binaries meeting the P8 stellar and product cuts
(Teff below 3600 K, radius below 0.45 solar, Tmag 12.5 to 14.0, |b| at
least 20 degrees, at least three sectors at 200 s with a QLP or TESS-SPOC
light curve, FFI-majority). Target 30. If fewer than 20 qualify, relax Teff
to below 4000 K, then Tmag to 12.0 to 14.5, in that order, and say so. If
the catalogue cannot be fetched, use the MAST TESS-EB catalogue under the
same cuts and say so. Withhold ephemerides, run the same nested sequence,
match with the P9 negative rule, autopsy every survivor past C.

**Stop rule 2 [default]:** if negative SUBMIT-equivalent survival exceeds
1 of N in either negative set (the 14 P9 holdout negatives, or the new
set), `p10.0` is not safe. Do not run Part 5 verdicts. Report which
condition let each negative through. A fix goes back through Part 2's
instruments and a fresh Part 4; one iteration is allowed, after which the
held-out sets are no longer held out and the handoff says so.

**Stop rule 3 [default]:** if positive SUBMIT-equivalent is 0 of 18 hosts
on the held-out planets, the endpoint change did not do what it was meant
to. Report which tier condition blocks (it will be one of H1, H4, K7 or
K9) and stop before Part 5's funnel; a survey rerun cannot help.

---------------------------------------------------------------------

## Part 5: the rerun

### 5a. Population

`data/survey/targets_p10.csv`: the 2,000 P8 stars plus the Part 3 stars
that passed the Gaia dwarf check and the FFI-majority rule, with the P8
columns, the `hard_stop_p10` status and the TCE association columns.
`docs/POPULATION_P10.md` as an addendum to the P8 memo: what changed and
the counts.

### 5b. Search

`survey_p10` over `targets_p10.csv` in the `p8_run_search.cmd` pattern
(prefetch at 8, search at 24, `--resume`, a retry pass). If `survey_p10` is
field-identical to `survey_p8`, reuse the P8 search results for the 2,000
and search only the Part 3 stars; if any field differs, search all 2,531
(gotcha 11: a wall-budgeted search is not reproducible enough to mix two
presets in one candidate list). Per-target log as P8.

### 5c. The funnel

`scripts/p8_funnel.py --rules p10.0 --root data/survey/p10`: collect, A, S,
B, C, stageD, in that order, nothing expensive before the cheap gates. Real
candidates enter only after Parts 1 to 4 are frozen, measured and
committed. Report the C count against the stop-rule-1 projection; if it
exceeds 150, run C in `ranking.score_v2` order, stop at 150, and list the
rest as not run (unknown, not rejected). Every A passer gets the secondary
scan; a seeded 10% of A failures get it too, as P8 did.

### 5d. D and the verdicts

For every C survivor: fresh hard stop (re-download the six catalogues; new
TOIs appear weekly), the all-transit fit with the density prior adopted
unless rejected, TRICERATOPS on the binned fold with the cached Gaia
neighbours, TESScut centroids for every selected sector, difference images
and fixed apertures (the P8 tools), the tiers applied with every K and H
condition recorded numerically, the flag list F1 to F9, the packet and
`ctoi_fields.json`. K9 by its written criterion, numbers on the record.

### 5e. `docs/AUDIT_P10.md`

- The funnel table (accepted, pre-gate, A, secondary, B, C, D) beside P8's.
- The ordered submission list: for each SUBMIT the two-sentence ExoFOP note
  and the flag list, including F9. A clean null is reported plainly.
- The comparison ledger: every P8 B passer with its p8.0 verdict, its
  p10.0 verdict, and the deciding condition; the same for every Part 3 star
  with a TCE match.
- The artefact census in the eight classes beside P8's.
- The Part 3 results: recovery by TCE SNR bin and by expected SNR, the
  forced-fit split, and the 3f comparison.
- The yield: the early expectation recomputed with the incumbent check's
  claimed fraction (0.03, novelty near one) through the `p10.0` injection
  curve, C retention from 2c(iii), and late retention from Part 4, giving an
  expected SUBMIT count and P(0) beside the observed count. Occurrence-model
  sensitivity (DC15 against the HU19 normalisation) reported next to it, as
  P8 and P9 did. No single number without its interval and its assumptions.

### 5f. Handoff and commit

`HANDOFF_P10.md` with section 0 unchanged, every measurement with its
sample size, every stop rule's outcome, what was refuted, what is open.
Commit naming prompt 10. The human then reads `docs/AUDIT_P10.md`, opens
every packet, and submits only SUBMIT verdicts, by hand, on
exofop.ipac.caltech.edu, with each candidate's F9 text in the comment.

---------------------------------------------------------------------

## Acceptance

- Prompt 9 and the incumbent check are committed; `p9/verify.py` still
  reports 397; the re-run incumbent check matches its stored output.
- `HANDOFF_P10.md` section 0 holds every pre-registered rule with its
  threshold, committed before the first measurement it judges.
- `p10.0` exists in `tesshunter.audit_rules` with the tier rules and the
  chosen 2a, 2b, 2c settings; `survey_p10` exists; tests fire and
  just-not-fire every new threshold; `p7_reproduce.py` reports 0/0/0.0; 20
  P8 records replay byte-identical under `p8.0`; `docs/RULES.md` section 9
  has every measured table.
- The tier re-derivation table for the 19 P8 B passers and 16 P9 final
  candidates exists and is labelled a re-scoring of seen records.
- The secondary, search and C measurements exist with sample sizes,
  paired, with the decision rule quoted beside each result; SNR50_S(p10.0)
  and the full level table stand beside p8.0's; stop rule 1 was applied as
  written.
- `run_tls` saves raw spectra; the HIP 97166 b trial has a diagnosed origin
  or a written statement that it could not be diagnosed; the fallback's
  trigger count on the 37 spectra is reported.
- The 531-star list, the TCE sidecar, `hard_stop_p10`, the paired blind
  search and the matching table exist; the forced-fit split and the 3f
  comparison are reported; any Part 2 iteration is named `p10.1` with its
  reason.
- The held-out evaluation exists in `p10/heldout/` with hashed source and
  protocol, paired tables against P9 for the 36 hosts, the three
  development hosts reported separately, the new negative set with its
  provenance, and stop rules 2 and 3 applied as written.
- If the rerun ran: every star ran or the handoff lists which did not and
  why; the funnel table, the comparison ledger, the census, the yield with
  intervals and the ordered submission list exist in `docs/AUDIT_P10.md`;
  every SUBMIT carries F1 to F9.
- Suite green. Commit on `improve/recovery` naming prompt 10. Write
  `HANDOFF_P10.md`.

---------------------------------------------------------------------

## Budget and sequencing

Rough wall-clock so the session can be planned and split at part
boundaries; all [A] until measured, and every C figure comes from the P8
and P9 tails, not from a pilot median.

- Part 0: under 1 h.
- Part 1: implementation and tests 2 to 4 h; the re-derivation minutes.
- Part 2a: the secondary variants on 1,093 injections plus the adversarial
  and P8 sets, about 10 s per candidate per mode, 2 to 4 h at 16 workers.
- Part 2b: about 900 injections plus 300 FA stars under three presets, the
  P8 mean of about 240 s per job (three times that at the 2,700 s budget),
  10 to 16 h at 24 workers; the fourth variant adds a third of that.
- Part 2c: the 600-s reproduction on 37 records and the 60-injection C
  sample, 12 to 24 h with two or three concurrent C jobs; the SDE audit and
  the strongest-peak variants on saved spectra, hours.
- Part 3: download for 531 stars at 4 workers, several hours in the
  background during Part 2; two paired searches, 1.5 to 3 h each at 24
  workers; matching and forced fits, an hour.
- Part 4: P9 used 27 process-hours for 48 hosts; 39 hosts plus about 30
  negatives, 30 to 40 process-hours, one overnight at the P9 worker layout,
  C tail up to 3 h per host.
- Part 5: the search 6 to 9 h at 24 workers if all 2,531 run; A about
  5 h; C up to 150 runs, several days with two or three concurrent jobs;
  D minutes per survivor plus review.

If the session must be split, split at a part boundary, commit, and leave a
"resume here" line at the top of `HANDOFF_P10.md`. Parts 3c and 5b can run
in the background while earlier parts are measured, as long as no real
candidate is looked at before its part permits it.
