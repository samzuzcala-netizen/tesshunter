"""Compact comparison and individual older-epoch plots for the report."""
from run_followup import *

def main():
    summary=read(OUT/'qlp_summary.json');pix=read(OUT/'pixel_summary.json')
    rows=[('Recent QLP SAP','P8_physical_fit_SAP_FLUX'),('Recent QLP SYS_RM','P8_physical_fit_SYS_RM_FLUX'),
          ('Recent QLP DET','P8_physical_fit_DET_FLUX'),('Older QLP SAP','old_physical_fit_SAP_FLUX'),
          ('Older QLP corrected','old_physical_fit_KSPSAP_FLUX')]
    labels=[r[0] for r in rows]+['Recent target PRF']
    depths=[summary[k]['depth_ppt'] for _,k in rows]+[pix['target_depth_ppt']]
    errors=[summary[k]['error_ppt'] for _,k in rows]+[pix['target_error_ppt']]
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    axes[0].errorbar(depths,np.arange(6),xerr=errors,fmt='o',color='#286b90',capsize=3)
    axes[0].axvline(0,c='grey');axes[0].set(yticks=np.arange(6),yticklabels=labels,xlabel='Fixed 2.899-hour depth (ppt)',title='Dimming depends on reduction and observing epoch')
    axes[0].invert_yaxis()
    g=pd.read_csv(OUT/'older_ephemeris_grid.csv');z=g.pivot(index='epoch_sigma_offset',columns='period_sigma_offset',values='depth_ppt')
    im=axes[1].imshow(z.values,origin='lower',extent=[-3.5,3.5,-3.5,3.5],cmap='RdBu_r',vmin=-1.5,vmax=1.5)
    axes[1].set(xticks=range(-3,4),yticks=range(-3,4),xlabel='Period offset / quoted uncertainty',ylabel='Epoch offset / quoted uncertainty',title='Older observations: ephemeris uncertainty test')
    fig.colorbar(im,ax=axes[1],label='Older corrected QLP depth (ppt)')
    fig.suptitle('TIC 404927114: no securely localized transit\nQLP series are correlated reductions; PRF depth uses a fitted target-flux scale',fontsize=14)
    fig.savefig(FIG/'evidence_comparison.png',dpi=170);plt.close(fig)
    events=pd.read_csv(OUT/'qlp_events.csv');ev=events[(events.old)&(events.ephemeris=='physical_fit')&(events.column=='KSPSAP_FLUX')]
    fig,axes=plt.subplots(len(ev),2,figsize=(12,2.3*len(ev)),squeeze=False,layout='constrained')
    for i,row in enumerate(ev.itertuples()):
        _,lc,_,_=read_lc(row.sector);t=lc['TIME']-row.tc_btjd;good=((lc['QUALITY']&(17087|4096))==0)&np.isfinite(t)
        win=abs(t)<.4
        for j,key in enumerate(['SAP_FLUX','KSPSAP_FLUX']):
            y=lc[key];b=np.nanmedian(y[win&good&(abs(t)>.1)])
            ax=axes[i,j];ax.plot(t[win]*24,(y[win]/b-1)*1000,'.',color='#b8b8b8',ms=2)
            mask=win&good;ax.plot(t[mask]*24,(y[mask]/b-1)*1000,'.',ms=2,color='#257394')
            ax.axvspan(-E['duration']*12,E['duration']*12,color='red',alpha=.12);ax.axhline(0,c='grey',lw=.6)
            ax.set_xlim(-9.6,9.6);ax.set_ylabel(f'S{row.sector} n{row.cycle}\nFlux (ppt)');ax.set_xlabel('Hours from physical-fit prediction')
            ax.set_title(key+'; '+('usable' if row.usable else 'incomplete'))
    fig.suptitle('All predicted events in the ten older cached QLP sectors; no epoch refit',fontsize=14)
    fig.savefig(FIG/'older_individual_events.png',dpi=120);plt.close(fig)

if __name__=='__main__':main()
