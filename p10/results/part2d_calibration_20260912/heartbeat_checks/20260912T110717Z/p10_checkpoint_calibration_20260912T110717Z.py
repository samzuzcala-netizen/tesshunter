from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,sys,time,tomllib,shutil

R=Path(r'C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter')
sys.path.insert(0,str(R/'p10/protocol'))
import run_part2d_injection_search as Q
O=R/'p10/results/part2d_calibration_20260912';W=O/'heartbeat_checks/20260912T110717Z'
report=Q.read(W/'check.json');fa=Q.read(O/'false_alarm_closed_seal_20260912.json');bound=Q.read(O/'geometric_C_load_bound.json')
inj=Q.read(W/'settled_injection_artifacts.json')
assert report['state']=='healthy_injection_calibration_running' and not report['shorten_schedule']
assert report['completed_injections']==len(inj['complete_job_ids'])==121
assert bound['C_load_upper_bound']<150 and not bound['stop_rule_1_evaluated']
def git(*args):
    p=subprocess.run(['git','-C',str(R),'-c','maintenance.auto=false','-c','gc.auto=0',*args],capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout
assert not git('diff','--cached','--name-only').strip()
assert not git('diff','--name-only').strip()
expected=Q.read(Path('work/p10_20260912T110717Z_automation_expected.json'))
actual=tomllib.loads(Path(r'C:\Users\seanj\.codex\automations\continue-local-p10-execution\automation.toml').read_text())
for k in ('id','kind','name','prompt','rrule','status'):assert actual[k]==expected[k],k
assert actual['target_thread_id']==expected['targetThreadId']
Q.save(W/'automation_updated_verified.json',dict(utc=Q.utc(),saved=actual,exact_prompt_match=True,
       schedule_minutes=120,reason='FA phases closed; injection A/S and full bootstrap remain, no credible finish within two hours.'),exclusive=True)
f=fa['metrics']
fa_md=f'''# P10 closed false-alarm calibration

The same 300 selected-e uninjected controls were collected under `survey_p10` and processed into fresh `p10.0` A/S records. Every expected record validates against its identity, input configuration, named preset/rules, exact writer thresholds, ephemeris, timing and A/S linkage. The original A phase closed naturally; its corrected successor validated all 709 A records without re-executing them, then completed S at 2026-09-12 10:41:53 UTC.

| Level | Count | Per control star |
|---|---:|---:|
| Accepted search candidates | {f['accepted']} | {f['accepted_per_star']:.6f} |
| Original pre-gate | {f['pregate']} | {f['pregate_per_star']:.6f} |
| Stage A pass | {f['stageA_pass']} | {f['stageA_pass_per_star']:.6f} |
| A + secondary pass (FA_S) | {f['stageA_pass_and_secondary']} | {f['stageA_pass_and_secondary_per_star']:.9f} |

Secondary ran on all 45 A passers and the original seeded 10% A-failure sample (66 failures; 41 S PASS, 25 S FAIL). The failure sample does not contribute to FA_S. There are 111 complete S records. Against the earlier selected-e p8.0 experiment, all 709 A keys/decisions and 111 S keys/gates match exactly. This is decision equality, not a claim that fresh timestamps or every serialized field is identical.

The frozen false-alarm term for 2,531 stars is **(2/300)*2,531 = {fa['projected_FA_only_C_load_2531']:.9f}**. This is an extrapolated control-candidate rate, not proof that the surviving controls contain no real signals. Its sampling uncertainty and constant-per-star assumption remain. The recovery curve, model signal yield and complete Stop Rule 1 decision are still pending.

The closed seal `false_alarm_closed_seal_20260912.json` records all {len(fa['files'])} artifact hashes, the full metrics and comparison. Original P8/P9 outcomes, numerical thresholds and scientific worker source are unchanged.
'''
(O/'FALSE_ALARM_CALIBRATION_P10.md').write_text(fa_md,encoding='utf-8')
bound_md=f'''# Conservative P10 Stage C workload bound

The fixed central DC15 model and claimed fraction 0.03 imply an expected-load upper bound of **{bound['C_load_upper_bound']:.9f}**, below the unchanged 150-run stop-rule limit. This supplies a sufficient conservative check of the workload component. **Stop Rule 1 is not yet decided:** the complete injection calibration, SNR50_S threshold and final yield review remain pending.

| Component | Expected-count upper bound |
|---|---:|
| Original 2,000 stars, perfect recovery | {bound['original_2000_perfect_recovery_signal_bound']:.9f} |
| Any additional subset of at most 531 stars | {bound['any_531_additional_perfect_recovery_signal_bound']:.9f} |
| Frozen empirical FA_S * 2,531 term | {bound['FA_S_times_2531']:.9f} |
| Total | {bound['C_load_upper_bound']:.9f} |

For each star and occurrence cell, the original P8 machinery multiplies rate, geometric transit probability, recovery probability and the unclaimed fraction, then averages over its four impact parameters. Recovery probabilities and their average are at most one. Setting all of them to one therefore bounds every possible logistic recovery curve; no prepared-noise measurement is needed for this bound.

The additional-star calculation uses the 531 largest geometric yield weights in the **entire 1,837-star bare-SPOC-only source pool**, a superset of the eventual Part 3 population. Any subset of at most 531 of those stars has a sum no larger than this value. These 531 maximizing identities are mathematical witnesses, **not selected targets**. No new candidate outcome or TCE ephemeris was inspected, and no Part 3 selection or policy was adopted.

The complete final calibration should still supply the original 2,000-star model yield with the new curve and claimed fraction 0.03. The prospective full-population signal expectation is bounded between that original-population value and that value plus {bound['any_531_additional_perfect_recovery_signal_bound']:.9f}. This is a missing-input bounding range, not a confidence interval or a measured-noise estimate for the additional stars. Report it with the calibrated yield and HU19 sensitivity.

This is a bound on **model expectation**, not on the realized candidate count. It retains the central occurrence model, stellar metadata, claimed fraction and empirical FA extrapolation assumptions. Occurrence-model sensitivity and false-alarm sampling uncertainty remain; the later realized 150-run Stage C cap still applies. Every source/input hash and per-star bound is in `geometric_C_load_bound.json`. Three focused tests verify the subset/probability bound, original geometry convention and rejection of invalid inputs.
'''
(O/'geometric_C_load_bound.md').write_text(bound_md,encoding='utf-8')
hp=R/'HANDOFF_P10.md';raw=hp.read_bytes();marker=b'## 0. Pre-registered decision rules'
assert Q.frozen_section_sha()==Q.FROZEN_SHA
note=f'''### False-alarm calibration closed; injection A/S progressing, 2026-09-12 11:19 UTC [M]

The original FA A owner closed at the anticipated record-schema guard. The checked successor verified that exact stop, all 709 valid A records and original source/input hashes, preserved their bytes/timers without re-execution, then completed **111 required S scans at 10:41:53 UTC**. FA A has 45 passers; 66 seeded A-failure controls also received S, and do not count toward FA_S. **FA_S is 2/300 = 0.006666667 per star**. All 709 A decisions and 111 S gates match the earlier selected-e p8.0 run, with no key/decision differences. The closed seal hashes {len(fa['files'])} FA artifacts. See `p10/results/part2d_calibration_20260912/FALSE_ALARM_CALIBRATION_P10.md`, `false_alarm_closed_seal_20260912.json` and the complete phase/diagnostic receipts. The old controller remains closed and must not restart.

The checked controller started injection A/S at 10:41:53 UTC. At this checkpoint **{report['completed_injections']}/1,240 injections have complete validated A/S pairs**, with {report['remaining_injections']} remaining; all 16 worker indices are present and {report['matching_workers_with_cpu_progress']} continuing workers show positive CPU deltas. The owner/child creation identities, correction manifest and frozen source/input hashes verify. No invalid current record was found. A/S progress is ongoing, so the snapshot census and subsequently hashed pairs have their recorded observation times. This checkpoint preserves all {len(inj['files'])} files belonging to the 121 complete pairs; in-progress job artifacts remain live.

Whole-queue timing does not support a short wake: {report['completed_pairs_per_hour']:.2f} completed pairs/hour overall, with {report['extrapolated_remaining_injection_h']:.2f} hours extrapolated for remaining injection work; the 15- and 30-minute windows both give {report['rolling_windows'][0]['extrapolated_remaining_h']:.2f} hours. These are descriptive extrapolations over the changing search-SNR-ordered host mix, not a firm ETA, and the full bootstrap follows. The existing heartbeat is verified ACTIVE every **120 minutes** with its full prompt updated for the closed FA phases and current injection owner. Latest health/schedule evidence: `p10/results/part2d_calibration_20260912/heartbeat_checks/20260912T110717Z/`. Continue with **run_part2d_calibration_checked.py inspect**; never duplicate a healthy owner or edit manifest-frozen inputs/source. No unchanged-source baseline was repeated.

A separate conservative C-load expectation bound resolves the missing-noise projection concern without opening later outcomes. Under the original DC15 geometry/search band and claimed fraction 0.03, perfect recovery on the original 2,000 stars gives {bound['original_2000_perfect_recovery_signal_bound']:.9f}; the 531 largest weights in the whole 1,837-star bare-SPOC source pool bound any eventual additional subset by {bound['any_531_additional_perfect_recovery_signal_bound']:.9f}. Together with FA_S*2,531={bound['FA_S_times_2531']:.9f}, the conservative model expectation is at most **{bound['C_load_upper_bound']:.9f} < 150**. This is a sufficient check of the workload component, not a realized-count guarantee, confidence interval, Part 3 selection, or completed Stop Rule 1 decision. Full proof, source/input/per-star hashes and limitations: `geometric_C_load_bound.json` and `.md` in the same results directory. Three focused bound tests passed; no scientific worker source was changed. The full final recovery curve, bootstrap interval, side-by-side table, actual original-population yield/new-curve range and HU19 sensitivity still need review. SNR50_S<=14.0 remains pending. Only the complete original stop-rule review can authorize later stages.

'''
after=raw.replace(marker,note.encode()+marker,1)
old=after.splitlines()[2];assert old.startswith(b'**Resume here:')
after=after.replace(old,b'**Resume here: FA CALIBRATION CLOSED; INJECTION A/S RUNNING.** The checked controller has completed FA A/S and is processing all 1,240 recovered injections before the full bootstrap and original Stop Rule 1. Use the latest dated entry and RESUME_P10.md. The adaptive heartbeat remains ACTIVE every two hours.',1)
hp.write_bytes(after);assert Q.frozen_section_sha()==Q.FROZEN_SHA
rp=R/'RESUME_P10.md'
entry=f'''# P10 current continuation: FA closed; injection A/S running

Checkpoint 2026-09-12 11:19 UTC. Both FA phases are complete: **709 A records, 111 required S records, 45 A passers and 2 A+S survivors among 300 controls**. All A/S identities and decisions match the prior selected-e p8.0 comparison. The checked successor completed its owner-boundary recovery without repeating A. The original controller and lock are closed; preserve its schema-guard diagnostics.

The current checked owner is running injection A/S with 16 workers since 10:41:53 UTC. **121/1,240 injections have complete validated A/S pairs; 1,119 remain at this checkpoint.** The owner/child creation identities, all frozen source/input hashes and continuing worker CPU progress verify. Use `p10/protocol/run_part2d_calibration_checked.py inspect`; state/lock/logs and receipts are in `p10/results/part2d_calibration_20260912/`, outputs in `data/survey/p10/part2d/calibration/`. Never repeat prepare/register, completed FA work or a healthy owner, and never edit manifest-frozen source/inputs. The full five-level 1000-bootstrap analysis follows automatically.

The adaptive heartbeat is verified ACTIVE at **120 minutes**. Descriptive whole-injection estimates exceed five hours, with bootstrap still pending; no early wake is warranted. Latest immutable checkpoint: `p10/results/part2d_calibration_20260912/heartbeat_checks/20260912T110717Z/`. Closed FA report/seal and 121 complete injection artifact groups are saved locally.

The independent conservative workload expectation bound is **148.931095986 < 150**, under the fixed central DC15 model, claimed fraction 0.03 and empirical FA term. It uses perfect recovery and the 531 largest geometric weights from the whole bare-SPOC source pool, without choosing Part 3 targets or reading new real outcomes. See `geometric_C_load_bound.md` and `.json`. The final new-curve yield for the original 2,000 stars and its prospective-population bounding range/HU19 sensitivity remain to be reported. This bound does not complete Stop Rule 1: **full_funnel_with_pregate SNR50_S<=14.0 is still pending**. On full calibration closure, validate/seal every record, report the complete table beside p8.0 in docs/RULES.md, finish the yield and original stop-rule review, then stop/commit/pause if either criterion fails or continue Parts 3-5 if both pass. Keep all later stop rules, exposure caveats, section 0 bytes and P8/P9 boundaries intact. Earlier entries are historical.

---

'''
rp.write_bytes(entry.encode()+rp.read_bytes())
shutil.copy2(Path(__file__),W/Path(__file__).name)
closed_names=['fa_a_complete.json','fa_a_checked_complete.json','fa_s_checked_complete.json',
    'original_schema_guard_stop_state.json','calibration_state.json','calibration_driver_20260912T0853Z.log',
    'calibration_driver_20260912T0853Z.stderr.log','fa_a_20260912T085316Z.log','fa_s_checked_20260912T104038Z.log',
    'false_alarm_closed_seal_20260912.json','FALSE_ALARM_CALIBRATION_P10.md',
    'geometric_C_load_bound.json','geometric_C_load_bound.md','load_bound_tests.json']
paths=['HANDOFF_P10.md','RESUME_P10.md','p10/protocol/project_part2d_load_bound.py','tests/test_p10_load_bound.py',W.relative_to(R).as_posix()]
paths += [(O/n).relative_to(R).as_posix() for n in closed_names]
artifacts=fa['files']+inj['files']
for row in artifacts:
    assert Q.sha(R/row['path'])==row['sha256'],row['path']
paths += [r['path'] for r in artifacts]
fp=Path('work/p10_stage_calibration_20260912T110717Z.txt').resolve();fp.write_bytes(b'\0'.join(p.encode() for p in sorted(set(paths)))+b'\0')
for attempt in range(3):
    try:
        git('-c','core.safecrlf=false','add',f'--pathspec-from-file={fp}','--pathspec-file-nul');break
    except RuntimeError as exc:
        if 'Permission denied' not in str(exc) or attempt==2:raise
        assert not git('diff','--cached','--name-only').strip();time.sleep(.5)
staged=git('diff','--cached','--name-only').splitlines()
assert all(p in paths or p.startswith(W.relative_to(R).as_posix()+'/') for p in staged)
assert not git('diff','--cached','--check').strip()
out=git('commit','-m','Prompt 10: seal false-alarm calibration and checkpoint 121 injection funnels')
Path('work/p10_commit_calibration_20260912T110717Z.log').write_text(out,encoding='utf-8')
assert not git('diff','--name-only').strip()
assert Q.frozen_section_sha()==Q.FROZEN_SHA
print(json.dumps(dict(commit=git('rev-parse','HEAD').strip(),files=len(staged),completed_injections=121,
     FA_A=709,FA_S_scanned=111,FA_S_survivors=2,C_model_load_bound=bound['C_load_upper_bound'],schedule_minutes=120),indent=2))
