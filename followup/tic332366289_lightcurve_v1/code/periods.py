import common as C
import numpy as np,pandas as pd
from analyze import series_for,fit,add_error
from recipe import aggregate,uncertainty,aliases
CFG=C.json.loads((C.WS/'config.json').read_text())
DEPTHS=C.json.loads((C.WS/'results/depths.json').read_text())
CTRLS=C.json.loads((C.WS/'results/controls.json').read_text())
SERIES={s:series_for(s)[0] for s in C.SECTORS}
CTRL={(s,l):[r for r in CTRLS if r['sector']==s and r['photometry']=='SAP' and r['ephemeris']==l] for s in C.SECTORS for l in ['EA','EF']}
def raw(s,tc,d=C.EA[2],label='EA'):
    b=SERIES[s].get('SAP')
    if b is None:return dict(valid=False,reason='No stellar SAP product')
    r=fit(b,tc,d);r.update(sector=s,tc=tc)
    if r['valid']:
        r['error']=uncertainty(r,CTRL[s,label]);r['depth']/=b['crowd'];r['error']/=b['crowd']
        r['valid']=bool(np.isfinite(r['error']))
    return r
def epochs(P,T,d=C.EA[2],sectors=None):
    for s in C.SECTORS if sectors is None else sectors:
        if 'SAP' not in SERIES[s]:continue
        t=SERIES[s]['SAP']['t']
        for k in range(int(np.ceil((t[0]-d/2-T)/P)),int(np.floor((t[-1]+d/2-T)/P))+1):yield s,k,T+k*P
def ref_depth(sectors,label='EA'):
    rr=[r for r in DEPTHS if r['sector'] in sectors and r['photometry']=='SAP' and r['ephemeris']==label]
    return aggregate([{**r,'depth':r.get('target_depth',np.nan),'error':r.get('target_error',np.nan)} for r in rr])
def supported():
    sectors=[];rows=[]
    for s in [57,79,80]:
        a=next(r for r in DEPTHS if r['sector']==s and r['photometry']=='SAP' and r['ephemeris']=='EA')
        b=next(r for r in DEPTHS if r['sector']==s and r['photometry']=='PIX_OPT' and r['ephemeris']=='EA')
        discrepancy=abs(a['target_depth']-b['target_depth'])/np.hypot(a['target_error'],b['target_error'])
        yes=a['snr']>=2.5 and b['snr']>=2 and discrepancy<3
        rows.append(dict(sector=s,sap_snr=a['snr'],pixel_snr=b['snr'],discrepancy_sigma=discrepancy,supported=yes))
        if yes:sectors.append(s)
    C.write(C.WS/'results/independent_support.json',rows);return sectors
def fixed_backprojection():
    out={}
    for label,(P,T,d) in [('EA',C.EA),('EF',C.EF)]:
        ref=ref_depth([57,79,80],label);rr=[raw(s,t,d,label) for s,k,t in epochs(P,T,d) if s<56 or s in [77,78]]
        joint=aggregate(rr);joint['shortfall_sigma']=(ref['depth']-joint['depth'])/np.hypot(ref['error'],joint['error'])
        out[label]=dict(reference=ref,backprojected=joint,per_epoch=rr)
    C.write(C.WS/'results/backprojection.json',out);print('Backprojection',out,flush=True)
def map_likelihood():
    cfg=CFG['map'];ps=np.linspace(cfg['P_min'],cfg['P_max'],cfg['nP']);ts=np.linspace(cfg['T0_min'],cfg['T0_max'],cfg['nT0'])
    arrays={k:np.full((len(ts),len(ps)),np.nan) for k in ['depth','error','loglike_gain','n','pre_depth','pre_error','pre_loglike_gain','pre_n','shortfall_sigma']}
    reference=ref_depth([57,79,80])
    for i,T in enumerate(ts):
        C.check()
        for j,P in enumerate(ps):
            rr=[raw(s,tc) for s,k,tc in epochs(P,T) if s!=84]
            allr=aggregate(rr);pre=aggregate([r for r in rr if r['sector']<56])
            for prefix,r in [('',allr),('pre_',pre)]:
                arrays[prefix+'depth'][i,j]=r['depth'];arrays[prefix+'error'][i,j]=r['error'];arrays[prefix+'n'][i,j]=r['n']
                # improvement against zero, one common nonnegative depth
                arrays[prefix+'loglike_gain'][i,j]=.5*max(0,r['snr'])**2 if r['n'] else np.nan
            if pre['n']:arrays['shortfall_sigma'][i,j]=(reference['depth']-pre['depth'])/np.hypot(reference['error'],pre['error'])
        if i%20==0:print('Map row',i,'/',len(ts),flush=True)
    np.savez_compressed(C.WS/'results/joint_period_phase_map.npz',periods=ps,t0s=ts,**arrays)
    idx=np.unravel_index(np.nanargmax(arrays['loglike_gain']),arrays['n'].shape)
    summary=dict(best_period=ps[idx[1]],best_t0=ts[idx[0]],best_depth=arrays['depth'][idx],best_error=arrays['error'][idx],best_n=arrays['n'][idx],best_loglike_gain=arrays['loglike_gain'][idx],n_range=[np.nanmin(arrays['n']),np.nanmax(arrays['n'])],pre_shortfall_range=[np.nanmin(arrays['shortfall_sigma']),np.nanmax(arrays['shortfall_sigma'])],all_map_excludes_reference=bool(np.nanmin(arrays['shortfall_sigma'])>=3),trials=len(ps)*len(ts),calibrated_significance=False)
    C.write(C.WS/'results/map_summary.json',summary);print('Map',summary,flush=True)
def alias_test():
    support=supported();conditional=len(support)<2
    # This conditional coverage exercise does not confer support on the anchors.
    anchors=[57,80] if conditional else [min(support),max(support)]
    anchorrows=[next(r for r in DEPTHS if r['sector']==s and r['photometry']=='SAP' and r['ephemeris']=='EA') for s in anchors]
    t1,t2=[r['tc'] for r in anchorrows];ref=ref_depth(anchors);ns,ps=aliases(t1,t2)
    offsets=np.array([0,-.5,-.25,.25,.5])*C.EA[2]
    out=[];nominal_events=[]
    for ii,(n,P) in enumerate(zip(ns,ps)):
        C.check();variants=[]
        for da in offsets:
            for db in offsets:
                pp=(t2+db-t1-da)/n;tt=t1+da
                rr=[];diag84=[]
                for s,k,tc in epochs(pp,tt):
                    if any(abs(tc-t)<C.EA[2] for t in [t1,t2]):continue
                    r=raw(s,tc)
                    r.update(alias_n=int(n),P=pp,cycle=k,diagnostic=s==84)
                    if s==84:diag84.append(r)
                    else:rr.append(r)
                    if da==0 and db==0:nominal_events.append(r)
                joint=aggregate(rr)
                z=(ref['depth']-joint['depth'])/np.hypot(ref['error'],joint['error']) if joint['n'] else 0.
                variants.append(dict(da=da,db=db,P=pp,T0=tt,joint=joint,shortfall_sigma=z,diagnostic84=aggregate(diag84)))
                # Once one admissible timing variant survives, exclusion is impossible.
                if z<3:break
            if variants[-1]['shortfall_sigma']<3:break
        best=min(variants,key=lambda r:r['shortfall_sigma']);nom=variants[0]
        row=dict(n=int(n),period=float(P),conditional=conditional,anchor_sectors=';'.join(map(str,anchors)),n_variants=len(variants),nominal_n=nom['joint']['n'],nominal_depth=nom['joint']['depth'],nominal_error=nom['joint']['error'],nominal_shortfall_sigma=nom['shortfall_sigma'],min_shortfall_sigma=best['shortfall_sigma'],best_tested_period=best['P'],best_tested_t0=best['T0'],survives=best['shortfall_sigma']<3,diagnostic84_depth=nom['diagnostic84']['depth'],diagnostic84_error=nom['diagnostic84']['error'])
        out.append(row)
        if ii%25==0:
            print('Aliases',ii+1,'/',len(ns),'survivors',sum(r['survives'] for r in out),flush=True)
            pd.DataFrame(out).to_csv(C.WS/'results/aliases.csv',index=False)
    pd.DataFrame(out).to_csv(C.WS/'results/aliases.csv',index=False);C.write(C.WS/'results/aliases.json',out)
    pd.DataFrame(nominal_events).to_csv(C.WS/'results/alias_nominal_epochs.csv',index=False)
    summary=dict(conditional=conditional,supported_sectors=support,anchors=anchors,reference=ref,n_tested=len(out),n_surviving=sum(r['survives'] for r in out),surviving_periods=[r['period'] for r in out if r['survives']],eighteen_day=next(r for r in out if r['n']==33),timing_grid='5x5 endpoint offsets; early exit only on survival; finite grid is not proof of continuous exclusion')
    C.write(C.WS/'results/alias_summary.json',summary);print('Alias summary',summary,flush=True)
if __name__=='__main__':
    import sys
    if sys.argv[1]=='map':supported();fixed_backprojection();map_likelihood()
    else:alias_test()
