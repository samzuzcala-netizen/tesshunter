SPRINT HANDOFF 2026-09-22T21:27:07.030383+00:00 [M]

**STOPPED_BEFORE_FINAL_SEARCH** [M]. **STOP-3: expected 116 passed, observed 118 passed on both attempts** [A, M]. No final search was run [M].

Unfinished work: entry acceptance failed; no engineering lane, P12 protocol module, live phase, population verification, pilot, forecast, freeze, launch-bar measurement, candidate list or packet was completed [M]. Full historical integrity and the redirected P9 verifier remain unrun [M]. No scientific owner is alive and no scheduling routine is armed [M].

An unintended read of candidate-level rows in required historical reports was recorded in `p12/manifests/exposure_ledger.jsonl` [M]. These were previously development-exposed P10.3 records [P10.3], not held-out truth. No rule or implementation decision used them [M]. User disposition is required before scientific continuation [I].

## Resume and stop disposition

Resume here: resolve the exact-count mismatch in Part 0a before Part 0b [M]. The expected count was not edited. No test was skipped, weakened, deleted or changed [M].
`PROMPT_P12.md` section 10a says: "No expectation is edited to pass, no test is skipped or weakened" and "if it still fails it is reported open in the handoff and STOP-3 applies as written."
The required next decision is approval to reconcile the stale entry expectation with the sealed suite and acknowledgment of the exposure incident. This is not launch approval for later science [I].

## Clock [M]

- T0: `2026-09-22T21:14:59.3552628Z`.
- Engineering deadline: `2026-09-22T23:44:59.3552628Z`; adopted offset 150 minutes [A].
- Live-phase closure deadline: `2026-09-23T00:49:59.3552628Z`; adopted offset 215 minutes [A].
- Owned-job stop deadline: `2026-09-23T00:59:59.3552628Z`; adopted offset 225 minutes [A].
- Handoff deadline: `2026-09-23T01:14:59.3552628Z`; adopted offset 240 minutes [A].
- This handoff follows the entry stop, before every deadline [M]. No subagent was started because section 10b requires completed entry checks first [M, A].

## Entry and exit evidence

| Check | Expected / reference | Observed | Outcome |
|---|---|---|---|
| Branch / entry HEAD | `improve/recovery` / `863c01be5` [A] | `improve/recovery` / `863c01be55f4455b482ad9edc764da20296fe6ec` [M] | pass |
| Tracked historical tree | clean [A] | clean before and after tests [M] | pass |
| Untracked historical paths | only listed patterns [A] | all match allowed patterns; 2,509 FA arrays [M] versus about 2,540 in prompt [P12] | pass: approximate count |
| Git maintenance / gc / detach | `false / 0 / false` [A] | `false / 0 / false` [M] | pass |
| Compatibility suite | 891 passed, 1 skipped [A] | 891 passed, 1 skipped [M] | pass |
| P10.3 suite | 116 passed [A] | 118 passed twice [M] | **STOP-3** |
| P10.3 sealed test bytes | unchanged [A] | 20 files, zero mismatches [M] | pass |
| Python version | 3.13.3 [A] | 3.13.3 [M] | pass |
| CPU / RAM | 32 logical / 24 physical; about 63.8 GiB [P12] | 32 logical / 24 physical; 68484653056 bytes [M] | pass |
| Python processes / owner receipts | none [A] | none at entry and shutdown [M] | pass |
| Historical automations | both PAUSED [A] | both PAUSED; exact TOML hashes unchanged [M] | pass |
| Population pins | three exact SHA-256 pins [A] | all three match [M] | pass |
| P9 verification receipt | record and preserve hash [A] | `5e600fa200955f10feacaa58dec953bafb8e5ba7552d6e816a5a4e3b3581ac08` unchanged [M] | pass |
| Full historical integrity | zero mismatches in Part 0c [A] | not run: Part 0c not reached [M] | open |
| Redirected P9 verification | 397 checks; one expected HEAD failure [A] | not run: copy not implemented [M] | open |
| C: free bytes | above 26,000,000,000 [A] | 53,519,015,936 [M] | pass |
| D: free bytes | above 50,000,000,000 [A] | 973,086,490,624 [M] | pass |

| Path | Count / bytes [M] | Link target [M] |
|---|---:|---|
| `data/cache/stitched` | 6,658 / 3,763,602,311 | D:\tesshunter_cache\stitched |
| `data/cache/lightkurve/tesscut` | 324 / 21,004,824,598 | D:\tesshunter_cache\lightkurve\tesscut |
| `data/cache/audit_lightkurve` | 80,093 / 68,713,655,884 | ordinary directory |
| `data/survey/audit_lc` | 82,807 / 14,144,688,973 | ordinary directory |
| `.git` | 23,972 / 11,185,863,760 | ordinary directory |

Decimal bytes are authoritative [M]. The prompt mixes decimal GB and GiB approximations [I]; cache byte differences caused only by unit labels are not interpreted as evidence changes. Exit disks: C `53,045,174,272` bytes and D `973,086,490,624` bytes free [M]. Whole-machine disk changes are not attributed to this task [I]. The exact entry status is preserved in `p12/logs/entry_preflight.json` [M].

## Diagnosis and verification [M unless labelled]

All tests passed. The compatibility suite completed in 162.427 process-wall seconds [M]; the P10.3 runs in 11.576 and 7.675 process-wall seconds [M]. Logs and hashes are in the entry receipt.

The sealed historical regression receipt was written at `2026-09-15T22:38:30.127442+00:00` and reports 116 [P10.3]. The file `test_autopsy_v1.py` contains two test functions [M], has filesystem modification time `2026-09-15T22:38:56Z` [M], and first appears in commit `ddf4050ea` at `2026-09-15T22:41:30Z` [M]. These timings explain the count gap plausibly [I]; filesystem times are supporting metadata, not proof of which tests the earlier run collected. The decisive evidence is unchanged sealed test bytes plus two fresh 118-pass results [M].

One diagnostic rerun was performed [M]. No permissible source fix was identified; deleting the additional tests or relabelling the expected count would violate the prompt [I]. Detailed evidence is `p12/logs/entry_count_diagnosis.json` [M].

The full historical integrity check has not run [M]. The limited checks cover tracked status, the population pins, P9's verification receipt, the automation TOMLs, and the sealed P10.3 test files [M]. No zero-mismatch claim is made for the entire historical dataset [I].

## Part 0 status and lane priorities

- Part 0a: measurements complete, acceptance blocked by STOP-3 [M].
- Part 0b: only entry logs, manifests, work and results directories exist; the D junction and cache redirect are open [M].
- Part 0c: all shared interfaces, copied modules, smoke tests, integrity, P9 verification and provenance remain open [M].
- Parts 0d, 0e, 0f, 0g, 0h: not launched; no catalogue snapshot hashes, eligibility counts, TTT count, probe count, pilot walls or forecast exist [M].
- Lead priority: resolve entry, complete workspace and shared interfaces, then dispatch the three disjoint lanes as section 10 requires [A].
- Lane A: controller, guards, recovery, blind I/O, verification, registration, supervision and ledger; all open [M].
- Lane B: policy input identity, preparation, downloads, neighbours, blind search, prediction locks, injections and SML inventory/store; all open [M].
- Lane C: catalogue snapshot, sidecar, crossmatch, population, sector probe and TTT acquisition; all open [M].
- Later-part modules remain outside the sprint until every lane integrates with green tests before the engineering deadline [A].

| Module / group | Status | Required validation (unrun) |
|---|---|---|
| `p12_common.py` | open [M] | roots on `D:`; keys present |
| `config.json` | open [M] | roots on `D:`; keys present |
| `controller_p12.py` | open [M] | exclusive owner; TIMEOUT with no orphan; freeze refusal; retry manifest |
| `guards_p12.py` | open [M] | exclusive owner; TIMEOUT with no orphan; freeze refusal; retry manifest |
| `checkin_p12.py` | open [M] | trigger table; sequence order; synthetic tree; synthetic interrupted phase |
| `continuation_p12.py` | open [M] | trigger table; sequence order; synthetic tree; synthetic interrupted phase |
| `final_shutdown_p12.py` | open [M] | trigger table; sequence order; synthetic tree; synthetic interrupted phase |
| `recover_p12.py` | open [M] | trigger table; sequence order; synthetic tree; synthetic interrupted phase |
| `integrity_check_p12.py` | open [M] | 0 mismatches at entry; seal round-trip |
| `register_p12.py` | open [M] | 0 mismatches at entry; seal round-trip |
| `p9_verify_p12.py` | open [M] | 397 checks with only `baseline_git_HEAD_unchanged` failing; the SHA-256 of `p9/results/verification.json` unchanged after the run |
| `blind_io_p12.py` | open [M] | an open fails the job |
| `policy_products_p12.py` | open [M] | no excluded QLP product is ever returned; swaps only named sectors |
| `build_input_jobs_p12.py` | open [M] | the 436 reproduce their P10.3 status and prepared SHA-256 |
| `verify_prepare_p12.py` | open [M] | the 436 reproduce their P10.3 status and prepared SHA-256 |
| `input_identity_p12.py` | open [M] | the 436 reproduce their P10.3 status and prepared SHA-256 |
| `download_star_p12.py` | open [M] | corrupt FITS re-downloaded with `force=True` |
| `build_batches_p12.py` | open [M] | corrupt FITS re-downloaded with `force=True` |
| `neighbours_worker_p12.py` | open [M] | corrupt FITS re-downloaded with `force=True` |
| `neighbours_batch_worker_p12.py` | open [M] | corrupt FITS re-downloaded with `force=True` |
| `blind_search_worker_p12.py` | open [M] | hash refusal; guarded open fails |
| `lock_predictions_p12.py` | open [M] | hash refusal; guarded open fails |
| `prepare_injections_p12.py` | open [M] | injected array differs only in-transit; on 5 injections whose host the policy leaves unchanged, the array equals `survey_p8.get_prepared(..., injection=row)` to 1e-12 (so LB4 compares like with like); 20 sealed 2d rows re-scored identically |
| `score_injections_p12.py` | open [M] | injected array differs only in-transit; on 5 injections whose host the policy leaves unchanged, the array equals `survey_p8.get_prepared(..., injection=row)` to 1e-12 (so LB4 compares like with like); 20 sealed 2d rows re-scored identically |
| `funnel_plan_p12.py` | open [M] | a sealed P10.3 A record replays byte-identically under `p10.0` |
| `funnel_worker_p12.py` | open [M] | a sealed P10.3 A record replays byte-identically under `p10.0` |
| `stage_c_plan_p12.py` | open [M] | a sealed P10.3 A record replays byte-identically under `p10.0` |
| `stage_c_worker_p12.py` | open [M] | a sealed P10.3 A record replays byte-identically under `p10.0` |
| `close_stage_c_p12.py` | open [M] | a sealed P10.3 A record replays byte-identically under `p10.0` |
| `stage_d_worker_p12.py` | open [M] | bare TCE FLAG and not K0; TOI REJECT and K0; P8 star CLEAN; cube path on `D:` |
| `stage_d_packets_p12.py` | open [M] | bare TCE FLAG and not K0; TOI REJECT and K0; P8 star CLEAN; cube path on `D:` |
| `crossmatch_p12.py` | open [M] | bare TCE FLAG and not K0; TOI REJECT and K0; P8 star CLEAN; cube path on `D:` |
| `catalog_adapter_p12.py` | open [M] | bare TCE FLAG and not K0; TOI REJECT and K0; P8 star CLEAN; cube path on `D:` |
| `catalog_snapshot_p12.py` | open [M] | its hashes unchanged after a run |
| `build_sidecar_p12.py` | open [M] | its hashes unchanged after a run |
| `rules_p12.py` | open [M] | Part 1; two FITS fixtures |
| `k10_p12.py` | open [M] | Part 1; two FITS fixtures |
| `tier_rederivation_p12.py` | open [M] | Part 1; two FITS fixtures |
| `sml_p12.py` | open [M] | Part 1; two FITS fixtures |
| `fetch_ttt_p12.py` | open [M] | cuts on a fixture; hash order; relaxation order |
| `sector_probe_p12.py` | open [M] | cuts on a fixture; hash order; relaxation order |
| `targets_p12.py` | open [M] | cuts on a fixture; hash order; relaxation order |
| `retention_p12.py` | open [M] | 156/377 from sealed P10.3 results; e's 146/291 and 709/300 from sealed 2b rows |
| `tce_families_p12.py` | open [M] | 156/377 from sealed P10.3 results; e's 146/291 and 709/300 from sealed 2b rows |
| `compare_arms_p12.py` | open [M] | 156/377 from sealed P10.3 results; e's 146/291 and 709/300 from sealed 2b rows |
| `heldout/` | open [M] | 4c; smoke tests |
| `freeze_p12.py` | open [M] | 4c; smoke tests |
| `launch_bar_p12.py` | open [M] | 4c; smoke tests |
| `candidate_list_p12.py` | open [M] | 4c; smoke tests |
| `seals_p12.py` | open [M] | 4c; smoke tests |
| `reports_p12.py` | open [M] | 4c; smoke tests |
| `ledger_p12.py` | open [M] | 4c; smoke tests |
| `diff_origins_p12.py` | open [M] | provenance generation |

There are no files under `p12/protocol/` or `p12/tests/` [M], so their file-hash lists are empty. `p12/manifests/module_status_p12.json` preserves every module's origin, permitted diff and required validation [M]. The entry reporting script is under `p12/work/`; it is not a protocol implementation [M].

## Deliverables and cost

The stop, diagnosis, entry and exit receipts, disabled-supervision receipt, exposure ledger, instruction snapshot, file seals, module inventory and historical-only completeness statement are saved [M]. `docs/AUDIT_P12.md` records the stop; `p12/results/COMPLETENESS_P12.md` is labelled "pre-P11 sector set, not the frozen input" [M]. Specificity has no new measurement and its report is not required before that part closes [A].

Scientific queue-hours, scientific job-wall hours, acquisition bytes and check-ins are each zero [M]. Test process wall totals 181.677 seconds [M]. The cost ledger records elapsed engineering time and its measurement limits [M].

Decision point 1 was not reached [M]. No population-tier selection or multiweek launch approval was requested [M]. The stopped run is awaiting the stop-rule disposition, not final science delivery [I].

## Commit and repository status

The lead makes the required local sprint commit with the maintenance flags, staging only `p12/`, `HANDOFF_P12.md` and `RESUME_P12.md` [A]. No push occurs [M]. The new `docs/AUDIT_P12.md` is delivered separately and remains untracked to honor section 10d's explicit staging scope [A].
The exact post-commit status is in `p12/logs/git_status_after_commit.txt` [M when captured]; it is rechecked after including that receipt in the same local commit. Historical untracked files remain in place [M].

## Assumptions and limitations

[A] The literal expected count remains binding until the user authorizes reconciliation; passing more tests does not authorize the agent to revise the prompt.
[I] The historical regression count appears stale. The evidence does not identify a science failure or authorize changing scientific thresholds.
[A] Previously development-exposed records remain in that category; unintended previews are still logged and must not be represented as unexposed.
[M] No P12 calibration, specificity, launch-bar or final-search measurement exists. All inherited completeness values remain labelled [P10].
