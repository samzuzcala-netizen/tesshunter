SPRINT HANDOFF 2026-09-22T23:45:38.716452+00:00

**STOPPED_BEFORE_FINAL_SEARCH. No final search was run.**

The user-authorized historical replay repair passed all twenty rows with exact scalar equality. The prior Part 0c STOP-3 is resolved. Work then continued through the live steps recorded below; the original clock was retained [M].

Stop / remaining work: Input manifest build ended after latest feasible verification launch [M].
Catalogue sources using historical read-only fallback: none recorded [M].

Resume: **Part 0e input verification and eligibility**. No owner alive; no routine armed [M].

## Original clock [M]

- t0_utc: `2026-09-22T21:14:59.3552628Z`
- engineering_deadline_utc: `2026-09-22T23:44:59.3552628Z`
- live_launch_close_deadline_utc: `2026-09-23T00:49:59.3552628Z`
- owned_jobs_stop_deadline_utc: `2026-09-23T00:59:59.3552628Z`
- handoff_deadline_utc: `2026-09-23T01:14:59.3552628Z`

## Part 0a entry measurements

| Check | Expected [A] | Observed at original entry [M] |
|---|---|---|
| Branch / HEAD | improve/recovery / 863c01be5 | improve/recovery / 863c01be55f4455b482ad9edc764da20296fe6ec |
| Tracked tree | Clean | Clean; listed untracked paths retained |
| Listed untracked FA arrays | Retain all | 2509 |
| Git maintenance.auto / gc.auto / gc.autoDetach | false / 0 / false | false / 0 / false |
| Python | 3.13.3 | 3.13.3 |
| CPU physical / logical; RAM | Remeasure | 24 / 32; 68484653056 bytes |
| C / D free storage | Above configured floors | 53519015936 bytes / 973086490624 bytes |
| Python processes / historical owners | None / none | None / none |
| Historical automations | Both PAUSED | Both PAUSED; original TOML hashes retained |
| Three population pins | Match section 0a | All three matched |
| P9 verification SHA-256 | Unchanged | 5e600fa200955f10feacaa58dec953bafb8e5ba7552d6e816a5a4e3b3581ac08 |
| Historical tests | 891 passed, 1 skipped | 891 passed, 1 skipped |
| P10.3 tests | Initially 116; approved correction 118 | 118 passed on original and repeat collection; original stop retained |

## Resolved check and verification

| Check | Expected [A] | Observed [M] |
|---|---|---|
| P12 tests | All required checks pass, none skipped | 143 passed, 0 failed, 0 skipped |
| Historical compatibility | 891 passed, 1 skipped | 891 passed, 1 skipped |
| P10.3 tests | Amended expectation 118 | 118 passed |
| Historical injection replay | 20 sealed rows, full period/window scoring | 20/20 exact, every scalar outcome field |
| Entry/final historical integrity | 0 mismatches | PASS / PASS, 0 mismatches |
| Redirected P9 verification | 397 checks; only baseline_git_HEAD_unchanged fails | Matched at entry and final |
| Shutdown | DISABLED_VERIFIED | No owner; no science process; no active routine |

The test now executes p12/tests/B_authorized_historical_replay.py rather than accepting a stored status flag. The evaluator verifies both the historical search seal and the calibration seal before reading the same twenty selected cases; period/window recovery, expected SNR, pre-gate and funnel fields agree exactly. No threshold or expected outcome changed [M].
The eligibility report now separates unique calibration_hosts from calibration_injections; a repeated-host fixture verifies the distinction [M].

## Amendment, prior stops and exposure

The approved 116-to-118 amendment remains in force. The two tests are test_trace_witness_is_distinct_from_final_selection and test_logged_gate_survivor_and_selection_witness, introduced in ddf4050eabef176fb10102732b4f4690d61e277e. Scientific entry HEAD: 863c01be55f4455b482ad9edc764da20296fe6ec [M].
count corrected to the live tracked suite; no test file changed since the seal
PROMPT_P12.md SHA-256: `8be9b707fa7da8a4c0e86e182f92963e21ec3f6fc4c799d52dda5612354b68a3` [M].
The original count STOP-3 and its resolution remain preserved. The subsequent replay stop, handoff, seals and receipt from af39ce8c9f26746c2b1402ef3da04e89ff6cf68f are archived in p12/manifests/sprint_stop_20260922_224608/. E3 records the latest user authorization; historical_replay_stop_resolution.json records the passing repair [M].
The original unintended report reads remain exactly DECISION_P10_3.md lines 1–92, FUNNEL_RETENTION_P10_3.md lines 1–60 and AUTOPSIES_P10_3.md lines 1–18 under p10/part3/. None of those reports was guarded truth [M].
E3 subsequently authorized the lead evaluator to read embedded calibration truth for the same twenty historical injection cases. Those reads are explicitly ledgered; blind-worker guards remain unchanged. P9 truth was not opened by this evaluator. Any Part 0 catalogue/negative-set preparation uses its original script-only authorization and ledger [A/M].

## Live Part 0 status [M]

| Step | Status |
|---|---|
| 0a | CLOSED: approved 118-count amendment |
| 0b | CLOSED: D-drive workspace |
| 0c | CLOSED for sprint lanes: 143 passing tests; 19 later-part modules remain open |
| 0d | CLOSED |
| 0e | PARTIAL: core frozen; verification not launched within original clock |
| 0f | NOT RUN |
| 0g | NOT RUN: timing-pilot dependencies remain open |
| 0h | NOT RUN: live forecast inputs incomplete |

Aggregate measurements (no per-candidate records displayed):

```json
{
  "controller_closures": {
    "catalog_snapshot": {
      "status": "CLOSED",
      "total": 1,
      "completed": 1,
      "pending": 0,
      "unknowns": 0,
      "queue_hours": 0.16658817361110576,
      "all_owned_workers_closed": true,
      "source_hashes_unchanged": true
    }
  },
  "catalog_summary": {
    "fallback_sources": [],
    "historical_catalogue_hashes_unchanged": true
  },
  "hard_stop_counts": {
    "CLEAN": 2000,
    "FLAG": 436
  },
  "hard_stop_source_counts": {
    "p8_2000": {
      "CLEAN": 2000
    },
    "p10_436": {
      "FLAG": 436
    }
  },
  "prepared_verification_jobs": 2436,
  "eligibility_summary": null,
  "probe_summary": null,
  "ttt_summary": null,
  "live_receipt_hashes": {
    "p12/manifests/catalog_versions_p12.json": "e9abaab869b15b0be004959c2f5ee25d1e62a7ece96e573808fc50a456415bdf",
    "p12/manifests/catalog_hashes_before.json": "8d1c6652e8719eaeb6578c3938f6067f2dcaa53a53efd00cb16d11aa943bec52",
    "p12/manifests/catalog_hashes_after.json": "8d1c6652e8719eaeb6578c3938f6067f2dcaa53a53efd00cb16d11aa943bec52",
    "p12/manifests/hard_stop_p12.json": "34901688c830d162423d4cddf6173040157fb89a20386c1c9c2d7b98b30c9f0f",
    "p12/manifests/targets_p12_core.csv": "c4936c14a68dadf3a5aab0d29615e001a4a2e4a910b4071afff76d3ac14291b9",
    "p12/manifests/verify_core_jobs.json": "e5faab270ca37d04089f9fc6a649ddbbf63b59b3c2cb1833d590e3b5008bee09",
    "p12/manifests/verify_core_not_launched.json": "3c6a7e0fb23022dc277f04fdaea14467c63d4419e9aaba9974785d5e8fa2f522"
  }
}
```

No timing pilot, Part 0h forecast, population decision, calibration search, held-out search or final search was completed. Missing measurements remain unmeasured. Per-star coverage above sector 105 cannot be inferred from directory-list membership; when absent, it is reported UNMEASURED, never zero [M].

## Module status [M]

| Module | Status | Passed / failed | Evidence |
|---|---|---:|---|
| p12_common.py | done and tested | 3 / 0 | test_common_p12.py |
| config.json | done and tested | 3 / 0 | test_common_p12.py |
| diff_origins_p12.py | done and tested | 3 / 0 | test_common_p12.py |
| controller_p12.py | done and tested | 9 / 0 | test_controller_p12.py |
| guards_p12.py | done and tested | 5 / 0 | test_guards_p12.py |
| checkin_p12.py | done and tested | 13 / 0 | test_supervision_p12.py |
| continuation_p12.py | done and tested | 13 / 0 | test_supervision_p12.py |
| final_shutdown_p12.py | done and tested | 13 / 0 | test_supervision_p12.py |
| recover_p12.py | done and tested | 3 / 0 | test_recover_p12.py |
| blind_io_p12.py | done and tested | 10 / 0 | test_blind_io_p12.py |
| integrity_check_p12.py | done and tested | 8 / 0 | test_integrity_p12.py |
| register_p12.py | done and tested | 4 / 0 | test_register_p12.py |
| p9_verify_p12.py | done and tested | 8 / 0 | test_integrity_p12.py |
| ledger_p12.py | done and tested | 7 / 0 | test_ledger_p12.py |
| policy_products_p12.py | done and tested | 3 / 0 | test_policy_products_p12.py |
| build_input_jobs_p12.py | done and tested | 4 / 0 | test_input_p12.py |
| verify_prepare_p12.py | done and tested | 4 / 0 | test_input_p12.py |
| input_identity_p12.py | done and tested | 4 / 0 | test_input_p12.py |
| download_star_p12.py | done and tested | 7 / 0 | test_download_p12.py |
| build_batches_p12.py | done and tested | 7 / 0 | test_download_p12.py |
| neighbours_worker_p12.py | done and tested | 3 / 0 | test_neighbours_p12.py |
| neighbours_batch_worker_p12.py | done and tested | 3 / 0 | test_neighbours_p12.py |
| blind_search_worker_p12.py | done and tested | 9 / 0 | test_search_p12.py |
| lock_predictions_p12.py | done and tested | 9 / 0 | test_search_p12.py |
| prepare_injections_p12.py | done and tested | 2 / 0 | test_injections_p12.py |
| score_injections_p12.py | done and tested | 9 / 0 | test_injections_p12.py |
| sml_p12.py | done and tested | 4 / 0 | test_sml_p12.py |
| catalog_snapshot_p12.py | done and tested | 12 / 0 | test_catalog_p12.py |
| build_sidecar_p12.py | done and tested | 12 / 0 | test_catalog_p12.py |
| crossmatch_p12.py | done and tested | 12 / 0 | test_catalog_p12.py |
| catalog_adapter_p12.py | done and tested | 12 / 0 | test_catalog_p12.py |
| targets_p12.py | done and tested | 28 / 0 | test_targets_p12.py |
| fetch_ttt_p12.py | done and tested | 28 / 0 | test_targets_p12.py |
| sector_probe_p12.py | done and tested | 28 / 0 | test_targets_p12.py |
| funnel_plan_p12.py | open | 0 / 0 |  |
| funnel_worker_p12.py | open | 0 / 0 |  |
| stage_c_plan_p12.py | open | 0 / 0 |  |
| stage_c_worker_p12.py | open | 0 / 0 |  |
| close_stage_c_p12.py | open | 0 / 0 |  |
| stage_d_worker_p12.py | open | 0 / 0 |  |
| stage_d_packets_p12.py | open | 0 / 0 |  |
| rules_p12.py | open | 0 / 0 |  |
| k10_p12.py | open | 0 / 0 |  |
| tier_rederivation_p12.py | open | 0 / 0 |  |
| retention_p12.py | open | 0 / 0 |  |
| tce_families_p12.py | open | 0 / 0 |  |
| compare_arms_p12.py | open | 0 / 0 |  |
| heldout/ | open | 0 / 0 |  |
| freeze_p12.py | open | 0 / 0 |  |
| launch_bar_p12.py | open | 0 / 0 |  |
| candidate_list_p12.py | open | 0 / 0 |  |
| seals_p12.py | open | 0 / 0 |  |
| reports_p12.py | open | 0 / 0 |  |

Per-module counts overlap and must not be summed. All 19 later-part modules remain open under the bounded sprint scope. Exact tests:

- `test_blind_io_p12.py::test_guard_caught_open_still_fails_job`
- `test_blind_io_p12.py::test_normal_python_import_is_allowed`
- `test_blind_io_p12.py::test_protected_registered_paths[data/cache/catalogs/spoc_tce/spoc_tce.ephemerides.csv]`
- `test_blind_io_p12.py::test_protected_registered_paths[data/survey/injections_p8.csv]`
- `test_blind_io_p12.py::test_protected_registered_paths[data/survey/p10/injections_2b.csv]`
- `test_blind_io_p12.py::test_protected_registered_paths[data/survey/p12/calibration/archival/truth/case.json]`
- `test_blind_io_p12.py::test_protected_registered_paths[data/survey/p12/catalogs/spoc_tce/spoc_tce.ephemerides.csv]`
- `test_blind_io_p12.py::test_protected_registered_paths[data/survey/p12/negatives/ttt_downloads/2506.05631.eprint.tar]`
- `test_blind_io_p12.py::test_protected_registered_paths[data/survey/p12/negatives/ttt_table.json]`
- `test_blind_io_p12.py::test_protected_registered_paths[p9/truth/final_truth.csv]`
- `test_catalog_p12.py::test_bare_tce_without_ephemerides_flags_without_k0`
- `test_catalog_p12.py::test_cache_redirect_to_p12_data_path`
- `test_catalog_p12.py::test_combined_population_falls_back_from_nan_coordinate_aliases`
- `test_catalog_p12.py::test_f7_has_only_available_fields_and_valid_alias`
- `test_catalog_p12.py::test_fallback_rejects_unpinned_date`
- `test_catalog_p12.py::test_mixed_tce_and_toi_keeps_reject`
- `test_catalog_p12.py::test_redaction_never_loads_catalogue`
- `test_catalog_p12.py::test_sidecar_uses_origin_schema_and_only_new_destination`
- `test_catalog_p12.py::test_six_sources_retry_fallback_and_historic_hashes_unchanged`
- `test_catalog_p12.py::test_snapshot_load_is_offline_and_never_refreshes`
- `test_catalog_p12.py::test_toi_rejects_and_clean_fixture_is_unchanged`
- `test_catalog_p12.py::test_unexpected_snapshot_failure_still_records_after_hashes`
- `test_common_p12.py::test_immutable_receipt_and_replace_retry`
- `test_common_p12.py::test_p12_data_junction_and_cache_redirect`
- `test_common_p12.py::test_registered_keys_and_no_queue_cap`
- `test_controller_p12.py::test_D_storage_floor_refused`
- `test_controller_p12.py::test_complete_result_and_durable_identity`
- `test_controller_p12.py::test_exact_command_identity_prevents_kill`
- `test_controller_p12.py::test_exclusive_owner`
- `test_controller_p12.py::test_missing_worker_hash_refused`
- `test_controller_p12.py::test_registered_post_part0_phase_requires_registration`
- `test_controller_p12.py::test_retry_manifest_only_operational_unknown`
- `test_controller_p12.py::test_sampled_child_closed_after_parent_exits`
- `test_controller_p12.py::test_timeout_closes_grandchildren`
- `test_download_p12.py::test_corrupt_fits_forces_redownload_and_preserves_historical_bytes`
- `test_download_p12.py::test_jobs_pin_sources_and_attempt_output`
- `test_download_p12.py::test_product_identity_failure_is_operational_unknown`
- `test_download_p12.py::test_sector_filter_and_explicit_network_gate`
- `test_download_p12.py::test_transport_retry_rule[OPERATIONAL_UNKNOWN-ConnectionError-True]`
- `test_download_p12.py::test_transport_retry_rule[OPERATIONAL_UNKNOWN-ValueError: bad shape-False]`
- `test_download_p12.py::test_transport_retry_rule[TIMEOUT--True]`
- `test_guards_p12.py::test_durable_integrity_failure`
- `test_guards_p12.py::test_freeze_hash_refusal`
- `test_guards_p12.py::test_freeze_required[bar_endpoint]`
- `test_guards_p12.py::test_freeze_required[final_search]`
- `test_guards_p12.py::test_freeze_required[neg_ttt]`
- `test_injections_p12.py::test_failed_search_stays_operational_unknown`
- `test_injections_p12.py::test_five_unchanged_calibration_hosts_equal_p10`
- `test_injections_p12.py::test_injection_changes_both_flux_streams_only_in_transit`
- `test_injections_p12.py::test_recovery_period_and_window_rules[0.3333333333333333-0.2-alias]`
- `test_injections_p12.py::test_recovery_period_and_window_rules[0.5-0.2-alias]`
- `test_injections_p12.py::test_recovery_period_and_window_rules[1.0-0.2-recovered]`
- `test_injections_p12.py::test_recovery_period_and_window_rules[1.0-0.45-missed]`
- `test_injections_p12.py::test_recovery_period_and_window_rules[2.0-0.2-alias]`
- `test_injections_p12.py::test_recovery_period_and_window_rules[3.0-0.2-alias]`
- `test_injections_p12.py::test_required_twenty_sealed_rows_full_period_window_replay`
- `test_injections_p12.py::test_twenty_sealed_outcome_rows_level_algebra`
- `test_input_p12.py::test_five_sealed_436_status_and_prepared_sha256`
- `test_input_p12.py::test_identity_time_flux_quality_and_v02`
- `test_input_p12.py::test_input_job_inventory_includes_both_c_and_redirected_d_cache`
- `test_input_p12.py::test_missing_store_is_input_ineligible`
- `test_integrity_p12.py::test_documented_seal_serializations[count_and_hashes]`
- `test_integrity_p12.py::test_documented_seal_serializations[list]`
- `test_integrity_p12.py::test_documented_seal_serializations[map]`
- `test_integrity_p12.py::test_documented_seal_serializations[records]`
- `test_integrity_p12.py::test_documented_seal_serializations[single]`
- `test_integrity_p12.py::test_original_writer_redirected_before_execution`
- `test_integrity_p12.py::test_p9_check_body_unchanged_except_output_destination`
- `test_integrity_p12.py::test_p9_output_only_adapter_fixture`
- `test_ledger_p12.py::test_after_part2_missing_or_excessive_ratio_refused[3.01]`
- `test_ledger_p12.py::test_after_part2_missing_or_excessive_ratio_refused[None]`
- `test_ledger_p12.py::test_forecast_margin_and_ratio_ceiling`
- `test_ledger_p12.py::test_measured_counts_and_stage_conversion`
- `test_ledger_p12.py::test_pilot_never_lowers_registered_unit`
- `test_ledger_p12.py::test_queue_units_divide_concurrency_once`
- `test_ledger_p12.py::test_reduced_calibration_retains_real_host_and_C_costs`
- `test_neighbours_p12.py::test_batch_retains_failure_receipt`
- `test_neighbours_p12.py::test_bulk_coverage_and_p12_destinations`
- `test_neighbours_p12.py::test_per_star_requires_both_bulk_sources`
- `test_policy_products_p12.py::test_excluded_qlp_and_failed_preferred_never_returned`
- `test_policy_products_p12.py::test_install_both_exactly_one_star_and_restore`
- `test_policy_products_p12.py::test_policy_refuses_changed_raw_and_changed_selection`
- `test_recover_p12.py::test_interrupted_phase_preserves_costs_and_complete_results`
- `test_recover_p12.py::test_owner_without_launch_fails_closed`
- `test_recover_p12.py::test_recycled_owner_stops_without_reconciliation`
- `test_register_p12.py::test_registration_roundtrip_preserves_existing_ledger`
- `test_register_p12.py::test_registration_tamper_refused[membership]`
- `test_register_p12.py::test_registration_tamper_refused[prompt]`
- `test_register_p12.py::test_registration_tamper_refused[python]`
- `test_search_p12.py::test_lock_changed_prepared_refused`
- `test_search_p12.py::test_lock_complete_and_idempotent_seal`
- `test_search_p12.py::test_lock_guarded_open_fails_even_when_no_worker_receipt`
- `test_search_p12.py::test_lock_merges_one_immutable_attempt2`
- `test_search_p12.py::test_lock_nonclosed_phase_refused`
- `test_search_p12.py::test_lock_requires_closure_and_preserves_unknowns`
- `test_search_p12.py::test_original_forbidden_read_cannot_be_erased_by_retry`
- `test_search_p12.py::test_worker_guard_blocks_synthetic_truth_runtime`
- `test_search_p12.py::test_worker_refuses_runtime_hash_before_science`
- `test_sml_p12.py::test_missing_column_stays_archival`
- `test_sml_p12.py::test_mixed_aperture_two_qlp_fits_and_spoc_only_flux_changes`
- `test_sml_p12.py::test_sml_tampering_other_arrays_refused`
- `test_sml_p12.py::test_store_reuses_verified_bytes_and_extends_index`
- `test_supervision_p12.py::test_checkin_trigger_table[closed-ADVANCE dummy]`
- `test_supervision_p12.py::test_checkin_trigger_table[healthy-SLEEP]`
- `test_supervision_p12.py::test_checkin_trigger_table[integrity-PAUSE STOP-1 INTEGRITY_FAILURE]`
- `test_supervision_p12.py::test_checkin_trigger_table[missing_owner-PAUSE OWNER_GONE_WITHOUT_CLOSURE]`
- `test_supervision_p12.py::test_checkin_trigger_table[pilot-PAUSE decision_point_1]`
- `test_supervision_p12.py::test_checkin_trigger_table[storage-PAUSE STORAGE_WITHIN_3GB]`
- `test_supervision_p12.py::test_checkin_trigger_table[user_stop-PAUSE STOP-4 USER_STOP]`
- `test_supervision_p12.py::test_printed_checkin_contract`
- `test_supervision_p12.py::test_sequence_rejects_forward_dependency`
- `test_supervision_p12.py::test_sequence_skips_false_branch_without_reordering`
- `test_supervision_p12.py::test_shutdown_absent_routine_and_historical_paused`
- `test_supervision_p12.py::test_shutdown_active_routine_refused`
- `test_supervision_p12.py::test_stall_stops_only_owned_worker_then_pauses`
- `test_targets_p12.py::test_core_reject_removal_and_partial_preparation_remains_unknown`
- `test_targets_p12.py::test_extension_cuts_allow_missing_lumclass_and_negative_latitude_boundary`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change0]`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change1]`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change2]`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change3]`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change4]`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change5]`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change6]`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change7]`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change8]`
- `test_targets_p12.py::test_extension_cuts_preserve_exact_origin_boundaries[change9]`
- `test_targets_p12.py::test_extension_ranking_uses_policy_count_radius_noise_and_tic_ties`
- `test_targets_p12.py::test_population_csv_refuses_silent_changed_content`
- `test_targets_p12.py::test_sector_listing_missing_membership_is_unmeasured`
- `test_targets_p12.py::test_sector_probe_requires_explicit_online_execution`
- `test_targets_p12.py::test_sector_probe_two_lists_no_per_star_requests`
- `test_targets_p12.py::test_ttt_does_not_apply_novelty_cut_to_known_negatives`
- `test_targets_p12.py::test_ttt_hash_order_core_exclusion_and_first30`
- `test_targets_p12.py::test_ttt_machine_readable_tic_and_period_parser`
- `test_targets_p12.py::test_ttt_never_relaxes_radius_latitude_coverage_or_ffi_majority[change0]`
- `test_targets_p12.py::test_ttt_never_relaxes_radius_latitude_coverage_or_ffi_majority[change1]`
- `test_targets_p12.py::test_ttt_never_relaxes_radius_latitude_coverage_or_ffi_majority[change2]`
- `test_targets_p12.py::test_ttt_never_relaxes_radius_latitude_coverage_or_ffi_majority[change3]`
- `test_targets_p12.py::test_ttt_never_relaxes_radius_latitude_coverage_or_ffi_majority[change4]`
- `test_targets_p12.py::test_ttt_parse_failure_preserves_download_identity`
- `test_targets_p12.py::test_ttt_relaxation_sequence_teff_then_tmag_and_inclusive_bounds`
- `test_targets_p12.py::test_ttt_relaxations_stop_at_teff_when20_qualify`

## Cost and remaining work

Controller queue-hours: 0.166588; summed job-wall hours: 0.166573 [M]. These are distinct quantities. Resource intervals, source hashes and disk readings remain in committed receipts. No calendar completion date is promised.

1. Resume the first unfinished Part 0 item stated above, respecting any recorded operational stop and the original clock or an explicit later-session amendment.
   The core CSV, per-star input manifests and verify_core_jobs.json are already complete. Verify their recorded hashes and reuse them; the exclusive writers must not be rerun into those destinations. No verify_core controller was launched and no verification launch receipt exists. A later session needs a launcher with its recorded execution window; wait_resumed_phase.ps1 intentionally retains this sprint's expired launch cutoff.
   Run verify_core with 8 workers and its unchanged 600-second per-job deadline, close every owned identity, then aggregate targets_p12.py core, rank targets_p12.py extension, and continue 0f. Advance only after an unrecovered closure with completed == total, pending == 0 and unknowns == 0.
2. Complete the timing-pilot dependencies and their required historical parity tests before running pilot_search/pilot_A. No live worker source may be edited while it runs.
3. Only measured eligibility, negative-set and timing inputs permit 0h and decision point 1. The user chooses the population tier there.
4. Review the recorded controller/check-in limits before future retry or recovered-phase auto-advancement; this resumption advances only an unrecovered closure with zero pending/unknowns and completed == total.

## Protocol/test SHA-256 [M]

| File | SHA-256 |
|---|---|
| p12/protocol/__pycache__/blind_io_p12.cpython-313.pyc | ab4872097ba40f65981f964f60ca6eacb6191e252cbd65ecde52b05467668858 |
| p12/protocol/__pycache__/controller_p12.cpython-313.pyc | 1e6fbdf3902e2323fe433d0c73677845e1ef68db8d152956638986e54aa2f856 |
| p12/protocol/__pycache__/guards_p12.cpython-313.pyc | 2ce111f875333d73cb672e3824aa4a5e37c3d78e1b6c8a88fe001948a1fdea69 |
| p12/protocol/__pycache__/p12_common.cpython-313.pyc | a8d9ffadbc5f87161c5447385f62bf2def0ee435b60dc040264d63454a89f698 |
| p12/protocol/AMENDMENTS_P12.md | 1c0fc7e6ec528dc00c76cfe92901aafe62ae255c2b1b1042ad6c7510c589fa0d |
| p12/protocol/blind_io_p12.py | 7235bfb24c7c97ade3d767b1e0a7d94a3a96737152dc38c7795906c9ea8c9177 |
| p12/protocol/blind_search_worker_p12.py | b760b27a14900fe9f9171c59d4525ff67c60fb2894b75869469291ffdc71ea42 |
| p12/protocol/build_batches_p12.py | 24cfa7cad3794b53ef0931430a8bdc6f472dc8765847964ea72ad495070cce1a |
| p12/protocol/build_input_jobs_p12.py | 961507c0fd23c804cdf14385f59752d030a948684c5b6d1fe9333565cc5ff3f2 |
| p12/protocol/build_sidecar_p12.py | ef1df06f1ee04d66579faa27c64cc85190ad62db9f85f0db5c9ff65c9c0d56cc |
| p12/protocol/catalog_adapter_p12.py | a5923b6fcae9ab76f90f69b4aa2b3e6edaf9012bb66abe68aafc9c1e82ae83df |
| p12/protocol/catalog_snapshot_p12.py | 479c8bbd050bdca9491a41bd047f61ff0be33e52e434a26d79e2f7503d0e1633 |
| p12/protocol/checkin_p12.py | fd51ccf1f3bfac11e95713d38d905128b79bd67f898333e3e34613c5611a6586 |
| p12/protocol/config.json | 93d8d21a54cf9c4ad795bb46c24bc0d1c1cd7520995598704ab6a1d8ff9a5c69 |
| p12/protocol/continuation_p12.py | 53abfcafd0e3d4842b92b20acb18041f0dd8567a85d6c5dca2030dec3f83142d |
| p12/protocol/controller_p12.py | 913117acec0f4ac6d5d4eb8b2910eff27ad0e02390278c8a57aaed2a5edf02c4 |
| p12/protocol/crossmatch_p12.py | 3e2072cce1257c82dc74dbfe9c3340ab95e72f5d82796915d538bb36c69a4dbc |
| p12/protocol/diff_origins_p12.py | 579084b453a00eef21ce0cfe566ddf8a3d3f0961000cc97b5ebbc31fe06823b3 |
| p12/protocol/download_star_p12.py | ec63655286354ed6177a17a828a9415b14fd9c1700a45bb49ad428344f4f6782 |
| p12/protocol/fetch_ttt_p12.py | da1630459f4370cfaae6b552dc695e6ad04b74858ea8647e9f221c15ce5a05f8 |
| p12/protocol/final_shutdown_p12.py | 0877c0f679e7e6014e467aa29a60aedf75b29639b649efd907ccb57133ff8446 |
| p12/protocol/guards_p12.py | c165689699aa71473f9547a87f9f6479715a53c2e85512d32c106afd19e7939e |
| p12/protocol/input_identity_p12.py | e980ed8b28e05c0d3aedc48eb4825c2fd6990e440c13e29d9c54e16105e23698 |
| p12/protocol/integrity_check_p12.py | 55260f1a946ed800607960db96bca283fe382efcedd61dbbaace6307cb460598 |
| p12/protocol/INTERFACES_P12.md | e566d80636fa8e043b686f250571a16b3a0009dbac5bd49a20c7028ef7c8b7dc |
| p12/protocol/ledger_p12.py | 7460e04ee36b9e8c70cd1103e5997a3319dc85d3222ddb0bf1bc45c76c358151 |
| p12/protocol/lock_predictions_p12.py | ecd8a36cfde65e937d41ee92f84817a112165b4bc8d544e483d80535852fd8d8 |
| p12/protocol/neighbours_batch_worker_p12.py | 59786512ce418ee840c9caa2ca81b5a83b6cdd8f1afd4e1fbfdb37ebb9385a9f |
| p12/protocol/neighbours_worker_p12.py | 25d4e656a26a4f54aa3dcc10a5c70d35832217452ea8186f69858b5155309801 |
| p12/protocol/p12_common.py | c61ee5ca60802ce081dcbf17a20d0855457c1bcad6c50942c9a5fe8c93af97f3 |
| p12/protocol/p9_verify_p12.py | 19384f5fd1aad665b31f8bbf35cd8c6537ac7a6d98ca5bc40ae7f0643258dbfc |
| p12/protocol/policy_products_p12.py | d544e896043c33f6dd718f8ab69138c5631244293c77fe99dd0ac2ec1d5d5e50 |
| p12/protocol/prepare_injections_p12.py | 3188611aab96c0346c2b510613dfdfc70feeffd3519fa64549d2dd3f0dd1853e |
| p12/protocol/recover_p12.py | 5609f5da50c200464a1d20272d954b6b2873fb5d70ecba14b35c4e1d135172dd |
| p12/protocol/register_p12.py | 78c484b0900004fecfa3c81775e83b5ab4fff08121ab53ed3210c7b02a4b8f28 |
| p12/protocol/score_injections_p12.py | 97cfa35f63e0bd3ba83f4d91ef8742c4542a8d75a02c3d7257ffad4ce1af4422 |
| p12/protocol/sector_probe_p12.py | db74921d89a5f4a026abf772aedc01e0694fa7b478eb5ff52cfc43e756d54bf3 |
| p12/protocol/sml_p12.py | 18fbeac0a3946b925b3743504611e098ea7f6a854232251ed9094053b4509c27 |
| p12/protocol/targets_p12.py | 0ae6ae2d9bff0d124512a2acd95e4f524ed4930cb0ab2cb7ba4612c1e953766e |
| p12/protocol/verify_prepare_p12.py | fbbbefb85094863f73083d2f88083212aa17d0055d450fa43dee1401c79774b0 |
| p12/tests/A_dummy_worker.py | 616171183ea10903aa6c166bb9d682cb56db2c23aeb2e8734a300f990b5ae7d3 |
| p12/tests/B_authorized_historical_replay.py | 655df191fa716765e2bbbf6c5ec56253d70d32726c04b7559c0ebbe7eb8e92e4 |
| p12/tests/B_exposure_ledger.jsonl | d222abcb5416435d8d2c048e88fe07e737f6273ca745c8692dcbffb4973c4fa1 |
| p12/tests/B_fixtures.py | a8e1efa8240f13f732d5514fbc56052150da34892be7d0fb73c8a3e3ffe75804 |
| p12/tests/B_lane_closeout.json | 6598ebf9ced5b4f0cf255ae1de57d366cb1563ca3add43ee960bdc1847c8753a |
| p12/tests/B_required_historical_replay.json | cf003db864b7681baf5eae25fa0cdc96aa60efccc4f014cd757761a0efa3b874 |
| p12/tests/B_sealed_replay.py | e0120679a60da8b28ffb7666ebe7c087744542dca86dcc3121a34ba6f34e438f |
| p12/tests/B_search_entry.py | fd08d4814e557ea324d23c72af49dbc49a5c335a8cd2a0c9c1245bf111691ffa |
| p12/tests/conftest.py | 15856c12a4d8707320bcf9d91227fe60c703f5cdcb6a66c7f18e231e61349f63 |
| p12/tests/test_blind_io_p12.py | 15f0cdbd59094a7410a538a3508c17280b14e8323c9e3b424d9aeb21eee64692 |
| p12/tests/test_catalog_p12.py | f049909ae7b04b24b3c74c982f01093052d23ddba248cdebd750fc666ca53b9e |
| p12/tests/test_common_p12.py | bf02294ee5146385a7ad0682fde772002903366e41daf0f9cf001482d3217649 |
| p12/tests/test_controller_p12.py | aac0a12c3bb817c751702894c908400092f2eabb980c0bb399f2e802abb9b781 |
| p12/tests/test_download_p12.py | c4d017acac1396a7a3637f6626665d4973bd73cf6bf6bd03db6c7aa3f08d7a5a |
| p12/tests/test_guards_p12.py | 71d9b877c568a0bdc8df31284b62a7193dbc1e5e761f189f10a6ce9425557ec5 |
| p12/tests/test_injections_p12.py | 5310fdc33b2ab76f03df59599ba5905148b07861e67bb723511dd2a68132e00d |
| p12/tests/test_input_p12.py | dc5ec1dd11c2fde7eb2ec3cd3d0591e38509101d8ae7258dfcb26860c9b4a4cb |
| p12/tests/test_integrity_p12.py | fcc06367814952c1c0026d509a2110a42c430da5453a20be1a3d23db6e605dc6 |
| p12/tests/test_ledger_p12.py | 352f7e00daea9f3da1e023b7fda25e0e76f3d04706695768b9d3016b1ecc5ac2 |
| p12/tests/test_neighbours_p12.py | c897ba4b52be0ce21a1ba51c2c406715c4b36989202209e84f92267681fedc45 |
| p12/tests/test_policy_products_p12.py | f3ebbd21f7474aa82392fb36abb930d9ab2da69b6b4143b2a88f2ce977f6be0c |
| p12/tests/test_recover_p12.py | 7516a951498bcbb130578d6920187e278ac81682a5784e61581e7778571781fd |
| p12/tests/test_register_p12.py | 5ab047f2184a9fe8a4ffe29f61d9e5fe232bcd2763e65196cc5d1c851e627558 |
| p12/tests/test_search_p12.py | d75722a4aae794a02d0cc3fe057933f27ca43da774c37da13971c1cc1e3f0969 |
| p12/tests/test_sml_p12.py | fe7d9480ac8e69aa1981c1c055d1a91258d3ca0af2d8427254f1af25e6419d3d |
| p12/tests/test_supervision_p12.py | 706f902687e3a061cf3f5f279821d09f75b691f106515549ba2884b5b0c64b09 |
| p12/tests/test_targets_p12.py | 9ed05ff121cc5aeb36b46ae28a30b5e8d936b7c31606051e1ee5ca6e693f1e89 |

## Commit and resume

One local commit at the end of this resumption, with the required Git maintenance flags. Stage only p12/, HANDOFF_P12.md and RESUME_P12.md. No push.
Post-commit git status --short is recorded in p12/logs/git_status_after_resumption_commit.txt [M].

resume here: Part 0e input verification and eligibility; no owner alive; no routine armed
