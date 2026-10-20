"""P10.3 v2 acquisition copied with P12 receipts and non-destructive refresh."""
from p12_common import REPO, ROOT, DATA, environment, read, write, sha, utc, redirect_audit_cache
import argparse
import os
import sys
import time
from pathlib import Path

POLICY = 'P12 frozen sector policy; corrupt cached FITS preserved; forced refresh into a new attempt cache'

def allowed_download_rows(result, configuration):
    lo = int(configuration['sector_min']); hi = int(configuration['sector_max'])
    excluded = set(int(s) for s in configuration['qlp_excluded_sectors'])
    indices = []
    for i in range(len(result)):
        mission = str(result.mission[i]); author = str(result.author[i])
        sector = int(mission.split()[-1]) if 'Sector' in mission else -1
        if not lo <= sector <= hi: continue
        if author == 'QLP' and sector in excluded: continue
        indices.append(i)
    return indices


def corrupt_cached_fits(tic, cache_roots):
    from astropy.io import fits
    records=[]
    for root in cache_roots:
        if not Path(root).exists():continue
        for path in Path(root).rglob(f'*{int(tic):016d}*.fits'):
            try:
                with fits.open(path,memmap=False) as handle:
                    data=handle[1].data
                    if not {'TIME','QUALITY'}.issubset(data.names):raise ValueError('Missing TIME or QUALITY')
                    if not {'DET_FLUX','PDCSAP_FLUX','KSPSAP_FLUX','FLUX'} & set(data.names):raise ValueError('Missing flux column')
                    _=data.shape
            except Exception as exc:
                records.append(dict(path=path.relative_to(REPO).as_posix(),bytes=path.stat().st_size,
                    sha256=sha(path),error=f'{type(exc).__name__}: {exc}',preserved=True))
    return records


def validate_store(tic,index,store,cache_roots):
    import numpy as np
    from input_identity_p12 import read_source,compare
    if index.get('n_failed')!=0:raise RuntimeError('Acquisition has failed products')
    sources=[]
    for root in cache_roots:
        if Path(root).exists():
            for path in Path(root).rglob(f'*{int(tic):016d}*.fits'):
                try:sources.append(read_source(path))
                except Exception:continue
    checked=[]
    for metadata in index['products']:
        if 'file' not in metadata:raise RuntimeError('Product missing raw array')
        path=store/f'tic{tic}'/metadata['file']
        with np.load(path,allow_pickle=False) as z:raw={k:z[k] for k in z.files}
        matching=[s for s in sources if s[0]['sector']==metadata['sector'] and s[0]['author']==metadata['author']
            and compare(raw,metadata,s)['all_required_exact']]
        if not matching:raise RuntimeError('Product TIME/flux/quality identity unverified')
        checked.append(dict(raw_path=path.relative_to(REPO).as_posix(),raw_sha256=sha(path),source_sha256=matching[0][0]['sha256']))
    return checked


def _download_one(tic,attempt,force,A,lk):
    start=time.perf_counter();started=utc();cpu=time.process_time()
    configuration=read(ROOT/'protocol/config.json')
    store=REPO/'data/survey/audit_lc';index_path=store/f'tic{tic}/index.json'
    previous_index=sha(index_path) if index_path.exists() else None
    if previous_index:
        write(ROOT/f'results/acquisition_metadata/tic{tic}_a{attempt}_old_index.json',read(index_path))
    roots=[REPO/'data/cache/audit_lightkurve',DATA/'lightkurve']
    corrupt=corrupt_cached_fits(tic,roots)
    force=bool(force or corrupt or (index_path.exists() and read(index_path).get('n_failed',0)))
    # The old FITS bytes remain in place; a fresh per-attempt cache defeats corrupt cache reuse.
    cache=DATA/f'lightkurve/acquisition/tic{tic}/attempt{attempt}'
    cache.mkdir(parents=True,exist_ok=True);A.AUDIT_CACHE=cache
    os.environ['LIGHTKURVE_CACHE']=str(cache);A.LC_DIR=store
    search=lk.search_lightcurve;calls=0
    def frozen_search(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls>1:raise RuntimeError('More than one lightcurve search for a star')
        result=search(*args,**kwargs)
        destination=ROOT/f'results/acquisition_metadata/tic{tic}_a{attempt}.csv'
        destination.parent.mkdir(parents=True,exist_ok=True)
        result.table.write(destination,format='ascii.csv',overwrite=False)
        return result[allowed_download_rows(result,configuration)]
    lk.search_lightcurve=frozen_search
    try:
        idx=A.download(tic,force=force,sector_min=int(configuration['sector_min']))
        checked=validate_store(tic,idx,store,roots)
        result=dict(tic_id=tic,n_products=idx['n_products'],n_failed=idx['n_failed'],
            bytes=sum((store/f'tic{tic}'/p['file']).stat().st_size for p in idx['products']),
            ok=True,status='COMPLETE',identity_checks=checked,index_sha256=sha(index_path))
    except Exception as exc:
        result=dict(tic_id=tic,ok=False,status='OPERATIONAL_UNKNOWN',error=f'{type(exc).__name__}: {exc}'[:500])
    finally:lk.search_lightcurve=search
    result.update(started_utc=started,completed_utc=utc(),wall_seconds=time.perf_counter()-start,
        cpu_seconds=time.process_time()-cpu,search_lightcurve_calls=calls,attempt=attempt,force=force,
        corrupt_cached_fits_preserved=corrupt,previous_index_sha256=previous_index,source_sha256=sha(__file__),
        policy=POLICY,sector_min=int(configuration['sector_min']),cache_path=cache.relative_to(REPO).as_posix())
    write(ROOT/f'results/download/tic{tic}_a{attempt}.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('tic',type=int);parser.add_argument('attempt',type=int,nargs='?',default=1)
    parser.add_argument('--force',action='store_true');parser.add_argument('--online',action='store_true');args=parser.parse_args(argv)
    if not args.online:raise RuntimeError('Acquisition requires explicit --online execution')
    if args.attempt not in (1,2):raise ValueError('Unregistered acquisition attempt')
    environment(offline=False)
    sys.path.insert(0,str(REPO/'scripts'))
    import audit_p5 as A
    redirect_audit_cache(A)
    import lightkurve as lk
    result=_download_one(args.tic,args.attempt,args.force,A,lk)
    print('acquisition',result['status'],flush=True)
    return 0 if result['ok'] else 2


if __name__=='__main__':raise SystemExit(main())
