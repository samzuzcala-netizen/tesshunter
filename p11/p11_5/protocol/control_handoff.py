"""Evaluator-only audited control inputs; blinded runtime candidate manifests."""
from common import *
environment()
import sys,time,shutil
from collections import Counter
import numpy as np
sys.path[:0]=[str(REPO/'src'),str(ROOT/'protocol')]
from tesshunter import survey_p8
from candidates import sources,catalogues

EXCLUDED={80,83,85,99,100,101,102,103,104}
AUTHOR={'SPOC':0,'TESS-SPOC':1,'QLP':2}

def selected(row):
    tic=row['tic_id'];audit=read(ROOT/f'results/control_inputs/tic{tic}.json');valid=[];exclusions=[]
    for p in audit['records']:
        m=p['metadata'];s=int(m['sector']);why=[]
        if s>105 or (not row['native_control'] and s<56):why.append('outside_input_sector_range')
        if row['restrict_sectors'] is not None and s not in row['restrict_sectors']:why.append('outside_original_control_sectors')
        if not p.get('checks') or not all(p['checks'].values()):why.append('unverified_source_identity_or_times')
        if m['author']=='QLP' and s in EXCLUDED:why.append('unresolved_timing')
        if m['author']=='QLP' and 74<=s<=79 and p.get('timing_status')!='QLP_74_79_CORRECTED_SOURCE_VERIFIED':why.append('unverified_corrected_era')
        if p.get('n_quality_good',0)<50:why.append('too_few_quality_points')
        if not row['native_control'] and float(m.get('cadence_s',1e9))>300:why.append('coarser_than_200s_policy')
        if why:exclusions.append(dict(metadata=m,reasons=why));continue
        if sha(REPO/p['raw_path'])!=p['raw_sha256']:raise ValueError('Control raw changed')
        valid.append(p)
    best={}
    for p in valid:
        s=p['metadata']['sector']
        if s not in best or AUTHOR[p['metadata']['author']]<AUTHOR[best[s]['metadata']['author']]:best[s]=p
    return [best[s] for s in sorted(best)],exclusions

def one(registration_id):
    started=time.perf_counter();rows=read(ROOT/'manifests/controls_evaluator.json')['entries'];row=next(r for r in rows if r['registration_id']==registration_id)
    tid=row['tic_id'];products,excluded=selected(row)
    record=dict(registration_id=registration_id,tic_id=tid,original_id=row['original_id'],collection=row['collection'],
        selected_products=[dict(metadata=p['metadata'],raw_path=p['raw_path'],raw_sha256=p['raw_sha256'],source_matches=p['source_matches']) for p in products],exclusions=excluded)
    if not products:
        record.update(status='INPUT_ERROR',reason='No trustworthy usable selected control product',wall_seconds=time.perf_counter()-started)
        write(ROOT/f'results/control_handoff/{registration_id}.json',record);return
    raw_key=digest(dict(products=[p['raw_sha256'] for p in products],model=row['fixed_absolute_model']))
    # Per-registration directories prevent concurrent creation races. Exact
    # measurement joins below remove overlaps after immutable inputs are sealed.
    rawroot=DATA/f'control_raw/{registration_id}';folder=rawroot/f'tic{tid}';folder.mkdir(parents=True,exist_ok=False)
    raw=[]
    for p in products:
        with np.load(REPO/p['raw_path'],allow_pickle=False) as z:raw.append(dict(dict(z),**p['metadata']))
    model=row['fixed_absolute_model']
    if model:
        raw,_=survey_p8.inject_products(raw,period=float(model['period']),t0=float(model['t0']),rp_rs=float(model['rp_rs']),
            b=float(model['b']),a_rs=float(model['a_rs']),u=(float(model['u1']),float(model['u2'])))
    index=[]
    for i,(p,data) in enumerate(zip(products,raw)):
        if model:
            if shutil.disk_usage(REPO).free<31000000000:raise RuntimeError('Headroom')
            dest=folder/f'product{i:03d}.npz'
            np.savez_compressed(dest,**{k:data[k] for k in ('time','flux','flux_err','sap_flux','sap_flux_err','sap_bkg','quality')})
        else:dest=REPO/p['raw_path']
        index.append(dict(p['metadata'],file=str(dest),sha256=sha(dest)))
    write(folder/'index.json',dict(tic_id=tid,products=index,input_key=raw_key,truth_fields_present=False))
    raw_key=digest([p['sha256'] for p in index])
    candidate=dict(row['candidate']);candidate['n_units']=len(products)
    stellar=REPO/f'p9/inputs/stellar/tic{tid}.json' if row['collection']=='C_native_37' and row['original_id'].startswith('p9_') else REPO/f'data/cache/tic/tic{tid}.json'
    stellar_reference=dict(path=stellar.relative_to(REPO).as_posix(),sha256=sha(stellar)) if stellar.exists() else None
    prediction_key=digest(dict(raw_key=raw_key,candidate={k:candidate[k] for k in ('period','epoch_btjd','duration_days','depth_ppt')},
                               stellar_reference=stellar_reference,star_fallback=row['star'],native_control=row['native_control'],source_hashes=sources()))
    cid='historical_'+prediction_key[:24]
    catalog=read(ROOT/'manifests/control_catalogue_references.json').get(str(tid))
    runtime=dict(candidate_id=cid,series_id='historical_'+raw_key[:24],tic_id=tid,candidate=candidate,
        all_candidates=[candidate],star=row['star'],raw_root=rawroot.relative_to(REPO).as_posix(),raw_index_sha256=sha(folder/'index.json'),
        raw_hashes={Path(p['file']).relative_to(REPO).as_posix():p['sha256'] for p in index},input_key=raw_key,source_hashes=sources(),
        catalogue_reference=catalog,engineering_label='Historical development control outside survey-domain inference',native_control=row['native_control'])
    runtime['stellar_reference']=stellar_reference
    # Per-registration handoffs are merged by an explicit serial finalizer; no
    # concurrent cache creation and no TIC-only joins.
    write(ROOT/f'manifests/control_runtime_drafts/{registration_id}.json',runtime)
    record.update(status='COMPLETE',candidate_id=cid,prediction_key=prediction_key,raw_input_key=raw_key,
                  wall_seconds=time.perf_counter()-started)
    write(ROOT/f'results/control_handoff/{registration_id}.json',record)
    print('control handoff',registration_id,flush=True)

def jobs():
    refs=catalogues()
    write(ROOT/'manifests/control_catalogue_references.json',{str(t):dict(path=p.as_posix(),sha256=sha(REPO/p)) for t,p in refs.items()})
    rows=read(ROOT/'manifests/controls_evaluator.json')['entries']
    paths=list(sources())+['p11/p11_5/protocol/candidates.py','p11/p11_5/protocol/control_handoff.py']
    write(ROOT/'manifests/control_handoff_jobs.json',[dict(job_id=r['registration_id'],command=['p11/p11_5/protocol/control_handoff.py','one',r['registration_id']],source_paths=paths) for r in rows])

def finalize():
    rows=read(ROOT/'manifests/controls_evaluator.json')['entries'];joins=[];unique={}
    for row in rows:
        r=read(ROOT/f'results/control_handoff/{row["registration_id"]}.json');cid=r.get('candidate_id')
        if cid and cid not in unique:
            runtime=read(ROOT/f'manifests/control_runtime_drafts/{row["registration_id"]}.json')
            write(ROOT/f'manifests/runtime_funnel/{cid}.json',runtime);unique[cid]=row['registration_id']
        joins.append(dict(row,**{k:r.get(k) for k in ('status','candidate_id','prediction_key','raw_input_key','reason')},
                          canonical_registration=unique.get(cid)))
    write(ROOT/'manifests/control_joins.json',dict(rows=joins,registered=len(rows),unique_measurements=len(unique),
        unavailable=sum(r['status']!='COMPLETE' for r in joins),meaning='All collections retain original rows; exact input/candidate/config equality alone shares work.'))
    for stage in ('A','S','B','C'):
        jobs=[dict(job_id=stage+'_'+cid,command=['p11/p11_5/protocol/funnel_worker.py',stage,f'p11/p11_5/manifests/runtime_funnel/{cid}.json'],source_paths=list(sources())) for cid in unique]
        write(ROOT/f'manifests/control_{stage}.json',jobs)
    print('control measurements',len(unique),'registered',len(rows))

if __name__=='__main__':
    if sys.argv[1]=='jobs':jobs()
    elif sys.argv[1]=='one':one(sys.argv[2])
    elif sys.argv[1]=='finalize':finalize()
