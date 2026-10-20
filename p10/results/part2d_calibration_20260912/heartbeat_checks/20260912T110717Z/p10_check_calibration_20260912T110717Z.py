from pathlib import Path
from datetime import datetime,timezone
import collections,json,math,shutil,sys,tomllib

R=Path(r'C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter')
sys.path.insert(0,str(R/'p10/protocol'))
import run_part2d_calibration_checked as K
import p10_completeness_calibration as F
C=K.C;O=C.OUT;W=O/'heartbeat_checks/20260912T110717Z'
W.mkdir(parents=True,exist_ok=False)
m,correction=K.verify()
prior_path=O/'inspect_checked_20260912T110757Z.json';prior=C.read(prior_path)
state=C.read(K.STATE);lock=C.read(K.LOCK);snap=C.process_snapshot()
assert state['status']=='running' and state['phase']=='injection_as'
assert not C.LOCK.exists() and state['owner']==lock
assert lock['correction_sha256']==C.sha(K.MANIFEST)
for pid,created in ((lock['pid'],lock['created_epoch']),(state['child_pid'],state['child_created_epoch'])):
    assert C.psutil.Process(pid).create_time()==created
assert not snap['inaccessible_pids']
def workers(snapshot):
    return {p['pid']:p for p in snapshot['processes'] if 'slice' in p['command'] and '--index' in p['command']}
a,b=workers(prior['process_snapshot']),workers(snap)
indices={p['command'][p['command'].index('--index')+1] for p in b.values()}
progress=[pid for pid,p in b.items() if pid in a and p['created_epoch']==a[pid]['created_epoch'] and
          p['cpu_user_s']+p['cpu_kernel_s']>a[pid]['cpu_user_s']+a[pid]['cpu_kernel_s']]
assert indices==set(map(str,range(16))) and progress
census={p:C.phase_census(p,m) for p in C.PHASES[:-1]}
assert census['fa_a']['complete'] and census['fa_s']['complete']
assert all(not x.get('invalid') for x in census.values())
assert not census['injection_as']['complete']
fa=F.fa_funnel_counts(300,'p10.0')
assert fa['stageA_done']==709 and fa['stageA_pass']==45 and fa['stageA_pass_and_secondary']==2
assert fa['stageA_failure_sample_n']==66
old_root=R/'data/survey/p10/fa_2b/e';new_root=C.CAL/'fa_funnel'
comparison={}
for stage,field in (('stageA','decision'),('secondary','gate')):
    new={p.name:C.read(p) for p in (new_root/stage).glob('*.json')}
    old={p.name:C.read(p) for p in (old_root/stage).glob('*.json')}
    assert new.keys()==old.keys()
    differences=[k for k in new if new[k][field]!=old[k][field]]
    assert not differences
    comparison[stage]=dict(records=len(new),key_differences=0,decision_differences=0)
fa_artifacts=[]
for p in sorted(new_root.rglob('*')):
    if p.is_file():fa_artifacts.append(dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=C.sha(p)))
fa_seal=dict(utc=C.utc(),status='FA_complete_verified',rules='p10.0',config='survey_p10',metrics=fa,
    required_secondary_scans=111,original_failure_sample_excluded_from_FA_S=True,
    selected_e_p8_comparison=comparison,projected_FA_only_C_load_2531=fa['stageA_pass_and_secondary_per_star']*2531,
    E_S_pending=True,original_controller_closed=True,original_A_reexecuted=False,
    manifest_sha256=C.sha(C.MANIFEST),correction_sha256=C.sha(K.MANIFEST),files=fa_artifacts)
seal_path=O/'false_alarm_closed_seal_20260912.json';C.save(seal_path,fa_seal,exclusive=True)
complete=[];injection_artifacts=[];timings=[];finish_times=[];a_only=[]
for row in m['recovered_jobs']:
    job=C.injection_job(row);key=F.kkey(job['tic_id'],job['period']);root=C.CAL/'inj_funnel'/row['job_id']
    ap=root/'stageA'/(key+'.json');sp=root/'secondary'/(key+'.json')
    if not sp.exists():
        if ap.exists():a_only.append(row['job_id'])
        continue
    ra=K.check_record(ap,'A',job);rs=K.check_record(sp,'S',job,ra['decision'])
    complete.append(row['job_id']);timings.append(float(ra['seconds'])+float(rs['seconds']))
    finish_times.append(sp.stat().st_mtime)
    for p in sorted(root.rglob('*')):
        if p.is_file():injection_artifacts.append(dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=C.sha(p)))
assert len(complete)<1240 and complete
now=datetime.now(timezone.utc);started=datetime.fromisoformat(state['utc'])
elapsed_h=(now-started).total_seconds()/3600
rate=len(complete)/elapsed_h;remaining_h=(1240-len(complete))/rate
windows=[]
for minutes in (15,30):
    exposure=min(minutes/60,elapsed_h);n=sum(t>=now.timestamp()-minutes*60 for t in finish_times)
    h=(1240-len(complete))/(n/exposure) if n else None
    windows.append(dict(minutes=minutes,complete=n,exposure_h=exposure,extrapolated_remaining_h=h))
assert remaining_h>2 and all(w['extrapolated_remaining_h'] is None or w['extrapolated_remaining_h']>2 for w in windows)
art_path=W/'settled_injection_artifacts.json'
C.save(art_path,dict(utc=C.utc(),complete_job_ids=complete,files=injection_artifacts),exclusive=True)
automation=tomllib.loads(Path(r'C:\Users\seanj\.codex\automations\continue-local-p10-execution\automation.toml').read_text())
assert automation['id']=='continue-local-p10-execution' and automation['status']=='ACTIVE'
assert automation['rrule']=='FREQ=MINUTELY;INTERVAL=120'
assert automation['target_thread_id']=='01a08dce-53a4-79a1-9b18-0929d292b272'
report=dict(utc=C.utc(),state='healthy_injection_calibration_running',phase='injection_as',census=census,
    completed_injections=len(complete),remaining_injections=1240-len(complete),A_only=len(a_only),
    injection_completed_job_ids=complete,matching_workers_with_cpu_progress=len(progress),process_snapshot=snap,
    controller_state=state,controller_lock=lock,earlier_inspection=str(prior_path.relative_to(R)),
    FA_seal=str(seal_path.relative_to(R)),FA_seal_sha256=C.sha(seal_path),
    elapsed_phase_h=elapsed_h,completed_pairs_per_hour=rate,extrapolated_remaining_injection_h=remaining_h,
    rolling_windows=windows,mean_A_plus_S_seconds=sum(timings)/len(timings),
    timing_caveat='Descriptive throughput from a changing, search-SNR-ordered host mix, not a firm ETA. Remaining injection A/S plus five-level 1000-bootstrap analysis all count; none of these complete-queue estimates supports a finish within two hours.',
    shorten_schedule=False,schedule_minutes=120,automation=automation)
C.save(W/'check.json',report,exclusive=True)
shutil.copy2(prior_path,W/prior_path.name)
for p in (K.STATE,K.LOCK):shutil.copy2(p,W/p.name)
for p in [R/state['log'],O/'checked_driver_20260912.log',O/'checked_driver_20260912.stderr.log']:
    shutil.copy2(p,W/p.name)
shutil.copy2(Path(__file__),W/Path(__file__).name)
print(json.dumps({k:report[k] for k in ('completed_injections','remaining_injections','A_only','matching_workers_with_cpu_progress',
    'completed_pairs_per_hour','extrapolated_remaining_injection_h','rolling_windows','schedule_minutes')},indent=2))
print(json.dumps(dict(FA_A=709,FA_S_scanned=111,FA_S_survivors=2,FA_stars=300,FA_artifacts=len(fa_artifacts),
    settled_injection_artifacts=len(injection_artifacts)),indent=2))
