"""Combine registered pixel evidence and make scientific diagnostic figures."""
from run_followup import *

def binned(t,y,width=.5/24):
    finite=np.isfinite(t)&np.isfinite(y);t=t[finite];y=y[finite]
    if not len(t):return np.array([]),np.array([])
    df=pd.DataFrame({'b':np.floor(t/width),'t':t,'y':y}).groupby('b').mean()
    # Empty bins remain NaN so plot lines cannot imply measurements in gaps.
    df=df.reindex(np.arange(df.index.min(),df.index.max()+1))
    return df.t.values,df.y.values

def main():
    metas=[read(p) for p in sorted(OUT.glob('s???.json'))]
    arrays={m['sector']:np.load(OUT/f's{m["sector"]:03d}_images.npz') for m in metas}
    usable=[(m,r) for m in metas for r in m['events'] if r['usable']]
    event_table=[]
    for m in metas:
        for r in m['events']:
            v={k:v for k,v in r.items() if not isinstance(v,dict)}
            v.update(target_reference_flux=m['reference_flux_target_e_s'])
            event_table.append(v)
    pd.DataFrame(event_table).to_csv(OUT/'pixel_events.csv',index=False)
    amplitudes=np.array([r['depth_e_s']/m['reference_flux_target_e_s']*1000 for m,r in usable])
    errors=np.array([r['empirical_error_e_s']/m['reference_flux_target_e_s']*1000 for m,r in usable])
    weights=1/errors**2;mean=float(weights@amplitudes/weights.sum());error=float(1/np.sqrt(weights.sum()))
    leave=[]
    for i,(m,r) in enumerate(usable):
        w=weights.copy();w[i]=0
        leave.append({'sector':m['sector'],'cycle':r['cycle'],'depth_ppt':float(w@amplitudes/w.sum()),'error_ppt':float(1/np.sqrt(w.sum()))})
    # Sky maps use a common target-flux unit. No centroid vectors in detector
    # coordinates are averaged across cameras/orientations.
    numer=np.zeros(2025);denom=np.zeros(2025);stack_terms=[]
    for m in metas:
        aa=arrays[m['sector']];events=[r for r in m['events'] if r['usable']]
        if not events:continue
        factor=1000/m['reference_flux_target_e_s'];control=aa['control_maps']*factor
        scatter=np.std(control,axis=0,ddof=1)
        # Formal floor and additional temporal error inflation per event.
        for r in events:
            white=np.sqrt(r['norm_w2']/aa['grid_den'])*factor
            err=np.maximum(scatter,white)
            err*=max(1,(r.get('series_block_error_e_s') or 0)/r['white_error_e_s'])
            w=1/err**2;data=aa['maps'][r['map_index']]*factor
            numer+=w*data;denom+=w
            stack_terms.append((m,r,w,control))
    snr=numer/np.sqrt(denom);depth=numer/denom
    offsets=arrays[metas[0]['sector']]['skyoff']*21
    within=np.hypot(offsets[:,0],offsets[:,1])<=90
    peak=int(np.argmax(np.where(within,snr,-np.inf)))
    # Same sector events use pairs separated by their real elapsed time when possible.
    nulls=np.zeros((CFG['null_stacks'],2025));null_target=np.zeros(CFG['null_stacks'])
    for m in metas:
        terms=[z for z in stack_terms if z[0]['sector']==m['sector']]
        if not terms:continue
        control=terms[0][3];tc=arrays[m['sector']]['control_centres'];inds=RNG.integers(0,len(tc),CFG['null_stacks'])
        if len(terms)>1:
            lag=terms[1][1]['tc_btjd']-terms[0][1]['tc_btjd']
            pairs=[]
            for i,c in enumerate(tc):
                j=int(np.argmin(abs(tc-(c+lag))))
                if abs(tc[j]-c-lag)<.5:pairs.append((i,j))
            picks=np.array(pairs)[RNG.integers(0,len(pairs),CFG['null_stacks'])] if pairs else np.column_stack([inds,RNG.integers(0,len(tc),CFG['null_stacks'])])
        else:picks=inds[:,None]
        for j,(_,r,w,ctrl) in enumerate(terms):nulls+=ctrl[picks[:,j]]*w[None,:]
    nullsnr=nulls/np.sqrt(denom)[None,:]
    nullmax=np.max(nullsnr[:,within],axis=1)
    global_p=float((1+np.sum(nullmax>=snr[peak]))/(1+len(nullmax)))
    target_index=int(np.argmin(np.sum(offsets**2,axis=1)))
    control_p=float((1+np.sum(nullsnr[:,target_index]>=snr[target_index]))/(1+len(nullmax)))
    np.savez_compressed(OUT/'stacked_localization.npz',snr=snr,depth_ppt=depth,error_ppt=1/np.sqrt(denom),offsets_arcsec=offsets,
         null_max_snr=nullmax,null_target_snr=nullsnr[:,target_index],peak_index=peak)
    summary={'n_events':len(usable),'target_depth_ppt':mean,'target_error_ppt':error,'target_snr':mean/error,
        'target_chi2_constant':float(np.sum(((amplitudes-mean)/errors)**2)),
        'nominal_two_sided_95_interval_ppt':[mean-1.96*error,mean+1.96*error],
        'leave_one_out':leave,'peak_offset_arcsec':offsets[peak],'peak_snr':float(snr[peak]),
        'peak_depth_target_equivalent_ppt':float(depth[peak]),'peak_control_global_tail_fraction':global_p,
        'target_map_control_tail_fraction':control_p,'null_stacks':CFG['null_stacks'],
        'localization_confidence_region':'not reported: point-source detection must precede source-coordinate confidence claims',
        'note':'Errors include control scatter and 30-min block noise; no blind-search false-alarm probability is inferred.'}
    save(OUT/'pixel_summary.json',summary)
    # Individual events: original aperture, sky, differential PRF, QLP products.
    events=[(m,r) for m in metas for r in m['events']]
    for page in range((len(events)+5)//6):
        subset=events[page*6:(page+1)*6]
        fig,axes=plt.subplots(len(subset),4,figsize=(16,3*len(subset)),squeeze=False,layout='constrained')
        for row,(m,r) in enumerate(subset):
            a=arrays[m['sector']];n=r['cycle'];t=a[f'n{n}_time'];gg=a[f'n{n}_good']
            columns=[('raw_ap','Original 2.5-pixel aperture (e/s)'),('background','Cutout median (e/s per pixel)'),('prf','Target differential PRF (ppt)'),('DET_FLUX','QLP SAP / corrected (ppt)')]
            for col,(name,title) in enumerate(columns):
                ax=axes[row,col]
                if name=='DET_FLUX':
                    for nm,color in [('SAP_FLUX','#999999'),('DET_FLUX','#286e9a'),('SYS_RM_FLUX','#478646')]:
                        key=f'n{n}_{nm}'
                        if key not in a:continue
                        y=a[key];base=np.nanmedian(y[np.abs(t)>.18]) if np.any(np.abs(t)>.18) else np.nanmedian(y)
                        tt,yy=binned(t[gg],(y[gg]-base)*1000)
                        ax.plot(tt*24,yy,'.-',ms=3,lw=.75,label=nm,color=color)
                    if row==0:ax.legend(fontsize=6)
                else:
                    y=a[f'n{n}_{name}'];factor=1000/m['reference_flux_target_e_s'] if name=='prf' else 1
                    y=(y-np.nanmedian(y))*factor
                    ax.plot(t*24,y,'.',ms=1,color='#d3d3d3',rasterized=True)
                    tt,yy=binned(t[gg],y[gg]);ax.plot(tt*24,yy,'.-',color='#236989',ms=3,lw=.8)
                ax.axvspan(-E['duration']*12,E['duration']*12,color='#cf4d4d',alpha=.13)
                ax.axvline(0,color='#b5313a',lw=.7)
                ax.set_xlim(-12,12);ax.set_xlabel('Hours from predicted centre')
                if row==0:ax.set_title(title,fontsize=10)
            axes[row,0].set_ylabel(f'S{m["sector"]}, n={n}\nBTJD {r["tc_btjd"]:.4f}\n'+('usable' if r['usable'] else 'insufficient clean coverage'),fontsize=9)
        fig.suptitle('Individual predicted events: grey points retain flagged exposures; blue curves use the primary mask',fontsize=14)
        fig.savefig(FIG/f'individual_events_{page+1}.png',dpi=135);plt.close(fig)
    fig,axes=plt.subplots(len(usable),3,figsize=(12,3.1*len(usable)),squeeze=False,layout='constrained')
    for row,(m,r) in enumerate(usable):
        a=arrays[m['sector']];raw=a['images'][r['map_index']].reshape(21,21);sigma=a['sigma']
        q=projection(nuisance(a['reference']),sigma);res=(project(raw.ravel()/sigma,q)*sigma).reshape(21,21)
        stars=read(OUT/f's{m["sector"]:03d}_sources.json');target=next(s for s in stars if s['source_id']==TID)
        for col,(im,title) in enumerate([(a['reference'],'Reference'),(raw,'Raw event contrast'),(res,'After background / registration fit')]):
            ax=axes[row,col]
            if col==0:im=np.log10(np.maximum(im,1));art=ax.imshow(im,origin='lower',cmap='gray')
            else:
                lim=np.percentile(abs(im),98);art=ax.imshow(im,origin='lower',cmap='RdBu_r',vmin=-lim,vmax=lim)
            ax.plot(target['x'],target['y'],'+',color='lime',ms=12,mew=1.7)
            bright=[s for s in stars if (s.get('phot_g_mean_mag') or 99)<18.5]
            ax.scatter([s['x'] for s in bright],[s['y'] for s in bright],s=13,facecolors='none',edgecolors='#f2d15b',lw=.5)
            ax.set_xlim(-.5,20.5);ax.set_ylim(-.5,20.5);ax.set_title(f'S{m["sector"]}, n={r["cycle"]}: {title}',fontsize=9)
            fig.colorbar(art,ax=ax,shrink=.72,label='log10 e/s' if col==0 else 'e/s (red = dimming)')
    fig.savefig(FIG/'event_difference_images.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(16,4.8),layout='constrained')
    ax=axes[0];z=arrays[metas[0]['sector']]['grid']*21
    art=ax.imshow(np.where(within,snr,np.nan).reshape(len(z),len(z)),origin='lower',extent=[z[0],z[-1],z[0],z[-1]],cmap='RdBu_r',vmin=-4,vmax=4)
    ax.plot(0,0,'+',color='lime',ms=13,mew=2,label='Target');ax.plot(*offsets[peak],'x',color='black',label='Strongest map point')
    gs=read(OUT/'s063_sources.json');tar=next(s for s in gs if s['source_id']==TID)
    for s in gs:
        if s['sep_epoch_arcsec']>90 or (s.get('phot_g_mean_mag') or 99)>18:continue
        x=(s['ra_epoch']-tar['ra_epoch'])*np.cos(np.deg2rad(tar['dec_epoch']))*3600;y=(s['dec_epoch']-tar['dec_epoch'])*3600
        ax.plot(x,y,'o',mfc='none',mec='#e6bf35',ms=5)
    ax.set(xlabel='East offset (arcsec)',ylabel='North offset (arcsec)',title='Stacked point-source significance');ax.legend(fontsize=7)
    fig.colorbar(art,ax=ax,label='Empirically scaled signal / noise')
    axes[1].hist(nullmax,bins=35,color='#8dafbc');axes[1].axvline(snr[peak],color='#af3030')
    axes[1].set(title=f'Control-map maxima: tail fraction {global_p:.3f}',xlabel='Maximum positive significance within 90 arcsec',ylabel='Control stacks')
    labels=[f'S{m["sector"]} n{r["cycle"]}' for m,r in usable]
    axes[2].errorbar(amplitudes,np.arange(len(labels)),xerr=errors,fmt='o',color='#246c91');axes[2].axvline(0,color='gray');axes[2].axvspan(3.746-.566,3.746+.566,color='#d45454',alpha=.2,label='P8 model mean depth')
    axes[2].set(yticks=np.arange(len(labels)),yticklabels=labels,xlabel='Target-referenced depth (ppt)',title=f'Target: {mean:.2f} ± {error:.2f} ppt');axes[2].legend(fontsize=8)
    fig.savefig(FIG/'source_localization_and_controls.png',dpi=170);plt.close(fig)
    inj=pd.concat([pd.read_csv(p,dtype={'source_id':str}) for p in sorted(OUT.glob('s???_injections.csv'))],ignore_index=True)
    inj.to_csv(OUT/'all_injections.csv',index=False)
    group=inj.groupby(['source_id','target_equiv_ppt','mismatch']).agg(n=('success','size'),recovery=('success','mean'),
        median_position_error_px=('position_error_px','median'),p90_position_error_px=('position_error_px',lambda x:x.quantile(.9)),
        mean_depth_increment_ratio=('increment_ratio','mean')).reset_index()
    group.to_csv(OUT/'injection_summary.csv',index=False)
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    colors=plt.get_cmap('tab10')(np.arange(inj.source_id.nunique()))
    for source,color in zip(inj.source_id.unique(),colors,strict=True):
        for mismatch,ls in [(False,'-'),(True,'--')]:
            g=group[(group.source_id==source)&(group.mismatch==mismatch)]
            label=('Target' if source==TID else 'Gaia …'+source[-6:])+(' altered PRF' if mismatch else '')
            axes[0].plot(g.target_equiv_ppt,g.recovery,'o'+ls,color=color,label=label)
            axes[1].plot(g.target_equiv_ppt,g.median_position_error_px,'o'+ls,color=color)
            axes[2].plot(g.target_equiv_ppt,g.mean_depth_increment_ratio,'o'+ls,color=color)
    for a in axes:a.set_xscale('log');a.set_xlabel('Injected target-equivalent depth (ppt)')
    axes[0].set(ylabel='Recovery fraction',ylim=(-.05,1.05));axes[0].legend(fontsize=6)
    axes[1].set_ylabel('Median position error (pixels)');axes[1].axhline(.5,c='gray',ls=':')
    axes[2].set_ylabel('Recovered / injected flux increment');axes[2].axhline(1,c='gray',ls=':')
    fig.suptitle('Spatial stress tests in S63, S90 and S98: 12 control windows per sector\nSome faint-source injections exceed the source flux; see the qualified injection table',fontsize=11)
    fig.savefig(FIG/'injection_validation.png',dpi=170);plt.close(fig)
    # Independent ground-based photometry of the nearby catalogued binary.
    ogfile=ARCH/'OGLE-LMC-ECL-36904_I.dat'
    if ogfile.exists():
        og=np.loadtxt(ogfile);pp=1.4769968;epoch=2460000.7092
        fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
        axes[0].errorbar(((og[:,0]-epoch)/pp)%1,og[:,1],og[:,2],fmt='.',ms=2,alpha=.5,color='#376e91')
        axes[0].invert_yaxis();axes[0].set(xlabel='OGLE orbital phase',ylabel='I magnitude',title='Independent OGLE photometry: P = 1.4769968 d')
        phasevals=[((r['tc_btjd']+2457000-epoch)/pp)%1 for _,r in usable]
        axes[1].plot(phasevals,np.arange(len(phasevals)),'o',color='#a74741');axes[1].set(xlim=(0,1),xlabel='Approximate OGLE orbital phase',yticks=np.arange(len(labels)),yticklabels=labels,title='TESS candidate events sample different EB phases')
        fig.suptitle('OGLE-LMC-ECL-36904, about 45.5 arcsec away; HJD and BJD are not equated for precise eclipse timing')
        fig.savefig(FIG/'independent_ogle_binary.png',dpi=170);plt.close(fig)
    print((OUT/'pixel_summary.json').read_text())

if __name__=='__main__':main()
