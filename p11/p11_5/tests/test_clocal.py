import copy
from dataclasses import replace
import numpy as np
import pytest
from tesshunter.p11_5_clocal import (shape,PhysicalFit,physical_limits,GRID,measure,
                                    decide,recurrence_evidence,D_GRID,E_GRID)

def fixture():
    t=np.r_[np.arange(0,8,.01),np.arange(30,38,.01)]
    s=np.r_[np.ones(800,int),np.full(800,2)]
    sh=shape(t,2.,.4,.15,.25,.01)
    f=1+.003*(t-np.where(s==1,4,34))/8-.008*sh
    return t,f,np.full(len(t),.001),s,sh

def test_physical_chi2_units_baselines_and_parameter_count():
    t,f,e,s,sh=fixture();fit=PhysicalFit(t,f,e,s).fit([sh],4,archive=True)
    assert fit['k']==2*2+4+1
    assert fit['chi2']==pytest.approx(np.sum(((f-fit['model'])/e)**2),abs=1e-9)
    assert fit['chi2_flat']==pytest.approx(np.sum(((f-fit['flat_model'])/e)**2))
    assert fit['chi2']<1e-15 and fit['depths'][0]==pytest.approx(.008)
    scaled=PhysicalFit(t,f*1000,e*1000,s).fit([sh],4)
    assert scaled['D']==pytest.approx(fit['D'])
    assert scaled['depths'][0]==pytest.approx(8)

def test_two_eclipse_counts_all_free_parameters_and_identical_baseline():
    t,f,e,s,sh=fixture();sec=shape(t,2.,1.3,.08,.1,.01)
    fit=PhysicalFit(t,f-.004*sec,e,s).fit([sh,sec],7,archive=True)
    assert fit['k']==4+7+2 and fit['chi2']<1e-12
    assert fit['depths']==pytest.approx([.008,.004])

def test_noise_beta_and_physical_residual_scaling():
    t,f,e,s,sh=fixture()
    a=PhysicalFit(t,f,e,s).fit([sh],4)
    b=PhysicalFit(t,f,e,s,{1:2,2:2}).fit([sh],4)
    assert b['D']==pytest.approx(a['D']/4)

def test_exposure_integration_resolves_sharp_edges():
    t=np.array([-.051,-.05,-.049,0,.05])
    sh=shape(t,3,0,.1,.1,.02,101)
    assert np.all((sh>=0)&(sh<=1)) and 0<sh[1]<1 and sh[3]==1

def record():
    p=dict(period_days=3.,epoch_btjd=1.,duration_days=.1,D=80.,BIC=100.)
    return dict(status='MEASURED',primary=p,primary_matches=True,baseline_days=100.,
        aliases=[dict(status='MEASURED',fit=p)],two_eclipse=[],residuals=[],broader_unresolved=[])

def test_alias_tie_unknown_and_better_alias_rejects():
    r=record();alias=dict(r['primary'],period_days=6.,BIC=96.)
    r['aliases'].append(dict(status='MEASURED',fit=alias))
    assert decide(r,49,6)['status']=='UNRESOLVED'
    alias['BIC']=93
    assert decide(r,49,6)['status']=='REJECT'
    alias['BIC']=120
    assert decide(r,49,6)['status']=='PASS'

def test_missing_alternatives_and_operations_never_pass():
    r=record();r['aliases'].append(dict(status='GRID_LIMITATION'))
    assert decide(r,49,6)['status']=='UNRESOLVED'
    for status in ('INPUT_ERROR','TIMEOUT'):
        assert decide(dict(status=status,reason='fixture'),49,6)['status']==status
    with pytest.raises(ValueError):decide(r,50,6)

def test_recurrent_binary_required_and_residual_threshold_equal():
    r=record();b=dict(status='MEASURED',fit={'E':12},recurrence={'sufficient':False})
    r['two_eclipse']=[b]
    assert decide(r,49,6)['status']=='PASS'
    b['recurrence']['sufficient']=True
    assert decide(r,49,10)['status']=='REJECT'
    r['two_eclipse']=[];r['residuals']=[dict(status='MEASURED',fit={'D':48})]
    assert decide(r,49,6)['status']=='REJECT'

def test_aliases_outside_blind_domain_and_grid_limit_not_impossibility():
    star=dict(radius_rsun=.3,mass_msun=.3)
    assert physical_limits(.3,star,200/86400)['status']=='ADMISSIBLE'
    assert physical_limits(120,star,200/86400)['status']=='ADMISSIBLE'
    assert physical_limits(.3,star,1)['status']=='GRID_LIMITATION'

def test_truth_fields_refused_before_scoring():
    t,f,e,s,_=fixture()
    candidate=dict(period_days=2,epoch_btjd=.4,duration_days=.15,injected_period=2)
    r=measure(t,f,e,s,candidate,dict(radius_rsun=.3,mass_msun=.3))
    assert r['status']=='INPUT_ERROR' and 'Non-runtime' in r['reason']

def test_actual_recurrence_needs_two_sectors():
    t,f,e,s,sh=fixture();p=dict(period_days=2.,epoch_btjd=.4)
    rec=recurrence_evidence(PhysicalFit(t,f,e,s),p,0.,.15)
    assert rec['sufficient']
    rec=recurrence_evidence(PhysicalFit(t[:800],f[:800],e[:800],s[:800]),p,0.,.15)
    assert not rec['sufficient']
def test_complete_grid_on_two_sector_physical_planet():
    import numpy as np
    from tesshunter import p11_5_clocal as c
    t=np.r_[np.arange(0,8,.003),np.arange(30,38,.003)]
    sector=np.where(t<10,1,2);e=np.full(len(t),.0001)
    rng=np.random.Generator(np.random.PCG64(2026091304))
    f=1-.008*c.shape(t,2.,.5,.04,.25,.003)+rng.normal(0,e)
    record=c.measure(t,f,e,sector,dict(period_days=2.,epoch_btjd=.5,duration_days=.04,depth_ppt=8.),
                     dict(radius_rsun=.3,mass_msun=.3))
    assert record['status']=='MEASURED' and c.decide(record,100,10)['status']=='PASS'
    assert len(record['aliases'])==7 and len(record['two_eclipse'])==2
    assert record['broad_grid']['min']==.5 and record['broad_grid']['max']==110.
    primary=record['primary'];model=primary['model']
    beta=np.array([record['noise_beta'][int(s)] for s in sector])
    assert np.isclose(primary['chi2'],np.sum(((f-model)/(e*beta))**2))
