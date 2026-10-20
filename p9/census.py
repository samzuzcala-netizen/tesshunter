"""Final candidate, sampling and operational census, separate from signal truth rates."""
from common import *
import csv,collections
import pandas as pd

def run():
    from scoring import verify_lock,accepted_match,times_for
    ids=read(P9/'manifests/final_ids.json');scores=read(P9/'results/scored_signals.json');associations=collections.defaultdict(list)
    truth=pd.read_csv(P9/'truth/final_truth.csv')
    for s in scores:
        if s.get('candidate_key'):associations[s['candidate_key']].append(s['truth_id']+':exact')
        for a in s.get('aliases',[]):associations[f'tic{s["tic_id"]}_P{a["period"]:.4f}'].append(s['truth_id']+':alias')
    rows=[];hosts=[];apertures=[];final_evidence=[];products=[]
    for tic in ids:
        verify_lock(tic);root=P9/'results/blind'/f'tic{tic}';sp=root/'search/results'/f'tic{tic}.json'
        products.extend(dict(tic_id=tic,**p) for p in read(P9/'manifests/products'/f'tic{tic}.json')['products'])
        sr=read(sp) if sp.exists() else {};planets=sr.get('result',{}).get('planets',[])
        tt=None
        hosts.append(dict(tic_id=tic,search_status=sr.get('status','unavailable'),n_accepted=len(planets),
          n_pre=sum(1 for _ in csv.DictReader((root/'survivors.csv').open(encoding='utf-8'))) if (root/'survivors.csv').exists() else 0))
        for q in planets:
            key=f'tic{tic}_P{q["period_days"]:.4f}'
            pre=bool(q.get('stitch_epoch_consistent') and (q.get('stitch_snr') or 0)>=7.1 and (q.get('stitch_n_transits') or 0)>=3)
            row=dict(tic_id=tic,key=key,planet_num=q['planet_num'],period_days=q['period_days'],depth_ppt=q.get('depth_ppt'),
              stitch_snr=q.get('stitch_snr'),stitch_n_transits=q.get('stitch_n_transits'),pre=pre,
              search_truth_associations=';'.join(sorted(set(associations[key]))),first_termination='pre' if not pre else None)
            if pre:
                for stage,folder,field,allowed in [('A','stageA','decision',{'PASS'}),('S','secondary','gate',{'PASS','HOLD'}),('B','stageB','decision',{'PASS'}),('C','stageC','decision',{'PASS'})]:
                    path=root/folder/f'{key}.json';d=read(path) if path.exists() else {}
                    row[stage]=d.get(field,'UNAVAILABLE');row[stage+'_reason']=d.get('reason')
                    if stage=='B':row['B_max_verdict']=d.get('max_verdict')
                    if row[stage] not in allowed:row['first_termination']=stage;break
                else:
                    d=read(root/'final'/f'{key}.json');row.update(D=d['scientific_verdict'],D_reason=d['reason'],
                      legitimate_useful_hold=d.get('legitimate_useful_hold',False),hold_reason=d.get('hold_reason'),first_termination='D')
                    fp=root/'fit'/f'{key}.json';fm=[]
                    if fp.exists():
                        fit=read(fp).get('adopted') or {}
                        if tt is None:tt=times_for(tic)
                        ep=dict(period=fit.get('period'),t0=fit.get('t0_btjd'),duration=(fit.get('t14_hours') or 0)/24)
                        for _,tr in truth[truth.tic_id==tic].iterrows():
                            exact=accepted_match(tt,tr.to_dict(),ep);alias=accepted_match(tt,tr.to_dict(),ep,True)
                            if exact['matched']:fm.append(tr.truth_id+':exact')
                            elif alias['matched']:fm.append(tr.truth_id+':alias')
                    row['final_fit_truth_associations']=';'.join(fm)
                    fit_record=read(fp) if fp.exists() else {};adopted=fit_record.get('adopted') or {}
                    xp=root/'expensive'/f'{key}.json';exp=read(xp) if xp.exists() else {}
                    fpp=exp.get('fpp') or {};centroid=exp.get('centroid') or {};sectors=centroid.get('per_sector') or []
                    final_evidence.append(dict(key=key,tic_id=tic,truth_association=row['final_fit_truth_associations'],
                      scientific_verdict=row['D'],legitimate_useful_hold=row['legitimate_useful_hold'],B_cap=row.get('B_max_verdict'),
                      fit_period=adopted.get('period'),fit_radius_rearth=adopted.get('rp_rearth'),fit_impact=adopted.get('b'),
                      delta_chi2_vs_flat=adopted.get('delta_chi2_vs_flat'),n_transits=adopted.get('n_transits'),
                      density_prior_adopted=fit_record.get('density_prior_adopted'),density_ratio=adopted.get('density_ratio_fit_over_cat'),
                      FPP=fpp.get('fpp'),NFPP=fpp.get('nfpp'),n_FPP_stars=fpp.get('n_stars'),n_FPP_scenarios=fpp.get('n_scenarios'),
                      expensive_status=exp.get('status'),centroid_shift_arcsec=centroid.get('shift_arcsec'),centroid_sigma=centroid.get('sigma'),
                      n_pixel_sectors_available=sum(s.get('available',False) for s in sectors),
                      n_sectors_in_weighted_centroid=centroid.get('n_sectors_used'),n_individual_centroid_flags=centroid.get('n_sectors_flagged_individually'),
                      review_path=str((root/'final'/f'{key}.json').relative_to(P9))))
                    ap=root/'eb_screen'/f'{key}_target_aperture.json'
                    if ap.exists():
                        a=read(ap);sectors=a.get('sectors',[])
                        apertures.append(dict(key=key,status=a.get('status','complete'),n_sectors=len(sectors),
                          available_sectors=sum(s.get('status','complete')=='complete' for s in sectors),
                          unavailable_sector_details=[s for s in sectors if s.get('status')=='unavailable']))
                    else:apertures.append(dict(key=key,status='not_available'))
            rows.append(row)
    pd.DataFrame(rows).to_csv(P9/'results/candidate_ledger.csv',index=False)
    write(P9/'results/candidate_ledger.json',rows)
    write(P9/'results/final_evidence_summary.json',final_evidence)
    pd.DataFrame(final_evidence).to_csv(P9/'results/final_evidence_summary.csv',index=False)
    pd.DataFrame(hosts).to_csv(P9/'results/host_operations.csv',index=False)
    operations=[]
    host_labels={int(tic):';'.join(sorted(set(g.label))) for tic,g in truth.groupby('tic_id')}
    for p in (P9/'results/operations').glob('*.json'):
        d=read(p);tic=int(d['token'].split('tic',1)[1].split('_')[0])
        operations.append(dict(token=d['token'],tic_id=tic,label=host_labels[tic],stage=d['token'].split('_')[0],status=d['status'],
          n_attempts=len(d['attempts']),reused_pilot_measurement='reuse_validation' in d,
          last_attempt_seconds=d['attempts'][-1]['wall_seconds'],
          measured_attempt_seconds=sum(a['wall_seconds'] for a in d['attempts'])))
    op=pd.DataFrame(operations);op.to_csv(P9/'results/operation_runtime.csv',index=False)
    runtime_summary=[]
    for (stage,label,status),g in op.groupby(['stage','label','status']):
        runtime_summary.append(dict(stage=stage,label=label,status=status,n_operations=len(g),n_hosts=int(g.tic_id.nunique()),
          n_attempts=int(g.n_attempts.sum()),reused_operations=int(g.reused_pilot_measurement.sum()),
          median_last_attempt_seconds=float(g.last_attempt_seconds.median()),
          p90_last_attempt_seconds=float(g.last_attempt_seconds.quantile(.9)),
          maximum_last_attempt_seconds=float(g.last_attempt_seconds.max()),
          total_measured_attempt_seconds=float(g.measured_attempt_seconds.sum())))
    pd.DataFrame(runtime_summary).to_csv(P9/'results/runtime_by_stage_and_label.csv',index=False)
    frame=pd.read_csv(P9/'truth/sampling_frame.csv');outcomes=collections.Counter()
    for r in frame[frame.label=='positive'].itertuples():
        for reason in str(r.ineligibility).split(';'):
            if reason not in ('','nan'):outcomes[reason]+=1
    ps=pd.read_csv(P9/'truth/catalogues/nasa_ps_truth.csv');missing_tic=int(ps.tic_id.isna().sum())
    toi=pd.read_csv(P9/'truth/catalogues/exofop_toi.csv')
    analysis=pd.read_csv(P9/'results/analysis_table.csv');domain=[]
    coverage=read(P9/'manifests/coverage_corrected.json')
    proxy=frame[(frame.label=='positive')&frame.frame_eligible&frame.p8_proxy.eq(True)]
    proxy_hosts=[]
    for tic in sorted(proxy.tic_id.astype(int).unique()):
        cv=coverage.get(str(tic),{});ffi=set(cv.get('ffi') or []);twomin=set(cv.get('twomin') or [])&ffi
        proxy_hosts.append(dict(tic_id=int(tic),n_ffi=len(ffi),n_two_minute=len(twomin),
          corrected_minority_two_minute=len(ffi)>=3 and len(twomin)<len(ffi)/2))
    for label,g in analysis.groupby('label'):
        domain.append(dict(label=label,n_signals=len(g),n_hosts=int(g.tic_id.nunique()),
          strict_P8_targeting_signals=int(g.strict_p8_stellar_and_targeting.eq(True).sum()),
          strict_P8_actual_product_signals=int(g.strict_p8_actual_product_overlap.eq(True).sum()),
          FFI_majority_signals=int(g.product_group.eq('FFI-majority').sum()),SPOC_majority_signals=int(g.product_group.eq('SPOC-majority').sum()),
          n_signal_hosts_radius_above_one=int(g.loc[g.rstar>1,'tic_id'].nunique()),
          n_signal_hosts_teff_above_6000=int(g.loc[g.teff>6000,'tic_id'].nunique())))
    out=dict(utc=utc(),n_hosts=len(hosts),n_accepted_signals=len(rows),n_pre=sum(r['pre'] for r in rows),
      candidate_survival={stage:sum(r.get(stage) in allowed for r in rows) for stage,allowed in [('A',{'PASS'}),('S',{'PASS','HOLD'}),('B',{'PASS'}),('C',{'PASS'})]},
      final_candidate_verdicts=dict(collections.Counter(r['D'] for r in rows if 'D' in r)),
      final_unassociated_candidates=[r['key'] for r in rows if 'D' in r and not r.get('final_fit_truth_associations')],
      association_note='Search and final-fit associations are separate. Primary completeness still requires the registered coherent nested path; a late association cannot rescue it.',
      auxiliary_fixed_aperture_availability=apertures,
      sample_domain=domain,
      entire_original_cool_faint_positive_frame=dict(n_signals=len(proxy),n_hosts=len(proxy_hosts),
        n_hosts_with_corrected_minority_two_minute=sum(p['corrected_minority_two_minute'] for p in proxy_hosts),hosts=proxy_hosts,
        scope='All hosts in the original NASA-stellar proxy frame, not every possible TIC-stellar definition or future catalogue'),
      selected_product_count=len(products),selected_product_authors=dict(collections.Counter(p['author'] for p in products)),
      selected_products_above_sector_105=[p for p in products if p['sector']>105],
      final_holds_by_reason=dict(collections.Counter(r.get('hold_reason') for r in rows if r.get('D')=='HOLD')),
      frame_counts={str(k):int(v) for k,v in frame.groupby(['label','frame_eligible']).size().items()},
      positive_frame_exclusion_reasons_nonexclusive=dict(outcomes),NASA_period_domain_rows=len(ps),NASA_missing_TIC_not_executed=missing_tic,
      ExoFOP_dispositions=toi['TFOPWG Disposition'].value_counts().to_dict(),
      uncalibrated_negative_subtypes=['independently attributable instrumental signal','variable-star signal outside the EB/ellipsoidal catalogue'],
      selected_hosts=len(ids),selected_signals=len(scores),
      selected_eligibility=dict(collections.Counter(s['eligibility'] for s in scores)),
      operation_counts=op.groupby(['stage','status']).size().rename('n').reset_index().to_dict(orient='records'),
      runtime_by_stage_and_label=runtime_summary,
      measured_seconds_new_primary=float(op.loc[~op.reused_pilot_measurement,'measured_attempt_seconds'].sum()),
      reused_measurement_seconds=float(op.loc[op.reused_pilot_measurement,'measured_attempt_seconds'].sum()),
      runtime_note='Sum of process wall times, not elapsed clock time or CPU seconds. Reused pilot measurements are separated. Original pilot search costs remain in timing_pilot/operations.',
      code_sha256=sha(Path(__file__)))
    write(P9/'results/census.json',out)
    print('candidate census',len(rows),'pre',out['n_pre'],'C',out['candidate_survival']['C'],'final',out['final_candidate_verdicts'],flush=True)

if __name__=='__main__':run()
