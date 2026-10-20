import common as C
import pandas as pd,numpy as np,shutil
# Remove only stale per-window arrays emitted by this new analysis before the
# detector-identity correction. No historical path is eligible.
d=pd.read_csv(C.WS/'results/depths.csv');keep=set()
for r in d[d.valid].itertuples():keep.add(f'window_{r.ephemeris}_s{r.sector}_n{r.cycle}_{r.photometry}.npz')
removed=[]
for p in (C.WS/'results').glob('window_*.npz'):
    assert p.resolve().is_relative_to((C.WS/'results').resolve())
    if p.name not in keep:removed.append(p.name);p.unlink()
C.write(C.WS/'logs/stale_window_cleanup.json',removed)
# Data integrity: compare exact hashes, sizes, and modification timestamps.
before=C.json.loads((C.WS/'inputs/integrity_before.json').read_text());after={};changed=[];missing=[]
for key,b in before.items():
    p=C.Path(key)
    if not p.exists():missing.append(key);continue
    a=C.fingerprint(p);after[key]=a
    if any(a[k]!=b[k] for k in ['sha256','size','mtime_ns']):changed.append(key)
C.write(C.WS/'inputs/integrity_after.json',after)
C.write(C.WS/'inputs/integrity_compare.json',dict(scope='Every historical P1–P12/localisation-v1 file whose content this run read, including all Python files content-scanned for K9; not a whole-repository integrity audit. Installed package files are represented by versions, not this historical manifest. The user prompt is fingerprinted after its initial read; it is not a historical analysis record.',n_files=len(before),changed=changed,missing=missing,checked_utc=C.datetime.datetime.now(C.datetime.timezone.utc).isoformat()))
assert not changed and not missing
shutil.copyfile(C.WS/'code/test_analysis.py',C.WS/'tests/test_analysis.py')
figures=[]
for p in sorted((C.WS/'figures').glob('*.png')):
    figures.append(dict(file=p.name,sha256=C.sha(p),checked='visually inspected: sign, BTJD-relative axes, EA/EF alignment, masks, units, legends, no title clipping; error-bar extents expanded after first review'))
C.write(C.WS/'results/figure_review.json',dict(figures=figures,notes='Aperture identity image revealed off-science-array sectors 25/40/50/52; verified against FITS CCD geometry and corrected. Negative plotted flux residual corresponds to positive tabulated depth. E39 gap displayed rather than interpolated. Per-bin bars are within-bin SEM, while title errors are empirically calibrated.'))
net=C.json.loads((C.WS/'inputs/network_ledger.json').read_text());downloads=C.json.loads((C.WS/'inputs/download_bytes.json').read_text())
C.write(C.WS/'results/resource_usage.json',dict(start_utc=C.datetime.datetime.fromtimestamp(C.START,C.datetime.timezone.utc).isoformat(),checked_utc=C.datetime.datetime.now(C.datetime.timezone.utc).isoformat(),wall_minutes=(C.time.time()-C.START)/60,download_received_bytes=downloads['received_bytes'],download_ceiling_bytes=C.LIMIT,network_attempts=len(net),transport_retries=sum(r['attempt']>0 for r in net),MAST_observation_searches=1,aggregate_product_list_requests=1,workers_per_analysis_process=1,peak_simultaneous_python_processes=2,numerical_threads_per_process=1,peak_two_reason='bounded alias computation overlapped brief input/QA scripts; no multiprocessing or detached jobs',new_D_directory_bytes=sum(p.stat().st_size for p in C.BIG.rglob('*') if p.is_file())))
print('Integrity',len(before),'files;',len(changed),'changed;',len(missing),'missing; stale arrays removed',len(removed))
