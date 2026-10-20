"""Post-lock P9 estimates; cluster-aware uncertainty and sparse coverage tables.

P12 held-out copy of ``p9/metrics.py`` (4c): ``cluster_draws``, ``interval`` and ``estimate`` unchanged; the
P9 analysis table, strata and figure are replaced (edit 5, P12 outputs) by the two Part 4 tables:
``p12/results/part4/p9_negatives_table.json`` (LB2a end to end, LB2b at D) and the blind rows of
``p12/results/part4/p9_positives_table.json`` (n_D). The ephemeris-assisted rows (LB3) are added by
``ephemeris_assisted_p12.py score``.
"""
from common import *
import math,collections
import numpy as np
import pandas as pd
from scipy.stats import beta
from scoring import GATES,wilson

OUT=REPO/'p12/results/part4'

def cluster_draws(df,columns,draws=5000):
    if df.empty:return np.empty((0,len(columns)+1))
    rng=np.random.default_rng(SEED);out=np.zeros((draws,len(columns)+1))
    # Each host belongs to exactly one sampling stratum, including all its signals.
    assert df.groupby('tic_id').stratum.nunique().max()==1
    for _,g in df.groupby('stratum'):
        sums=g.groupby('tic_id')[columns].sum().astype(float)
        n=g.groupby('tic_id').size().reindex(sums.index).to_numpy()
        arr=np.column_stack([n,sums.to_numpy()]);h=len(arr)
        indices=rng.integers(0,h,size=(draws,h));out+=arr[indices].sum(axis=1)
    return out

def interval(x):
    x=np.asarray(x);x=x[np.isfinite(x)]
    return list(np.quantile(x,[.025,.975]).astype(float)) if len(x) else [None,None]

def estimate(df):
    n=len(df);h=df.tic_id.nunique() if n else 0
    counts={g:int(df[g].sum()) if n else 0 for g in GATES}
    # Missing execution is not a scientific FAIL. Both the observed lower endpoint
    # and all unresolved paths surviving are retained as logical bounds.
    stage_rank={'search':0,'pre':1,'A':2,'S':3,'B':4,'C':5,'D':6}
    upper_df=df.copy();unknown={};oper=df.get('operational',pd.Series([None]*n,index=df.index,dtype=object))
    for g in GATES:
        rank=6 if g.startswith('D_') else GATES.index(g)
        mask=oper.map(lambda v:stage_rank.get(v,99)<=rank)&(~df[g].astype(bool)) if n else pd.Series([],dtype=bool)
        unknown[g]=int(mask.sum())
        if n:upper_df[g]=df[g].astype(bool)|mask
    for i,g in enumerate(GATES):
        before=n if i==0 else counts['C'] if g.startswith('D_') else counts[GATES[i-1]]
        assert counts[g]<=before,(g,counts,before)
    if n:assert ((~df.D_submit)|df.D_useful).all()
    boot=cluster_draws(df,GATES);upper_boot=cluster_draws(upper_df,GATES);stats={}
    for i,g in enumerate(GATES):
        den=n if i==0 else counts['C'] if g.startswith('D_') else counts[GATES[i-1]]
        bden=boot[:,0] if i==0 else boot[:,1+GATES.index('C')] if g.startswith('D_') else boot[:,i]
        with np.errstate(divide='ignore',invalid='ignore'):
            ub=boot[:,i+1]/boot[:,0] if n else [];cb=boot[:,i+1]/bden if n else []
        k=counts[g]
        previous=None if i==0 else 'C' if g.startswith('D_') else GATES[i-1]
        previous_unknown=unknown[previous] if previous else 0
        max_den=den+previous_unknown
        logical_conditional=[k/max_den,(k+unknown[g])/max_den] if max_den else [None,None]
        with np.errstate(divide='ignore',invalid='ignore'):
            upper_ub=upper_boot[:,i+1]/upper_boot[:,0] if n else []
            max_bden=upper_boot[:,0] if i==0 else upper_boot[:,1+GATES.index('C')] if g.startswith('D_') else upper_boot[:,i]
            conditional_lower_boot=boot[:,i+1]/max_bden if n else []
            conditional_upper_boot=upper_boot[:,i+1]/max_bden if n else []
        # This bound concerns probability of ANY retained signal on an independent host.
        hk=int(df.groupby('tic_id')[g].any().sum()) if n else 0
        host_ci=[0. if hk==0 else float(beta.ppf(.025,hk,h-hk+1)),1. if hk==h else float(beta.ppf(.975,hk+1,h-hk))] if h else [None,None]
        hk_upper=int(upper_df.groupby('tic_id')[g].any().sum()) if n else 0
        host_upper=(1. if hk_upper==h else float(beta.ppf(.975,hk_upper+1,h-hk_upper))) if h else None
        stats[g]=dict(k=k,n=n,rate=k/n if n else None,wilson95=wilson(k,n),host_bootstrap95=interval(ub),
          conditional_n=den,conditional_rate=k/den if den else None,conditional_wilson95=wilson(k,den),conditional_host_bootstrap95=interval(cb),
          independent_hosts=h,hosts_with_any_survival=hk,host_any_survival_exact95=host_ci,
          hosts_with_possible_survival=hk_upper,host_any_possible_survival_exact95_envelope=[host_ci[0],host_upper])
        stats[g].update(n_operational_unknown=unknown[g],scientific_rate_bounds=[k/n,(k+unknown[g])/n] if n else [None,None],
          scientific_Wilson95_envelope=[wilson(k,n)[0],wilson(k+unknown[g],n)[1]],
          scientific_host_bootstrap95_envelope=[interval(ub)[0],interval(upper_ub)[1]],
          scientific_conditional_rate_bounds=logical_conditional,
          scientific_conditional_Wilson95_envelope=[wilson(k,max_den)[0],wilson(k+unknown[g],max_den)[1]],
          scientific_conditional_host_bootstrap95_envelope=[interval(conditional_lower_boot)[0],interval(conditional_upper_boot)[1]],
          interval_interpretation='Ordinary intervals describe observed survival. Scientific envelopes include unresolved operational paths; completed-only cohorts are separately reported.')
    products={}
    for end in ['D_submit','D_useful']:
        gates=GATES[:6]+[end];rates=[stats[g]['conditional_rate'] for g in gates]
        prod=float(np.prod(rates)) if all(v is not None for v in rates) else None
        direct=counts[end]/n if n else None
        if prod is not None:assert math.isclose(prod,direct,abs_tol=1e-12)
        products[end]=dict(conditional_product=prod,direct_rate=direct,verified=prod is not None,
      note='Undefined downstream 0/0 is not replaced by zero' if prod is None else 'Product equals direct observed nested-cohort count; operationally unknown outcomes remain bounded separately')
    return dict(n_signals=n,n_hosts=int(h),gates=stats,conditional_product_checks=products)

def _frame(rows):
    flat=[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in rows]
    df=pd.DataFrame(flat)
    for g in GATES:
        if g not in df:df[g]=False
    if 'operational' not in df:df['operational']=None
    if 'stratum' not in df or df['stratum'].isna().any():df['stratum']=df.get('label','all')
    return df

def negatives(scored):
    rows=[];e2e=0;at_d_n=0;at_d_submit=0
    for s in scored:
        if s['label']!='negative':continue
        fam=s.get('negative_family_traces') or []
        end_to_end=any(f.get('D_submit') for f in fam)
        reached=[a for a in (s.get('negative_family_at_D') or []) if a.get('reached_D')]
        submit_at_d=any(a.get('submit_equivalent') for a in reached)
        e2e+=end_to_end;at_d_n+=bool(reached);at_d_submit+=submit_at_d
        rows.append(dict(truth_id=s['truth_id'],tic_id=s['tic_id'],subtype=s.get('subtype'),eligibility=s['eligibility'],
            family_keys=[f.get('candidate_key') for f in fam],family_gates=s.get('negative_family_gates'),
            submit_equivalent_end_to_end=end_to_end,reached_D=bool(reached),submit_equivalent_at_D=submit_at_d,
            at_D=reached,first_termination=s.get('first_termination'),operational=s.get('operational')))
    n=len(rows)
    lb2a=dict(clause='LB2a',number=e2e,N=n,wilson95=wilson(e2e,n),threshold='<= 1 of 13',decisive=True,holds=e2e<=1)
    lb2b=dict(clause='LB2b',number=at_d_submit,N=at_d_n,wilson95=wilson(at_d_submit,at_d_n),threshold='<= 1 of N2_D',
              decisive=at_d_n>=5,holds=at_d_submit<=1 if at_d_n>=5 else None)
    fam=_frame([dict(r,**(r['family_gates'] or {})) for r in rows]) if rows else pd.DataFrame()
    return dict(utc=utc(),rows=rows,LB2a=lb2a,LB2b=lb2b,family_estimate=estimate(fam) if len(fam) else None,
        rule='SUBMIT-equivalent: a candidate matching the binary period family (exact or 2, 3, 1/2, 1/3 within 1%) ends SUBMIT '
             '(tier 1 or 2) under p12.0 with the 4a redaction; end to end under the S and B gates, at D under the forced route')

def positives(scored):
    rows=[s for s in scored if s['label']=='positive']
    n_d=sum(1 for s in rows if s.get('C'))
    table=[dict(truth_id=s['truth_id'],tic_id=s['tic_id'],eligibility=s['eligibility'],first_termination=s.get('first_termination'),
        reached_D=bool(s.get('C')),verdict=s.get('verdict'),deciding_condition=s.get('deciding_condition'),
        candidate_tier=s.get('candidate_tier'),d_fired=s.get('d_fired'),operational=s.get('operational'),
        **{g:bool(s.get(g)) for g in GATES}) for s in rows]
    df=_frame(rows)
    return dict(utc=utc(),blind=dict(rows=table,n_signals=len(rows),n_D=n_d,estimate=estimate(df[df.eligibility=='eligible']) if len(df) else None,
        expectation='0 to 2 of 13 signals reach D on the blind leg (P9 search-stage failures)'))

def run():
    scored=read(H/'results/scored_signals.json')
    neg=negatives(scored);pos=positives(scored)
    OUT.mkdir(parents=True,exist_ok=True)
    write(OUT/'p9_negatives_table.json',json.loads(json.dumps(neg,default=float)))
    path=OUT/'p9_positives_table.json'
    existing=read(path) if path.exists() else {}
    existing.update(pos)
    write(path,json.loads(json.dumps(existing,default=float)))
    print('negatives',neg['LB2a']['number'],'/',neg['LB2a']['N'],'end to end;',neg['LB2b']['number'],'/',neg['LB2b']['N'],'at D;',
          'positives n_D',pos['blind']['n_D'],flush=True)

if __name__=='__main__':run()
