import common as C
import shutil,zipfile
OUT=C.LOCAL/'outputs/tic332366289_lightcurve_v1'
OUT.mkdir(parents=True,exist_ok=True)
allowed=['LIGHTCURVE_REPORT.md','PLAN.md','config.json','events.csv']
files=[C.WS/n for n in allowed]
for name in ['code','tests','inputs','results','figures','logs']:
    files.extend(p for p in (C.WS/name).rglob('*') if p.is_file() and p.suffix not in ['.pyc','.fits','.zip'] and '__pycache__' not in p.parts)
for src in files:
    rel=src.relative_to(C.WS);dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
manifest=[dict(path=str(p.relative_to(C.WS)).replace('\\','/'),size=p.stat().st_size,sha256=C.sha(p)) for p in files]
C.write(C.WS/'bundle_manifest.json',manifest);shutil.copyfile(C.WS/'bundle_manifest.json',OUT/'bundle_manifest.json')
bundle=C.WS/'review_bundle.zip'
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,str(p.relative_to(C.WS)))
    z.write(C.WS/'bundle_manifest.json','bundle_manifest.json')
with zipfile.ZipFile(bundle) as z:
    assert z.testzip() is None
    for r in manifest:
        assert C.hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
shutil.copyfile(bundle,OUT/'review_bundle.zip')
C.write(OUT/'delivery_verification.json',dict(bundle_sha256=C.sha(bundle),bundle_size=bundle.stat().st_size,n_files=len(files),manifest_checked=True,raw_cubes_or_caches_included=False,canonical_workspace=str(C.WS),large_data=str(C.BIG)))
print('DELIVERED',str(OUT),'files',len(files),'zip bytes',bundle.stat().st_size,'sha256',C.sha(bundle))
