"""Evaluator-only common-array generation; runtime jobs never receive truth."""
from common import *
environment()
import csv
import sys
import time
import numpy as np
import psutil
sys.path.insert(0,str(REPO/'src'))
from tesshunter import survey,survey_p8
from tesshunter.p11_5_search import array_key

def save_native(path,lc,prov):
    if path.exists():raise FileExistsError(path)
    np.savez_compressed(path,time=lc.time.value,flux=lc.flux.value,flux_err=lc.flux_err.value,
                        sector=lc.meta['TESSHUNTER_SECTOR'])
    write(path.with_suffix('.json'),prov)

def selection():
    hosts=[r for r in read(ROOT/'manifests/hosts.json') if r['population']=='D_core']
    groups={}
    for h in hosts:
        m=float(h['original']['tmag']);s=h['n_ffi']
        label=f'{min(2,int((m-12.5)/.5))}:{0 if s<=5 else 1 if s<=10 else 2}'
        groups.setdefault(label,[]).append(h)
    for rows in groups.values():rows.sort(key=lambda r:order(r['tic_id'],'development'))
    chosen=[];used={k:0 for k in groups}
    for i in range(len(hosts)):
        key=max((k for k in groups if used[k]<len(groups[k])),
                key=lambda k:((i+1)*len(groups[k])/len(hosts)-used[k],k))
        chosen.append(dict(tic_id=groups[key][used[key]]['tic_id'],stratum=key));used[key]+=1
    ordered=sorted(hosts,key=lambda r:(r['n_quality_points'],r['baseline_days'],r['tic_id']))
    pilot=[]
    for tercile in np.array_split(np.array(ordered,dtype=object),3):
        parts=np.array_split(np.array(sorted(tercile,key=lambda r:r['baseline_days']),dtype=object),2)
        for part in parts:pilot.append(min(part,key=lambda r:order(r['tic_id'],'timing'))['tic_id'])
    write(ROOT/'manifests/development_order.json',dict(order=chosen,nested_sizes=[n for n in (60,120,180,len(hosts)) if n<=len(hosts)],pilot_hosts=pilot,
          strata={k:len(v) for k,v in groups.items()},outcomes_inspected=False))
    jobs=[dict(job_id=f'prepare_tic{r["tic_id"]}',tic_id=r['tic_id'],phase='prepare') for r in hosts]
    write(ROOT/'manifests/prepare_jobs.json',jobs)
    print('preparation hosts',len(jobs),'timing pilot',pilot)

def one(tic):
    start=time.perf_counter();cpu=time.process_time()
    h=next(r for r in read(ROOT/'manifests/hosts.json') if r['tic_id']==tic)
    root=DATA/f'prepared_v2/tic{tic}';root.mkdir(parents=True,exist_ok=True)
    out=ROOT/f'results/preparation/tic{tic}.json'
    if out.exists():raise FileExistsError(out)
    products=survey_p8.load_audit_products(tic,DATA/'raw',sector_min=56,sector_max=105)
    cfg=survey.get_config('survey_p10')
    harmonised,notes=survey_p8.harmonise_cadence(products,cfg.target_cadence_minutes)
    lc,prov=survey_p8.build_prepared(tic,cfg,harmonised,cadence_notes=notes)
    save_native(root/'uninjected.npz',lc,prov)
    prepared_sector=np.asarray(lc.meta['TESSHUNTER_SECTOR'])
    counts={int(s):int(np.count_nonzero(prepared_sector==s)) for s in np.unique(prepared_sector)}
    usable=[s for s in h['verified_native_ffi_sectors'] if counts.get(s,0)>=50]
    core=len(usable)>=3 and len(set(usable)&set(h['targeted_ffi_sectors']))<len(usable)/2
    model_rows=[r for r in read(ROOT/'manifests/injections_evaluator.json') if r['tic_id']==tic]
    # Signals are generated before harmonisation and every adaptive operation.
    cases=[dict(job_id=f'tic{tic}',kind='natural',prepared='uninjected.npz')]
    reference_t=np.asarray(lc.time.value);reference_f=np.asarray(lc.flux.value)
    for row in model_rows:
        model=row['fixed_absolute_model'];p=float(model['period']);t0=float(model['t0'])
        injected,info=survey_p8.inject_products(products,period=p,t0=t0,rp_rs=float(model['rp_rs']),
            b=float(model['b']),a_rs=float(model['a_rs']),u=(float(model['u1']),float(model['u2'])))
        injected,cad_notes=survey_p8.harmonise_cadence(injected,cfg.target_cadence_minutes)
        ilc,iprov=survey_p8.build_prepared(tic,cfg,injected,info,cad_notes)
        # Provenance boolean signals injection, but truth parameters never enter runtime files.
        name=row['job_id']+'.npz';save_native(root/name,ilc,iprov)
        cases.append(dict(job_id=row['job_id'],kind='injection',prepared=name))
    for case in cases:
        path=root/case['prepared'];clc,cprov=survey.load_stitched(path)
        with np.load(path,allow_pickle=False) as z:clc.meta['TESSHUNTER_SECTOR']=z['sector']
        case.update(prepared_path=path.relative_to(REPO).as_posix(),prepared_sha256=sha(path),
                    array_key=array_key(clc.time.value,clc.flux.value,clc.flux_err.value,clc.meta['TESSHUNTER_SECTOR'],config=cfg.to_dict()),
                    n_points=len(clc),baseline_days=float(np.ptp(clc.time.value)))
    write(out,dict(tic_id=tic,status='COMPLETE',eligible_after_preparation=core,usable_ffi_sectors=usable,sector_points=counts,
        cases=cases,wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
        memory_rss_bytes=psutil.Process().memory_info().rss,memory_peak_bytes=getattr(psutil.Process().memory_info(),'peak_wset',None)))
    print('prepared',tic,'cases',len(cases),'eligible',core,flush=True)

if __name__=='__main__':
    selection() if sys.argv[1]=='select' else one(int(sys.argv[1]))
