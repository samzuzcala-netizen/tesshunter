"""Gaia epoch photometry, actual mission timing, and older-epoch uncertainty grid."""
from run_followup import *
from lightcurve_followup import combine

def main():
    receipts=[]
    for name in ['TESS_orbit_times.csv','TESS_FFI_observation_times.csv']:
        url='https://tess.mit.edu/public/files/'+name;p=fetch(url,name)
        receipts.append({'url':url,'path':name,'sha256':sha(p)})
    ep=ARCH/'gaia_epoch_download.bin'
    url='https://gea.esac.esa.int/data-server/data'
    params={'ID':TID,'RETRIEVAL_TYPE':'EPOCH_PHOTOMETRY','FORMAT':'csv','DATA_STRUCTURE':'RAW','RELEASE':'Gaia DR3'}
    if not ep.exists():
        r=requests.get(url,params=params,timeout=60);r.raise_for_status();ep.write_bytes(r.content)
    receipts.append({'url':url,'params':params,'path':ep.name,'sha256':sha(ep)})
    row=pd.read_csv(ep,dtype={'source_id':str}).iloc[0];assert row.source_id==TID
    def ar(name):return np.array([float(x.strip()) for x in row[name].strip('()[]').split(',')])
    def flag(name):return np.array([x.strip()=='true' for x in row[name].strip('()[]').split(',')])
    gt=ar('g_transit_time');gf=ar('g_transit_flux');ge=ar('g_transit_flux_error');gm=ar('g_transit_mag')
    times=Time(gt+2455197.5,format='jd',scale='tcb').tdb.jd-2457000
    good=np.isfinite(gf)&np.isfinite(times)&~flag('variability_flag_g_reject')&~flag('photometry_flag_noisy_data')
    phases=phase(times,E['period'],E['epoch']);inside=good&(abs(phases)<E['duration']/2)
    period=np.linspace(.3,60,20000);power=LombScargle(times[good],gf[good],ge[good]).power(1/period)
    k=int(np.argmax(power));gtab=pd.DataFrame({'time_btjd_tdb':times,'g_flux':gf,'g_error':ge,'g_mag':gm,'good':good,'hours_from_candidate':phases*24})
    gtab.to_csv(OUT/'gaia_epoch_photometry.csv',index=False)
    gsummary={'n_total':len(times),'n_good':int(good.sum()),'n_in_candidate_window':int(inside.sum()),
      'good_g_magnitude_percentiles_5_50_95':np.percentile(gm[good],[5,50,95]),
      'g_magnitude_robust_scatter':float(mad(gm[good])),'nearest_good_epoch_hours':float(np.min(abs(phases[good]))*24),
      'time_convention':'Gaia BJD_TCB - 2455197.5 converted with Astropy to BJD_TDB - 2457000',
      'period_scan_max_days':float(period[k]),'period_scan_max_power':float(power[k]),
      'power_at_candidate':float(LombScargle(times[good],gf[good],ge[good]).power(1/E['period'])),
      'interpretation':'Sparse epochs/stellar variability; periodogram maximum is exploratory, not a rotation-period measurement.'}
    fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    axes[0].plot(times[good],gm[good],'.',ms=4);axes[0].invert_yaxis();axes[0].set(xlabel='BTJD (TDB)',ylabel='Gaia G magnitude',title='Independent Gaia DR3 epoch photometry')
    axes[1].plot(phases[good]*24,gm[good],'.',ms=4);axes[1].axvspan(-1.4495,1.4495,color='red',alpha=.15);axes[1].invert_yaxis()
    axes[1].set(xlabel='Hours from predicted centre',ylabel='Gaia G magnitude',title=f'{int(inside.sum())} good epochs inside nominal event')
    axes[2].plot(period,power,lw=.6);axes[2].axvline(E['period'],c='red',ls='--');axes[2].set(xlabel='Period (days)',ylabel='Lomb-Scargle power',title='Exploratory, sparse-sampling periodogram')
    fig.savefig(FIG/'independent_gaia_photometry.png',dpi=150);plt.close(fig)
    # Three-sigma rectangular ephemeris sensitivity, covariance unavailable.
    cached=[];records=pd.read_csv(OUT/'qlp_events.csv')
    for sec in [27,28,29,31,32,34,35,37,38,39]:
        _,lc,_,_=read_lc(sec);good=np.isfinite(lc['TIME'])&((lc['QUALITY']&(17087|4096))==0)
        cc=records[(records.sector==sec)&(records.ephemeris=='physical_fit')&(records.column=='KSPSAP_FLUX')]
        controls=cc.control_sigma.dropna();emp=float(controls.iloc[0]) if len(controls) else .001
        cached.append((sec,lc['TIME'],lc['KSPSAP_FLUX'],good,emp))
    grid=[]
    for z0 in np.linspace(-3,3,7):
        for zp in np.linspace(-3,3,7):
            p=E['period']+zp*E['period_err'];epoch=E['epoch']+z0*E['epoch_err'];rr=[]
            for sec,t,y,good,emp in cached:
                for n,tc in centres(t,p,epoch):
                    v=measure_series(t,y,tc,E['duration'],good)
                    if v['usable']:v['error']=max(emp,v['block_error'])
                    rr.append(v)
            grid.append({'epoch_sigma_offset':z0,'period_sigma_offset':zp,**combine(rr)})
    pd.DataFrame(grid).to_csv(OUT/'older_ephemeris_grid.csv',index=False)
    timing=pd.read_csv(ARCH/'TESS_orbit_times.csv')
    timing['sec']=pd.to_numeric(timing.Sector,errors='coerce')
    timing['start']=pd.to_datetime(timing['Start of Orbit'],errors='coerce');timing['end']=pd.to_datetime(timing['End of Orbit'],errors='coerce')
    tt=[]
    for mpath in sorted(OUT.glob('s???.json')):
        m=read(mpath);d=timing[timing.sec==m['sector']].dropna(subset=['start','end'])
        if not len(d):continue
        starts=Time(d.start.dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),format='iso',scale='utc').tdb.jd-2457000
        ends=Time(d.end.dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),format='iso',scale='utc').tdb.jd-2457000
        for ev in m['events']:
            tc=ev['tc_btjd'];inside=(tc>=starts)&(tc<=ends)
            j=int(np.argmin(abs(starts-tc))) if not inside.any() else np.flatnonzero(inside)[0]
            tt.append({'sector':m['sector'],'cycle':ev['cycle'],'orbit_label':str(d.iloc[j].Orbit),
               'hours_from_segment_start_approx':float((tc-starts[j])*24),
               'hours_before_segment_end_approx':float((ends[j]-tc)*24),
               'within_nominal_science_segment':bool(inside.any()),
               'timing_caveat':'UTC converted to TDB; observer-to-barycentre correction not applied to schedule; uncertain by <9 min.'})
    pd.DataFrame(tt).to_csv(OUT/'mission_contact_comparison.csv',index=False)
    save(OUT/'independent_checks.json',{'receipts':receipts,'gaia':gsummary,'old_grid_max_snr':max(grid,key=lambda v:v['snr']),
           'old_grid_max_depth_ppt':max(v['depth_ppt'] for v in grid)})
    print(json.dumps(gsummary,default=lambda a:a.tolist(),indent=2));print('OLD GRID MAX',max(grid,key=lambda v:v['snr']));print(pd.DataFrame(tt).to_string(index=False))

if __name__=='__main__':main()
