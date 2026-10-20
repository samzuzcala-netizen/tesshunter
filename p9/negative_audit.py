"""Post-lock negative timing audit and conservative host-candidate upper bounds.

No alternative match is credited to primary counts. Unrelated candidates retain
unknown truth; their inclusion supplies an upper bound, never a false-positive label.
"""
from common import *
import argparse, csv, math
import numpy as np
import pandas as pd
from scoring import GATES,match_signal,times_for,verify_lock
from metrics import estimate
from tables import table,percent,interval


def candidate_paths(tic):
    root=P9/'results/blind'/f'tic{tic}';sr=read(root/'search/results'/f'tic{tic}.json')
    output=[]
    for q in sr.get('result',{}).get('planets',[]):
        key=f'tic{tic}_P{q["period_days"]:.4f}'
        d=dict(key=key,period=q['period_days'],operational=None,**{g:False for g in GATES});d['search']=True
        pre=bool(q.get('stitch_epoch_consistent') and (q.get('stitch_snr') or 0)>=7.1 and (q.get('stitch_n_transits') or 0)>=3)
        d['pre']=pre;d['first_termination']='pre'
        if pre:
            for stage,folder,field,allowed in [('A','stageA','decision',{'PASS'}),('S','secondary','gate',{'PASS','HOLD'}),
              ('B','stageB','decision',{'PASS'}),('C','stageC','decision',{'PASS'})]:
                path=root/folder/f'{key}.json';rec=read(path) if path.exists() else {};decision=rec.get(field)
                d['first_termination']=stage
                if decision in ('ERROR','SKIP',None):d['operational']=stage;break
                if decision not in allowed:break
                d[stage]=True
            else:
                f=root/'final'/f'{key}.json';review=read(f) if f.exists() else {}
                d['first_termination']='D';verdict=review.get('scientific_verdict')
                if verdict in (None,'OPERATIONAL_INCOMPLETE'):d['operational']='D'
                else:
                    d['D_submit']=verdict=='SUBMIT_EQUIVALENT'
                    d['D_useful']=d['D_submit'] or (verdict=='HOLD' and review.get('legitimate_useful_hold',False))
        output.append(d)
    return output,sr


def run(partial=False):
    suffix='_partial' if partial else ''
    scores=read(P9/f'results/scored_signals{suffix}.json')
    negative=[s for s in scores if s['label']=='negative' and s['eligibility']=='eligible']
    truth=pd.read_csv(P9/'truth/final_truth.csv').set_index('truth_id')
    features={f['truth_id']:f for f in read(P9/'results/diagnostic_features.json')}
    eb_path=P9/'truth/catalogues/tess_eb.csv';eb=pd.read_csv(eb_path)
    rows=[];allpaths=[];upper=[];nominal=[]
    for s in negative:
        tic=int(s['tic_id']);verify_lock(tic);r=truth.loc[s['truth_id']].to_dict();tt=times_for(tic)
        paths,sr=candidate_paths(tic);allpaths.extend(paths)
        operations=[p['operational'] for p in paths if p['operational']]
        u=dict(tic_id=tic,stratum=s['stratum'],operational=min(operations,key=lambda v:['search','pre','A','S','B','C','D'].index(v)) if operations else None,
          **{g:any(p[g] for p in paths) for g in GATES});upper.append(u)
        ops=[p['operational'] for p in s.get('negative_family_traces',[]) if p.get('operational')]
        if s.get('operational'):ops.append(s['operational'])
        nominal.append(dict(tic_id=tic,stratum=s['stratum'],operational=min(ops,key=lambda v:['search','pre','A','S','B','C','D'].index(v)) if ops else None,
          **{g:s.get('negative_family_gates',{}).get(g,False) for g in GATES}))
        near=[]
        for q in sr.get('result',{}).get('planets',[]):
            ratio=q['period_days']/r['period'];base=[1,.5,2,1/3,3]
            k=round(ratio) if ratio>=1 else round(1/ratio)
            if k>=1:base.append(float(k) if ratio>=1 else 1/k)
            ratios=sorted(set(base));best=min(ratios,key=lambda v:abs(ratio/v-1))
            if abs(ratio/best-1)>.01:continue
            match=match_signal(tt,r,dict(period=q['period_days'],t0=q['epoch_btjd'],duration=q['duration_days']),best)
            registered=best in (1,.5,2,1/3,3)
            key=f'tic{tic}_P{q["period_days"]:.4f}';path=next(p for p in paths if p['key']==key)
            near.append(dict(key=key,period=q['period_days'],period_ratio=ratio,nearest_harmonic=best,registered=registered,
              nominal_rule_matched=match['matched'],event_match=match,native_first_termination=path['first_termination'],
              native_operational=path['operational'],native_C=path['C'],native_D_useful=path['D_useful'],
              interpretation='Period proximity is diagnostic only; unregistered harmonics and failed event matches are not credited or given a false-positive label'))
        f=features.get(s['truth_id'],{})
        timing_sigma=f.get('ephemeris_sigma_over_duration');timing_source='frozen truth-manifest diagnostic'
        timing_parameters=None
        # The original EB truth rows omitted error columns that remain in the
        # immutable catalogue. Recover these only for a labelled post-lock audit.
        source_rows=eb[eb.tess_id==tic]
        if s['truth_id'].startswith('TESS-EB-'):
            signal=int(s['truth_id'].rsplit('-',1)[1]);source_rows=source_rows[source_rows.signal_id==signal]
        else:source_rows=source_rows.iloc[:0]
        if len(source_rows)==1:
            source=source_rows.iloc[0];pe=source.period_uncert;ee=source.bjd0_uncert
            if pd.notna(pe) and pd.notna(ee):
                cycles=max(abs((tt.min()-r['epoch_btjd'])/r['period']),abs((tt.max()-r['epoch_btjd'])/r['period']))
                timing_sigma=float(np.hypot(float(ee),cycles*float(pe))/(r['duration_hours']/24))
                timing_parameters=dict(period_uncert_days=float(pe),epoch_uncert_days=float(ee),maximum_cycles=float(cycles))
                timing_source='Post-lock diagnostic from frozen MAST EB catalogue; errors were not copied into the original truth manifest; independent-error approximation, no covariance or eclipse-timing variation model'
        rows.append(dict(truth_id=s['truth_id'],tic_id=tic,subtype=s['subtype'],primary_termination=s['first_termination'],
          ephemeris_sigma_over_duration=timing_sigma,timing_uncertainty_source=timing_source,timing_uncertainty_parameters=timing_parameters,near_period_candidates=near,
          host_any_candidate_gates={g:u[g] for g in GATES},host_unresolved_stage=u['operational']))
    lo=estimate(pd.DataFrame(nominal));hi=estimate(pd.DataFrame(upper))
    bounds={g:dict(registered_family_observed=lo['gates'][g]['k'],possible_host_candidate_upper=hi['gates'][g]['k']+hi['gates'][g]['n_operational_unknown'],
      n=len(negative),host_operational_unknown=hi['gates'][g]['n_operational_unknown']) for g in GATES}
    for v in bounds.values():assert v['registered_family_observed']<=v['possible_host_candidate_upper']<=v['n']
    out=dict(utc=utc(),partial=partial,controls=rows,candidate_paths=allpaths,bounds=bounds,
      host_candidate_estimate_for_upper_bound=hi,registered_family_estimate=lo,script_sha256=sha(Path(__file__)),
      frozen_EB_catalogue_sha256=sha(eb_path),
      interpretation='Primary matching remains fixed. The host-wide union is an intentionally conservative upper bound on labelled-signal survival, not a classification of unrelated candidates. Nominal ephemeris ambiguity is not silently called scientific rejection.')
    write(P9/f'results/negative_timing_audit{suffix}.json',out)
    text=['# P9 negative-control timing and escape audit','',out['interpretation'],'',
      'This is a post-lock diagnostic supplement. Integer harmonics outside the registered set are listed only when their periods agree within 1%; they receive no primary recovery credit. A close period with failed event alignment can reflect a nominal ephemeris problem, duration/window counting or a different eclipse. It does not establish a unique cause.','',
      table(['Gate','Registered exact/alias observed','Conservative any-candidate upper','Selected negatives','Operationally unknown hosts'],
        [[g,v['registered_family_observed'],v['possible_host_candidate_upper'],v['n'],v['host_operational_unknown']] for g,v in bounds.items()]),'',
      'The upper column allows any accepted candidate on that negative-control host, plus unresolved execution, to represent the labelled signal. Unrelated real planets or artifacts are not assigned the negative label. Where the upper count is zero, matching ambiguity cannot conceal a surviving candidate at that gate in these observed runs. This is an identification bound, not a new primary efficiency estimate or an independent test set.','']
    for r in rows:
        text+=['## '+r['truth_id'],'',f'TIC {r["tic_id"]}; primary termination {r["primary_termination"]}; propagated nominal ephemeris uncertainty / duration: {r["ephemeris_sigma_over_duration"]}.',
          r['timing_uncertainty_source']+'.','']
        rr=[]
        for q in r['near_period_candidates']:
            mm=q['event_match'];rr.append([q['key'],f'{q["nearest_harmonic"]:.5g}',q['registered'],q['nominal_rule_matched'],
              f'{mm.get("matched_events",0)}/{mm.get("n_truth_opportunities","?")}',
              f'{mm.get("matched_events",0)}/{mm.get("n_found_opportunities","?")}',q['native_first_termination'],q['native_operational'] or 'complete'])
        text+=[table(['Blind candidate','Period ratio','Registered','Fixed match','Matched / truth events','Matched / found events','Native termination','Execution'],rr),'']
    (P9/('NEGATIVE_AUDIT_PARTIAL.md' if partial else 'NEGATIVE_AUDIT.md')).write_text('\n'.join(text),encoding='utf-8')
    print('Negative timing audit',len(negative),'controls; C/D upper bounds',{g:bounds[g] for g in ['C','D_submit','D_useful']},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');a=p.parse_args();run(a.partial)
