"""Descriptive P11 audit tables, host uncertainty, input policy and queue accounting."""
from collections import Counter,defaultdict
from datetime import datetime
import csv
import json
from pathlib import Path
import time
import numpy as np
from common import REPO,P11,DATA,read,write,sha,utc,append_event,science_environment
science_environment()


def median(values):
    values=[float(v) for v in values if v is not None and np.isfinite(v)]
    return float(np.median(values)) if values else None


def merge_intervals(intervals):
    intervals=sorted(intervals);merged=[]
    for left,right in intervals:
        if not merged or left>merged[-1][1]:merged.append([left,right])
        else:merged[-1][1]=max(merged[-1][1],right)
    return merged


def resources():
    events=[json.loads(s) for s in (P11/'manifests/queue_intervals.jsonl').read_text().splitlines()]
    stamp=lambda s:datetime.fromisoformat(s).timestamp()
    starts={};intervals=[];unclosed=[]
    for e in events:
        key=(e['phase'],e.get('pid'))
        if e['event']=='start':starts[key]=e
        elif e['event']=='end':
            begin=starts.pop(key,None)
            if begin:intervals.append((stamp(begin['utc']),stamp(e['utc'])))
            elif e.get('started_utc'):intervals.append((stamp(e['started_utc']),stamp(e['utc'])))
        elif e['event']=='interval':intervals.append((stamp(e['started_utc']),stamp(e['ended_utc'])))
    merged=merge_intervals(intervals)
    acquisitions=[json.loads(s) for s in (DATA/'acquisition/acquisition.jsonl').read_text().splitlines()]
    return dict(scientific_union_seconds=sum(b-a for a,b in merged),scientific_union_hours=sum(b-a for a,b in merged)/3600,
                union_intervals_unix=merged,unclosed=list(starts.values()),
                acquired_bytes=sum(r.get('bytes',0) for r in acquisitions),acquisition_requests=len(acquisitions),
                scientific_cap_hours=48,audit_cap_hours=2,max_scientific_workers=4,BLAS_threads_per_worker=1,
                reference_TLS_runs=0,search_runs=0,C_local_runs=0,validation_runs=0,
                CPU_accounting='Completed noise workers report CPU; failed import attempts retain wall time but lack complete process-tree CPU. No speed or CPU-feasibility qualification is claimed.')


def input_policy():
    excluded_qlp={80,83,85,99,100,101,102,103,104};rows=[]
    for p in sorted((P11/'results/input_inventory_v2').glob('tic*.json')):
        inv=read(p);best={}
        for rec in inv['records']:
            m=rec['metadata'];s=m.get('sector',-1);a=m.get('author')
            if 'raw_path' not in rec or not 56<=s<=104 or m.get('cadence_s',1e9)>300 or rec['n_quality_good']<50:continue
            if not all(rec['checks'].values()):continue
            if a=='QLP' and s in excluded_qlp:continue
            if rec['timing_status'] not in ('UNAFFECTED_SOURCE_VERIFIED','QLP_74_79_CORRECTED_SOURCE_VERIFIED'):continue
            rank={'SPOC':0,'TESS-SPOC':1,'QLP':2}
            if s not in best or rank[a]<rank[best[s]['metadata']['author']]:best[s]=rec
        selected=[dict(sector=s,author=r['metadata']['author'],raw_path=r['raw_path'],raw_sha256=r['raw_sha256'],
                       source_fits_path=r['source_matches'][0]['path'],source_fits_sha256=r['source_matches'][0]['sha256']) for s,r in sorted(best.items())]
        rows.append(dict(tic_id=inv['tic_id'],selected_products=selected,n_sectors=len(selected),
                         meets_at_least_three_cached_sectors=len(selected)>=3,
                         status='INPUT_INELIGIBLE' if len(selected)<3 else 'CANDIDATE_COMMON_INPUT_ONLY_NOT_QUALIFIED'))
    policy=dict(utc=utc(),status='FROZEN_INPUT_GATE_STOP_NO_VALIDATION_DRAW',sector_range=[56,104],excluded_QLP_sectors=sorted(excluded_qlp),
        exclusion_reasons={'99-104':'official redelivery pending; six current source checks are TIME-identical to cache',
                          '80,83,85':'quality-passing same-cadence timing discrepancies with independent TESS-SPOC; no correction inferred'},
        same_policy_for_both_methods=True,minimum_native_FFI_sectors=3,retained_host_count_requirement=300,
        cached_hosts_with_three_sectors=sum(r['meets_at_least_three_cached_sectors'] for r in rows),hosts=rows,
        limits=['This is a frozen input eligibility policy, not a frozen finalist or validation prediction manifest.',
                'The original P8 native-FFI and strict-minority 2-minute requirements remain additional conditions; cached >=3-sector counts are optimistic availability counts.',
                'No new source-family timing correction, optimized aperture or transit-based clock shift was introduced.'],
        source_sha256=sha(__file__),evidence_sha256={str(p.relative_to(REPO)).replace('\\','/'):sha(p) for p in [P11/'results/coverage/summary.json',P11/'results/timestamp_redelivery_checks.json',P11/'results/peer_timing_quality_filtered.json']})
    write(P11/'protocol/MAIN_INPUT_POLICY.json',policy)
    return policy


def summarize():
    timer=time.perf_counter();started=utc()
    rows=[read(p) for p in sorted((P11/'results/noise_v2').glob('tic*.json'))]
    if len(rows)!=60 or any(r['status']!='OK' for r in rows):raise RuntimeError('The fixed 60-host audit is incomplete')
    metrics=[]
    for r in rows:
        item=dict(tic_id=r['tic_id'],tmag=float(r['host']['tmag']),stratum=r['host']['stratum'],selection_probability=r['host']['selection_probability'],
                  audited_sector_count=len(r['selected_sectors']),timing_caveat_QLP_sectors=','.join(str(x['sector']) for x in r['raw_diagnostics'] if x['author']=='QLP' and x['sector'] in (80,83,85)))
        primary=next(m for m in r['measurements'] if m['group']=='selected_products' and m['variant']=='corrected')
        item['point_scatter_ppt']=median(x['point_scatter_ppt'] for x in primary['noise'])
        item['duty_cycle']=median(x['duty_cycle'] for x in primary['noise'])
        item['depth_retained']=primary['injected_depth_retention'].get('retained_depth_fraction')
        item['transit_cadences_retained']=primary['injected_depth_retention'].get('common_transit_cadence_fraction')
        for key in ('0.5','1','2','4'):
            item['noise_'+key+'h_ppt']=median(x['timescales'][key]['scatter_ppt'] for x in primary['noise'])
            item['red_'+key+'h']=median(x['timescales'][key]['red_noise_inflation'] for x in primary['noise'])
        for group,variant,label in [('selected_products','SAP','SAP'),('QLP_supplied_apertures','small','QLP_small'),('QLP_supplied_apertures','large','QLP_large')]:
            measure=next((m for m in r['measurements'] if m['group']==group and m['variant']==variant),None)
            item[label+'_ratio_1h']=None;item[label+'_depth_retained']=None;item[label+'_artifact_tail_difference']=None
            if measure:
                matched=measure['matched_time_noise'];ref={x['sector']:x for x in matched['reference']};ratios=[];tails=[]
                for a in matched['alternative']:
                    b=ref.get(a['sector'])
                    if not b:continue
                    an=a['timescales']['1'];bn=b['timescales']['1']
                    if an['scatter_ppt'] is not None and bn['scatter_ppt']:
                        ratios.append(an['scatter_ppt']/bn['scatter_ppt'])
                    if an['fraction_beyond_5_mad'] is not None and bn['fraction_beyond_5_mad'] is not None:
                        tails.append(an['fraction_beyond_5_mad']-bn['fraction_beyond_5_mad'])
                item[label+'_ratio_1h']=median(ratios);item[label+'_depth_retained']=measure['injected_depth_retention'].get('retained_depth_fraction')
                item[label+'_artifact_tail_difference']=median(tails)
        metrics.append(item)
    out=P11/'results/noise_summary';out.mkdir(parents=True,exist_ok=True)
    with (out/'host_measurements.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(metrics[0]));w.writeheader();w.writerows(metrics)
    rng=np.random.Generator(np.random.PCG64(2026091204))
    strata=sorted(set(r['stratum'] for r in metrics));indices=[]
    for stratum in strata:
        ix=np.array([i for i,r in enumerate(metrics) if r['stratum']==stratum])
        indices.append(rng.choice(ix,size=(10000,len(ix)),replace=True))
    resamples=np.concatenate(indices,axis=1);stats={}
    fields=[k for k in metrics[0] if k not in ('tic_id','tmag','stratum','selection_probability','timing_caveat_QLP_sectors')]
    for name in fields:
        a=np.array([r[name] if r[name] is not None else np.nan for r in metrics],dtype=float)
        boots=np.nanmedian(a[resamples],axis=1)
        stats[name]=dict(n_finite=int(np.isfinite(a).sum()),n_total=60,median=float(np.nanmedian(a)),
                         host_bootstrap_95_interval=np.nanquantile(boots,[0.025,0.975]).tolist())
    summary=dict(utc=utc(),n_hosts=60,status_counts={'OK':60},stratum_counts=dict(Counter(r['stratum'] for r in metrics)),
        statistics=stats,bootstrap=dict(unit='host',replicates=10000,seed=2026091204,stratified_by='registered magnitude strata',
            interpretation='Descriptive median for the deliberate 30/15/15 audit allocation; not a population-weighted survey estimate'),
        source_sha256=sha(__file__),caveats=['QLP sectors 80/83/85 were found unresolved by the independent timing audit after these descriptive cache preparations. Their original measurements remain labelled, not silently discarded.',
            'Depth retention is the paired flux-level injection test, not a pixel-level extraction test.',
            'Supplied small/large aperture errors missing from FITS use the original robust error-filling recipe; no physical chi-squared or C discrimination is claimed.',
            'Instrument-noise calibration from full FITS headers is in instrument_noise_model.json and supersedes the compact-header placeholder in per-host raw diagnostics.'])
    write(out/'summary.json',summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    colors=['#4662ab','#15806e','#bf7843']
    x=np.array([0.5,1,2,4])
    for stratum,color in zip(strata,colors):
        subset=[r for r in metrics if r['stratum']==stratum]
        vals=np.array([[r[f'noise_{h}h_ppt'] for h in ('0.5','1','2','4')] for r in subset],dtype=float)
        med=np.nanmedian(vals,axis=0);lo,hi=np.nanquantile(vals,[.25,.75],axis=0)
        axes[0].plot(x,med,'o-',color=color,label=f'Tmag {stratum} (n={len(subset)})');axes[0].fill_between(x,lo,hi,color=color,alpha=.12)
    axes[0].set(xscale='log',xticks=x,xticklabels=['0.5','1','2','4'],xlabel='Bin duration (hours)',ylabel='Robust scatter (ppt)',title='Transit-scale noise; bands show host IQR');axes[0].legend(fontsize=8)
    axes[0].minorticks_off()
    axes[1].scatter([r['tmag'] for r in metrics],[100*r['depth_retained'] for r in metrics],color='#4662ab',alpha=.75,s=24)
    axes[1].axhline(95,color='#bf7843',ls='--',lw=1,label='95% future-pilot requirement')
    axes[1].set(xlabel='TESS magnitude',ylabel='Injected depth retained (%)',title='Flux-level preservation through P10 preparation');axes[1].legend(fontsize=8)
    fig.suptitle('P11 input audit — descriptive cached-flux diagnostics',fontweight='bold')
    fig.savefig(out/'noise_audit.png',dpi=170);plt.close(fig)
    policy=input_policy()
    append_event(P11/'manifests/queue_intervals.jsonl',dict(event='interval',phase='audit_analysis',started_utc=started,ended_utc=utc(),wall_seconds=time.perf_counter()-timer))
    write(P11/'results/resource_accounting.json',resources())
    print('noise medians',{k:v['median'] for k,v in stats.items() if k in ('point_scatter_ppt','noise_1h_ppt','depth_retained','SAP_ratio_1h','QLP_small_ratio_1h','QLP_large_ratio_1h')},flush=True)
    print('cached hosts with >=3 sectors after all timing exclusions',policy['cached_hosts_with_three_sectors'],flush=True)


if __name__=='__main__':summarize()
