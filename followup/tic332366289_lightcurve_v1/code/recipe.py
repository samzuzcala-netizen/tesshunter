"""Fixed local linear baseline and exposure-integrated box estimator."""
import numpy as np
from dataclasses import dataclass
GUARD=1/24; REF=5/24
def box_overlap(t,tc,duration,exposure):
    return np.maximum(0,np.minimum(t+exposure/2,tc+duration/2)-np.maximum(t-exposure/2,tc-duration/2))/exposure
def measure(t,y,good,tc,duration,cadence,exposure=None,dumps=None,details=False):
    exposure=cadence if exposure is None else exposure
    span=duration/2+GUARD+REF
    lo=np.searchsorted(t,tc-span-exposure);hi=np.searchsorted(t,tc+span+exposure)
    tt=t[lo:hi];yy=y[lo:hi];gg=good[lo:hi]&np.isfinite(yy)&np.isfinite(tt)
    x=tt-tc;q=box_overlap(tt,tc,duration,exposure)
    inn=(q>1e-8)&gg
    left=(x>=-span)&(x<=-duration/2-GUARD)&gg
    right=(x<=span)&(x>=duration/2+GUARD)&gg
    out=left|right
    coverage=float(np.sum(q[inn])*cadence/duration)
    rec=dict(tc=float(tc),n_in=int(sum(inn)),n_left=int(sum(left)),n_right=int(sum(right)),coverage=min(coverage,1),valid=False,reason='')
    if coverage<.75 or sum(inn)<2: rec['reason']='in-event coverage <75% or <2 samples';return rec
    if min(sum(left),sum(right))<max(3,.6*REF/cadence): rec['reason']='reference-side coverage <60% or <3 samples';return rec
    local=gg&(abs(x)<=span);tl=tt[local]
    if np.max(np.diff(tl),initial=0)>2.5*cadence:rec['reason']='gap >2.5 native cadences in local window';return rec
    if dumps is not None and np.any(abs(dumps-tc)<span):rec['reason']='momentum dump in local window';return rec
    X=np.column_stack((np.ones(sum(out)),x[out]));beta=np.linalg.lstsq(X,yy[out],rcond=None)[0]
    baseline=beta[0]+beta[1]*x
    if np.min(baseline[inn|out])<=0:rec['reason']='nonpositive fitted baseline';return rec
    residual=yy/baseline-1
    qi=q[inn];den=np.sum(qi**2)
    depth=-np.sum(qi*residual[inn])/den*1000
    noise=np.std(residual[out],ddof=2)
    # White error includes baseline-fit uncertainty, preserving time leverage.
    v=np.sum(qi[:,None]*np.column_stack((np.ones(sum(inn)),x[inn])),axis=0)/den
    white=noise*np.sqrt(1/den+v@np.linalg.inv(X.T@X)@v)*1000
    rec.update(valid=True,depth=float(depth),white=float(white),effective_n=float(den),baseline=float(beta[0]),slope=float(beta[1]),reason='')
    if details:rec.update(t=tt,flux=yy,baseline_curve=baseline,residual_ppt=residual*1000,in_mask=inn,out_mask=out,good_mask=gg,box=q)
    return rec
def uncertainty(rec,controls):
    d=np.array([r['depth'] for r in controls if r['valid']]); n=np.array([r['effective_n'] for r in controls if r['valid']])
    if len(d)<8:return np.nan
    scale=max(np.std(d,ddof=1),1.4826*np.median(abs(d-np.median(d))),np.sqrt(np.mean(d*d)))
    return max(rec['white'],scale*np.sqrt(max(1,np.median(n)/rec['effective_n'])))
def aggregate(rows):
    rr=[r for r in rows if r.get('valid') and np.isfinite(r.get('error',np.nan)) and r['error']>0]
    if not rr:return dict(n=0,depth=np.nan,error=np.nan,snr=np.nan)
    w=1/np.square([r['error'] for r in rr]);d=np.array([r['depth'] for r in rr]);mu=np.sum(w*d)/sum(w);err=1/np.sqrt(sum(w))
    from scipy.stats import chi2
    q=np.sum(w*(d-mu)**2)
    return dict(n=len(rr),depth=float(mu),error=float(err),snr=float(mu/err),chi2=float(q),p_const=float(chi2.sf(q,len(rr)-1)) if len(rr)>1 else None)
def aliases(t1,t2,pmin=1,pmax=100):
    delta=abs(t2-t1)
    n=np.arange(int(np.ceil(delta/pmax)),int(np.floor(delta/pmin))+1)
    return n,delta/n
