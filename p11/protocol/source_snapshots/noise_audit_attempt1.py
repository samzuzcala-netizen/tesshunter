"""Bounded P11 product-noise/depth-retention audit; no search or new candidate outcomes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from common import REPO,P11,DATA,read,write,sha,utc,append_event,science_environment
science_environment()
sys.path.insert(0,str(REPO/"src"))
import numpy as np
import psutil
from astropy.io import fits
from tesshunter import survey_p8
from tesshunter.survey import a_over_rs, limb_darkening_for_teff, transit_model


def mad(x):
    x=np.asarray(x);x=x[np.isfinite(x)]
    return float(1.4826*np.median(abs(x-np.median(x)))) if len(x) else None


def noise(t,f,sector):
    rows=[]
    for s in sorted(set(sector)):
        take=(sector==s)&np.isfinite(t)&np.isfinite(f)
        st,sf=t[take],f[take]
        if len(st)<50:continue
        cadence=float(np.median(np.diff(st)));scatter=mad(sf);scales={}
        for hours in (0.5,1,2,4):
            width=hours/24;idx=np.floor((st-st.min())/width).astype(int)
            counts=np.bincount(idx);means=np.bincount(idx,weights=sf)/np.maximum(counts,1)
            good=counts>=0.5*width/cadence;means=means[good];counts=counts[good]
            value=mad(means) if len(means)>=8 else None
            scales[str(hours)]=dict(n_bins=int(len(means)),median_occupancy=float(np.median(counts)) if len(counts) else None,
                scatter_ppt=1000*value if value is not None else None,
                red_noise_inflation=value/(scatter/np.sqrt(np.median(counts))) if value is not None and scatter and len(counts) else None,
                fraction_beyond_5_mad=float(np.mean(abs(means-np.median(means))>5*value)) if value else None,
                p99_absolute_deviation_ppt=float(1000*np.quantile(abs(means-np.median(means)),0.99)) if len(means) else None)
        rows.append(dict(sector=int(s),n=len(st),point_scatter_ppt=1000*scatter,cadence_seconds=86400*cadence,
                         duty_cycle=min(1.0,len(st)*cadence/(st.max()-st.min()+cadence)),timescales=scales))
    return rows


def paired_depth(t,uninj,injected,shape):
    # The intercept accounts for preparation renormalization. The slope is
    # retention of the known depth shape, not the depth of a selected real event.
    good=np.isfinite(t)&np.isfinite(uninj)&np.isfinite(injected)&np.isfinite(shape)
    t,uninj,injected,shape=t[good],uninj[good],injected[good],shape[good]
    if np.count_nonzero(shape>0)<3 or np.ptp(shape)==0:
        return dict(status="UNMEASURED",reason="Fewer than three common in-transit cadences")
    X=np.column_stack([np.ones(len(t)),shape])
    beta=np.linalg.lstsq(X,uninj-injected,rcond=None)[0]
    return dict(status="MEASURED",retained_depth_fraction=float(beta[1]),renormalization_offset=float(beta[0]),n_common=len(t),n_common_in_transit=int(np.count_nonzero(shape>0)))


def parameters():
    path=P11/"manifests/audit_injections.json"
    if path.exists():return read(path)
    rng=np.random.Generator(np.random.PCG64(2026091201));rows=[]
    for host in read(P11/"manifests/audit_hosts.json"):
        rows.append(dict(tic_id=int(host["tic_id"]),period=5.137,t0_frac=float(rng.uniform()),rp_rs=0.08,b=0.3,
                         a_rs=a_over_rs(5.137,float(host["mass_msun"]),float(host["radius_rsun"])),
                         u=list(limb_darkening_for_teff(float(host["teff_k"])))) )
    value=dict(utc=utc(),seed=2026091201,bit_generator="PCG64",state_after=rng.bit_generator.state,rows=rows,
               source_sha256=sha(__file__),purpose="Input-depth preservation engineering audit; never blind search truth")
    write(path,value);return value


def load_products(tic):
    inventory=read(P11/f"results/input_inventory_v2/tic{tic}.json")
    original=survey_p8.load_audit_products(tic,sector_min=56,sector_max=104)
    selected=[];records={r['raw_path']:r for r in inventory['records'] if 'raw_path' in r}
    for p in original:
        if p['sector'] not in inventory['audited_selected_sectors']:continue
        record=records[f"data/survey/audit_lc/tic{tic}/{p['file']}"]
        p=dict(p,_audit_record=record)
        selected.append(p)
    return inventory,selected


def worker(tic):
    started=utc();timer=time.perf_counter();process=psutil.Process()
    output=P11/f"results/noise/tic{tic}.json"
    if output.exists():raise RuntimeError("Completed timing/result must not be overwritten")
    host=next(r for r in read(P11/"manifests/audit_hosts.json") if int(r["tic_id"])==tic)
    param=next(r for r in read(P11/"manifests/audit_injections.json")["rows"] if r["tic_id"]==tic)
    inv,raw=load_products(tic)
    if not raw:raise RuntimeError("No audited unaffected input product")
    param=dict(param);param['t0']=min(float(np.nanmin(p['time'])) for p in raw)+param.pop('t0_frac')*param['period'];param.pop('tic_id')
    groups={"selected_products":{"corrected":raw,"SAP":[dict(p,flux=p['sap_flux'],flux_err=p['sap_flux_err']) for p in raw]}}
    qlp=[];sml=[];lag=[]
    for p in raw:
        if p['author']!='QLP':continue
        src=p['_audit_record']['source_matches'][0]
        with fits.open(REPO/src['path'],memmap=False) as hd:
            d=hd[1].data
            if not {'DET_FLUX_SML','DET_FLUX_LAG'}.issubset(d.names):continue
            valid=np.isfinite(d['TIME'])
            if len(d)==len(p['time']):valid=np.ones(len(d),dtype=bool)
            qlp.append(p)
            sml.append(dict(p,flux=np.asarray(d['DET_FLUX_SML'][valid],dtype=float),flux_err=np.full(len(p['time']),np.nan)))
            lag.append(dict(p,flux=np.asarray(d['DET_FLUX_LAG'][valid],dtype=float),flux_err=np.full(len(p['time']),np.nan)))
    if qlp:groups['QLP_supplied_apertures']={'corrected':qlp,'small':sml,'large':lag}
    measurements=[];arrays=DATA/f"audit_prepared/tic{tic}";arrays.mkdir(parents=True,exist_ok=True)
    for group,variants in groups.items():
        prepared={}
        for variant,products in variants.items():
            begin=time.perf_counter()
            raw_injected,injinfo=survey_p8.inject_products(products,**param,supersample=7)
            uninj,notes=survey_p8.harmonise_cadence(products,200/60)
            inj,_=survey_p8.harmonise_cadence(raw_injected,200/60)
            baseline=survey_p8.prepare_search_input(uninj,0.75)
            tested=survey_p8.prepare_search_input(inj,0.75)
            common,i,j=np.intersect1d(baseline['time'],tested['time'],return_indices=True)
            shape=1-transit_model(common,**param,exp_time_days=200/86400,supersample=7)
            depth=paired_depth(common,baseline['flux'][i],tested['flux'][j],shape)
            depths_by_sector=[]
            for s in sorted(set(baseline['sector'][i])):
                m=baseline['sector'][i]==s
                depths_by_sector.append(dict(sector=int(s),**paired_depth(common[m],baseline['flux'][i][m],tested['flux'][j][m],shape[m])))
            unshape=1-transit_model(baseline['time'],**param,exp_time_days=200/86400,supersample=7)
            n_original=int(np.count_nonzero(unshape>0))
            depth['common_transit_cadence_fraction']=float(np.count_nonzero(shape>0)/n_original) if n_original else None
            saved=arrays/f"{group}_{variant}.npz"
            np.savez_compressed(saved,time=baseline['time'],flux=baseline['flux'],flux_err=baseline['flux_err'],sector=baseline['sector'],
                                injected_time=tested['time'],injected_flux=tested['flux'],common_time=common,injected_shape=shape)
            rec=dict(group=group,variant=variant,noise=noise(baseline['time'],baseline['flux'],baseline['sector']),
                injected_depth_retention=depth,depth_by_sector=depths_by_sector,
                preparation_counters=baseline['counters'],injected_preparation_counters=tested['counters'],
                raw_injection=injinfo,cadence_notes=notes,wall_seconds=time.perf_counter()-begin,
                arrays_path=saved.relative_to(REPO).as_posix(),arrays_sha256=sha(saved),
                errors="original source errors; supplied small/large apertures without matching errors use P10 robust scatter filling")
            measurements.append(rec);prepared[variant]=baseline
        reference=prepared['corrected']
        for rec in measurements:
            if rec['group']!=group:continue
            value=prepared[rec['variant']];common,i,j=np.intersect1d(reference['time'],value['time'],return_indices=True)
            rec['matched_time_noise']=dict(n_common=len(common),reference=noise(common,reference['flux'][i],reference['sector'][i]),
                alternative=noise(common,value['flux'][j],value['sector'][j]))
    raw_diagnostics=[]
    for p in raw:
        good=np.isfinite(p['flux'])&(p['flux']>0)&((p['quality']&p['_audit_record']['quality_mask'])==0)
        src=p['_audit_record']['source_matches'][0]
        raw_diagnostics.append(dict(sector=p['sector'],author=p['author'],product_era=p['_audit_record']['product_era'],
            raw_fractional_variability_mad_ppt=1000*mad(p['flux'][good]/np.median(p['flux'][good])) if good.any() else None,
            raw_path=p['_audit_record']['raw_path'],raw_sha256=p['_audit_record']['raw_sha256'],
            fits_path=src['path'],fits_sha256=src['sha256'],flux_units=src['columns'].get(p['flux_column'].upper()),
            aperture=src['aperture'],crowding=src['headers'].get('CROWDSAP'),
            total_noise_model=dict(status='UNMEASURED',formula='(N_source + N_sky + n_pixels*n_reads*read_noise_e**2)/N_source**2',
                reason='Source-specific aperture/sky calibration and read-noise inputs are not jointly present in the selected products; no Tmag-only substitution')))
    rss=getattr(process.memory_info(),'peak_wset',process.memory_info().rss)
    result=dict(tic_id=tic,status='OK',started_utc=started,completed_utc=utc(),host=host,
        selected_sectors=inv['audited_selected_sectors'],host_meets_three_sector_rule=inv['meets_three_sector_rule'],
        physical_injection_parameters=param,measurements=measurements,raw_diagnostics=raw_diagnostics,
        wall_seconds=time.perf_counter()-timer,cpu_seconds=sum(process.cpu_times()[:2]),peak_rss_bytes=rss,
        source_sha256=sha(__file__),inventory_sha256=sha(P11/f"results/input_inventory_v2/tic{tic}.json"))
    write(output,result);print(tic,'OK',round(result['wall_seconds'],2),flush=True)


def run_case(tic,deadline):
    output=P11/f"results/noise/tic{tic}.json";output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():return read(output)
    remaining=deadline-time.perf_counter()
    if remaining<=0:
        write(output,dict(tic_id=tic,status='NOT_RUN_BUDGET',utc=utc(),reason='Audit queue deadline reached before launch'))
        return read(output)
    log=P11/f"logs/noise_tic{tic}.log";log.parent.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();started=utc()
    with log.open('x',encoding='utf-8') as stream:
        try:
            completed=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--host',str(tic)],cwd=REPO,stdout=stream,stderr=subprocess.STDOUT,
                                     timeout=min(600,max(1,remaining)))
            code=completed.returncode
        except subprocess.TimeoutExpired:
            code='TIMEOUT'
    if not output.exists():
        write(output,dict(tic_id=tic,status='TIMEOUT' if code=='TIMEOUT' else 'INPUT_ERROR',exit_code=code,
                          started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-start,
                          log_sha256=sha(log),reason='See preserved per-host log; never counted as a measured photometry rejection'))
    print('completed noise host',tic,read(output)['status'],flush=True)
    return read(output)


def run():
    parameters()
    source=sha(__file__);seal=P11/'protocol/noise_audit_seal.json'
    if not seal.exists():write(seal,dict(utc=utc(),source_sha256=source,parameters_sha256=sha(P11/'manifests/audit_injections.json')))
    if read(seal)['source_sha256']!=source:raise RuntimeError('Noise source changed after measurement seal')
    previous=[json.loads(s) for s in (P11/'manifests/queue_intervals.jsonl').read_text().splitlines()]
    spent=sum(r.get('wall_seconds',0) for r in previous if r['event']=='end' and r['phase'].startswith('audit'))
    allowance=max(0,7200-spent);timer=time.perf_counter();started=utc();proc=psutil.Process()
    if allowance<600:raise RuntimeError('Insufficient remaining audit budget for pilot')
    append_event(P11/'manifests/queue_intervals.jsonl',dict(event='start',phase='audit_noise',pid=proc.pid,create_time=proc.create_time(),source_sha256=source))
    ids=[int(r['tic_id']) for r in read(P11/'manifests/audit_hosts.json')]
    deadline=timer+allowance
    first=run_case(ids[0],deadline)
    workers=4 if first.get('status')=='OK' and first.get('peak_rss_bytes',1e12)*4<0.5*psutil.virtual_memory().available else 1
    write(P11/'results/noise/memory_pilot.json',dict(utc=utc(),tic_id=ids[0],pilot_status=first['status'],peak_rss_bytes=first.get('peak_rss_bytes'),selected_workers=workers,BLAS_threads=1,source_sha256=source))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(run_case,tic,deadline):tic for tic in ids[1:]}
        for i,future in enumerate(as_completed(futures),start=2):
            future.result()
            write(P11/'results/noise/progress.json',dict(completed=i,total=60,utc=utc(),wall_seconds=time.perf_counter()-timer,workers=workers))
    append_event(P11/'manifests/queue_intervals.jsonl',dict(event='end',phase='audit_noise',pid=proc.pid,started_utc=started,wall_seconds=time.perf_counter()-timer))
    print('noise audit closed',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--host',type=int);parser.add_argument('--run',action='store_true');args=parser.parse_args()
    worker(args.host) if args.host is not None else run()
