"""Paired whole-host PCG64 bootstrap, independent of scientific outcomes."""
import numpy as np


def host_weights(host_count, draws=10000, seed=2026091401):
    if host_count <= 0 or draws <= 0:
        raise ValueError('Positive host and draw counts required')
    rng = np.random.Generator(np.random.PCG64(seed))
    weights = np.empty((draws, host_count), dtype=np.uint16 if host_count <= 65535 else np.uint32)
    for i in range(draws):
        weights[i] = np.bincount(rng.integers(0, host_count, size=host_count), minlength=host_count)
    return weights


def fractions(numerator_by_host, denominator_by_host, weights):
    numerator, denominator = np.asarray(numerator_by_host, float), np.asarray(denominator_by_host, float)
    if numerator.shape != denominator.shape or numerator.ndim != 1:
        raise ValueError('Paired one-dimensional host counts required')
    if weights.shape[1] != len(numerator) or not np.all(np.isfinite(numerator)) or not np.all(np.isfinite(denominator)):
        raise ValueError('Invalid host alignment or nonfinite counts')
    if np.any(numerator < 0) or np.any(denominator < numerator):
        raise ValueError('A fraction must have 0 <= numerator <= denominator')
    n, d = float(numerator.sum()), float(denominator.sum())
    if d == 0:
        return dict(numerator=n, denominator=d, fraction=None, ci95=None, bootstrap_valid_draws=0)
    boot_n, boot_d = weights @ numerator, weights @ denominator
    valid = boot_d > 0
    values = boot_n[valid]/boot_d[valid]
    return dict(numerator=n, denominator=d, fraction=n/d,
                ci95=np.percentile(values, [2.5, 97.5]).tolist() if len(values) else None,
                bootstrap_valid_draws=int(valid.sum()))


def logistic_snr50(snr, recovered, weights=None):
    """Unpenalized binomial MLE for sigmoid(a+b*log(SNR)).

    Detect complete/quasi separation rather than returning a spurious finite
    crossing. Host multiplicities are supplied as observation weights.
    """
    snr, y = np.asarray(snr,float), np.asarray(recovered,float)
    w = np.ones_like(y) if weights is None else np.asarray(weights,float)
    if snr.shape != y.shape or w.shape != y.shape or y.ndim != 1:
        raise ValueError('Equal-length observation vectors required')
    if (not np.all(np.isfinite(snr)) or not np.all(snr>0) or
        not np.all(np.isin(y,[0,1])) or not np.all(np.isfinite(w)) or np.any(w<0)):
        raise ValueError('Invalid logistic observations')
    positive=w>0;snr,y,w=snr[positive],y[positive],w[positive]
    failed=dict(status='UNIDENTIFIED',a=None,b=None,snr50=None,log_snr50=None,
                observations=int(len(y)),weighted_observations=float(w.sum()))
    if len(y)<3 or len(np.unique(y))<2:
        return dict(failed,reason='INSUFFICIENT_OUTCOME_VARIATION')
    x=np.log(snr)
    if len(np.unique(x))<2:
        return dict(failed,reason='NO_SNR_VARIATION')
    if np.max(x[y==0])<=np.min(x[y==1]) or np.max(x[y==1])<=np.min(x[y==0]):
        return dict(failed,reason='COMPLETE_OR_QUASI_SEPARATION')
    center=np.average(x,weights=w);scale=np.sqrt(np.average((x-center)**2,weights=w))
    X=np.column_stack((np.ones_like(x),(x-center)/scale))
    successes=float(w@y);total=float(w.sum())
    beta=np.array([np.log((successes+.5)/(total-successes+.5)),0.])
    converged=False
    for iteration in range(100):
        z=X@beta;p=1/(1+np.exp(-np.clip(z,-700,700)))
        grad=X.T@(w*(p-y))
        if np.max(np.abs(grad))<1e-9*(total+1):
            converged=True;break
        hessian=X.T@((w*p*(1-p))[:,None]*X)
        try:step=np.linalg.solve(hessian,grad)
        except np.linalg.LinAlgError:return dict(failed,reason='SINGULAR_INFORMATION')
        old=float(np.sum(w*(np.logaddexp(0,z)-y*z)))
        accepted=False
        for half in range(30):
            proposal=beta-step*(.5**half);newz=X@proposal
            new=float(np.sum(w*(np.logaddexp(0,newz)-y*newz)))
            if np.isfinite(new) and new<=old+1e-12:
                beta=proposal;accepted=True;break
        if not accepted or np.max(np.abs(beta))>1e6:
            return dict(failed,reason='NUMERICAL_NONCONVERGENCE')
    if not converged:
        return dict(failed,reason='ITERATION_LIMIT')
    b=float(beta[1]/scale);a=float(beta[0]-b*center)
    if abs(b)<1e-12:
        return dict(failed,a=a,b=b,reason='NO_IDENTIFIED_SNR50_CROSSING')
    log_snr50=-a/b
    snr50=float(np.exp(log_snr50)) if -745<log_snr50<709 else None
    if snr50 is None or not np.isfinite(snr50) or snr50<=0:
        return dict(failed,a=a,b=b,log_snr50=log_snr50,reason='NONFINITE_SNR50_CROSSING')
    return dict(status='IDENTIFIED',a=a,b=b,snr50=snr50,log_snr50=log_snr50,
                observations=int(len(y)),weighted_observations=total,
                increasing_with_snr=b>0,iterations=iteration+1,
                negative_log_likelihood=float(np.sum(w*(np.logaddexp(0,X@beta)-y*(X@beta)))))
