# Prompt 8: historical calibration implementation notes

These dated checkpoints precede the frozen real-candidate funnel. Statements about pending work below describe their original checkpoint; see HANDOFF_P8.md for the current state.

## Implementation history through calibration

The checkpoints below are historical; the current status is stated above.

Resume-session checks [M]: clean `improve/recovery` at cb21449; 30,660 legacy lightkurve
cache files; 163.97 GiB free on C:; baseline 482 passed, 1 skipped (115.90 s). The
`survey_v1` smoke check reproduces all four stored candidates with zero differences.

Correction before the resumed measurements: the unfinished P8 audit driver inherited all
downloaded sectors and 30-minute TLS bins. It now uses `survey_p8`'s sector >= 56 selection,
product preference and common 200-second cadence, with no further binning. Its injection
loader follows the *completed search's actual order*: select/harmonise, inject at the
common product exposure into SAP and corrected flux, then detrend/clip. Context stamps
invalidate the 12 preliminary injection audit records; P5-P7 defaults are unchanged.
The targeted suite passed 52 tests, including the historical audit fixtures; additional
tests refuse missing, errored or stale measurements in completeness analysis.

Live logs: `data/survey/p8/logs/inj_funnel_slice*.log` and
`data/survey/p8/fa_funnel/logs/stageA_slice*.log`. Resume with the commands in
`HANDOFF_P8_5.md` section 6; the corrected context makes the funnel idempotent.

Before the yield measurement, two accounting corrections were made to the previously unrun
expectation script: incumbent completeness is now applied per occurrence cell and impact
parameter before summing detected yield (the old population-weighted average could mix a
recoverable, already-known cell with an unrecoverable, unsearched cell); the HU19 sensitivity
includes fractional cells crossing its 10-day boundary. The HU19 abstract's 1.19 +0.70/-0.49
rate was verified at https://arxiv.org/abs/1905.05900. It is a sensitivity proxy, not the central
model: its full 0.5-2.5 Earth-radius rate is assigned to DC15's supported 1-2.5 range with a
DC15 shape. No stop threshold or prior value was changed. Per-star native noise is checkpointed
under `data/survey/p8/noise_p8/`; `p8_expected_yield.py --noise-only --workers 4` builds the
prepared caches without a search or network requests. A missing noise curve after retry
prevents a stop decision instead of silently lowering the population's yield.

Further resumed-session measurements [M]: all 2,000 native noise curves are now complete,
with no failed target. TIC 287493127 sector 98 had a sparse window containing a corrected
flux value of 5.2e23; wotan's uncapped absolute-tolerance iteration could not converge at
float64 precision. `biweight_precision.py` preserves ordinary wotan calls and uses the same
window/estimator with a floating-point convergence floor only where necessary. The input
scan found 24 affected product/column pairs on 12 stars, including 3 injection-sample stars.
All 33 comparisons (the 12 stars' prepared arrays and all 21 injections on those 3 sample
stars) are byte-identical, with zero maximum array difference. Evidence:
`numerical_inputs_p8.json` and `precision_verification_p8.json`. The numerical/preprocessing
suite passed 51 tests; the final guard-specific checks passed 3 tests [M].

The earlier workers stopped before completion; the funnels resumed from their saved records
on 2026-09-05 at 13:27 EDT [M]. The current continuation driver is
`scripts/p8_finish_measurements.py`, now logged in `data/survey/p8/logs/finish_measurements_expanded.log`.
It validates complete inputs before completeness, yield and decision tables, and never starts
the real search or selects p8.0. Inspect the running processes before starting another copy.
P8 audit JSON and prepared-array checkpoints now use atomic replacement to avoid truncated
records after interruption. `p7_reproduce.py all --slices 16 --out data/survey/p8/reproduce_p7_p8.json`
can retain the historical P7 summary when the required final reproduction is run.

The recovered-injection fit/CTOI/verdict exercise has completed under p7.0 [M], in the
separate `demo_inj` root, on `inj00378_tic154567574`. The generic limb-darkening fallback
initially put the impact parameter at zero and made the covariance singular. P8 fits now
use the project's Claret interpolation at the TIC temperature when no packet supplies
coefficients; missing uncertainties are JSON null, with HOLD required for an unresolved
fit uncertainty issue. The final fit uses 9 transits, recovers Rp/R*=0.2037795 +/-0.0011519
for injected 0.20443, gives Rp=3.890 +/-0.390 Earth radii, b=0.10780 +/-0.06318, and T14=1.339
+/-0.125 h [M]. The density prior is adopted (delta chi2=0.18977), beta=1.02, and the geometry
is not grazing [M]. The Gaia excess-noise flag still gives the real-data provisional HOLD;
the explicitly labelled SUBMIT stamp exercises only the writer. The packet says never submit.
`fit_exercises_p8.json` retains both this exercise and the previously completed TOI-270 c fit.
The fit/packet/input checks passed 12 tests before the final limb-darkening-specific check [M].

The TLS timing check [M] repeated 3 injection and 2 control-sample forced searches, including
native arrays of about 200,000 cadences, with exactly equal complete TLS summaries: 0 field
differences and 0.0 worst relative difference. `tls_epoch.py` avoids repeated phase sorting
in TLS 1.32's final epoch scan while preserving its grid, score arithmetic and first-minimum
rule. Paired timings on identical control arrays and synthetic templates were 9.46 to 2.99 s
and 24.12 to 8.89 s [M]. This measures that step only; the period search still dominates and
the historical whole-fit wall times were measured under different CPU loads. Future native
TLS calls use the equivalent routine; legacy calls and unknown TLS versions retain upstream
behavior. The static calibration workers retained their in-flight work until the shared-queue
resume described below; the resumed native workers use this equivalent routine.
Evidence: `tls_epoch_benchmark_p8.json`, `tls_epoch_benchmark_fa_p8.json` and
`tls_epoch_paired_timing_p8.json` [M].

The completeness report now carries both the ungated and pre-gated outcomes in every map,
and verifies and reports the seeded secondary-scan sample of Stage A failures before accepting
the false-alarm budget. The full regression run passed 524 tests with 1 skipped in 328.17 s;
the subsequent native-input, epoch-scan and report checks passed 42 tests in 15.58 s [M].
The legacy survey smoke check again returned 4 candidates with 0 differences; free disk was
158.66 GiB [M]. The final P8 rule-set regression and the full P7 reproduction are still due.

The completeness, false-alarm totals, expected yield and rule decisions remain pending.
The stop threshold and pre-registered choices below have not changed.

To overlap the inexpensive rule comparisons with the remaining native TLS work,
`p8_measure_ready_decisions.py --limit 64 --workers 2` measures only injections with settled
Stage A and secondary records. The first batch completed all 64 in 5.1 min, with no errors;
the instrument reproduced their P7 Stage A and secondary decisions [M]. A second bounded
batch is logged in `data/survey/p8/logs/decisions_ready_batch2.log` and is complete. This does
not select a rule: `p8_decisions.py tables` still requires the complete
injection and reference sets. The continuation driver now accepts `--inj-slices`, `--fa-slices`
and `--decision-slices` for a checkpointed rebalance after a phase frees CPU cores; the
original driver used 16 injection and 8 control slices [M].

The yield JSON now records its calibration's rule version, sample size and stage boundary,
with model assumptions kept separately. The population memo explains the adopted incumbent
priors and the HU19 sensitivity's restricted transcription; it does not present a projected
yield as a measured candidate count.

The first two bounded decision batches completed 320 injections with no errors, reproducing
all 320 stored baseline Stage A decisions and all 320 stored secondary decisions [M]. These
are measurement checkpoints only; the full-set guard still prevents a rule selection.

At 15:28 EDT on 2026-09-05 [M], CPU counters showed the final 16 logical processors fully busy
and most of the first 16 lightly used. The 24 computation workers had unrestricted affinity,
normal priority and system-managed execution QoS [M]. Windows HighQoS was applied to these
verified workers without restarting them, changing their priority or changing the system power
plan. The subsequent 20.01-second check measured a mean 0.975 CPU-second per worker per
elapsed second [M], with the previously idle processors active. Future P8 slice workers request
the same scheduling mode. Evidence: `worker_scheduling_p8.json`; method:
[Microsoft's SetProcessInformation documentation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setprocessinformation).
This changes scheduling, not the scientific calculation. The early native TLS wall times
include the slower scheduling period and should not be used as a clean benchmark of the code.

The checkpointed resume uses `p8_finish_measurements.py --shared-queues`: SQLite
claims distribute the remaining cases among the existing top-level subprocess workers.
The completed scientific files, rather than queue state, remain the resume checkpoints;
a new run creates a new queue and cached cases return immediately. Three queue concurrency
and lifecycle tests passed [M]. `p8_queue_smoke.py` replayed 5 settled injections and 5 controls
through the new worker loops, leaving all 45 hashed scientific files unchanged [M]; evidence
is `queue_smoke_p8.json`.

At 16:07 EDT [M], the verified static driver and its producer tree were stopped and resumed
with `--shared-queues --inj-slices 24 --fa-slices 8 --decision-slices 24`. The old logs were
preserved under `data/survey/p8/logs/static_before_shared/`. All 4,768 JSON checkpoints and
14 recently written array archives passed the interruption integrity check; none was removed
[M]. The latest bounded instrument batches are complete: 628 injections, 0 Stage A or
secondary differences from their stored p7.0 baselines [M]. Evidence:
`data/survey/p8/reporting_checkpoint_p8.json`. Check the active shared driver before launching
any additional producer; launcher PID at resume was 33672 [M].

The rotation map previously ended at an arbitrary reporting boundary of 1e9 ppt [A]. Three
sample stars (TIC 233622554, 233630091 and 233731417) have extreme raw-photometry proxies,
covering 21 injections [M]; these now have an explicit final bin, preserving all 2,100 rows
in the map. The analysis reports their TICs separately and changes no search or vetting gate.
All 3 reporting checks passed in 60.05 s under calibration load [M]. The report also states
the individual-injection bootstrap assumption and the conditioning of depth-consistency
p-values on recovery, ephemeris estimation and event removal.

Before the first yield run, an end-to-end test with a synthetic calibration exposed an
incorrect list argument to the existing pandas-Series contamination helper. The P8 caller
now supplies the expected Series; the shared yield model is unchanged. All 3 yield checks
passed in 15.82 s [M], including the actual entrypoint, missing-contamination fill, finite
JSON output, prior ordering and calibration provenance. The real-input preflight found
2,000 valid measured-noise records and no missing/nonfinite radius, mass or temperature;
11 contamination entries use the existing measured-median fill [M]. All 2,100 injections
lie within the period, radius and Tmag plot bounds [M]. The apparent 0.450-Rsun endpoint
in the published target CSV is rounding to 3 decimals [A]; the population's strict radius
cut was applied to the original unrounded TIC values.

At 16:57 EDT [M], the continuation driver alone was replaced, leaving all native fits
running. The active driver launcher is 18848, attached to the injection coordinator 6212
and the existing control dispatcher 34780; the original injection dispatcher remains 12484
[M]. Verify identities before acting on these historical PIDs. The coordinator
(`p8_expand_injection_queue.py`) waits for the control dispatcher, adds 8 top-level workers
to the existing injection queue, then waits for both the original dispatcher and every
added worker before allowing validation/retry. Its log is `logs/injection_expansion.log`.
The new driver will retry incomplete sets through a fresh shared queue if needed.
No native fit was stopped in this transition [M].

The expansion smoke replayed 5 settled injections in 2 helper workers, preserved all 25
hashed scientific files, and verified that the coordinator stayed live after its helpers
finished until the owned original-dispatcher fixture was released [M]. Evidence:
`queue_expansion_smoke_p8.json`. Queue and expansion checks passed 5 tests in 2.21 s [M],
including capacity waiting and a partial startup failure that must drain live producers
before a retry is possible. This is scheduling only; the calibrated calculations are unchanged.

The full regression suite after the yield/reporting/scheduling work passed 545 tests with
1 skipped and 9 dependency/deprecation warnings in 386.50 s under calibration load [M].
Log: `data/survey/p8/logs/pytest_expansion.log`. The final frozen-P8 regression and the
required full P7 reproduction still remain. The sixth bounded decision batch completed all
128 planned injections in 11.7 min at 2 workers [M], with no errors; log
`logs/decisions_ready_batch6.log`. All 628 instrument records reproduce their stored
baseline Stage A and secondary decisions [M]. This does not choose rules or write
complete-set tables. A seventh batch (limit 128, 2 workers [A]) started at 18:08 EDT [M],
logged in `logs/decisions_ready_batch7.log`; inspect its completion and the running
processes before launching another bounded batch.

The seventh batch completed all 128 injections in 8.2 min [M], bringing the instrument to
756 records [M]. All secondary decisions agree with the stored baseline [M]. One Stage A
comparison differs: `inj01014_tic234507624` [M]. The fixed-ephemeris instrument masks around
its chosen TLS timing; full Stage A detrended around the survey timing before TLS. With
the instrument mask, inflated p = 0.00098707 and the criterion fails; with the original
survey mask, p = 0.00415901 and it passes [M]. A diagnostic replay using the original mask
exactly reproduces all 7 compared statistics/decisions and preserves source hashes [M];
`decision_mask_replay_p8.json` records the inputs and checks. The pre-registered instrument
and the full-funnel calibration are retained as measured; neither record was changed.
Reproduce the diagnostic with `python scripts/p8_replay_mask_difference.py`.

The eighth bounded batch completed all 128 injections in 7.2 min [M], bringing validation
to 884 instrument records [M]. No additional Stage A differences occurred; all secondary
decisions still agree [M]. The injection audit was at 923 of 1,163 Stage A records at
18:41 EDT [M]. No bounded comparison batch remains running at this checkpoint.

The ninth and last bounded batch (limit 128, 2 workers [A]) started at 18:57 EDT [M],
launcher PID 30952 [M], with the injection audit at 1,013 of 1,163 records [M]. Its log
is `logs/decisions_ready_batch9.log`. Verify process identities before starting more work;
the complete-set driver will handle the final unmeasured decision records automatically.

The ninth batch finished 128 injections in 8.3 min [M], yielding 1,012 instrument records
[M]. Three fixed-ephemeris Stage A decisions differ from full Stage A [M]:
`inj00448_tic160068028`, `inj01014_tic234507624`, `inj02014_tic436869614`. Replays using
each original survey mask exactly reproduce their decisions, depth statistics and matching
event counts [M]; see `decision_mask_replay*.json`. The first case has 148 kept event-table
rows but 147 finite kept depths [M], so those two counters must not be interchanged.

The same validation caught one secondary-bound discrepancy [M], `inj01639_tic350654423`:
rebuilding its gate from the displayed, rounded SAP depth/error changed a near-threshold
FAIL to PASS. Current scans already carry every variant's decision before display rounding.
`p8_decisions.py` now uses those recorded gates; older P7 scans without them retain the
existing shoulder reconstruction. The current scan's quiet-gate N counts its full dip list,
whereas the displayed independent-dip count excludes shoulders; rebuilding from the latter
also changed quiet variants. This changes no threshold or eligibility criterion.

`p8_refresh_decision_gates.py` refreshed 45 derived records (16 injection, 6 adversarial,
23 cached P8 reference records) with 0 changes to their other fields [M]. The reference
refresh makes stale cached fields agree with the reconstruction already used by tables;
the original P6/P7 inputs are unchanged [M]. `decision_gate_refresh_p8.json` records every
before/after value. The initial serialization regression passed 3 tests in 19.02 s [M];
the completed-set and frozen-P8 checks remain pending.

The false-alarm budget is complete on all 300 stars [M]: 2,097 accepted search records,
586 passing the pre-gate, 36 passing Stage A, and 2 passing Stage A plus secondary [M].
The seeded sample of 55 Stage A failures has 32 secondary PASS and 23 FAIL [M]; all 91
selected secondary checks completed [M]. Evidence: `false_alarm_budget_p8.json`. These
are uninjected calibration signals, not a full-population candidate list. The per-star
rate through these gates is 0.006667 [M]; later vetting remains outside this calibration.
