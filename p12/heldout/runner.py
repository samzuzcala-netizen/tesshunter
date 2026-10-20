"""Ephemeris-blind P9 adapter around unchanged archived P8 functions.

Reads no truth manifests. Each scientific stage is a separate top-level process.

P12 held-out copy of ``p9/runner.py`` (4c). Edits (the numbering of 4c; each tested):
(1) the frozen snapshot ``BASE`` and its seal (``common.verify_seal`` at every entry point);
(2) preset and rules from the freeze: ``survey_p10`` and ``p12.0`` (``p10_funnel_calibration`` configured by
    ``rules_p12.configure_early_funnel``: A, S, B and C under p10.0 stage rules; D under the p12.0 tiers
    through ``stage_d_worker_p12`` with ``--product-source heldout``) in place of ``F.set_rules('p8.0')``
    and ``config='survey_p8'``;
(3) ``--route negatives|normal`` replacing the requirements table: negatives are forced (C on every A
    passer whatever S and B decided, D on every C PASS or UNRESOLVED case) and redacted; positives run the
    normal route (S on A passers, B on S PASS or HOLD, C on B PASS, D on C PASS or UNRESOLVED);
(4) the P12 deadlines (``DEADLINES``), with the one C retry at 36,000 s;
(5) outputs under ``p12/heldout/{results,logs,work}``, prepared arrays and the Lightkurve / TESScut cache
    under ``data/survey/p12/heldout/`` (the read boundary follows);
(6) inputs read-only from ``p9/inputs/raw`` with the harness's own selection (``common.select_products``),
    recorded per host; the search runs the frozen P12 search worker on the harness-prepared arrays so the
    prediction lock (``lock_predictions_p12``) is the one every P12 search uses;
(7) scoring through the adapter copy (``scoring.py``, ``p9_scoring_adapter.py``);
(8) ``batch`` replaced by ``plan --stage <X> --route <R>``, which writes ``p12/manifests/neg_p9_<X>_jobs.json``
    with one ``runner.py stage --tic --stage --key --route`` job per case, so the P12 controller owns every job.
``p9/`` is never written.
"""
from common import *
import argparse, csv, copy, time, traceback

DATA = REPO / 'data/survey/p12/heldout'
MANIFESTS = REPO / 'p12/manifests'
DEADLINES = {'search': 3600, 'A': 1200, 'S': 300, 'B': 300, 'C': 12240, 'C_retry': 36000, 'D': 5400, 'eph': 5400}
WORKERS = {'search': 4, 'A': 4, 'S': 4, 'B': 4, 'C': 2, 'D': 2, 'eph': 2}
REQUIREMENTS = {
    'normal': {'A': [], 'S': [('stageA', 'decision', {'PASS'})],
               'B': [('stageA', 'decision', {'PASS'}), ('secondary', 'gate', {'PASS', 'HOLD'})],
               'C': [('stageB', 'decision', {'PASS'})], 'D': [('stageC', 'decision', {'PASS', 'UNRESOLVED'})]},
    'negatives': {'A': [], 'S': [('stageA', 'decision', {'PASS'})], 'B': [('stageA', 'decision', {'PASS'})],
                  'C': [('stageA', 'decision', {'PASS'})], 'D': [('stageC', 'decision', {'PASS', 'UNRESOLVED'})]},
}

def hosts():
    return read(MANIFESTS/'heldout_hosts.json')

def route_of(tic):
    return hosts()['route'][str(int(tic))]

def _roots(*paths):
    out=[]
    for q in paths:
        out+=[Path(os.path.abspath(q)),Path(q).resolve()]
    return out

def blocked(p):
    """The P9 read/write boundary (edit 5): truth, historical data, docs and follow-ups, except the P12
    held-out data root and the neg_p9 packet subtree. Both the written and the resolved path are checked, since
    data/survey/p12 and the relocated audit stores are junctions to D: (0b)."""
    here=_roots(p)
    inside=lambda roots:any(q==d or q.is_relative_to(d) for q in here for d in roots)
    if inside(_roots(P9/'truth')):return True
    if inside(_roots(DATA,REPO/'docs/packets/audit_p12/neg_p9')):return False
    return inside(_roots(REPO/'data',REPO/'docs',REPO/'followups',REPO/'data/survey/audit_lc',REPO/'data/cache/audit_lightkurve'))

def restrict_inputs():
    """Audit-hook guard against historical packets/results and truth-side reads (edit 5: P12 outputs allowed)."""
    DATA.mkdir(parents=True,exist_ok=True)
    def audit(event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            try: p=Path(os.fsdecode(args[0]))
            except Exception:return
            if blocked(p):
                raise PermissionError(f'P9 execution read/write boundary: {p}')
    sys.addaudithook(audit)

def execution_rows():
    return {int(r['tic_id']):r for r in csv.DictReader((H/'manifests/heldout_execution.csv').open(encoding='utf-8'))}

def setup(tic, root=None):
    verify_seal()
    frozen_imports()
    import numpy as np
    np.random.seed(SEED + tic%100000)
    import audit_p5 as A
    import revet_p6 as V
    import p10_funnel_calibration as F
    base_first()
    from rules_p12 import configure_early_funnel
    root=root or H/'results/blind'/f'tic{tic}';root.mkdir(parents=True,exist_ok=True)
    F.REPO=A.REPO=V.REPO=H
    F.LC_ROOT=P9/'inputs/raw';F.PACKETS=H/'work/empty_packets'
    F.PACKETS.mkdir(exist_ok=True,parents=True)
    F.set_root(root);configure_early_funnel(F,'p12.0');A.set_roots(root,F.LC_ROOT)
    A.AUDIT_CACHE=CACHE
    A.AUDIT_CACHE.mkdir(parents=True,exist_ok=True)
    os.environ['LIGHTKURVE_CACHE']=str(A.AUDIT_CACHE)
    install_products(tic)
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

def prepare(tic):
    """Evaluator side, before the search (edit 6): the recorded selection and the prepared native arrays."""
    frozen_imports()
    import numpy as np
    from tesshunter import survey, survey_p8
    install_products(tic)
    cfg=survey.get_config('survey_p10')
    products=survey_p8.load_audit_products(tic)
    harmonised,notes=survey_p8.harmonise_cadence(products,cfg.target_cadence_minutes)
    lc,prov=survey_p8.build_prepared(tic,cfg,harmonised,cadence_notes=notes)
    t=np.asarray(lc.time.value);f=np.asarray(lc.flux.value);e=np.asarray(lc.flux_err.value);sectors=np.asarray(lc.meta['TESSHUNTER_SECTOR'])
    native=DATA/f'prepared/tic{tic}/native200.npz'
    if native.exists():raise FileExistsError(native)
    native.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(native,time=t,flux=f,flux_err=e,sector=sectors)
    write(native.with_suffix('.json'),prov)
    counts={str(int(s)):int((sectors==s).sum()) for s in np.unique(sectors)}
    ok=np.isfinite(f)
    result=dict(tic_id=tic,utc=utc(),usable_sectors=sorted(int(s) for s,n in counts.items() if n>=50),sector_points=counts,
        n_cad=int(ok.sum()),prepared_path=native.relative_to(REPO).as_posix(),prepared_sha256=sha(native),
        provenance_sha256=sha(native.with_suffix('.json')),ingest_key=cfg.ingest_key(),source_sha256=sha(Path(__file__)))
    write(H/'results/prepared'/f'tic{tic}.json',result)
    return result

def _job_id(tic):
    return f'p9h_tic{int(tic)}'

def collect_host(tic):
    """After the prediction lock: the host's locked search result into its blind root, then the P10 collect."""
    root,F,A,V=setup(tic)
    lock=read(MANIFESTS/'neg_p9_search_predictions_lock.json')
    row=next(r for r in lock['jobs'] if r['job_id']==_job_id(tic))
    if row['status']!='COMPLETE':return dict(tic_id=tic,status=row['status'])
    source=REPO/row['result_path']
    if sha(source)!=row['result_sha256']:raise RuntimeError('Locked search result changed')
    target=root/'search/results'/f'tic{tic}.json'
    if not target.exists():write(target,read(source))
    summary=F.collect(root/'search',H/'manifests/heldout_execution.csv')
    return dict(tic_id=tic,status='COMPLETE',n_pass_pregate=summary['n_pass_pregate'])

def stage(tic,which,key,route):
    root,F,A,V=setup(tic)
    if route!=route_of(tic):raise RuntimeError('Route differs from the registered host route')
    for folder,field,allowed in REQUIREMENTS[route][which]:
        rec=root/folder/f'{key}.json'
        if not rec.exists() or read(rec).get(field) not in allowed:raise RuntimeError(f'{which} is not registered for {key} on the {route} route')
    job=next(j for j in V.jobs() if V.kkey(tic,j['period'])==key)
    if which=='D':
        return stage_d(tic,key,route,job,root,'neg_p9_D')
    kw={'threads':8,'oversampling':3} if which=='C' else ({'threads':1} if which=='A' else {})
    r=F.STAGE_FN[which](job,**kw)
    print(which,key,r.get('decision',r.get('gate',r.get('provisional_verdict'))),r.get('reason'),flush=True)
    if r.get('decision')=='ERROR' or r.get('gate')=='ERROR' or r.get('verdict')=='ERROR':raise SystemExit(1)

def d_runtime(tic,key,route,job,root,phase,crossmatch_star,redact,tier):
    """The Stage D runtime (stage_d_worker_p12 fields) for one held-out case."""
    star={k:float(v) for k,v in execution_rows()[tic].items() if k!='tic_id'}
    nb=P9/'inputs/neighbours'/f'tic{tic}.json'
    seal=read(MANIFESTS/'heldout_source_seal.json')
    sources=dict(seal['files']);sources[(MANIFESTS/'heldout_source_seal.json').relative_to(REPO).as_posix()]=sha(MANIFESTS/'heldout_source_seal.json')
    return dict(candidate_id=key,key=key,tic_id=tic,period=float(job['period']),depth_ppt=float(job['depth_ppt']),phase=phase,
        root=root.relative_to(REPO).as_posix(),route=route,redact_catalogue=redact,product_source='heldout',arm='p9_inputs',
        rules=['p12.0'],crossmatch_star=crossmatch_star,tce_association=None,star=star,
        neighbours_reference=dict(path=nb.relative_to(REPO).as_posix(),sha256=sha(nb)),packet_subtree='neg_p9',
        population_tier=tier,n_draws=100000,source_hashes=sources,review_reference=None,
        job=dict(rank=int(job.get('rank') or 0),tic_id=tic,period=float(job['period']),depth_ppt=float(job['depth_ppt'])))

def stage_d(tic,key,route,job,root,phase):
    """D through the P12 worker: the P9 crossmatch adapter (known status redacted as P9 ran it), 4a redaction on negatives."""
    policy=read(P9/'inputs/catalogue_policy'/f'tic{tic}.json')
    xm=dict(status='KNOWN_STATUS_REDACTED',catalog_stamp='P9 frozen catalogue outcome on preparation side',**policy)
    negative=route=='negatives'
    runtime=d_runtime(tic,key,'forced_negatives' if negative else 'normal',job,root,phase,xm,negative,
                      'heldout_p9_negative' if negative else 'heldout_p9_positive')
    path=H/'work/d_runtime'/phase/f'{key}.json'
    if path.exists():raise FileExistsError(path)
    write(path,runtime)
    import stage_d_worker_p12 as W
    code=W.main(str(path),sha(path))
    if code:raise SystemExit(code)

def plan(which,routes,phase=None):
    """Edit (8): the P12 controller's jobs manifest for one stage; the coordinator reads only blind records."""
    if (MANIFESTS/'controller_owner.json').exists():raise RuntimeError('Plan only between phases')
    verify_seal()
    phase=phase or f'neg_p9_{which}'
    registered=hosts()
    ids=[int(t) for t,r in registered['route'].items() if r in routes]
    seal=read(MANIFESTS/'heldout_source_seal.json')
    sources=dict(seal['files']);sources[(MANIFESTS/'heldout_source_seal.json').relative_to(REPO).as_posix()]=sha(MANIFESTS/'heldout_source_seal.json')
    sources[(MANIFESTS/'heldout_hosts.json').relative_to(REPO).as_posix()]=sha(MANIFESTS/'heldout_hosts.json')
    jobs=[]
    if which=='search':
        stars=execution_rows()
        for tic in sorted(ids):
            prepared=read(H/'results/prepared'/f'tic{tic}.json')
            runtime=dict(tic_id=tic,preset='survey_p10',job_id=_job_id(tic),star={k:float(v) for k,v in stars[tic].items() if k!='tic_id'},
                prepared_path=prepared['prepared_path'],prepared_sha256=prepared['prepared_sha256'],
                provenance_sha256=prepared['provenance_sha256'],ingest_key=prepared['ingest_key'],source_hashes=sources,
                run=(DATA/'runs/survey_p10').relative_to(REPO).as_posix())
            path=MANIFESTS/f'runtime/{phase}/{_job_id(tic)}.json';write(path,runtime)
            rel=path.relative_to(REPO).as_posix()
            jobs.append(dict(job_id=_job_id(tic),attempt=1,arguments=['p12/protocol/blind_search_worker_p12.py',rel,sha(path)],
                result_path=f"p12/results/search_receipts/{(DATA/'runs/survey_p10').relative_to(REPO/'data/survey/p12').as_posix()}/{_job_id(tic)}.json",
                source_hashes=dict(sources,**{rel:sha(path)})))
    else:
        for tic in sorted(ids):
            if which=='A' and not (H/'results/blind'/f'tic{tic}'/'survivors.csv').exists():
                collect_host(tic)
            root=H/'results/blind'/f'tic{tic}';table=root/'survivors.csv'
            if not table.exists():continue
            route=registered['route'][str(tic)]
            for r in csv.DictReader(table.open(encoding='utf-8')):
                key=f'tic{tic}_P{float(r["period_days"]):.4f}'
                if all((root/folder/f'{key}.json').exists() and read(root/folder/f'{key}.json').get(field) in allowed
                       for folder,field,allowed in REQUIREMENTS[route][which]):
                    jobs.append(dict(job_id=key,attempt=1,arguments=['p12/heldout/runner.py','stage','--tic',str(tic),'--stage',which,
                        '--key',key,'--route',route],result_path=_result_path(root,which,key),source_hashes=sources))
    out=MANIFESTS/f'{phase}_jobs.json'
    if out.exists():raise FileExistsError(out)
    write(out,jobs)
    sys.path.insert(0,str(REPO/'p12/protocol'))
    from ledger_p12 import price_phase
    price_phase(phase,out)
    print('planned',phase,len(jobs),'jobs; deadline',DEADLINES[which],'workers',WORKERS[which],flush=True)
    return out

def _result_path(root,which,key):
    if which=='D':return f'p12/results/funnel/neg_p9_D/D/{key}.json'
    folder={'A':'stageA','S':'secondary','B':'stageB','C':'stageC','D':'stageD'}[which]
    return (root/folder/f'{key}.json').relative_to(REPO).as_posix()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=['prepare','stage','plan','collect'])
    p.add_argument('--tic',type=int);p.add_argument('--stage',default='search');p.add_argument('--key')
    p.add_argument('--route',action='append',choices=['negatives','normal']);p.add_argument('--phase');a=p.parse_args()
    if a.cmd=='prepare':prepare(a.tic)
    elif a.cmd=='collect':print(collect_host(a.tic))
    elif a.cmd=='stage':stage(a.tic,a.stage,a.key,a.route[0])
    else:plan(a.stage,a.route or ['negatives','normal'],a.phase)
