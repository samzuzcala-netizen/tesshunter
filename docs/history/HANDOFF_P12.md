# HANDOFF_P12. Final state: FINAL_SEARCH_DELIVERED_BAR_NOT_MET

> **Added by the session at final delivery (2026-10-01), not by the frozen generator:** every post-freeze operation, the three STOP decisions (STOP-4 CONTINUE, STOP-7 on LB3 CONTINUE, STOP-7 on final Stage B REPAIR), the 54 repaired Stage B cases, the frozen-code defects worked around without changing frozen bytes, and the finalization at decision point 3 are in `p12/results/POST_FREEZE_INCIDENTS_P12.md` (machine record `p12/manifests/post_freeze_operations.jsonl`).


Written 2026-10-01T09:25:25.330248+00:00 by `p12/protocol/report_handoff_p12.py`.

## What shipped [M]

- The candidate list `p12/results/candidates_p12.csv`: {"REJECT_PREGATE": 21869, "REJECT_A": 5304, "REJECT_S": 573, "REJECT_C": 62, "UNKNOWN": 22, "NO_ACCEPTED_SIGNAL": 2, "KILL": 8, "HOLD": 8, "SUBMIT tier 2": 2, "INPUT_INELIGIBLE": 378}.
- The launch bar `p12/results/part4/launch_bar.json`: bar_met = False; failing []; not decisive ['LB1a', 'LB1b', 'LB2b', 'LB3'].
- `p12/results/COMPLETENESS_P12.md`, `p12/results/SPECIFICITY_P12.md`, `docs/AUDIT_P12.md`, the packets under `docs/packets/audit_p12/`, the seals and the cost ledger.

## What was measured [M]

- Photometry decision: KEEP_ARCHIVAL ().
- K10: K10_FLAG.
- Plumbing: MATCH with 4 registered live-measurement update(s).
- Queue-hours, all parts: 168.28997285647247.

## What was refuted or not measured [M]

- Launch-bar clauses not decisive: ['LB1a', 'LB1b', 'LB2b', 'LB3'] (a clause that is not decisive never counts as a pass).
- Stop receipts: ['stop_3_entry.json', 'stop_3_integration.json', 'stop_STOP-4_20260924T152709.json', 'stop_STOP-6_20260923T165952Z.json', 'stop_STOP-7_20260926T194951Z.json', 'stop_STOP-7_20260930T015624Z.json', 'stop_controller_cal_a_A.json', 'stop_controller_plumbing_d.json', 'stop_controller_plumbing_d_resume.json', 'stop_normal_exposure.json'].

## What is open [A]

- The registered P12 work on these inputs is complete; these measurements bound what it can find, and the specific experiments that could move those bounds are pixel-level photometry, the only untested input change with a measured noise lever; a detrending-window test on the 2b instrument (about 20 queue-hours); an unexposed in-domain truth-positive set, which the records do not contain.

## The three decision points [M]

1. Launch approval after Part 0: the user chose tier E1 (2026-09-23T15:42:19.855637+00:00).
2. Stop rules: STOP-6 on plumbing_d (a pricing defect, 2026-09-23); the user wrote "continue" and the phase resumed after its fix (AMENDMENTS_P12.md). Other stops: ['stop_3_entry.json', 'stop_3_integration.json', 'stop_STOP-4_20260924T152709.json', 'stop_STOP-6_20260923T165952Z.json', 'stop_STOP-7_20260926T194951Z.json', 'stop_STOP-7_20260930T015624Z.json', 'stop_controller_cal_a_A.json', 'stop_controller_plumbing_d.json', 'stop_controller_plumbing_d_resume.json', 'stop_normal_exposure.json'].
3. Final delivery: pending the user (the next message).

## Environment [M]

- Entry: {}.
- Exit: C: free 101.9 GB; D: free 795.5 GB.

## Exposure ledger [M]

64958 rows; by reader: {"lead": 12, "test_five_sealed_436_status_and_prepared_sha256": 2868, "B_sealed_replay.link_host": 4407, "test_five_unchanged_calibration_hosts_equal_p10": 2100, "test_twenty_sealed_outcome_rows_level_algebra": 140, "lane_b source inspection via Get-Content": 1, "lane_b source inspection via Get-Content -TotalCount 25": 1, "lead E3 historical replay evaluator": 613, "build_sidecar_p12.py": 1955, "crossmatch_p12.py": 436, "script Stage A engineering replay": 49, "lead tool output": 2, "lead filename inventory": 2509, "archive metadata and manuscript URL extractor": 1, "fetch_ttt_p12.py": 4578, "timing only": 65, "script-only manuscript structure inspection and ttt_eprint_attempt4_p12.py": 30, "fetch_ttt_p12.py MRT evaluator": 10001, "select_ttt_attempt5.py": 10001, "lead (Claude session) head -3 column check": 2, "lead (Claude session) schema inspection": 3, "ttt_adjacent_p12.py fetch": 10001, "ttt_adjacent_p12.py select": 10001, "test_rules_p12 reproduction": 17, "k10_p12.py calibrate": 1371, "stage_d_plan_p12.py plumbing": 60, "retention_p12.reproduce_p10_3": 1, "lead (Claude session) diagnosis": 1, "test_part2_p12 retention": 1, "agent (progress read before the registered plumbing_check)": 3, "p12/work/harness_dryrun/dryrun_run.py": 1, "p12/work/plumbing_updates.py": 2, "lead (copy only, not displayed)": 1, "tier_rederivation_p12.py": 22, "plan_part2_p12.py cases": 2181, "retention_p12.py": 872, "plan_part4_p12.py": 10, "report_ttt_p12.py ttt": 1, "report_ttt_p12.py ttta": 1, "report_p9_blind_p12.py (heldout scoring.run)": 1, "ephemeris_assisted_p12.py plan": 1, "plan_part4_p12.py fa_c": 28, "report_specificity_p12.py": 1, "plan_part5_p12.py ext_cases": 600, "plan_part5_p12.py": 5, "plan_part5_p12.py d": 1}.

## Assumptions [A]

The assumptions of PROMPT_P12.md section 9; each measured one is reported in COMPLETENESS_P12.md.

---

# PART 5 CLOSED (2026-10-01T09:08:29.058470+00:00) [M]

- `final_ext_relocation` (gate, `p12/protocol/gates_p12.py` relocation): complete [M].
- `final_e1_targets` (evaluator, `p12/protocol/plan_part5_p12.py` e1_targets): complete [M].
- `final_ext_download_pilot` (controller): CLOSED, 50 of 50 jobs, 0 operational unknowns, 0.226 queue-h [M].
- `final_ext_download_pilot_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_pilot_rates` (evaluator, `p12/protocol/plan_part5_p12.py` pilot_rates final_ext_download_pilot): complete [M].
- `final_ext_download_01` (controller): CLOSED, 100 of 100 jobs, 0 operational unknowns, 0.450 queue-h [M].
- `final_ext_download_01_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_download_02` (controller): CLOSED, 99 of 99 jobs, 0 operational unknowns, 0.451 queue-h [M].
- `final_ext_download_02_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_download_03` (controller): CLOSED, 100 of 100 jobs, 0 operational unknowns, 0.437 queue-h [M].
- `final_ext_download_03_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_download_04` (controller): CLOSED, 100 of 100 jobs, 0 operational unknowns, 0.439 queue-h [M].
- `final_ext_download_04_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_download_05` (controller): CLOSED, 100 of 100 jobs, 0 operational unknowns, 0.414 queue-h [M].
- `final_ext_download_05_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_download_06` (controller): CLOSED, 99 of 99 jobs, 0 operational unknowns, 0.433 queue-h [M].
- `final_ext_download_06_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_download_07` (controller): CLOSED, 99 of 99 jobs, 0 operational unknowns, 0.449 queue-h [M].
- `final_ext_download_07_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_download_08` (controller): CLOSED, 100 of 100 jobs, 1 operational unknowns, 0.601 queue-h [M].
- `final_ext_download_08_retry` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.013 queue-h [M].
- `final_ext_download_09` (controller): CLOSED, 100 of 100 jobs, 0 operational unknowns, 0.463 queue-h [M].
- `final_ext_download_09_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_download_10` (controller): CLOSED, 50 of 50 jobs, 0 operational unknowns, 0.221 queue-h [M].
- `final_ext_download_10_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_ext_neighbours` (controller): CLOSED, 1 of 1 jobs, 1 operational unknowns, 0.250 queue-h [M].
- `final_ext_verify` (controller): CLOSED, 1000 of 1000 jobs, 0 operational unknowns, 0.276 queue-h [M].
- `final_ext_cal_sample` (evaluator, `p12/protocol/plan_part5_p12.py` ext_sample): complete [M].
- `final_ext_cal_prepare` (controller): CLOSED, 600 of 600 jobs, 0 operational unknowns, 0.203 queue-h [M].
- `final_ext_cal_search` (controller): CLOSED, 900 of 900 jobs, 0 operational unknowns, 2.995 queue-h [M].
- `final_ext_cal_search_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `lock_final_ext_cal_search` (evaluator, `p12/protocol/lock_predictions_p12.py` final_ext_cal_search): complete [M].
- `score_final_ext_cal` (evaluator, `p12/protocol/score_injections_p12.py` archival --phase final_ext_cal_search --out p12/results/part5/injection_outcomes_ext.csv): complete [M].
- `final_ext_cal_A` (controller): CLOSED, 967 of 967 jobs, 4 operational unknowns, 1.988 queue-h [M].
- `final_ext_cal_S` (controller): CLOSED, 315 of 315 jobs, 0 operational unknowns, 0.130 queue-h [M].
- `report_extension` (evaluator, `p12/protocol/reports_p12.py` extension): complete [M].
- `final_search` (controller): CLOSED, 2788 of 2788 jobs, 0 operational unknowns, 22.547 queue-h [M].
- `final_search_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `lock_final_search` (evaluator, `p12/protocol/lock_predictions_p12.py` final_search): complete [M].
- `collect_final` (evaluator, `p12/protocol/plan_part5_p12.py` collect final_search): complete [M].
- `final_A` (controller): CLOSED, 5979 of 5979 jobs, 24 operational unknowns, 19.965 queue-h [M].
- `final_A_retry` (controller): CLOSED, 24 of 24 jobs, 22 operational unknowns, 0.334 queue-h [M].
- `final_S` (controller): CLOSED, 1183 of 1183 jobs, 0 operational unknowns, 0.407 queue-h [M].
- `final_B` (controller): CLOSED, 80 of 80 jobs, 54 operational unknowns, 0.036 queue-h [M].
- `final_C` (controller): CLOSED, 26 of 26 jobs, 2 operational unknowns, 11.782 queue-h [M].
- `final_C_retry` (controller): CLOSED, 2 of 2 jobs, 0 operational unknowns, 1.926 queue-h [M].
- `close_final_C` (evaluator, `p12/protocol/close_stage_c_p12.py` final_C): complete [M].
- `final_B_repair_neighbours` (controller): CLOSED, 1 of 1 jobs, 1 operational unknowns, 0.001 queue-h [M].
- `final_B_repair_neighbours_2` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.087 queue-h [M].
- `final_B_repair` (controller): CLOSED, 54 of 54 jobs, 0 operational unknowns, 0.010 queue-h [M].
- `final_C_repair` (controller): CLOSED, 54 of 54 jobs, 3 operational unknowns, 13.583 queue-h [M].
- `final_C_repair_retry` (controller): CLOSED, 3 of 3 jobs, 0 operational unknowns, 3.867 queue-h [M].
- `final_neighbours` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `final_D` (controller): CLOSED, 18 of 18 jobs, 0 operational unknowns, 0.883 queue-h [M].
- `final_D_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `candidate_list` (evaluator, `p12/protocol/candidate_list_p12.py` ): complete [M].
- `natural_load` (evaluator, `p12/protocol/reports_p12.py` natural_load): complete [M].
- `final_novelty` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.009 queue-h [M].
- `handoff_part_5` (evaluator, `p12/protocol/handoff_p12.py` 5): not run [M].
- `commit_part_5`: commit "prompt 12 part 5" follows this section.

Cumulative new queue-hours: 168.290 [M].


---

# PART 4 CLOSED (2026-09-27T15:18:36.434926+00:00) [M]

- `neg_ttt_inputs` (evaluator, `p12/protocol/plan_part4_p12.py` inputs ttt): complete [M].
- `neg_ttt_download` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.012 queue-h [M].
- `neg_ttt_download_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `neg_ttt_verify` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.002 queue-h [M].
- `neg_ttt_neighbours` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.013 queue-h [M].
- `neg_ttt_search` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.138 queue-h [M].
- `neg_ttt_search_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `lock_neg_ttt_search` (evaluator, `p12/protocol/lock_predictions_p12.py` neg_ttt_search): complete [M].
- `neg_ttt_A` (controller): CLOSED, 4 of 4 jobs, 0 operational unknowns, 0.021 queue-h [M].
- `neg_ttt_A_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `neg_ttt_S` (controller): CLOSED, 2 of 2 jobs, 0 operational unknowns, 0.003 queue-h [M].
- `neg_ttt_S_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `neg_ttt_B` (controller): CLOSED, 2 of 2 jobs, 0 operational unknowns, 0.002 queue-h [M].
- `neg_ttt_B_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `neg_ttt_C` (controller): CLOSED, 2 of 2 jobs, 0 operational unknowns, 0.663 queue-h [M].
- `neg_ttt_C_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `close_neg_ttt_C` (evaluator, `p12/protocol/close_stage_c_p12.py` neg_ttt_C): complete [M].
- `neg_ttt_D` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.077 queue-h [M].
- `neg_ttt_D_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `score_neg_ttt` (evaluator, `p12/protocol/reports_p12.py` ttt ttt): complete [M].
- `neg_ttta_inputs` (evaluator, `p12/protocol/plan_part4_p12.py` inputs ttta): complete [M].
- `neg_ttta_download` (controller): CLOSED, 29 of 29 jobs, 0 operational unknowns, 0.137 queue-h [M].
- `neg_ttta_download_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `neg_ttta_verify` (controller): CLOSED, 29 of 29 jobs, 0 operational unknowns, 0.010 queue-h [M].
- `neg_ttta_neighbours` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.055 queue-h [M].
- `neg_ttta_search` (controller): CLOSED, 18 of 18 jobs, 0 operational unknowns, 0.173 queue-h [M].
- `neg_ttta_search_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `lock_neg_ttta_search` (evaluator, `p12/protocol/lock_predictions_p12.py` neg_ttta_search): complete [M].
- `neg_ttta_A` (controller): CLOSED, 50 of 50 jobs, 0 operational unknowns, 0.070 queue-h [M].
- `neg_ttta_A_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `neg_ttta_S` (controller): CLOSED, 25 of 25 jobs, 0 operational unknowns, 0.008 queue-h [M].
- `neg_ttta_S_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `neg_ttta_B` (controller): CLOSED, 25 of 25 jobs, 0 operational unknowns, 0.006 queue-h [M].
- `neg_ttta_B_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `neg_ttta_C` (controller): CLOSED, 25 of 25 jobs, 0 operational unknowns, 2.488 queue-h [M].
- `neg_ttta_C_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `close_neg_ttta_C` (evaluator, `p12/protocol/close_stage_c_p12.py` neg_ttta_C): complete [M].
- `neg_ttta_D` (controller): CLOSED, 4 of 4 jobs, 0 operational unknowns, 0.079 queue-h [M].
- `neg_ttta_D_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `score_neg_ttta` (evaluator, `p12/protocol/reports_p12.py` ttt ttta): complete [M].
- `heldout_prepare` (evaluator, `p12/protocol/heldout_p12.py` prepare): complete [M].
  - `p12/manifests/heldout_source_seal.json` (SHA-256 `abc9a2fd8efdfd61…`): git_head = "ddcbbe9fe2b63f477989e688ef2e4bc4ef756f5b"; snapshot = "git archive HEAD src scripts"; n_snapshot = 128
- `neg_p9_search` (controller): CLOSED, 25 of 25 jobs, 0 operational unknowns, 0.189 queue-h [M].
- `lock_neg_p9_search` (evaluator, `p12/protocol/lock_predictions_p12.py` neg_p9_search): complete [M].
- `neg_p9_A` (controller): CLOSED, 62 of 62 jobs, 4 operational unknowns, 0.864 queue-h [M].
- `neg_p9_S` (controller): CLOSED, 13 of 13 jobs, 0 operational unknowns, 0.011 queue-h [M].
- `neg_p9_B` (controller): CLOSED, 13 of 13 jobs, 0 operational unknowns, 0.006 queue-h [M].
- `neg_p9_C` (controller): CLOSED, 13 of 13 jobs, 1 operational unknowns, 0.421 queue-h [M].
- `neg_p9_C_retry` (controller): CLOSED, 1 of 1 jobs, 1 operational unknowns, 0.025 queue-h [M].
- `neg_p9_D` (controller): CLOSED, 2 of 2 jobs, 1 operational unknowns, 0.106 queue-h [M].
- `score_neg_p9` (evaluator, `p12/protocol/reports_p12.py` p9_blind): complete [M].
- `bar_p9_eph` (controller): CLOSED, 13 of 13 jobs, 13 operational unknowns, 0.011 queue-h [M].
- `score_bar_p9_eph` (evaluator, `p12/protocol/reports_p12.py` p9_assisted): complete [M].
- `neg_fa_C` (controller): CLOSED, 28 of 28 jobs, 6 operational unknowns, 11.113 queue-h [M].
- `neg_fa_C_retry` (controller): CLOSED, 6 of 6 jobs, 0 operational unknowns, 8.395 queue-h [M].
- `close_neg_fa_C` (evaluator, `p12/protocol/close_stage_c_p12.py` neg_fa_C): complete [M].
- `neg_fa_D` (controller): CLOSED, 5 of 5 jobs, 0 operational unknowns, 0.007 queue-h [M].
- `launch_bar` (evaluator, `p12/protocol/launch_bar_p12.py` ): complete [M].
- `specificity` (evaluator, `p12/protocol/reports_p12.py` specificity): complete [M].
- `handoff_part_4` (evaluator, `p12/protocol/handoff_p12.py` 4): not run [M].
- `commit_part_4`: commit "prompt 12 part 4" follows this section.

Cumulative new queue-hours: 82.412 [M].


---

# PART 3 CLOSED (2026-09-26T13:43:36.355920+00:00) [M]

- `freeze_readiness` (gate, `p12/protocol/readiness_p12.py` ): complete [M].
  - `p12/manifests/freeze_readiness.json` (SHA-256 `c2ffc26f24cd1567…`): status = "READY"; phases_checked = 130; rule = "every module a phase after the freeze runs exists and is sealed before freeze_p12_0.json is written"
- `freeze` (evaluator, `p12/protocol/freeze_build_p12.py` ): complete [M].
- `handoff_part_3` (evaluator, `p12/protocol/handoff_p12.py` 3): not run [M].
- `commit_part_3`: commit "prompt 12 part 3" follows this section.

Cumulative new queue-hours: 57.309 [M].


---

# PART 2 CLOSED (2026-09-26T13:28:14.946116+00:00) [M]

- `part2_inputs` (evaluator, `p12/protocol/plan_part2_p12.py` inputs): complete [M].
  - `p12/manifests/part2/inputs.json` (SHA-256 `8854c6059a513d9c…`): e_cal_hosts = 241; calibration_hosts = 300; sml_cal_targets = "p12/manifests/part2/sml_cal_targets.csv"; sml_cal_targets_sha256 = "a7d2833263018e7e1d3d8f455c071f64b7e3f2e3988d7a1660daff4feccdf7c3"; e_cal_path = "p12/manifests/part2/e_cal_hosts.csv"; e_cal_sha256 = "5975e356430a3a21ec92393e14715c429a71a8ffcc851c0c20d1881d304eaefe"; sml_inventory_targets = "p12/manifests/part2/sml_inventory_targets.csv"; sml_inventory_targets_sha256 = "95c7125a3d2a115fb4be9ea451fff78ae1d529a19bc5d3b031cd4b32aaae8b6b"; rule = "an injection on an input-ineligible host is INPUT_INELIGIBLE, reported in its own row, never a miss"
- `cal_a_prepare` (controller): CLOSED, 1687 of 1687 jobs, 0 operational unknowns, 0.660 queue-h [M].
- `cal_a_search` (controller): CLOSED, 1928 of 1928 jobs, 0 operational unknowns, 17.148 queue-h [M].
- `cal_a_search_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `lock_cal_a_search` (evaluator, `p12/protocol/lock_predictions_p12.py` cal_a_search): complete [M].
- `score_cal_a` (evaluator, `p12/protocol/score_injections_p12.py` archival): complete [M].
  - `p12/results/part2/injection_outcomes_archival.csv` (SHA-256 `431dbfdf34a89d58…`): 
- `cal_a_A` (controller): FAILED, 130 of 1492 jobs, 27 operational unknowns, 0.802 queue-h [M].
- `cal_a_A_resume` (controller): CLOSED, 1385 of 1385 jobs, 22 operational unknowns, 5.590 queue-h [M].
- `cal_a_A_resume_retry` (controller): CLOSED, 22 of 22 jobs, 2 operational unknowns, 0.334 queue-h [M].
- `cal_a_A_retry` (controller): CLOSED, 3 of 3 jobs, 0 operational unknowns, 0.150 queue-h [M].
- `cal_a_S` (controller): CLOSED, 984 of 984 jobs, 0 operational unknowns, 0.223 queue-h [M].
- `cal_a_S_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `cal_a_B` (controller): CLOSED, 3 of 3 jobs, 0 operational unknowns, 0.002 queue-h [M].
- `cal_a_B_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `cal_a_C` (controller): CLOSED, 30 of 30 jobs, 0 operational unknowns, 11.884 queue-h [M].
- `cal_a_C_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `close_cal_a_C` (evaluator, `p12/protocol/close_stage_c_p12.py` cal_a_C): complete [M].
- `cal_a_real436` (controller): CLOSED, 436 of 436 jobs, 0 operational unknowns, 3.844 queue-h [M].
- `cal_a_real436_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `lock_cal_a_real436` (evaluator, `p12/protocol/lock_predictions_p12.py` cal_a_real436): complete [M].
- `retention_archival` (evaluator, `p12/protocol/retention_p12.py` archival): complete [M].
  - `p12/results/part2/retention_archival.json` (SHA-256 `7e7defa2c67d3c70…`): arm = "archival"; lock_phase = "cal_a_real436"; lock_sha256 = "69dca2ae97a3470c8cdf46ee1e2b502d83e9acdbd7523c52893414b725ab66c2"; sidecar_sha256 = "27c1184136122170d993ceef99a6c1776cb389f2dd2ea9583602ca427d5e3624"; hosts = 436; host_unknowns = 0; families = 1449; rule = "P10.3: exact or 2, 3, 1/2, 1/3 within 1% with the epoch check; presence from the sealed P10.3 forced fits"; label = "development-exposed, EB-contaminated real-signal instrument; search level"
- `report_cal_a` (evaluator, `p12/protocol/report_calibration_json_p12.py` archival): complete [M].
  - `p12/results/part2/COMPLETENESS_ARM_A.json` (SHA-256 `9c2902fc2b1cb31b…`): arm = "archival"; label = "cal_archival"; n_injections = 1687; n_eligible = 1687; rules_version = "p12.0 (A, S as p10.0)"; scope = "injection completeness through S; C on the 30-injection sample; no injection runs through D"
- `sml_inventory` (evaluator, `p12/protocol/sml_p12.py` inventory --targets p12/manifests/part2/sml_inventory_targets.csv): complete [M].
- `sml_gate` (gate, `p12/protocol/sml_gate_p12.py` ): complete [M].
  - `p12/manifests/sml_gate.json` (SHA-256 `b84b1bebb8b7beaa…`): run_arm_b = true; e_cal_hosts = 241; hosts_with_sml_sector = 194; selected_products_on_e_cal = 2595; sml_usable_products = 973; sml_usable_fraction = 0.37495183044315994; inventory_sha256 = "5317438b6adf18d3e45c4629e35d6146b2c6a749822330e2fe87c9ed4010a797"
- `sml_store_cal` (evaluator, `p12/protocol/sml_p12.py` store --targets p12/manifests/part2/sml_cal_targets.csv): complete [M].
- `cal_b_verify` (controller): CLOSED, 677 of 677 jobs, 0 operational unknowns, 0.284 queue-h [M].
- `cal_b_prepare` (controller): CLOSED, 494 of 494 jobs, 0 operational unknowns, 0.198 queue-h [M].
- `cal_b_search` (controller): CLOSED, 735 of 735 jobs, 0 operational unknowns, 5.951 queue-h [M].
- `cal_b_search_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `lock_cal_b_search` (evaluator, `p12/protocol/lock_predictions_p12.py` cal_b_search): complete [M].
- `cal_b_real436` (controller): CLOSED, 436 of 436 jobs, 0 operational unknowns, 3.868 queue-h [M].
- `cal_b_real436_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `lock_cal_b_real436` (evaluator, `p12/protocol/lock_predictions_p12.py` cal_b_real436): complete [M].
- `score_cal_b` (evaluator, `p12/protocol/score_injections_p12.py` sml): complete [M].
  - `p12/results/part2/injection_outcomes_sml.csv` (SHA-256 `f05d18e8d653ca95…`): 
- `retention_sml` (evaluator, `p12/protocol/retention_p12.py` sml): complete [M].
- `cal_b_A` (controller): CLOSED, 663 of 663 jobs, 8 operational unknowns, 2.467 queue-h [M].
- `cal_b_A_retry` (controller): CLOSED, 8 of 8 jobs, 0 operational unknowns, 0.179 queue-h [M].
- `cal_b_S` (controller): CLOSED, 345 of 345 jobs, 0 operational unknowns, 0.078 queue-h [M].
- `cal_b_S_retry` (controller): CLOSED, 0 of 0 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `compare_arms` (evaluator, `p12/protocol/compare_arms_p12.py` archival sml --out p12/results/part2/photometry_decision.json): complete [M].
  - `p12/results/part2/photometry_decision.json` (SHA-256 `0b45d552bfec3976…`): decision = "KEEP_ARCHIVAL"; median_wall_ratio = 0.764553156141263; n_paired_2b = 494; rule = "every clause required (PROMPT_P12.md 2c); a failed change is not adopted and not retried with a lower bar"
- `cal_b_full_prepare` (controller): not run (condition not met or skipped) [M].
- `cal_b_full_search` (controller): not run (condition not met or skipped) [M].
- `cal_b_full_search_retry` (controller): not run (condition not met or skipped) [M].
- `lock_cal_b_full_search` (evaluator, `p12/protocol/lock_predictions_p12.py` cal_b_full_search): not run [M].
- `cal_b_full_A` (controller): not run (condition not met or skipped) [M].
- `cal_b_full_A_retry` (controller): not run (condition not met or skipped) [M].
- `cal_b_full_S` (controller): not run (condition not met or skipped) [M].
- `cal_b_full_S_retry` (controller): not run (condition not met or skipped) [M].
- `cal_b_full_C` (controller): not run (condition not met or skipped) [M].
- `cal_b_full_C_retry` (controller): not run (condition not met or skipped) [M].
- `report_cal_b` (evaluator, `p12/protocol/report_calibration_json_p12.py` sml): not run [M].
- `sml_store_core` (evaluator, `p12/protocol/sml_p12.py` store --core): not run [M].
- `sml_verify_core` (controller): not run (condition not met or skipped) [M].
- `part2_tabulations` (evaluator, `p12/protocol/reports_p12.py` tabulations): complete [M].
- `forecast_after_part2` (evaluator, `p12/protocol/ledger_p12.py` forecast --after-part2): complete [M].
- `handoff_part_2` (evaluator, `p12/protocol/handoff_p12.py` 2): not run [M].
- `commit_part_2`: commit "prompt 12 part 2" follows this section.

Cumulative new queue-hours: 57.309 [M].


---

# PART 1 CLOSED (2026-09-23T18:47:40.403901+00:00) [M]

- `registration` (evaluator, `p12/protocol/register_p12.py` ): complete [M].
- `k10_calibration` (evaluator, `p12/protocol/k10_p12.py` calibrate): complete [M].
  - `p12/results/part1/k10_calibration.json` (SHA-256 `6dc7a7c621e48edf…`): schema = "p12-k10-calibration-v1"; word = "K10_FLAG"; fires_on_key_record = true; artefact_kills_fired = 2; artefact_kill_bar = 3; denominator = "fired / all records of the set (a not-measurable record counts as not fired)"; source_sha256 = "a0fde20b3b7d989b2297c845e63eee5dff12ada0ecf18de91b01955fba38eff9"; rules_sha256 = "9ddf364811bc943754d43e0204e0f2ff46ba45b41be8b27d8cd81aae0f0b67b7"; label = "calibration on seen records under a rule written before it ran"
- `plumbing_d` (controller): FAILED, 3 of 6 jobs, 2 operational unknowns, 0.250 queue-h [M].
- `plumbing_d_resume` (controller): FAILED, 0 of 5 jobs, 0 operational unknowns, 0.000 queue-h [M].
- `plumbing_d_resume_2` (controller): CLOSED, 5 of 5 jobs, 0 operational unknowns, 1.450 queue-h [M].
- `plumbing_d_rerun` (controller): CLOSED, 1 of 1 jobs, 0 operational unknowns, 0.039 queue-h [M].
- `plumbing_check` (evaluator, `p12/protocol/stage_d_plan_p12.py` check): complete [M].
  - `p12/results/part1/plumbing_d.json` (SHA-256 `717551a676268294…`): status = "MATCH"; k10_word = "K10_FLAG"; updates_sha256 = "a3d0d2eba1ae1fe7f6a7c06ab26ad8e7592689ee1444b3b28dcd741441a0716a"
- `tier_rederivation` (evaluator, `p12/protocol/tier_rederivation_p12.py` --out p12/results/part1): complete [M].
  - `p12/results/part1/tier_rederivation_p12.json` (SHA-256 `3df7901caf5f0e44…`): label = "re-scoring of seen records under pre-registered rules, not a validation"; rules_version = "p12.0"; all_p10_reproduced = true; source_sha256 = "e55836213b44b55748b6e8adee81c4cbea24b007c2a6f8ebba42e3e4e684b508"
- `handoff_part_1` (evaluator, `p12/protocol/handoff_p12.py` 1): not run [M].
- `commit_part_1`: commit "prompt 12 part 1" follows this section.

Cumulative new queue-hours: 3.648 [M].


---

# DECISION POINT 1 RESOLVED: tier E1 (2026-09-23T15:42:19.855637+00:00)

The user chose E1 in chat; `p12/manifests/decision_point_1.json` records it [M]. E1 stars carry population_tier "E1" in every table and packet; the extension runs as Part 5a is written, with its own calibration and no admission rule [A].

## Audit-store relocation (0b, 5a) [M]

| Store | Files before | Bytes before | Files after | Bytes after | Sample (seed 2026092002) equal |
|---|---:|---:|---:|---:|---|
| `data/cache/audit_lightkurve` -> `D:\tesshunter_cache\audit_lightkurve` | 80093 | 68713655884 | 80093 | 68713655884 | 1000 files, True |
| `data/survey/audit_lc` -> `D:\tesshunter_cache\audit_lc` | 82807 | 14144688973 | 82807 | 14144688973 | 1000 files, True |

C: free after relocation: 127.2 GB [M]. Paths are unchanged through the junctions.

## LB1c adjacent-domain negatives (amendment 2026-09-23) [A/M]

Reported, never part of bar_met; page one labels it "adjacent domain (K and late-K dwarfs), not the M-dwarf domain" [A]. LB1a stays as written with N1 = 1 and bar_met still requires LB1a, so the final state is BAR_NOT_MET by construction [A].

TIC metadata: 10001 of 10001 union TICs returned by MAST (0 missing), 21 chunk attempts, 64.1 s [M].

| Cut | Stars remaining |
|---|---:|
| union_with_tic_metadata | 10001 |
| teff_lt_4500 | 569 |
| tmag_11.5_to_14.5 | 353 |
| abs_b_ge_20 | 222 |
| ge_3_sectors_200s_with_lc | 41 |
| ffi_majority | 36 |
| core_and_E1_excluded | 36 |

Selected (first 30 by SHA-256 of 20260908:ttt:<TIC>): 30 [M]; overlap with the LB1a star: 1 [M]. Manifest `p12/manifests/ttt_adjacent_negatives.csv`; ephemerides in the guarded `data/survey/p12/negatives/truth/ttt_adjacent_ephemerides.json` [M].
The P8 pool is an M-dwarf TIC query (Teff 2,000 to 3,600 K, radius <= 0.50), so LB1c applies its enumerated cuts to the union with fresh TIC v8 metadata; no radius cut and no pool join [A].

## Forecast re-rendered for the chosen tier [A/I]

DECISION POINT 1: tier E1 chosen

| Part | Base queue-h [A/I] | With margin [A/I] |
|---|---:|---:|
| 0 | 3.10 to 3.10 | 3.88 to 3.88 |
| 1 | 1.20 to 1.20 | 1.50 to 1.50 |
| 2 | 55.10 to 55.10 | 68.87 to 68.87 |
| 3 | 0.00 to 0.00 | 0.00 to 0.00 |
| 4 | 41.43 to 41.43 | 51.79 to 51.79 |
| 5 | 96.53 to 119.26 | 120.66 to 149.08 |
| 6 | 1.00 to 1.00 | 1.25 to 1.25 |

Part 4 includes LB1c (30 stars): 15.86 base queue-h [A/I].
Part 5 includes E1: 39.01 to 49.01 base queue-h [A/I].
Total with margin: 247.95 to 276.37 queue-h [I].
Separate C retry tail: up to 79.7 queue-h [A].
Calendar at duty 0.553: 18.7 to 20.8 days [I]; no date is promised.

Assumptions
[A] Section 6.1 stage-load rates apply to the frozen-policy eligible population.
[A] Calibration stage-load and preparation proportions scale within their own full-injection, 2b-injection or host cohorts; both real-host legs scale only with eligible TCE hosts.
[A] Both 30-job calibration C allocations remain conservatively priced even when fewer calibration hosts qualify; actual job manifests replace phase costs when available.
[A] Queue costs are job-wall sums divided by the measured concurrency once.
[A] The 1.25 margin is applied once; C retries remain a separate tail.
[I] Calendar conversion at duty 0.553 is conditional and promises no completion date.
[A/I] Part 4 TTT line items scale with measured N1; natural late-stage load scales with eligible calibration hosts. The inherited rounding residual is retained.
[A/I] The mixed-stage P9 allocation and extension-calibration allocation scale conservatively by the larger raised search/A pilot factor because their inherited budgets are not fully decomposed.
[A/I] Extension variable allocations and download/storage estimates scale with measured ranked pool size; the acquisition pilot stays fixed. Retry-tail and core-storage allocations remain conservative inherited upper bounds.
[A/I] Decision point 1 chose E1; its extension row (0e-ranked count, pilot-scaled search and A units) is added to Part 5.
[A/I] LB1c reuses the 4b line per selected star (30 of 30) in Part 4; it is reported and never part of bar_met.
[A] The 5a acquisition pilot is unmeasured here; its per-star bytes and wall replace the adopted units when higher.


---

# DECISION POINT 1

Core-only is the registered recommendation [A]. Extension eligibility is not measured completeness [I].

| Part | Base queue-h [A/I] | With margin [A/I] |
|---|---:|---:|
| 0 | 3.10 to 3.10 | 3.88 to 3.88 |
| 1 | 1.20 to 1.20 | 1.50 to 1.50 |
| 2 | 55.10 to 55.10 | 68.87 to 68.87 |
| 3 | 0.00 to 0.00 | 0.00 to 0.00 |
| 4 | 25.57 to 25.57 | 31.97 to 31.97 |
| 5 | 57.53 to 70.26 | 71.91 to 87.82 |
| 6 | 1.00 to 1.00 | 1.25 to 1.25 |

Total with margin: 179.37 to 195.29 queue-h [I].
Separate C retry tail: up to 63 queue-h [A].
Decision points [A]: launch approval after Part 0; any stop rule; final delivery.

Assumptions
[A] Section 6.1 stage-load rates apply to the frozen-policy eligible population.
[A] Calibration stage-load and preparation proportions scale within their own full-injection, 2b-injection or host cohorts; both real-host legs scale only with eligible TCE hosts.
[A] Both 30-job calibration C allocations remain conservatively priced even when fewer calibration hosts qualify; actual job manifests replace phase costs when available.
[A] Queue costs are job-wall sums divided by the measured concurrency once.
[A] The 1.25 margin is applied once; C retries remain a separate tail.
[I] Calendar conversion at duty 0.553 is conditional and promises no completion date.
[A/I] Part 4 TTT line items scale with measured N1; natural late-stage load scales with eligible calibration hosts. The inherited rounding residual is retained.
[A/I] The mixed-stage P9 allocation and extension-calibration allocation scale conservatively by the larger raised search/A pilot factor because their inherited budgets are not fully decomposed.
[A/I] Extension variable allocations and download/storage estimates scale with measured ranked pool size; the acquisition pilot stays fixed. Retry-tail and core-storage allocations remain conservative inherited upper bounds.

| Core scenario | Queue-hours with margin [I] |
|---|---:|
| archival | 179.37 to 195.29 |
| ADOPT_SML_ratio_1 | 211.47 to 227.38 |
| ADOPT_SML_ratio_3_ceiling | 313.19 to 329.11 |

| Extension | Ranked stars [M] | Additional queue-hours with margin [I] | D storage GB [I] |
|---|---:|---:|---:|
| E1 | 1000 | 48.76 to 61.26 | 48.0 |
| E2 | 7989 | 271.27 to 368.77 | 383.0 |

Measured selected N1 is below 20: LB1a cannot be decisive and the registered launch bar cannot be met with this cohort. Final search still requires the user population decision [A/M].


## Part 0 measurements [M]

| Cohort | Eligible | Ineligible | Novelty rejected | Unknown |
|---|---:|---:|---:|---:|
| p8_2000 | 1622 | 378 | 0 | 0 |
| p10_436 | 436 | 0 | 0 | 0 |
| calibration_300 | 241 | 59 | 0 | 0 |

Eligible injection rows [M]: {"2b": {"calibration_hosts": 272, "calibration_injections": 600, "eligible": 494, "total": 600}, "full": {"calibration_hosts": 300, "calibration_injections": 2100, "eligible": 1687, "total": 2100}}.
Catalogue hard-stop counts [M]: {"CLEAN": 2000, "FLAG": 436}.
Independent negatives N1: 1 [M]; source: journal MRT union (Tables 3 and 4); fetch path: `['data/survey/p12/negatives/ttt_downloads/apjsade2d8t3_mrt.txt', 'data/survey/p12/negatives/ttt_downloads/apjsade2d8t4_mrt.txt']`.
The fetch attempt URLs, UTC, bytes, hashes and relaxation counts are in `p12/manifests/ttt_fetch.json` [M].
Latest public QLP sector: 105 [M]. Per-star coverage above 105: UNMEASURED [M]. Directory membership does not measure per-star above-105 coverage; no per-star calls performed

## Pilot costs [M]

| Stage | COMPLETE | Unknown | Mean job wall, s | Queue s/job at 24 workers | Value used |
|---|---:|---:|---:|---:|---:|
| search | 24 | 0 | 765.782 | 31.908 | 31.908 (pilot) |
| A | 41 | 0 | 353.224 | 14.718 | 15.500 (inherited floor) |

Pilot results were used only for timing and counts. No per-candidate measurement was displayed or reused [M].

## Recommendation and decision [A/I]

Core only. The ranked E2 pool has 7989 stars, including 5157 at Tmag 13.5–14 [M]. The extension requires its own calibration; the inherited whole-funnel recovery in this faint band is 41% [P10.3]. Its additional cost and storage are explicit in the forecast [I].
Pause here. The user chooses core, E1 or E2 and writes `p12/manifests/decision_point_1.json`. The agent has not written that file [M].
The three human decision points remain launch approval after Part 0, any stop rule, and final delivery [A].

## Provenance and resolved stops

The sprint is closed by the user. Its original T0 and complete handoff remain in `p12/manifests/closed_sprint_20260922/`; section 10 no longer limits this continuation [A/M].
The audit-only commit is `22a779d0456b81bce24fc9caa60c4fb86c8ba574` [M]. Normal verification uses its recorded source-refresh manifest with identical scientific job payloads [M].
The failed initial native launcher started no controller and no scientific job. Its logs and the PowerShell 7 repair are preserved under `p12/manifests/verify_core_startup_failure_1/` [M].
The earlier count and replay stop receipts and authorized resolutions remain preserved. The 118-test correction and exact historical exposures are recorded in `p12/protocol/AMENDMENTS_P12.md`; no new exception is authorized here [M].
PROMPT_P12.md SHA-256: `8be9b707fa7da8a4c0e86e182f92963e21ec3f6fc4c799d52dda5612354b68a3` [M].

## Original entry and sprint evidence

The archived sprint handoff retains the full Part 0a table, test and integrity receipts, original T0, prior stops and their resolutions [M].
Current evidence: `p12/results/decision_point_1_report.json`, `p12/results/pilot_timing.json`, and `p12/manifests/forecast_p12.json` [M].



## Journal source amendment, attempt 5 — 2026-09-23T15:16:18.956527+00:00 [A/M]

The user supplied the full journal MRT sources. Both were downloaded once and parsed by script; the validated union contains 10,001 rows and 10,001 distinct TICs. Table 3 has 7,936 new EBs and Table 4 has 2,065 known EBs. Source receipts retain URL, start/end UTC, byte count and SHA-256 per file.

- Table 3: https://content.cld.iop.org/journals/0067-0049/279/2/50/revision1/apjsade2d8t3_mrt.txt; 7936 rows; 2002473 bytes; SHA-256 e197c05c167225bf9d5ca1bb3a5b9e672d76b9b938168b7a44c7382768fd0fb6
- Table 4: https://content.cld.iop.org/journals/0067-0049/279/2/50/revision1/apjsade2d8t4_mrt.txt; 2065 rows; 309972 bytes; SHA-256 f5f27c251f53216492fbe0db9c3788d7fc20752c09c9d81ab7ae9099a9331493

Table 4 differs from the supplied shorthand: its published header labels the TESS period Per-TESS, bytes 38–46, days; Table 3 uses Per, bytes 45–53. Both Astropy parsing and an independent byte-range cross-check passed. The initial schema failures remain preserved. Their reconciliation reused the downloaded bytes and completed within the original 600-second wall bound, with no extra HTTP request. Table 3 completed in 19.270 seconds; Table 4, including schema reconciliation, in 318.836 seconds. Parser/selection tests: 42 passed, zero failures.

The unchanged pool join finds 15 of the 10,001 TICs; 9,986 are absent from the pool. Qualifying counts are 0 at baseline, 0 after Teff relaxation, and 1 after Tmag relaxation. Final selected N1=1. The original cuts, core exclusion, relaxation order, hash seed/order and first-30 limit are unchanged, verified by AST comparison. No padding, fallback union or extra relaxation was applied.

The earlier TESS-EB fallback, its N1=6 selection, original acquisition history and guarded ephemerides are preserved in the before-attempt-5 archive. The journal union is the current successful source. Only the Part 4 cohort allocation was repriced; eligibility, hard-stop counts and pilot unit costs are unchanged. N1 here means the selected negative cohort; the final launch-bar denominator still requires COMPLETE searches in Part 4.

The routine remains PAUSED with a stored sixty-minute interval; future supervision permits one early ten-minute check followed by hourly checks. All owners and workers are closed. No decision-point JSON was written and Part 1 has not started. The earlier temporary stop-rule authorization expired at 2026-09-23 12:00 UTC; this work follows the explicit attempt-5 source amendment. Prior stop resolutions and decision-point revisions remain in AMENDMENTS_P12.md and the archived handoffs.
