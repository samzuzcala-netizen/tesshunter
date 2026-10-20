"""Post-lock, truth-informed diagnostics. No result here changes a blind verdict."""
from common import *
import argparse, csv, collections, hashlib, math
import numpy as np
import pandas as pd

def slug(name):return hashlib.sha256(name.encode()).hexdigest()[:14]
def finite(v):
    try:return float(v) if np.isfinite(float(v)) else None
    except Exception:return None

def scores_available():
    path=P9/'results/scored_signals.json'
    return read(path if path.exists() else P9/'results/scored_signals_partial.json')

def one(name):
    from scoring import verify_lock
    scores=scores_available();score=next(r for r in scores if r['truth_id']==name)
    tic=int(score['tic_id']);verify_lock(tic)
    truth=pd.read_csv(P9/'truth/final_truth.csv');r=truth[truth.truth_id==name].iloc[0].to_dict()
    root=P9/'diagnostics'/slug(name);root.mkdir(parents=True,exist_ok=True)
    frozen_imports()
    import audit_p5 as A
    from tesshunter import survey,survey_p8
    from tesshunter.event_vet import stagea_criteria,classes_of
    A.REPO=P9;A.set_rules('p8.0');A.set_input_config(survey.get_config('survey_p8'));A.set_roots(root,P9/'inputs/raw')
    A.stellar_from_cache=lambda t:read(P9/'inputs/stellar'/f'tic{int(t)}.json')
    st=A.stellar_from_cache(tic);rad=finite(r.get('radius_re'));rs=finite(r.get('rstar')) or st.get('radius')
    dep=finite(r.get('depth_ppm'))
    if dep is None and rad and rs:dep=1e6*(rad/(109.076*rs))**2
    if dep is None:dep=1000.
    p=float(r['period']);t0=float(r['epoch_btjd']);dur=float(r['duration_hours'])/24
    row=dict(rank=1,tic_id=tic,planet_num=1,period_days=p,epoch_btjd=t0,duration_days=dur,depth_ppt=dep/1000,
      stitch_snr=0,stitch_n_transits=score.get('opportunities') or 0,n_units=1,tmag=st.get('tmag'),
      radius_rsun=st.get('radius'),mass_msun=st.get('mass'),teff_k=st.get('teff'),ra_deg=st.get('ra'),dec_deg=st.get('dec'))
    table=root/'counterfactual_truth_ephemeris.csv';pd.DataFrame([row]).to_csv(table,index=False)
    A.set_population(survivors_csv=table,packets_dir=P9/'inputs/empty_packets')
    features=dict(truth_id=name,tic_id=tic,first_termination=score.get('first_termination'),
      label=r['label'],subtype=r['subtype'],stratum=r['stratum'],period=p,radius_re=rad,duration_hours=dur*24,
      opportunities=score.get('opportunities'),tmag=st.get('tmag'),teff=st.get('teff'),rstar=st.get('radius'),
      depth_ppm=dep,ttv_flag=finite(r.get('ttv_flag')),diagnostic_only=True)
    try:
        lc,prov,_=survey_p8.get_prepared(tic,survey.get_config('survey_p8'),cache_dir=P9/'work/stitched',lc_root=P9/'inputs/raw')
        t=np.asarray(lc.time.value);f=np.asarray(lc.flux.value);ok=np.isfinite(t)&np.isfinite(f);t=t[ok];f=f[ok]
        sigma=float(1.4826*np.median(np.abs(f-np.median(f))))
        pe=finite(r.get('period_err'));ee=finite(r.get('epoch_err'))
        if pe is not None and ee is not None:
            ncycle=max(abs((t.min()-t0)/p),abs((t.max()-t0)/p))
            sigep=float(np.hypot(ee,ncycle*pe))
            features['published_ephemeris_sigma_at_window_end_days']=sigep
            features['ephemeris_sigma_over_duration']=sigep/dur
            features['ephemeris_uncertainty_assumption']='Independent period/epoch errors; covariance and TTVs not available; diagnostic only'
        phase=(t-t0+p/2)%p-p/2;inside=abs(phase)<=dur/2
        features.update(sigma_cadence_ppt=sigma*1000,n_in_transit=int(inside.sum()),
          snr_box_expected=float(dep/1e6*np.sqrt(inside.sum())/sigma) if sigma>0 else None,
          n_sectors=len(prov.get('units_used',[])),products=prov.get('products'),rotation_proxy=prov.get('rotation_proxy'))
        ps=pd.read_csv(P9/'truth/catalogues/nasa_ps_truth.csv');ps=ps[ps.pl_name==name]
        if rad and rs and len(ps):
            raw=ps.iloc[0];impact=finite(raw.pl_imppar);assumed=impact is None
            impact=.5 if impact is None else impact
            mass=finite(r.get('mass')) or st.get('mass') or rs
            ars=survey.a_over_rs(p,mass,rs);u=survey.limb_darkening_for_teff(r.get('teff') or st.get('teff'))
            model=survey.transit_model(t,period=p,t0=t0,rp_rs=rad/(109.076*rs),b=impact,a_rs=ars,u=u,exp_time_days=200/86400)
            features.update(snr_expected=float(np.sqrt(np.sum((1-model)**2))/sigma) if sigma else None,
              snr_model_assumptions=dict(circular_orbit=True,impact=impact,impact_assumed=assumed,radius_rsun=rs,mass_msun=mass,
                radius_re=rad,exposure_seconds=200,method='Same batman matched-filter norm / cadence MAD as P8; literature planet+stellar geometry'),
              template_duration_hours=survey.transit_duration_days(p,ars,impact,rad/(109.076*rs))*24)
        prep=A.prepare_step(tic,p);ev=A.events_step(tic,p,source='survey')
        features['truth_event_summary']=ev['summary'];features['truth_counterfactual_A']=stagea_criteria(ev['summary']['det_kept'],dep/1000,p_min=.001)
        features['event_removal_counts']=dict(collections.Counter(c for e in ev['events'] if e.get('observed') for c in classes_of(e.get('exclusion_reasons') or [])))
        features['counterfactual_label']='Uses published ephemeris and depth; excluded from primary completeness; no forced TLS rescue'
        blindroot=P9/'results/blind'/f'tic{tic}';key=score.get('candidate_key') or score.get('alias_candidate_key')
        if key:
            features['blind_evidence']={}
            for folder in ['stageA','secondary','stageB','stageC','final']:
                path=blindroot/folder/f'{key}.json'
                if path.exists():features['blind_evidence'][folder]={'path':str(path.relative_to(P9)),'sha256':sha(path),'reason':read(path).get('reason')}
        auxpath=P9/'inputs/stellar_aux'/f'tic{tic}.json'
        aux=read(auxpath) if auxpath.exists() else {}
        cv=read(P9/'manifests/coverage_corrected.json').get(str(tic),{})
        features['strict_p8_stellar_and_targeting']=bool(st.get('teff') and st['teff']<3600 and st.get('radius') and st['radius']<.45
          and st.get('tmag') and 12.5<=st['tmag']<=14 and abs(aux.get('galactic_latitude') or 0)>=20
          and aux.get('gaia_dwarf_check') and aux.get('lumclass') in ('DWARF','nan','None','')
          and len(cv.get('ffi',[]))>=3 and len(set(cv.get('twomin',[]))&set(cv.get('ffi',[])))<len(cv.get('ffi',[]))/2)
        actual=read(P9/'manifests/products'/f'tic{tic}.json')['products']
        features['actual_spoc_fraction']=sum(q['author']=='SPOC' for q in actual)/len(actual)
        features['strict_p8_actual_product_overlap']=features['strict_p8_stellar_and_targeting'] and features['actual_spoc_fraction']<.5
        features['auxiliary_stellar']=aux
        nbpath=P9/'inputs/neighbours'/f'tic{tic}.json'
        if nbpath.exists():
            nb=read(nbpath);features['crowding']=dict(n_sources=(nb.get('gaia') or {}).get('n_within_1arcmin'),
              n_possible_1ppt=(nb.get('gaia') or {}).get('n_neighbours_within_3px_could_make_1ppt'),
              n_vsx=(nb.get('vsx') or {}).get('n_within_1arcmin'))
        features['status']='complete'
        figure(root/'autopsy.png',r,score,t,f,ev,blindroot)
    except Exception as e:
        features.update(status='diagnostic_error',error=f'{type(e).__name__}: {e}')
    A.jdump(root/'diagnostic.json',features)
    print(name,features['status'],flush=True)

def binned_phase(t,f,p,t0,dur):
    ph=(t-t0+p/2)%p-p/2;m=abs(ph)<dur*2
    edges=np.linspace(-2*dur,2*dur,61);counts,_=np.histogram(ph[m],edges);sums,_=np.histogram(ph[m],edges,weights=f[m])
    g=counts>0;centers=(edges[:-1]+edges[1:])/2
    return ph,m,centers[g],sums[g]/counts[g]

def figure(path,r,score,t,f,ev,blindroot):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    p=r['period'];t0=r['epoch_btjd'];d=r['duration_hours']/24
    fig,ax=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    stride=max(1,len(t)//12000);ax[0,0].scatter(t[::stride],1000*(f[::stride]-1),s=1,alpha=.35,color='#315F85')
    ax[0,0].set(xlabel='BTJD',ylabel='Prepared flux (ppt)',title='Blind search input; native 200 s')
    ph,m,bx,by=binned_phase(t,f,p,t0,d)
    ax[0,1].scatter(ph[m]*24,1000*(f[m]-1),s=2,alpha=.12,color='#315F85');ax[0,1].plot(bx*24,1000*(by-1),'o-',ms=3,color='#A73B35')
    ax[0,1].axvspan(-d*12,d*12,color='grey',alpha=.1)
    ax[0,1].set(xlabel='Hours from published transit center',ylabel='Prepared flux (ppt)',title='TRUTH-INFORMED fold; no search rescue')
    es=[e for e in ev['events'] if e.get('observed')]
    for excluded,color,label in [(False,'#2E7952','Kept at truth ephemeris'),(True,'#AC433E','Removed at truth ephemeris')]:
        group=[e for e in es if bool(e.get('excluded'))==excluded and e.get('det_depth_ppt') is not None and e.get('det_depth_err_ppt') is not None]
        ax[1,0].errorbar([e['tc_btjd'] for e in group],[e['det_depth_ppt'] for e in group],
          yerr=[e['det_depth_err_ppt'] for e in group],fmt='.',color=color,label=label,alpha=.65)
    ax[1,0].legend(fontsize=8);ax[1,0].set(xlabel='Event BTJD',ylabel='Event depth (ppt)',title='Counterfactual event audit at published ephemeris')
    sr=read(blindroot/'search/results'/f'tic{int(r["tic_id"])}.json');planets=sr.get('result',{}).get('planets',[])
    ax[1,1].scatter([q['period_days'] for q in planets],[q.get('stitch_snr') or 0 for q in planets],color='#315F85')
    ax[1,1].axvline(p,color='#A73B35',label='Published period');ax[1,1].axhline(7.1,color='grey',ls='--',label='Pre-gate SNR')
    ax[1,1].set(xscale='log',xlabel='Blind accepted period (d)',ylabel='Stitch SNR',title='Every accepted signal on this host');ax[1,1].legend(fontsize=8)
    fig.suptitle(f'{r["truth_id"]} | first termination: {score.get("first_termination")}\nPublished P={p:.6f} d; blind verdict remains locked',fontsize=13)
    fig.savefig(path,dpi=140);plt.close(fig)

def batch():
    import subprocess
    from concurrent.futures import ThreadPoolExecutor,as_completed
    scores=scores_available()
    names=[r['truth_id'] for r in scores if r['eligibility']=='eligible']
    def job(name):
        path=P9/'diagnostics'/slug(name)/'diagnostic.json'
        if path.exists() and read(path).get('status')=='complete':return name,'cached'
        log=P9/'logs'/f'diagnostic_{slug(name)}.log'
        with log.open('w',encoding='utf-8') as f:
            p=subprocess.run([sys.executable,str(Path(__file__)),'--name',name],stdout=f,stderr=subprocess.STDOUT,timeout=1800)
        return name,p.returncode
    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in as_completed([ex.submit(job,n) for n in names]):print(f.result(),flush=True)
    rows=[read(p) for p in (P9/'diagnostics').glob('*/diagnostic.json')]
    write(P9/'results/diagnostic_features.json',rows)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name');a=p.parse_args()
    if a.name:one(a.name)
    else:batch()
