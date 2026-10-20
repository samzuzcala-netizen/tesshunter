import common as C
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
import sys,re
def match_time(t,reference,tolerance):
    valid=np.where(np.isfinite(reference))[0]; rt=reference[valid]
    if np.any(np.diff(rt)<=0): raise ValueError('Reference times not strictly increasing')
    j=np.clip(np.searchsorted(rt,t),1,len(rt)-1)
    j=np.where(abs(t-rt[j-1])<=abs(t-rt[j]),j-1,j)
    dt=t-rt[j]; good=np.isfinite(t)&(abs(dt)<tolerance)
    if len(np.unique(j[good]))!=sum(good): raise ValueError('Non one-to-one time matching')
    return valid[j],good,dt
def aperture_map(ap,ap_origin,shape,cut_origin):
    mask=np.zeros(shape,bool)
    for r,c in zip(*np.where((ap&2)!=0)):
        rr=r+ap_origin[1]-cut_origin[1]; cc=c+ap_origin[0]-cut_origin[0]
        if 0<=rr<shape[0] and 0<=cc<shape[1]: mask[rr,cc]=True
    if mask.sum()!=np.sum((ap&2)!=0): raise ValueError('Optimal aperture clipped by cutout')
    return mask
def net_flux(cube,mask,bg): return np.sum(cube[:,mask],axis=1)-mask.sum()*bg
def products():
    return C.json.loads((C.WS/'inputs/product_inventory.json').read_text())
def load(s,kind='spoc'):
    return dict(np.load(C.BIG/'arrays'/f'{kind}_{s}.npz'))
def lcs():
    rows=[]; sources=list(C.ACQ.rglob('*lc.fits'))+list((C.BIG/'downloads').glob('*lc.fits'))
    for p in sources:
        C.check()
        if p.is_relative_to(C.ACQ): C.historical(p)
        with fits.open(p,memmap=True) as h:
            head=dict(h[0].header); head.update(dict(h[1].header)); d=h[1].data
            sec=int(head['SECTOR']); kind='qlp' if 'qlp' in p.name else 'spoc'
            assert int(head['TICID'])==332366289 and head['TIMESYS']=='TDB' and int(head['BJDREFI'])==2457000
            t=np.array(d['TIME'],float); ok=np.isfinite(t); t=t[ok]
            arr={'time':t,'quality':np.array(d['QUALITY'],np.int64)[ok]}
            for k in ['SAP_FLUX','PDCSAP_FLUX','SAP_BKG','DET_FLUX','DET_FLUX_ERR','CADENCENO','TIMECORR']:
                if k in d.columns.names: arr[k]=np.array(d[k])[ok]
            if 'KSPSAP_FLUX' in d.columns.names:
                arr['DET_FLUX']=np.array(d['KSPSAP_FLUX'])[ok]
                arr['DET_FLUX_ERR']=np.array(d['KSPSAP_FLUX_ERR'])[ok]
            cadence=float(np.median(np.diff(t))); arr['cadence']=cadence
            arr['exposure_span']=float(head.get('TIMEDEL',cadence))
            arr['crowdsap']=float(head.get('CROWDSAP',1));arr['flfrcsap']=float(head.get('FLFRCSAP',1))
            if kind=='spoc':
                arr['aperture']=np.array(h[2].data,np.int64)
                arr['ap_origin']=np.array([h[2].header['CRVAL1P'],h[2].header['CRVAL2P']],int)
            np.savez_compressed(C.BIG/'arrays'/f'{kind}_{sec}.npz',**arr)
            keys=['SECTOR','TICID','TIMESYS','TIMEREF','BJDREFI','BJDREFF','TIMEUNIT','TIMEDEL','INT_TIME','READTIME','FRAMETIM','NUM_FRM','EXPOSURE','DEADC','CROWDSAP','FLFRCSAP','PROCVER','DATA_REL','ORIGIN','VERSION','RA_OBJ','DEC_OBJ']
            row=dict(sector=sec,kind=kind,path=str(p),sha256=C.sha(p),size=p.stat().st_size,tmin=t.min(),tmax=t.max(),cadence_s=cadence*86400,columns=d.columns.names,metadata={k:head.get(k) for k in keys})
            rows.append(row)
    C.write(C.WS/'inputs/product_inventory.json',rows)
    needed=[]; epochs=[]
    for sec in C.SECTORS:
        base=next((r for r in rows if r['sector']==sec and r['kind']=='spoc'),None) or next((r for r in rows if r['sector']==sec),None)
        if base is None:
            if sec<56: needed.append(dict(sector=sec,reason='No pipeline LC in single MAST search; cutout required to establish coverage and raw pixel photometry'))
            continue
        a=load(sec,base['kind']); t=a['time']; good=(a['quality']&191)==0; total=0
        for label,(p,t0,d) in [('EA',C.EA),('EF',C.EF)]:
            for n in range(int(np.ceil((t[0]-d-t0)/p)),int(np.floor((t[-1]+d-t0)/p))+1):
                tc=t0+n*p; nin=int(np.sum((abs(t-tc)<d/2)&good));total+=nin
                epochs.append(dict(sector=sec,ephemeris=label,cycle=n,tc=tc,n_good_near_epoch=nin))
        if sec<56 and total: needed.append(dict(sector=sec,covered_frames=total))
    C.write(C.WS/'inputs/epoch_inventory_before_depths.json',epochs)
    C.write(C.WS/'inputs/needed_cutouts.json',needed)
    print('LC inventory',[(r['sector'],r['kind'],round(r['cadence_s'])) for r in rows]);print('Needed cubes',needed)
def pixels():
    rows=[]
    paths=list(C.TC.glob('*257.222579_50.487785_21x21_astrocut.fits'))+list((C.BIG/'downloads').glob('*astrocut.fits'))
    for p in paths:
        C.check()
        if p.is_relative_to(C.TC): C.historical(p)
        with fits.open(p,memmap=True) as h:
            sec=int(h[0].header['SECTOR'])
            if sec not in C.SECTORS: continue
            tcut=np.array(h[1].data['TIME'],float);q=np.array(h[1].data['QUALITY'],np.int64)
            has_spoc=(C.BIG/'arrays'/f'spoc_{sec}.npz').exists()
            if has_spoc: a=load(sec)
            else:
                cad=np.median(np.diff(tcut[np.isfinite(tcut)]))
                a=dict(time=tcut,quality=q,cadence=cad,exposure_span=float(h[1].header.get('TIMEDEL',cad)),crowdsap=np.nan,flfrcsap=np.nan)
            li,match,dt=match_time(tcut,a['time'],float(a['cadence'])*0.5)
            assert np.mean(match)>.98,(sec,'Cadence matching failed')
            cube=np.array(h[1].data['FLUX'],float)
            w=WCS(h[2].header);xy=np.asarray(w.all_world2pix([[257.222579,50.487785]],0)[0])
            origin=np.array([h[1].header['1CRV4P'],h[1].header['2CRV4P']],int)
            opt=aperture_map(a['aperture'],a['ap_origin'],cube.shape[1:],origin) if has_spoc else np.zeros(cube.shape[1:],bool)
            small=np.zeros(cube.shape[1:],bool);x,y=np.rint(xy).astype(int);small[y-1:y+2,x-1:x+2]=True
            good=(q==0)&match&((a['quality'][li]&191)==0)
            median=np.nanmedian(cube[good],axis=0);yy,xx=np.indices(median.shape)
            candidates=(np.hypot(xx-xy[0],yy-xy[1])>4)&~opt&np.isfinite(median)
            ids=np.flatnonzero(candidates);ids=ids[np.argsort(median.flat[ids])[:int(median.size*.2)]]
            bgmask=np.zeros(median.shape,bool);bgmask.flat[ids]=True
            bg=np.nanmedian(cube[:,bgmask],axis=1)
            good &= np.isfinite(bg)
            data=dict(time=a['time'][li],original_time=tcut,matched=match,quality=q,spoc_quality=a['quality'][li],good=good,background=bg,optimal=net_flux(cube,opt,bg),small=net_flux(cube,small,bg),raw_optimal=np.sum(cube[:,opt],axis=1),cadence=a['cadence'],exposure_span=a['exposure_span'],opt_mask=opt,small_mask=small,bg_mask=bgmask,median_image=median,target_xy=xy,crowdsap=a['crowdsap'],flfrcsap=a['flfrcsap'])
            if not has_spoc: data['optimal'][:]=np.nan
            np.savez_compressed(C.BIG/'arrays'/f'pixel_{sec}.npz',**data)
            np.savez_compressed(C.WS/'results'/f'apertures_s{sec}.npz',opt_mask=opt,small_mask=small,bg_mask=bgmask,median_image=median,target_xy=xy)
            meta=dict(sector=sec,path=str(p),sha256=C.sha(p),size=p.stat().st_size,matched=int(sum(match)),n=len(match),n_quality_good=int(sum(good)),finite_small=int(np.sum(np.isfinite(data['small']))),median_small=float(np.nanmedian(data['small'][good])),dt_min_s=np.min(dt[match])*86400,dt_max_s=np.max(dt[match])*86400,optimal_npix=int(opt.sum()),small_npix=int(small.sum()),bg_npix=int(bgmask.sum()),target_xy=xy,background_subtracted_in_input=bool(h[1].header.get('BACKAPP',False)),flux_bkg_zero=bool(np.all(h[1].data['FLUX_BKG']==0)),timesys=h[1].header.get('TIMESYS'),bjdrefi=h[1].header.get('BJDREFI'),cadence_s=float(a['cadence'])*86400)
            rows.append(meta); print('Pixels',sec,meta['optimal_npix'],meta['matched'],meta['dt_min_s'],meta['dt_max_s'],flush=True)
    C.write(C.WS/'inputs/pixel_inventory.json',rows)
if __name__=='__main__':
    if sys.argv[1]=='lcs': lcs()
    else: pixels()
