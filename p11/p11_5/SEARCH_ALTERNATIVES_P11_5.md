# P11.5 alternative search: completed development

Completed development: 120 D_core hosts, 242 fixed injections, and 120 uninjected series.

Original population: 300 hosts / 600 injections. Verified input-eligible D_core: 235 hosts / 484 injections. Input exclusions are not measured misses. No extrapolation to excluded hosts or sectors is made.

Selected search: **R0**. Low-SNR comparison is after unchanged pre-gate, A and bound S: 45/109 versus 42/109; +2.75 percentage points (95% host interval +0.00 to +6.25); 3 paired wins / 0 losses.
Overall paired comparison: 113/242 versus 108/242; +2.07 percentage points (95% host interval +0.39 to +4.47); 5 paired wins / 0 losses.

| Search admission requirement | Met |
|---|---|
| low_gain | False |
| overall_gain | True |
| natural_pregate | False |
| wall | False |

| Method | Natural pre-gate candidates | Search/confirmation wall h | Search/confirmation/A/S wall h | Scientific CPU h |
|---|---:|---:|---:|---:|
| R0 | 222 | 68.409 | 152.217 | 133.993 |
| R1 | 458 | 69.126 | 243.583 | 216.795 |

R0 and R1 share one newly measured ordinary trajectory on identical frozen arrays. The observer retains complete gate-passing resolved pools and reconstructable masks. Each method includes the full shared work in its deployable cost; actual experiment expenditure counts it once. Original timings are retained on cache reuse.

R1 preserves ordinary winners and all original accepted candidates within the original 24 limit, top-16 internal pool and 2,700-second detector budget. Up to two distinct extras per pass enter a separate 12-candidate reservoir. Only ordinary winners change subsequent masks. Extras undergo actual whole-stitch confirmation. Deduplication requires relative period difference at most 0.001 and epoch offset plus accumulated drift at most half the shorter duration; rational aliases remain distinct.

All 52 historical ranking-loss cases and 124 witnesses were inspected. Only 4 meet the applicability/exhaustion/reclaimable-time conditions, below ten; R2 was not admitted. Historical witnesses are not new recoveries, and incomplete historical masks were not treated as valid replay evidence.

The complete nested population was selected before aggregate efficacy from measured six-host timing distributions, clustered runtime resampling and a 25% allocation margin. See `results/affordability_forecast.json` and `manifests/development_selection.json`.

The first main controller stopped during a Windows progress-record access error. Its completed predictions were reused and all 24 interrupted attempts and partial snapshots were preserved. A source-versioned controller resumed the same registered search/A/S/B workload with bounded progress-write retries; remaining C work used the already registered corrected version. No scientific outcome chose a retry, and no per-case deadline or cumulative cap was increased. See `manifests/controller_interruption_recovery_v1.json` and `manifests/development_resume_freeze_v2.json`.

2 completed payload artifacts had owning-controller TIMEOUT receipts. The registered controller deadline takes precedence: exact original payload bytes and timings remain in `results/late_payloads_v1/`, while subsequent handoffs and recovery/workload accounting use terminal operational unknowns. The uniform rule, discovered before aggregate efficacy scoring, is registered in `manifests/operational_deadline_precedence_v1.json`; per-application receipts are `results/deadline_precedence_*.json`. Already computed descendants and all attempt costs remain preserved.

The original-NPZ storage forecast exceeded available headroom, so all 897 remaining corrected-C candidates were retained in 13 finite batches. Completed model containers were packed losslessly as XZ; original NPZ hashes and exact-container verification receipts remain in `results/model_storage/C_v2/`. Packing owners occupied 0.1057 queue-hours, included in total expenditure. These storage phases are separate from the scientific C measurements. The frozen plan and each disk/memory/budget preflight are in `manifests/c_v2_storage_plan_v1.json` and `results/c_v2_batch_checks/`. Every C case retained its 600-second deadline, and each packing job had a separate 300-second deadline.

The read-only source review in `results/shared_downstream_contract_review.json` verifies that R1 extra-candidate context does not change the shared A/S/B scientific gates. Deep-candidate flags remain recorded diagnostic metadata under P10. This equivalence does not extend to later endpoint tiers.

The prepared-provenance audit checked all 719 generated array files and sidecars. Runtime arrays contain time, flux, errors and sector identity, with no physical injection parameters or recovery truth in provenance. A series-membership boolean remains in the sidecar; the fixed predictor does not consume it or copy it into the LightCurve metadata. This distinction is explicit in `results/prepared_provenance_review.json`. The prediction freeze additionally verifies prepared array, provenance, resolved-pool and mask-snapshot hashes.

Per-injection exact and alias outcomes, physical period/radius tables, expected-SNR bins and 10,000 paired whole-host bootstrap intervals are in `results/development_evaluation.json` and `results/sensitivity_tables.json`. Unobservable included injections remain in the overall denominator.

This is upstream development evidence. It establishes neither planet discovery, astrophysical false-positive probability, endpoint reliability nor authority for a survey or submission.
