from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'protocol'))
from score_common import match,ordered,isolated,u10,bootstrap_weights,paired,binomial

def record(decision,key='decision'):
    return dict(status='COMPLETE',measurement={key:decision})

def test_exact_p10_match_keeps_alias_out_of_positive_and_checks_epoch():
    truth=dict(period=3.,t0=1.,t14_days=.1)
    e=dict(period_days=6.,epoch_btjd=1.,duration_days=.1)
    assert match(truth,e) is None and match(truth,e,(1,2,3,.5,1/3))==2
    assert match(truth,dict(e,period_days=3.,epoch_btjd=1.5)) is None

def test_unknown_never_protects_a_control_or_recovers_an_injection():
    a=record('PASS');s=record('PASS','gate');b=record('PASS');c=dict(status='INPUT_ERROR')
    assert u10(a,s) and ordered(a,s,b,c,'S2',25,6)=='UNRESOLVED'
    assert isolated(s,c,'S2',25,6)=='UNRESOLVED'
    assert ordered(a,s,record('FAIL'),c,'S2',25,6)=='REJECT'
    assert not u10(dict(status='TIMEOUT'),s)

def test_host_bootstrap_keeps_all_host_injections_together_and_zero_risk_is_not_zero():
    hosts=[1,2];w=bootstrap_weights(hosts,['a','a'])
    assert np.all(w.sum(axis=1)==2)
    rows=[dict(tic_id=1,b=False,y=True),dict(tic_id=1,b=False,y=True),dict(tic_id=2,b=True,y=False)]
    result=paired(rows,'b','y',[True]*3,hosts,w)
    assert result['wins']==2 and result['losses']==1 and result['n']==3
    assert result['ci95_pp']==[-100.,100.]
    assert binomial(0,300)['ci95'][1]>0
