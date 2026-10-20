"""Pure paired metrics and ordered-route rules; evaluator only."""
import numpy as np
from scipy.stats import beta

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

def bootstrap_weights(hosts,strata,seed=2026091303,draws=10000):
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
