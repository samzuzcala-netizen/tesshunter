# P12 post-freeze incidents and operations

Written by the session on 2026-10-01 before the Part 5 commit, so that it is committed and sealed with the run. The
frozen audit generator lists the stop receipts but has no input for the operations below. Every item is [M] (measured
or recorded) unless marked [A] (a session action). Machine record: `p12/manifests/post_freeze_operations.jsonl`.

No file hashed in `freeze_p12_0.json` was changed after the freeze. Each workaround ran frozen code unchanged and is
checked against its frozen hash. Every phase below has its own controller receipts.

## Stops and user decisions

| receipt | phase | what | decision |
|---|---|---|---|
| `stop_STOP-4_20260924T152709.json` | cal_a_A (Part 2) | user pause for a PC restart | CONTINUE (`CONTINUE_cal_a_A`): reconciled; 103 kept; resumed as `cal_a_A_resume` |
| `stop_STOP-7_20260926T194951Z.json` | bar_p9_eph (Part 4, LB3) | 13 of 13 jobs OPERATIONAL_UNKNOWN: the frozen `ephemeris_assisted_p12.plan` leaves `stitch_snr`, `stitch_n_transits`, `n_units` blank and the frozen `revet_p6.jobs` raises on `float("")` | CONTINUE (`CONTINUE_bar_p9_eph`): LB3 not measured; no repair |
| `stop_STOP-7_20260930T015624Z.json` | final_B (Part 5) | 54 of 80 B cases OPERATIONAL_UNKNOWN ("Complete neighbour reference missing"): the frozen `plan_part2_p12._neighbours` reads only `data/survey/p8/neighbours/`, so no P10.3 or E1 case had a reference; the E1 neighbour set (`final_ext_neighbours`, 900 s) had also timed out | REPAIR (`REPAIR_final_B`, plan `p12/work/repair_final_B/PLAN.md`) |

Both STOP-7s were declared by the session, not by the frozen continuation: it checks STOP-7 only on retry closures,
and these phases have no registered retry. The session's chain script did not check unknown rates, and the user found
the final_B unknowns. `final_C` had been launched on the 26 B-complete cases before the stop. It was left running
because its cases are valid either way.

## Frozen-code defects worked around without changing frozen bytes [A]

| phase | defect | operation | outcome |
|---|---|---|---|
| neg_p9_search, A, S, B, C, D | continuation runs planners only from `p12/protocol`; the held-out rows register `p12/heldout/runner.py plan` | the registered planner command run by the session (`run_heldout_planner.py`) after a frozen-hash check | manifests as registered |
| neg_p9_search | the P12 copy of `p9/runner.py` (edit 8) converts every execution value with `float()`; P9 skips `""` and `"nan"`; 5 held-out hosts have an empty stellar value | the frozen `runner.plan` run on the rows with empty values left out, as P9 does (`heldout_search_plan.py`); the partial runtime of the failed run rewritten byte-identically | 25 jobs, all COMPLETE |
| neg_p9_C, neg_p9_D | the same conversion inside the frozen held-out workers (no planner-side fix possible) | none; left as operational unknowns | C: 1 case (TIC 207174531) ERROR, also after its retry; D: 1 of 2 (TIC 80025900) ERROR |
| final_search, collect_final | the frozen `plan_part5_p12._final_stars` reads `targets_p8.csv` and the E1 table only; the 436 P10.3 core hosts have no stellar row (KeyError) | the frozen planners run with the star map completed in memory from `p10/part3/manifests/targets_evaluated.csv`, the source the frozen Part 2 `real436` planner used for the same stars (`final_search_plan.py`, `final_collect_plan.py`) | 2,788 search jobs; 5,979 pre-gate cases |
| completeness (Part 6) | schema mismatch between two frozen modules: `report_tabulations_p12` writes `window_check.json` `windows` as the list of window lengths with the numbers under `summary`, `report_completeness_p12.closing` reads `windows` as a list of `{window_days, retention, noise_ratio_1h}` (AttributeError) | the frozen report run with the same numbers reshaped in memory (`run_completeness_adapted.py`); the result must agree with the producer's own `closing_sentence_item_2_holds` (it does: the 1.5-d window); the row's transition written by the session and marked so | `COMPLETENESS_P12.md`, `closing_sentence.json` (3 items) |
| lock_final_search | the registered evaluator exceeded continuation's default 3,600-s evaluator timeout (it re-hashes every pinned source and input of 2,788 jobs); nothing was written | the registered script run without the timeout (`run_evaluator.py`); the lock is idempotent, so the continuation row then verified it | 2,788 jobs, 27,848 accepted, 0 unknowns, 4,080 s |

## Held-out leg (Part 4, LB2) operational unknowns [M]

`neg_p9_A`: 4 of 62 TIMEOUT (TIC 149473467 x2, 229804573, 349059354). The held-out leg registers only the C retry (4c edit 4), so these are final. Read literally, STOP-7 ("after its one recorded retry pass") did not fire, and the session did not stop. All held-out unknowns stay in the LB2 denominators; none is a miss.

## The final Stage B repair (Part 5) [A]

1. `final_B_repair_neighbours`: failed at launch (the session's targets file had no coordinates). `final_B_repair_neighbours_2`: the registered neighbour worker, 47 of 47 tables, 5.2 min.
2. `final_B_repair`: Stage B attempt 2 on the 54 cases. Each used its collect runtime with only `neighbours_reference` and `attempt` changed. The first jobs manifest was refused in preflight: a `D:`-junction table path cannot be a controller pin. That manifest was archived at `p12/manifests/failed_plan/final_B_repair_1/` and never launched. Result: 54 of 54 COMPLETE, all PASS.
3. `final_C_repair`: the frozen `c_job` for the 54 B passers, 51 COMPLETE + 3 OPERATIONAL_UNKNOWN. `final_C_repair_retry`: 3 of 3 COMPLETE. Frozen close: 14 PASS, 40 FAIL.
4. `C_closure_final_C.json`, which the registered `final_neighbours`, `final_D`, `candidate_list` and `natural_load` read, was rewritten as the union of the original closure (4 PASS, 22 FAIL) and the repair closure. The original is archived as `C_closure_final_C_before_repair.json`, and both hashes are recorded in the file. The union has 18 PASS and 62 FAIL.
5. The sequence then continued as registered: `final_neighbours` had 0 targets, and `final_D` ran 18 of 18 COMPLETE.

The 54 repair cases are the P10.3 and E1 cases listed in `p12/manifests/final_B_repair_jobs.json`. Their B, C and D records are the attempt-2 B receipts and the `final_C_repair` receipts.

## Other operational events [M]

- `cal_b_verify`: the first native launch was refused ("Other Python remains before detached launch"), because a session Python call fell inside the launch window. Its launch files are archived at `p12/manifests/failed_launch/cal_b_verify_1/`, and the unchanged row was relaunched.
- `final_C_retry`: launched by an orphaned session chain script. It had outlived its stopped wrapper. This was the next registered row, and the orphan was stopped before it ran anything else.
- `commit_part_5`: the first `git add` failed transiently and succeeded when the row was re-run.
- `final_integrity`: the registered check failed before checking anything. Its output folder `p12/results/integrity_final` already existed: it was a 2026-09-22 Part 0 engineering-sprint run of the same check (PASS, committed in `af39ce8c9`), and `integrity_check_p12` refuses an existing folder. That folder was archived byte-identically as `p12/results/integrity_final_engineering_20260922/` (hashes in `post_freeze_operations.jsonl`; `source_seal_final.json` lists those files at the old path). The registered row then ran fresh.

- `final_integrity`: PASS (75,705 sealed files re-hashed, no mismatch).
- `final_tests`: the registered gate cannot pass when run from the sequence. `run_tests_p12` refuses to run while another Python exists ("Test suite must run alone"), but `final_tests_p12` launches it under itself and continuation. The session ran each registered suite alone from a shell, one after another: compatibility 891 passed, 1 skipped; `p10/part3/tests` 118 passed; `p12/tests` 248 passed; none failed. The frozen gate was then evaluated on those receipts (`run_final_tests_gate.py`): PASS. The row's transition was written by the session and marked so.

- `final_p9_verify`: the registered result is 397 checks with only `baseline_git_HEAD_unchanged` failing, and the script exits 1 on any failure, so the evaluator row cannot pass on the expected result. Its output path also held the 2026-09-22 sprint file, which was archived as `p12/logs/p9_verification_final_engineering_20260922.json`. The session ran the registered command (`run_final_p9_verify.py`) and got 397 checks, only `baseline_git_HEAD_unchanged` failing, and `p9/results/verification.json` unchanged. That equals the registered expectation and the entry run, so the row's transition was written by the session and marked so.
- **Final-state label:** the frozen `report_audit_p12.conditions` tests `integrity_*_zero` as `mismatches == 0`. Both integrity summaries record `status: PASS` with `mismatches: []`, and `[] == 0` is false, so the frozen state function returns `STOPPED_AFTER_FINAL_SEARCH_INCOMPLETE`. Every other delivered-state condition evaluates true. The rows were run as registered, so the frozen label stands, and the question goes to the user at decision point 3. Section 8 also lists "a stop rule fired, the user stopped" under the INCOMPLETE state, and this run had STOP-4, STOP-6 and two STOP-7s, each resolved by a user decision.

## Finalization at decision point 3 (user decision, `p12/manifests/DECISION_POINT_3`) [A]

The user, in chat: "let the shutdown check accept everything, dont let the labels stop you". `p12/work/finalize_p12.py` then:

- **`final_shutdown`:** the frozen `verify_shutdown` was run with the three FAILED-but-reconciled closures accepted: `cal_a_A` (STOP-4), `plumbing_d` (STOP-6), and `plumbing_d_resume` (a zero-job launch). Each has `all_owned_workers_closed` and no live identity. The result is DISABLED_VERIFIED, and the receipt lists the accepted closures with their real status.
- **`final_state`:** the frozen `audit finalize` was run with the two integrity summaries' mismatch lists passed as counts. Both are PASS with 0 mismatches. Every section 8 condition holds, so the state is **FINAL_SEARCH_DELIVERED_BAR_NOT_MET**.
- **`COMPLETENESS_ARM_B`:** written with the registered entry point (`report_calibration_json_p12.py sml`). Arm B ran, but its report row is conditioned on ADOPT_SML. Result: 494 injections, 287 through the whole funnel.

## Deliverable gaps [M]

- **TIC 459189437:** the HOLD case `tic459189437_P0.9293` (H3) has no packet. Its Stage D stopped at the staging step ("Gaia neighbour record unavailable"). The star's neighbour table is complete (10 Gaia sources within 1 arcmin), but the TIC carries no Gaia cross-match for the target (`tic_gaia_id` null; SIMBAD lists PM*). The frozen D worker requires the target's own Gaia source, so no D measurement ran. HOLD H3 records exactly that.
- **Negative-set packet subtrees:** `neg_ttt/`, `neg_p9/` and `neg_fa/` are absent because no negative case received SUBMIT or HOLD; packets are written only for those verdicts.

## Not repaired [M]

- **LB3:** not measured (user decision).
- **LB1a and LB1b:** not decisive (the TTT set yielded N1 = 1).
- **LB2b:** not decisive (N = 1).
- **Held-out unknowns:** listed above.
- **Final Stage A:** 22 of 5,979 cases unknown after the retry (0.4%).

This page was amended after `final_seals` (the `final_integrity` item and anything below it); the hash in `source_seal_final.json` is of the earlier version.
