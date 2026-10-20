"""Truth-side sampling/data preparation. Execution imports only common and runner."""
from common import *
import argparse, csv, time, shutil, subprocess, hashlib
import numpy as np
import pandas as pd

def order(tic,salt='sampling'):
    return hashlib.sha256(f'{SEED}:{salt}:{int(tic)}'.encode()).hexdigest()
def select():
    df=pd.read_csv(P9/'truth/sampling_frame.csv');df=df[df.frame_eligible]
    groups=['p8_proxy','small_long','small_short','other_radius','EB_detached','EB_contact','uncertain']
    picked=set();rows=[]
    for g in groups:
        ids=sorted(set(df[df.stratum==g].tic_id.astype(int))-picked,key=order)
        for i,tic in enumerate(ids):rows.append(dict(tic_id=tic,stratum=g,priority=i+1,order_hash=order(tic),split='development' if int(order(tic,'split')[:8],16)%4==0 else 'holdout'))
        picked.update(ids)
    pr=pd.DataFrame(rows);pr.to_csv(P9/'truth/selection_priority.csv',index=False)
    pilot=pr[((pr.stratum=='p8_proxy')&(pr.priority<=2))|((pr.stratum.isin(['small_long','small_short','EB_detached','uncertain']))&(pr.priority==1))]
    pilot.to_csv(P9/'truth/pilot_selection.csv',index=False)
    write(P9/'manifests/pilot_ids.json',list(pilot.tic_id.astype(int)))
    write(P9/'protocol/pilot_lock.json',dict(utc=utc(),seed=SEED,protocol_sha256=sha(P9/'protocol/PREREGISTRATION.md'),
       priority_sha256=sha(P9/'truth/selection_priority.csv'),pilot_sha256=sha(P9/'truth/pilot_selection.csv'),
       frame_sha256=sha(P9/'truth/sampling_frame.csv'),code_sha256={p.name:sha(p) for p in P9.glob('*.py')}))
    print(pilot.to_string(index=False),flush=True)

def download(tic):
    frozen_imports()
    import audit_p5 as A
    from tesshunter.stellar import fetch_tic_params
    os.environ.pop('TESSHUNTER_OFFLINE',None)
    A.AUDIT_CACHE=P9/'work/download_cache';A.AUDIT_CACHE.mkdir(parents=True,exist_ok=True)
    A.set_roots(P9/'work/preparation',P9/'inputs/raw')
    target=P9/'inputs/raw'/f'tic{tic}'
    start=time.perf_counter();receipt={'tic_id':tic,'started_utc':utc(),'free_bytes':shutil.disk_usage(REPO).free}
    try:
        existing=REPO/'data/survey/audit_lc'/f'tic{tic}'
        if existing.exists() and not target.exists():
            shutil.copytree(existing,target);receipt['cache_origin']=str(existing)
        idx=A.download(tic,sector_min=56)
        receipt['download_index']=idx
        old=REPO/'data/cache/tic'/f'tic{tic}.json'
        cache=P9/'work/tic_cache';cache.mkdir(parents=True,exist_ok=True)
        if old.exists():shutil.copy2(old,cache/old.name)
        st=fetch_tic_params(tic,cache_dir=cache).to_dict()
        # Fixed allow-list: stellar data only, even if a future cache adds planet fields.
        fields=['tic_id','ra','dec','tmag','teff','teff_err','logg','logg_err','radius','radius_err','mass','mass_err',
          'rho','rho_err','lum','distance_pc','contamination_ratio','gaia_id','gaia_mag','gaia_bp','gaia_rp','source','fetched_utc','assumed_errors']
        st={k:st.get(k) for k in fields};st['notes']=[]
        write(P9/'inputs/stellar'/f'tic{tic}.json',st)
        receipt['raw_sha256']={p.name:sha(p) for p in target.glob('*') if p.is_file()}
        receipt['stellar_sha256']=sha(P9/'inputs/stellar'/f'tic{tic}.json')
        receipt['status']='complete' if any(p.get('file') for p in idx.get('products',[])) else 'no_data'
    except Exception as e:
        receipt.update(status='error',error=f'{type(e).__name__}: {e}')
    receipt['seconds']=time.perf_counter()-start;write(P9/'manifests/preparation'/f'tic{tic}.json',receipt)
    print(tic,receipt['status'],round(receipt['seconds'],1),receipt.get('error',''),flush=True)

def prepare_batch(kind):
    from concurrent.futures import ThreadPoolExecutor,as_completed
    ids=read(P9/f'manifests/{kind}_ids.json')
    def one(tic):
        path=P9/'manifests/preparation'/f'tic{tic}.json'
        if path.exists() and read(path).get('status')=='complete': return (tic,'cached')
        log=P9/'logs'/f'prepare_tic{tic}.log'
        with log.open('a',encoding='utf-8') as f:
            pr=subprocess.Popen([sys.executable,str(Path(__file__)),'download','--tic',str(tic)],stdout=f,stderr=subprocess.STDOUT)
            try: return tic,pr.wait(timeout=2400)
            except subprocess.TimeoutExpired:
                import psutil
                parent=psutil.Process(pr.pid)
                for c in parent.children(recursive=True): c.kill()
                parent.kill();write(path,dict(tic_id=tic,status='timeout',seconds=2400));return tic,'timeout'
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in as_completed([ex.submit(one,int(t)) for t in ids]):print(f.result(),flush=True)

def inputs(kind):
    frozen_imports()
    from tesshunter.survey_p8 import load_audit_products,harmonise_cadence
    from tesshunter import catalog_crossmatch as X
    X.CATALOG_CACHE_DIR=P9/'truth/production_catalogues'
    cat=X.KnownObjectCatalog.load(offline=True)
    ids=read(P9/f'manifests/{kind}_ids.json');frame=pd.read_csv(P9/'truth/sampling_frame.csv')
    truth=frame[frame.tic_id.isin(ids)&frame.frame_eligible].copy();elig=[];execrows=[]
    for tic in ids:
        stpath=P9/'inputs/stellar'/f'tic{tic}.json'
        if not stpath.exists():
            for _,r in truth[truth.tic_id==tic].iterrows():elig.append(dict(truth_id=r.truth_id,tic_id=tic,status='unavailable_data',opportunities=None))
            continue
        st=read(stpath)
        hs=cat.check(tic,st.get('ra'),st.get('dec'),resolve_neighbours=False).to_dict()
        write(P9/'truth/exclusions'/f'tic{tic}.json',hs)
        write(P9/'inputs/catalogue_policy'/f'tic{tic}.json',dict(mode='external_validation',
          known_status_exclusion_bypassed=hs['status'] in ('REJECT','FLAG'),actual_submission_eligible=False,
          original_result_sha256=sha(P9/'truth/exclusions'/f'tic{tic}.json'),
          neighbour_positions_checked=True,extra_tic_cone_resolution=False))
        try:
            prods=load_audit_products(tic,P9/'inputs/raw',sector_min=56)
            prods,notes=harmonise_cadence(prods,200/60)
            times=np.sort(np.concatenate([p['time'][np.isfinite(p['time'])] for p in prods]))
            for _,r in truth[truth.tic_id==tic].iterrows():
                p=float(r.period);t0=float(r.epoch_btjd);d=float(r.duration_hours)/24
                centers=np.arange(np.floor((times.min()-t0)/p),np.ceil((times.max()-t0)/p)+1)*p+t0
                observed=[]
                for c in centers:
                    ni=np.sum(np.abs(times-c)<d/2);nb=np.sum((np.abs(times-c)>d*.65)&(np.abs(times-c)<max(.5,3*d)))
                    if ni*(200/86400)/d>=.5 and nb>=10:observed.append(float(c))
                status='eligible' if len(observed)>=3 and len(prods)>=3 else 'insufficient_observed_opportunities'
                elig.append(dict(truth_id=r.truth_id,tic_id=tic,status=status,opportunities=len(observed),centers=observed))
            write(P9/'manifests/products'/f'tic{tic}.json',dict(tic_id=tic,notes=notes,products=[{k:p[k] for k in p if k not in ['time','flux','flux_err','sap_flux','sap_flux_err','sap_bkg','quality']} for p in prods],
              n_cadences=len(times),baseline_days=float(np.ptp(times))))
            execrows.append(dict(tic_id=tic,radius_rsun=st.get('radius'),mass_msun=st.get('mass'),teff_k=st.get('teff'),
              tmag=st.get('tmag'),ra_deg=st.get('ra'),dec_deg=st.get('dec')))
        except Exception as e:
            for _,r in truth[truth.tic_id==tic].iterrows():elig.append(dict(truth_id=r.truth_id,tic_id=tic,status='unavailable_data',error=str(e),opportunities=None))
    truth.to_csv(P9/f'truth/{kind}_truth.csv',index=False)
    write(P9/f'truth/{kind}_eligibility.json',elig)
    # Every available selected host executes; opportunity exclusions apply only in scoring.
    pd.DataFrame(execrows).to_csv(P9/f'manifests/{kind}_execution.csv',index=False)
    write(P9/f'protocol/{kind}_inputs_lock.json',dict(utc=utc(),truth_sha256=sha(P9/f'truth/{kind}_truth.csv'),
      execution_sha256=sha(P9/f'manifests/{kind}_execution.csv'),eligibility_sha256=sha(P9/f'truth/{kind}_eligibility.json'),
      product_hashes={str(t):sha(P9/'manifests/products'/f'tic{t}.json') for t in ids if (P9/'manifests/products'/f'tic{t}.json').exists()}))
    print('execution hosts',len(execrows),'eligibility',pd.Series([e['status'] for e in elig]).value_counts().to_dict(),flush=True)

def sky(tic):
    frozen_imports()
    import audit_p5 as A
    os.environ.pop('TESSHUNTER_OFFLINE',None)
    A.REPO=P9;A.set_roots(P9/'truth/sky_raw',P9/'inputs/raw')
    A.stellar_from_cache=lambda t:read(P9/'inputs/stellar'/f'tic{int(t)}.json')
    table=P9/'work/sky_empty_survivors.csv';table.write_text('tic_id,depth_ppt\n',encoding='utf-8')
    A.set_population(survivors_csv=table,packets_dir=P9/'inputs/empty_packets')
    raw=A.neighbours_step(tic)
    import copy
    nb=copy.deepcopy(raw);changes=[]
    forbidden={'main_id','otype','otypes','best_class_name','vari_class','Type','Name','OID','Period','Epoch','nss',
               'period','period_error','eccentricity','semi_amplitude_primary','inclination','nss_solution_type'}
    def redact(o,prefix=''):
        if isinstance(o,dict):
            for k in list(o):
                if k in forbidden:
                    changes.append(prefix+k);o[k]=[] if isinstance(o[k],list) else None
                else:redact(o[k],prefix+k+'.')
        elif isinstance(o,list):
            for i,v in enumerate(o):redact(v,prefix+str(i)+'.')
    redact(nb)
    nb['summary']='P9 sanitized sky measurements; counts, astrometry, magnitudes and generic variability retained; source names, classes and orbital solutions redacted.'
    write(P9/'inputs/neighbours'/f'tic{tic}.json',nb)
    write(P9/'truth/sky_redactions'/f'tic{tic}.json',dict(tic_id=tic,fields=changes,raw_sha256=sha(P9/'truth/sky_raw/neighbours'/f'tic{tic}.json'),sanitized_sha256=sha(P9/'inputs/neighbours'/f'tic{tic}.json')))
    print(tic,'sky',nb.get('gaia',{}).get('target_match'),nb.get('gaia',{}).get('error'),flush=True)

def sky_batch(kind):
    from concurrent.futures import ThreadPoolExecutor,as_completed
    ids=read(P9/f'manifests/{kind}_ids.json')
    def one(tic):
        path=P9/'inputs/neighbours'/f'tic{tic}.json'
        if path.exists():return tic,'cached'
        with (P9/'logs'/f'sky_tic{tic}.log').open('w',encoding='utf-8') as f:
            pr=subprocess.Popen([sys.executable,str(Path(__file__)),'sky','--tic',str(tic)],stdout=f,stderr=subprocess.STDOUT)
            try:return tic,pr.wait(timeout=900)
            except subprocess.TimeoutExpired:
                from runner import stop_tree
                stop_tree(pr);return tic,'timeout'
    with ThreadPoolExecutor(max_workers=2) as ex:
        for f in as_completed([ex.submit(one,int(t)) for t in ids]):print(f.result(),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=['select','download','batch','inputs','sky','sky_batch']);p.add_argument('--tic',type=int);p.add_argument('--kind',default='pilot');a=p.parse_args()
    if a.cmd=='select':select()
    elif a.cmd=='download':download(a.tic)
    elif a.cmd=='batch':prepare_batch(a.kind)
    elif a.cmd=='inputs':inputs(a.kind)
    elif a.cmd=='sky':sky(a.tic)
    else:sky_batch(a.kind)
