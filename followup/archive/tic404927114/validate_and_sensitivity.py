"""Supplemental physical-shape, nearby-source and background diagnostics.

These are declared supplemental after the first primary results. They do not
replace the fixed primary estimator or select events by measured depth.
"""
from run_followup import *
import batman

def main():
    result=[];sensitivity=[];joints=[];bgrows=[];eph_rows=[]
    fit=read(P8/'fit'/(KEY+'.json'));ad=fit['adopted']
    injection_source='4659942076276901120'
    for mpath in sorted(OUT.glob('s???.json')):
        m=read(mpath);sec=m['sector'];a=np.load(OUT/f's{sec:03d}_images.npz')
        series=np.load(OUT/f's{sec:03d}_series.npz');t=series['time'];good=series['good']
        with fits.open(REPO/m['path']) as h:cube=np.array(h[1].data['FLUX'],float).reshape(-1,441)
        sigma=a['sigma'];q=projection(nuisance(a['reference']),sigma)
        stars=read(OUT/f's{sec:03d}_sources.json');target=next(s for s in stars if s['source_id']==TID)
        prf=PRF(m['camera'],m['ccd'],m['col'],m['row'])
        p=prf.at(target['x'],target['y']).ravel();pw=project(p/sigma,q);ff=pw/sigma/(pw@pw)
        factor=1000/m['reference_flux_target_e_s']
        nearest=min([s for s in stars if s['source_id']!=TID],key=lambda s:s['sep_epoch_arcsec'])
        nearp=project(prf.at(nearest['x'],nearest['y']).ravel()/sigma,q)
        correlation=float(pw@nearp/np.linalg.norm(pw)/np.linalg.norm(nearp))
        mat=np.column_stack([pw,nearp]);joint=np.linalg.pinv(mat)
        for r in m['events']:
            n=r['cycle'];tc=r['tc_btjd']
            eph_rows.append({'sector':sec,'cycle':n,'physical_tc':tc,
                'fit_sigma_no_cov_minutes':1440*np.hypot(E['epoch_err'],n*E['period_err']),
                'fit_sigma_cov_upper_minutes':1440*(E['epoch_err']+abs(n)*E['period_err']),
                **{label+'_minus_fit_minutes':1440*(e['epoch']+n*e['period']-tc) for label,e in EPH.items()}})
            for label in EPH:
                v=r[label]
                if v['usable']:sensitivity.append({'sector':sec,'cycle':n,'kind':label,'depth_ppt':v['depth_e_s']*factor,
                    'white_error_ppt':v['white_error_e_s']*factor})
            if not r['usable']:continue
            tw,_=temporal_weights(t,tc,E['duration'],good);idx,w,_=tw
            contrast=w@cube[idx]
            # Correlations of raw aperture variability with diffuse background.
            wi=good&(abs(t-tc)<.4)
            bgrows.append({'sector':sec,'cycle':n,'raw_sky_correlation':float(np.corrcoef(series['raw_ap'][wi],series['background'][wi])[0,1]),
              'raw_ap_contrast_e_s':float(w@series['raw_ap'][idx]),'median_sky_contrast_e_s_per_pixel':float(w@series['background'][idx]),
              'target_prf_contrast_e_s':r['depth_e_s'],'diffuse_median_image_e_s':r['diffuse_median_e_s']})
            for kind,depth in r['background_sensitivities'].items():sensitivity.append({'sector':sec,'cycle':n,'kind':kind,'depth_ppt':depth*factor})
            coef=joint@project(contrast/sigma,q)
            cov=(w@w)*np.linalg.pinv(mat.T@mat)
            joints.append({'sector':sec,'cycle':n,'nearest_source_id':nearest['source_id'],'separation_arcsec':nearest['sep_epoch_arcsec'],
               'template_correlation':correlation,'condition_number':float(np.linalg.cond(mat)),
               'joint_target_depth_ppt':float(coef[0]*factor),'joint_neighbour_depth_target_equiv_ppt':float(coef[1]*factor),
               'joint_target_white_error_ppt':float(np.sqrt(cov[0,0])*factor),
               'formal_white_error_inflation':float(1/np.sqrt(1-correlation**2))})
            par=batman.TransitParams();par.t0=tc;par.per=E['period'];par.rp=ad['rp_rs'];par.a=ad['a_rs'];par.inc=ad['inc_deg']
            par.ecc=0;par.w=90;par.u=[fit['limb_darkening']['u1'],fit['limb_darkening']['u2']];par.limb_dark='quadratic'
            model=batman.TransitModel(par,t[idx],supersample_factor=7,exp_time=200/86400)
            signal=(1-model.light_curve(par))*m['reference_flux_target_e_s']
            expected=float(-w@signal)
            source=next(s for s in stars if s['source_id']==injection_source)
            sf=source.get('reference_flux_e_s')
            for which in ['target_physical_fit','target_1ppt_box','neighbour_50percent_box']:
                loc=target if which!='neighbour_50percent_box' else source
                if which=='target_physical_fit':loss=signal
                elif which=='target_1ppt_box':loss=(abs(t[idx]-tc)<E['duration']/2)*m['reference_flux_target_e_s']*.001
                else:
                    if sf is None or sf<=0:continue
                    loss=(abs(t[idx]-tc)<E['duration']/2)*sf*.5
                truth=float(-w@loss)
                own=project(prf.at(loc['x'],loc['y']).ravel()/sigma,q);ownfilter=own/sigma/(own@own)
                for mismatch in [False,True]:
                    pp=prf.at(loc['x']+(.12 if mismatch else 0),loc['y']-(.09 if mismatch else 0),blur=.15 if mismatch else 0).ravel()
                    inj=cube[idx]-loss[:,None]*pp
                    d=w@inj;rec=float(ownfilter@d);before=float(ownfilter@contrast)
                    result.append({'sector':sec,'cycle':n,'kind':which,'mismatch':mismatch,'source_id':loc['source_id'],
                       'intrinsic_eclipse_fraction':.5 if which=='neighbour_50percent_box' else None,
                       'expected_contrast_e_s':truth,'recovered_increment_e_s':rec-before,'increment_ratio':(rec-before)/truth,
                       'after_injection_contrast_e_s':rec,'before_injection_e_s':before})
    pd.DataFrame(result).to_csv(OUT/'physical_event_injections.csv',index=False)
    pd.DataFrame(sensitivity).to_csv(OUT/'pixel_sensitivities.csv',index=False)
    pd.DataFrame(joints).to_csv(OUT/'joint_nearest_source.csv',index=False)
    pd.DataFrame(bgrows).to_csv(OUT/'diffuse_background_evidence.csv',index=False)
    pd.DataFrame(eph_rows).to_csv(OUT/'ephemeris_event_comparison.csv',index=False)
    # Qualify which artificial flux-loss tests can be physically supplied by a star.
    df=pd.read_csv(OUT/'all_injections.csv',dtype={'source_id':str})
    classifications=[]
    for row in df.itertuples():
        stars=read(OUT/f's{row.sector:03d}_sources.json');s=next(s for s in stars if s['source_id']==row.source_id)
        tar=next(s for s in stars if s['source_id']==TID)
        fl=s.get('reference_flux_e_s');method='reference fit'
        if fl is None or fl<=0:
            mag=s.get('phot_rp_mean_mag') or s.get('phot_g_mean_mag');tmag=tar.get('phot_rp_mean_mag') if s.get('phot_rp_mean_mag') else tar.get('phot_g_mean_mag')
            fl=tar['reference_flux_e_s']*10**(-.4*(mag-tmag));method='Gaia RP/G flux-ratio proxy; TESS colour uncertain'
        fraction=row.injected_e_s/fl
        classifications.append({'source_flux_estimate':fl,'estimated_eclipse_fraction':fraction,
                               'flux_estimate_method':method,'physically_possible_under_flux_estimate':fraction<=1})
    df=pd.concat([df.reset_index(drop=True),pd.DataFrame(classifications)],axis=1)
    df.to_csv(OUT/'injections_with_physical_limits.csv',index=False)
    cat=read(OUT/'catalogue_queries.json');og=cat['ogle_neighbours'][0]
    epoch=2460000.7092;porb=1.4769968
    facts={'known_binary':og,'candidate_over_binary_period':E['period']/porb,
       'candidate_events_approx_eb_phase':[{'sector':r['sector'],'cycle':r['cycle'],'phase':((r['physical_tc']+2457000-epoch)/porb)%1} for r in eph_rows],
       'gaia_rotation_row_count':len(pd.read_csv(ARCH/'gaia_rotation.csv')),
       'gaia_eb_row_count_within90arcsec':len(pd.read_csv(ARCH/'gaia_eb_cone.csv')),
       'physical_injections':pd.DataFrame(result).groupby(['kind','mismatch']).increment_ratio.agg(['mean','min','max']).reset_index().to_dict('records'),
       'over_total_eclipse_spatial_injections':int((~df.physically_possible_under_flux_estimate).sum()),
       'spatial_injection_total':len(df)}
    save(OUT/'supplemental_validation.json',facts)
    print(pd.DataFrame(joints).to_string(index=False));print(pd.DataFrame(bgrows).to_string(index=False));print(json.dumps(facts['physical_injections'],indent=2))

if __name__=='__main__':main()
