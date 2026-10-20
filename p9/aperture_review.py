"""Render native aperture measurements, explicitly retaining unavailable sectors.

The native extractor and its minimum sky-pixel requirement are unchanged. This
presentation repair follows a ValueError in a crowded field; it does not invent
a clean sky annulus or modify the original difference-image measurements.
"""
from common import *
import argparse
import numpy as np

def run(tic,key):
    if (P9/'results/locks'/f'tic{tic}.json').exists():raise RuntimeError('Host is locked')
    from runner import setup
    root,F,A,V=setup(tic)
    import p8_eb_aperture as AP
    import lightkurve as lk
    import astropy.units as u
    from tesshunter.secondary import box_depth,planet_secondary_bound
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    source=root/'eb_screen'/f'{key}_fit_difference.json';diff=read(source)
    for relative,h in diff['source_sha256'].items():
        if sha(P9/relative)!=h:raise RuntimeError('Stale native difference evidence: '+relative)
    eph=diff['ephemeris'];p,t0,d=eph['period'],eph['t0'],eph['duration']
    tid=int(read(root/'neighbours'/f'tic{tic}.json')['gaia']['target']['source_id']);st=read(P9/'inputs/stellar'/f'tic{tic}.json')
    fig,axes=plt.subplots(len(diff['sectors']),2,figsize=(11,3.1*len(diff['sectors'])),squeeze=False,layout='constrained')
    records=[];arrays={}
    for i,s in enumerate(diff['sectors']):
        sec=s['sector'];pos=next(o for o in s['gaia_positions'] if o['source_id']==tid)
        name=next(n for n in diff['source_sha256'] if f'tess-s{sec:04d}-' in n)
        tpf=lk.TessTargetPixelFile(str(P9/name));flux=np.asarray(tpf.flux.to_value(u.electron/u.s));time=np.asarray(tpf.time.value)
        try:
            values,ap,sky=AP.extract(flux,pos,s['gaia_positions'])
        except ValueError as e:
            # Count available pixels using the exact native geometry for a useful
            # failure receipt; do not use this diagnostic mask to extract flux.
            yy,xx=np.indices(flux.shape[1:]);r2=(xx-pos['x'])**2+(yy-pos['y'])**2;ap=r2<=1;sky=(r2>=25)&(r2<=81)
            for star in s['gaia_positions']:
                if star.get('G') is not None and star['G']<18:sky&=(xx-star['x'])**2+(yy-star['y'])**2>4
            records.append(dict(sector=sec,status='unavailable',error=str(e),n_aperture_pixels=int(ap.sum()),n_background_pixels=int(sky.sum()),required_background_pixels=16))
            for ax in axes[i]:
                ax.axis('off');ax.text(.5,.5,f'Sector {sec}: native extraction unavailable\n{str(e)}\n{int(sky.sum())} clean sky pixels; 16 required\nNo relaxed mask or replacement flux',ha='center',va='center',transform=ax.transAxes,fontsize=11)
            arrays.update({f's{sec}_aperture':ap,f's{sec}_sky':sky});continue
        bg=np.nanmedian(flux[:,sky],axis=1);finite=np.isfinite(time)&np.isfinite(values)&np.isfinite(bg)
        time,values,bg=time[finite],values[finite],bg[finite];med=float(np.median(values))
        if med<=0:raise RuntimeError('Nonpositive target-aperture flux')
        f=values/med;phase=((time-t0)/p+.25)%1-.25
        primary=box_depth(time,f,0,p,t0,d);secondary=box_depth(time,f,.5,p,t0,d)
        for ax,y,label in [(axes[i,0],(f-1)*1000,'Target aperture (ppt)'),(axes[i,1],bg,'Local background (electrons/s/pixel)')]:
            draw=np.linspace(0,len(time)-1,min(12000,len(time)),dtype=int);ax.scatter(phase[draw],y[draw],s=1,alpha=.12,color='#426681')
            bins=np.minimum(((phase+.25)*200).astype(int),199);b=np.array([(j/200-.25+.0025,np.median(y[bins==j])) for j in range(200) if np.any(bins==j)])
            ax.plot(b[:,0],b[:,1],color='#b94328',lw=1.1);lo,hi=np.quantile(y,[.002,.998]);pad=(hi-lo)*.1
            ax.set(xlim=(-.25,.75),ylim=(lo-pad,hi+pad),xlabel='Phase at blind fitted ephemeris',ylabel=label,title=f'Sector {sec}');ax.grid(alpha=.15)
        records.append(dict(sector=sec,status='complete',primary=primary,secondary=secondary,n_aperture_pixels=int(ap.sum()),n_background_pixels=int(sky.sum()),
          planet_secondary_bound=planet_secondary_bound(p,st['radius'],st['mass'],st['teff'],primary['depth_ppt']) if primary else None))
        arrays.update({f's{sec}_time':time,f's{sec}_flux':f,f's{sec}_background':bg,f's{sec}_aperture':ap,f's{sec}_sky':sky})
    n=sum(r['status']=='complete' for r in records);status='complete' if n==len(records) else 'partial' if n else 'unavailable'
    fig.suptitle(f'{key}: native target-aperture and background review\nUnblinded review; unavailable sectors remain unavailable',fontsize=11)
    base=root/'eb_screen'/f'{key}_target_aperture';output=lambda ext:base.with_name(base.name+ext)
    fig.savefig(output('.png'),dpi=135);plt.close(fig);np.savez_compressed(output('.npz'),**arrays)
    A.jdump(output('.json'),dict(key=key,ephemeris=eph,status=status,n_sectors_available=n,n_sectors_requested=len(records),sectors=records,
      method=AP.extract.__doc__,native_extractor_sha256=sha(BASE/'scripts/p8_eb_aperture.py'),
      limitations='No relaxation of the native aperture/sky requirement. Box-depth errors omit correlated noise. Pixel maxima are not fitted source positions.',
      source_sha256={str(source.relative_to(P9)):sha(source)},adapter_sha256=sha(Path(__file__)),manual_review_blinded=False))
    print(key,'aperture status',status,n,'of',len(records),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tic',required=True,type=int);p.add_argument('--key',required=True);a=p.parse_args();run(a.tic,a.key)
