"""P10.3 A/S/B adapter with frozen P12 policy products and isolated writes."""
from p12_common import REPO,ROOT,DATA,environment,read,write,sha,utc,redirect_audit_cache
environment()
import csv,sys,time
from pathlib import Path
from blind_io_p12 import install,summary
from blind_search_worker_p12 import safe
from rules_p12 import configure_early_funnel
import policy_products_p12

def legacy(root):
    sys.path[:0]=[str(REPO/'src'),str(REPO/'scripts'),str(REPO/'p10/protocol')]
    import p10_funnel_calibration as F
    import audit_p5 as A
    redirect_audit_cache(A)
    F.LC_ROOT=REPO/'data/survey/audit_lc';F.PACKETS=DATA/'funnel/empty_packets'
    F.set_root(root);configure_early_funnel(F)
    redirect_audit_cache(A)
    return F

def setup(runtime, root):
    tic=int(runtime['tic_id'])
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    columns=sorted(set(runtime['candidate'])|set(runtime['star'])|{'period_days','tic_id'})
    candidate=dict(runtime['candidate'],**runtime['star'],tic_id=tic)
    for name,rows in [('survivors.csv',[candidate]),('candidates.csv',runtime['all_candidates'])]:
        path=root/name
        if not path.exists():
            with path.open('x',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore')
                writer.writeheader();writer.writerows(rows)
    F=legacy(root)
    import audit_p5 as A
    from tesshunter import survey
    A.set_input_config(survey.get_config('survey_p10'));A.set_roots(root,REPO/'data/survey/audit_lc')
    restore=policy_products_p12.install(tic,runtime['arm'])
    star=runtime['star']
    stellar={'radius':star['radius_rsun'],'mass':star['mass_msun'],'teff':star['teff_k'],
        'tmag':star['tmag'],'ra':star['ra_deg'],'dec':star['dec_deg']}
    A.stellar_from_cache=lambda requested:stellar if int(requested)==tic else {}
    return F,restore

def main(stage,runtime_path,expected_runtime_sha256):
    if stage not in ('A','S','B'):raise ValueError('Unregistered early stage')
    runtime_path=Path(runtime_path)
    if not runtime_path.is_absolute():runtime_path=REPO/runtime_path
    guard=install(ROOT/f'results/funnel_io/{stage}_{runtime_path.stem}.jsonl')
    if sha(runtime_path)!=expected_runtime_sha256:raise RuntimeError('Frozen runtime changed')
    r=read(runtime_path);cid=r['candidate_id'];tic=int(r['tic_id'])
    allowed={'candidate_id','tic_id','candidate','all_candidates','star','source_hashes','neighbours_reference','phase','arm'}
    if set(r)!=allowed or cid!=runtime_path.stem:raise RuntimeError('Unregistered runtime fields/identity')
    if r['phase']!='pilot':raise RuntimeError('Later-part funnel binding requires its registration')
    for name,digest in r['source_hashes'].items():
        if sha(REPO/name)!=digest:raise RuntimeError('Frozen funnel input/source changed')
    destination=ROOT/f'results/funnel/{r["phase"]}/{stage}/{cid}.json'
    if destination.exists():raise FileExistsError(destination)
    root=DATA/f'funnel/{r["phase"]}/cases/{cid}'
    F,restore=setup(r,root)
    try:
        if stage=='B':
            nb=r['neighbours_reference']
            if not nb or sha(REPO/nb['path'])!=nb['sha256']:raise RuntimeError('Complete neighbour reference missing')
            write(root/f'neighbours/tic{tic}.json',read(REPO/nb['path']))
        job=F.V.jobs()[0];started=utc();timer=time.perf_counter();cpu=time.process_time()
        if stage=='A':measurement=F.V.stagea_one(job,threads=1)
        elif stage=='S':measurement=F.secondary_one(job)
        else:measurement=F.V.stageb_one(job)
        decision=measurement.get('decision',measurement.get('gate',measurement.get('status')))
        status='OPERATIONAL_UNKNOWN' if decision in ('ERROR','SKIP','INPUT_ERROR','TIMEOUT') else 'COMPLETE'
        io=summary(guard)
        receipt=dict(candidate_id=cid,tic_id=tic,stage=stage,status=status,started_utc=started,completed_utc=utc(),
            wall_seconds=time.perf_counter()-timer,cpu_seconds=time.process_time()-cpu,measurement=measurement,
            runtime_sha256=sha(runtime_path),rules_version='p10.0',io=io,phase=r['phase'],arm=r['arm'])
        write(destination,safe(receipt))
        write(ROOT/f'results/funnel_timing/{r["phase"]}/{stage}/{cid}.json',{k:v for k,v in receipt.items() if k not in ('measurement','io')})
        print(stage,status,round(receipt['wall_seconds'],2),flush=True)
        if status!='COMPLETE':raise SystemExit(2)
    finally:restore()

if __name__=='__main__':main(*sys.argv[1:])
