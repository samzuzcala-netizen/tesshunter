"""Post-lock P9 estimates; cluster-aware uncertainty and sparse coverage tables."""
from common import *
import math,collections
import numpy as np
import pandas as pd
from scipy.stats import beta
from scoring import GATES,wilson

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

def label_bin(v,edges,labels):
    try:
        if v is None or not np.isfinite(v):return 'missing'
        for i in range(len(labels)):
            if edges[i]<=v<edges[i+1]:return labels[i]
    except (TypeError,ValueError):pass
    return 'outside'

def build_table():
    scored=read(P9/'results/scored_signals.json');truth=pd.read_csv(P9/'truth/final_truth.csv').set_index('truth_id')
    features={r['truth_id']:r for r in read(P9/'results/diagnostic_features.json')};rows=[]
    for s in scored:
        t=truth.loc[s['truth_id']];f=features.get(s['truth_id'],{});tic=int(s['tic_id'])
        row={k:v for k,v in s.items() if not isinstance(v,(dict,list))}
        for k in ['period','radius_re','duration_hours','depth_ppm','ttv_flag']:
            v=t.get(k);row[k]=float(v) if pd.notna(v) else None
        for k in ['tmag','teff','rstar','snr_expected','snr_box_expected','sigma_cadence_ppt','n_sectors','strict_p8_stellar_and_targeting','strict_p8_actual_product_overlap','actual_spoc_fraction']:
            row[k]=f.get(k)
        row['diagnostic_status']=f.get('status','missing');row['split']=t['split']
        rot=f.get('rotation_proxy') or {};row['rotation_amplitude_ppt']=rot.get('semi_amplitude_ppt');row['rotation_period']=rot.get('peak_period_days')
        row['nearby_sources']=(f.get('crowding') or {}).get('n_sources')
        bs=(f.get('truth_event_summary') or {}).get('red_noise_beta_by_sector') or {}
        vals=[v.get('beta') if isinstance(v,dict) else v for v in bs.values()] if isinstance(bs,dict) else []
        vals=[float(v) for v in vals if v is not None and np.isfinite(v)]
        row['red_noise_beta_median']=float(np.median(vals)) if vals else None
        prods=read(P9/'manifests/products'/f'tic{tic}.json')['products'];row['n_sectors']=len(prods)
        counts=collections.Counter(p['author'] for p in prods)
        row['product_group']='SPOC-majority' if counts['SPOC']>=len(prods)/2 else 'FFI-majority'
        row['authors']=';'.join(sorted(counts));row['cadence_seconds']=';'.join(str(v) for v in sorted(set(p['cadence_s'] for p in prods)))
        row['radius_bin']=label_bin(row['radius_re'],[1,2,4,float('inf')],['1–2','2–4','>=4'])
        row['period_bin']=label_bin(row['period'],[.5,10,30.00001],['0.5–10','10–30'])
        row['snr_bin']=label_bin(row['snr_expected'],[0,12,20,50,float('inf')],['<12','12–20','20–50','>=50'])
        row['depth_bin']=label_bin(row['depth_ppm'],[0,1000,5000,float('inf')],['<1000 ppm','1000–5000 ppm','>=5000 ppm'])
        row['duration_bin']=label_bin(row['duration_hours'],[0,1,2,5],['<1 h','1–2 h','2–5 h'])
        row['opportunity_bin']=label_bin(row['opportunities'],[0,10,30,float('inf')],['3–9','10–29','>=30'])
        row['tmag_bin']=label_bin(row['tmag'],[0,10,12.5,14,20],['<10','10–12.5','12.5–14','>=14'])
        row['teff_bin']=label_bin(row['teff'],[0,3600,4500,7000],['<3600 K','3600–4500 K','>=4500 K'])
        row['rstar_bin']=label_bin(row['rstar'],[0,.45,.7,2],['<0.45','0.45–0.7','>=0.7'])
        row['rotation_bin']=label_bin(row['rotation_amplitude_ppt'],[0,.5,3,1e9,float('inf')],['<0.5 ppt','0.5–3 ppt','>=3 ppt','extreme proxy'])
        row['red_noise_bin']=label_bin(row['red_noise_beta_median'],[0,1.5,3,10],['<1.5','1.5–3','>=3'])
        row['crowding_bin']=label_bin(row['nearby_sources'],[0,5,15,float('inf')],['<5 Gaia sources','5–14','>=15'])
        row['sector_bin']=label_bin(len(prods),[0,5,10,float('inf')],['3–4','5–9','>=10'])
        row['ttv_bin']='flagged' if row['ttv_flag']==1 else 'not flagged' if row['ttv_flag']==0 else 'missing'
        rows.append(row)
    df=pd.DataFrame(rows);df.to_csv(P9/'results/analysis_table.csv',index=False);return df

def run():
    df=build_table();eligible=df[df.eligibility=='eligible'];pos=eligible[eligible.label=='positive'];cohorts={}
    def add(name,d):cohorts[name]=estimate(d)
    add('positive_all',pos);add('positive_operational_complete',pos[pos.operational.isna()])
    add('positive_cool_faint_oversample',pos[pos.stratum=='p8_proxy'])
    add('positive_strict_P8_targeting',pos[pos.strict_p8_stellar_and_targeting==True])
    add('positive_strict_P8_actual_products',pos[pos.strict_p8_actual_product_overlap==True])
    neg=eligible[eligible.label=='negative'];add('negative_exact',neg)
    add('negative_exact_operational_complete',neg[neg.operational.isna()])
    for typ,g in neg.groupby('subtype'):add('negative_exact_'+typ,g)
    family=neg.copy();sc={r['truth_id']:r for r in read(P9/'results/scored_signals.json')}
    for i,r in family.iterrows():
        for g in GATES:family.loc[i,g]=sc[r.truth_id].get('negative_family_gates',{}).get(g,False)
        ops=[v.get('operational') for v in sc[r.truth_id].get('negative_family_traces',[]) if v.get('operational')]
        if r.operational is not None and pd.notna(r.operational):ops.append(r.operational)
        family.loc[i,'operational']=min(ops,key=lambda v:['search','pre','A','S','B','C','D'].index(v)) if ops else None
    add('negative_exact_or_registered_alias',family)
    add('negative_family_operational_complete',family[family.operational.isna()])
    for typ,g in family.groupby('subtype'):add('negative_family_'+typ,g)
    add('uncertain_descriptive',eligible[eligible.label=='uncertain'])
    strata={}
    for col in ['stratum','split','radius_bin','period_bin','snr_bin','depth_bin','duration_bin','opportunity_bin','tmag_bin','teff_bin','rstar_bin','rotation_bin','red_noise_bin','crowding_bin','sector_bin','ttv_bin','product_group']:
        strata[col]={str(k):estimate(g) for k,g in pos.groupby(col,dropna=False)}
    out=dict(utc=utc(),uncertainty='Wilson marginal; 5000 whole-host resamples within frozen sampling strata; exact host-any-survival bounds are a different estimand',
      cohorts=cohorts,stratification=strata,weighting=dict(status='unsupported' if cohorts['positive_strict_P8_actual_products']['n_hosts']<10 else 'requires cell support audit',
        minimum_hosts_per_cell=5,minimum_ESS=10,maximum_weight=5,ESS=None),
      selected_counts=df.groupby(['label','eligibility']).size().to_dict())
    out['selected_counts']={str(k):int(v) for k,v in out['selected_counts'].items()}
    write(P9/'results/metrics.json',out)
    census=pos.groupby('first_termination').agg(n_signals=('truth_id','size'),n_hosts=('tic_id','nunique')).reset_index()
    census.to_csv(P9/'results/loss_census.csv',index=False)
    op=eligible.groupby(['label','operational'],dropna=False).size().reset_index(name='n_signals');op['cohort']='exact primary signal'
    fop=family.groupby(['label','operational'],dropna=False).size().reset_index(name='n_signals');fop['cohort']='negative exact-or-alias family'
    pd.concat([op,fop],ignore_index=True).to_csv(P9/'results/operational_completion.csv',index=False)
    figure(cohorts,census)
    print('positive',cohorts['positive_all']['n_signals'],{g:cohorts['positive_all']['gates'][g]['k'] for g in GATES},flush=True)

def figure(cohorts,census):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    labels=['Search','Pre','A','Secondary','B','C','Submit eq.','Useful']
    for name,color,label in [('positive_all','#27648B','Confirmed planets'),('negative_exact_or_registered_alias','#AA4438','Labelled negatives, incl. registered aliases')]:
        c=cohorts[name];y=[c['gates'][g]['rate'] or 0 for g in GATES]
        ax[0].plot(range(6),y[:6],'o-',color=color,label=f'{label} (n={c["n_signals"]})')
        for branch in [6,7]:ax[0].plot([5,branch],[y[5],y[branch]],'o--',color=color,alpha=.8)
        for i,g in enumerate(GATES):
            lo,hi=c['gates'][g]['scientific_Wilson95_envelope'];ax[0].plot([i,i],[lo or 0,hi or 0],color=color,alpha=.55)
    ax[0].set(ylim=(-.03,1.03),ylabel='Fraction of eligible labelled signals',title='Unconditional survival; both D branches start at C')
    ax[0].set_xticks(range(len(labels)),labels)
    ax[0].tick_params(axis='x',rotation=40);ax[0].legend(fontsize=8);ax[0].grid(axis='y',alpha=.2)
    c=census.sort_values('n_signals')
    display={'search':'Search match','C':'Native C gate','C_signal_switch':'C identity (duration)','D':'Final review','retained':'Useful retained'}
    ax[1].barh([display.get(t,t) for t in c.first_termination],c.n_signals,color='#466E86')
    for i,n in enumerate(c.n_signals):ax[1].text(n+.1,i,str(n),va='center')
    ax[1].set(xlabel='Number of confirmed-planet signals',title='First termination; diagnostic causes are separate')
    fig.suptitle('P9 observed survival — Wilson 95% bars include envelopes for operationally unknown outcomes',fontsize=11)
    out=P9/'figures';out.mkdir(exist_ok=True);fig.savefig(out/'funnel_and_losses.png',dpi=160);plt.close(fig)

if __name__=='__main__':run()
