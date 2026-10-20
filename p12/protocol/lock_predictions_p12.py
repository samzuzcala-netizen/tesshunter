"""P10.3 prediction normalization and P12 terminal/source/input/I/O locking."""
from p12_common import REPO,ROOT,read,write,sha,utc
from register_p12 import verify
from blind_io_p12 import is_protected
from blind_search_worker_p12 import safe
from pathlib import Path
import argparse
import json
import math

def normalize(tic,result):
    partitions={r['label']:bool(r.get('budget_exhausted')) for r in result.get('searches',[])}
    rows=[]
    for candidate in (result.get('result') or {}).get('planets') or []:
        required=['planet_num','period_days','epoch_btjd','duration_days','depth_ppt']
        if any(k not in candidate or candidate[k] is None for k in required):raise RuntimeError('Accepted prediction lacks ephemeris fields')
        if not all(math.isfinite(float(candidate[k])) for k in required):raise RuntimeError('Accepted prediction is nonfinite')
        partition=candidate.get('search')
        rows.append(dict(tic_id=tic,candidate_id=f'tic{tic}_p{int(candidate["planet_num"]):02d}',planet_num=int(candidate['planet_num']),
            period_days=float(candidate['period_days']),epoch_btjd=float(candidate['epoch_btjd']),duration_days=float(candidate['duration_days']),
            depth_ppt=float(candidate['depth_ppt']),stitch_snr=candidate.get('stitch_snr'),partition=partition,
            partition_budget_exhausted=partitions.get(partition),all_partition_budget_flags=partitions,raw_candidate=candidate))
    if len({r['candidate_id'] for r in rows})!=len(rows):raise RuntimeError('Duplicate accepted candidate identity')
    return rows


def inspect(log):
    forbidden=[];malformed=0;events=0
    for line in log.read_text(encoding='utf-8').splitlines():
        try:row=json.loads(line)
        except json.JSONDecodeError:malformed+=1;continue
        if not isinstance(row,dict) or not isinstance(row.get('path'),str) or not isinstance(row.get('denied'),bool):
            malformed+=1;continue
        events+=1
        if row['denied'] or is_protected(row['path']):forbidden.append(row['path'])
    return dict(path=log.relative_to(REPO).as_posix(),sha256=sha(log),events=events,malformed_rows=malformed,forbidden=forbidden)


def _check(path,digest,label):
    if not digest or sha(path)!=digest:raise RuntimeError(label+' hash changed or missing')


def _closed_phase(folder):
    closure=read(folder/'closure.json');launch=read(folder/'launch.json')
    if closure['status']!='CLOSED' or not closure['all_owned_workers_closed'] or not closure['source_hashes_unchanged'] or closure['pending']:
        raise RuntimeError('Search phase did not close cleanly')
    _check(REPO/launch['jobs_path'],launch['jobs_sha256'],'Jobs manifest')
    if read(REPO/launch['jobs_path'])!=launch['frozen_jobs']:raise RuntimeError('Frozen job membership changed')
    if not launch['source_hashes']:raise RuntimeError('Missing frozen search sources')
    for name,digest in launch['source_hashes'].items():_check(REPO/name,digest,'Search source')
    return closure,launch


def lock(phase):
    verify()
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Search owner has not closed')
    destination=ROOT/f'manifests/{phase}_predictions_lock.json'
    if phase=='final_search':destination=ROOT/'manifests/final_predictions_lock.json'
    if destination.exists():
        seal=read(destination.with_name(destination.stem+'_seal.json'))
        _check(destination,seal['sha256'],'Locked predictions')
        return seal
    phase_root=ROOT/f'results/controllers/{phase}'
    closure,launch=_closed_phase(phase_root)
    jobs=launch['frozen_jobs']
    if len({j['job_id'] for j in jobs})!=len(jobs):raise RuntimeError('Duplicate search job')
    effective={j['job_id']:(j,phase_root) for j in jobs};retry_closures={};prior_audits=[]
    for original_job in jobs:
        original_log=ROOT/f'results/search_io/{Path(original_job["arguments"][1]).stem}.jsonl'
        if original_log.exists():
            original_audit=inspect(original_log);prior_audits.append(original_audit)
            if original_audit['forbidden']:raise RuntimeError('STOP-4: protected truth access in original blind attempt')
    retry_folders=[]
    for path in (ROOT/'results/controllers').glob('*/closure.json'):
        if path.parent!=phase_root and read(path).get('retry_of')==phase:retry_folders.append(path.parent)
    if len(retry_folders)>1:raise RuntimeError('More than one recorded retry pass')
    for folder in retry_folders:
        retry_closure,retry_launch=_closed_phase(folder)
        if retry_launch.get('retry_of')!=phase:raise RuntimeError('Retry parent mismatch')
        retry_closures[folder.name]=sha(folder/'closure.json')
        seen=set()
        for retry_job in retry_launch['frozen_jobs']:
            jid=retry_job['job_id']
            if jid in seen or jid not in effective or retry_job['attempt']!=2:raise RuntimeError('Retry membership/attempt mismatch')
            seen.add(jid);original_path=phase_root/f'attempts/{jid}.json';original=read(original_path)
            if original['status'] not in ('TIMEOUT','OPERATIONAL_UNKNOWN'):raise RuntimeError('Unpermitted retry status')
            _check(original_path,retry_job['original_receipt_sha256'],'Original retry receipt')
            effective[jid]=(retry_job,folder)
    rows=[];audits=list(prior_audits);unknown=[]
    for original_job in jobs:
        job,attempt_root=effective[original_job['job_id']]
        job_id=job['job_id'];attempt_path=attempt_root/f'attempts/{job_id}.json';attempt=read(attempt_path)
        if attempt['job_id']!=job_id or attempt['status'] not in ('COMPLETE','TIMEOUT','OPERATIONAL_UNKNOWN','INTERRUPTED_UNKNOWN'):
            raise RuntimeError('Missing terminal job accounting')
        row=dict(job_id=job_id,attempt_status=attempt['status'],attempt_sha256=sha(attempt_path),accepted=[],status='OPERATIONAL_UNKNOWN')
        log=ROOT/f'results/search_io/{Path(job["arguments"][1]).stem}.jsonl'
        audit=inspect(log) if log.exists() else None
        if audit:
            if not any(a['path']==audit['path'] for a in audits):audits.append(audit)
            if audit['forbidden']:raise RuntimeError('STOP-4: protected truth access in blind search')
        receipt_path=REPO/attempt['result_path'] if attempt.get('result_path') else None
        receipt=read(receipt_path) if receipt_path and receipt_path.exists() else None
        if receipt:
            _check(receipt_path,attempt.get('result_sha256'),'Worker receipt')
            if receipt['job_id']!=job_id or receipt['preset']!='survey_p10':raise RuntimeError('Worker identity/preset differs')
            runtime_path=REPO/receipt['runtime_manifest_path'];_check(runtime_path,receipt['runtime_manifest_sha256'],'Runtime manifest')
            if job['arguments'][1]!=receipt['runtime_manifest_path'] or job['arguments'][2]!=receipt['runtime_manifest_sha256']:
                raise RuntimeError('Runtime differs from frozen controller job')
            runtime=read(runtime_path)
            if runtime['job_id']!=job_id or runtime['run']!=receipt['run']:raise RuntimeError('Runtime identity differs')
            for name,digest in receipt['source_hashes'].items():_check(REPO/name,digest,'Search source')
            if runtime['source_hashes']!=receipt['source_hashes']:raise RuntimeError('Runtime sources differ')
            _check(REPO/receipt['prepared_path'],receipt['prepared_sha256'],'Prepared input')
            _check((REPO/receipt['prepared_path']).with_suffix('.json'),receipt['provenance_sha256'],'Input provenance')
            if runtime['prepared_sha256']!=receipt['prepared_sha256'] or runtime['provenance_sha256']!=receipt['provenance_sha256']:
                raise RuntimeError('Runtime input differs')
            _check(REPO/receipt['result_path'],receipt['result_sha256'],'Search result')
            if receipt.get('trace_sha256'):_check(REPO/receipt['trace_path'],receipt['trace_sha256'],'Search trace')
            if (REPO/receipt['file_access_log']).resolve()!=log.resolve():raise RuntimeError('I/O log identity differs')
            result=read(REPO/receipt['result_path'])
            row.update(tic_id=receipt['tic_id'],receipt_sha256=sha(receipt_path),result_path=receipt['result_path'],
                result_sha256=receipt['result_sha256'],prepared_sha256=receipt['prepared_sha256'])
            if attempt['status']=='COMPLETE' and receipt['status']=='COMPLETE' and result['status']=='ok' and audit and audit['events'] and not audit['malformed_rows']:
                row.update(status='COMPLETE',accepted=normalize(receipt['tic_id'],result))
        if row['status']!='COMPLETE':unknown.append(job_id)
        rows.append(row)
    payload=dict(utc=utc(),status='LOCKED',phase=phase,preset='survey_p10',jobs=rows,n_jobs=len(rows),
        n_accepted=sum(len(r['accepted']) for r in rows),operational_unknown_job_ids=unknown,io_audits=audits,
        launch_sha256=sha(phase_root/'launch.json'),closure_sha256=sha(phase_root/'closure.json'),retry_closure_sha256=retry_closures,
        meaning='Terminal accounting includes every unknown; aliases/truth are evaluated only after this immutable lock')
    write(destination,safe(payload))
    seal=dict(utc=utc(),path=destination.relative_to(REPO).as_posix(),sha256=sha(destination),jobs=len(rows),accepted=payload['n_accepted'],unknowns=len(unknown))
    write(destination.with_name(destination.stem+'_seal.json'),seal)
    return seal


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('phase');args=parser.parse_args(argv)
    result=lock(args.phase);print('predictions locked',result['jobs'],'unknowns',result['unknowns'],flush=True);return 0


if __name__=='__main__':main()
