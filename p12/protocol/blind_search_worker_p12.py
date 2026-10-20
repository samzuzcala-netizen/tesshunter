"""One unchanged preset search on a frozen native input, with traces and I/O guard."""
from p12_common import REPO,ROOT,DATA,environment,read,write,sha,utc
environment()
import sys,time,logging
from blind_io_p12 import install,summary
from pathlib import Path
import re


def safe(value):
    import numpy as np
    import math
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [safe(v) for v in value]
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def main(runtime_path,expected_runtime_sha256):
    # Install before scientific imports and before reading the runtime manifest.
    runtime_path=__import__('pathlib').Path(runtime_path)
    if not runtime_path.is_absolute():runtime_path=REPO/runtime_path
    label=runtime_path.stem
    guard=install(ROOT/f'results/search_io/{label}.jsonl',REPO/'data/cache/catalogs/spoc_tce/spoc_tce.ephemerides.csv')
    if sha(runtime_path)!=expected_runtime_sha256:raise RuntimeError('Runtime manifest differs from the frozen controller job')
    import numpy as np
    sys.path.insert(0,str(REPO/'src'))
    from tesshunter import survey,survey_p8
    runtime=read(runtime_path)
    allowed={'tic_id','preset','job_id','star','prepared_path','prepared_sha256','provenance_sha256','ingest_key','source_hashes','run'}
    if set(runtime)!=allowed:raise RuntimeError('Unregistered/non-runtime search fields')
    if not runtime['source_hashes']:raise RuntimeError('Missing frozen search sources')
    for name,digest in runtime['source_hashes'].items():
        if sha(REPO/name)!=digest:raise RuntimeError('Search source changed: '+name)
    tic=int(runtime['tic_id']);preset=runtime['preset']
    if preset!='survey_p10':raise RuntimeError('Unregistered preset')
    job_id=runtime['job_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+',job_id):raise RuntimeError('Unsafe search job identity')
    cfg=survey.get_config(preset,record_traces=True)
    path=REPO/runtime['prepared_path']
    if sha(path)!=runtime['prepared_sha256'] or sha(path.with_suffix('.json'))!=runtime['provenance_sha256']:raise RuntimeError('Frozen prepared input changed')
    if cfg.ingest_key()!=runtime['ingest_key']:raise RuntimeError('Paired ingestion identity changed')
    lc,prov=survey.load_stitched(path)
    with np.load(path,allow_pickle=False) as z:lc.meta['TESSHUNTER_SECTOR']=z['sector']
    if prov['ingest_key']!=cfg.ingest_key():raise RuntimeError('Prepared provenance ingestion mismatch')
    previous=survey_p8.get_prepared
    def frozen(*args,**kwargs):
        if int(args[0])!=tic or args[1].ingest_key()!=runtime['ingest_key']:raise RuntimeError('Unexpected prepared input request')
        return lc,prov,dict(cache_hit=True,path=str(path),load_s=0.,download_s=0.,stitch_s=0.)
    run=REPO/runtime['run']
    if not run.resolve().is_relative_to(DATA.resolve()):raise RuntimeError('Search run outside P12 DATA')
    result_path=run/f'results/{job_id}.json'
    if result_path.exists():raise FileExistsError(result_path)
    trace=run/f'traces/{job_id}.jsonl';trace.parent.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(name)s %(levelname)s %(message)s')
    started=utc();timer=time.perf_counter();cpu=time.process_time()
    survey_p8.get_prepared=frozen
    try:
        result=survey.run_job(dict(job_id=job_id,tic_id=tic,star=runtime['star'],config=preset,
                                   overrides={'record_traces':True},trace_path=str(trace)),allow_download=False)
    finally:survey_p8.get_prepared=previous
    io=summary(guard)
    if io['sidecar_open_attempts']:raise RuntimeError('STOP-4: sidecar access attempted')
    write(result_path,safe(result))
    planets=(result.get('result') or {}).get('planets') or []
    pregate=sum((p.get('stitch_snr') or 0)>=7.1 and (p.get('stitch_n_transits') or 0)>=3 and bool(p.get('stitch_epoch_consistent')) for p in planets)
    receipt=dict(tic_id=tic,preset=preset,job_id=job_id,run=runtime['run'],status='COMPLETE' if result['status']=='ok' else 'OPERATIONAL_UNKNOWN',
        started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-timer,cpu_seconds=time.process_time()-cpu,
        n_cad=len(lc),n_units=len(prov['units_used']),n_accepted=len(planets),n_pre_gate=pregate,
        budget_exhausted_partitions=sum(bool(s.get('budget_exhausted')) for s in result.get('searches',[])),
        result_path=result_path.relative_to(REPO).as_posix(),result_sha256=sha(result_path),
        trace_path=trace.relative_to(REPO).as_posix(),trace_sha256=sha(trace) if trace.exists() else None,
        prepared_path=runtime['prepared_path'],prepared_sha256=runtime['prepared_sha256'],ingest_key=runtime['ingest_key'],
        runtime_manifest_path=runtime_path.relative_to(REPO).as_posix(),runtime_manifest_sha256=sha(runtime_path),
        source_hashes=runtime['source_hashes'],provenance_sha256=runtime['provenance_sha256'],
        file_access_log=f'p12/results/search_io/{label}.jsonl',io=io)
    receipt_path=ROOT/'results/search_receipts'/run.relative_to(DATA)/f'{job_id}.json'
    write(receipt_path,safe(receipt))
    print('search',preset,tic,receipt['status'],'seconds',round(receipt['wall_seconds'],2),flush=True)
    if receipt['status']!='COMPLETE':raise SystemExit(2)
    return receipt


if __name__=='__main__':main(sys.argv[1],sys.argv[2])
