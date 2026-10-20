"""Separate, truth-bearing preparation process. Never imported by runner.py."""
from common import *
import argparse, csv, importlib.metadata, platform, shutil, subprocess, urllib.parse
def snapshot():
    files = {str(p.relative_to(BASE)):sha(p) for p in sorted(BASE.rglob('*')) if p.is_file()}
    versions={x.metadata['Name']:x.version for x in importlib.metadata.distributions()}
    write(P9/'baseline/environment.json', dict(utc=utc(),python=sys.version,executable=sys.executable,
          platform=platform.platform(),packages=versions,disk_free_bytes=shutil.disk_usage(REPO).free,
          cpu_count=os.cpu_count(),git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()))
    write(P9/'baseline/source_hashes.json',files)
    hist={str(p.relative_to(REPO)):sha(p) for pat in ['HANDOFF_P8.md','PROMPT_P8.md','docs/AUDIT_P8.md',
      'docs/COMPLETENESS_P8.md','docs/POPULATION_P8.md','docs/TIC404927114_FOLLOWUP.md','followups/**/*']
      for p in REPO.glob(pat) if p.is_file()}
    write(P9/'baseline/preserved_hashes.json',hist)
    frozen_imports()
    from tesshunter.survey import get_config
    from tesshunter.audit_rules import P8_RULES,thresholds
    write(P9/'baseline/configuration.json',dict(config=get_config('survey_p8').to_dict(),rules=thresholds(P8_RULES)))
    print('baseline frozen',len(files),'files',flush=True)
def fetch():
    import requests, pandas as pd
    cols='pl_name,hostname,tic_id,default_flag,soltype,pl_controv_flag,tran_flag,pl_orbper,pl_orbpererr1,pl_orbpererr2,pl_tranmid,pl_tranmiderr1,pl_tranmiderr2,pl_trandur,pl_rade,pl_trandep,pl_imppar,pl_orbeccen,ttv_flag,st_teff,st_rad,st_mass,sy_tmag,ra,dec,disc_year,disc_refname,pl_refname'
    query=f'select {cols} from ps where default_flag=1 and tran_flag=1 and pl_orbper>=0.5 and pl_orbper<=30'
    urls={'nasa_ps_truth.csv':'https://exoplanetarchive.ipac.caltech.edu/TAP/sync?'+urllib.parse.urlencode({'query':query,'format':'csv'}),
      'exofop_toi.csv':'https://exofop.ipac.caltech.edu/tess/download_toi.php?sort=toi&output=csv',
      'exofop_ctoi.csv':'https://exofop.ipac.caltech.edu/tess/download_ctoi.php?sort=ctoi&output=csv',
      'tess_eb.csv':'https://archive.stsci.edu/hlsps/tess-ebs/hlsp_tess-ebs_tess_lcf-ffi_s0001-s0026_tess_v1.0_cat.csv'}
    receipts={}
    for name,url in urls.items():
        dest=P9/'truth/catalogues'/name; dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            try:
                r=requests.get(url,timeout=(30,180));r.raise_for_status();dest.write_bytes(r.content)
            except Exception as e:
                receipts[name]={'url':url,'error':str(e),'utc':utc()};print(name,str(e),flush=True);continue
        receipts[name]={'url':url,'sha256':sha(dest),'bytes':dest.stat().st_size,'utc':utc()}
        try:
            df=pd.read_csv(dest,comment='#');print(name,len(df),list(df.columns),flush=True)
        except Exception as e: print('parse error',str(e),flush=True)
    write(P9/'truth/catalogues/receipts.json',receipts)
    dest=P9/'truth/production_catalogues'
    if not dest.exists():
        shutil.copytree(REPO/'data/cache/catalogs',dest,ignore=shutil.ignore_patterns('raw'))
    write(P9/'truth/production_catalogues_hashes.json',{str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()})
def inventory():
    import pandas as pd
    ps=pd.read_csv(P9/'truth/catalogues/nasa_ps_truth.csv',comment='#')
    ps['tic_num']=ps.tic_id.str.extract(r'(\d+)')[0].astype('Int64')
    idx=[]
    for p in (REPO/'data/survey/audit_lc').glob('tic*/index.json'):
        try:
            d=read(p);prods=[x for x in d.get('products',[]) if x.get('file') and int(x['sector'])>=56 and float(x.get('cadence_s',9999))<301]
            idx.append(dict(tic_num=int(p.parent.name[3:]),n_200s=len(set(x['sector'] for x in prods)),products=len(prods)))
        except Exception: pass
    inv=pd.DataFrame(idx);inv.to_csv(P9/'work/store_inventory.csv',index=False)
    ps=ps.merge(inv,on='tic_num',how='left')
    good=ps[(ps.st_rad<=1)&(ps.st_teff<=6000)&(ps.sy_tmag<=14.5)&(ps.pl_controv_flag==0)]
    print('broad planet frame',len(good),'already stored >=3',int((good.n_200s>=3).sum()),flush=True)
    print(good[good.n_200s>=3][['pl_name','tic_num','pl_orbper','pl_rade','sy_tmag','st_teff','st_rad','n_200s']].to_string(index=False),flush=True)
    good.to_csv(P9/'truth/frame_precoverage.csv',index=False)
def frame():
    import pandas as pd, numpy as np
    ps=pd.read_csv(P9/'truth/catalogues/nasa_ps_truth.csv',comment='#')
    ps['tic_num']=pd.to_numeric(ps.tic_id.str.extract(r'(\d+)')[0],errors='coerce')
    toi=pd.read_csv(P9/'truth/catalogues/exofop_toi.csv')
    eb=pd.read_csv(P9/'truth/catalogues/tess_eb.csv')
    allids=np.unique(np.concatenate([ps.tic_num.dropna().astype('int64'),toi['TIC ID'].dropna().astype('int64'),eb.tess_id.astype('int64')]))
    coverage={int(t):{'ffi':[],'twomin':[]} for t in allids}; hashes={}
    for directory,kind in [('target_lists','ffi'),('twomin_lists','twomin')]:
        for path in sorted((REPO/'data/survey/cache'/directory).glob('*.npy')):
            import re
            m=re.search(r'_s(\d+)',path.name)
            if not m or not 56<=int(m[1])<=105: continue
            a=np.load(path,mmap_mode='r');ix=np.searchsorted(a,allids);hit=(ix<len(a))
            if len(a): hit &= a[np.minimum(ix,len(a)-1)]==allids
            else: hit[:]=False
            for t in allids[hit]: coverage[int(t)][kind].append(int(m[1]))
            hashes[str(path.relative_to(REPO))]=sha(path)
    for d in coverage.values():
        d['ffi']=sorted(set(d['ffi']));d['twomin']=sorted(set(d['twomin']))
    write(P9/'manifests/coverage.json',coverage);write(P9/'baseline/target_list_hashes.json',hashes)
    rows=[]
    for _,r in ps.iterrows():
        if pd.isna(r.tic_num):continue
        tic=int(r.tic_num);cv=coverage[tic]
        ts=toi[toi['TIC ID']==tic];ts=ts[np.abs(ts['Period (days)']/r.pl_orbper-1)<.001]
        dur=r.pl_trandur;epoch=r.pl_tranmid;dep=r.pl_trandep*10000;rp=r.pl_rade
        duration_source='NASA PS default';epoch_source='NASA PS default'
        if len(ts):
            ts=ts.iloc[0]
            if pd.isna(dur):dur=ts['Duration (hours)'];duration_source='ExoFOP TOI period-matched'
            if pd.isna(epoch):epoch=ts['Epoch (BJD)'];epoch_source='ExoFOP TOI period-matched'
            if pd.isna(dep):dep=ts['Depth (ppm)']
        reasons=[]
        if r.pl_controv_flag!=0:reasons.append('controversial_label')
        if not 0<r.st_rad<=1 or not 0<r.st_teff<=6000 or not 0<r.sy_tmag<=14.5:reasons.append('broad_stellar_domain')
        if len(cv['ffi'])<3:reasons.append('fewer_than_3_delivered_ffi_sectors')
        if not .48<=dur<=4.8:reasons.append('duration_outside_or_missing')
        if not np.isfinite(epoch):reasons.append('missing_epoch')
        p8=bool(r.st_rad<.45 and r.st_teff<3600 and 12.5<=r.sy_tmag<=14 and len(cv['twomin'])<len(cv['ffi'])/2)
        stratum='p8_proxy' if p8 else ('small_long' if 1<=rp<=4 and r.pl_orbper>=10 else ('small_short' if 1<=rp<=4 else 'other_radius'))
        rows.append(dict(truth_id=r.pl_name,tic_id=tic,label='positive',subtype='catalogue_confirmed',period=r.pl_orbper,
          epoch_btjd=epoch-2457000,duration_hours=dur,depth_ppm=dep,radius_re=rp,period_err=r.pl_orbpererr1,
          epoch_err=r.pl_tranmiderr1,ttv_flag=r.ttv_flag,teff=r.st_teff,rstar=r.st_rad,mass=r.st_mass,tmag=r.sy_tmag,
          ra=r.ra,dec=r.dec,disc_year=r.disc_year,discovery_reference=r.disc_refname,parameter_reference=r.pl_refname,
          duration_source=duration_source,epoch_source=epoch_source,stratum=stratum,p8_proxy=p8,n_ffi=len(cv['ffi']),
          n_twomin=len(cv['twomin']),frame_eligible=not reasons,ineligibility=';'.join(reasons)))
    for _,r in eb.iterrows():
        tic=int(r.tess_id);cv=coverage[tic];dur=r.prim_width_pf*r.period*24
        rows.append(dict(truth_id=f'TESS-EB-{tic}-{int(r.signal_id)}',tic_id=tic,label='negative',
          subtype='detached_or_semidetached_EB' if r.morph_coeff<.6 else 'contact_or_ellipsoidal_EB',
          period=r.period,epoch_btjd=r.bjd0,duration_hours=dur,depth_ppm=r.prim_depth_pf*1e6,
          radius_re=None,tmag=r.Tmag,ra=r.ra,dec=r.dec,stratum='EB_detached' if r.morph_coeff<.6 else 'EB_contact',
          frame_eligible=bool(.5<=r.period<=30 and .48<=dur<=4.8 and len(cv['ffi'])>=3 and r.Tmag<=14.5),
          ineligibility='period_duration_coverage_or_magnitude' if not (.5<=r.period<=30 and .48<=dur<=4.8 and len(cv['ffi'])>=3 and r.Tmag<=14.5) else '',
          n_ffi=len(cv['ffi']),n_twomin=len(cv['twomin']),parameter_reference='https://archive.stsci.edu/hlsp/tess-ebs',morph_coeff=r.morph_coeff))
    known=set(int(t) for t in ps.tic_num.dropna());ebs=set(eb.tess_id.astype(int))
    for _,r in toi.iterrows():
        tic=int(r['TIC ID']);cv=coverage[tic];dis=str(r['TFOPWG Disposition']);com=str(r.Comments)
        if tic in known or tic in ebs:continue
        if dis=='PC':label='uncertain';sub='TOI_PC'
        elif dis=='FP':
            label='uncertain';sub='TOI_FP_unverified_subtype'
        else:continue
        per=r['Period (days)'];dur=r['Duration (hours)'];ep=r['Epoch (BJD)']
        rows.append(dict(truth_id=f'TOI-{r.TOI}',tic_id=tic,label=label,subtype=sub,period=per,epoch_btjd=ep-2457000,
          duration_hours=dur,depth_ppm=r['Depth (ppm)'],radius_re=r['Planet Radius (R_Earth)'],
          tmag=r['TESS Mag'],teff=r['Stellar Eff Temp (K)'],rstar=r['Stellar Radius (R_Sun)'],
          stratum='uncertain' if dis=='PC' else 'fp_unverified',comments=com,
          frame_eligible=bool(.5<=per<=30 and .48<=dur<=4.8 and len(cv['ffi'])>=3 and r['TESS Mag']<=14.5 and np.isfinite(ep)),
          ineligibility='period_duration_coverage_or_magnitude',n_ffi=len(cv['ffi']),n_twomin=len(cv['twomin']),
          parameter_reference=f'https://exofop.ipac.caltech.edu/tess/target.php?id={tic}'))
    df=pd.DataFrame(rows);df.to_csv(P9/'truth/sampling_frame.csv',index=False)
    print(df[df.frame_eligible].groupby(['label','stratum']).agg(signals=('tic_id','size'),hosts=('tic_id','nunique')).to_string(),flush=True)
    print('P8 proxies',df[df.frame_eligible & (df.stratum=='p8_proxy')][['truth_id','tic_id','period','radius_re','tmag','n_ffi']].to_string(index=False),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=['snapshot','fetch','inventory','frame']);a=p.parse_args();globals()[a.cmd]()
