import json
import subprocess
import sys
import numpy as np
import pytest
import input_identity_p12 as I
import policy_products_p12 as P
import prepare_injections_p12 as J
import score_injections_p12 as S
from B_fixtures import REAL_REPO,roots,product,identity
from p12_common import read


def test_injection_changes_both_flux_streams_only_in_transit(monkeypatch,tmp_path):
    repo,root,_=roots(monkeypatch,tmp_path,I,P,J)
    meta,source=product(repo,1,56,n=1200);identity(repo,root,1,[meta],[source])
    original=P.load_policy_products(1)[0]
    row=dict(job_id='synthetic',tic_id=1,period=.7,t0_frac=.4,rp_rs=.08,b=.3,a_rs=10.,u1=.3,u2=.2)
    _,_,injected,model=J.prepare_arrays(1,row)
    changed=injected[0]
    from tesshunter import survey
    parameters=J.injection_parameters([original],row)
    transit=survey.transit_model(original['time'],**parameters,exp_time_days=200/86400.)
    inside=transit<1
    assert inside.any() and (~inside).any()
    for key in original:
        if not isinstance(original[key],np.ndarray):continue
        if key in ('flux','sap_flux'):
            np.testing.assert_array_equal(original[key][~inside],changed[key][~inside])
            assert np.any(original[key][inside]!=changed[key][inside])
        else:np.testing.assert_array_equal(original[key],changed[key])


def test_five_unchanged_calibration_hosts_equal_p10(tmp_path):
    result=subprocess.run([sys.executable,str(REAL_REPO/'p12/tests/B_sealed_replay.py'),'injection',str(tmp_path)],
        cwd=REAL_REPO,capture_output=True,text=True,timeout=240)
    assert result.returncode==0,result.stderr
    assert '"passed": 5' in result.stdout


@pytest.mark.parametrize('ratio,epoch,status',[(1.,.2,'recovered'),(2.,.2,'alias'),(.5,.2,'alias'),(3.,.2,'alias'),(1/3,.2,'alias'),(1.,.45,'missed')])
def test_recovery_period_and_window_rules(ratio,epoch,status):
    model=dict(period=2.,t0=.2,t14_days=.06,rp_rs=.06,b=.3,a_rs=12.,u1=.3,u2=.2)
    row=dict(job_id='synthetic',tic_id=1,injection=dict(period=2.,rp_rs=.06,b=.3),injection_model=model)
    candidate=dict(planet_num=1,period_days=2.*ratio,epoch_btjd=epoch,duration_days=.06,snr=10.,
        stitch_snr=10.,stitch_n_transits=5,stitch_epoch_consistent=True)
    t=np.arange(6000)*200/86400.;prepared=dict(time=t,flux=1+.001*np.sin(np.arange(len(t))))
    result=S.score_row(row,dict(status='COMPLETE',accepted=[candidate]),prepared)
    assert result['status']==status
    assert result['recovered']==(status=='recovered')
    assert result['snr_expected']>0


def test_failed_search_stays_operational_unknown():
    model=dict(period=2.,t0=.2,t14_days=.06,rp_rs=.06,b=.3,a_rs=12.,u1=.3,u2=.2)
    row=dict(job_id='synthetic',tic_id=1,injection=dict(period=2.,rp_rs=.06,b=.3),injection_model=model)
    t=np.arange(1000)*200/86400.;prepared=dict(time=t,flux=1+.001*np.sin(np.arange(len(t))))
    assert S.score_row(row,dict(status='TIMEOUT',accepted=[]),prepared)['status']=='operational_unknown'


def test_twenty_sealed_outcome_rows_level_algebra(tmp_path):
    result=subprocess.run([sys.executable,str(REAL_REPO/'p12/tests/B_sealed_replay.py'),'outcomes',str(tmp_path)],
        cwd=REAL_REPO,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert '"passed": 20' in result.stdout


def test_required_twenty_sealed_rows_full_period_window_replay(tmp_path):
    """Execute the authorized replay; a prior status receipt cannot satisfy it."""
    result=subprocess.run([sys.executable,str(REAL_REPO/'p12/tests/B_authorized_historical_replay.py'),str(tmp_path)],
        cwd=REAL_REPO,capture_output=True,text=True,timeout=180)
    assert result.returncode==0,result.stderr+result.stdout
    receipt=read(tmp_path/'replay.json')
    assert receipt['full_historical_replay_completed'] and receipt['passed']==20
    assert not receipt['failures'] and not receipt['expectation_changed']
