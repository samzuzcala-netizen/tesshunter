"""Fixed ephemeris checks on all 22 cached QLP sectors, including older data."""
from run_followup import *

def combine(vals):
    a=[v for v in vals if v.get('usable') and np.isfinite(v.get('error',np.nan)) and v['error']>0]
    if not a:return {'n':0}
    d=np.array([v['depth'] for v in a]);se=np.array([v['error'] for v in a]);w=1/se**2
    mean=float(w@d/w.sum());err=float(1/np.sqrt(w.sum()))
    contribution=(np.maximum(d,0)/se)**2
    j=int(np.argmax(contribution));wt=w.copy();wt[j]=0
    return {'n':len(a),'depth_ppt':mean*1000,'error_ppt':err*1000,'snr':mean/err,
        'chi2':float(np.sum(((d-mean)/se)**2)),'p_constant':float(stats.chi2.sf(np.sum(((d-mean)/se)**2),len(a)-1)),
        'top_share_positive_snr2':float(contribution[j]/max(contribution.sum(),1e-20)),
        'snr_without_top':float(wt@d/np.sqrt(wt.sum())) if wt.sum() else None,
        'n_positive':int((d>0).sum())}

def main():
    rows=[];metadata=[];periodograms=[];data=[]
    flat=np.load(P8/'tls'/(KEY+'_lc.npz'))
    index=read(REPO/'data/survey/audit_lc/tic404927114/index.json')
    fig,axes=plt.subplots(6,4,figsize=(16,18),layout='constrained');axes=axes.ravel()
    for j,item in enumerate(index['products']):
        sec=item['sector'];_,lc,h0,h1=read_lc(sec);t=lc['TIME']
        mask=17087 | (2**30 if sec>=56 else 2**12)
        good=np.isfinite(t)&((lc['QUALITY']&mask)==0)
        cols=[k for k in ['SAP_FLUX','DET_FLUX','KSPSAP_FLUX','SYS_RM_FLUX','DET_FLUX_SML','DET_FLUX_LAG'] if k in lc]
        metadata.append({'sector':sec,'cadence_s':item['cadence_s'],'n':len(t),'n_good':int(good.sum()),
            'bestap':h1.get('BESTAP'),'smallap':h1.get('SMALLAP'),'largeap':h1.get('LARGEAP'),
            'quality_values':np.unique(lc['QUALITY'],return_counts=True),'time_start':np.nanmin(t),'time_end':np.nanmax(t)})
        plotcol='DET_FLUX' if 'DET_FLUX' in lc else 'KSPSAP_FLUX'
        yy=lc[plotcol];ax=axes[j]
        ax.plot(t[good],yy[good],'.',ms=.5,alpha=.35,color='#386a91',rasterized=True)
        for n,tc in centres(t,E['period'],E['epoch']):ax.axvline(tc,color='#c13f42',lw=1)
        ax.set_title(f'S{sec} ({item["cadence_s"]:g} s)');ax.set_ylim(1-5*mad(yy[good]),1+5*mad(yy[good]))
        ax.tick_params(labelsize=7)
        for label,e in EPH.items():
            ctr=np.linspace(np.nanmin(t)+.5,np.nanmax(t)-.5,120)
            ctr=ctr[np.abs(phase(ctr,e['period'],e['epoch']))>.8]
            for col in cols:
                y=lc[col];y=y/np.nanmedian(y[good])
                controls=[measure_series(t,y,c,e['duration'],good) for c in ctr]
                values=[v['depth'] for v in controls if v.get('usable')]
                emp=max(float(mad(values)),float(np.std(values,ddof=1))) if len(values)>5 else np.nan
                for n,tc in centres(t,e['period'],e['epoch']):
                    v=measure_series(t,y,tc,e['duration'],good)
                    v.update(sector=sec,cycle=n,tc_btjd=tc,ephemeris=label,column=col,old=bool(sec<56),
                      control_sigma=emp,cadence_s=item['cadence_s'])
                    if v['usable']:v['error']=max(v['block_error'],emp)
                    rows.append(v)
        # Period/alias diagnostics use hourly bins, robustly clipped at 5 MAD.
        lscol='SYS_RM_FLUX' if 'SYS_RM_FLUX' in lc else 'SAP_FLUX'
        for name in [lscol,'SAP_BKG']:
            if name not in lc:continue
            y=lc[name];gg=good&np.isfinite(y);med=np.nanmedian(y[gg]);sc=mad(y[gg]);gg &= np.abs(y-med)<5*sc
            if gg.sum()<100:continue
            bins=np.floor((t[gg]-np.nanmin(t))*24).astype(int)
            tab=pd.DataFrame({'bin':bins,'time':t[gg],'y':y[gg]}).groupby('bin').median()
            period=np.linspace(.3,40,7000);power=LombScargle(tab.time,tab.y).power(1/period)
            k=int(np.argmax(power));periodograms.append({'sector':sec,'column':name,'best_period_days':period[k],
                'power':power[k],'power_at_candidate':float(LombScargle(tab.time,tab.y).power(1/E['period']))})
            data.append((sec,name,period,power))
        # Additional eclipses at half phase / P/3 and a 27.3-day systematic hypothesis.
        for name,p,epoch in [('P_half_extra',E['period'],E['epoch']+E['period']/2),
                             ('P_third_extra1',E['period'],E['epoch']+E['period']/3),
                             ('P_third_extra2',E['period'],E['epoch']+2*E['period']/3)]:
            for n,tc in centres(t,p,epoch):
                y=lc[plotcol];v=measure_series(t,y,tc,E['duration'],good)
                v.update(sector=sec,cycle=n,tc_btjd=tc,ephemeris=name,column=plotcol,old=bool(sec<56))
                if v['usable']:v['error']=v['block_error']
                rows.append(v)
    for ax in axes[len(index['products']):]:ax.axis('off')
    fig.suptitle('All cached QLP sectors; red lines are the fixed physical-fit predictions\nS27-S39 are additional observing epochs, excluded from the frozen P8 search',fontsize=15)
    fig.supxlabel('BTJD = BJD (TDB) - 2457000')
    fig.supylabel('Normalized QLP corrected flux')
    fig.savefig(FIG/'all_qlp_sectors.png',dpi=145);plt.close(fig)
    pd.DataFrame(rows).to_csv(OUT/'qlp_events.csv',index=False)
    save(OUT/'qlp_metadata.json',metadata)
    summary={}
    for old in [False,True]:
        for label in EPH:
            for col in ['SAP_FLUX','DET_FLUX','KSPSAP_FLUX','SYS_RM_FLUX']:
                v=[r for r in rows if r['old']==old and r['ephemeris']==label and r['column']==col]
                summary[f'{"old" if old else "P8"}_{label}_{col}']=combine(v)
    save(OUT/'qlp_summary.json',summary);save(OUT/'periodograms.json',periodograms)
    fig,ax=plt.subplots(2,1,figsize=(12,7),layout='constrained')
    for sec,col,p,power in data:
        if sec<56:continue
        ax[int(col=='SAP_BKG')].plot(p,power,label=f'S{sec}',lw=.8,alpha=.8)
    for a,title in zip(ax,['QLP systematics-removed flux (stellar variability retained)','QLP background']):
        a.axvline(E['period'],c='black',ls='--');a.axvline(E['period']/2,c='grey',ls=':');a.set_title(title)
        a.set(xlabel='Period (days)',ylabel='Lomb-Scargle power',xlim=(0,40));a.legend(ncol=6,fontsize=7)
    fig.savefig(FIG/'variability_and_background_periods.png',dpi=160);plt.close(fig)
    # Actual orbital labels and gap timing, with candidate phase drift recorded.
    timing=[]
    for m in metadata:
        sec=m['sector'];_,lc,_,_=read_lc(sec);t=lc['TIME'];ft=np.isfinite(t)
        gaps=np.flatnonzero(np.diff(t)>0.2);edges=np.r_[t[ft][0],t[ft][-1],t[gaps],t[gaps+1]]
        orbit=lc.get('ORBITID')
        for n,tc in centres(t,E['period'],E['epoch']):
            k=np.nanargmin(abs(t-tc));timing.append({'sector':sec,'cycle':n,'tc':tc,'nearest_gap_or_edge_days':float(np.min(abs(edges-tc))),
              'nearest_cadence_minutes':float(abs(t[k]-tc)*1440),'orbit_id':float(orbit[k]) if orbit is not None else None,
              'phase_13_7_days':float((tc-E['epoch'])/13.7%1),'phase_27_32166_days':float((tc-E['epoch'])/27.321661%1)})
    pd.DataFrame(timing).to_csv(OUT/'timing_and_gaps.csv',index=False)
    print(json.dumps({k:v for k,v in summary.items() if 'physical_fit' in k and v['n']},indent=2))

if __name__=='__main__':main()
