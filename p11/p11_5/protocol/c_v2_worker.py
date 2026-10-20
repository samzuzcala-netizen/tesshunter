"""Blind corrected C measurement from hash-bound, completed A/S/B evidence.

The original C worker and measurements remain immutable. This stage records a
new attempt and never substitutes its new implementation into an old cache key.
"""
from common import *
environment()
import sys,time,traceback
import numpy as np
import psutil
from funnel_worker import setup,safe,archive_arrays,A

def validate_handoff(handoff):
    allowed={'candidate_id','runtime_path','runtime_sha256','stage_hashes',
             'prepared_path','prepared_sha256','prep_metadata_path','prep_metadata_sha256',
             'source_hashes','correction_registration_sha256'}
    if set(handoff)!=allowed:raise ValueError('Unexpected corrected-C handoff fields')
    for path,expected in handoff['source_hashes'].items():
        if sha(REPO/path)!=expected:raise ValueError('Corrected C source changed: '+path)
    if sha(ROOT/'manifests/C_v2_correctness_registration.json')!=handoff['correction_registration_sha256']:
        raise ValueError('Correctness registration changed')
    for key in ('runtime','prepared','prep_metadata'):
        if sha(REPO/handoff[key+'_path'])!=handoff[key+'_sha256']:
            raise ValueError('Corrected C input changed: '+key)
    cid=handoff['candidate_id']
    if set(handoff['stage_hashes'])!={'A','S','B'}:raise ValueError('Missing predecessor identity')
    for stage,expected in handoff['stage_hashes'].items():
        if sha(ROOT/f'results/funnel/{stage}/{cid}.json')!=expected:
            raise ValueError('Predecessor measurement changed: '+stage)
    runtime=read(REPO/handoff['runtime_path'])
    if runtime['candidate_id']!=cid:raise ValueError('Candidate identity changed')
    return runtime

def main(path):
    from tesshunter import p11_5_clocal_v2 as C
    start=time.perf_counter();cpu=time.process_time();handoff=read(path)
    cid=handoff['candidate_id'];out=ROOT/f'results/funnel/C_v2/{cid}.json'
    if out.exists():raise FileExistsError(out)
    record=dict(candidate_id=cid,stage='C_v2',truth_opened=False,implementation=C.VERSION,
                handoff_path=Path(path).as_posix(),handoff_sha256=sha(path),
                source_hashes=handoff['source_hashes'],previous_attempts_preserved=True)
    try:
        runtime=validate_handoff(handoff);root,job=setup(runtime)
        record.update(series_id=runtime['series_id'],tic_id=runtime['tic_id'],
            input_key=runtime['input_key'],raw_index_sha256=runtime['raw_index_sha256'],
            runtime_manifest_sha256=handoff['runtime_sha256'],stage_hashes=handoff['stage_hashes'],
            engineering_label=runtime.get('engineering_label'))
        predecessors={s:read(ROOT/f'results/funnel/{s}/{cid}.json') for s in ('A','S','B')}
        ar=predecessors['A'].get('measurement',{})
        if predecessors['A']['status']!='COMPLETE' or not (ar.get('decision')=='PASS' or
                runtime.get('engineering_label') and ar.get('chosen_ephemeris')):
            raise ValueError('C requires measured A passer or labelled engineering ephemeris')
        eph=ar['per_ephemeris'][ar['chosen_ephemeris']]['ephemeris']
        prepared=REPO/handoff['prepared_path'];meta=read(REPO/handoff['prep_metadata_path'])
        expected=root/f"tls/{A.key(job['tic_id'],job['period'])}_lc.npz"
        if prepared.resolve()!=expected.resolve():raise ValueError('Prepared file is not this candidate A input')
        with np.load(prepared,allow_pickle=False) as z:
            t,f,e=z['time'],z['flux'],z['flux_err'];tu,fu,su=z['time_unbinned'],z['flux_unbinned'],z['sector_unbinned']
            index=np.searchsorted(tu,t)
            if np.any(index>=len(tu)) or not np.array_equal(tu[index],t) or not np.array_equal(fu[index],f):
                raise ValueError('Corrected C native A array/sector mismatch')
            sector=su[index]
        secondary=predecessors['S'].get('measurement',{}).get('secondary',{})
        seed=secondary.get('deepest_secondary_in_sap') or next(iter(secondary.get('secondaries',[])),{})
        phase=seed.get('phase') if isinstance(seed,dict) else None
        ep=dict(period_days=eph['period'],epoch_btjd=eph['t0'],duration_days=eph['duration'],
                depth_ppt=job['depth_ppt'],candidate_id=cid)
        star=dict(radius_rsun=meta['R_star'],mass_msun=meta['M_star'],teff_k=runtime['star'].get('teff_k'))
        measurement=C.measure(t,f,e,sector,ep,star,secondary_phase=phase)
        br=predecessors['B'].get('measurement',{})
        record.update(measurement=archive_arrays(measurement,DATA/f'c_models_v2/{cid}.npz'),
            policy_decisions={f'D{d}_E{ee}':C.decide(measurement,d,ee) for d in C.D_GRID for ee in C.E_GRID},
            A_prepared_sha256=sha(prepared),A_ephemeris=eph,B_decision=br.get('decision'),
            diagnostic_only_B_not_pass=br.get('decision')!='PASS',secondary_seed_phase=phase,
            correction_registration_sha256=handoff['correction_registration_sha256'])
        decision=measurement.get('status')
        record['status']='INPUT_ERROR' if decision in ('ERROR','INPUT_ERROR','SKIP') else 'TIMEOUT' if decision=='TIMEOUT' else 'COMPLETE'
    except Exception as exc:
        record.update(status='INPUT_ERROR',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    record.update(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
        peak_memory_bytes=getattr(psutil.Process().memory_info(),'peak_wset',None),new_network_response_body_bytes=0)
    write(out,safe(record));print('C_v2',cid,record['status'],flush=True)
    if record['status']=='INPUT_ERROR':raise SystemExit(1)

if __name__=='__main__':main(sys.argv[1])
