"""Finite candidate-conditioned C experiment with physical residual units.

Exposure-integrated symmetric trapezoids are an explicit approximation, not a
physical planet-radius inference. Stellar density limits admissible periods and
maximum duration; all model comparisons share the same native flux/error units,
sector baselines and fixed measured noise inflation. No catalogue/truth fields.
"""
from dataclasses import dataclass, asdict
from itertools import product
import math
import time
import numpy as np
from astropy.timeseries import BoxLeastSquares
from scipy.optimize import minimize, nnls
from . import audit_rules, audit_prep, event_vet, secondary, stage_c, survey
from .p11_5_search import array_key, ephemeris_equal

VERSION='p11.5-clocal-v1'
RATIOS=(1/3,1/2,2/3,1.,1.5,2.,3.)
D_GRID=(25,36,49,64,81,100)
E_GRID=(6,10)

@dataclass(frozen=True)
class Grid:
    local_fraction:float=.015
    local_periods:int=257
    bls_durations:int=8
    ingress_fractions:tuple=(.1,.25,.5)
    geometric_phase_seeds:int=3
    bls_seed_peaks:int=2
    refine_evaluations:int=64
    refine_iterations:int=12
    secondary_phase_seeds:int=32
    exposure_subsamples:int=7
    broad_periods:int=40000
    broad_pmin:float=.5
    broad_pmax:float=110.
    max_competitors:int=4
    max_residual_masks:int=3
    deadline_seconds:float=600.

GRID=Grid()

class Deadline(Exception):pass

def check(deadline):
    if time.perf_counter()>=deadline:raise Deadline('C_local operational deadline')

def shape(t,period,epoch,duration,ingress,exposure,subsamples=7):
    """Numerically exposure-integrated unit-depth trapezoid in [0,1]."""
    if period<=0 or duration<=0 or duration>=period or not 0<ingress<=.5:
        raise ValueError('Invalid transit template geometry')
    exp=np.broadcast_to(exposure,np.shape(t))
    y=np.zeros_like(t,dtype=float)
    for offset in (np.arange(subsamples)+.5)/subsamples-.5:
        phase=abs((t+exp*offset-epoch+.5*period)%period-.5*period)
        y+=np.clip((.5*duration-phase)/(duration*ingress),0,1)
    return y/subsamples

class PhysicalFit:
    """Weighted Frisch-Waugh-Lovell fit; every chi2 is sum((flux-model)/err)^2."""
    def __init__(self,t,f,e,sector,beta=None):
        self.t=np.asarray(t,float);self.f=np.asarray(f,float);self.e=np.asarray(e,float)
        self.sector=np.asarray(sector)
        if not (self.t.shape==self.f.shape==self.e.shape==self.sector.shape):raise ValueError('Array lengths')
        if len(t)<50 or not np.isfinite([self.t,self.f,self.e]).all() or np.any(self.e<=0):raise ValueError('Native data/errors invalid')
        self.groups=[];self.flat=np.zeros_like(self.f);self.w=1/self.e**2
        for s in np.unique(self.sector):
            ix=np.flatnonzero(self.sector==s)
            if len(ix)<3:raise ValueError('Insufficient sector baseline points')
            if beta:self.w[ix]/=float(beta[int(s)])**2
            x=self.t[ix]-np.mean(self.t[ix]);x/=max(np.ptp(x),1e-9)
            b=np.column_stack([np.ones(len(ix)),x]);w=self.w[ix]
            inv=np.linalg.inv(b.T@(w[:,None]*b))
            coefficient=inv@(b.T@(w*self.f[ix]))
            self.flat[ix]=b@coefficient
            self.groups.append((int(s),ix,b,inv,coefficient))
        self.y=self.f-self.flat
        self.chi2_flat=float(np.dot(self.w,self.y**2))
        self.k_baseline=2*len(self.groups)

    def fit(self,templates,k_shape,archive=False):
        x=-np.column_stack(templates);xr=x.copy()
        projected=[]
        for s,ix,b,inv,coef in self.groups:
            c=inv@(b.T@(self.w[ix,None]*x[ix]));xr[ix]-=b@c;projected.append(c)
        gram=xr.T@(self.w[:,None]*xr);rhs=xr.T@(self.w*self.y)
        if len(templates)==1:
            depth=np.array([max(0.,float(rhs[0]/gram[0,0])) if gram[0,0]>0 else 0.])
        else:
            # Two-variable NNLS in the original weighted residual problem.
            try:
                chol=np.linalg.cholesky(gram+np.eye(len(templates))*1e-18)
                depth=nnls(chol.T,np.linalg.solve(chol,rhs))[0]
            except np.linalg.LinAlgError:depth=np.zeros(len(templates))
        residual=self.y-xr@depth
        chi2=float(np.dot(self.w,residual**2))
        k=self.k_baseline+k_shape+len(templates)
        record=dict(chi2_flat=self.chi2_flat,chi2=chi2,D=self.chi2_flat-chi2,
                    BIC=chi2+k*math.log(len(self.t)),k=k,n=len(self.t),depths=depth.tolist())
        if archive:
            baseline=self.flat.copy();coefficients=[]
            for (s,ix,b,inv,coef),c in zip(self.groups,projected):
                fit_coef=coef-c@depth;baseline[ix]=b@fit_coef
                coefficients.append(dict(sector=s,constant=float(fit_coef[0]),linear=float(fit_coef[1])))
            record.update(model=baseline+x@depth,flat_model=self.flat.copy(),baseline_model=baseline,baseline_coefficients=coefficients)
        return record

def physical_limits(period,star,cadence):
    r=float(star['radius_rsun']);m=float(star['mass_msun'])
    if min(r,m,period)<=0 or not np.isfinite([r,m,period]).all():raise ValueError('Stellar inputs invalid')
    a=survey.a_over_rs(period,m,r)
    if a<=1:return dict(status='PHYSICALLY_IMPOSSIBLE',reason='Circular orbit centre lies inside star',a_rs=a)
    maximum=min(.3*period,period/np.pi*np.arcsin(min(1.,1.5/a)))
    if maximum<cadence:return dict(status='GRID_LIMITATION',reason='Maximum central duration below one exposure',a_rs=a)
    return dict(status='ADMISSIBLE',a_rs=a,duration_min=cadence,duration_max=float(maximum))

def params_model(fitter,params,exposure,grid):
    p,epoch,dur,ingress=params
    return shape(fitter.t,p,epoch,dur,ingress,exposure,grid.exposure_subsamples)

def local_fit(fitter,centre,epoch,duration,star,exposure,deadline,grid=GRID,primary_only=False):
    check(deadline);cad=float(np.median(exposure));bounds=physical_limits(centre,star,cad)
    if bounds['status']!='ADMISSIBLE':return dict(centre=centre,**bounds)
    lo,hi=centre*(1-grid.local_fraction),centre*(1+grid.local_fraction)
    periods=1/np.linspace(1/hi,1/lo,grid.local_periods)[::-1]
    durations=np.geomspace(cad,bounds['duration_max'],grid.bls_durations)
    bls=BoxLeastSquares(fitter.t,1+fitter.y,np.sqrt(1/fitter.w))
    power=bls.power(periods,durations,objective='likelihood',method='fast',oversample=5)
    if not (np.isclose(np.min(power.period),lo) and np.isclose(np.max(power.period),hi)):
        raise ValueError('Returned local grid bounds differ from registered band')
    peaks=np.argsort(power.power)[::-1]
    seeds=[(centre,epoch,max(cad,min(duration,bounds['duration_max'])),.25)]
    if not primary_only:
        for phase in np.linspace(0,1,grid.geometric_phase_seeds,endpoint=False)[1:]:
            seeds.append((centre,epoch+phase*centre,max(cad,min(duration,bounds['duration_max'])),.25))
    for i in peaks[:grid.bls_seed_peaks]:
        ep=float(power.transit_time[i])
        distance=abs((ep-epoch+.5*centre)%centre-.5*centre)
        if not primary_only or distance<=max(duration,float(power.duration[i])):
            seeds.append((float(power.period[i]),ep,float(power.duration[i]),.25))
    # Evaluate all ingress choices at each seed, then refine exactly the best two.
    ranked=[]
    for seed in seeds:
        for ingress in grid.ingress_fractions:
            par=(*seed[:3],ingress)
            result=fitter.fit([params_model(fitter,par,exposure,grid)],4)
            ranked.append((result['chi2'],par))
    ranked.sort(key=lambda x:x[0]);solutions=[]
    for _,seed in ranked[:2]:
        check(deadline)
        span=max(duration,float(seed[2]));period_span=(hi-lo)/2
        # Coordinates scale with period band and transit width, avoiding an
        # ill-conditioned BTJD/period optimization. Bounds are always explicit.
        def decode(x):return (centre+x[0]*period_span,seed[1]+x[1]*span,
                               cad+x[2]*(bounds['duration_max']-cad),.1+.4*x[3])
        x0=np.array([(seed[0]-centre)/period_span,0,(seed[2]-cad)/max(bounds['duration_max']-cad,1e-12),(seed[3]-.1)/.4])
        def objective(x):
            check(deadline)
            return fitter.fit([params_model(fitter,decode(x),exposure,grid)],4)['chi2']
        opt=minimize(objective,np.clip(x0,[-1,-1,0,0],[1,1,1,1]),method='Powell',bounds=[(-1,1),(-1,1),(0,1),(0,1)],
            options=dict(maxfev=grid.refine_evaluations,maxiter=grid.refine_iterations,xtol=1e-4,ftol=1e-5))
        # Finite optimization exhaustion is a registered grid endpoint, not an
        # assertion of a global optimum. Preserve best seed if refinement worsens.
        candidates=[seed,decode(opt.x)]
        par=min(candidates,key=lambda v:fitter.fit([params_model(fitter,v,exposure,grid)],4)['chi2'])
        fit=fitter.fit([params_model(fitter,par,exposure,grid)],4,archive=True)
        fit.update(period_days=par[0],epoch_btjd=par[1],duration_days=par[2],ingress_fraction=par[3],
            optimized_shape_parameters=['period','epoch','duration','ingress'],optimized_depth_parameters=1,
            optimizer_evaluations=int(opt.nfev),optimizer_converged=bool(opt.success))
        solutions.append(fit)
    best=min(solutions,key=lambda v:v['chi2'])
    return dict(status='MEASURED',centre=centre,grid_min=float(np.min(periods)),grid_max=float(np.max(periods)),
                n_periods=len(periods),durations=durations.tolist(),physical_limits=bounds,fit=best)

def recurrence_evidence(fitter,fit,secondary_phase,duration):
    t,f,sec=fitter.t,fitter.f,fitter.sector;p=fit['period_days'];epoch=fit['epoch_btjd']
    events=secondary.event_depths(t,f,secondary_phase,p,epoch,duration,sector=sec)
    recurrence=secondary.recurrence(events,t,f,sec,secondary_phase,p,epoch,duration)
    sectors=[]
    for s in np.unique(sec):
        mask=sec==s
        result=secondary.box_depth(t[mask],f[mask],secondary_phase,p,epoch,duration)
        sectors.append(dict(sector=int(s),sigma=None if result is None else float(result['sigma'])))
    measured=sum(r['sigma'] is not None and r['sigma']>=audit_rules.SEC_RECUR_GROUP_SIGMA for r in sectors)
    return dict(existing=recurrence,per_sector=sectors,
                sufficient=bool(recurrence['recurs'] and measured>=2),sectors_ge_2sigma=measured)

def two_eclipse(fitter,planet,primary,seed_phase,star,exposure,deadline,grid=GRID):
    check(deadline)
    p=planet['period_days'];epoch=planet['epoch_btjd'];dur=planet['duration_days']
    primary_shape=params_model(fitter,(p,epoch,dur,planet['ingress_fraction']),exposure,grid)
    phases=list(np.linspace(0,1,grid.secondary_phase_seeds,endpoint=False))
    if seed_phase is not None:phases.append(float(seed_phase)%1)
    ranked=[]
    for phase in phases:
        if min(phase,1-phase)*p<1.5*dur:continue
        secshape=shape(fitter.t,p,epoch+phase*p,dur,.25,exposure,grid.exposure_subsamples)
        result=fitter.fit([primary_shape,secshape],7)
        ranked.append((result['chi2'],phase))
    if not ranked:return dict(status='UNRESOLVED',reason='No admissible secondary phase')
    ranked.sort();phase=ranked[0][1]
    # All seven optimized nonlinear coordinates are explicit: the primary's
    # four plus secondary phase, duration and ingress. Two depths are linear.
    cad=float(np.median(exposure));maxdur=physical_limits(p,star,cad)['duration_max'];band=grid.local_fraction*p
    def decode(x):
        return (p+x[0]*band,epoch+x[1]*dur,max(cad,dur*x[2]),.1+.4*x[3],
                (phase+x[4]/grid.secondary_phase_seeds)%1,max(cad,dur*x[5]),.1+.4*x[6])
    def fit(x,archive=False):
        pp,ep,d1,g1,ph,d2,g2=decode(x)
        if min(ph,1-ph)*pp<.5*(d1+d2):return None
        sh=[shape(fitter.t,pp,ep,d1,g1,exposure,grid.exposure_subsamples),
            shape(fitter.t,pp,ep+ph*pp,d2,g2,exposure,grid.exposure_subsamples)]
        out=fitter.fit(sh,7,archive=archive)
        out.update(period_days=pp,epoch_btjd=ep,duration_days=d1,ingress_fraction=g1,
                   secondary_phase=ph,secondary_duration_days=d2,secondary_ingress_fraction=g2)
        return out
    def objective(x):
        check(deadline);r=fit(x)
        return r['chi2'] if r is not None else fitter.chi2_flat+1e9
    x0=[0,0,1,.375,0,1,.375]
    duration_bounds=(cad/dur,maxdur/dur)
    opt=minimize(objective,x0,method='Powell',bounds=[(-1,1),(-1,1),duration_bounds,(0,1),(-1,1),duration_bounds,(0,1)],
                 options=dict(maxfev=grid.refine_evaluations,maxiter=grid.refine_iterations,xtol=1e-4,ftol=1e-5))
    x=min([x0,opt.x],key=objective);result=fit(x,archive=True)
    if result is None:return dict(status='UNRESOLVED',reason='Overlapping eclipses')
    rec=recurrence_evidence(fitter,result,result['secondary_phase'],result['secondary_duration_days'])
    result.update(E=primary['BIC']-result['BIC'],optimized_shape_parameters=7,optimized_depth_parameters=2,
                  optimizer_evaluations=int(opt.nfev),optimizer_converged=bool(opt.success))
    return dict(status='MEASURED',fit=result,recurrence=rec,
                equal_depth=bool(abs(result['depths'][0]-result['depths'][1])<=.1*max(result['depths'])))

def decide(measurement,D,E):
    if D not in D_GRID or E not in E_GRID:raise ValueError('Threshold outside registered grid')
    status=measurement.get('status')
    if status in ('INPUT_ERROR','TIMEOUT'):return dict(status=status,reason=measurement.get('reason'))
    if status!='MEASURED':return dict(status='UNRESOLVED',reason='Missing measurements')
    primary=measurement.get('primary')
    if primary is None:return dict(status='UNRESOLVED',reason='Primary unmeasured')
    if not measurement.get('primary_matches',False):return dict(status='REJECT',reason='Primary period/epoch mismatch')
    if primary['D']<D:return dict(status='REJECT',reason='Primary D below threshold')
    for binary in measurement['two_eclipse']:
        if binary['status']=='MEASURED' and binary['fit']['E']>=E and binary['recurrence']['sufficient']:
            return dict(status='REJECT',reason='Two-eclipse BIC and recurrent sector evidence')
    unknown=[]
    for alias in measurement['aliases']:
        if alias['status']=='PHYSICALLY_IMPOSSIBLE':continue
        if alias['status']!='MEASURED':unknown.append('Missing local alias');continue
        fit=alias['fit']
        if ephemeris_equal(primary,fit,measurement['baseline_days']):continue
        if fit['D']>=D and fit['BIC']<primary['BIC']-6:return dict(status='REJECT',reason='Distinct transit alias BIC more than 6 better')
        if fit['D']>=D and abs(fit['BIC']-primary['BIC'])<=6:unknown.append('Distinct transit alias within 6 BIC')
    for binary in measurement['two_eclipse']:
        if binary['status']!='MEASURED':unknown.append('Missing two-eclipse model')
    if measurement.get('broader_unresolved'):unknown.extend(measurement['broader_unresolved'])
    for residual in measurement['residuals']:
        if residual['status']!='MEASURED':unknown.append('Missing residual support')
        elif residual['fit']['D']<D:return dict(status='REJECT',reason='Residual D below threshold')
    if unknown:return dict(status='UNRESOLVED',reason='; '.join(sorted(set(unknown))))
    return dict(status='PASS',reason='Primary, aliases, two-eclipse and residual checks complete')

def measure(t,f,e,sector,candidate,star,*,exposure=None,secondary_phase=None,grid=GRID):
    start=time.perf_counter();cpu=time.process_time();deadline=start+grid.deadline_seconds
    result=dict(version=VERSION,grid=asdict(grid),status='INPUT_ERROR')
    try:
        if set(candidate)-{'period_days','epoch_btjd','duration_days','depth_ppt','candidate_id'}:
            raise ValueError('Non-runtime candidate fields forbidden')
        t,f,e,sector=map(np.asarray,(t,f,e,sector))
        if not np.all(np.diff(t)>=0):raise ValueError('Native times must be sorted')
        cadence={int(s):float(np.median(np.diff(t[sector==s])))*86400 for s in np.unique(sector)}
        if exposure is None:exposure=np.array([cadence[int(s)]/86400 for s in sector])
        else:exposure=np.broadcast_to(exposure,t.shape).astype(float)
        p=float(candidate['period_days']);epoch=float(candidate['epoch_btjd']);dur=max(float(candidate['duration_days']),float(np.median(exposure)))
        mask=audit_prep.transit_mask(t,p,epoch,dur)
        beta=event_vet.sector_beta(t,f,sector,mask,dur,cadence)
        fit=PhysicalFit(t,f,e,sector,beta)
        result.update(array_key=array_key(t,f,e,sector,exposure,config=asdict(grid)),candidate=candidate,star=star,
                      noise_beta=beta,n=len(t),baseline_days=float(np.ptp(t)),chi2_flat=fit.chi2_flat,
                      k_baseline=fit.k_baseline,flux_units='normalized relative flux; flux_err in identical units')
        main=local_fit(fit,p,epoch,dur,star,exposure,deadline,grid,primary_only=True)
        if main['status']!='MEASURED':
            result.update(status='UNRESOLVED',reason='Primary physically inadmissible or unmeasured',primary_diagnostic=main)
            return result
        primary=main['fit'];aliases=[]
        for ratio in RATIOS:
            if ratio==1:aliases.append(main);continue
            aliases.append(local_fit(fit,p*ratio,epoch,dur,star,exposure,deadline,grid))
        binaries=[]
        for ratio in (1,2):
            local=next(a for a in aliases if np.isclose(a['centre'],p*ratio))
            if local['status']=='MEASURED':binaries.append(two_eclipse(fit,local['fit'],primary,secondary_phase,star,exposure,deadline,grid))
            else:binaries.append(dict(status='UNRESOLVED',reason='Missing binary-period model'))
        check(deadline)
        period_grid=1/np.linspace(1/grid.broad_pmax,1/grid.broad_pmin,grid.broad_periods)[::-1]
        bls=BoxLeastSquares(t,1+fit.y,np.sqrt(1/fit.w))
        broad=bls.power(period_grid,np.geomspace(max(float(np.median(exposure)),.02),.20,8),objective='likelihood',method='fast',oversample=5)
        ix=np.argsort(broad.power)[::-1];competitors=[]
        for i in ix:
            value=dict(period_days=float(broad.period[i]),epoch_btjd=float(broad.transit_time[i]),duration_days=float(broad.duration[i]),power=float(broad.power[i]))
            if any(a['status']=='MEASURED' and ephemeris_equal(value,a['fit'],float(np.ptp(t))) for a in aliases):continue
            if any(abs(value['period_days']/a['period_days']-1)<.02 for a in competitors):continue
            competitors.append(value)
            if len(competitors)==grid.max_competitors:break
        residuals=[];unresolved=[];stronger=[]
        for competitor in competitors:
            check(deadline)
            c=local_fit(fit,competitor['period_days'],competitor['epoch_btjd'],competitor['duration_days'],star,exposure,deadline,grid)
            competitor['measurement']=c
            if c['status']=='PHYSICALLY_IMPOSSIBLE':continue
            if c['status']!='MEASURED':unresolved.append('Unmeasured broader competitor');continue
            if any(a['status']=='MEASURED' and ephemeris_equal(c['fit'],a['fit'],float(np.ptp(t))) for a in aliases):
                competitor['already_tested_alias']=True
                continue
            if c['fit']['D']<=primary['D']:continue
            cc=c['fit'];n=stage_c.covered_transits(t,cc['period_days'],cc['epoch_btjd'],cc['duration_days'])
            competitor['covered_events']=n
            if n<3:unresolved.append('Stronger competitor with fewer than three covered events');continue
            stronger.append(cc)
        if len(stronger)>grid.max_residual_masks:unresolved.append('More than three stronger competitors')
        for cc in stronger[:grid.max_residual_masks]:
            keep=~audit_prep.transit_mask(t,cc['period_days'],cc['epoch_btjd'],cc['duration_days'],n_durations=audit_rules.C_RESIDUAL_MASK_DURATIONS)
            try:
                residual_fitter=PhysicalFit(t[keep],f[keep],e[keep],sector[keep],beta)
                residual=local_fit(residual_fitter,p,epoch,dur,star,exposure[keep],deadline,grid,primary_only=True)
            except ValueError as exc:residual=dict(status='UNRESOLVED',reason=str(exc))
            residual.update(masked_competitor={k:cc[k] for k in ('period_days','epoch_btjd','duration_days')},n_masked=int((~keep).sum()))
            residuals.append(residual)
        epoch_distance=abs((primary['epoch_btjd']-epoch+.5*p)%p-.5*p)
        result.update(status='MEASURED',primary=primary,primary_grid=main,
            primary_matches=bool(abs(primary['period_days']/p-1)<.01 and epoch_distance<=max(dur,primary['duration_days'],.02)),
            aliases=aliases,two_eclipse=binaries,competitors=competitors,residuals=residuals,broader_unresolved=unresolved,
            broad_grid=dict(min=float(np.min(broad.period)),max=float(np.max(broad.period)),n=len(period_grid),hash=array_key(period_grid)),
            alias_equal_depth_double_ambiguity=any(b.get('equal_depth',False) for b in binaries))
    except Deadline as exc:result.update(status='TIMEOUT',reason=str(exc))
    except Exception as exc:result.update(status='INPUT_ERROR',reason=f'{type(exc).__name__}: {exc}')
    finally:result.update(wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu)
    return result
