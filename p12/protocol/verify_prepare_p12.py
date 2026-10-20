"""Part D: source identity followed by unchanged native P10 preparation and noise."""
from p12_common import REPO,ROOT,DATA,environment,read,write,sha,utc
environment()
import sys,time
import numpy as np
sys.path.insert(0,str(REPO/'src'))
from tesshunter import survey,survey_p8
from tesshunter.audit_prep import product_bitmask
from input_identity_p12 import read_source,compare,timing_status,choose_verified
import policy_products_p12


def main(tic,arm='archival'):
    if arm not in ('archival','sml'):raise ValueError('Unknown photometry arm')
    start=time.perf_counter();cpu=time.process_time();config=read(ROOT/'protocol/config.json')
    job=read(ROOT/f'manifests/input_jobs/tic{tic}.json')
    rawdir=REPO/f'data/survey/audit_lc/tic{tic}'
    if job['index_sha256'] is None and not (rawdir/'index.json').exists():
        result=dict(tic_id=tic,utc=utc(),status='INPUT_INELIGIBLE',reason='acquisition index absent',usable_sectors=[],n_cad=0,sigma=None)
        write(ROOT/f'results/native_noise/{arm}/tic{tic}.json',result)
        return result
    if sha(rawdir/'index.json')!=job['index_sha256']:raise RuntimeError('Acquisition index changed')
    for name,digest in job.get('source_hashes',{}).items():
        if sha(REPO/name)!=digest:raise RuntimeError('Frozen FITS source changed')
    idx=read(rawdir/'index.json');sources=[];errors=[]
    for name in job['source_paths']:
        try:sources.append(read_source(REPO/name))
        except Exception as exc:errors.append(dict(path=name,error=f'{type(exc).__name__}: {exc}'))
    records=[]
    for p in idx['products']:
        if 'file' not in p:
            records.append(dict(metadata=p,timing_status='ACQUISITION_FAILURE',n_quality_good=0));continue
        path=rawdir/p['file']
        with np.load(path,allow_pickle=False) as z:raw={k:np.asarray(z[k]) for k in z.files}
        comparisons=[]
        for source in sources:
            if source[0]['sector']==p['sector'] and source[0]['author']==p['author']:
                comparisons.append((source,compare(raw,p,source)))
        exact=[pair for pair in comparisons if pair[1]['all_required_exact']]
        exact.sort(key=lambda pair:(str(pair[0][0]['version']) not in ('02','2','2.0'),pair[0][0]['path']))
        matched,checks=exact[0] if exact else (None,dict(all_required_exact=False))
        source=matched[0] if matched else None
        mask=product_bitmask(p)
        good=np.isfinite(raw['time'])&np.isfinite(raw['flux'])&(raw['flux']>0)&((raw['quality']&mask)==0)
        records.append(dict(metadata=p,raw_path=path.relative_to(REPO).as_posix(),raw_sha256=sha(path),
            source=source,comparison=checks,available_source_checks=[dict(source=s[0],comparison=c) for s,c in comparisons],
            timing_status=timing_status(p,source,checks,config),quality_mask=int(mask),n_quality_good=int(good.sum())))
    selected=choose_verified(records,config)
    identity=dict(tic_id=tic,utc=utc(),index_sha256=job['index_sha256'],records=records,source_read_errors=errors,
        selected_sectors=[r['metadata']['sector'] for r in selected],notice_snapshot_sha256=job['notice_snapshot_sha256'])
    identity_path=ROOT/f'manifests/input_identity/tic{tic}.json'
    if arm=='archival':write(identity_path,identity)
    else:
        old=read(identity_path)
        for key in ('index_sha256','selected_sectors','notice_snapshot_sha256','records'):
            if old[key]!=identity[key]:raise RuntimeError('SML input identity differs from archival')
    result=dict(tic_id=tic,utc=utc(),status='INPUT_INELIGIBLE',n_products=idx['n_products'],n_verified_products=sum(r['timing_status'] in ('SOURCE_VERIFIED','CORRECTED_V02_SOURCE_VERIFIED') for r in records),
                verified_selected_sectors=identity['selected_sectors'],usable_sectors=[],n_cad=0,sigma=None,
                identity_record_sha256=sha(identity_path))
    if selected:
        products=policy_products_p12.load_policy_products(tic,arm)
        cfg=survey.get_config('survey_p10')
        if cfg.ingest_key()!=survey.get_config('survey_p8').ingest_key():raise RuntimeError('Paired ingestion keys differ')
        harmonised,notes=survey_p8.harmonise_cadence(products,cfg.target_cadence_minutes)
        lc,prov=survey_p8.build_prepared(tic,cfg,harmonised,cadence_notes=notes)
        t=np.asarray(lc.time.value);f=np.asarray(lc.flux.value);e=np.asarray(lc.flux_err.value);sectors=np.asarray(lc.meta['TESSHUNTER_SECTOR'])
        counts={str(int(s)):int((sectors==s).sum()) for s in np.unique(sectors)}
        usable=[int(s) for s,n in counts.items() if n>=50]
        ok=np.isfinite(f)
        sigma=float(1.4826*np.median(np.abs(f[ok]-np.median(f[ok])))) if ok.any() else None
        native=DATA/f'prepared/{arm}/tic{tic}/native200.npz';native.parent.mkdir(parents=True,exist_ok=True)
        if native.exists():raise FileExistsError(native)
        np.savez_compressed(native,time=t,flux=f,flux_err=e,sector=sectors)
        write(native.with_suffix('.json'),prov)
        result.update(status='INPUT_ELIGIBLE' if len(usable)>=3 and ok.sum()>=100 and sigma and np.isfinite(sigma) and sigma>0 else 'INPUT_INELIGIBLE',
            usable_sectors=sorted(usable),sector_points=counts,n_cad=int(ok.sum()),sigma=sigma if sigma is None or np.isfinite(sigma) else None,
            cadence_days=float(np.median(np.diff(np.sort(t[ok])))) if ok.sum()>1 else None,
            span_days=float(np.ptp(t[ok])) if ok.any() else 0.,midpoint_btjd=float((t[ok].min()+t[ok].max())/2) if ok.any() else None,
            prepared_path=native.relative_to(REPO).as_posix(),prepared_sha256=sha(native),provenance_sha256=sha(native.with_suffix('.json')),
            ingest_key=cfg.ingest_key(),rotation_proxy=prov.get('rotation_proxy'),prepare_counters=prov['counters'])
    result.update(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,source_sha256=sha(__file__))
    write(ROOT/f'results/native_noise/{arm}/tic{tic}.json',result)
    print('verified/prepared',tic,result['status'],len(result['usable_sectors']),result['n_cad'],flush=True)
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('tic',type=int);parser.add_argument('--arm',choices=('archival','sml'),default='archival')
    args=parser.parse_args();main(args.tic,args.arm)
