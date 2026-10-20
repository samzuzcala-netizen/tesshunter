# P9 handoff

Completed external-validation baseline at `fbc68571d68896d45c1b703d6c615344a4ab872e`. Read [docs/AUDIT_P9.md](docs/AUDIT_P9.md) for interpretation and [p9/TABLES.md](p9/TABLES.md) for full numerical results.

- 48 hosts, 51 eligible independently categorized signals; 31 confirmed/validated planet signals on 28 hosts.
- Positive nested counts: search 14 → pre 14 → A 14 → S 14 → B 14 → C 11; final SUBMIT-equivalent 0, useful retained 10. Every actual submission flag is false.
- Negative exact-or-alias family: 16 labelled signals; final SUBMIT-equivalent 0, useful 0. Use unknown-outcome envelopes and completed-only tables when execution fails.
- 3 unresolved exact labelled paths; operations, retries and auxiliary pixel availability are recorded separately.
- 17 positive search-match failures, including 15 with expected model SNR below 7.1. TOI-849 b is a documented published-timing exception, with no primary credit changed. Every positive has an autopsy.
- Strict corrected P8 product/targeting overlap: 0 hosts. Analytic matched comparison: unsupported. ESS and a transported P8 final-yield posterior are unavailable.
- All 397 final integrity checks pass; all 48 hosts locked. Original scientific source, P8 outcomes and pre-existing follow-ups remain unchanged.

The final inference is limited by sample/product coverage. Weak-signal search sensitivity is a major observed loss, with documented ranking and C strongest-peak exceptions. TOI-849 b fails the frozen timing match despite a locked useful signal; a post-lock published-solution audit identifies it without changing primary scores. HIP 97166 b also fails C despite the correct strongest period: one extreme negative trial ordinate dominates the global power variance. Its native FAIL remains; raw trial residuals are unavailable, and no replacement statistic was calculated. TOI-1450 A b also fails primary C identity because its reported duration is shorter than one cadence, despite native C PASS and a matching locked final fit; its primary score is unchanged. All six historical P8 C survivors already had B HOLD ceilings; subsequent D source/background judgments remain unchanged. This identifies the recorded submission constraint, but does not establish whether changing a cap would retain real planets safely or explain the astrophysical population. The old 11.7 is an early-secondary expectation; [yield scenarios](p9/results/yield_scenarios.csv) apply conditional late retention exactly once.

## Evidence and commands

Use the original Python environment recorded in [p9/baseline/environment.json](p9/baseline/environment.json), with the psutil supplement. Scientific execution imports [p9/baseline/source](p9/baseline/source). [p9/README.md](p9/README.md) gives full commands. Recompute from locked evidence with scoring → diagnostics → search audit → spectrum audit → ephemeris audit → ephemeris figures → duration audit → autopsies → failure figures → metrics → comparison → catalogue audit → historical caps → census → negative audit → tables → verify → report. Do not reopen or overwrite locked host trees.

The raw input/sky/truth manifests are separately hashed. The scientific runner has not changed since final sample freeze. Additional recording, scheduling, scoring and pixel-presentation repairs are disclosed in [AMENDMENTS.md](p9/protocol/AMENDMENTS.md), [SCORING_IMPLEMENTATION.md](p9/protocol/SCORING_IMPLEMENTATION.md) and [LEAKAGE_AUDIT.md](p9/LEAKAGE_AUDIT.md). Manual review is unblinded.

## What remains uncalibrated

No gate variant was evaluated; do not claim an improvement or specificity cost. No validated transplantation or spatial injection was performed. Independent instrumental/variable negatives outside the EB catalogue, representative P8 late-gate sensitivity, weighting and a full yield posterior remain unsupported. These are inference limitations, not unfinished permitted candidate stages.

Any future gate experiment or new sample belongs in a separate workspace with a fresh freeze and independent evaluation. No additional discovery survey or external submission is authorized by this handoff.
