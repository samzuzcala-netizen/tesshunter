# P9 reproducible external-validation experiment

Read [the audit](../docs/AUDIT_P9.md) for the scientific conclusions and
[HANDOFF_P9.md](../HANDOFF_P9.md) for continuation. This directory contains the
experiment, independently labelled truth, execution manifests, locked measurements,
scoring and evidence. The original P8 source, data and verdicts are preserved.

## Evidence layout

| Path | Purpose |
|---|---|
| `baseline/` | Exact commit, initial Git state, archived source/configuration, dependencies and hashes of P8/follow-up evidence |
| `protocol/` | Preregistration, explicit amendments, implementation gate map, runtime sizing and input/sample locks |
| `truth/` | Frozen NASA/ExoFOP/MAST EB catalogues, label/reference provenance, original exclusions, field-level sky redactions and selection log |
| `manifests/` | IDs, stellar-only execution CSV, coverage inventories, selected-product and preparation receipts |
| `inputs/` | Frozen raw products, whitelisted stellar and sanitized neighbour inputs; no planet solution in execution inputs |
| `results/blind/` | Per-host searches, every recorded BLS/alias trial, pre-gate tables, permitted stages, FPP/pixel evidence and final scientific reviews |
| `results/locks/` | Per-host exact file hashes created before truth scoring |
| `results/timing_pilot/` | Preserved original pilot; valid downstream reuse requires exact primary-search compatibility |
| `results/operations/`, `logs/` | Commands, adapter hashes, retries, wall times and stdout/stderr |
| `results/` | Signal scores, candidate ledger, metrics, loss census, comparison, yield scenarios and integrity receipt |
| `diagnostics/`, `AUTOPSIES.md` | Post-lock known-ephemeris diagnostics for each signal and every positive control; excluded from primary counts |
| `reviews/`, `LEAKAGE_AUDIT.md` | Explicitly unblinded final adjudication and boundary audit |
| `calibration/` | P8 analytic injections re-scored against the registered P9 event-matching rule, including missing downstream outcomes |
| `figures/`, `TABLES.md` | Rendered scientific figures and numerical tables |

## Runtime and commands

The experiment used Python 3.13.3 in
`C:\Users\seanj\Downloads\tesshunter_venv\Scripts\python.exe`.
Exact package versions are in `baseline/environment.json`, with the non-scientific
psutil addition in `environment_supplement.json`. Scientific imports come from
`baseline/source`, not the live checkout. Do not regenerate the source snapshot,
sample or truth in this completed experiment.

For read-only verification and recomputation from existing locked evidence, run
the following in the repository root, using that interpreter or a separately
prepared environment with the saved package versions:

```powershell
python p9/verify.py
python p9/scoring.py
python p9/diagnose.py
python p9/search_audit.py
python p9/spectrum_audit.py
python p9/ephemeris_audit.py
python p9/ephemeris_figures.py
python p9/duration_audit.py
python p9/autopsies.py
python p9/failure_figures.py
python p9/metrics.py
python p9/comparison.py compare
python p9/comparison.py yield
python p9/catalogue_audit.py
python p9/historical_caps.py
python p9/census.py
python p9/negative_audit.py
python p9/tables.py
python p9/verify.py
python p9/report.py
python -m pytest p9/test_protocol.py -q
```

`diagnose.py` reuses already completed diagnostic caches; its known ephemerides
never enter the blind result tree. Scores and tables are reproducible from the
saved measurements without redoing TLS/FPP. Operation receipts and locks are
checked independently of the report text.

`ephemeris_audit.py` uses cached post-lock archive timing snapshots. Its
alternative-solution checks never alter the primary truth, scores or verdicts.
The source-selection rule and scope of the supplemental audits are recorded in
[POST_LOCK_DIAGNOSTICS.md](docs/POST_LOCK_DIAGNOSTICS.md).

A **fresh replication belongs in a separate copy**, preserving this completed
experiment. Restore the frozen inputs and baseline archive, retain the registered
manifests, and use new result/log/work directories. The executable stage sequence is:

```powershell
python p9/runner.py batch --kind final --stage search
python p9/runner.py batch --kind final --stage A
python p9/runner.py batch --kind final --stage S
python p9/runner.py batch --kind final --stage B
python p9/runner.py batch --kind final --stage C
python p9/runner.py batch --kind final --stage D
python p9/adjudicate.py queue
```

The batch runner schedules only permitted successors. Native D is followed by
`pixels.py prepare --tic ID` and `pixels.py run --tic ID --key BLIND_KEY` for each
permitted survivor, inspection of saved evidence, a structured review through
`adjudicate.py apply --review PATH`, and `maintenance.py lock`. The review is a
scientific judgement, not an automatic substitute for inspected pixel evidence.
The pixel presentation includes every available sector, even a sector omitted
from the native weighted centroid because its reported error is zero.
`aperture_review.py --tic ID --key BLIND_KEY` records each sector's availability
under the unchanged native extractor and is called by `pixels.py`. It does not
relax the sky mask or convert missing flux into a clean source measurement.
Actual submissions remain disabled. Do not call a second batch for a stage whose
workers are already active: completed-operation checkpointing is not a distributed
job lock. Per-host stage pipelining is allowed with the registered worker limits.
`dispatch.py` provides the recorded S/B/C/D pipelining coordinator while a fixed A
batch runs; it must not be combined with newly launched competing downstream batches.

Fresh execution will not necessarily be bit-identical: the frozen search uses wall
budgets, remote products/catalogues can change, and final review is unblinded and
partly manual. Frozen bytes, seeds, commands, returned measurements and all timing
stops make this run auditable. A fresh sample from current catalogues is a new
experiment and needs its own freeze. The original two-minute parser and its
corrected inventory are deliberately both retained, rather than silently rewriting
the historical selection process.

The portable report bundle includes the frozen raw light curves and complete
locked host trees, including their numerical arrays. It omits intermediate
execution/TESScut and compiler caches, which remain in the full repository P9
workspace. Product filenames, URLs/receipt metadata and SHA256 values identify
the required pixel bytes; a later archive download is not assumed identical
without a hash check. The included `verify_portable.py` checks the bundle and
exact host locks. Full `verify.py` additionally needs original P8 injection
results, target lists, preserved follow-up files and Git metadata outside the
portable bundle. Recompute in a working copy because derived timestamped files
will differ from the original package manifest.

## Scope of the measurements

Only an exact registered signal match earns primary planet recovery. Aliases are
separate, and unrelated signals on a labelled host do not inherit its label.
Uncertain TOIs are descriptive. Negative subtypes lacking independent signal labels
remain uncalibrated. Light-curve injections do not validate unchanged pixels.
Unsupported P8 covariate regions receive no weights or precise transported yield.
No gate tuning or discovery search is part of P9.
