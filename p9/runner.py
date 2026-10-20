"""Ephemeris-blind P9 adapter around unchanged archived P8 functions.

Reads no truth manifests. Each scientific stage is a separate top-level process.
"""
from common import *
import argparse, csv, copy, time, subprocess, traceback

def restrict_inputs():
    """Audit-hook guard against historical packets/results and truth-side reads."""
    forbidden=[P9/'truth',REPO/'data',REPO/'docs',REPO/'followups']
    def audit(event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            try: p=Path(os.fsdecode(args[0])).resolve()
            except Exception:return
            if any(p==d or p.is_relative_to(d) for d in forbidden):
                raise PermissionError(f'P9 execution read/write boundary: {p}')
    sys.addaudithook(audit)

def setup(tic):
    frozen_imports()
    import numpy as np
    np.random.seed(SEED + tic%100000)
    import p8_funnel as F
    import audit_p5 as A
    import revet_p6 as V
    root=P9/'results/blind'/f'tic{tic}';root.mkdir(parents=True,exist_ok=True)
    F.REPO=A.REPO=V.REPO=P9
    F.LC_ROOT=P9/'inputs/raw';F.PACKETS=P9/'inputs/empty_packets'
    F.PACKETS.mkdir(exist_ok=True,parents=True)
    F.set_root(root);F.set_rules('p8.0');A.set_roots(root,F.LC_ROOT)
    A.AUDIT_CACHE=P9/'work/execution_lightkurve'
    A.AUDIT_CACHE.mkdir(parents=True,exist_ok=True)
    os.environ['LIGHTKURVE_CACHE']=str(A.AUDIT_CACHE)
    A.stellar_from_cache=lambda t:read(P9/'inputs/stellar'/f'tic{int(t)}.json')
    def neighbours(t,force=False):
        path=P9/'inputs/neighbours'/f'tic{t}.json'
        if not path.exists():raise RuntimeError('P9 permitted neighbour input not prepared')
        nb=copy.deepcopy(read(path))
        depths=[float(x['depth_ppt']) for x in csv.DictReader((root/'survivors.csv').open(encoding='utf-8'))]
        g=nb.get('gaia') or {}
        if g.get('error') or not g.get('target'):raise RuntimeError('P9 Gaia input unavailable: '+str(g.get('error')))
        for n in g.get('neighbours',[]):
            d=n.get('max_observed_depth_ppt_total_eclipse')
            n['can_produce_candidate_depths_total_eclipse']=[d>=v for v in depths] if d is not None else None
            n['can_produce_candidate_depths_50pct_eclipse']=[d/2>=v for v in depths] if d is not None else None
        g['n_neighbours_that_could_produce_depth_total_eclipse_within_63arcsec']=sum(1 for n in g.get('neighbours',[]) if (n.get('sep_arcsec') or 0)<=63 and any(n.get('can_produce_candidate_depths_total_eclipse') or []))
        nb['candidate_depths_ppt']=depths
        A.jdump(root/'neighbours'/f'tic{t}.json',nb)
        return nb
    A.neighbours_step=neighbours
    original=V.provisional_verdict
    def external_verdict(rec):
        review=copy.deepcopy(rec)
        ((review.get('crossmatch') or {}).get('star') or {}).pop('status',None)
        return original(review)
    V.provisional_verdict=external_verdict
    restrict_inputs()
    return root,F,A,V

def search(tic,kind):
    root,F,A,V=setup(tic)
    import logging
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(name)s %(levelname)s %(message)s',force=True)
    from tesshunter import bls_search,pipeline
    trace=root/'search_trials.jsonl'
    def record(event,data):
        with trace.open('a',encoding='utf-8') as f:
            f.write(json.dumps(pipeline._to_native(dict(event=event,**data)),default=str)+'\n')
    original_bls=bls_search.run_bls
    def recorded_bls(*args,**kwargs):
        result=original_bls(*args,**kwargs)
        record('broad_bls',dict(candidates=result[2].to_dict(orient='records'),settings=kwargs))
        return result
    original_alias=bls_search.resolve_aliases_for_candidate
    def recorded_alias(*args,**kwargs):
        result=original_alias(*args,**kwargs)
        record('alias_resolution',dict(raw_candidate=args[1].to_dict(),resolved=result[0].to_dict(),
          trials=result[1].to_dict(orient='records')))
        return result
    bls_search.run_bls=recorded_bls;bls_search.resolve_aliases_for_candidate=recorded_alias
    from tesshunter.survey import run_job
    rows=list(csv.DictReader((P9/f'manifests/{kind}_execution.csv').open(encoding='utf-8')))
    row=next(r for r in rows if int(r['tic_id'])==tic)
    star={k:float(v) for k,v in row.items() if k!='tic_id' and v not in ('','nan')}
    result=run_job(dict(job_id=f'tic{tic}',tic_id=tic,config='survey_p8',star=star,
      lc_root=str(P9/'inputs/raw'),offline=True),cache_dir=P9/'work/stitched',allow_download=False)
    A.jdump(root/'search/results'/f'tic{tic}.json',result)
    F.collect(root/'search',P9/f'manifests/{kind}_execution.csv')
    print('search',tic,result['status'],result.get('timings'),flush=True)
    if result['status']!='ok':raise SystemExit(1)

def stage(tic,which,key):
    root,F,A,V=setup(tic)
    if which=='S':jobs=[j for j in V.jobs() if F.decisions('A').get(V.kkey(tic,j['period']))=='PASS']
    else:jobs=F.eligible(which)
    job=next(j for j in jobs if V.kkey(tic,j['period'])==key)
    if which=='D':
        policy=read(P9/'inputs/catalogue_policy'/f'tic{tic}.json')
        xm=dict(catalog_stamp='P9 frozen catalogue outcome on preparation side',per_star={str(tic):dict(status='KNOWN_STATUS_REDACTED',**policy)})
        A.jdump(root/f'crossmatch_{root.name}.json',xm)
        r=V.staged_one(job,xm)
        r['external_validation']=policy;A.jdump(root/'stageD'/f'{key}.json',r)
        if r.get('verdict')!='ERROR' and not r.get('fit',{}).get('error'):
            import p8_stage_d_packets as D
            D.REPO=P9
            job.update(key=key,score_v2=None,rank_v2=None)
            extra=D.measure_one(root,job,n_draws=100000)
            r['expensive_status']=extra['status'];A.jdump(root/'stageD'/f'{key}.json',r)
    else:
        kw={'threads':8,'oversampling':3} if which=='C' else ({'threads':1} if which=='A' else {})
        r=F.STAGE_FN[which](job,**kw)
    print(which,key,r.get('decision',r.get('gate',r.get('provisional_verdict'))),r.get('reason'),flush=True)
    if r.get('decision')=='ERROR' or r.get('gate')=='ERROR' or r.get('verdict')=='ERROR':raise SystemExit(1)

def stop_tree(pr):
    import psutil
    try:
        parent=psutil.Process(pr.pid)
        for c in parent.children(recursive=True):
            try:c.kill()
            except psutil.NoSuchProcess:pass
        parent.kill()
    except psutil.NoSuchProcess:pass
    pr.wait(timeout=30)

def invoke(cmd,token,timeout):
    path=P9/'results/operations'/f'{token}.json'
    if path.exists() and read(path).get('status')=='complete':return read(path)
    attempts=read(path).get('attempts',[]) if path.exists() else []
    for attempt in range(len(attempts),2):
        log=P9/'logs'/f'{token}_attempt{attempt+1}.log';start=time.perf_counter()
        with log.open('w',encoding='utf-8') as f:
            pr=subprocess.Popen([sys.executable,str(Path(__file__)),*cmd],stdout=f,stderr=subprocess.STDOUT)
            rec=dict(started_utc=utc(),command=cmd,pid=pr.pid,log=str(log.relative_to(P9)),
              runner_sha256=sha(Path(__file__)),protocol_sha256=sha(P9/'protocol/PREREGISTRATION.md'))
            try:
                code=pr.wait(timeout=timeout);rec.update(status='complete' if code==0 else 'error',returncode=code)
            except subprocess.TimeoutExpired:
                stop_tree(pr);rec.update(status='timeout')
        rec['wall_seconds']=time.perf_counter()-start;attempts.append(rec)
        out=dict(token=token,status=rec['status'],attempts=attempts,utc=utc())
        write(path,out)
        if rec['status']=='complete':return out
    return out

def batch(kind,which,only_tic=None):
    from concurrent.futures import ThreadPoolExecutor,as_completed
    ids=[int(r['tic_id']) for r in csv.DictReader((P9/f'manifests/{kind}_execution.csv').open(encoding='utf-8'))]
    if only_tic is not None:ids=[t for t in ids if t==only_tic]
    tasks=[]
    if which=='search':
        tasks=[(['search','--tic',str(t),'--kind',kind],f'search_tic{t}',1800) for t in ids]
    else:
        # Coordinator reads only blind records; eligible ordering is identical to F.eligible.
        for tic in ids:
            root=P9/'results/blind'/f'tic{tic}'
            table=root/'survivors.csv'
            if not table.exists():continue
            for r in csv.DictReader(table.open(encoding='utf-8')):
                key=f'tic{tic}_P{float(r["period_days"]):.4f}'
                requirements={'A':[],'S':[('stageA','decision',{'PASS'})],
                  'B':[('stageA','decision',{'PASS'}),('secondary','gate',{'PASS','HOLD'})],
                  'C':[('stageB','decision',{'PASS'})],'D':[('stageC','decision',{'PASS'})]}[which]
                if not all((root/folder/f'{key}.json').exists() and read(root/folder/f'{key}.json').get(field) in allowed for folder,field,allowed in requirements):continue
                tasks.append((['stage','--tic',str(tic),'--stage',which,'--key',key],f'{which}_{key}',{'A':3600,'S':900,'B':900,'C':36000,'D':14400}[which]))
    print('queued',which,len(tasks),'jobs',flush=True)
    with ThreadPoolExecutor(max_workers=2 if which in ('C','D') else 4) as ex:
        for f in as_completed([ex.submit(invoke,*t) for t in tasks]):
            r=f.result();print(r['token'],r['status'],round(r['attempts'][-1]['wall_seconds'],1),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=['search','stage','batch']);p.add_argument('--tic',type=int);p.add_argument('--kind',default='pilot');p.add_argument('--stage',default='search');p.add_argument('--key');a=p.parse_args()
    if a.cmd=='search':search(a.tic,a.kind)
    elif a.cmd=='stage':stage(a.tic,a.stage,a.key)
    else:batch(a.kind,a.stage,a.tic)
