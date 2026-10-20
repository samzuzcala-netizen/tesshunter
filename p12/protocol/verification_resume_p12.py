"""Authorized verification recovery: retain completions, archive partials, resume once."""
from p12_common import REPO,ROOT,DATA,read,write,sha,utc,append_jsonl
from part0_plan_p12 import source_snapshot
from pathlib import Path
import argparse,copy,json


def archive_partial(source,destination,boundary):
    source=Path(source);destination=Path(destination);boundary=Path(boundary).resolve(strict=True)
    if not source.resolve().is_relative_to(boundary) or not destination.resolve().is_relative_to(boundary):
        raise RuntimeError('Partial archive escapes the intended P12 root')
    if not source.exists():return None
    if destination.exists():raise FileExistsError(destination)
    files=sorted(p for p in source.rglob('*') if p.is_file()) if source.is_dir() else [source]
    hashes={p.relative_to(source).as_posix() if source.is_dir() else '.':sha(p) for p in files}
    record=dict(source=str(source),destination=str(destination),files=len(files),hashes=hashes)
    destination.parent.mkdir(parents=True,exist_ok=True)
    source.rename(destination)
    for relative,digest in hashes.items():
        path=destination if relative=='.' else destination/relative
        if sha(path)!=digest:raise RuntimeError('Archived partial bytes changed')
    return record


def preserved_completions():
    recovery=read(ROOT/'manifests/recovery_verify_core_rechecked.json')
    folder=ROOT/'results/controllers/verify_core';result={}
    for jid in recovery['completed_predictions_retained']:
        path=folder/'attempts'/f'{jid}.json';attempt=read(path)
        if attempt['status']!='COMPLETE' or sha(REPO/attempt['result_path'])!=attempt['result_sha256']:
            raise RuntimeError('Completed verification receipt/result changed')
        result[jid]=dict(attempt_sha256=sha(path),result_path=attempt['result_path'],result_sha256=attempt['result_sha256'])
    return result


def prepare():
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner remains')
    if read(ROOT/'manifests/normal_exposure_resolution.json')['status']!='RESOLVED_BY_USER_RULING':
        raise RuntimeError('User ruling is missing')
    recovery=read(ROOT/'manifests/recovery_verify_core_rechecked.json')
    complete=preserved_completions();rows=copy.deepcopy(read(REPO/recovery['resume_manifest']))
    interrupted={r['job_id'] for r in recovery['rows'] if r.get('status')=='INTERRUPTED_UNKNOWN'}
    if len(complete)!=680 or len(rows)!=1756 or len(interrupted)!=4:
        raise RuntimeError('Authorized recovery counts differ')
    if set(complete)&{r['job_id'] for r in rows}:raise RuntimeError('Completed job present in resume manifest')
    write(ROOT/'manifests/verify_core_completed_retained.json',dict(utc=utc(),jobs=complete))
    archived=[]
    for jid in sorted(interrupted):
        if not jid.startswith('tic') or not jid[3:].isdigit():raise RuntimeError('Unexpected verification identity')
        tic=int(jid[3:])
        for source,destination,boundary in (
            (ROOT/f'manifests/input_identity/tic{tic}.json',ROOT/f'manifests/interrupted_verify_core/input_identity/tic{tic}.json',ROOT),
            (ROOT/f'results/native_noise/archival/tic{tic}.json',ROOT/f'manifests/interrupted_verify_core/native_noise/tic{tic}.json',ROOT),
            (DATA/f'prepared/archival/tic{tic}',DATA/f'interrupted_verify_core/prepared/tic{tic}',DATA)):
            record=archive_partial(source,destination,boundary)
            if record:
                record.update(job_id=jid,utc=utc());archived.append(record)
                append_jsonl(ROOT/'manifests/verify_core_partial_archive.jsonl',record)
    snapshot=source_snapshot()
    for row in rows:
        row['source_hashes'].update(snapshot)
        if row['job_id'] in interrupted:row['attempt']=2
    jobs_path=ROOT/'manifests/verify_core_resume_jobs.json';write(jobs_path,rows)
    sequence=read(ROOT/'manifests/phase_sequence.json');phases=sequence['phases']
    position=next(i for i,p in enumerate(phases) if p['name']=='verify_core')+1
    plan=dict(name='verify_core_resume',part=0,kind='controller',depends_on=['verify_core'],workers=8,deadline_s=600,
        jobs=jobs_path.relative_to(REPO).as_posix(),recovery_of='verify_core',authorized_interrupted=4,authorized_unstarted=1752)
    phases.insert(position,plan)
    phases.insert(position+1,dict(name='verify_core_reconcile_complete',part=0,kind='evaluator',depends_on=['verify_core_resume'],
        script='p12/protocol/verification_resume_p12.py',args=['close']))
    next(p for p in phases if p['name']=='eligibility_core')['depends_on']=['verify_core_reconcile_complete']
    write(ROOT/'manifests/phase_sequence.json',sequence,replace=True)
    write(ROOT/'manifests/verify_core_resume_plan.json',dict(utc=utc(),status='PREPARED',jobs=1756,
        completed_retained=680,interrupted=4,never_started=1752,partial_archives=len(archived),
        recovered_jobs_sha256=sha(REPO/recovery['resume_manifest']),resume_jobs_sha256=sha(jobs_path),
        worker_arguments_and_scientific_input_hashes_unchanged=True,controller_attempts_in_separate_phase=True))
    if preserved_completions()!=complete:raise RuntimeError('Preparation modified a completed job')
    print(json.dumps(dict(status='PASS',completed_retained=680,interrupted=4,never_started=1752,jobs=1756)))
    return plan


def close():
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Owner remains')
    retained=read(ROOT/'manifests/verify_core_completed_retained.json')['jobs']
    if preserved_completions()!=retained:raise RuntimeError('A retained completion changed')
    folder=ROOT/'results/controllers/verify_core_resume';closure=read(folder/'closure.json');launch=read(folder/'launch.json')
    if closure['status']!='CLOSED' or closure['unknowns'] or closure['pending'] or not closure['all_owned_workers_closed'] or not closure['source_hashes_unchanged']:
        raise RuntimeError('Verification resume did not close completely')
    completed=set(retained)
    for job in launch['frozen_jobs']:
        path=folder/'attempts'/f'{job["job_id"]}.json';attempt=read(path)
        if attempt['status']!='COMPLETE' or sha(REPO/attempt['result_path'])!=attempt['result_sha256']:
            raise RuntimeError('Resume result is incomplete or changed')
        if job['job_id'] in completed:raise RuntimeError('Duplicate completion across phases')
        completed.add(job['job_id'])
    original={j['job_id'] for j in read(ROOT/'results/controllers/verify_core/launch.json')['frozen_jobs']}
    if completed!=original or len(completed)!=2436:raise RuntimeError('Effective verification membership differs')
    result=dict(utc=utc(),status='COMPLETE',jobs=2436,original_completions_retained=680,resumed=1756,unknowns=0,
        original_closure_sha256=sha(ROOT/'results/controllers/verify_core/closure.json'),resume_closure_sha256=sha(folder/'closure.json'),
        completed_receipts_unchanged=True)
    write(ROOT/'manifests/verify_core_effective_closure.json',result)
    print(json.dumps({key:result[key] for key in ('status','jobs','original_completions_retained','resumed','unknowns')}))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','close'));args=parser.parse_args()
    prepare() if args.action=='prepare' else close()
