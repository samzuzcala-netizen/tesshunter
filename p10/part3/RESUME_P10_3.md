# P10.3: funnel_C running

Current launch 2026-09-15T20:07:34.186853+00:00: funnel_C, 6 new jobs, 3 workers, 12240-second deadlines. Exact owner PID 39436, creation 1789502854.0196433, and command verified. Use live owner/progress receipts for current state. The same hourly routine is ACTIVE for its single early ten-minute check, then 60 minutes. The old P10 routine remains PAUSED.

forced_fits closed with all jobs accounted for. Both paired prediction manifests remain sealed. All 436 stars remain allocated to both presets with six pilot hosts reused. Part F entry is recorded and all 531 original stars are now development-exposed. No scientific retry is authorized.

[A] Auto-advance through the registered sequence; N_C is frozen from the B-closure ledger using floor((remaining_hours - 3.0)*3/3.4). H and any five autopsies follow the registered rule; p10.1 is costed only. Pause only for Part I stops, integrity failures or final delivery. At C closure finish retention tables, H and final delivery using STAGE_C_IMPLEMENTATION_20260915.md and PART_F_IMPLEMENTATION_20260915.md when implementation is needed between closed phases. Never edit sealed or loaded sources.

## Dated history (earlier pending states are historical)

2026-09-14T17:05:36Z [M]: download_pilot launched; owner PID 34828, creation time 1789405535.9473228. Normal hourly routine prompt-10-3-hourly-check-in is ACTIVE with the single initial 10-minute exception; old P10 routine verified PAUSED. Initial launch verification saw four active workers, one completed, zero operational unknowns; no per-case science was opened.

2026-09-14T17:20:24.938920+00:00 [M]: download_pilot; completed 1, pending 45, active 4, unknowns 0; C free 39.141 GB; new queue 0.25422 h; triggers [].

2026-09-14T17:22Z [M]: early-check action compared fresh OS process-tree CPU against the saved conversation launch-verification measurement from 17:06:42Z. Three identified download workers were checked for the >300-second nonadvancing-CPU signature; exact actions are in logs/early_stall_action_20260914.json. The owning controller was preserved and continues the registered queue. Network-stalled inputs remain operational unknowns, never misses. Normal supervision is now 60 minutes; no extra wakeups were scheduled.

2026-09-14T18:23:46.354252+00:00 [M]: download_pilot; completed 48, pending 0, active 2, unknowns 11; C free 37.141 GB; new queue 1.31059 h; triggers ['RISING_ERROR_COUNT'].

2026-09-14T18:23:46Z [M]: 48/50 acquisition attempts terminal, 11 operational unknowns, no queued jobs and two active. Owner remains alive; disk 37.141 GB; charged new union time 1.31059 h. Deadline-based remaining phase forecast is at most about 5.2 minutes. The single routine was shortened to six minutes for closure; unknowns require input recovery/verification and never become misses.

2026-09-14T18:32:45.189032+00:00 [M]: download_pilot; completed 50, pending 0, active 0, unknowns 13; C free 37.152 GB; new queue 1.39595 h; triggers ['RISING_ERROR_COUNT', 'PHASE_CLOSED'].

2026-09-14T18:39:29.742136+00:00 [M]: clean pilot closure and supervisor pause verified. Final closed-interval new union charge is 1.395951786444 h; measured new HTTP body bytes 1,415,122,549, with 65,536 bytes of unreconciled reservation retained conservatively. No scientific endpoint or stop state has been assigned. Main-task continuation must review acquisition failures and complete the all-473 acquisition/storage forecast before another launch. See PILOT_CHECKPOINT_P10_3.md.

Engineering follow-up: commit e942f949 saved the pilot checkpoint. Git auto-maintenance was stopped, but its newly created 2.25 GB temporary pack remains after cleanup was blocked by automatic approval review. See logs/checkpoint_commit_maintenance.json. Use both -c maintenance.auto=false and -c gc.auto=0 for future local commits.

2026-09-14T20:20Z [M, user's Claude session, not the Codex owner]: main-task review of the pilot is written to MAIN_REVIEW_20260914.md. Environment repairs applied outside the protocol: the two orphaned git temporary packs (8.34 GB + 2.25 GB, reported as garbage by git) were removed, repo-local maintenance.auto=false / gc.auto=0 / gc.autoDetach=false were set, and the loose object store was packed once with no controller alive. Free space on C: rose from 32.06 GB to 41.93 GB before the repack. No protocol source, manifest, seal or receipt was modified. The review classifies the 13 unknowns (7 deadline, 3 stalled-and-stopped, 2 HTTP 502, 1 HTTP 404; all MAST-side), measures the sector-56-and-later byte share (58% of array bytes), forecasts the remaining 436 stars under the current and a 56-105 acquisition floor, and proposes amendments D1-D4 (sector floor 56, download deadline 600 s, one recorded network-class retry pass, batches of about 100) for prospective registration before the next launch. Next action belongs to the Codex main task: register D1-D4, re-freeze sector_policy.json, add the D1 test, launch batch 1 with the hourly routine.

2026-09-14T20:33:20Z [M, user's Claude session with the user's explicit go-ahead]: amendments D1-D4 registered in AMENDMENTS_D1_D4_20260914.md (versioned protocol/download_star_v2.py + build_batches_v2.py + tests/test_download_v2.py, 26 tests pass; registration seal untouched). Plan: 436 remaining stars in 5 ascending-TIC batches of 100 (manifests/download_v2_batch_01..05.json), 13 pilot failures at attempt 2. download_v2_batch_01 launched hidden via controller.py --workers 4 --deadline 600; owner PID 42956, creation time 1789417999.901083; launcher receipt manifests/download_v2_batch_01_launcher.json. Supervision: one early check at ~10 min, then bounded read-only checks via protocol/checkin.py no more often than every 30 min; next batch launched only after a clean closure; retry pass (build_batches_v2.py retry) after batch 05; no Part E or later phase will be launched by this session.

2026-09-14T20:45:47.253129+00:00 [M]: download_v2_batch_01; completed 65, pending 31, active 4, unknowns 0; C free 40.789 GB; new queue 1.60317 h; triggers [].

2026-09-14T20:55:09.582742+00:00 [M]: download_v2_batch_01; completed 100, pending 0, active 0, unknowns 0; C free 39.361 GB; new queue 1.74038 h; triggers ['PHASE_CLOSED'].

2026-09-14T20:55Z [M, user's Claude session]: download_v2_batch_01 CLOSED 100/100, 0 unknowns (the 13 pilot failures all completed at attempt 2). download_v2_batch_02 launched, same recipe (4 workers, 600 s deadline); launcher receipt manifests/download_v2_batch_02_launcher.json.

2026-09-14T21:24:40.145650+00:00 [M]: download_v2_batch_02; completed 100, pending 0, active 0, unknowns 0; C free 37.211 GB; new queue 2.20348 h; triggers ['PHASE_CLOSED'].

2026-09-14T21:17Z [M, user's Claude session]: download_v2_batch_02 CLOSED 100/100, 0 unknowns. download_v2_batch_03 launched, same recipe; launcher receipt manifests/download_v2_batch_03_launcher.json.

2026-09-14T21:44:31.558031+00:00 [M]: download_v2_batch_03; completed 100, pending 0, active 0, unknowns 0; C free 34.947 GB; new queue 2.51593 h; triggers ['PHASE_CLOSED'].

2026-09-14T21:44Z [M, user's Claude session]: download_v2_batch_03 CLOSED 100/100, 0 unknowns; cap forecast for the remaining 136 stars fits under 15 GB. download_v2_batch_04 launched, same recipe; launcher receipt manifests/download_v2_batch_04_launcher.json.

2026-09-14T22:04:55.929315+00:00 [M]: download_v2_batch_04; completed 100, pending 0, active 0, unknowns 0; C free 29.789 GB; new queue 2.84118 h; triggers ['PHASE_CLOSED'].

2026-09-14T22:05Z [M, user's Claude session]: download_v2_batch_04 CLOSED 100/100, 0 unknowns. download_v2_batch_05 (final 36 stars) launched, same recipe; launcher receipt manifests/download_v2_batch_05_launcher.json.

2026-09-14T22:14:08.380115+00:00 [M]: download_v2_batch_05; completed 36, pending 0, active 0, unknowns 0; C free 36.967 GB; new queue 2.96428 h; triggers ['PHASE_CLOSED'].

2026-09-14T22:16Z [M, user's Claude session]: download_v2_batch_05 CLOSED 36/36, 0 unknowns; all five batches 436/436 complete, 473/473 stars indexed, acquisition 12.10 GB cumulative of 15. Regenerable caches relocated to D: behind junctions (stitched 3.76 GB during batch 05 when C: fell to 27.7 GB; tesscut 21.0 GB after closure), receipts manifests/cache_relocation_*.json, ledger cache_relocation set; C: now ~54 GB free. download_v2_retry launched: 6 stars with one product-level failure each, --force re-index, attempt 2.

2026-09-14T22:18:39.145059+00:00 [M]: download_v2_retry; completed 6, pending 0, active 0, unknowns 0; C free 57.971 GB; new queue 2.97691 h; triggers ['PHASE_CLOSED'].

2026-09-14T22:22:12.847242+00:00 [M]: download_v2_retry_pilot; completed 3, pending 0, active 0, unknowns 0; C free 57.989 GB; new queue 2.98364 h; triggers ['PHASE_CLOSED'].

2026-09-14T22:24Z [M, user's Claude session]: ACQUISITION COMPLETE. download_v2_retry CLOSED 6/6 and download_v2_retry_pilot CLOSED 3/3 (forced re-index, n_failed now 0 everywhere). 473/473 stars indexed, 11,532 products (10,895 at s56+), 0 recorded product failures; queue 2.98/31.98 h; acquisition 12.10/15 GB; C: 54.0 GB free after relocating stitched (3.76 GB) and tesscut (21.0 GB) caches to D: behind junctions. No owner, no live process, no Part E work started. Read ACQUISITION_CLOSEOUT_20260914.md, then AMENDMENTS_D1_D4_20260914.md and MAIN_REVIEW_20260914.md. Next: Codex finishes Part D verification/neighbours/noise/eligibility/STOP-1, commits the checkpoint, and starts Part E.

2026-09-15T02:51:31.134294+00:00 [M, Codex main]: authorized acquisition handoff adopted; 7 v2 phases and 9 registered hashes verified, 473 indices/11,532 products/0 recorded product failures, cache junction counts/bytes verified. D1-D4 incorporated with original preregistration snapshot and amendment chain. Aggregate ledger refreshed; Part D FITS/neighbour/noise verification is next.

2026-09-15T03:45:47.973333+00:00 [M, Codex main]: Part D closed with 436 INPUT_ELIGIBLE, 0 input/neighbour unknowns, and 95 independent likely-periodic in-band families; STOP-1 NOT FIRED. All 11,532 indexed source arrays verified, including source TICID headers; eligible-host corrected-v02 comparisons 1,309. Historical integrity recheck PASS; 43 focused tests plus 2 additional runtime-hash binding tests pass. Native/source/neighbour evidence sealed (25,909 files, 15,620,836,569 bytes; this footprint is not acquisition cost). Six timing hosts selected only by registered hash and native-point-count tercile; all 12 paired runtime/input/source hashes verified. Pilot approved before search; main allocation decision remains pending.

2026-09-15T03:51:39.395309+00:00 [M, Codex main]: e9e4f91e committed verified Part D and the pilot implementation. timing_pilot_search launched hidden; exact owner PID/creation/command verified (PID 17236, creation 1789444178.757736); initial active 12, pending 0, completed 0, unknowns 0, C free 51.133 GB. Launch CPU baseline saved without opening per-case science. This task's hourly routine is verified ACTIVE with the single early ten-minute exception, then 60 minutes; old P10 remains PAUSED. Mechanical pilot A may follow; level/P8 allocation must return to main review.

2026-09-15T04:02:24.870916+00:00 [M]: timing_pilot_search; completed 8, pending 0, active 4, unknowns 0; C free 51.132 GB; new queue 3.55351 h; triggers [].

2026-09-15T04:03:44.168385+00:00 [M]: timing-pilot early check found 8/12 complete, 4 CPU-advancing workers, zero unknowns and C: 51.132 GB free. Normal 60-minute cadence restored, then a single registered final interval of 49 minutes set from the 04:49:39Z latest worker deadline plus closure buffer. No per-case science opened; active controller retains ledger ownership.

2026-09-15T04:53:19.730927+00:00 [M]: timing_pilot_search; completed 12, pending 0, active 0, unknowns 0; C free 50.450 GB; new queue 3.66367 h; triggers ['PHASE_CLOSED'].

2026-09-15T04:55:11.188968+00:00 [M]: check-in observed timing_pilot_search CLOSED at 2026-09-15T04:09:00.626638+00:00: 12/12 complete, 0 unknowns, all owned workers closed and source hashes unchanged. The registered machine-only I/O audit and transition passed, preparing 17 pilot Stage A jobs (forecast 7.629 min; 1,200 s deadline, one attempt). Routine temporarily paused for this mechanical transition; level/P8 allocation remain unselected. No per-case science read by the session. New queue 3.664372011 h; check-in count 13 reconciled after closure.

2026-09-15T04:58:07.905231+00:00 [M]: timing_pilot_A launched hidden after checkpoint 0667dd9a; exact owner PID 8364 and creation 1789448165.7843091 verified. Initial active 17, pending 0, complete 0, unknowns 0. Source and native raw-product hashes passed preflight; one attempt, 1,200 s deadline. Routine verified ACTIVE for the single early ten-minute check, then normal hourly cadence if needed. Next clean closure must pause for main allocation review; no per-case science was read by this session.

2026-09-15T05:08:48.239767+00:00 [M]: timing_pilot_A; completed 17, pending 0, active 0, unknowns 0; C free 50.253 GB; new queue 3.76834 h; triggers ['PHASE_CLOSED'].

2026-09-15T05:12:57.033554+00:00 [M]: early A check observed clean closure (17/17, 0 unknowns, source hashes unchanged). pilot_next.py returned PAUSE_FOR_MAIN_ALLOCATION_REVIEW and wrote the timing/count-only summary. Both owners/recorded workers closed; routine and old P10 routine verified PAUSED; 14 check-ins reconciled. New scientific charge 3.768334899 h, remaining 28.211665101 h. Closed pilot evidence sealed as opaque bytes. No level/P8 allocation, case-science interpretation or Part F work performed.

2026-09-15T07:02:59.998990+00:00 [A/M]: user all-436 paired allocation and supervision amendment registered prospectively. 430 remaining jobs per preset; all six pilot hosts and 17 pilot A measurements reused. Final prediction locking is implemented at each preset closure. Execution chain, all prepared inputs and closed pilot evidence verified. Part3 tests passed (62 full, 18 focused follow-up). No further science launched yet.

2026-09-15T07:07:18.169510+00:00 [M]: search_survey_p10 launched hidden after commit 6f109c44; owner PID 47148, creation 1789455871.7988515 and command verified. Initial active 24, pending 406, unknowns 0; C free 49.766 GB. Revised same-task routine verified ACTIVE with one early ten-minute check and normal hourly cadence. P8 and subsequent registered phases auto-advance under the user amendment; p10.1 execution remains forbidden. No per-case science was opened for launch verification.

2026-09-15T07:18:34.950806+00:00 [M]: search_survey_p10; completed 20, pending 386, active 24, unknowns 0; C free 49.710 GB; new queue 4.00237 h; triggers [].

2026-09-15T07:19:16.758561+00:00 [M]: full P10 early check passed: 20/430 complete, 386 pending, 24 active, 0 unknowns; exact owner alive and no nonadvancing workers detected. C: 49.710 GB free. The same routine is verified ACTIVE at the normal 60-minute interval; no final-interval exception is justified. Schedule count 15; active controller retains resource-ledger ownership.

2026-09-15T08:19:56.692431+00:00 [M]: search_survey_p10; completed 137, pending 269, active 24, unknowns 0; C free 49.717 GB; new queue 5.02487 h; triggers [].

2026-09-15T09:21:45.442187+00:00 [M]: search_survey_p10; completed 260, pending 146, active 24, unknowns 0; C free 49.477 GB; new queue 6.05464 h; triggers [].

2026-09-15T10:26:18.860092+00:00 [M]: search_survey_p10; completed 384, pending 22, active 24, unknowns 0; C free 48.539 GB; new queue 7.13022 h; triggers [].

2026-09-15T11:27:53.511395+00:00 [M]: search_survey_p10; completed 430, pending 0, active 0, unknowns 0; C free 48.480 GB; new queue 7.57966 h; triggers ['PHASE_CLOSED'].

2026-09-15T11:32:06.291754+00:00 [M]: search_survey_p10 closed with 430 completed new jobs, 0 operational unknowns and unchanged source hashes. continuation_next.py returned search_survey_p8: 430 jobs, 24 workers, deadline 3600 s. Closed ledger 7.579603171/31.98 h; remaining 24.400396829 h; forecast 136.837 min. Check-in count reconciled to 19. Prelaunch arguments and hashes recorded.

2026-09-15T11:33:48.378359+00:00 [M]: search_survey_p8 launched hidden from checkpoint cf369a9d278f1bcb1ddd77441355c74ff5354041; owner PID 26512, creation 1789472003.731344, command verified. Initial snapshot 24 active, 406 pending, 0 complete, 0 unknowns. Same heartbeat verified ACTIVE at 10 minutes for the single early check; then normal 60 minutes. C free 48.422 GB.

2026-09-15T11:44:22.082348+00:00 [M]: search_survey_p8; completed 45, pending 361, active 24, unknowns 0; C free 48.357 GB; new queue 7.76171 h; triggers [].

2026-09-15T12:45:26.150823+00:00 [M]: search_survey_p8; completed 345, pending 62, active 23, unknowns 0; C free 51.536 GB; new queue 8.77945 h; triggers [].

2026-09-15T13:26:54.584356+00:00 [M]: search_survey_p8; completed 430, pending 0, active 0, unknowns 0; C free 51.470 GB; new queue 9.07781 h; triggers ['PHASE_CLOSED'].

2026-09-15T13:28:12.227643+00:00 [M]: search_survey_p8 closed with 430 completed new jobs, 0 operational unknowns and unchanged source hashes. continuation_next.py returned funnel_A: 1087 jobs, 24 workers, deadline 1200 s. Closed ledger 9.082341842/31.98 h; remaining 22.897658158 h; forecast 495.458 min. Check-in count reconciled to 22. Prelaunch arguments and hashes recorded.

2026-09-15T13:29:30.503792+00:00 [M]: funnel_A launched hidden from checkpoint 8125d723ee4110e3625972206a9e01d475e55a7c; owner PID 43744, creation 1789478947.7730877, command verified. Initial snapshot 24 active, 1063 pending, 0 complete, 0 unknowns. Same heartbeat verified ACTIVE at 10 minutes for the single early check; then normal 60 minutes. C free 51.355 GB.

2026-09-15T13:39:54.162736+00:00 [M]: funnel_A; completed 9, pending 1055, active 23, unknowns 0; C free 50.936 GB; new queue 9.26139 h; triggers [].

2026-09-15T14:40:57.708453+00:00 [M]: funnel_A; completed 292, pending 771, active 24, unknowns 2; C free 48.706 GB; new queue 10.27916 h; triggers ['RISING_ERROR_COUNT'].

2026-09-15T14:42:41.992326+00:00 [M]: RISING_ERROR_COUNT diagnosis: tic177352028_p01 and tic33866201_p01 reached the registered 1200-second A deadline (1201.362 and 1201.781 s). Original worker identities are no longer alive. Both remain operational unknowns, with no retry. At the bounded check 292 jobs were terminal, 24 active, 771 pending; no stalled workers. Queue and 60-minute supervision continue. Diagnostic: results/operations/funnel_A_timeout_check_20260915T144057.json. No per-case science opened; controller-owned resource ledger untouched.

2026-09-15T15:43:29.753313+00:00 [M]: funnel_A; completed 582, pending 481, active 24, unknowns 2; C free 45.998 GB; new queue 11.32142 h; triggers [].

2026-09-15T16:44:33.578778+00:00 [M]: funnel_A; completed 790, pending 273, active 24, unknowns 2; C free 54.668 GB; new queue 12.33858 h; triggers [].

2026-09-15T17:45:37.255891+00:00 [M]: funnel_A; completed 1015, pending 48, active 24, unknowns 2; C free 53.037 GB; new queue 13.35637 h; triggers [].

2026-09-15T18:42:05.036403+00:00 [M]: funnel_A; completed 1087, pending 0, active 0, unknowns 2; C free 52.479 GB; new queue 13.76294 h; triggers ['PHASE_CLOSED'].

2026-09-15T18:43:37.677934+00:00 [M]: funnel_A closed with 1087 completed new jobs, 2 operational unknowns and unchanged source hashes. continuation_next.py returned funnel_S: 293 jobs, 24 workers, deadline 300 s. Closed ledger 13.765379553/31.98 h; remaining 18.214620447 h; forecast 65.000 min. Check-in count reconciled to 28. Prelaunch arguments and hashes recorded.

2026-09-15T18:45:09.207374+00:00 [M]: funnel_S launched hidden from checkpoint ccbb8ebee5c38f400a8576cb76ebd5c4b3bc3183; owner PID 29692, creation 1789497886.6157882, command verified. Initial snapshot 24 active, 269 pending, 0 complete, 0 unknowns. Same heartbeat verified ACTIVE at 10 minutes for the single early check; then normal 60 minutes. C free 52.379 GB.

2026-09-15T18:55:39.275511+00:00 [M]: funnel_S; completed 293, pending 0, active 0, unknowns 0; C free 51.955 GB; new queue 13.87029 h; triggers ['PHASE_CLOSED'].

2026-09-15T18:56:53.548121+00:00 [M]: funnel_S closed with 293 completed new jobs, 0 operational unknowns and unchanged source hashes. continuation_next.py returned funnel_B: 29 jobs, 24 workers, deadline 300 s. Closed ledger 13.870911861/31.98 h; remaining 18.109088139 h; forecast 10.000 min. Check-in count reconciled to 29. Prelaunch arguments and hashes recorded.

2026-09-15T19:08:46.042894+00:00 [M]: funnel_B; completed 29, pending 0, active 0, unknowns 0; C free 51.961 GB; new queue 13.87453 h; triggers ['PHASE_CLOSED'].

2026-09-15T19:10:20.990231+00:00 [M]: funnel_B closed all 29 jobs at 2026-09-15T18:58:30.431682+00:00, 0 unknowns, source hashes unchanged, all owned workers closed. N_C fixed at 13 from the B-closure ledger before Part F. B launch/closure owner identity matches the prospective launcher; live initial CPU baseline was not captured because this 13-second phase had closed before verification. The gap is recorded in results/funnel_B_launch_verification.json. Part F engineering continues in this active task; heartbeat restored to normal 60 minutes. No further scientific job or sidecar read yet.

2026-09-15T19:41:24.598274+00:00 [A/M]: Part F v1 methods prospectively registered in PART_F_IMPLEMENTATION_20260915.md and part_f_method_registration_v1.json; 30 focused tests and all 93 Part 3 tests passed. Both prediction locks and all 2861 closed early-funnel evidence hashes verified. No Part F sidecar parse or forced fit has occurred. Existing source/seal bytes are preserved. The frozen B-closure C cap remains 13. Next: one Part F preparation, commit its matching and 1-per-family job plan, then detached controller v4 with the existing hourly routine.

2026-09-15T19:42:08.599623+00:00 [M]: funnel_B closed with 29 completed new jobs, 0 operational unknowns and unchanged source hashes. continuation_next.py returned forced_fits: 1449 jobs, 24 workers, deadline 300 s. Closed ledger 13.878461975/31.98 h; remaining 18.101538025 h; forecast 305.000 min. Check-in count reconciled to 30. Prelaunch arguments and hashes recorded.

2026-09-15T19:44:13.245431+00:00 [M]: forced_fits launched hidden from checkpoint 9c9a1ca54947bee4060f7151b0e80e95e6069745; owner PID 21596, creation 1789501383.6984355, command verified. Initial snapshot 24 active, 1377 pending, 48 complete, 1 unknowns. Same heartbeat verified ACTIVE at 10 minutes for the single early check; then normal 60 minutes. C free 50.803 GB.

2026-09-15T19:45:12.761614+00:00 [M/I]: Bounded forced-fit launch diagnostic examined 11 operational unknowns, all 'No measured in- or out-of-transit level'. No integrity-failure signal. No fits or sources changed and no retries. These measurements remain unknown, never absent or missed. The unchanged queue continues under the single early check then hourly routine. Exact attempt/result hashes are in p10/part3/results/operations/forced_fit_launch_unknown_diagnostic.json.

2026-09-15T19:56:06.266037+00:00 [M]: forced_fits; completed 1449, pending 0, active 0, unknowns 24; C free 50.774 GB; new queue 13.99100 h; triggers ['RISING_ERROR_COUNT', 'PHASE_CLOSED'].

2026-09-15T19:59:08.966998+00:00 [M]: Forced fits CLOSED: 1449 families, presence counts {'PRESENT': 1218, 'ABSENT': 207, 'OPERATIONAL_UNKNOWN': 24}, 0.112535785 queue-hours, all attempts accounted, sources unchanged. All 5809 closed artifacts sealed. Same heartbeat restored to ACTIVE/60; check-in count 31. Ledger 13.995696480/31.98 h. No fit retry. Active task continues C selection and implementation; B-closure cap stays 13.

2026-09-15T20:06:41.311949+00:00 [M]: forced_fits closed with 1449 completed new jobs, 24 operational unknowns and unchanged source hashes. continuation_next.py returned funnel_C: 6 jobs, 3 workers, deadline 12240 s. Closed ledger 13.995732392/31.98 h; remaining 17.984267608 h; forecast 408.000 min. Check-in count reconciled to 31. Prelaunch arguments and hashes recorded.

2026-09-15T20:08:08.248997+00:00 [M]: funnel_C launched hidden from checkpoint 11963ee23f36befca5c793ad9a0ef720ee645b49; owner PID 39436, creation 1789502854.0196433, command verified. Initial snapshot 3 active, 3 pending, 0 complete, 0 unknowns. Same heartbeat verified ACTIVE at 10 minutes for the single early check; then normal 60 minutes. C free 50.709 GB.

2026-09-15T20:18:45.587993+00:00 [M]: funnel_C; completed 0, pending 3, active 3, unknowns 0; C free 50.470 GB; new queue 14.18159 h; triggers [].

2026-09-15T20:19:51.268562+00:00 [M]: Routine check 32, phase funnel_C: exact owner verified True; triggers []. Existing heartbeat verified ACTIVE/60 minutes after the one early check; older P10 heartbeat remains PAUSED. Live scientific ledger untouched.

2026-09-15T21:20:34.969912+00:00 [M]: funnel_C; completed 1, pending 2, active 3, unknowns 0; C free 48.797 GB; new queue 15.21198 h; triggers [].

2026-09-15T21:20:43.512577+00:00 [M]: Routine check 33, phase funnel_C: exact owner verified True; triggers []. Existing heartbeat verified ACTIVE/60 minutes after the one early check; older P10 heartbeat remains PAUSED. Live scientific ledger untouched.

2026-09-15T22:21:09.634304+00:00 [M]: funnel_C; completed 6, pending 0, active 0, unknowns 0; C free 49.434 GB; new queue 16.14574 h; triggers ['PHASE_CLOSED'].

2026-09-15T22:21:40.646626+00:00 [M]: Routine check 34, phase funnel_C: exact owner verified False; triggers ['PHASE_CLOSED']. Existing heartbeat verified ACTIVE/60 minutes after the one early check; older P10 heartbeat remains PAUSED. Live scientific ledger untouched.

2026-09-15T22:24:40.995267+00:00 [M]: C closed and validated, counts {'PASS': 5, 'FAIL': 1}; six one-attempt jobs, 2.150001711 union hours, no unknowns or sidecar access. 88 C artifacts sealed. Active final analysis continues; no controller alive. Ledger 16.145837867/31.98 h.

2026-09-15T23:05:52.823116+00:00 [M]: FINAL_CLOSED. All 436 paired searches, F/G/H and five autopsies complete; no owner alive. Both H rules fire with negative slopes and unstable SNR50 interpretation. New queue 16.155157144/31.98 h; acquisition upper charge 12105787657 bytes; C free 49.096 GB. Routine PAUSED and freshly verified in manifests/final_supervision_disabled.json; 34 actual check-ins retained. Final seals/local commit and export are engineering delivery; no further science or p10.1 iteration.

2026-09-16T03:58:08.919539+00:00 [M]: Final evidence audit PASS: 35891 unique parent files, 12413 new-data files and 124 source files sealed; all recorded owners/workers closed. Every reported primary fraction matches the fixed 10,000-host-bootstrap analysis. Five autopsies and final DECISION written after disabled supervision verification. Final state RETENTION_MEASURED_CALIBRATION_OPTIMISTIC; local commit and exported receipt identify this completed delivery.
