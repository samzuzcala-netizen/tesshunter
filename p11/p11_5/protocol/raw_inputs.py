"""Evaluator-only injection into both raw flux streams before adaptive work."""
from common import *
environment()
import sys,time,shutil
import numpy as np
sys.path.insert(0,str(REPO/'src'))
from tesshunter import survey_p8

def one(tic):
    started=time.perf_counter();cpu=time.process_time()
    rows=[r for r in read(ROOT/'manifests/injections_evaluator.json') if r['tic_id']==tic]
    base=read(DATA/f'raw/tic{tic}/index.json')
    products=survey_p8.load_audit_products(tic,DATA/'raw',sector_min=56,sector_max=105)
    outputs=[]
    for row in rows:
        jid=row['job_id'];model=row['fixed_absolute_model']
        target=DATA/f'injected_raw/{jid}/tic{tic}';target.mkdir(parents=True,exist_ok=False)
        if shutil.disk_usage(REPO).free<32000000000:raise RuntimeError('Raw preparation headroom')
        injected,_=survey_p8.inject_products(products,period=float(model['period']),t0=float(model['t0']),
            rp_rs=float(model['rp_rs']),b=float(model['b']),a_rs=float(model['a_rs']),u=(float(model['u1']),float(model['u2'])))
        index=[]
        for k,p in enumerate(injected):
            dest=target/f'product{k:03d}.npz'
            np.savez_compressed(dest,**{v:p[v] for v in ('time','flux','flux_err','sap_flux','sap_flux_err','sap_bkg','quality')})
            meta=next(m for m in base['products'] if int(m['sector'])==int(p['sector']))
            index.append(dict(meta,file=str(dest),sha256=sha(dest),original_file=meta['file']))
        write(target/'index.json',dict(tic_id=tic,products=index,source_index_sha256=sha(DATA/f'raw/tic{tic}/index.json'),
            input_identity=jid,truth_fields_present=False))
        outputs.append(dict(job_id=jid,root=target.parent.relative_to(REPO).as_posix(),index_sha256=sha(target/'index.json')))
    write(ROOT/f'results/raw_inputs/tic{tic}.json',dict(tic_id=tic,status='COMPLETE',rows=outputs,
        wall_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu))
    print('raw handoff complete',tic,flush=True)

if __name__=='__main__':one(int(sys.argv[1]))
