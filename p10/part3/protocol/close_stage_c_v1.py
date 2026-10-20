"""Validate and seal all six executed Stage C cases without re-execution."""
from common import REPO,ROOT,read,write,sha,utc,environment
environment()
import json,time,psutil
from collections import Counter
from registration_execution_v3 import verify
from part_f_guards_v1 import require_hash,assert_no_integrity_failure,IntegrityFailure
from full_funnel_plan import stage_decision,charge

def assert_dead(identity):
    try:
        p=psutil.Process(identity['pid'])
        if abs(p.create_time()-identity['create_time'])<.01:
            raise IntegrityFailure('A supposedly closed C process is still alive')
    except psutil.NoSuchProcess:pass

def main():
    assert_no_integrity_failure();verify(require_launch_seal=True)
    assert not (ROOT/'manifests/controller_owner.json').exists()
    assert not (ROOT/'manifests/stage_C_closed_evidence_seal.json').exists()
    base=ROOT/'results/controllers/funnel_C';closure=read(base/'closure.json');launch=read(base/'launch.json')
    assert closure['status']=='CLOSED' and closure['pending']==0 and closure['all_owned_workers_closed'] and closure['source_hashes_unchanged']
    assert_dead(closure['owner'])
    for path,digest in launch['source_hashes'].items():require_hash(REPO/path,digest,'C launch source')
    for name in ('early_funnel_closed_evidence_seal.json','forced_fits_closed_evidence_seal.json'):
        for path,digest in read(ROOT/'manifests'/name)['files'].items():require_hash(REPO/path,digest,'Prior sealed evidence')
    plan=read(ROOT/'manifests/funnel_C_preflight.json');jobs=read(ROOT/'manifests/funnel_C_jobs.json')
    require_hash(ROOT/'manifests/funnel_C_jobs.json',plan['jobs_sha256'],'C jobs')
    require_hash(ROOT/'manifests/stage_C_selection_v1.json',plan['selection_sha256'],'C selection')
    require_hash(ROOT/'manifests/stage_C_method_registration_v1.json',plan['method_registration_sha256'],'C method')
    expected={j['job_id'] for j in jobs}
    assert expected=={p.stem for p in (base/'attempts').glob('*.json')} and len(jobs)==closure['completed']
    started,timer=utc(),time.perf_counter()
    try:
        records={};files=set(base.rglob('*'))
        for job in jobs:
            cid=job['job_id'];attempt=read(base/f'attempts/{cid}.json');assert_dead(attempt)
            require_hash(REPO/job['arguments'][1],job['arguments'][2],'C runtime')
            runtime=read(REPO/job['arguments'][1]);result=read(REPO/job['result_path'])
            assert attempt['attempt']==1 and attempt['job_id']==cid and runtime['candidate_id']==cid
            assert result['candidate_id']==cid and result['tic_id']==runtime['tic_id'] and result['stage']=='C'
            assert result['runtime_sha256']==job['arguments'][2] and result['scientific_attempt']==1
            assert result['method_registration_sha256']==runtime['method_registration_sha256']
            for path,digest in runtime['source_hashes'].items():require_hash(REPO/path,digest,'C method source')
            for path,digest in runtime['upstream_hashes'].items():require_hash(REPO/path,digest,'C upstream evidence')
            if result.get('io',{}).get('sidecar_open_attempts'):raise IntegrityFailure('C sidecar access')
            io=ROOT/f'results/funnel_io/C_{cid}.jsonl'
            assert io.is_file()
            for line in io.read_text(encoding='utf-8-sig').splitlines():
                event=json.loads(line)
                if event.get('denied') or event['path'].replace('\\','/').lower().endswith('/spoc_tce.ephemerides.csv'):
                    raise IntegrityFailure('C open log records sidecar access')
            decision=stage_decision(result) if attempt['status']=='COMPLETE' else 'OPERATIONAL_UNKNOWN'
            if attempt['status']=='COMPLETE':assert decision in ('PASS','FAIL')
            case=REPO/runtime['output_root']
            assert not list(case.rglob('ctoi_fields.json')) and not (case/'stageD').exists()
            records[cid]=dict(candidate_id=cid,tic_id=runtime['tic_id'],decision=decision,
                receipt_path=job['result_path'],receipt_sha256=sha(REPO/job['result_path']),
                measurement=result.get('measurement'),attempt_status=attempt['status'],case_root=runtime['output_root'])
            files.update(case.rglob('*'));files.update([io,REPO/job['result_path'],REPO/job['arguments'][1],ROOT/f'results/funnel_timing/C/{cid}.json'])
        summary=dict(utc=utc(),status='CLOSED_VALIDATED',n_jobs=len(jobs),counts=dict(Counter(r['decision'] for r in records.values())),
            candidates=records,closure=closure,selection_sha256=plan['selection_sha256'],source_hashes_verified=True,
            C_cap=plan['C_cap'],no_cap_exclusions=True,unverdicted=True)
        write(ROOT/'results/stage_C_summary.json',summary)
        files.update([ROOT/'results/stage_C_summary.json',ROOT/'manifests/funnel_C_jobs.json',ROOT/'manifests/funnel_C_preflight.json',
            ROOT/'manifests/stage_C_selection_v1.json',ROOT/'manifests/stage_C_method_registration_v1.json',
            ROOT/'logs/controller_funnel_C.log',ROOT/'logs/controller_funnel_C.stderr.log'])
        hashes={p.relative_to(REPO).as_posix():sha(p) for p in sorted(files) if p.is_file()}
        write(ROOT/'manifests/stage_C_closed_evidence_seal.json',dict(utc=utc(),files=hashes,n_files=len(hashes),
            n_bytes=sum((REPO/p).stat().st_size for p in hashes),summary_sha256=sha(ROOT/'results/stage_C_summary.json')))
    finally:charge(started,timer,'G_C_validation_and_seal')
    ledger=read(ROOT/'manifests/resource_ledger.json');schedule=read(ROOT/'manifests/checkin_schedule.json')
    ledger.update(utc=utc(),phase_state='C_CLOSED_FINAL_ANALYSIS_ACTIVE',checkin_count=schedule['count'],
        checkin_schedule_state={k:schedule.get(k) for k in ('verified_status','phase','current_interval_minutes','first_firing','last_firing','count')})
    write(ROOT/'manifests/resource_ledger.json',ledger,replace=True)
    with (ROOT/'RESUME_P10_3.md').open('a',encoding='utf-8') as f:
        f.write(f"\n{utc()} [M]: C closed and validated, counts {summary['counts']}; six one-attempt jobs, {closure['queue_hours']:.9f} union hours, no unknowns or sidecar access. {len(hashes)} C artifacts sealed. Active final analysis continues; no controller alive. Ledger {ledger['new_queue_hours']:.9f}/31.98 h.\n")
    print(json.dumps(dict(status=summary['status'],counts=summary['counts'],sealed_files=len(hashes),remaining_hours=31.98-ledger['new_queue_hours'])))

if __name__=='__main__':main()
