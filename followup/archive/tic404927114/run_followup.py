"""Reproducible, read-only-to-P8 crowded-field follow-up of TIC 404927114.

Differential flux uses simultaneous spatial nuisance + a point-source template.
Positive amplitudes mean DIMMING. No fitted planet likelihood is used here.
"""
from __future__ import annotations
import os
for _k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:
    os.environ[_k] = '1'
import argparse
import hashlib
import json
import re
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from scipy import ndimage, optimize, linalg, stats
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from astropy.timeseries import LombScargle
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P8 = REPO/'data/survey/p8'
KEY = 'tic404927114_P27.5436'
TID = '4659930359605646592'
CFG = json.loads((HERE/'config.json').read_text())
OUT = HERE/'measurements'
FIG = HERE/'figures'
ARCH = HERE/'archive'
for _p in [OUT, FIG, ARCH]: _p.mkdir(exist_ok=True)
MANIFEST = {}
RNG = np.random.default_rng(CFG['seed'])

def sha(path):
    path=Path(path)
    with path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    try: key=path.relative_to(REPO).as_posix()
    except ValueError: key=str(path)
    MANIFEST[key]=digest
    return digest

def read(path):
    sha(path)
    return json.loads(Path(path).read_bytes())

def save(path, data):
    def default(x):
        if isinstance(x,np.ndarray): return x.tolist()
        if isinstance(x,np.generic): return x.item()
        if isinstance(x,Path): return str(x)
        raise TypeError(type(x))
    Path(path).write_text(json.dumps(data,indent=2,default=default,allow_nan=True)+'\n',encoding='utf8')

def mad(a,axis=None):
    return 1.4826*np.nanmedian(np.abs(a-np.nanmedian(a,axis=axis,keepdims=True)),axis=axis)

def phase(t, p, epoch): return (np.asarray(t)-epoch+p/2)%p-p/2

def ephemerides():
    a=read(P8/'stageA'/(KEY+'.json')); c=read(P8/'stageC'/(KEY+'.json'))
    f=read(P8/'fit'/(KEY+'.json'))['adopted']
    e={}
    for label,key in [('survey','survey'),('stageA_forced','tls')]:
        x=a['per_ephemeris'][key]['ephemeris']; e[label]={'period':x['period'],'epoch':x['t0'],'duration':x['duration']}
    e['blind']={'period':c['blind']['period'],'epoch':c['blind']['T0_btjd'],'duration':c['blind']['duration_days']}
    e['physical_fit']={'period':f['period'],'epoch':f['t0_btjd'],'duration':f['t14_hours']/24,
                       'period_err':f['period_err'],'epoch_err':f['t0_err'],'duration_err':f['t14_err_hours']/24}
    save(OUT/'ephemerides.json',{'ephemerides':e,'time':'BJD_TDB - 2457000',
          'fit_covariance_available':False,'blind_duration_note':'reported TLS duration; not equated to physical T14',
          'stageA_chosen':a['chosen_ephemeris'],'stageA_summary':a['per_ephemeris']['survey']['det_kept']})
    return e

EPH=ephemerides(); E=EPH['physical_fit']
NB=read(P8/'neighbours/tic404927114.json')
GAIA=read(P8/'eb_screen/tic404927114_gaia_cone_300arcsec.json')['objects']
for g in GAIA: g['source_id']=str(g['source_id'])
assert str(NB['gaia']['target']['source_id'])==TID

def catalogue_xy(wcs, time):
    year=Time(float(np.nanmedian(time))+2457000,format='jd',scale='tdb').jyear
    rows=[]
    for g in GAIA:
        ra,dec=g['ra'],g['dec']; dt=year-2016
        # Linear tangent-plane propagation; annual parallax <=0.01 arcsec for target.
        ra+=float(g.get('pmra') or 0)*dt/(3.6e6*np.cos(np.deg2rad(dec)))
        dec+=float(g.get('pmdec') or 0)*dt/3.6e6
        x,y=wcs.all_world2pix(ra,dec,0)
        rows.append({**g,'x':float(x),'y':float(y),'ra_epoch':ra,'dec_epoch':dec,'jyear':year,
                     'proper_motion_available':g.get('pmra') is not None and g.get('pmdec') is not None})
    return rows

def fetch(url, name):
    path=ARCH/name
    if not path.exists():
        r=requests.get(url,timeout=60);r.raise_for_status();path.write_bytes(r.content)
    sha(path)
    return path

class PRF:
    def __init__(self, camera, ccd, col, row):
        base=f'https://archive.stsci.edu/missions/tess/models/prf_fitsfiles/start_s0004/cam{camera}_ccd{ccd}/'
        listing=fetch(base,f'prf_cam{camera}_ccd{ccd}_index.html').read_text()
        names=sorted(set(re.findall(r'href="(tess2019[^"]+row\d+-col\d+\.fits)"',listing)))
        vals=[(int(re.search(r'row(\d+)',n)[1]),int(re.search(r'col(\d+)',n)[1]),n) for n in names]
        rr=sorted(set(v[0] for v in vals));cc=sorted(set(v[1] for v in vals))
        def brack(v,z):
            i=np.clip(np.searchsorted(v,z)-1,0,len(v)-2)
            return v[i],v[i+1],np.clip((z-v[i])/(v[i+1]-v[i]),0,1)
        r0,r1,fr=brack(rr,row);c0,c1,fc=brack(cc,col)
        self.data=np.zeros((117,117));self.files=[]
        for r,wr in [(r0,1-fr),(r1,fr)]:
            for c,wc in [(c0,1-fc),(c1,fc)]:
                n=next(n for rr,cc,n in vals if rr==r and cc==c)
                p=fetch(base+n,n);self.data+=fits.getdata(p)*wr*wc;self.files.append(n)
    def at(self,x,y,blur=0):
        yy,xx=np.indices((21,21));d=self.data
        if blur: d=ndimage.gaussian_filter(d,blur*9)
        im=ndimage.map_coordinates(d,[58+9*(yy-y),58+9*(xx-x)],order=1,mode='constant',cval=0)
        fy,fx=np.indices((13,13));cx=np.floor(x);cy=np.floor(y)
        norm=ndimage.map_coordinates(d,[58+9*(fy+cy-6-y),58+9*(fx+cx-6-x)],order=1,mode='constant',cval=0).sum()
        return im/max(norm,1e-10)

def poly(kind='quadratic'):
    y,x=np.indices((21,21));x=(x.ravel()-10)/10;y=(y.ravel()-10)/10
    parts=[np.ones(441),x,y]
    if kind!='plane':parts +=[x*x,x*y,y*y]
    return np.array(parts).T

def nuisance(ref,kind='primary'):
    b=poly('plane' if kind=='plane' else 'quadratic')
    if kind!='no_registration':
        gy,gx=np.gradient(ref)
        b=np.column_stack([b,ref.ravel(),gx.ravel(),gy.ravel()])
    return b

def projection(b,sigma):
    bw=b/sigma[:,None]
    q,_,_=linalg.svd(bw,full_matrices=False)
    return q

def project(a,q): return a-q@(q.T@a)

def read_lc(sector):
    p=next((REPO/'data/cache/audit_lightkurve/mastDownload/HLSP').glob(f'*s{sector:04d}-0000000404927114*/*.fits'))
    sha(p)
    with fits.open(p) as h:
        d={k:np.array(h[1].data[k],dtype=float) for k in h[1].data.names}
        h0=dict(h[0].header);h1=dict(h[1].header)
    d['QUALITY']=d['QUALITY'].astype('int64')
    return p,d,h0,h1

def match_times(t,lc):
    # Astrocut CADENCENO is all zeros, so match uniquely to the nearest exposure.
    qt=lc['TIME']; ok=np.isfinite(qt); ind=np.flatnonzero(ok);qt=qt[ok]
    i=np.searchsorted(qt,np.nan_to_num(t,nan=qt[0]));i=np.clip(i,1,len(qt)-1)
    i-=np.abs(qt[i-1]-t)<np.abs(qt[i]-t)
    ix=ind[i];dt=(lc['TIME'][ix]-t)*86400
    good=np.isfinite(t)&(np.abs(dt)<90)
    if len(np.unique(ix[good]))!=good.sum():raise RuntimeError('Nonunique exposure match')
    return np.where(good,lc['TIME'][ix],t),ix,good,dt

def reference_fit(ref,sigma,prf,stars):
    selected=[s for s in stars if -1<s['x']<21 and -1<s['y']<21 and (s.get('phot_g_mean_mag') or 99)<18.5]
    b=poly();q=projection(b,sigma);y=project(ref.ravel()/sigma,q)
    def fit_shift(v,ret=False):
        a=np.column_stack([prf.at(s['x']+v[0],s['y']+v[1]).ravel() for s in selected])
        aw=project(a/sigma[:,None],q)
        flux,res=optimize.nnls(aw,y,maxiter=5000)
        return (a,flux) if ret else res*res
    opt=optimize.minimize(fit_shift,[0,0],method='Powell',bounds=[(-0.8,0.8),(-0.8,0.8)],options={'xtol':0.005,'ftol':0.0002,'maxiter':12})
    a,fl=fit_shift(opt.x,True)
    sky=np.linalg.lstsq(b/sigma[:,None],(ref.ravel()-a@fl)/sigma,rcond=None)[0]
    model=(a@fl+b@sky).reshape(21,21)
    return opt.x,{s['source_id']:float(f) for s,f in zip(selected,fl)},model,float(opt.fun),len(selected)

def temporal_weights(t,tc,duration,good):
    dt=t-tc;inside=np.abs(dt)<duration/2
    win=(np.abs(dt)<CFG['window_half_days'])&good
    # Exclude shoulders between half-duration and 0.75 duration to protect ingress/egress.
    win &= inside | (np.abs(dt)>0.75*duration)
    idx=np.flatnonzero(win); x=dt[idx];h=inside[idx].astype(float)
    expected=duration/np.nanmedian(np.diff(t[np.isfinite(t)]))
    counts=[int(h.sum()),int((x < -0.75*duration).sum()),int((x>0.75*duration).sum())]
    if counts[0]<max(4,CFG['minimum_in_coverage']*expected) or min(counts[1:])<CFG['minimum_flank_points']:
        return None,{'n_in':counts[0],'n_left':counts[1],'n_right':counts[2],'coverage':counts[0]/expected,'usable':False}
    design=np.column_stack([np.ones(len(x)),x,-h])
    w=np.linalg.pinv(design)[2]
    return (idx,w,design),{'n_in':counts[0],'n_left':counts[1],'n_right':counts[2],'coverage':counts[0]/expected,'usable':True}

def measure_series(t,y,tc,duration,good):
    good=good&np.isfinite(y)
    tw,rec=temporal_weights(t,tc,duration,good)
    if tw is None:return rec
    ix,w,design=tw
    coef=np.linalg.lstsq(design,y[ix],rcond=None)[0]
    residual=y[ix]-design@coef
    white=float(np.std(residual,ddof=3)*np.linalg.norm(w))
    # Cluster-robust error with 30-min blocks, using the actual signed contrast.
    block=np.floor((t[ix]-tc+CFG['window_half_days'])/(0.5/24)).astype(int)
    sums=np.bincount(block,weights=w*residual)
    cluster=float(np.sqrt(np.sum(sums*sums)*len(sums)/max(1,len(sums)-3)))
    return {**rec,'depth':float(w@y[ix]),'white_error':white,'block_error':max(white,cluster)}

def centres(t,p,epoch):
    ft=t[np.isfinite(t)]
    first=int(np.ceil((ft.min()-epoch)/p));last=int(np.floor((ft.max()-epoch)/p))
    return [(n,epoch+n*p) for n in range(first,last+1)]

def make_grid(stars,wcs,shift):
    target=next(s for s in stars if s['source_id']==TID)
    # A sky-aligned grid permits stacking detectors with different orientations.
    z=np.arange(-4.4,4.4001,CFG['localization_grid_step_pixels'])
    dy,dx=np.meshgrid(z,z,indexing='ij');off=np.column_stack([dx.ravel(),dy.ravel()])
    ra=target['ra_epoch']+off[:,0]*21/(3600*np.cos(np.deg2rad(target['dec_epoch'])))
    dec=target['dec_epoch']+off[:,1]*21/3600
    px,py=wcs.all_world2pix(ra,dec,0)
    return z,off,np.column_stack([px+shift[0],py+shift[1]])

def candidate_sources(stars,ref_flux):
    t=next(s for s in stars if s['source_id']==TID)
    for s in stars:
        s['sep_epoch_arcsec']=float(np.hypot((s['ra_epoch']-t['ra_epoch'])*np.cos(np.deg2rad(t['dec_epoch'])),s['dec_epoch']-t['dec_epoch'])*3600)
        s['reference_flux_e_s']=ref_flux.get(s['source_id'])
    close=[s for s in stars if s['source_id']!=TID and s['sep_epoch_arcsec']<15]
    mid=[s for s in stars if 15<=s['sep_epoch_arcsec']<40]
    bright=lambda s:s.get('phot_rp_mean_mag') or s.get('phot_g_mean_mag') or 99
    # Cached SIMBAD EB is the G=19.3566 star at approximately 45.6 arcsec.
    ebs=[s for s in stars if 40<s['sep_epoch_arcsec']<51]
    eb=min(ebs,key=lambda s:abs((s.get('phot_g_mean_mag') or 99)-19.356613))
    return [t,min(close,key=bright),min(mid,key=bright),eb]

def run_sector(path):
    sha(path)
    with fits.open(path,memmap=True) as h:
        hd=dict(h[1].header);sector=int(hd['SECTOR']);wcs=WCS(h[2].header)
        rawtime=np.array(h[1].data['TIME'],float);quality=np.array(h[1].data['QUALITY'],np.int64)
        cube=np.array(h[1].data['FLUX'],float).reshape(-1,441)
        ferr=np.array(h[1].data['FLUX_ERR'],float).reshape(-1,441)
    lp,lc,lh0,lh1=read_lc(sector)
    t,ix,matched,dt=match_times(rawtime,lc)
    finite=np.isfinite(t)&np.isfinite(cube).all(axis=1)
    ffi_good=finite&((quality&CFG['quality_bitmask'])==0)
    qlp_mask=CFG['quality_bitmask'] | (2**30 if sector>=56 else 2**12)
    good=ffi_good&matched&((lc['QUALITY'][ix]&qlp_mask)==0)
    out=good&(np.abs(phase(t,E['period'],E['epoch']))>0.8)
    pick=np.flatnonzero(out)[::max(1,int(out.sum()/600))]
    ref=np.nanmedian(cube[pick],axis=0).reshape(21,21)
    sigma=np.maximum(np.nanmedian(ferr[pick],axis=0),mad(np.diff(cube[pick],axis=0),axis=0)/np.sqrt(2))
    sigma=np.maximum(sigma,0.1)
    stars=catalogue_xy(wcs,t)
    col=hd['1CRV5P']+(10+1-hd['1CRP5P']);row=hd['2CRV5P']+(10+1-hd['2CRP5P'])
    prf=PRF(int(hd['CAMERA']),int(hd['CCD']),col,row)
    shift,ref_flux,ref_model,ref_chi,nref=reference_fit(ref,sigma,prf,stars)
    for s in stars:s['x']+=shift[0];s['y']+=shift[1]
    target=next(s for s in stars if s['source_id']==TID)
    # make_grid expects original WCS + fitted translation (catalogue sky unaffected).
    grid,skyoff,xygrid=make_grid(stars,wcs,shift)
    plist=np.array([prf.at(x,y).ravel() for x,y in xygrid]).T
    b=nuisance(ref);q=projection(b,sigma)
    ap=project(plist/sigma[:,None],q);den=np.sum(ap*ap,axis=0)
    pt=prf.at(target['x'],target['y']).ravel();apt=project(pt/sigma,q);dent=float(apt@apt)
    target_filter=apt/sigma/dent
    extracted=cube@target_filter
    rawap=((np.indices((21,21))[1]-target['x'])**2+(np.indices((21,21))[0]-target['y'])**2<2.5**2).ravel()
    rawsum=cube[:,rawap].sum(axis=1);background=np.median(cube,axis=1)
    records=[];images=[];maps=[];event_windows={};control_maps=[];control_target=[];control_centres=[]
    def difference(tc,duration,mask):
        tw,rec=temporal_weights(t,tc,duration,mask)
        if tw is None:return rec,None
        idx,w,design=tw
        d=w@cube[idx];dw=project(d/sigma,q);num=dw@ap
        a=float(target_filter@d);norm=float(w@w)
        white=np.sqrt(norm/dent)
        rec.update(depth_e_s=a,white_error_e_s=float(white),norm_w2=norm,
                   diffuse_median_e_s=float(np.median(d)),point_fraction=float(np.max(num*num/den)/max(dw@dw,1e-15)),
                   max_snr_white=float(np.max(num/np.sqrt(den*norm))))
        return rec,(d,num/den, norm,idx,w)
    for n,tc in centres(t,E['period'],E['epoch']):
        rec,d=difference(tc,E['duration'],good)
        rec.update(sector=sector,cycle=n,tc_btjd=tc)
        ins=finite&(np.abs(t-tc)<E['duration']/2)
        rec.update(ffi_quality_fraction=float(np.mean(~ffi_good[ins])) if ins.any() else None,
                   qlp_bad_fraction=float(np.mean((lc['QUALITY'][ix[ins]]&qlp_mask)!=0)) if ins.any() else None,
                   nearest_exposure_minutes=float(np.nanmin(np.abs(t-tc))*1440),
                   time_to_edge_days=float(min(tc-np.nanmin(t),np.nanmax(t)-tc)))
        fr,_=difference(tc,E['duration'],ffi_good);rec['ffi_only']=fr
        for label,e in EPH.items():
            ec=e['epoch']+n*e['period'];v,_=difference(ec,e['duration'],good);rec[label]=v
        qrec=measure_series(t,extracted,tc,E['duration'],good);rec['series_block_error_e_s']=qrec.get('block_error')
        if d is not None:
            di,am,norm,idx,w=d;images.append(di);maps.append(am)
            rec['map_index']=len(maps)-1
            rec['background_sensitivities']={}
            for kind in ['plane','no_registration']:
                qv=projection(nuisance(ref,kind),sigma);pv=project(pt/sigma,qv)
                rec['background_sensitivities'][kind]=float(pv@(di/sigma)/(pv@pv))
        # Preserve all cadences, raw flags and pixel/QLP traces for every event.
        wi=np.flatnonzero(finite&(np.abs(t-tc)<0.6))
        event_windows[f'n{n}_time']=t[wi]-tc;event_windows[f'n{n}_raw_ap']=rawsum[wi]
        event_windows[f'n{n}_prf']=extracted[wi];event_windows[f'n{n}_background']=background[wi]
        event_windows[f'n{n}_good']=good[wi];event_windows[f'n{n}_ffi_quality']=quality[wi]
        event_windows[f'n{n}_qlp_quality']=lc['QUALITY'][ix[wi]]
        for name in ['SAP_FLUX','DET_FLUX','KSPSAP_FLUX','SYS_RM_FLUX','SAP_BKG','DET_FLUX_SML','DET_FLUX_LAG']:
            if name in lc:event_windows[f'n{n}_{name}']=lc[name][ix[wi]]
        records.append(rec)
    # Uniform deterministic control grid; independent of measured flux/depth.
    trial=np.linspace(np.nanmin(t)+0.5,np.nanmax(t)-0.5,300)
    trial=trial[np.abs(phase(trial,E['period'],E['epoch']))>CFG['control_exclusion_days']]
    for tc in trial:
        rec,d=difference(tc,E['duration'],good)
        if d is None:continue
        control_maps.append(d[1]);control_target.append(rec['depth_e_s']);control_centres.append(tc)
    sel=np.linspace(0,len(control_centres)-1,min(CFG['controls_per_sector'],len(control_centres))).astype(int)
    control_maps=np.array(control_maps)[sel];control_target=np.array(control_target)[sel];control_centres=np.array(control_centres)[sel]
    ctrl_sigma=max(float(mad(control_target)),float(np.std(control_target,ddof=1)))
    median_white=np.median([v['white_error_e_s'] for v in records if v['usable']]) if maps else np.nan
    for rec in records:
        if rec['usable']:
            rec['empirical_error_e_s']=max(ctrl_sigma,rec['white_error_e_s'],rec.get('series_block_error_e_s') or 0)
            rec['empirical_snr']=rec['depth_e_s']/rec['empirical_error_e_s']
            rec['target_depth_ppt']=rec['depth_e_s']/ref_flux[TID]*1000 if ref_flux.get(TID,0)>0 else None
    chosen=candidate_sources(stars,ref_flux)
    inj=[]
    if sector in CFG['injection_sectors']:
        cs=control_centres[np.linspace(0,len(control_centres)-1,CFG['injection_windows_per_sector']).astype(int)]
        for tc in cs:
            tw,_=temporal_weights(t,tc,E['duration'],good);idx,w,_=tw
            h=(np.abs(t[idx]-tc)<E['duration']/2).astype(float)
            original=cube[idx]
            base=w@original
            for source in chosen:
                for depth in CFG['injection_target_equivalent_depths_ppt']:
                    amp=ref_flux[TID]*depth/1000
                    for mismatch in [False,True]:
                        pp=prf.at(source['x']+(0.12 if mismatch else 0),source['y']-(0.09 if mismatch else 0),blur=0.15 if mismatch else 0).ravel()
                        injected=original-h[:,None]*amp*pp[None,:]
                        di=w@injected;dw=project(di/sigma,q);amps=(dw@ap)/den
                        signal=amps/np.maximum(np.std(control_maps,axis=0,ddof=1),0.01)
                        # Position maximizes the spatial likelihood. Empirical
                        # control scatter calibrates significance, not morphology.
                        best=int(np.argmax(amps*np.sqrt(den)))
                        location_error=float(np.linalg.norm(xygrid[best]-[source['x'],source['y']]))
                        sp=project(prf.at(source['x'],source['y']).ravel()/sigma,q)
                        own=float(sp@(di/sigma)/(sp@sp));before=float(sp@(base/sigma)/(sp@sp))
                        inj.append({'sector':sector,'tc':tc,'source_id':source['source_id'],'target_equiv_ppt':depth,
                          'injected_e_s':amp,'mismatch':mismatch,'recovered_e_s':own,'increment_e_s':own-before,
                          'increment_ratio':(own-before)/amp,'peak_control_snr':float(signal[best]),
                          'position_error_px':location_error,'success':bool(signal[best]>3 and location_error<0.5),
                          'source_reference_flux':ref_flux.get(source['source_id']),
                          'intrinsic_eclipse_fraction':amp/ref_flux[source['source_id']] if ref_flux.get(source['source_id'],0)>0 else None})
    meta={'sector':sector,'path':str(path.relative_to(REPO)),'qlp_path':str(lp.relative_to(REPO)),
          'camera':hd['CAMERA'],'ccd':hd['CCD'],'col':col,'row':row,'n_pixels':441,'n_cadences':len(t),
          'matched_exposures':int(matched.sum()),'time_match_delta_seconds':np.nanpercentile(dt[matched],[0,50,100]),
          'qlp_bestap':lh1.get('BESTAP'),'qlp_smallap':lh1.get('SMALLAP'),'qlp_largeap':lh1.get('LARGEAP'),
          'reference_shift_pixels':shift,'reference_flux_target_e_s':ref_flux.get(TID),
          'reference_fit_n_sources':nref,'reference_chi2':ref_chi,'reference_rms_e_s':float(np.std(ref-ref_model)),
          'control_n':len(control_centres),'control_std_e_s':float(np.std(control_target,ddof=1)),
          'control_mad_e_s':float(mad(control_target)),'control_mean_e_s':float(np.mean(control_target)),
          'control_sigma_e_s':ctrl_sigma,'median_event_white_error':median_white,
          'prf_files':prf.files,'injection_sources':chosen,'events':records}
    save(OUT/f's{sector:03d}.json',meta)
    save(OUT/f's{sector:03d}_sources.json',stars)
    np.savez_compressed(OUT/f's{sector:03d}_images.npz',reference=ref,reference_model=ref_model,
        images=np.array(images),maps=np.array(maps),grid=grid,skyoff=skyoff,xygrid=xygrid,
        control_maps=control_maps,control_target=control_target,control_centres=control_centres,
        grid_den=den,sigma=sigma,prf_target=pt.reshape(21,21),**event_windows)
    # Full traces for timing, aliases, and independently reproducible event plots.
    np.savez_compressed(OUT/f's{sector:03d}_series.npz',time=t,prf=extracted,raw_ap=rawsum,background=background,
        good=good,ffi_good=ffi_good,quality=quality,qlp_quality=lc['QUALITY'][ix])
    if inj:pd.DataFrame(inj).to_csv(OUT/f's{sector:03d}_injections.csv',index=False)
    print(f'S{sector}: {sum(v["usable"] for v in records)}/{len(records)} usable events; '
          f'target flux {ref_flux.get(TID,0):.1f} e/s, controls {ctrl_sigma:.2f} e/s; shift {shift.round(3)}',flush=True)
    return meta

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sectors',type=int,nargs='*');ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    paths=sorted((REPO/'data/cache/audit_lightkurve/tesscut').glob('*85.137263_-66.173515*'))
    assert len(paths)==12
    for path in paths:
        sec=int(re.search(r'-s(\d+)',path.name)[1])
        if args.sectors and sec not in args.sectors:continue
        if args.resume and (OUT/f's{sec:03d}.json').exists():continue
        run_sector(path)
    sha(HERE/'config.json');sha(Path(__file__))
    save(OUT/'run_manifest.json',{'utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,
          'numpy':np.__version__,'source_sha256':MANIFEST,'seed':CFG['seed']})

if __name__=='__main__':main()
