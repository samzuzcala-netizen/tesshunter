"""Registered evaluator diagnostics, run only after locked development scoring."""
from common import *
environment()
import numpy as np
from scipy.optimize import minimize
from score_common import paired,bootstrap_weights,binomial

SNR_BINS=[(0,7),(7,10),(10,15),(15,20),(20,30),(30,50),(50,float('inf'))]
PERIOD_BINS=[(0,.5),(.5,1),(1,2),(2,5),(5,10),(10,20),(20,30),(30,float('inf'))]
RADIUS_BINS=[(0,1),(1,1.5),(1.5,2),(2,2.5),(2.5,3),(3,4),(4,float('inf'))]

def logistic_point(rows,key):
    # Same two-parameter logistic in ln SNR as historical diagnostics. These
    # point crossings do not replace the paired, 10,000-host-bootstrap tests.
    good=[r for r in rows if np.isfinite(r['snr_expected']) and r['snr_expected']>0]
    if not good:return dict(status='UNIDENTIFIED',n=0)
    x=np.log([r['snr_expected'] for r in good]);y=np.array([r[key] for r in good],dtype=float)
    if np.ptp(y)==0:return dict(status='UNIDENTIFIED',n=len(y),reason='One outcome class; no finite logistic crossing')
    def nll(theta):
        z=theta[0]+theta[1]*x
        return float(np.sum(np.logaddexp(0,-z)*y+np.logaddexp(0,z)*(1-y)))
    fits=[minimize(nll,v,method='Nelder-Mead',options=dict(xatol=1e-6,fatol=1e-8,maxiter=4000))
          for v in ((-4,2),(-2,1),(-8,4))]
    fit=min(fits,key=lambda r:r.fun);a,b=fit.x
    if not fit.success or b<=0:return dict(status='UNIDENTIFIED',n=len(y),reason='No converged increasing finite crossing',a=float(a),b=float(b))
    crossings={}
    for name,z in [('snr50',0.),('snr90',float(np.log(9)))]:
        power=float((z-a)/b)
        value=float(np.exp(power)) if power<700 else None
        crossings[name]=value
        crossings[name+'_outside_observed_range']=value is None or value<np.exp(x.min()) or value>np.exp(x.max())
    return dict(status='COMPLETE',n=len(y),a=float(a),b=float(b),**crossings,
                inference='Point diagnostic only; no injection-level bootstrap. Required sensitivity inference uses paired host resampling.')

def main():
    result=read(ROOT/'results/development_evaluation.json');selection=read(ROOT/'manifests/development_selection.json')
    rows=result['rows'];hosts=selection['host_ids'];meta={r['tic_id']:r for r in read(ROOT/'manifests/development_order.json')['order']}
    weights=bootstrap_weights(hosts,[meta[h]['stratum'] for h in hosts])
    routes=['R0_search','R1_search','R0_pre','R1_pre','R0_AS','R1_AS']+[p['policy'] for p in result['policies']]
    table=[]
    for key in routes:
        entry=dict(route=key,overall=paired(rows,'R0_AS',key,[True]*len(rows),hosts,weights),
            high_snr=paired(rows,'R0_AS',key,[r['snr_expected']>=20 for r in rows],hosts,weights),
            alias_count=sum(r.get(key.split('_')[0]+'_alias',False) and not r.get(key.split('_')[0]+'_search',False) for r in rows),
            logistic=logistic_point(rows,key),binned={})
        for field,bins in [('snr_expected',SNR_BINS),('period',PERIOD_BINS),('rp_earth',RADIUS_BINS)]:
            entry['binned'][field]=[dict(low=lo,high=hi if np.isfinite(hi) else None,
                **paired(rows,'R0_AS',key,[lo<=r[field]<hi for r in rows],hosts,weights)) for lo,hi in bins]
        table.append(entry)
    write(ROOT/'results/sensitivity_tables.json',dict(utc=utc(),evaluation_sha256=sha(ROOT/'results/development_evaluation.json'),
        routes=table,bootstrap_draws=10000,bootstrap_seed=2026091303,
        n_unobservable=sum(r['snr_expected']==0 for r in rows),
        alias_definition='Separate blind-search true/alias-family matches. Alias-only count excludes exact-period matches; aliases never contribute a positive recovery.',
        bins='Half-open intervals; final open upper endpoint. Physical period/radius tables retain all included injections.',
        diagnostic_scope='Complete declared D_core development only. Original P10 SNR50 and stop remain unchanged. No validation or endpoint inference.'))
    print('sensitivity tables complete',len(routes),'routes',len(rows),'injections')

if __name__=='__main__':main()
