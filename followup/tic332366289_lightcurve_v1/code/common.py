"""Isolated, candidate-only follow-up; no historical writes."""
import os, json, hashlib, time, datetime, math
from pathlib import Path
REPO=Path(r'C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter')
WS=REPO/'followup/tic332366289_lightcurve_v1'
BIG=Path(r'D:\tesshunter_followup\tic332366289_lightcurve_v1')
LOCAL=Path(r'C:\Users\seanj\Documents\Codex\2026-10-01\c-users-seanj-downloads-claude-tic332366289')
for k,v in {'PYTHONDONTWRITEBYTECODE':'1','LIGHTKURVE_CACHE':str(BIG/'cache/lightkurve'),'MPLCONFIGDIR':str(BIG/'cache/matplotlib'),'XDG_CACHE_HOME':str(BIG/'cache'),'XDG_CONFIG_HOME':str(BIG/'config')}.items(): os.environ[k]=v
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMBA_NUM_THREADS']: os.environ[k]='1'
for p in [WS/'inputs',WS/'results',WS/'figures',WS/'logs',WS/'tests',BIG/'downloads',BIG/'arrays',BIG/'cache/astropy',BIG/'config/astropy']: p.mkdir(parents=True,exist_ok=True)
START=1790878320.0 # 2026-10-01 18:12 UTC; includes verification time
LIMIT=5_000_000_000
def check():
    if time.time()-START>3*3600-300: raise RuntimeError('Wall ceiling reserve reached; checkpoint and report')
def clean(x):
    import numpy as np
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)): return [clean(v) for v in x]
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.bool_,)): return bool(x)
    if isinstance(x,(float,np.floating)): return float(x) if math.isfinite(x) else None
    if isinstance(x,Path): return str(x)
    return x
def write(p,x):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(clean(x),indent=2,allow_nan=False),encoding='utf-8')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
def fingerprint(p):
    p=Path(p); s=p.stat()
    return dict(path=str(p),resolved=str(p.resolve()),sha256=sha(p),size=s.st_size,mtime_ns=s.st_mtime_ns)
def historical(p):
    p=Path(p); dest=WS/'inputs/integrity_before.json'
    reg=json.loads(dest.read_text()) if dest.exists() else {}
    key=str(p)
    if key not in reg:
        reg[key]=fingerprint(p); write(dest,reg)
    return p
ACQ=Path(r'D:\tesshunter_data\survey_p12\lightkurve\acquisition\tic332366289\attempt1\mastDownload\HLSP')
TC=Path(r'D:\tesshunter_data\survey_p12\lightkurve\tesscut')
PACKET=REPO/'docs/packets/audit_p12/tic332366289_p02/tic332366289_P18.7481'
EA=(18.748084871649127,2869.8700663100585,0.0928318)
EF=(18.748273038412,2869.852493755,1.93/24)
SECTORS=[24,25,26,40,50,51,52,53,57,77,78,79,80,84]
