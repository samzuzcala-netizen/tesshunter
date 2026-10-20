# P11.5 closed handoff

Final state: **NO_QUALIFIED_GAIN**. Completed development: 120 D_core hosts, 242 fixed injections, and 120 uninjected series.

All registered cases reached a terminal accounting state, with 43 required stage records retaining operational unknowns. Recovery and workload use the predeclared conservative treatment. This is a complete attempted-cohort result with incomplete individual scientific measurements; it does not establish what the censored stages would have returned.

All owned P11.5 scientific queues are closed. Original P10/P11 controllers and sealed evidence remain unchanged. No scheduled continuation, full discovery survey, reserved TCE-ephemeris exercise, submission or push occurred.

The versioned implementation is in `src/tesshunter/p11_5_detector.py`, `p11_5_search.py` and final `p11_5_clocal_v2.py`; the first C implementation remains as `p11_5_clocal.py`. Isolated orchestration/evaluation is in `p11/p11_5/protocol/`. Per-case source/input identities, failed attempts and timing receipts remain durable. New scientific arrays and models are in `data/survey/p11/p11_5/` and indexed by the final data seal.

Reproduction uses the recorded Python environment. Completed outputs are immutable; do not rerun fixed-path writers over this evidence. Reproduce in a separate isolated P11.5 revision with matching input/source hashes, or use the tests and read-only hash checks. The executed phase manifests and owning-controller receipts record exact commands.

Scoped Git attributes preserve the exact bytes of the new P11.5 source and evidence despite the checkout's automatic line-ending conversion setting. The source-directory attribute pattern applies only to `p11_5_*.py` and its own attribute file; existing named scientific configurations retain their prior bytes and behavior.

Core commands, in their original execution order:

```powershell
python p11/p11_5/protocol/cost_selection.py
python p11/p11_5/protocol/development_handoff.py
python p11/p11_5/protocol/controller.py p11/p11_5/manifests/development_input_jobs.json --workers 24 --timeout 300
python p11/p11_5/protocol/flow_controller.py development_complete --series p11/p11_5/manifests/development_series.json --candidates p11/p11_5/manifests/control_A.json --workers 24 --stages ASBC
python p11/p11_5/protocol/recover_controller_interruption.py
python p11/p11_5/protocol/bounded_launch_v2.py development_complete_v2 p11/p11_5/protocol/flow_controller_v2.py development_complete_v2 --series p11/p11_5/manifests/development_series.json --candidates p11/p11_5/manifests/control_A.json --workers 24 --stages ASB
python p11/p11_5/protocol/reconcile_operational.py
python p11/p11_5/protocol/prerequisite_completion.py prerequisite_completion_after_development_v2
python p11/p11_5/protocol/reconcile_operational_v2.py
python p11/p11_5/protocol/prerequisite_completion.py prerequisite_completion_after_deadline_precedence_v1
python p11/p11_5/protocol/c_v2_handoff.py
python p11/p11_5/protocol/c_v2_plan.py pilot
python p11/p11_5/protocol/bounded_launch_v2.py c_v2_memory_pilot p11/p11_5/protocol/controller_v2.py p11/p11_5/manifests/c_v2_memory_pilot_jobs.json --workers 1 --timeout 600
python p11/p11_5/protocol/reconcile_operational_v2.py
python p11/p11_5/protocol/c_v2_plan.py remaining
# The full-plain-archive preflight above refused storage; its receipt is preserved.
python p11/p11_5/protocol/bounded_launch_v2.py c_v2_storage_pilot p11/p11_5/protocol/controller_v2.py p11/p11_5/manifests/c_v2_storage_pilot_jobs.json --workers 1 --timeout 300
python p11/p11_5/protocol/c_v2_storage_plan.py register
python p11/p11_5/protocol/c_v2_storage_plan.py C 1
python p11/p11_5/protocol/bounded_launch_v2.py c_v2_batch_01 p11/p11_5/protocol/controller_v2.py p11/p11_5/manifests/c_v2_batch_01_jobs.json --workers 24 --timeout 600
python p11/p11_5/protocol/reconcile_operational_v2.py
python p11/p11_5/protocol/c_v2_storage_plan.py PACK 1
python p11/p11_5/protocol/bounded_launch_v2.py c_v2_pack_batch_01 p11/p11_5/protocol/controller_v2.py p11/p11_5/manifests/c_v2_pack_batch_01_jobs.json --workers 24 --timeout 300
# Repeat the frozen C/reconcile/PACK sequence for indices 2 through 13; use the packing worker count returned by each preflight.
python p11/p11_5/protocol/reconcile_operational_v2.py
python -m pytest tests p11/tests p11/p11_5/tests -q
python p11/p11_5/protocol/evaluate.py freeze regression_before_prediction_freeze_v3
python p11/p11_5/protocol/evaluate.py evaluate
python p11/p11_5/protocol/sensitivity_tables_v2.py
python p11/p11_5/protocol/plot_development.py
python p11/p11_5/protocol/population_final.py
```

No eligible development finalist exists. A future fresh validation run must follow a new eligible frozen development result and the original full-domain criteria; reusing these exposed hosts does not create a holdout. See the measured admission failures and costed next-step evidence.

The unretuned P10 endpoint risks remain: confirmed TOI-762 A b and TOI-122 b are rejected by tier thresholds; TIC 144277542 changes from artifact KILL to SUBMIT under rescoring. P11.5 does not repair or validate these endpoints.

The prediction freeze followed a full regression of 886 passed / 1 skipped tests (9 warnings). A later sensitivity-table export exposed a NumPy boolean serialization issue. The versioned `protocol/sensitivity_tables_v2.py` adapter converts NumPy scalars only at the JSON writer boundary; the original diagnostic calculations, every prediction-freeze source hash, and the single development evaluation remain unchanged. The complete follow-up regression passed 891 tests with 1 skipped and 9 warnings; its source-hash checks passed. See `manifests/sensitivity_serialization_v2.json` and `results/regression_after_reporting_serialization_v4/`.

The final diagnostic and delivery steps also ran `control_tables.py`, `resource_ledger.py`, `costed_next_step.py`, and `reports.py NO_QUALIFIED_GAIN`. Final historical/source/data checks and delivery use `integrity.py historical`, `integrity.py final`, and `local_delivery.py commit` / `local_delivery.py package OUTPUT_DIR`. Execute reproduction commands only in the isolated reproduction described above. Manual report annotations are recorded in `results/final_report_amendments_v1.json`. The local commit identity is recorded separately in `manifests/local_commit_receipt.json`; its receipt is excluded from its own commit.
