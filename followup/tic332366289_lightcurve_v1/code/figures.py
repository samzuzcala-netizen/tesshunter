import common as C
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np,pandas as pd
from analyze import series_for,fit
from ingest import load
from recipe import GUARD,REF
plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.2,'figure.dpi':100})
D=pd.read_csv(C.WS/'results/depths.csv');E=pd.read_csv(C.WS/'events.csv');EA=E[E.ephemeris=='EA']
names=['PDCSAP','SAP','PIX_OPT','PIX_SMALL','QLP'];labels={'PDCSAP':'TESS-SPOC PDCSAP','SAP':'TESS-SPOC SAP','PIX_OPT':'TESScut optimal, sky subtracted','PIX_SMALL':'TESScut 3x3, sky subtracted','QLP':'QLP detrended'}
def save(fig,name):
    fig.savefig(C.WS/'figures'/name,dpi=135,bbox_inches='tight');plt.close(fig)
def bins(t,y,width):
    finite=np.isfinite(t)&np.isfinite(y);t=t[finite];y=y[finite]
    idx=np.floor(t/width).astype(int);ks=np.unique(idx)
    return np.array([np.mean(t[idx==k]) for k in ks]),np.array([np.mean(y[idx==k]) for k in ks]),np.array([np.std(y[idx==k],ddof=1)/np.sqrt(sum(idx==k)) if sum(idx==k)>1 else np.nan for k in ks])
def event_figures():
    for ev in EA.itertuples():
        if not ev.target_on_science_pixels or ev.sector==77:continue
        s=ev.sector;n=ev.cycle;tc=ev.tc;series,diag=series_for(s)
        fig,axes=plt.subplots(5,1,figsize=(11,10),sharex=True,layout='constrained')
        for name,ax in zip(names,axes):
            ax.axvspan(-C.EA[2]*12,C.EA[2]*12,color='#d97706',alpha=.15)
            edge=C.EA[2]*12+1
            for left,right in [(-edge-5,-edge),(edge,edge+5)]:ax.axvspan(left,right,color='#15803d',alpha=.08)
            ax.axvline((ev.tc_other-tc)*24,color='#7c3aed',ls='--',lw=1);ax.axhline(0,color='0.5',lw=.7)
            ax.set_ylabel('Flux residual\n(ppt)');ax.set_xlim(-7.3,7.3)
            if name not in series:ax.text(.5,.5,labels[name]+' unavailable',transform=ax.transAxes,ha='center');continue
            b=series[name];r=fit(b,tc,C.EA[2],True)
            dr=D[(D.sector==s)&(D.cycle==n)&(D.ephemeris=='EA')&(D.photometry==name)].iloc[0]
            if r['valid']:
                x=(r['t']-tc)*24;y=r['residual_ppt'];good=r['good_mask'];ax.scatter(x[good],y[good],s=3,color='0.65',alpha=.25)
                xx,yy,er=bins(x[good],y[good],max(1/3,b['cadence']*24))
                ax.errorbar(xx,yy,yerr=er,fmt='o',ms=3,color='#1d4ed8',lw=.8)
                model=-dr.depth*r['box'];ax.plot(x,model,color='#c2410c',lw=1.6)
                ax.set_title(f"{labels[name]}: {dr.depth:.2f} ± {dr.error:.2f} ppt; S/N {dr.snr:.2f}",loc='left',fontsize=10)
                ee=np.nan_to_num(er,nan=0);ymin,ymax=np.nanpercentile(np.r_[yy-ee,yy+ee,model],[0,100]);pad=max(3,(ymax-ymin)*.1);ax.set_ylim(ymin-pad,ymax+pad)
            else:
                sel=abs(b['t']-tc)<7.3/24;good=b['good'][sel]&np.isfinite(b['y'][sel]);tt=b['t'][sel];yy=b['y'][sel]
                if good.any():
                    x=(tt[good]-tc)*24;y=(yy[good]/np.median(yy[good])-1)*1000;xx,yy,er=bins(x,y,max(1/3,b['cadence']*24));ax.plot(xx,yy,'o',ms=3,color='0.5')
                ax.set_title(labels[name]+': no valid depth',loc='left',fontsize=10)
                ax.text(.02,.12,r['reason']+'; shown relative to local median only',transform=ax.transAxes,fontsize=9)
        axes[-1].set_xlabel(f'Hours from E_A centre {tc:.6f} BTJD (TDB); violet dashed = E_F centre')
        fig.suptitle(f'TIC 332366289 — s{s}, cycle {n}' + (' — E39 diagnostic, never pooled' if s==84 else '')+'\nOrange: event; green: baseline; violet: E_F. Bins ≥20 min; bars: within-bin SEM; title errors: controls.',fontsize=11)
        save(fig,f'event_s{s:02d}_cycle{n}.png')
def pdc_figures():
    summary=[]
    for s in [57,79,80,84]:
        ev=EA[EA.sector==s].iloc[0];tc=ev.tc;a=load(s);pix=load(s,'pixel');t=a['time'];sel=abs(t-tc)<.35
        crowd=float(a['crowdsap']);flfr=float(a['flfrcsap']);med=np.nanmedian(a['SAP_FLUX'][(a['quality']&191)==0]);scale=med*crowd
        correction=(a['PDCSAP_FLUX']*flfr-(a['SAP_FLUX']-(1-crowd)*med))/scale*1000
        fig,axs=plt.subplots(3,1,figsize=(11,7),sharex=True,layout='constrained')
        xx,yy,er=bins((t[sel]-tc)*24,correction[sel],1/3);offset=np.nanmedian(yy);axs[0].plot(xx,yy-offset,'o-',ms=3,lw=.6)
        axs[0].set_ylabel('PDC − scaled SAP\n(ppt, median removed)')
        p=C.WS/'results'/f'pdc_difference_EA_s{s}_n{int(ev.cycle)}.npz'
        if p.exists():
            b=dict(np.load(p));good=b['good'];x,y,e=bins((b['t'][good]-tc)*24,b['correction_ppt'][good],1/3);axs[1].errorbar(x,y,yerr=e,fmt='o',ms=3)
        else:axs[1].text(.5,.5,'Paired depth unavailable: PDC gap crosses event',ha='center',transform=axs[1].transAxes)
        axs[1].set_ylabel('Local correction\nresidual (ppt)');axs[1].axhline(0,color='0.5',lw=.8)
        selp=abs(pix['time']-tc)<.35;xx,yy,e=bins((pix['time'][selp]-tc)*24,pix['background'][selp],1/3);axs[2].plot(xx,yy,'o-',ms=3,lw=.6,color='#047857');axs[2].set_ylabel('Background\n(e−/s/pixel)')
        for ax in axs:
            ax.axvspan(-C.EA[2]*12,C.EA[2]*12,color='#d97706',alpha=.15);ax.axvline((ev.tc_other-tc)*24,color='#7c3aed',ls='--',lw=.8);ax.set_xlim(-7.3,7.3)
            miss=sel&~np.isfinite(a['PDCSAP_FLUX']);ax.plot((t[miss]-tc)*24,np.full(sum(miss),.03),'|',color='red',transform=ax.get_xaxis_transform())
            scatter=sel&((a['quality']&4096)!=0);ax.plot((t[scatter]-tc)*24,np.full(sum(scatter),.07),'|',color='purple',transform=ax.get_xaxis_transform())
        axs[-1].set_xlabel(f'Hours from E_A {tc:.6f} BTJD (TDB); red ticks PDC missing, purple ticks scattered light')
        fig.suptitle(f's{s}: PDC correction and background'+(' — E39 diagnostic only' if s==84 else '')+'\nTop uses PDC × FLFRCSAP − [SAP − (1−CROWDSAP) × median SAP]. Negative correction deepens a dip.',fontsize=11)
        save(fig,f'pdc_s{s}.png')
        inside=abs(pix['time']-tc)<C.EA[2]/2;out=(abs(pix['time']-tc)>C.EA[2]/2+GUARD)&(abs(pix['time']-tc)<C.EA[2]/2+GUARD+REF)
        summary.append(dict(sector=s,background_first_reference=float(np.nanmedian(pix['background'][out&(pix['time']<tc)])),background_last_reference=float(np.nanmedian(pix['background'][out&(pix['time']>tc)])),background_in=float(np.nanmedian(pix['background'][inside])),raw_sky_correlation=float(np.corrcoef(pix['raw_optimal'][selp],pix['background'][selp])[0,1]),sap_sky_correlation=float(np.corrcoef(a['SAP_FLUX'][sel][np.isfinite(a['SAP_FLUX'][sel])],a['SAP_BKG'][sel][np.isfinite(a['SAP_FLUX'][sel])])[0,1])))
    C.write(C.WS/'results/background_diagnostics.json',summary)
def summary_figures():
    fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for ax,ep in zip(axs,['EA','EF']):
        rows=D[(D.ephemeris==ep)&(D.sector.isin([24,26,51,53,57,79,80]))]
        secs=[24,26,51,53,57,79,80]
        for i,name in enumerate(['SAP','PDCSAP','PIX_OPT']):
            rr=rows[(rows.photometry==name)&rows.valid];xx=[secs.index(s)+(i-1)*.15 for s in rr.sector]
            ax.errorbar(xx,rr.target_depth,yerr=rr.target_error,fmt='o',ms=4,label=name)
        ax.axhline(0,color='0.5',lw=.7);ax.set_xticks(range(len(secs)),[f's{s}' for s in secs]);ax.axvline(3.5,color='0.5',ls=':');ax.set_ylabel('Depth ± calibrated error (ppt, target fraction)');ax.set_title(ep+' ephemeris; earlier epochs | retained events');ax.legend(fontsize=9)
    fig.suptitle('Back-projection at both distinct ephemerides; missing estimates are not zero depths')
    save(fig,'backprojection_depths.png')
    a=dict(np.load(C.WS/'results/joint_period_phase_map.npz'));fig,axs=plt.subplots(1,3,figsize=(15,4.7),layout='constrained')
    extent=[a['periods'][0],a['periods'][-1],(a['t0s'][0]-C.EA[1])*1440,(a['t0s'][-1]-C.EA[1])*1440]
    for ax,key,title in zip(axs,['loglike_gain','pre_loglike_gain','shortfall_sigma'],['All usable SAP epochs: ΔlogL vs zero','Pre-56 SAP epochs: ΔlogL vs zero','Pre-56 shortfall / combined error']):
        im=ax.imshow(a[key],origin='lower',extent=extent,aspect='auto',cmap='viridis');fig.colorbar(im,ax=ax,shrink=.8)
        ax.plot(C.EA[0],0,'rx',ms=7,label='E_A');ax.plot(C.EF[0],(C.EF[1]-C.EA[1])*1440,'w+',ms=8,label='E_F');ax.set_xlabel('Period (days)');ax.set_ylabel('T0 − E_A T0 (minutes)');ax.set_title(title,fontsize=10);ax.ticklabel_format(axis='x',style='plain',useOffset=False);ax.legend(fontsize=8)
    fig.suptitle('Bounded joint period–phase map; fixed E_A duration, common nonnegative depth; no trials-calibrated significance')
    save(fig,'joint_period_phase_map.png')
    aliases=pd.read_csv(C.WS/'results/aliases.csv');fig,axs=plt.subplots(2,1,figsize=(11,7),sharex=True,layout='constrained')
    for valid,color,label in [(True,'#2563eb','not excluded on tested grid'),(False,'#dc2626','disfavoured at ≥3 calibrated σ')]:
        rr=aliases[aliases.survives==valid];axs[0].scatter(rr.period,rr.min_shortfall_sigma,s=12,color=color,label=label);axs[1].scatter(rr.period,rr.nominal_n,s=12,color=color)
    axs[0].axhline(3,ls='--',color='0.3');axs[0].set_ylabel('Lowest tested shortfall\n(calibrated error units)');axs[0].legend(fontsize=9);axs[1].set_ylabel('Other usable predicted epochs\n(nominal timing)');axs[1].set_xlabel('Conditional alias period (days; log scale)')
    for ax in axs:ax.set_xscale('log');ax.axvline(C.EA[0],color='#7c3aed',ls=':')
    fig.suptitle('Conditional s57+s80 aliases: Δt/n, 1–100 d\nOnly s57 meets the independent-support rule; these are hypotheses, not measured periods. E39 excluded from all pooled tests.',fontsize=11)
    save(fig,'conditional_aliases.png')
def controls_figure():
    ct=pd.read_csv(C.WS/'results/controls.csv');inj=pd.read_csv(C.WS/'results/injections.csv')
    fig,axs=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    for ax,s in zip(axs[0],[57,79,80]):
        for name in ['SAP','PDCSAP','PIX_OPT']:
            v=ct[(ct.sector==s)&(ct.photometry==name)&(ct.ephemeris=='EA')&ct.valid].depth
            ax.hist(v,bins=12,histtype='step',lw=1.5,label=f'{name}, n={len(v)}')
        ax.axvline(0,color='0.5',lw=.7);ax.set_title(f's{s}: control depths');ax.set_xlabel('Depth (ppt)');ax.legend(fontsize=8)
    for ax,name in zip(axs[1],['SAP','PIX_OPT','PIX_SMALL']):
        for amp,c in [(3.76,'#2563eb'),(6.5,'#d97706')]:
            rr=inj[(inj.photometry==name)&(inj.injected_ppt==amp)&inj.valid];ax.scatter(rr.sector,rr.incremental_ppt-amp,s=9,alpha=.5,color=c,label=f'{amp} ppt')
        ax.axhline(0,color='0.5');ax.set_title(name+' incremental injection bias');ax.set_xlabel('Sector');ax.set_ylabel('Recovered increment − input (ppt)');ax.legend(fontsize=8)
    fig.suptitle('Empirical controls and raw injections; same local recipe, no detrending adjustment')
    save(fig,'controls_injections.png')
if __name__=='__main__':event_figures();pdc_figures();summary_figures();controls_figure();print('All figures generated')
