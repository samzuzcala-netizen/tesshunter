"""Save a healthy injection-phase checkpoint after a recent canonical inspection."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,shutil,subprocess,sys,tomllib

R=Path(r'C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter')
sys.path.insert(0,str(R/'p10/protocol'))
import run_part2d_calibration_checked as K
C=K.C;O=C.OUT
ap=argparse.ArgumentParser();ap.add_argument('stamp');ap.add_argument('inspection');args=ap.parse_args()
W=O/'heartbeat_checks'/args.stamp
assert W.resolve().is_relative_to((O/'heartbeat_checks').resolve())
W.mkdir(parents=True,exist_ok=False)
inspection_path=O/args.inspection
assert inspection_path.resolve().is_relative_to(O.resolve())
first=C.read(inspection_path)
now=datetime.now(timezone.utc)
assert 0<=(now-datetime.fromisoformat(first['utc'])).total_seconds()<1800
assert first['state']['status']=='running' and first['state']['phase']=='injection_as'
assert first['census']['fa_a']['complete'] and first['census']['fa_s']['complete']
assert all(not x.get('invalid') for x in first['census'].values())
assert not first['process_snapshot']['inaccessible_pids']
# The canonical inspect above already rehashed every source/input. Check source
# and owner continuity again, without rereading the unchanged multi-GB inputs.
m=C.read(C.MANIFEST);correction=C.read(K.MANIFEST)
assert C.Q.frozen_section_sha()==C.Q.FROZEN_SHA
C.verify_hashes(m['source_sha256']);C.verify_hashes(correction['source_sha256'])
assert C.sha(C.MANIFEST)==correction['original_manifest_sha256']
assert C.sha(K.MANIFEST)==first['correction_sha256']
state=C.read(K.STATE);lock=C.read(K.LOCK);snap=C.process_snapshot()
assert state==first['state'] and state['owner']==lock and not C.LOCK.exists()
for pid,created in ((lock['pid'],lock['created_epoch']),(state['child_pid'],state['child_created_epoch'])):
    assert C.psutil.Process(pid).create_time()==created
assert not snap['inaccessible_pids']
def workers(snapshot):
    return {p['pid']:p for p in snapshot['processes'] if 'slice' in p['command'] and '--index' in p['command']}
a,b=workers(first['process_snapshot']),workers(snap)
indices={p['command'][p['command'].index('--index')+1] for p in b.values()}
progress=[pid for pid,p in b.items() if pid in a and p['created_epoch']==a[pid]['created_epoch'] and
          p['cpu_user_s']+p['cpu_kernel_s']>a[pid]['cpu_user_s']+a[pid]['cpu_kernel_s']]
assert indices==set(map(str,range(16))) and progress
tracked_proc=subprocess.run(['git','-C',str(R),'ls-files','-z','--','data/survey/p10/part2d/calibration/inj_funnel'],capture_output=True,text=True,check=True)
tracked=set(tracked_proc.stdout.strip('\0').split('\0'))
complete=[];files=[];new_ids=[];finish_times=[];timings=[];a_only=[]
for row in m['recovered_jobs']:
    job=C.injection_job(row)
    key=f"tic{job['tic_id']}_P{job['period']:.4f}"
    root=C.CAL/'inj_funnel'/row['job_id'];apath=root/'stageA'/(key+'.json');spath=root/'secondary'/(key+'.json')
    if not spath.exists():
        if apath.exists():
            K.check_record(apath,'A',job);a_only.append(row['job_id'])
        continue
    ar=K.check_record(apath,'A',job);sr=K.check_record(spath,'S',job,ar['decision'])
    complete.append(row['job_id']);finish_times.append(spath.stat().st_mtime)
    timings.append(float(ar['seconds'])+float(sr['seconds']))
    group=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.relative_to(R).as_posix() not in tracked:
            group.append(dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=C.sha(p)))
    if group:new_ids.append(row['job_id']);files.extend(group)
assert 0<len(complete)<1240
observed=datetime.now(timezone.utc);started=datetime.fromisoformat(state['utc'])
elapsed_h=(observed-started).total_seconds()/3600;rate=len(complete)/elapsed_h;remaining=1240-len(complete)
windows=[]
for minutes in (15,30,60,120):
    exposure=min(minutes/60,elapsed_h);n=sum(t>=observed.timestamp()-minutes*60 for t in finish_times)
    r=n/exposure
    windows.append(dict(minutes=minutes,completed=n,jobs_per_hour=r,extrapolated_remaining_h=remaining/r if r else None))
automation=tomllib.loads(Path(r'C:\Users\seanj\.codex\automations\continue-local-p10-execution\automation.toml').read_text())
assert automation['id']=='continue-local-p10-execution' and automation['status']=='ACTIVE'
assert automation['rrule']=='FREQ=MINUTELY;INTERVAL=120'
assert automation['target_thread_id']=='01a08dce-53a4-79a1-9b18-0929d292b272'
report=dict(utc=C.utc(),state='healthy_injection_calibration_running',phase='injection_as',
    completed_injections=len(complete),remaining_injections=remaining,A_only=len(a_only),newly_checkpointed=len(new_ids),
    completed_job_ids=complete,new_job_ids=new_ids,matching_workers_with_cpu_progress=len(progress),
    process_snapshot=snap,controller_state=state,controller_lock=lock,
    canonical_inspection=str(inspection_path.relative_to(R)),canonical_inspection_sha256=C.sha(inspection_path),
    input_hashes_verified_by_canonical_inspection=True,source_continuity_verified=True,
    manifest_sha256=C.sha(C.MANIFEST),correction_sha256=C.sha(K.MANIFEST),
    initial_census=first['census'],elapsed_phase_h=elapsed_h,completed_pairs_per_hour=rate,
    extrapolated_remaining_injection_h=remaining/rate,rolling_windows=windows,
    mean_completed_A_plus_S_seconds=sum(timings)/len(timings),
    all_five_bootstrap_levels_pending=True,
    timing_caveat='Throughput is descriptive over a changing search-SNR-ordered host mix. A short fast window alone does not establish a whole-calibration finish; all remaining injection A/S jobs and five 1000-bootstrap level fits count.',
    schedule_minutes=120,automation=automation)
C.save(W/'check.json',report,exclusive=True)
C.save(W/'new_settled_injection_artifacts.json',dict(utc=C.utc(),new_complete_job_ids=new_ids,files=files),exclusive=True)
shutil.copy2(inspection_path,W/inspection_path.name)
for p in (K.STATE,K.LOCK):shutil.copy2(p,W/p.name)
for p in [R/state['log'],O/'checked_driver_20260912.log',O/'checked_driver_20260912.stderr.log']:
    shutil.copy2(p,W/p.name)
shutil.copy2(Path(__file__),W/Path(__file__).name)
print(json.dumps({k:report[k] for k in ('utc','completed_injections','remaining_injections','A_only','newly_checkpointed',
    'matching_workers_with_cpu_progress','completed_pairs_per_hour','extrapolated_remaining_injection_h','rolling_windows')},indent=2))
