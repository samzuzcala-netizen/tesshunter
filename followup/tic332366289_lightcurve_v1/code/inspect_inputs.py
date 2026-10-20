import common as C
import sys, shutil, importlib.metadata as md, re
from astropy.io import fits
import numpy as np
init=C.LOCAL/'work/initial_integrity.jsonl'
if init.exists():
    shutil.copyfile(init,C.WS/'inputs/initial_integrity.jsonl')
    for line in init.read_text(encoding='utf-8-sig').splitlines():
        row=C.json.loads(line); p=C.historical(row['path'])
        assert C.sha(p).lower()==row['sha256'].lower()
for rel in ['fit.json','stageA.json']:
    p=C.historical(C.PACKET/rel); shutil.copyfile(p,C.WS/'inputs'/('inherited_'+rel))
loc=C.REPO/'followup/tic332366289_localisation_v1'
for rel in ['events.csv','results/controls.csv','code/data.py']:
    p=C.historical(loc/rel); shutil.copyfile(p,C.WS/'inputs'/('localisation_'+p.name))
# Each source file is fingerprinted BEFORE content search, even if no match.
hits=[]
for root in [C.REPO/'p12/protocol',C.REPO/'src']:
    for p in root.rglob('*.py'):
        text=C.historical(p).read_text(encoding='utf-8',errors='replace')
        lines=text.splitlines()
        idx=[i for i,l in enumerate(lines) if re.search(r'K9a|k9a|corrcoef',l)]
        for i in idx:
            hits.append({'path':str(p),'line':i+1,'context':'\n'.join(f'{j+1}: {lines[j]}' for j in range(max(0,i-12),min(len(lines),i+24)))})
C.write(C.WS/'inputs/k9_source_context.json',hits)
print('K9 contexts',C.json.dumps(hits)[:24000])
files=[]
for p in C.ACQ.rglob('*lc.fits'):
    C.historical(p)
    with fits.open(p,memmap=True) as h:
        t=np.asarray(h[1].data['TIME']); ft=t[np.isfinite(t)]
        keys=['SECTOR','TICID','TIMESYS','TIMEREF','BJDREFI','TIMEDEL','EXPOSURE','CROWDSAP','FLFRCSAP','PROCVER','DATA_REL','TSTART','TSTOP']
        meta={k:h[1].header.get(k,h[0].header.get(k)) for k in keys}
        files.append(dict(path=str(p),columns=h[1].columns.names,meta=meta,tmin=ft.min(),tmax=ft.max(),cadence_s=np.median(np.diff(ft))*86400))
C.write(C.WS/'inputs/local_lightcurves.json',files)
C.write(C.WS/'inputs/environment.json',dict(utc=C.datetime.datetime.now(C.datetime.timezone.utc).isoformat(),python=sys.version,packages={p:md.version(p) for p in ['numpy','scipy','astropy','astroquery','lightkurve','pandas','matplotlib','requests','pytest']},free={x:shutil.disk_usage(x).free for x in ['C:/','D:/']},process_preflight='No Python/wsl/bash jobs in elevated Win32_Process check',workers=1,threads=1))
print('LIGHTCURVES',C.json.dumps(C.clean(files),indent=1))
