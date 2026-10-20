"""Validate and seal the one-attempt forced-fit phase; never fit a signal."""
from common import REPO, ROOT, read, write, sha, utc, environment
environment()
import json
import time
import hashlib
import tomllib
from pathlib import Path
from collections import Counter
from registration_execution_v3 import verify
from lock_predictions import both_locked
from part_f_guards_v1 import require_hash, assert_no_integrity_failure, IntegrityFailure
from full_funnel_plan import charge


def validate_family(job, attempt, runtime, result):
    fid=job['job_id']
    if attempt['job_id']!=fid or runtime['family_id']!=fid or attempt['attempt']!=1:
        raise IntegrityFailure('Forced attempt or runtime family identity mismatch')
    if result is not None:
        if (result['family_id']!=fid or result['tic_id']!=runtime['tic_id'] or
            result['runtime_sha256']!=job['arguments'][2] or result['scientific_attempt']!=1 or
            result['representative_row_id']!=runtime['representative_row_id'] or
            result['method_registration_sha256']!=runtime['method_registration_sha256']):
            raise IntegrityFailure('Forced result identity or method mismatch')
    if attempt['status']=='COMPLETE':
        if not result or result['status']!='COMPLETE' or result['presence'] not in ('PRESENT','ABSENT'):
            raise IntegrityFailure('Completed forced attempt lacks a complete scientific receipt')
        presence=result['presence']
    else:
        presence='OPERATIONAL_UNKNOWN'
    return dict(family_id=fid,tic_id=runtime['tic_id'],representative_row_id=runtime['representative_row_id'],
        status='COMPLETE' if presence!='OPERATIONAL_UNKNOWN' else 'OPERATIONAL_UNKNOWN',presence=presence,
        attempt_status=attempt['status'],fit=result)


def main():
    assert_no_integrity_failure();verify(require_launch_seal=True);both_locked()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Controller still owns the queue')
    if (ROOT/'results/forced_fits.json').exists():raise RuntimeError('Forced aggregation already exists; no overwrite')
    phase=ROOT/'results/controllers/forced_fits'
    closure=read(phase/'closure.json');launch=read(phase/'launch.json')
    if not (closure['status']=='CLOSED' and closure['all_owned_workers_closed'] and
        closure['pending']==0 and closure['source_hashes_unchanged']):
        raise IntegrityFailure('Forced phase did not close cleanly')
    for path,digest in launch['source_hashes'].items():require_hash(REPO/path,digest,'Forced launch source')
    preflight=read(ROOT/'manifests/forced_fits_preflight.json')
    require_hash(ROOT/'manifests/forced_fits_jobs.json',preflight['jobs_sha256'],'Forced jobs')
    require_hash(ROOT/'results/matching.json',preflight['matching_sha256'],'Locked matching')
    method_path=ROOT/'manifests/part_f_method_registration_v1.json'
    require_hash(method_path,preflight['method_registration_sha256'],'Forced method')
    method=read(method_path)
    for path,digest in method['source_hashes'].items():require_hash(REPO/path,digest,'Registered Part F source')
    entry_path=ROOT/'manifests/part_f_entry_v1.json'
    jobs=read(ROOT/'manifests/forced_fits_jobs.json')
    matching=read(ROOT/'results/matching.json')
    expected={f['family_id'] for f in matching['ephemeris_families']}
    if expected!={j['job_id'] for j in jobs} or len(jobs)!=closure['completed']:
        raise IntegrityFailure('Forced family coverage mismatch')
    if expected!={p.stem for p in (phase/'attempts').glob('*.json')}:
        raise IntegrityFailure('Forced attempt coverage mismatch')
    started,timer=utc(),time.perf_counter()
    try:
        records={}
        for job in jobs:
            fid=job['job_id'];runtime_path=REPO/job['arguments'][1]
            require_hash(runtime_path,job['arguments'][2],'Forced runtime')
            runtime=read(runtime_path)
            require_hash(entry_path,runtime['part_f_entry_sha256'],'Part F entry')
            if runtime['source_hashes']!=method['source_hashes']:
                raise IntegrityFailure('Worker source set differs from registered method')
            attempt=read(phase/f'attempts/{fid}.json')
            if attempt.get('result_path')!=job['result_path']:
                raise IntegrityFailure('Forced result path mismatch')
            result_path=REPO/job['result_path'];result=read(result_path) if result_path.exists() else None
            records[fid]=validate_family(job,attempt,runtime,result)
            records[fid]['result_path']=job['result_path']
            records[fid]['result_sha256']=sha(result_path) if result_path.exists() else None
        counts=Counter(r['presence'] for r in records.values())
        if counts.get('OPERATIONAL_UNKNOWN',0)!=closure['unknowns']:
            raise IntegrityFailure('Forced unknown census differs from controller')
        aggregate=dict(utc=utc(),status='COMPLETE_WITH_UNKNOWNS' if closure['unknowns'] else 'COMPLETE',
            evaluated_hosts=matching['evaluated_hosts'],n_families=len(records),raw_rows=matching['raw_rows'],
            presence_counts=dict(counts),families=records,matching_sha256=sha(ROOT/'results/matching.json'),
            method_registration_sha256=sha(method_path),controller_closure_sha256=sha(phase/'closure.json'),
            unknown_reasons=dict(Counter((r['fit'] or {}).get('error',r['attempt_status'])
                for r in records.values() if r['presence']=='OPERATIONAL_UNKNOWN')),
            assumptions=method['assumptions'])
        write(ROOT/'results/forced_fits.json',aggregate)
        paths=set(phase.rglob('*'))|set((ROOT/'results/forced_fits').glob('*.json'))|set((ROOT/'manifests/forced_fit_runtime').glob('*.json'))
        paths|={ROOT/'results/forced_fits.json',ROOT/'results/matching.json',method_path,entry_path,
            ROOT/'manifests/exposure_ledger.json',ROOT/'manifests/exposure_ledger_before_part_f.json',
            ROOT/'manifests/forced_fits_jobs.json',ROOT/'manifests/forced_fits_preflight.json',
            ROOT/'logs/controller_forced_fits.log',ROOT/'logs/controller_forced_fits.stderr.log'}
        files={p.relative_to(REPO).as_posix():sha(p) for p in sorted(paths) if p.is_file()}
        write(ROOT/'manifests/forced_fits_closed_evidence_seal.json',dict(utc=utc(),files=files,
            n_files=len(files),scientific_attempts=1,source_hashes_verified=True,closure=closure))
    finally:charge(started,timer,'F_forced_aggregation_and_seal')
    auto=Path(r'C:\Users\seanj\.codex\automations\prompt-10-3-hourly-check-in\automation.toml')
    cfg=tomllib.loads(auto.read_text(encoding='utf-8-sig'))
    rows=[json.loads(line) for line in (ROOT/'logs/checkins.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    schedule=read(ROOT/'manifests/checkin_schedule.json');last=rows[-1]
    if schedule.get('current_launch_last_firing')!=last['checkin_utc']:
        schedule['current_launch_count']=schedule.get('current_launch_count',0)+1
    schedule.update(utc=utc(),verified_status=cfg['status'],current_interval_minutes=60,
        schedule_sha256=sha(auto),prompt_sha256=hashlib.sha256(cfg['prompt'].encode()).hexdigest(),
        first_firing=rows[0]['checkin_utc'],last_firing=last['checkin_utc'],count=len(rows),
        current_launch_first_firing=schedule.get('current_launch_first_firing') or last['checkin_utc'],
        current_launch_last_firing=last['checkin_utc'],early_check_pending=False,early_check_completed=True,
        current_operation='Active Part F aggregation and prospective Stage C implementation; no controller alive')
    write(ROOT/'manifests/checkin_schedule.json',schedule,replace=True)
    ledger=read(ROOT/'manifests/resource_ledger.json')
    ledger.update(utc=utc(),phase_state='FORCED_FITS_CLOSED_C_IMPLEMENTATION_ACTIVE',checkin_count=len(rows),
        supervisor_status='ACTIVE_REGISTERED_HANDOVER',checkin_schedule_state={k:schedule.get(k) for k in
        ('verified_status','phase','current_interval_minutes','first_firing','last_firing','count')})
    write(ROOT/'manifests/resource_ledger.json',ledger,replace=True)
    with (ROOT/'RESUME_P10_3.md').open('a',encoding='utf-8') as f:
        f.write(f"\n{utc()} [M]: Forced fits CLOSED: {len(records)} families, presence counts {dict(counts)}, {closure['queue_hours']:.9f} queue-hours, all attempts accounted, sources unchanged. All {len(files)} closed artifacts sealed. Same heartbeat restored to ACTIVE/60; check-in count {len(rows)}. Ledger {ledger['new_queue_hours']:.9f}/31.98 h. No fit retry. Active task continues C selection and implementation; B-closure cap stays 13.\n")
    print(json.dumps(dict(status='FORCED_FITS_VALIDATED_AND_SEALED',n_families=len(records),presence_counts=dict(counts),
        unknown_reasons=aggregate['unknown_reasons'],sealed_files=len(files),remaining_hours=31.98-ledger['new_queue_hours'])))


if __name__=='__main__':main()
