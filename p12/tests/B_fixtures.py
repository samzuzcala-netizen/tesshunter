"""Lane B fixtures, isolated from all live science and cache destinations."""
import json
import os
from pathlib import Path
import numpy as np
from astropy.io import fits
from p12_common import REPO as REAL_REPO, read, sha, write


def roots(monkeypatch, tmp_path, *modules):
    repo=tmp_path;root=repo/'p12';data=repo/'data/survey/p12'
    (root/'protocol').mkdir(parents=True,exist_ok=True)
    write(root/'protocol/config.json',read(REAL_REPO/'p12/protocol/config.json'))
    for module in modules:
        for name,value in [('REPO',repo),('ROOT',root),('DATA',data)]:
            if hasattr(module,name):monkeypatch.setattr(module,name,value)
    return repo,root,data


def product(repo,tic,sector,*,author='QLP',sml=True,finite_ratio=1.,n=500,version='01'):
    rawdir=repo/f'data/survey/audit_lc/tic{tic}';rawdir.mkdir(parents=True,exist_ok=True)
    time=2000+sector*2+np.arange(n)*200/86400
    flux=1+.001*np.sin(np.arange(n)*1.231)+.0002*np.cos(np.arange(n)*.182)
    raw=dict(time=time,flux=flux,flux_err=np.full(n,np.nan),sap_flux=flux*1000,
        sap_flux_err=np.full(n,np.nan),sap_bkg=np.zeros(n),quality=np.zeros(n,dtype=np.int32))
    name=f's{sector}_{author}.npz';np.savez_compressed(rawdir/name,**raw)
    column='DET_FLUX' if author=='QLP' else 'PDCSAP_FLUX'
    meta=dict(file=name,sector=sector,author=author,cadence_s=200.,flux_column=column,
        camera=1,ccd=1)
    cols=[fits.Column(name='TIME',format='D',array=time),fits.Column(name=column,format='D',array=flux),
        fits.Column(name=column+'_ERR',format='D',array=raw['flux_err']),
        fits.Column(name='SAP_FLUX',format='D',array=raw['sap_flux']),
        fits.Column(name='SAP_FLUX_ERR',format='D',array=raw['sap_flux_err']),
        fits.Column(name='QUALITY',format='J',array=raw['quality'])]
    if sml:
        small=flux.copy()+.0003*np.sin(np.arange(n)*.17)
        small[int(n*finite_ratio):]=np.nan
        cols.append(fits.Column(name='DET_FLUX_SML',format='D',array=small))
    hdu=fits.BinTableHDU.from_columns(cols)
    for key,value in dict(SECTOR=sector,TIMESYS='TDB',TIMEREF='SOLARSYSTEM',BJDREFI=2457000,BJDREFF=0).items():hdu.header[key]=value
    prefix='hlsp_qlp' if author=='QLP' else 'hlsp_tess-spoc' if author=='TESS-SPOC' else 'tess'
    source=repo/f'data/cache/audit_lightkurve/mastDownload/fixture/{prefix}_{tic:016d}_s{sector:04d}_v{version}_lc.fits'
    source.parent.mkdir(parents=True,exist_ok=True)
    fits.HDUList([fits.PrimaryHDU(),hdu]).writeto(source)
    return meta,source


def index(repo,tic,products):
    path=repo/f'data/survey/audit_lc/tic{tic}/index.json'
    write(path,dict(tic_id=tic,n_products=len(products),n_failed=0,products=products))
    return path


def identity(repo,root,tic,products,sources):
    import input_identity_p12 as I
    idx=index(repo,tic,products);cfg=read(root/'protocol/config.json');records=[]
    for meta,source in zip(products,sources):
        path=idx.parent/meta['file']
        with np.load(path) as z:raw={k:z[k] for k in z.files}
        src=I.read_source(source);comparison=I.compare(raw,meta,src)
        records.append(dict(metadata=meta,raw_path=path.relative_to(repo).as_posix(),raw_sha256=sha(path),
            source=src[0],comparison=comparison,timing_status=I.timing_status(meta,src[0],comparison,cfg),n_quality_good=len(raw['time'])))
    chosen=I.choose_verified(records,cfg)
    value=dict(tic_id=tic,index_sha256=sha(idx),records=records,
        selected_sectors=[r['metadata']['sector'] for r in chosen],notice_snapshot_sha256='0'*64)
    write(root/f'manifests/input_identity/tic{tic}.json',value)
    return value


def link_file(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():return
    try:os.link(source,destination)
    except OSError:
        # The audit stores live on D: behind junctions since 2026-09-23 (0b/5a relocation);
        # a hard link cannot cross drives, so the fixture takes a byte-identical copy.
        import shutil;shutil.copyfile(source,destination)
