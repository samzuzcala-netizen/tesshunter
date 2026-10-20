"""D review assets from frozen P8 pixel methods; never reads planet truth."""
from common import *
import argparse, csv, warnings
import numpy as np

def positions(tic):
    path=P9/'inputs/gaia_positions'/f'tic{tic}.json'
    if path.exists() and read(path).get('status')=='complete':return path
    from astroquery.gaia import Gaia
    st=read(P9/'inputs/stellar'/f'tic{tic}.json')
    query=f"SELECT source_id,ra,dec,pmra,pmdec,phot_g_mean_mag,phot_rp_mean_mag FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{float(st['ra'])},{float(st['dec'])},0.075))"
    tab=Gaia.launch_job_async(query,dump_to_file=False).get_results()
    rows=[]
    for r in tab:
        row={}
        for k in tab.colnames:
            if np.ma.is_masked(r[k]):row[k]=None
            elif k=='source_id':row[k]=int(r[k])
            else:
                v=float(r[k]);row[k]=v if np.isfinite(v) else None
        rows.append(row)
    write(path,dict(utc=utc(),status='complete',query=query,source='Gaia DR3 TAP; astrometry and magnitudes only',objects=rows))
    return path

def run(tic,key):
    from runner import setup
    root,F,A,V=setup(tic)
    import p8_eb_difference_image as I
    import p8_eb_aperture as AP
    import lightkurve as lk
    import astropy.units as u
    from tesshunter.secondary import box_depth,planet_secondary_bound
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    extra=read(root/'expensive'/f'{key}.json')
    sectors=extra.get('centroid',{}).get('sectors_used',[])
    if not sectors:raise RuntimeError('No native D TESScut sectors available')
    gaia=P9/'inputs/gaia_positions'/f'tic{tic}.json'
    I.ROOT=root;I.REPO=P9
    (root/'eb_screen').mkdir(exist_ok=True)
    # Frozen implementation and its fit-cache validation are used unchanged.
    sys.argv=['p8_eb_difference_image.py','--key',key,'--sectors',*[str(s) for s in sectors],
      '--gaia',str(gaia),'--ephemeris','fit','--pixel-cache',str(P9/'work/execution_lightkurve/tesscut')]
    I.main()
    differencepath=root/'eb_screen'/f'{key}_fit_difference.json'
    diff=read(differencepath);eph=diff['ephemeris'];p,t0,d=eph['period'],eph['t0'],eph['duration']
    tid=int(read(root/'neighbours'/f'tic{tic}.json')['gaia']['target']['source_id'])
    st=read(P9/'inputs/stellar'/f'tic{tic}.json')
    fig,axes=plt.subplots(len(sectors),2,figsize=(11,3.1*len(sectors)),squeeze=False,layout='constrained')
    records=[];arrays={}
    for i,s in enumerate(diff['sectors']):
        sec=s['sector'];pos=next(o for o in s['gaia_positions'] if o['source_id']==tid)
        name=next(n for n in diff['source_sha256'] if f'tess-s{sec:04d}-' in n)
        path=P9/name
        if sha(path)!=diff['source_sha256'][name]:raise RuntimeError('Changed pixel input')
        tpf=lk.TessTargetPixelFile(str(path));flux=np.asarray(tpf.flux.to_value(u.electron/u.s));time=np.asarray(tpf.time.value)
        values,ap,sky=AP.extract(flux,pos,s['gaia_positions']);bg=np.nanmedian(flux[:,sky],axis=1)
        finite=np.isfinite(time)&np.isfinite(values)&np.isfinite(bg);time,values,bg=time[finite],values[finite],bg[finite]
        med=float(np.median(values))
        if med<=0:raise RuntimeError('Nonpositive target-aperture flux')
        f=values/med;phase=((time-t0)/p+.25)%1-.25
        primary=box_depth(time,f,0,p,t0,d);secondary=box_depth(time,f,.5,p,t0,d)
        for ax,y,label in [(axes[i,0],(f-1)*1000,'Target aperture (ppt)'),(axes[i,1],bg,'Local background (electrons/s/pixel)')]:
            draw=np.linspace(0,len(time)-1,min(12000,len(time)),dtype=int)
            ax.scatter(phase[draw],y[draw],s=1,alpha=.12,color='#426681')
            bins=np.minimum(((phase+.25)*200).astype(int),199)
            b=np.array([(j/200-.25+.0025,np.median(y[bins==j])) for j in range(200) if np.any(bins==j)])
            ax.plot(b[:,0],b[:,1],color='#b94328',lw=1.1)
            lo,hi=np.quantile(y,[.002,.998]);pad=(hi-lo)*.1
            ax.set(xlim=(-.25,.75),ylim=(lo-pad,hi+pad),xlabel='Phase at blind fitted ephemeris',ylabel=label,title=f'Sector {sec}')
            ax.grid(alpha=.15)
        records.append(dict(sector=sec,primary=primary,secondary=secondary,n_aperture_pixels=int(ap.sum()),n_background_pixels=int(sky.sum()),
          planet_secondary_bound=planet_secondary_bound(p,st['radius'],st['mass'],st['teff'],primary['depth_ppt']) if primary else None))
        arrays.update({f's{sec}_time':time,f's{sec}_flux':f,f's{sec}_background':bg,f's{sec}_aperture':ap,f's{sec}_sky':sky})
    fig.suptitle(f'{key}: native P8 target-aperture and background review\nObserved diluted flux; local sky removed; no detrending; this session is unblinded',fontsize=11)
    stem=root/'eb_screen'/f'{key}_target_aperture'
    output=lambda ext:stem.with_name(stem.name+ext)
    fig.savefig(output('.png'),dpi=135);plt.close(fig)
    np.savez_compressed(output('.npz'),**arrays)
    A.jdump(output('.json'),dict(key=key,ephemeris=eph,sectors=records,method=AP.extract.__doc__,
      limitations='Box-depth errors omit correlated noise. Pixel maxima are not fitted source positions. FPP and centroid significance alone do not establish localization.',
      source_sha256={str(differencepath.relative_to(P9)):sha(differencepath),str(gaia.relative_to(P9)):sha(gaia)},
      adapter_sha256=sha(Path(__file__)),manual_review_blinded=False))
    print('pixel review assets complete',key,flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('cmd',choices=['prepare','run']);a.add_argument('--tic',type=int,required=True);a.add_argument('--key');args=a.parse_args()
    if args.cmd=='prepare':print(positions(args.tic),flush=True)
    else:run(args.tic,args.key)
