"""Evaluator-only fixed P10 expected-SNR coordinate on new uninjected arrays."""
from common import *
environment()
import sys,time
import numpy as np
sys.path.insert(0,str(REPO/'src'))
from tesshunter import survey

def one(tic):
    started=time.perf_counter();rows=[r for r in read(ROOT/'manifests/injections_evaluator.json') if r['tic_id']==tic]
    prep=read(ROOT/f'results/preparation/tic{tic}.json');case=next(r for r in prep['cases'] if r['kind']=='natural')
    path=REPO/case['prepared_path']
    if sha(path)!=case['prepared_sha256']:raise ValueError('Uninjected reference changed')
    with np.load(path,allow_pickle=False) as z:t,f=z['time'],z['flux']
    ok=np.isfinite(t)&np.isfinite(f);t,f=t[ok],f[ok]
    sigma=float(1.4826*np.median(abs(f-np.median(f))));cad=float(np.median(np.diff(np.sort(t))))
    measurements=[]
    for r in rows:
        m=r['fixed_absolute_model']
        model=survey.transit_model(t,period=m['period'],t0=m['t0'],rp_rs=m['rp_rs'],b=m['b'],a_rs=m['a_rs'],u=(m['u1'],m['u2']),exp_time_days=cad)
        delta=1-model;inside=delta>0;n=int(inside.sum())
        snr=float(np.sqrt(np.sum(delta[inside]**2))/sigma) if n and sigma>0 else 0.
        measurements.append(dict(job_id=r['job_id'],tic_id=tic,snr_expected=snr,sigma_cadence_ppt=1000*sigma,
            n_in_transit_cadences=n,n_transits_in_prepared=int(len(np.unique(np.round((t[inside]-m['t0'])/m['period'])))),
            reference_cadence_days=cad,depth_max_ppt=float(delta.max())*1000,
            prepared_reference_sha256=case['prepared_sha256'],included_despite_observability=True))
    write(ROOT/f'results/reference_snr/tic{tic}.json',dict(utc=utc(),tic_id=tic,rows=measurements,wall_seconds=time.perf_counter()-started,
        method='Unchanged P10 matched-filter expected SNR on the new common uninjected preparation; original absolute model parameters. No recovery outcome read.'))

if __name__=='__main__':one(int(sys.argv[1]))
