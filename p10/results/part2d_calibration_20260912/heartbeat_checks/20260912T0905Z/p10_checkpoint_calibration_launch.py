from pathlib import Path
from datetime import datetime,timezone
import json,os,shutil,subprocess,sys,time,tomllib

R=Path(r'C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter')
sys.path.insert(0,str(R/'p10/protocol'))
import run_part2d_calibration_checked as K
C=K.C
import run_part2d_injection_search as Q
O=C.OUT
W=O/'heartbeat_checks/20260912T0905Z'
W.mkdir(parents=True,exist_ok=False)
def git(*args):
    p=subprocess.run(['git','-C',str(R),'-c','maintenance.auto=false','-c','gc.auto=0',*args],capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout
assert not git('diff','--cached','--name-only').strip()
assert not git('diff','--name-only').strip()
expected=json.loads(Path('work/p10_calibration_automation_expected.json').read_text())
automation=tomllib.loads(Path(r'C:\Users\seanj\.codex\automations\continue-local-p10-execution\automation.toml').read_text())
for k in ('id','kind','name','prompt','rrule','status'):assert automation[k]==expected[k],k
assert automation['target_thread_id']==expected['targetThreadId']
C.save(W/'automation_verified.json',dict(utc=C.utc(),saved=automation,exact_prompt_match=True,normal_minutes=120),exclusive=True)
m,correction=K.verify()
assert len(m['recovered_jobs'])==1240 and len(m['fa_jobs'])==709
previous_path=sorted(O.glob('inspect_*.json'))[-1]
previous=C.read(previous_path)
now=C.process_snapshot();state=C.read(C.STATE);lock=C.read(C.LOCK)
checked_state=C.read(K.STATE);checked_lock=C.read(K.LOCK)
assert checked_state['status']=='waiting_for_original_fa_a_boundary'
assert checked_state['owner']==checked_lock
assert C.psutil.Process(checked_lock['pid']).create_time()==checked_lock['created_epoch']
assert state['status']=='running' and state['phase']=='fa_a'
assert lock['pid']==state['owner']['pid'] and lock['created_epoch']==state['owner']['created_epoch']
assert lock['manifest_sha256']==C.sha(C.MANIFEST)
for pid,created in ((lock['pid'],lock['created_epoch']),(state['child_pid'],state['child_created_epoch'])):
    assert C.psutil.Process(pid).create_time()==created
assert not now['inaccessible_pids']
def workers(snap):
    return {p['pid']:p for p in snap['processes'] if 'slice' in p['command'] and '--index' in p['command']}
a=workers(previous['process_snapshot']);b=workers(now)
progress=[pid for pid,p in b.items() if pid in a and a[pid]['created_epoch']==p['created_epoch'] and
          p['cpu_user_s']+p['cpu_kernel_s']>a[pid]['cpu_user_s']+a[pid]['cpu_kernel_s']]
indices={p['command'][p['command'].index('--index')+1] for p in b.values()}
assert indices==set(map(str,range(16))) and progress,(indices,progress)
census={p:C.phase_census(p,m) for p in C.PHASES[:-1]}
assert all(not d.get('invalid') for d in census.values()),census
report=dict(utc=C.utc(),state='healthy_calibration_running_with_checked_successor',phase='fa_a',owner=lock,controller_state=state,
            checked_successor_state=checked_state,checked_successor_lock=checked_lock,
            validation_correction=correction,
            manifest_sha256=C.sha(C.MANIFEST),census=census,process_snapshot=now,
            earlier_inspection=str(previous_path.relative_to(R)),matching_workers_with_cpu_progress=len(progress),
            configured_worker_indices=sorted(indices,key=int),schedule_minutes=120,shorten_schedule=False,
            timing='Initial FA A is still running; FA S, all 1240 injection A/S jobs and five-level 1000-bootstrap analysis remain. Original P8 injection A median was 226 s (p90 1133.6 s). A comparable current whole-calibration finish within two hours is not established; retain the default rather than guessing an early ETA.')
C.save(W/'check.json',report,exclusive=True)
shutil.copy2(previous_path,W/previous_path.name)
for p in (C.STATE,C.LOCK,K.STATE,K.LOCK):shutil.copy2(p,W/p.name)
for p in [R/state['log'],O/'calibration_driver_20260912T0853Z.log',O/'calibration_driver_20260912T0853Z.stderr.log']:
    shutil.copy2(p,W/p.name)
shutil.copy2(Path(__file__),W/Path(__file__).name)
hp=R/'HANDOFF_P10.md';raw=hp.read_bytes();marker=b'## 0. Pre-registered decision rules'
note=f'''### Full Part 2d calibration launched, 2026-09-12 08:53 UTC [M]

The full regression suite passes **774 tests, 1 skipped, 9 warnings in 137.37 s**, including eight focused calibration routing/ownership/record-validation checks. All original P7/P8 reproduction receipts remain binding and original shared source is unchanged. The new isolated adapters retain the original recovery, A, bound-S, seeded FA failure sampling and logistic/1000-bootstrap definitions. After launch the initial controller incorrectly compared Stage A record metadata to the rules-summary schema; the worker records match the original V.THRESHOLDS schema and every numerical threshold agrees. The separate checked successor corrects that validation-only defect without editing any live/frozen worker source. Ten focused correction/controller/routing tests passed in 24.05 s, including rejection of changed numerical cuts and incomplete A. Fresh records explicitly name p10.0 and survey_p10; no original outcome was retagged.

Preparation verifies all 2,100 search outcomes and all 8,400 sealed search artifacts, the original selected-e 300-star FA searches, the full original calibration population, and the frozen section/source/input hashes. **1,240 injections are recovered; 709 FA candidates pass the original pre-gate.** Every original injection model, stellar input, preparation/rotation diagnostic, raw cadence count/baseline/unit count and ingest key matches. The same existing un-injected prepared paths are hashed. All 2,100 expected-SNR cache entries were copied byte for byte into P10 with that explicit equality proof. Details: p10/results/part2d_calibration_20260912/expected_snr_reuse.json and calibration_manifest.json (SHA256 {C.sha(C.MANIFEST)}).

The original controller launched at 08:53:12 UTC and owns the current 16-worker FA A phase. It is allowed to close naturally at its known record-schema guard. The registered checked successor waits for that exact owner/launcher closure, verifies the anticipated stop and complete valid A population, preserves all A bytes/timers, skips completed A, then runs FA S, all recovered-injection A/S and analysis. Its source and correction manifest are independently hashed; original manifest/source/input guards still pass. This successor is waiting with a verified live owner. See calibration_guard_correction.json, calibration_checked_state.json and calibration_checked.lock. Current inspection validates the lock/owner/child creation times and all 16 worker indices; {len(progress)} continuing worker processes have positive CPU deltas. Every currently settled record validates. The latest immutable operational check is p10/results/part2d_calibration_20260912/heartbeat_checks/20260912T0905Z/check.json. Use **p10/protocol/run_part2d_calibration_checked.py inspect**; current mutable state/lock/logs are under p10/results/part2d_calibration_20260912. Scientific outputs are under data/survey/p10/part2d/calibration. Never repeat prepare, duplicate a healthy owner or edit any manifest-frozen source/input while active. A stopped phase requires preserved diagnostics and reviewed recovery, not a blind run.

The existing heartbeat's full prompt now describes this phase and is verified ACTIVE every **120 minutes**. All pending phases count toward the whole-computation ETA. There is not yet a credible near-term whole-calibration finish, so no short interval is scheduled. On closure, validate every named record and all frozen inputs, seal the complete results, report p10.0 beside p8.0 in docs/RULES.md section 9, calculate E_S using the P8 yield machinery with claimed fraction 0.03, and apply original Stop Rule 1. Report projection population assumptions explicitly: the original yield script defaults to the 2,000 P8 targets; the C-load formula specifies FA_S times 2,531 plus E_S. Resolve that population interpretation before stating the load. A metadata-only inventory found no cached prepared/raw curves for the raw bare-SPOC-TCE pool; no new candidate search/funnel outcomes or TCE ephemerides were opened. Later real/held-out stages remain closed until Stop Rule 1 passes. No protocol threshold changed.

'''
after=raw.replace(marker,note.encode()+marker,1)
old=after.splitlines()[2];assert old.startswith(b'**Resume here:')
after=after.replace(old,b'**Resume here: PART 2D FULL CALIBRATION RUNNING.** The 2,100-job selected search is closed. The guarded calibration controller now runs FA A/S, all 1,240 recovered-injection A/S jobs and the full bootstrap in sequence. Use the latest dated entry and RESUME_P10.md. The adaptive heartbeat is ACTIVE every two hours.',1)
hp.write_bytes(after);assert Q.frozen_section_sha()==Q.FROZEN_SHA
rp=R/'RESUME_P10.md'
entry=f'''# P10 current continuation: full calibration running

Launched 2026-09-12 08:53:12 UTC. The original full 2,100-injection selected-preset search is closed and committed ({git('rev-parse','HEAD').strip()}); calibration has **1,240 recovered injections** and the same **300-star FA population / 709 pre-gate candidates**. Full regression: **774 passed, 1 skipped**. Expected-SNR cache reuse has complete model/stellar/preparation/ingest/path equality proof and original/cache-input hashes. Fresh P10 records name p10.0/survey_p10.

Use `p10/protocol/run_part2d_calibration_checked.py inspect` with the existing venv and offline/single-thread BLAS environment. Manifest/state/lock/phase logs: `p10/results/part2d_calibration_20260912/`; output root: `data/survey/p10/part2d/calibration/`. Current phase FA A has a validated owner and 16 active worker indices. The registered checked successor waits for this exact original owner/launcher to finish FA A and close at the anticipated metadata-schema guard. It then validates all 709 A records, preserves their bytes/timers, skips their re-execution, and runs FA S, injection A/S and the original five-level 1000-bootstrap analysis. Read calibration_checked_state.json and its lock alongside the original state while it waits. A waiting successor plus healthy original FA A workers is intentional. Never repeat correction registration or launch another successor. **Do not repeat prepare, restart healthy owners, edit manifest-frozen code/inputs, run old search/C controllers or blindly remove a lock.** A failure stops for review and must preserve its diagnostics.

The existing adaptive heartbeat is verified ACTIVE every two hours with the full new-phase continuation prompt. Include all remaining phases in finish estimates; shorten only near a credible whole-computation finish, restoring 120 minutes on that wake. Latest immutable launch/health/schedule receipt: `p10/results/part2d_calibration_20260912/heartbeat_checks/20260912T0905Z/`.

When complete, validate and seal every named A/S record, report the full level table beside p8.0 and update docs/RULES.md section 9. Compute E_S using P8 yield machinery/new curve/claimed fraction 0.03, explicitly resolving the projection population (original model defaults to 2,000 targets; formula is FA_S*2,531+E_S). Apply frozen Stop Rule 1: full_funnel_with_pregate SNR50_S<=14.0 AND projected C load<=150. If either fails, localize losses, document numbers, commit and stop/pause the heartbeat; otherwise continue Parts 3-5 and all later stop rules. Preserve section 0 bytes, P8/P9 read-only outputs and exposure caveats. Earlier entries are historical.

---

'''
rp.write_bytes(entry.encode()+rp.read_bytes())
paths=['HANDOFF_P10.md','RESUME_P10.md',
       'p10/protocol/p10_funnel_calibration.py','p10/protocol/p10_completeness_calibration.py','p10/protocol/run_part2d_calibration.py','p10/protocol/run_part2d_calibration_checked.py',
       'tests/test_p10_calibration_controller.py','tests/test_p10_calibration_routing.py','tests/test_p10_calibration_schema_correction.py',
       'p10/results/part2d_calibration_20260912/adapter_routing.json','p10/results/part2d_calibration_20260912/calibration_guard_correction.json','p10/results/part2d_calibration_20260912/schema_correction_tests.json','p10/results/part2d_calibration_20260912/checked_launch_20260912.json',
       'p10/results/part2d_calibration_20260912/calibration_manifest.json',
       'p10/results/part2d_calibration_20260912/expected_snr_reuse.json',
       'p10/results/part2d_calibration_20260912/full_regression.json','p10/results/part2d_calibration_20260912/full_regression.log',
       'p10/results/part2d_calibration_20260912/launch_20260912.json',W.relative_to(R).as_posix(),
       'data/survey/p10/part2d/calibration/expected_snr_p10.json',
       'data/survey/p10/part2d/calibration/fa_funnel/candidates.csv',
       'data/survey/p10/part2d/calibration/fa_funnel/survivors.csv',
       'data/survey/p10/part2d/calibration/fa_funnel/collect_p10.json']
fp=Path('work/p10_calibration_launch_stage_paths.txt').resolve();fp.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0')
for attempt in range(3):
    try:
        git('-c','core.safecrlf=false','add',f'--pathspec-from-file={fp}','--pathspec-file-nul');break
    except RuntimeError as exc:
        if 'Permission denied' not in str(exc) or attempt==2:raise
        assert not git('diff','--cached','--name-only').strip();time.sleep(.5)
staged=git('diff','--cached','--name-only').splitlines()
assert all(p in paths or p.startswith(W.relative_to(R).as_posix()+'/') for p in staged)
assert not git('diff','--cached','--check').strip()
out=git('commit','-m','Prompt 10: launch guarded full p10.0 A/S calibration')
Path('work/p10_calibration_launch_commit.log').write_text(out,encoding='utf-8')
assert Q.frozen_section_sha()==Q.FROZEN_SHA
print(json.dumps(dict(commit=git('rev-parse','HEAD').strip(),staged_files=len(staged),census=census,
      workers_with_cpu_progress=len(progress),schedule_minutes=120),indent=2))
