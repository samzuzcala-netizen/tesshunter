"""Blind shared R0/R1 trajectory on frozen prepared arrays, no truth access."""
from common import *
environment()
import copy
import logging
import sys
import time
import numpy as np
import psutil
sys.path.insert(0,str(REPO/'src'))
from tesshunter import survey,survey_p8
from tesshunter.p11_5_search import PoolRecorder,capture_pools,replay,confirm_extras,array_key

def safe(x):
    if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [safe(v) for v in x]
    if isinstance(x,np.generic):return safe(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x

def main(path):
    job=read(path)
    if set(job)-{'job_id','tic_id','star','prepared_path','prepared_sha256','array_key','source_hashes'}:
        raise ValueError('Non-runtime field in blinded job')
    for name,expected in job['source_hashes'].items():
        if sha(REPO/name)!=expected:raise ValueError('Worker source identity changed')
    out=ROOT/f'results/search/{job["job_id"]}.json'
    if out.exists():raise FileExistsError(out)
    prepared=REPO/job['prepared_path']
    if sha(prepared)!=job['prepared_sha256']:raise ValueError('Prepared file changed')
    cfg=survey.get_config('survey_p10')
    lc,prov=survey.load_stitched(prepared)
    with np.load(prepared,allow_pickle=False) as z:lc.meta['TESSHUNTER_SECTOR']=z['sector']
    if array_key(lc.time.value,lc.flux.value,lc.flux_err.value,lc.meta['TESSHUNTER_SECTOR'],config=cfg.to_dict())!=job['array_key']:
        raise ValueError('Prepared array identity mismatch')
    recorder=PoolRecorder(DATA/f'search_snapshots/{job["job_id"]}',job['array_key'],digest(cfg.to_dict()))
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(name)s %(levelname)s %(message)s')
    old_get=survey_p8.get_prepared
    def get(*args,**kwargs):
        return lc,prov,dict(cache_hit=True,path=str(prepared),load_s=0.,download_s=0.,stitch_s=0.,
                           meaning='Frozen input handoff; preparation charged separately, not a runtime benchmark')
    start=time.perf_counter();cpu=time.process_time()
    try:
        survey_p8.get_prepared=get
        with capture_pools(recorder):
            ordinary=survey.run_job(dict(job_id=job['job_id'],tic_id=job['tic_id'],star=job['star'],config='survey_p10'),allow_download=False)
    finally:survey_p8.get_prepared=old_get
    ordinary_wall=time.perf_counter()-start-recorder.seconds
    ordinary_cpu=time.process_time()-cpu-recorder.cpu_seconds
    recorder.close()
    if ordinary['status']!='ok':raise RuntimeError(ordinary['error'])
    originals=ordinary['result']['planets'];before=copy.deepcopy(originals)
    extras,truncation=replay(recorder.pools,originals,float(np.ptp(lc.time.value)),job['array_key'],digest(cfg.to_dict()))
    t=time.perf_counter();c=time.process_time()
    confirmation=confirm_extras(lc,extras,cfg)
    extra_wall=time.perf_counter()-t;extra_cpu=time.process_time()-c
    assert originals==before and len(originals)<=24 and len(extras)<=12
    # Every stored snapshot is reconstructed and byte-checked before sealing.
    for pool in recorder.pools:recorder.restore(pool)
    source_hashes=job['source_hashes']
    pools_path=ROOT/f'results/pools/{job["job_id"]}.json'
    write(pools_path,safe(recorder.pools))
    record=dict(job_id=job['job_id'],tic_id=job['tic_id'],status='COMPLETE',input_key=job['array_key'],
        input_sha256=job['prepared_sha256'],config_key=digest(cfg.to_dict()),source_hashes=source_hashes,
        R0=ordinary,R1_extras=extras,truncation=truncation,extra_confirmation=confirmation,
        pools_path=pools_path.relative_to(REPO).as_posix(),pools_sha256=sha(pools_path),
        snapshots={p.relative_to(REPO).as_posix():sha(p) for p in recorder.root.glob('*.npz')},
        timings=dict(ordinary_wall=ordinary_wall,ordinary_cpu=ordinary_cpu,
            observer_wall=recorder.seconds,observer_cpu=recorder.cpu_seconds,
            extra_confirmation_wall=extra_wall,extra_confirmation_cpu=extra_cpu,
            workflow_wall=time.perf_counter()-start,workflow_cpu=time.process_time()-cpu,
            R0_deployable_wall=ordinary_wall,R1_deployable_wall=ordinary_wall+recorder.seconds+extra_wall,
            R0_deployable_cpu=ordinary_cpu,R1_deployable_cpu=ordinary_cpu+recorder.cpu_seconds+extra_cpu),
        peak_memory_bytes=getattr(psutil.Process().memory_info(),'peak_wset',None),truth_opened=False)
    write(out,safe(record))
    print('search complete',job['job_id'],flush=True)

if __name__=='__main__':main(sys.argv[1])
