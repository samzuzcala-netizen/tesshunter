"""Historical analytic controls and transparent yield scenarios; post-lock external comparison."""
from common import *
import argparse,math,collections
import numpy as np
import pandas as pd
from scoring import match_signal,wilson

def prepare():
    frozen_imports()
    from tesshunter.survey_p8 import load_audit_products,harmonise_cadence
    original=REPO/'data/survey/p8/injection_outcomes_p8.csv';df=pd.read_csv(original);rows=[];sources={str(original.relative_to(REPO)):sha(original)}
    for tic,g in df.groupby('tic_id',sort=False):
        products,_=harmonise_cadence(load_audit_products(int(tic),REPO/'data/survey/audit_lc',sector_min=56),200/60)
        times=np.sort(np.concatenate([p['time'][np.isfinite(p['time'])&np.isfinite(p['flux'])] for p in products]))
        for _,r in g.iterrows():
            path=REPO/'data/survey/runs/inj_p8/results'/f'{r.job_id}.json';sr=read(path);im=sr['injection_model'];star=sr['star']
            sources[str(path.relative_to(REPO))]=sha(path)
            truth=dict(period=im['period'],epoch_btjd=im['t0'],duration_hours=24*im['t14_days'])
            prods=sr['result']['provenance']['products'];spoc=sum(p['author']=='SPOC' for p in prods)/len(prods)
            row=dict(job_id=r.job_id,tic_id=int(tic),period=float(r.period),radius_re=float(r.rp_earth),snr_expected=float(r.snr_expected),
              tmag=star.get('tmag'),teff=star.get('teff_k'),rstar=star.get('radius_rsun'),n_sectors=len(prods),spoc_fraction=spoc,
              product_group='SPOC-majority' if spoc>=.5 else 'FFI-majority',rotation_amplitude_ppt=float(r.rot_amp_ppt),
              legacy_search=bool(r.recovered),legacy_S=bool(r.through_funnel_pregated),search=False,pre=False,A=False,S=False,comparison_status='complete')
            matches=[]
            for q in sr['result'].get('planets',[]):
                m=match_signal(times,truth,dict(period=q['period_days'],t0=q['epoch_btjd'],duration=q['duration_days']))
                if m['matched']:matches.append((q,m))
            if matches:
                q,m=sorted(matches,key=lambda x:(-x[1]['matched_events'],x[1]['mean_normalized_timing_residual'],x[0]['planet_num']))[0]
                row['search']=True
                row['pre']=bool(q.get('stitch_epoch_consistent') and (q.get('stitch_snr') or 0)>=7.1 and (q.get('stitch_n_transits') or 0)>=3)
                if row['pre']:
                    key=f'tic{tic}_P{q["period_days"]:.4f}';root=REPO/'data/survey/p8/inj_funnel'/r.job_id;ap=root/'stageA'/f'{key}.json'
                    if ap.exists():
                        a=read(ap);sources[str(ap.relative_to(REPO))]=sha(ap)
                        if abs(a['survey']['period']-q['period_days'])>1e-9:row.update(comparison_status='different_saved_candidate',A=None,S=None)
                        elif a['decision']=='PASS':
                            ae=a['per_ephemeris'][a['chosen_ephemeris']]['ephemeris'];row['A']=match_signal(times,truth,ae)['matched']
                            if row['A']:
                                sp=root/'secondary'/f'{key}.json'
                                if sp.exists():row['S']=read(sp)['gate'] in ('PASS','HOLD');sources[str(sp.relative_to(REPO))]=sha(sp)
                                else:row.update(comparison_status='secondary_unavailable',S=None)
                    else:row.update(comparison_status='stageA_unavailable_for_selected_signal',A=None,S=None)
            rows.append(row)
        print('historical injection host',int(tic),flush=True)
    dst=P9/'calibration';dst.mkdir(exist_ok=True)
    frame=pd.DataFrame(rows)
    for g in ['search','pre','A','S']:frame[g]=frame[g].astype(float)
    frame.to_csv(dst/'p8_injections_rescored.csv',index=False)
    write(dst/'p8_source_hashes.json',sources)
    write(dst/'preparation_receipt.json',dict(utc=utc(),script_sha256=sha(Path(__file__)),protocol_sha256=sha(P9/'protocol/COMPARISON.md'),
      n_rows=len(rows),n_hosts=df.tic_id.nunique(),status_counts=dict(collections.Counter(r['comparison_status'] for r in rows))))

def compare():
    from metrics import label_bin
    real=pd.read_csv(P9/'results/analysis_table.csv');real=real[(real.label=='positive')&(real.eligibility=='eligible')]
    inj=pd.read_csv(P9/'calibration/p8_injections_rescored.csv');matches=[]
    for _,r in real.iterrows():
        finite=np.isfinite(r.snr_expected) if pd.notna(r.snr_expected) else False
        def ratio(x,y,f):return (x/y>=1/f)&(x/y<=f) if y and np.isfinite(y) else np.zeros(len(x),bool)
        masks=dict(period=ratio(inj.period,r.period,1.5),radius=ratio(inj.radius_re,r.radius_re,1.5),
          snr=ratio(inj.snr_expected,r.snr_expected,2) if finite else np.zeros(len(inj),bool),
          tmag=abs(inj.tmag-r.tmag)<=.5,teff=abs(inj.teff-r.teff)<=300,rstar=abs(inj.rstar-r.rstar)<=.1,
          sectors=ratio(inj.n_sectors,r.n_sectors,2),product=inj.product_group==r.product_group,
          spoc_fraction=abs(inj.spoc_fraction-r.actual_spoc_fraction)<=.25)
        good=np.logical_and.reduce(list(masks.values()));m=inj[good]
        matches.append(dict(truth_id=r.truth_id,tic_id=int(r.tic_id),individual_caliper_n={k:int(np.sum(v)) for k,v in masks.items()},
          n_matching_injections=len(m),n_matching_hosts=m.tic_id.nunique(),n_matching_missing_S=int(m.S.isna().sum()),matches=list(m.job_id),
          cell=f'{"long" if r.period>=10 else "short"}/{"weak" if not finite or r.snr_expected<20 else "strong"}/{r.product_group}'))
    supported=[m for m in matches if m['n_matching_hosts']>=5]
    cells=collections.defaultdict(set)
    for m in supported:cells[m['cell']].add(m['tic_id'])
    accepted=[m for m in supported if len(cells[m['cell']])>=5];nh=len(set(m['tic_id'] for m in accepted))
    out=dict(utc=utc(),matches=matches,n_real=len(real),n_real_with_five_injection_hosts=len(supported),
      cell_host_counts={k:len(v) for k,v in cells.items()},n_supported_real_hosts=nh,
      inference_status='unsupported' if nh<10 else 'supported_pending_bootstrap',
      reason='Product, coverage and stellar overlap are required; no relaxation to create an apparent calibration.',
      legacy_counts={g:int(inj[g].sum()) for g in ['legacy_search','legacy_S']},
      rescored_counts={g:int(inj[g].sum()) for g in ['search','pre','A','S']},
      rescored_missing_counts={g:int(inj[g].isna().sum()) for g in ['search','pre','A','S']},
      rescoring_status_counts=inj.comparison_status.value_counts().to_dict(),n_injections=len(inj),n_injection_hosts=inj.tic_id.nunique(),
      transplantation='not performed: donor noise removal, exposure/dilution transfer and spatial consistency not validated',
      pixel_scope='Historical analytic injections alter flux and SAP only; no pixel-localization calibration')
    # With no adequate supported population, ratios of unmatched samples are not reported as optimism.
    if nh>=10:raise RuntimeError('Supported overlap found: implement and audit preregistered two-population cluster bootstrap before inference')
    write(P9/'results/analytic_comparison.json',out)
    bins=[]
    for population,df in [('real',real),('analytic',inj)]:
        for k,g in df.groupby([label_bin(v,[0,12,20,50,float('inf')],['<12','12–20','20–50','>=50']) for v in df.snr_expected]):
            for gate in ['search','pre','A','S']:
                kpass=int(g[gate].sum());nmissing=int(g[gate].isna().sum());n=len(g)
                bins.append(dict(population=population,snr_bin=k,gate=gate,k=kpass,n=n,n_missing=nmissing,
                  rate_lower_bound=kpass/n,rate_upper_bound=(kpass+nmissing)/n,
                  complete_only_rate=float(g[gate].mean()),complete_only_wilson95=wilson(kpass,n-nmissing),
                  interpretation='UNMATCHED descriptive; missing A/S are bounds, not failures; not an optimism estimate'))
    write(P9/'results/analytic_unmatched_snr_table.json',bins)
    print('comparison',out['inference_status'],'supported real hosts',nh,flush=True)

def yield_scenarios():
    source=REPO/'data/survey/p8/expected_yield_p8.json';historical=read(source)
    anchors={k+'_incumbent':historical['expected_new_signals']['through_funnel'][k] for k in ['high','mid','low']};rows=[];stage_bounds=[]
    for model,field in [('DC15_adopted_giants','through_funnel'),('HU19_normalization_sensitivity','through_funnel_hu19')]:
        for prior in ['high','mid','low']:
            early=historical['expected_new_signals'][field][prior]
            for q in [0,.05,.1,.25,.5,1]:
                mu=early*q;rows.append(dict(occurrence_assumption=model,incumbent_assumption=prior,expected_new_early_S=early,late_retention=q,
                  expected_new_submit_equivalent=mu,probability_zero_conditional_Poisson=math.exp(-mu)))
            if model=='DC15_adopted_giants':
                search=historical['expected_new_signals']['search_only'][prior]
                for stage,lo,hi,basis in [('search',search,search,'historical calibrated model'),('pre',early,search,'nested-funnel bounds'),
                  ('A',early,search,'nested-funnel bounds'),('S',early,early,'historical calibrated model'),
                  ('B',0,early,'unsupported late efficiency'),('C',0,early,'unsupported late efficiency'),
                  ('HOLD',0,early,'separate disposition; unsupported late efficiency'),('SUBMIT_equivalent',0,early,'unsupported late efficiency')]:
                    stage_bounds.append(dict(incumbent_assumption=prior,stage=stage,lower=lo,upper=hi,basis=basis))
    pd.DataFrame(rows).to_csv(P9/'results/yield_scenarios.csv',index=False)
    pd.DataFrame(stage_bounds).to_csv(P9/'results/yield_stage_bounds.csv',index=False)
    write(P9/'results/yield_scenarios.json',dict(utc=utc(),status='scenarios, not a calibrated posterior',rows=rows,stage_bounds=stage_bounds,
      source_sha256=sha(source),historical_model=historical,
      late_gate_calibration='No strict P8-like positive host in selected controls after corrected cadence inventory',
      efficiency_accounting='Only conditional B/C/D retention multiplies already calibrated early-S expected yield; never multiply external end-to-end retention again',
      uncertainty='Incumbent and occurrence alternatives are labelled assumptions; finite external calibration and product-selection bias prevent a predictive posterior. Conditional Poisson count variation is shown, not all uncertainty.',
      stage_expectations=dict(search='historical model',pre='bounded between S and search',A='bounded between S and search',S=anchors,
        B='unsupported; bounded 0 to early-S',C='unsupported; bounded 0 to B',HOLD='unsupported; a disposition distinct from submission',SUBMIT_equivalent='unsupported; scenarios')))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    q=np.linspace(0,1,200);fig,ax=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for (name,early),color in zip(anchors.items(),['#467E95','#232F48','#AF6740']):
        ax[0].plot(q,early*q,label=name.replace('_',' '),color=color);ax[1].plot(q,np.exp(-early*q),color=color)
    ax[0].set(xlabel='Assumed conditional B/C/D retention',ylabel='Expected new submissions',title='Historical early yield × late retention');ax[0].legend(fontsize=8)
    ax[1].set(xlabel='Assumed conditional B/C/D retention',ylabel='P(zero submissions | scenario)',title='Conditional Poisson count model',ylim=(0,1))
    for a in ax:a.grid(alpha=.2)
    fig.suptitle('P9 yield scenarios — no calibrated posterior for P8',fontsize=12)
    (P9/'figures').mkdir(exist_ok=True);fig.savefig(P9/'figures/yield_scenarios.png',dpi=160);plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=['prepare','compare','yield']);a=p.parse_args()
    if a.cmd=='prepare':prepare()
    elif a.cmd=='compare':compare()
    else:yield_scenarios()
