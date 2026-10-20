"""Post-lock signal-level scoring. This module is never imported by execution."""
from common import *
import argparse, csv, math, collections
import numpy as np
import pandas as pd
from scipy.stats import norm,beta

GATES=['search','pre','A','S','B','C','D_submit','D_useful']
def observed_centers(times,period,epoch,duration):
    if len(times)==0 or not (period>0 and duration>0):return np.array([])
    centers=np.arange(math.floor((times[0]-epoch)/period),math.ceil((times[-1]-epoch)/period)+1)*period+epoch
    # Vectorized searchsorted counts; nominal 200 s samples, same preregistered window rule.
    count=np.searchsorted(times,centers+duration/2)-np.searchsorted(times,centers-duration/2)
    half=max(.5,3*duration)
    base=(np.searchsorted(times,centers+half)-np.searchsorted(times,centers-half)
          -np.searchsorted(times,centers+duration*.65)+np.searchsorted(times,centers-duration*.65))
    return centers[(count*(200/86400)/duration>=.5)&(base>=10)]

def match_signal(times,truth,candidate,ratio=1):
    p=float(candidate.get('period',0) or 0);t0=float(candidate.get('t0',float('nan')) or 0)
    dur=float(candidate.get('duration',0) or 0)
    expected=float(truth['period'])*ratio
    result=dict(ratio=ratio,period_fraction=abs(p/expected-1) if expected else None,matched=False,matched_events=0)
    if p<=0 or not np.isfinite(t0) or dur<=0 or result['period_fraction']>.01:return result
    # For alias accounting use the true primary opportunities, never pretend a host match suffices.
    true=observed_centers(times,float(truth['period']),float(truth['epoch_btjd']),float(truth['duration_hours'])/24)
    found=observed_centers(times,p,t0,dur)
    tolerance=(dur+float(truth['duration_hours'])/24)/2
    i=j=0;errors=[]
    while i<len(true) and j<len(found):
        delta=found[j]-true[i]
        if abs(delta)<=tolerance:errors.append(abs(delta)/tolerance);i+=1;j+=1
        elif delta<0:j+=1
        else:i+=1
    n=len(errors);rt=n/len(true) if len(true) else 0;rf=n/len(found) if len(found) else 0
    result.update(matched=n>=3 and rt>=.5 and rf>=.5,matched_events=n,n_truth_opportunities=len(true),
      n_found_opportunities=len(found),truth_fraction=rt,found_fraction=rf,
      mean_normalized_timing_residual=float(np.mean(errors)) if errors else None)
    return result

def wilson(k,n):
    if not n:return [None,None]
    z=norm.ppf(.975);p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]

def verify_lock(tic):
    lock=read(P9/'results/locks'/f'tic{tic}.json')
    for path,h in lock['sha256'].items():
        if sha(P9/path)!=h:raise RuntimeError(f'Blind outcome changed after lock: {path}')
    return lock

def times_for(tic):
    frozen_imports()
    from tesshunter.survey_p8 import load_audit_products,harmonise_cadence
    prods,_=harmonise_cadence(load_audit_products(tic,P9/'inputs/raw',sector_min=56),200/60)
    return np.sort(np.concatenate([p['time'][np.isfinite(p['time'])&np.isfinite(p['flux'])] for p in prods]))

def accepted_match(times,truth,eph,allow_alias=False):
    matches=[match_signal(times,truth,eph,q) for q in ((1,.5,2,1/3,3) if allow_alias else (1,))]
    good=[m for m in matches if m['matched']]
    return sorted(good,key=lambda m:(-m['matched_events'],m['mean_normalized_timing_residual']))[0] if good else matches[0]

def score_one(r,eligibility,force_key=None,allow_alias=False):
    tic=int(r['tic_id']);lock=verify_lock(tic);root=P9/'results/blind'/f'tic{tic}'
    result=dict(truth_id=r['truth_id'],tic_id=tic,label=r['label'],subtype=r['subtype'],stratum=r['stratum'],
      eligibility=eligibility['status'],opportunities=eligibility.get('opportunities'),
      outcome_locked_utc=lock['utc'],**{g:False for g in GATES})
    if eligibility['status']!='eligible':return dict(result,first_termination=eligibility['status'],operational='preparation')
    op=P9/'results/operations'/f'search_tic{tic}.json'
    if op.exists() and read(op).get('status')!='complete':
        return dict(result,first_termination='search_execution',operational='search',termination_reason='Search operation exhausted its registered attempts')
    srpath=root/'search/results'/f'tic{tic}.json'
    if not srpath.exists():return dict(result,first_termination='search_unavailable',operational='search')
    sr=read(srpath)
    if sr.get('status')!='ok':return dict(result,first_termination='search_execution',operational='search')
    tt=times_for(tic);exact=[];aliases=[];allmatches=[]
    planets=(sr.get('result') or {}).get('planets',[])
    for q in planets:
        eph={'period':q['period_days'],'t0':q['epoch_btjd'],'duration':q['duration_days']}
        m=accepted_match(tt,r,eph,allow_alias)
        allmatches.append(dict(planet_num=q['planet_num'],period=q['period_days'],match=m))
        if m['matched'] and (force_key is None or force_key==f'tic{tic}_P{q["period_days"]:.4f}'):exact.append((q,m))
        for ratio in (.5,2,1/3,3):
            am=match_signal(tt,r,eph,ratio)
            if am['matched']:aliases.append((q,am))
    best=lambda x:(-x[1]['matched_events'],x[1]['mean_normalized_timing_residual'],x[0]['planet_num'])
    result.update(n_accepted_signals=len(planets),search_budget_stop=any('would not fit' in n for n in sr.get('result',{}).get('notes',[])),
      aliases=[dict(planet_num=q['planet_num'],period=q['period_days'],**m) for q,m in aliases],all_search_matches=allmatches)
    if not exact:
        result.update(first_termination='search',operational=None)
        if aliases:
            q,m=sorted(aliases,key=best)[0];result['alias_candidate_key']=f'tic{tic}_P{q["period_days"]:.4f}'
        return result
    q,m=sorted(exact,key=best)[0];key=f'tic{tic}_P{q["period_days"]:.4f}'
    result.update(search=True,candidate_key=key,search_match=m,detected_period=q['period_days'],matched_planet_num=q['planet_num'])
    pregate=bool(q.get('stitch_epoch_consistent')) and (q.get('stitch_snr') or 0)>=7.1 and (q.get('stitch_n_transits') or 0)>=3
    if not pregate:return dict(result,first_termination='pre',operational=None,
      pregate_fields={k:q.get(k) for k in ['stitch_epoch_consistent','stitch_snr','stitch_n_transits']})
    result['pre']=True
    for stage,folder,field,allowed in [('A','stageA','decision',{'PASS'}),('S','secondary','gate',{'PASS','HOLD'}),
      ('B','stageB','decision',{'PASS'}),('C','stageC','decision',{'PASS'})]:
        path=root/folder/f'{key}.json'
        if not path.exists():return dict(result,first_termination=stage+'_unavailable',operational=stage)
        rec=read(path);decision=rec.get(field)
        if decision in ('ERROR','SKIP',None):return dict(result,first_termination=stage+'_execution',operational=stage,termination_reason=rec.get('reason'))
        if decision not in allowed:return dict(result,first_termination=stage,operational=None,termination_reason=rec.get('reason'))
        if stage=='A':eph=rec['per_ephemeris'][rec['chosen_ephemeris']]['ephemeris']
        elif stage=='C':
            b=rec['blind'];eph=dict(period=b['period'],t0=b['T0_btjd'],duration=b['duration_days'])
        else:eph=None
        if eph:
            gm=accepted_match(tt,r,eph,allow_alias)
            result[stage+'_match']=gm
            if not gm['matched']:return dict(result,first_termination=stage+'_signal_switch',operational=None,termination_reason='Accepted ephemeris no longer matches this truth signal')
        result[stage]=True
    verdictpath=root/'final'/f'{key}.json'
    if not verdictpath.exists():return dict(result,first_termination='D_unavailable',operational='D')
    v=read(verdictpath);result.update(verdict=v['scientific_verdict'],hold_reason=v.get('hold_reason'),final_reason=v.get('reason'),
      actual_submission_eligible=False)
    if v['scientific_verdict']=='OPERATIONAL_INCOMPLETE':return dict(result,first_termination='D_execution',operational='D')
    fitpath=root/'fit'/f'{key}.json'
    if fitpath.exists():
        a=read(fitpath).get('adopted') or {}
        dm=accepted_match(tt,r,dict(period=a.get('period'),t0=a.get('t0_btjd'),duration=(a.get('t14_hours') or 0)/24),allow_alias)
        result['D_match']=dm
        if not dm['matched']:return dict(result,first_termination='D_signal_switch',operational=None)
    result['D_submit']=v['scientific_verdict']=='SUBMIT_EQUIVALENT'
    result['D_useful']=result['D_submit'] or (v['scientific_verdict']=='HOLD' and v.get('legitimate_useful_hold',False))
    return dict(result,first_termination='retained' if result['D_useful'] else 'D',operational=None)

def run(kind='final',locked_only=False):
    ids=read(P9/f'manifests/{kind}_ids.json')
    missing=[t for t in ids if not (P9/'results/locks'/f'tic{t}.json').exists()]
    if missing and not locked_only:raise RuntimeError(f'Truth remains closed: {len(missing)} hosts lack outcome locks')
    if len(missing)==len(ids):raise RuntimeError('Truth remains closed: no hosts have outcome locks')
    truth=pd.read_csv(P9/f'truth/{kind}_truth.csv');elig={r['truth_id']:r for r in read(P9/f'truth/{kind}_eligibility.json')}
    out=[]
    for _,row in truth.iterrows():
        if not (P9/'results/locks'/f'tic{int(row.tic_id)}.json').exists():continue
        r=score_one(row.to_dict(),elig[row.truth_id])
        if row.label=='negative' and r['eligibility']=='eligible':
            keys=set([f'tic{int(row.tic_id)}_P{a["period"]:.4f}' for a in r.get('all_search_matches',[]) if a['match']['matched']]+
              [f'tic{int(row.tic_id)}_P{a["period"]:.4f}' for a in r.get('aliases',[])])
            family=[score_one(row.to_dict(),elig[row.truth_id],k,True) for k in sorted(keys)]
            r['negative_family_traces']=family
            r['negative_family_gates']={g:any(s[g] for s in family) for g in GATES}
        out.append(r)
    suffix='_partial' if locked_only else ''
    write(P9/f'results/scored_signals{suffix}.json',out)
    flat=[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in out]
    pd.DataFrame(flat).to_csv(P9/f'results/scored_signals{suffix}.csv',index=False)
    write(P9/f'results/scoring_receipt{suffix}.json',dict(utc=utc(),scorer_sha256=sha(Path(__file__)),
       truth_sha256=sha(P9/f'truth/{kind}_truth.csv'),n_scored=len(out),n_selected_signals=len(truth),pending_host_ids=missing,complete=not missing))
    print('scored',len(out),'of',len(truth),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',default='final');p.add_argument('--locked-only',action='store_true');a=p.parse_args();run(a.kind,a.locked_only)
