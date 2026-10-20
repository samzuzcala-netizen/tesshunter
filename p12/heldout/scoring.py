"""Post-lock signal-level scoring. This module is never imported by execution.

P12 held-out copy of ``p9/scoring.py`` (4c), edits: (5) the P12 roots, (6) event opportunities from the
harness's own input selection, (7) the adapter copy (``p9_scoring_adapter.py``): the P9 event match and
candidate choice, nested credit, the alias family for negatives, and the TLS cadence floor on the Stage C
ephemeris. Outcome gates read the p12.0 D verdict (``stageD`` ``tiers``: SUBMIT tier 1 or 2 is the
SUBMIT-equivalent). Every blind record of a host is hashed into ``p12/heldout/results/locks/tic<id>.json``
before its truth row is read; a record changed after that lock is a STOP-1.
"""
from common import *
import argparse, csv, math, collections
import numpy as np
from scipy.stats import norm

GATES=['search','pre','A','S','B','C','D_submit','D_useful']
ROOT=H/'results/blind'
TRUTH=P9/'truth/final_truth.csv'

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

def lock_host(tic):
    """Hash every blind record of the host before its truth row is opened (P9's outcome lock)."""
    path=H/'results/locks'/f'tic{tic}.json'
    if path.exists():return verify_lock(tic)
    root=ROOT/f'tic{tic}'
    files={p.relative_to(H).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file()} if root.exists() else {}
    for extra in sorted((REPO/'p12/results/funnel/neg_p9_D/D').glob(f'tic{tic}_*.json')):
        files[extra.relative_to(H.parents[1]).as_posix()]=sha(extra)
    write(path,dict(utc=utc(),tic_id=tic,sha256=files,meaning='every blind outcome of this host, frozen before its truth row is read'))
    return read(path)

def verify_lock(tic):
    lock=read(H/'results/locks'/f'tic{tic}.json')
    for name,h in lock['sha256'].items():
        p=H/name if (H/name).exists() else REPO/name
        if sha(p)!=h:raise RuntimeError(f'STOP-1: blind outcome changed after lock: {name}')
    return lock

def times_for(tic):
    frozen_imports()
    from tesshunter.survey_p8 import harmonise_cadence
    prods,_=harmonise_cadence(load_products(tic),200/60)
    return np.sort(np.concatenate([p['time'][np.isfinite(p['time'])&np.isfinite(p['flux'])] for p in prods]))

def accepted_match(times,truth,eph,allow_alias=False):
    matches=[match_signal(times,truth,eph,q) for q in ((1,.5,2,1/3,3) if allow_alias else (1,))]
    good=[m for m in matches if m['matched']]
    return sorted(good,key=lambda m:(-m['matched_events'],m['mean_normalized_timing_residual']))[0] if good else matches[0]

def stage_c_ephemeris(tt,rec):
    """Edit (7): the Stage C blind ephemeris with the P10 TLS cadence floor on its duration."""
    from p9_scoring_adapter import tls_candidate
    return tls_candidate(tt,rec['blind'])

def d_record(root,key):
    path=root/'stageD'/f'{key}.json'
    if not path.exists():return None
    rec=read(path);tiers=rec.get('tiers') or {}
    return dict(verdict=tiers.get('verdict'),deciding_condition=tiers.get('deciding_condition'),
        candidate_tier=(tiers.get('candidate_tier') or {}).get('candidate_tier'),
        fired=[n for n,c in (tiers.get('conditions') or {}).items() if c.get('fired')],
        not_measurable=tiers.get('not_measurable'),fit=(rec.get('fit') or {}).get('adopted'),fit_error=(rec.get('fit') or {}).get('error'))

def eligibility(tt,r):
    opportunities=len(observed_centers(tt,float(r['period']),float(r['epoch_btjd']),float(r['duration_hours'])/24))
    return dict(status='eligible' if opportunities>=3 else 'fewer_than_3_observed_opportunities',opportunities=opportunities)

def score_one(r,elig,tt,search_lock,force_key=None,allow_alias=False):
    tic=int(r['tic_id']);lock=verify_lock(tic);root=ROOT/f'tic{tic}'
    result=dict(truth_id=r['truth_id'],tic_id=tic,label=r['label'],subtype=r.get('subtype'),stratum=r.get('stratum'),
      eligibility=elig['status'],opportunities=elig.get('opportunities'),
      outcome_locked_utc=lock['utc'],**{g:False for g in GATES})
    if elig['status']!='eligible':return dict(result,first_termination=elig['status'],operational='preparation')
    row=next((j for j in search_lock['jobs'] if j['job_id']==f'p9h_tic{tic}'),None)
    if row is None or row['status']!='COMPLETE':
        return dict(result,first_termination='search_execution',operational='search',termination_reason='Search operation exhausted its registered attempts')
    srpath=root/'search/results'/f'tic{tic}.json'
    if not srpath.exists():return dict(result,first_termination='search_unavailable',operational='search')
    sr=read(srpath)
    if sr.get('status')!='ok':return dict(result,first_termination='search_execution',operational='search')
    exact=[];aliases=[];allmatches=[]
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
    result['at_D']=at_d(root,key,tt,r,allow_alias)
    pregate=bool(q.get('stitch_epoch_consistent')) and (q.get('stitch_snr') or 0)>=7.1 and (q.get('stitch_n_transits') or 0)>=3
    if not pregate:return dict(result,first_termination='pre',operational=None,
      pregate_fields={k:q.get(k) for k in ['stitch_epoch_consistent','stitch_snr','stitch_n_transits']})
    result['pre']=True
    for stage,folder,field,allowed in [('A','stageA','decision',{'PASS'}),('S','secondary','gate',{'PASS','HOLD'}),
      ('B','stageB','decision',{'PASS'}),('C','stageC','decision',{'PASS','UNRESOLVED'})]:
        path=root/folder/f'{key}.json'
        if not path.exists():return dict(result,first_termination=stage+'_unavailable',operational=stage)
        rec=read(path);decision=rec.get(field)
        if decision in ('ERROR','SKIP',None):return dict(result,first_termination=stage+'_execution',operational=stage,termination_reason=rec.get('reason'))
        if decision not in allowed:return dict(result,first_termination=stage,operational=None,termination_reason=rec.get('reason'))
        if stage=='A':eph=rec['per_ephemeris'][rec['chosen_ephemeris']]['ephemeris']
        elif stage=='C' and decision=='PASS':eph=stage_c_ephemeris(tt,rec)
        else:eph=None
        if eph:
            gm=accepted_match(tt,r,eph,allow_alias)
            result[stage+'_match']=gm
            if not gm['matched']:return dict(result,first_termination=stage+'_signal_switch',operational=None,termination_reason='Accepted ephemeris no longer matches this truth signal')
        result[stage]=True
    v=d_record(root,key)
    if v is None:return dict(result,first_termination='D_unavailable',operational='D')
    result.update(verdict=v['verdict'],deciding_condition=v['deciding_condition'],candidate_tier=v['candidate_tier'],d_fired=v['fired'])
    if v['verdict'] is None:return dict(result,first_termination='D_execution',operational='D')
    if v['fit']:
        dm=accepted_match(tt,r,dict(period=v['fit'].get('period'),t0=v['fit'].get('t0_btjd'),duration=(v['fit'].get('t14_hours') or 0)/24),allow_alias)
        result['D_match']=dm
        if not dm['matched']:return dict(result,first_termination='D_signal_switch',operational=None)
    result['D_submit']=v['verdict']=='SUBMIT'
    result['D_useful']=result['D_submit'] or v['verdict']=='HOLD'
    return dict(result,first_termination='retained' if result['D_useful'] else 'D',operational=None)

def at_d(root,key,tt,r,allow_alias):
    """The forced route's outcome at D for this key (4a): reached D, verdict, the fit still on the truth family."""
    v=d_record(root,key)
    if v is None:return dict(reached_D=False)
    match=None
    if v['fit']:
        match=accepted_match(tt,r,dict(period=v['fit'].get('period'),t0=v['fit'].get('t0_btjd'),duration=(v['fit'].get('t14_hours') or 0)/24),allow_alias)
    return dict(reached_D=v['verdict'] is not None,verdict=v['verdict'],deciding_condition=v['deciding_condition'],
        candidate_tier=v['candidate_tier'],fired=v['fired'],fit_on_family=None if match is None else match['matched'],
        submit_equivalent=bool(v['verdict']=='SUBMIT' and (match is None or match['matched'])))

def truth_rows():
    import pandas as pd
    hosts=read(REPO/'p12/manifests/heldout_hosts.json')
    ids=set(hosts['positives'])|set(hosts['negatives'])
    truth=pd.read_csv(TRUTH)
    return [r for r in truth.to_dict('records') if int(r['tic_id']) in ids and r.get('split')=='holdout'],hosts

def run():
    """After every blind leg closed: lock each host, then read truth and score (edit 7)."""
    search_lock=read(REPO/'p12/manifests/neg_p9_search_predictions_lock.json')
    hosts=read(REPO/'p12/manifests/heldout_hosts.json')
    for t in hosts['positives']+hosts['negatives']:lock_host(int(t))
    rows,hosts=truth_rows();out=[]
    times={}
    for r in rows:
        tic=int(r['tic_id'])
        if tic not in times:times[tic]=times_for(tic)
        tt=times[tic];elig=eligibility(tt,r)
        s=score_one(r,elig,tt,search_lock)
        if r['label']=='negative' and s['eligibility']=='eligible':
            keys=set([f'tic{tic}_P{a["period"]:.4f}' for a in s.get('all_search_matches',[]) if a['match']['matched']]+
              [f'tic{tic}_P{a["period"]:.4f}' for a in s.get('aliases',[])])
            family=[score_one(r,elig,tt,search_lock,k,True) for k in sorted(keys)]
            s['negative_family_traces']=family
            s['negative_family_gates']={g:any(f[g] for f in family) for g in GATES}
            s['negative_family_at_D']=[dict(key=f.get('candidate_key'),**(f.get('at_D') or {})) for f in family]
        out.append(s)
    write(H/'results/scored_signals.json',json.loads(json.dumps(out,default=float)))
    write(H/'results/scoring_receipt.json',dict(utc=utc(),scorer_sha256=sha(Path(__file__)),truth_sha256=sha(TRUTH),
        n_scored=len(out),hosts=len({r['tic_id'] for r in rows}),search_lock_sha256=sha(REPO/'p12/manifests/neg_p9_search_predictions_lock.json')))
    print('scored',len(out),'signals on',len({r['tic_id'] for r in rows}),'hosts',flush=True)
    return out

if __name__=='__main__':
    argparse.ArgumentParser().parse_args();run()
