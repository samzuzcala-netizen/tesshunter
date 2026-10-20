"""P10.3 v2 deterministic download batching, with P12 identities and receipts."""
from p12_common import REPO,ROOT,read,write,sha,utc
import argparse
import csv
import re

BATCH=100
MAX_ATTEMPTS=2
WORKER='p12/protocol/download_star_p12.py'
TRANSPORT=re.compile(r'HTTPError|ConnectionError|Timeout|RemoteDisconnected|IncompleteRead|ChunkedEncoding|ProtocolError|URLError|socket|Max retries|Bad Gateway|Service Unavailable|Gateway Time-out|Connection aborted|Connection reset|Name or service not known|getaddrinfo',re.I)


def transport_class(status,error):
    if status=='TIMEOUT':return True
    if error is None or error=='':return True
    return bool(TRANSPORT.search(str(error)))


def job(tic,attempt,force=False):
    if attempt not in (1,2):raise ValueError('Acquisition permits exactly two attempts')
    names=[WORKER,'p12/protocol/p12_common.py','p12/protocol/input_identity_p12.py','scripts/audit_p5.py','src/tesshunter/audit_prep.py']
    arguments=[WORKER,str(int(tic)),str(attempt),'--online']+(['--force'] if force else [])
    result=f'p12/results/download/tic{int(tic)}_a{attempt}.json'
    return dict(job_id=f'tic{int(tic)}',arguments=arguments,attempt=attempt,force=force,result_path=result,
        source_hashes={name:sha(REPO/name) for name in names},
        retry_arguments=[WORKER,str(int(tic)),'2','--online','--force'],
        retry_result_path=f'p12/results/download/tic{int(tic)}_a2.json')


def refuse_if_owner():
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Build manifests only between phases')


def plan(targets,phase='download'):
    refuse_if_owner()
    with open(targets,newline='',encoding='utf-8-sig') as stream:tics=sorted({int(r['tic_id']) for r in csv.DictReader(stream)})
    jobs=[]
    for tic in tics:
        path=REPO/f'data/survey/audit_lc/tic{tic}/index.json'
        if not path.exists() or read(path).get('n_failed',0):jobs.append(job(tic,1,path.exists()))
    manifests=[]
    for index in range(0,len(jobs),BATCH):
        path=ROOT/f'manifests/download_{phase}_{index//BATCH+1:02d}_jobs.json'
        write(path,jobs[index:index+BATCH]);manifests.append(path.relative_to(REPO).as_posix())
    result=dict(utc=utc(),targets=len(tics),jobs=len(jobs),batch_size=BATCH,batches=manifests,order='ascending TIC identity')
    write(ROOT/f'manifests/download_{phase}_plan.json',result)
    return result


def retry(phase):
    refuse_if_owner()
    closure=read(ROOT/f'results/controllers/{phase}/closure.json')
    if closure['status']!='CLOSED' or not closure['all_owned_workers_closed'] or closure['pending']:
        raise RuntimeError('Retry requires a closed phase')
    jobs=[];skipped=[]
    for path in sorted((ROOT/f'results/controllers/{phase}/attempts').glob('*.json')):
        record=read(path);tic=int(record['job_id'][3:]);attempt=int(record['attempt'])
        receipt=REPO/record['result_path'] if record.get('result_path') else None
        result=read(receipt) if receipt and receipt.exists() else {};error=result.get('error')
        if record['status']=='COMPLETE' and result.get('ok') and not result.get('n_failed'):continue
        if attempt>=MAX_ATTEMPTS:skipped.append(dict(tic_id=tic,reason='attempts_exhausted'));continue
        if result.get('n_failed'):reason,force='product_level_failures',True
        elif record['status'] not in ('TIMEOUT','OPERATIONAL_UNKNOWN'):
            skipped.append(dict(tic_id=tic,reason='status_not_retryable'));continue
        elif transport_class(record['status'],error):reason,force='transport_or_deadline',True
        else:skipped.append(dict(tic_id=tic,reason='non_transport_error'));continue
        jobs.append(dict(job(tic,2,force),reason=reason))
    path=ROOT/f'manifests/download_{phase}_retry_jobs.json';write(path,jobs)
    result=dict(utc=utc(),retry_jobs=len(jobs),skipped=skipped,manifest=path.relative_to(REPO).as_posix(),max_attempts=MAX_ATTEMPTS)
    write(ROOT/f'manifests/download_{phase}_retry_plan.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('plan','retry'));parser.add_argument('--phase',default='download')
    parser.add_argument('--targets',default=str(ROOT/'manifests/targets_p12_core.csv'));args=parser.parse_args(argv)
    result=plan(args.targets,args.phase) if args.action=='plan' else retry(args.phase)
    print('acquisition plan',result,flush=True);return 0


if __name__=='__main__':main()
