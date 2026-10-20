"""Regression checks for the two registered correctness repairs."""
import numpy as np
import pytest
from tesshunter import p11_5_clocal_v2 as C

def record():
    primary=dict(period_days=3.,epoch_btjd=1.,duration_days=.1,D=80.,BIC=100.)
    return dict(status='MEASURED',primary=primary,primary_matches=True,baseline_days=100.,
        candidate=dict(primary),aliases=[dict(status='MEASURED',fit=primary)],two_eclipse=[],
        residuals=[dict(status='MEASURED',fit=dict(primary))],broader_unresolved=[])

def test_broad_native_bls_includes_one_exposure_duration():
    duration=C.broad_duration_grid(np.full(100,200/86400))
    assert len(duration)==8 and duration[0]==pytest.approx(200/86400)
    assert duration[-1]==.20

@pytest.mark.parametrize('changes',[{'period_days':6.},{'epoch_btjd':1.4}])
def test_large_residual_D_does_not_pass_wrong_identity(changes):
    evidence=record();evidence['residuals'][0]['fit'].update(changes)
    assert C.decide(evidence,49,6)['status']=='UNRESOLVED'

def test_matching_residual_passes_and_missing_identity_is_unknown():
    evidence=record()
    assert C.decide(evidence,49,6)['status']=='PASS'
    evidence['residuals'][0]['fit']={'D':80.}
    assert C.decide(evidence,49,6)['status']=='UNRESOLVED'

def test_residual_duration_floor_and_shared_D_threshold():
    evidence=record();evidence['residuals'][0]['fit']['D']=48.
    assert C.decide(evidence,49,6)['status']=='REJECT'
    assert C.decide(evidence,36,6)['status']=='PASS'

def test_v2_complete_physical_planet_grid():
    t=np.r_[np.arange(0,8,.003),np.arange(30,38,.003)]
    sector=np.where(t<10,1,2);e=np.full(len(t),.0001)
    rng=np.random.Generator(np.random.PCG64(2026091304))
    f=1-.008*C.shape(t,2.,.5,.04,.25,.003)+rng.normal(0,e)
    result=C.measure(t,f,e,sector,dict(period_days=2.,epoch_btjd=.5,duration_days=.04,depth_ppt=8.),
                     dict(radius_rsun=.3,mass_msun=.3))
    assert result['status']=='MEASURED' and C.decide(result,100,10)['status']=='PASS'
    assert len(result['aliases'])==7 and len(result['two_eclipse'])==2
    beta=np.array([result['noise_beta'][int(s)] for s in sector])
    assert np.isclose(result['primary']['chi2'],np.sum(((f-result['primary']['model'])/(e*beta))**2))

def test_free_secondary_phase_and_two_sector_binary_evidence():
    t=np.r_[np.arange(0,8,.003),np.arange(30,38,.003)]
    sector=np.where(t<10,1,2);e=np.full(len(t),.0001)
    rng=np.random.Generator(np.random.PCG64(2026091304))
    f=1+.002*(t-np.where(sector==1,4,34))/8-.008*C.shape(t,2.,.5,.04,.25,.003)
    f-=.004*C.shape(t,2.,1.1,.025,.25,.003)
    f+=rng.normal(0,e)
    result=C.measure(t,f,e,sector,dict(period_days=2.,epoch_btjd=.5,duration_days=.04,depth_ppt=8.),
        dict(radius_rsun=.3,mass_msun=.3),secondary_phase=.3)
    assert result['status']=='MEASURED'
    binary=result['two_eclipse'][0]
    assert binary['fit']['secondary_phase']==pytest.approx(.3,abs=.005)
    assert binary['fit']['E']>10 and binary['fit']['k']==13 and result['primary']['k']==9
    assert binary['recurrence']['sufficient'] and binary['recurrence']['sectors_ge_2sigma']==2
    assert C.decide(result,100,10)['reason']=='Two-eclipse BIC and recurrent sector evidence'
