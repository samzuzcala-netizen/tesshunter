"""Post-lock descriptive audit of saved native TLS normalization.

No ordinate is removed or replaced, no alternative SDE/pass is calculated, and
no failed path advances. This measures concentration of the saved variance.
"""
from common import *
import argparse,importlib.metadata,importlib.util,shutil
import numpy as np


def run(partial=False):
    records=[]
    for tic in read(P9/'manifests/final_ids.json'):
        if not (P9/'results/locks'/f'tic{tic}.json').exists():
            if partial:continue
            raise RuntimeError('Unsettled host '+str(tic))
        root=P9/'results/blind'/f'tic{tic}'
        for sp in sorted((root/'tls').glob('*_spectrum.npz')):
            key=sp.name.removesuffix('_spectrum.npz');cp=root/'stageC'/f'{key}.json'
            if not cp.exists():continue
            c=read(cp);z=np.load(sp);p=z['periods'];y=z['power'];good=np.isfinite(y)
            mean=float(np.mean(y[good]));ss=(y-mean)**2;total=float(np.sum(ss[good]));i=int(np.nanargmin(y));j=int(np.nanargmax(ss))
            records.append(dict(tic_id=tic,key=key,C_decision=c.get('decision'),SDE=(c.get('blind') or {}).get('SDE'),
              TLS_transit_snr=(c.get('blind') or {}).get('snr'),n_trials=len(y),n_nonfinite=int((~good).sum()),
              mean_power=mean,std_power=float(np.std(y[good])),minimum_power=float(y[i]),minimum_period=float(p[i]),
              minimum_bin_variance_fraction=float(ss[i]/total) if total else None,
              largest_variance_bin_power=float(y[j]),largest_variance_bin_period=float(p[j]),
              largest_bin_variance_fraction=float(ss[j]/total) if total else None,
              power_quantiles={str(q):float(v) for q,v in zip([0,.001,.01,.1,.5,.9,.99,.999,1],np.quantile(y[good],[0,.001,.01,.1,.5,.9,.99,.999,1]))},
              source_sha256={str(f.relative_to(P9)):sha(f) for f in [sp,cp]}))
    package=Path(importlib.util.find_spec('transitleastsquares').origin).parent
    dst=P9/'calibration/tls_implementation';dst.mkdir(exist_ok=True);source_hashes={}
    for name in ['stats.py','main.py','core.py','helpers.py','tls_constants.py']:
        source=package/name;target=dst/name
        if target.exists() and sha(target)!=sha(source):raise RuntimeError('Installed TLS source changed')
        if not target.exists():shutil.copy2(source,target)
        source_hashes[name]=sha(source)
    suffix='_partial' if partial else ''
    write(P9/f'results/spectrum_normalization_audit{suffix}.json',dict(utc=utc(),records=records,
      TLS_version=importlib.metadata.version('transitleastsquares'),TLS_source_sha256=source_hashes,
      TLS_source_copy=str(dst.relative_to(P9)),script_sha256=sha(Path(__file__)),
      method='Variance contribution is (power_i - mean(power))^2 / sum((power-mean(power))^2), using every finite saved ordinate.',
      limitation='Native TLS divides detrended power by its global standard deviation. Saved C files omit raw chi-square trial residuals, so the upstream origin of an extreme ordinate is not determined by this decomposition. No alternate normalization, gate or completeness is evaluated.'))
    print('Saved C spectra audited',len(records),flush=True)
    for r in records:
        if r['C_decision']!='PASS':print(r['key'],'SDE',r['SDE'],'minimum',r['minimum_power'],'variance fraction',r['minimum_bin_variance_fraction'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');a=p.parse_args();run(a.partial)
