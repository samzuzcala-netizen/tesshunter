"""Blind, separately timed unchanged A/S/B and finite C candidate worker."""
from common import *
environment()
import csv,copy,sys,time,traceback,dataclasses,http.client
import numpy as np
import psutil
sys.path[:0]=[str(REPO/'src'),str(REPO/'scripts')]
from tesshunter import survey
from tesshunter import p11_5_clocal as C
import audit_p5 as A
import revet_p6 as V
import p8_funnel as F

def safe(x):
    if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [safe(v) for v in x]
    if isinstance(x,np.generic):return safe(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x

def archive_arrays(value,path):
    arrays={}
    def visit(x,key='root'):
        if isinstance(x,np.ndarray):
            arrays[key]=x
            return dict(archive=path.relative_to(REPO).as_posix(),array=key,shape=list(x.shape))
        if isinstance(x,dict):return {str(k):visit(v,key+'_'+str(k)) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [visit(v,key+'_'+str(i)) for i,v in enumerate(x)]
        return safe(x)
    record=visit(value)
    if arrays:
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():raise FileExistsError(path)
        np.savez_compressed(path,**arrays)
    return record

def setup(runtime):
    def reject_truth(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('truth','injection','injection_model','fixed_absolute_model') or key.startswith('inj_'):
                    raise ValueError('Evaluator truth field in runtime input')
                reject_truth(item)
        elif isinstance(value,list):
            for item in value:reject_truth(item)
    reject_truth(runtime)
    if set(runtime)-{'candidate_id','series_id','tic_id','candidate','all_candidates','star','raw_root','raw_index_sha256',
                     'input_key','source_hashes','catalogue_reference','engineering_label','config_name','native_control','raw_hashes','stellar_reference'}:
        raise ValueError('Truth/non-runtime field in candidate job')
    for path,expected in runtime['source_hashes'].items():
        if sha(REPO/path)!=expected:raise ValueError('Funnel source changed: '+path)
    tid=runtime['tic_id'];root=DATA/f'funnel/{runtime["candidate_id"]}'
    raw=REPO/runtime['raw_root'];index=raw/f'tic{tid}/index.json'
    if sha(index)!=runtime['raw_index_sha256']:raise ValueError('Raw input index changed')
    for path,expected in runtime['raw_hashes'].items():
        if sha(REPO/path)!=expected:raise ValueError('Frozen raw array bytes changed')
    reference=runtime.get('stellar_reference')
    if reference:
        if sha(REPO/reference['path'])!=reference['sha256']:raise ValueError('Stellar reference changed')
        A.stellar_from_cache=lambda tic:read(REPO/reference['path']) if int(tic)==int(tid) else {}
    for row in read(index)['products']:
        p=Path(row['file']);p=p if p.is_absolute() else index.parent/p
        expected=row.get('sha256') or row.get('npz_sha256')
        if expected and sha(p)!=expected:raise ValueError('Raw product changed')
    root.mkdir(parents=True,exist_ok=True)
    candidate=dict(runtime['candidate']);candidate.update(runtime['star']);candidate['tic_id']=tid
    columns=sorted(set(candidate)|{'period_days','rank','planet_num','n_units','snr'})
    for name,rows in [('survivors.csv',[candidate]),('candidates.csv',runtime['all_candidates'])]:
        path=root/name
        if not path.exists():
            with path.open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
    F.LC_ROOT=raw;F.PACKETS=root/'empty_packets';F.set_root(root);F.set_rules('p10.0')
    cfg=survey.get_config(runtime.get('config_name','survey_p10'))
    if runtime.get('native_control'):
        if not runtime.get('engineering_label'):raise ValueError('Native control profile requires explicit engineering domain')
        cfg=dataclasses.replace(cfg,name='p11_5_native_control',sector_min=None,bin_minutes=None)
        # The frozen engineering index already has one trusted native product per
        # sector. Preserve its actual per-sector exposures without homogenising.
        A.choose_per_sector=lambda products:sorted(products,key=lambda p:int(p['sector']))
    A.set_input_config(cfg)
    A.set_roots(root,raw)
    return root,candidate

def main(stage,path):
    start=time.perf_counter();cpu=time.process_time();runtime=read(path)
    cid=runtime['candidate_id'];out=ROOT/f'results/funnel/{stage}/{cid}.json'
    if out.exists():raise FileExistsError(out)
    network_bytes=0;http_read=http.client.HTTPResponse.read
    def counted_read(response,*args,**kwargs):
        nonlocal network_bytes
        value=http_read(response,*args,**kwargs);network_bytes+=len(value)
        if value:
            log=ROOT/f'results/network/{stage}_{cid}.jsonl';log.parent.mkdir(parents=True,exist_ok=True)
            with log.open('a',encoding='utf-8') as f:
                f.write(json.dumps(dict(utc=utc(),cumulative_response_body_bytes=network_bytes))+'\n');f.flush();os.fsync(f.fileno())
        return value
    http.client.HTTPResponse.read=counted_read
    root,job=setup(runtime);tid=job['tic_id'];key=A.key(tid,job['period'])
    record=dict(candidate_id=cid,series_id=runtime['series_id'],tic_id=tid,input_key=runtime['input_key'],
        raw_index_sha256=runtime['raw_index_sha256'],runtime_manifest_sha256=sha(path),source_hashes=runtime['source_hashes'],
        stage=stage,truth_opened=False,engineering_label=runtime.get('engineering_label'))
    try:
        if stage=='A':
            calls=[];old_tls=A.run_tls
            def tls(*args,**kwargs):
                result=old_tls(*args,**kwargs)
                periods=np.asarray(result.periods);pmin=args[3];pmax=args[4]
                calls.append(dict(requested_min=pmin,requested_max=pmax,actual_min=float(periods.min()),actual_max=float(periods.max()),
                    n_periods=len(periods),within_requested=bool(periods.min()>=pmin-1e-9 and periods.max()<=pmax+1e-9),
                    reused_in_C=False,reason='Original A behavior preserved; independent registered C grid'))
                return result
            A.run_tls=tls
            try:record['measurement']=V.stagea_one(job,threads=1)
            finally:A.run_tls=old_tls
            record['tls_grid_receipts']=calls
        elif stage=='S':record['measurement']=F.secondary_one(job)
        elif stage=='B':
            reference=runtime.get('catalogue_reference')
            if reference:
                if sha(REPO/reference['path'])!=reference['sha256']:raise ValueError('Catalogue reference changed')
                nb=read(REPO/reference['path']);nb['p11_5_reuse']=dict(reference,meaning='Catalogue measurements only; candidate flags recomputed by unchanged B')
                # gaia_flag_digest uses the current job depth, not the historical depths list.
                write(root/f'neighbours/tic{tid}.json',nb)
            record['measurement']=V.stageb_one(job)
        elif stage=='C':
            ar=read(ROOT/f'results/funnel/A/{cid}.json')['measurement']
            sr=read(ROOT/f'results/funnel/S/{cid}.json')['measurement']
            br=read(ROOT/f'results/funnel/B/{cid}.json')['measurement']
            if ar.get('decision')!='PASS' and not (runtime.get('engineering_label') and ar.get('chosen_ephemeris')):
                raise ValueError('C requires measured A passer or explicitly labelled engineering control')
            eph=ar['per_ephemeris'][ar['chosen_ephemeris']]['ephemeris']
            prepared=root/f'tls/{key}_lc.npz';meta=read(root/f'prep/{key}.json')
            with np.load(prepared,allow_pickle=False) as z:
                t,f,e=z['time'],z['flux'],z['flux_err'];tu=z['time_unbinned'];fu=z['flux_unbinned'];su=z['sector_unbinned']
                index=np.searchsorted(tu,t)
                if not np.array_equal(tu[index],t) or not np.array_equal(fu[index],f):raise ValueError('C native A array/sector mismatch')
                sector=su[index]
            sec=sr.get('secondary',{})
            seed=sec.get('deepest_secondary_in_sap') or next(iter(sec.get('secondaries',[])),{})
            phase=seed.get('phase') if isinstance(seed,dict) else None
            ep=dict(period_days=eph['period'],epoch_btjd=eph['t0'],duration_days=eph['duration'],depth_ppt=job['depth_ppt'],candidate_id=cid)
            star=dict(radius_rsun=meta['R_star'],mass_msun=meta['M_star'],teff_k=runtime['star'].get('teff_k'))
            measurement=C.measure(t,f,e,sector,ep,star,secondary_phase=phase)
            record.update(measurement=archive_arrays(measurement,DATA/f'c_models/{cid}.npz'),
                policy_decisions={f'D{d}_E{ee}':C.decide(measurement,d,ee) for d in C.D_GRID for ee in C.E_GRID},
                A_prepared_sha256=sha(prepared),A_ephemeris=eph,B_decision=br.get('decision'),
                diagnostic_only_B_not_pass=br.get('decision')!='PASS',secondary_seed_phase=phase)
        else:raise ValueError('Unknown stage')
        m=record['measurement'];decision=m.get('decision',m.get('gate',m.get('status')))
        record['status']='INPUT_ERROR' if decision in ('ERROR','SKIP','INPUT_ERROR') else 'TIMEOUT' if decision=='TIMEOUT' else 'COMPLETE'
    except Exception as exc:
        record.update(status='INPUT_ERROR',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    record.update(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
        peak_memory_bytes=getattr(psutil.Process().memory_info(),'peak_wset',None),new_network_response_body_bytes=network_bytes)
    http.client.HTTPResponse.read=http_read
    write(out,safe(record));print(stage,cid,record['status'],flush=True)
    if record['status']=='INPUT_ERROR':raise SystemExit(1)

if __name__=='__main__':main(sys.argv[1],sys.argv[2])
