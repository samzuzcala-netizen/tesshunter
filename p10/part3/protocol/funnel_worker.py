"""Unchanged p10.0 A/S/B on all eligible blind candidates, with isolated roots."""
from common import REPO,ROOT,DATA,environment,read,write,sha,utc
environment()
import csv,sys,time
import numpy as np
from blind_io import install,summary
from science_json import safe


def legacy(root):
    sys.path[:0]=[str(REPO/'src'),str(REPO/'scripts'),str(REPO/'p10/protocol')]
    import p10_funnel_calibration as F
    F.LC_ROOT=REPO/'data/survey/audit_lc';F.PACKETS=DATA/'funnel/empty_packets'
    F.set_root(root);F.set_rules('p10.0')
    return F


def main(stage,runtime_path,expected_runtime_sha256):
    if stage not in ('A','S','B'):raise ValueError('Only registered early stages A/S/B are implemented')
    runtime_path=__import__('pathlib').Path(runtime_path)
    guard=install(ROOT/f'results/funnel_io/{stage}_{runtime_path.stem}.jsonl',REPO/'data/cache/catalogs/spoc_tce/spoc_tce.ephemerides.csv')
    if sha(runtime_path)!=expected_runtime_sha256:raise RuntimeError('Candidate runtime differs from the frozen controller job')
    r=read(runtime_path);cid=r['candidate_id'];tic=int(r['tic_id'])
    if cid!=runtime_path.stem:raise RuntimeError('Candidate identity differs from its runtime filename')
    allowed={'candidate_id','tic_id','candidate','all_candidates','star','raw_products','source_hashes','neighbours_reference'}
    if set(r)!=allowed:raise RuntimeError('Unexpected candidate runtime field')
    for name,digest in r['source_hashes'].items():
        if sha(REPO/name)!=digest:raise RuntimeError('Funnel source changed: '+name)
    root=DATA/f'funnel/cases/{cid}';root.mkdir(parents=True,exist_ok=True)
    columns=sorted(set(r['candidate'])|set(r['star'])|{'period_days','tic_id'})
    candidate=dict(r['candidate'],**r['star'],tic_id=tic)
    for name,rows in [('survivors.csv',[candidate]),('candidates.csv',r['all_candidates'])]:
        path=root/name
        if not path.exists():
            with path.open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
    F=legacy(root);import audit_p5 as A
    cfg=__import__('tesshunter.survey',fromlist=['get_config']).get_config('survey_p10')
    A.set_input_config(cfg);A.set_roots(root,REPO/'data/survey/audit_lc')
    def products(requested):
        if int(requested)!=tic:raise RuntimeError('Unexpected host in raw input request')
        out=[]
        for product in r['raw_products']:
            path=REPO/product['raw_path']
            if sha(path)!=product['raw_sha256']:raise RuntimeError('Verified raw array changed')
            with np.load(path,allow_pickle=False) as z:p={k:np.asarray(z[k]) for k in z.files}
            p.update(product['metadata']);out.append(p)
        return out
    A.load_products=products
    star=r['star']
    stellar={'radius':star['radius_rsun'],'mass':star['mass_msun'],'teff':star['teff_k'],
             'tmag':star['tmag'],'ra':star['ra_deg'],'dec':star['dec_deg']}
    A.stellar_from_cache=lambda requested:stellar if int(requested)==tic else {}
    if stage=='B':
        nb=r['neighbours_reference']
        if not nb or sha(REPO/nb['path'])!=nb['sha256']:raise RuntimeError('Missing/changed complete Part D neighbour input')
        path=root/f'neighbours/tic{tic}.json'
        if not path.exists():write(path,read(REPO/nb['path']))
    # jobs() performs the legacy table conversions, with no alternative candidate selection.
    job=F.V.jobs()[0]
    started=utc();timer=time.perf_counter();cpu=time.process_time()
    if stage=='A':m=F.V.stagea_one(job,threads=1)
    elif stage=='S':m=F.secondary_one(job)
    else:m=F.V.stageb_one(job)
    decision=m.get('decision',m.get('gate',m.get('status')))
    status='OPERATIONAL_UNKNOWN' if decision in ('ERROR','SKIP','INPUT_ERROR','TIMEOUT') else 'COMPLETE'
    io=summary(guard)
    if io['sidecar_open_attempts']:raise RuntimeError('STOP-4: sidecar access in early funnel')
    receipt=dict(candidate_id=cid,tic_id=tic,stage=stage,status=status,started_utc=started,completed_utc=utc(),
                 wall_seconds=time.perf_counter()-timer,cpu_seconds=time.process_time()-cpu,measurement=m,
                 runtime_sha256=sha(__import__('pathlib').Path(runtime_path)),rules_version='p10.0',io=io)
    write(ROOT/f'results/funnel/{stage}/{cid}.json',safe(receipt))
    write(ROOT/f'results/funnel_timing/{stage}/{cid}.json',{k:v for k,v in receipt.items() if k not in ('measurement','io')})
    print(stage,cid,status,round(receipt['wall_seconds'],2),flush=True)
    if status!='COMPLETE':raise SystemExit(2)


if __name__=='__main__':main(sys.argv[1],sys.argv[2],sys.argv[3])
