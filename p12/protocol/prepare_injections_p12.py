"""Evaluator-side P11.5 preparation copy, using the P10 harmonise-before-inject order."""
from p12_common import REPO,ROOT,DATA,environment,read,write,sha,utc
environment()
import argparse
import csv
import sys
import time
import re
import numpy as np
sys.path.insert(0,str(REPO/'src'))
from tesshunter import survey,survey_p8
from policy_products_p12 import load_policy_products


def save_native(path,lc,prov):
    if path.exists():raise FileExistsError(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,time=lc.time.value,flux=lc.flux.value,flux_err=lc.flux_err.value,
        sector=lc.meta['TESSHUNTER_SECTOR'])
    write(path.with_suffix('.json'),prov)


def injection_parameters(products,row):
    # Copied from survey_p8.get_prepared; same defaults and absolute-epoch calculation.
    star=row.get('star') or row
    period=float(row['period']);t_all=np.concatenate([p['time'][np.isfinite(p['time'])] for p in products])
    t0=float(row['t0']) if row.get('t0') not in (None,'') else float(t_all.min())+float(row.get('t0_frac',.5))*period
    radius=float(star.get('radius_rsun') or 1.0);mass=float(star.get('mass_msun') or radius)
    a_rs=float(row.get('a_rs') or survey.a_over_rs(period,mass,radius))
    u=(float(row['u1']),float(row['u2'])) if row.get('u1') not in (None,'') else survey.limb_darkening_for_teff(star.get('teff_k'))
    return dict(period=period,t0=t0,rp_rs=float(row['rp_rs']),b=float(row['b']),a_rs=a_rs,u=u)


def prepare_arrays(tic,row,arm='archival'):
    products=load_policy_products(tic,arm);cfg=survey.get_config('survey_p10')
    products,notes=survey_p8.harmonise_cadence(products,cfg.target_cadence_minutes)
    if not products:raise RuntimeError('No policy products after cadence harmonisation')
    injected,info=survey_p8.inject_products(products,**injection_parameters(products,row))
    lc,prov=survey_p8.build_prepared(tic,cfg,injected,info,notes)
    return lc,prov,injected,info


def prepare_one(tic,row,arm='archival'):
    if arm not in ('archival','sml'):raise ValueError('Unknown photometry arm')
    start=time.perf_counter();cpu=time.process_time();tic=int(tic)
    if int(row.get('tic_id',tic))!=tic:raise RuntimeError('Injection host identity mismatch')
    job_id=row['job_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+',job_id):raise RuntimeError('Unsafe injection job identity')
    host=read(ROOT/f'results/native_noise/{arm}/tic{tic}.json')
    if host['status']!='INPUT_ELIGIBLE':raise RuntimeError('Injection host is input-ineligible')
    if sha(REPO/host['prepared_path'])!=host['prepared_sha256']:raise RuntimeError('Uninjected input changed')
    cfg=survey.get_config('survey_p10');lc,prov,injected,info=prepare_arrays(tic,row,arm)
    root=DATA/f'calibration/{arm}';path=root/f'prepared/{job_id}.npz';save_native(path,lc,prov)
    raw_root=root/f'injected_raw/{job_id}';raw_root.mkdir(parents=True,exist_ok=True);raw_records=[]
    for index,product in enumerate(injected):
        raw_path=raw_root/f'product_{index:03d}.npz'
        arrays={k:v for k,v in product.items() if isinstance(v,np.ndarray)}
        metadata={k:v for k,v in product.items() if not isinstance(v,np.ndarray)}
        if raw_path.exists():raise FileExistsError(raw_path)
        np.savez_compressed(raw_path,**arrays)
        raw_records.append(dict(metadata=metadata,raw_path=raw_path.relative_to(REPO).as_posix(),raw_sha256=sha(raw_path)))
    write(raw_root/'index.json',dict(tic_id=tic,job_id=job_id,products=raw_records))
    truth=root/f'truth/{job_id}.json'
    write(truth,dict(tic_id=tic,job_id=job_id,injection=row,injection_model=info))
    receipt=dict(utc=utc(),tic_id=tic,job_id=job_id,arm=arm,status='COMPLETE',
        prepared_path=path.relative_to(REPO).as_posix(),prepared_sha256=sha(path),
        provenance_sha256=sha(path.with_suffix('.json')),ingest_key=cfg.ingest_key(),
        uninjected_path=host['prepared_path'],uninjected_sha256=host['prepared_sha256'],
        raw_index_path=(raw_root/'index.json').relative_to(REPO).as_posix(),raw_index_sha256=sha(raw_root/'index.json'),
        truth_path=truth.relative_to(REPO).as_posix(),truth_sha256=sha(truth),
        wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,source_sha256=sha(__file__))
    write(ROOT/f'results/preparation/{arm}/{job_id}.json',receipt)
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=('archival','sml'),default='archival')
    parser.add_argument('--spec',required=True);parser.add_argument('--job-id',required=True);args=parser.parse_args(argv)
    with open(args.spec,newline='',encoding='utf-8-sig') as stream:rows=[r for r in csv.DictReader(stream) if r['job_id']==args.job_id]
    if len(rows)!=1:raise RuntimeError('Injection job is absent or duplicated')
    prepare_one(int(rows[0]['tic_id']),rows[0],args.arm);print('injection prepared',flush=True);return 0


if __name__=='__main__':main()
