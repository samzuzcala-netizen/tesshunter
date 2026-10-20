"""Pure paired metrics and ordered-route rules; evaluator only.

Superseded 2026-09-23 (AMENDMENTS_P12.md): ``--out`` names the outcome table (the extension calibration of 5a
and the ADOPT_SML full arm write their own table beside Part 2's), and an uninjected false-alarm search job is
recognised by ``tic<id>`` with an optional set prefix (``extfa_tic<id>``). Scoring is unchanged.
"""
from p12_common import REPO,ROOT,DATA,environment,read,write,sha,utc
environment()
import sys
sys.path.insert(0,str(REPO/'src'))
sys.path.insert(0,str(REPO/'scripts'))
import numpy as np
from scipy.stats import beta


def levels(row):
    """Unchanged P10 2d level algebra, separately from ephemeris recovery."""
    recovered=row['status']=='recovered'
    pregate=row.get('pregate') in (True,'True','true','1')
    through_a=bool(recovered and row.get('stageA')=='PASS')
    through_funnel=bool(through_a and row.get('secondary_gate') in ('PASS','HOLD'))
    return dict(recovered=recovered,through_pregate=bool(recovered and pregate),through_stageA=through_a,
        through_funnel=through_funnel,through_funnel_pregated=bool(through_funnel and pregate))


def score_row(row,predictions,prepared):
    """Evaluate one locked prediction against evaluator truth and uninjected arrays."""
    from analyze_completeness import classify
    from tesshunter import survey
    model=row['injection_model'];injection=row.get('injection') or row
    accepted=predictions.get('accepted')
    planets=[p.get('raw_candidate',p) for p in accepted] if accepted is not None else (predictions.get('result') or {}).get('planets',[])
    status=predictions.get('status')
    complete=status in ('ok','COMPLETE')
    outcome=classify(dict(status='ok' if complete else status,injection=injection,injection_model=model,result=dict(planets=planets)))
    if not complete:outcome['status']='operational_unknown'
    t=np.asarray(prepared['time'],dtype=float);f=np.asarray(prepared['flux'],dtype=float);ok=np.isfinite(f)
    resid=f[ok]-np.nanmedian(f[ok]);sigma=float(1.4826*np.median(np.abs(resid))) if ok.any() else 0.
    cad=float(np.nanmedian(np.diff(np.sort(t[ok])))) if ok.sum()>1 else 200/86400.
    transit=survey.transit_model(t[ok],period=model['period'],t0=model['t0'],rp_rs=model['rp_rs'],
        b=model['b'],a_rs=model['a_rs'],u=(model['u1'],model['u2']),exp_time_days=cad)
    delta=1-transit;inside=delta>0;n_inside=int(inside.sum())
    expected=float(np.sqrt(np.sum(delta[inside]**2))/sigma) if n_inside and sigma>0 else 0.
    n_transits=int(np.unique(np.round((t[ok][inside]-model['t0'])/model['period'])).size) if n_inside else 0
    recovered=outcome['status']=='recovered';matched=None
    if recovered:matched=next(p for p in planets if abs(float(p['period_days'])/outcome['matched_period']-1)<1e-9)
    pregate=bool(matched and matched.get('stitch_epoch_consistent') and (matched.get('stitch_snr') or 0)>=7.1 and (matched.get('stitch_n_transits') or 0)>=3) if recovered else None
    funnel=row.get('funnel') or {};rotation=prepared.get('rotation_proxy') or {}
    result=dict(job_id=row['job_id'],tic_id=int(row['tic_id']),status=outcome['status'],ratio=outcome['ratio'],
        period=float(injection['period']),period_bin=int(injection.get('period_bin',-1)),
        rp_earth=float(injection['rp_earth']) if injection.get('rp_earth') else None,rp_rs=float(injection['rp_rs']),
        b=float(injection['b']),tmag=float(injection['tmag']) if injection.get('tmag') else None,
        snr_expected=expected,n_transits_expected=n_transits,rot_amp_ppt=rotation.get('semi_amplitude_ppt'),
        rot_period=rotation.get('peak_period_days'),matched_snr=outcome['matched_snr'],matched_stitch_snr=outcome['matched_stitch_snr'],
        pregate=pregate,stageA=funnel.get('stageA'),secondary_gate=funnel.get('secondary_gate'),
        kept_snr=funnel.get('kept_snr'),n_kept=funnel.get('n_kept'),depth_over_survey=funnel.get('depth_over_survey'),
        stageA_criteria=funnel.get('stageA_criteria'),gate_by_mode=funnel.get('gate_by_mode'),
        p_const_white=funnel.get('p_const_white'),p_const_inflated=funnel.get('p_const_inflated'),
        wall_s=predictions.get('wall_s'),job_status='ok' if complete else status)
    result.update(levels(result));return result


def main(argv=None):
    import argparse,csv,json,re
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=('archival','sml'));parser.add_argument('--phase');parser.add_argument('--out')
    args=parser.parse_args(argv);phase=args.phase or ('cal_a_search' if args.arm=='archival' else 'cal_b_search')
    if (ROOT/'manifests/controller_owner.json').exists():raise RuntimeError('Evaluator requires closed workers')
    closure_path=ROOT/f'results/controllers/{phase}/closure.json';closure=read(closure_path)
    if closure['status']!='CLOSED' or closure['pending'] or not closure['all_owned_workers_closed'] or not closure['source_hashes_unchanged']:
        raise RuntimeError('Evaluator requires a clean phase closure')
    lock_path=ROOT/f'manifests/{phase}_predictions_lock.json';seal=read(lock_path.with_name(lock_path.stem+'_seal.json'))
    if sha(lock_path)!=seal['sha256']:raise RuntimeError('Prediction lock changed')
    locked=read(lock_path)
    if locked['closure_sha256']!=sha(closure_path):raise RuntimeError('Closure changed after prediction lock')
    outcomes=[]
    for prediction in locked['jobs']:
        receipt_path=ROOT/f'results/preparation/{args.arm}/{prediction["job_id"]}.json'
        if not receipt_path.exists():
            if re.fullmatch(r'(?:[a-z]+_)?tic\d+',prediction['job_id']):continue
            raise RuntimeError('Injection preparation receipt missing')
        receipt=read(receipt_path)
        if sha(REPO/receipt['truth_path'])!=receipt['truth_sha256']:raise RuntimeError('Evaluator truth changed')
        truth=read(REPO/receipt['truth_path'])
        if sha(REPO/receipt['uninjected_path'])!=receipt['uninjected_sha256']:raise RuntimeError('Uninjected reference changed')
        with np.load(REPO/receipt['uninjected_path'],allow_pickle=False) as z:prepared={k:z[k] for k in z.files}
        prov=read((REPO/receipt['uninjected_path']).with_suffix('.json'));prepared['rotation_proxy']=prov.get('rotation_proxy')
        outcomes.append(score_row(truth,prediction,prepared))
    path=(REPO/args.out) if args.out else ROOT/f'results/part2/injection_outcomes_{args.arm}.csv';path.parent.mkdir(parents=True,exist_ok=True)
    if not outcomes:raise RuntimeError('No injection outcomes to evaluate')
    with path.open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(outcomes[0]));writer.writeheader();writer.writerows(outcomes)
    print('injection outcomes',len(outcomes),flush=True);return 0

def match(model,eph,ratios=(1.,)):
    if not eph:return None
    for ratio in ratios:
        pf=float(eph['period_days']);p=float(model['period'])
        if abs(pf/(p*ratio)-1)<.01:
            base=min(p,pf);dt=(float(eph['epoch_btjd'])-float(model['t0'])+.5*base)%base-.5*base
            tol=max(float(model.get('t14_days') or 0),float(eph.get('duration_days') or 0),.02)
            if abs(dt)<=tol:return ratio
    return None

def s_gate(s,S):
    if s.get('status')!='COMPLETE':return 'UNKNOWN'
    m=s['measurement']
    if m.get('gate') not in ('PASS','FAIL','HOLD'):return 'UNKNOWN'
    if S=='S2':return 'PASS'
    if S=='S0':return m['gate']
    return m.get('secondary',{}).get('gate_by_mode_p10',{}).get('recurrent_bound','UNKNOWN')

def ordered(a,s,b,c,S,D,E,pre=True):
    if not pre:return 'REJECT'
    if a.get('status')!='COMPLETE':return 'UNRESOLVED'
    if a['measurement'].get('decision')=='FAIL':return 'REJECT'
    if a['measurement'].get('decision')!='PASS':return 'UNRESOLVED'
    gate=s_gate(s,S)
    if gate=='FAIL':return 'REJECT'
    if gate!='PASS':return 'UNRESOLVED'
    if b.get('status')!='COMPLETE':return 'UNRESOLVED'
    if b['measurement'].get('decision')=='FAIL':return 'REJECT'
    if b['measurement'].get('decision')!='PASS':return 'UNRESOLVED'
    if c.get('status')!='COMPLETE':return 'UNRESOLVED'
    status=c.get('policy_decisions',{}).get(f'D{D}_E{E}',{}).get('status','UNRESOLVED')
    return status if status in ('PASS','REJECT','UNRESOLVED') else 'UNRESOLVED'

def isolated(s,c,S,D,E):
    gate=s_gate(s,S)
    if gate=='FAIL':return 'REJECT'
    if gate!='PASS':return 'UNRESOLVED'
    if c.get('status')!='COMPLETE':return 'UNRESOLVED'
    return c.get('policy_decisions',{}).get(f'D{D}_E{E}',{}).get('status','UNRESOLVED')

def u10(a,s,pre=True):
    return bool(pre and a.get('status')=='COMPLETE' and a['measurement'].get('decision')=='PASS' and s_gate(s,'S0')=='PASS')

def binomial(k,n):
    if not n:return dict(k=k,n=n,rate=None,ci95=[None,None])
    return dict(k=int(k),n=int(n),rate=float(k/n),ci95=[0. if k==0 else float(beta.ppf(.025,k,n-k+1)),
        1. if k==n else float(beta.ppf(.975,k+1,n-k))],method='Clopper-Pearson exact interval; zero empirical events does not establish zero risk')

def bootstrap_weights(hosts,strata,seed=2026092001,draws=10000):
    rng=np.random.Generator(np.random.PCG64(seed));weights=np.zeros((draws,len(hosts)),dtype=np.int16)
    for label in sorted(set(strata)):
        idx=np.flatnonzero(np.asarray(strata)==label);n=len(idx)
        weights[:,idx]=rng.multinomial(n,np.full(n,1/n),size=draws)
    return weights

def paired(rows,baseline,proposed,mask,hosts,weights):
    rows=[r for r,m in zip(rows,mask) if m]
    if not rows:return dict(n=0,gain_pp=None,ci95_pp=[None,None],lower_one_sided95_pp=None)
    by={h:i for i,h in enumerate(hosts)};den=np.zeros(len(hosts));delta=np.zeros(len(hosts));b=0;y=0;wins=0;losses=0
    for r in rows:
        i=by[r['tic_id']];x=bool(r[baseline]);v=bool(r[proposed]);den[i]+=1;delta[i]+=int(v)-int(x)
        b+=x;y+=v;wins+=v and not x;losses+=x and not v
    draw_den=weights@den;draw_delta=weights@delta;valid=draw_den>0;rates=draw_delta[valid]/draw_den[valid]*100
    return dict(n=len(rows),hosts_with_bin=int(np.count_nonzero(den)),baseline=int(b),proposed=int(y),wins=int(wins),losses=int(losses),
        baseline_rate=b/len(rows),proposed_rate=y/len(rows),gain_pp=(y-b)/len(rows)*100,
        ci95_pp=np.quantile(rates,[.025,.975]).tolist(),lower_one_sided95_pp=float(np.quantile(rates,.05)),
        valid_host_bootstraps=int(valid.sum()),degenerate_bootstrap=bool(np.ptp(rates)==0),
        estimand='Paired empirical evaluated population; resample complete hosts within registered metadata strata; no missing-domain extrapolation')

if __name__=='__main__':main()
