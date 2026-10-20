import common as C
from ingest import load,products,match_time
from recipe import measure,uncertainty,aggregate,box_overlap,GUARD,REF
import numpy as np,pandas as pd
def series_for(s):
    series={}; diag={}
    if (C.BIG/'arrays'/f'spoc_{s}.npz').exists():
        a=load(s);t=a['time'];q=a['quality'];good=(q&191)==0;dumps=t[(q&32)!=0]
        base=dict(t=t,good=good,dumps=dumps,cadence=float(a['cadence']),exposure=float(a['exposure_span']),crowd=float(a['crowdsap']))
        for kind,key in [('SAP','SAP_FLUX'),('PDCSAP','PDCSAP_FLUX')]:series[kind]={**base,'y':a[key]}
        diag=a
    if (C.BIG/'arrays'/f'pixel_{s}.npz').exists():
        pix=load(s,'pixel');t=pix['time'];good=pix['good'];q=pix['quality']|pix['spoc_quality']
        geo=next(r for r in C.json.loads((C.WS/'inputs/ccd_geometry.json').read_text()) if r['sector']==s)
        col,row=geo['target_ccd'];active=45<=col<=2092 and 1<=row<=2048
        if not active:good=good&False
        base=dict(t=t,good=good,dumps=t[(q&32)!=0],cadence=float(pix['cadence']),exposure=float(pix['exposure_span']),crowd=float(pix['crowdsap']))
        if np.isfinite(pix['optimal']).any():series['PIX_OPT']={**base,'y':pix['optimal']}
        series['PIX_SMALL']={**base,'y':pix['small']}
        if not diag:diag=dict(time=t,quality=q,SAP_BKG=pix['background'])
    if (C.BIG/'arrays'/f'qlp_{s}.npz').exists() and s!=80:
        a=load(s,'qlp');t=a['time'];q=a['quality'];ignore=4096 if s<56 else 1073741824
        good=(q&~ignore)==0;timemeta={}
        if 'SAP' in series:
            li,ok,dt=match_time(t,series['SAP']['t'],float(a['cadence'])*.5)
            timemeta=dict(n=len(t),matched=int(ok.sum()),dt_min_s=float(np.min(dt[ok])*86400),dt_max_s=float(np.max(dt[ok])*86400))
            good &= ok;t=series['SAP']['t'][li]
        base=dict(t=t,good=good,dumps=t[(q&32)!=0],cadence=float(a['cadence']),exposure=float(a['exposure_span']),crowd=1.)
        series['QLP']={**base,'y':a['DET_FLUX']}
        C.write(C.WS/'inputs'/f'qlp_timing_s{s}.json',timemeta)
    return series,diag
def fit(b,tc,d,details=False,y=None,good=None):
    return measure(b['t'],b['y'] if y is None else y,b['good'] if good is None else good,tc,d,b['cadence'],b['exposure'],b['dumps'],details)
def control_times(t):
    span=C.EA[2]/2+GUARD+REF
    vals=np.arange(t[0]+span,t[-1]-span,.65)
    for P,T,d in [C.EA,C.EF]:
        phase=(vals-T+P/2)%P-P/2
        vals=vals[abs(phase)>2*span]
    return vals[:60]
def distance(t,tc):return float(np.min(abs(t-tc))) if len(t) else np.nan
def add_error(rec,ctrl,crowd=1):
    if rec['valid']:
        rec['error']=uncertainty(rec,ctrl);rec['snr']=rec['depth']/rec['error']
        rec['empirical_null_p']=(1+sum(r['depth']>=rec['depth'] for r in ctrl if r['valid']))/(1+sum(r['valid'] for r in ctrl))
        rec['target_depth']=rec['depth']/crowd;rec['target_error']=rec['error']/crowd
    return rec
def main():
    seal=C.json.loads((C.WS/'inputs/premeasurement_addendum_seal.json').read_text())
    assert seal['config_sha256']==C.sha(C.WS/'config.json') and seal['plan_sha256']==C.sha(C.WS/'PLAN.md')
    events=[];depths=[];controls=[];injections=[];pdc=[];ctab=[]
    for s in C.SECTORS:
        C.check();series,diag=series_for(s)
        if not series:continue
        main=series.get('SAP',series['PIX_SMALL']);t=main['t'];centres=control_times(t);ctrl={}
        for label,(P,T,d) in [('EA',C.EA),('EF',C.EF)]:
            for name,b in series.items():
                rr=[dict(sector=s,photometry=name,ephemeris=label,**fit(b,float(tc),d)) for tc in centres]
                ctrl[label,name]=rr;controls.extend(rr)
                ds=np.array([r['depth'] for r in rr if r['valid']]);errs=np.array([r['white'] for r in rr if r['valid']])
                ctab.append(dict(sector=s,photometry=name,ephemeris=label,n_attempted=len(rr),n_valid=len(ds),mean=np.mean(ds) if len(ds) else np.nan,sd=np.std(ds,ddof=1) if len(ds)>1 else np.nan,median_white=np.median(errs) if len(errs) else np.nan))
            for n in range(int(np.ceil((t[0]-d-T)/P)),int(np.floor((t[-1]+d-T)/P))+1):
                tc=T+n*P;allin=abs(diag['time']-tc)<=d/2;q=diag['quality']
                r=dict(sector=s,cycle=n,ephemeris=label,tc=tc,tc_other=(C.EF[1]+n*C.EF[0] if label=='EA' else C.EA[1]+n*C.EA[0]),cadence_s=main['cadence']*86400,products=';'.join(series),diagnostic=(s==84),n_frames=int(sum(allin)),quality_bad_fraction=float(np.mean((q[allin]&191)!=0)) if sum(allin) else np.nan,scattered_light_fraction=float(np.mean((q[allin]&4096)!=0)) if sum(allin) else np.nan,edge_distance_d=min(abs(tc-t[0]),abs(t[-1]-tc)),momentum_distance_d=distance(diag['time'][(q&32)!=0],tc),pdc_missing_distance_d=distance(diag['time'][~np.isfinite(diag.get('PDCSAP_FLUX',np.ones(len(q))))],tc))
                r['target_on_science_pixels']=s not in [25,40,50,52]
                gaps=np.where(np.diff(t)>2.5*main['cadence'])[0]
                r['data_gap_distance_d']=distance(np.r_[t[gaps],t[gaps+1]],tc)
                for name,b in series.items():
                    m=fit(b,tc,d);m.update(sector=s,cycle=n,ephemeris=label,photometry=name,diagnostic=(s==84))
                    if not r['target_on_science_pixels']:m['reason']='target outside active CCD science pixels; not stellar photometry'
                    crowd=b['crowd'] if name in ['SAP','PIX_OPT'] else 1.
                    add_error(m,ctrl[label,name],crowd);depths.append(m)
                    if name==('SAP' if 'SAP' in series else 'PIX_SMALL'):r.update(coverage=m['coverage'],recipe_valid=m['valid'],reason=m['reason'])
                    detail=fit(b,tc,d,True)
                    if detail['valid']:
                        arrays={k:v for k,v in detail.items() if isinstance(v,np.ndarray)}
                        np.savez_compressed(C.WS/'results'/f'window_{label}_s{s}_n{n}_{name}.npz',**arrays)
                events.append(r)
        # Injections at fixed inherited amplitudes, into raw series only, primary duration.
        for name in ['SAP','PIX_OPT','PIX_SMALL']:
            if name not in series:continue
            b=series[name]
            for orig in ctrl['EA',name]:
                if not orig['valid']:continue
                tc=orig['tc'];shape=box_overlap(b['t'],tc,C.EA[2],b['exposure'])
                for amp in [3.76,6.5]:
                    inj=fit(b,tc,C.EA[2],y=b['y']*(1-amp/1000*shape))
                    injections.append(dict(sector=s,photometry=name,tc=tc,injected_ppt=amp,recovered_ppt=inj.get('depth'),original_ppt=orig['depth'],incremental_ppt=inj.get('depth',np.nan)-orig['depth'],valid=inj['valid']))
        # Paired common finite masks retain SAP/PDC covariance; baseline independently fit.
        if 'SAP' in series:
            sap=series['SAP'];pdc_b=series['PDCSAP'];good=sap['good']&np.isfinite(sap['y'])&np.isfinite(pdc_b['y']);crowd=sap['crowd']
            for label,(_,_,d) in [('EA',C.EA),('EF',C.EF)]:
                diffs=[]
                for tc in centres:
                    a=fit(sap,tc,d,good=good);b=fit(pdc_b,tc,d,good=good)
                    if a['valid'] and b['valid']:diffs.append(dict(valid=True,depth=b['depth']-a['depth']/crowd,white=np.hypot(b['white'],a['white']/crowd),effective_n=a['effective_n'],tc=tc))
                for ev in [r for r in events if r['sector']==s and r['ephemeris']==label]:
                    tc=ev['tc'];a=fit(sap,tc,d,good=good);b=fit(pdc_b,tc,d,good=good)
                    row=dict(sector=s,cycle=ev['cycle'],ephemeris=label,tc=tc,n_controls=len(diffs),valid=a['valid'] and b['valid'])
                    if row['valid']:
                        aa=fit(sap,tc,d,True,good=good);bb=fit(pdc_b,tc,d,True,good=good)
                        delta=bb['residual_ppt']-aa['residual_ppt']/crowd
                        oot=aa['out_mask'];inn=aa['in_mask'];xx=aa['t']-tc
                        X=np.column_stack((np.ones(sum(oot)),xx[oot]));qi=aa['box'][inn];den=np.sum(qi**2)
                        v=np.sum(qi[:,None]*np.column_stack((np.ones(sum(inn)),xx[inn])),axis=0)/den
                        paired_white=np.std(delta[oot],ddof=2)*np.sqrt(1/den+v@np.linalg.inv(X.T@X)@v)
                        row.update(depth=b['depth']-a['depth']/crowd,white=paired_white,effective_n=a['effective_n'])
                        row['error']=uncertainty(row,diffs);row['snr']=row['depth']/row['error'];row['sap_depth_target']=a['depth']/crowd;row['pdc_depth']=b['depth']
                        np.savez_compressed(C.WS/'results'/f'pdc_difference_{label}_s{s}_n{ev["cycle"]}.npz',t=aa['t'],correction_ppt=bb['residual_ppt']-aa['residual_ppt']/crowd,good=aa['good_mask'],in_mask=aa['in_mask'],out_mask=aa['out_mask'])
                    else:row['reason']=a['reason']+';'+b['reason']
                    pdc.append(row)
        print('Measured',s,[(r['photometry'],round(r.get('depth',np.nan),2),round(r.get('error',np.nan),2),r['reason']) for r in depths if r['sector']==s and r['ephemeris']=='EA'],flush=True)
        for name,rows in [('depths',depths),('controls',controls),('injections',injections),('pdc_diagnostics',pdc),('control_summary',ctab)]:
            pd.DataFrame(rows).to_csv(C.WS/'results'/f'{name}.csv',index=False);C.write(C.WS/'results'/f'{name}.json',rows)
        pd.DataFrame(events).to_csv(C.WS/'events.csv',index=False)
    summary={}
    for label in ['EA','EF']:
        summary[label]={}
        for name in ['SAP','PDCSAP','PIX_OPT','PIX_SMALL','QLP']:
            rr=[r for r in depths if r['sector'] in [57,79,80] and r['photometry']==name and r['ephemeris']==label]
            rr=[{**r,'depth':r.get('target_depth',np.nan),'error':r.get('target_error',np.nan)} for r in rr]
            summary[label][name]=aggregate(rr)
    C.write(C.WS/'results/retained_joint.json',summary);print('JOINT',summary)
if __name__=='__main__':main()
