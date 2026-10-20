import copy
import numpy as np
import pandas as pd
import pytest
from tesshunter.p11_5_search import array_key,ephemeris_equal,pass_extras,reservoir,replay

def q(p=3.,t=1.,s=10.,d=.1):
    return dict(period_days=p,epoch_btjd=t,snr=s,duration_days=d)

def test_epoch_identity_aliases_and_accumulated_drift():
    assert ephemeris_equal(q(),q(t=4.),100)
    assert not ephemeris_equal(q(),q(t=1.5),100)
    assert not ephemeris_equal(q(),q(p=6.),100)
    assert not ephemeris_equal(q(),q(p=3.0009),1000)

def test_winner_duplicate_does_not_spend_an_extra_and_stable_tie():
    pool=[q(s=20),q(t=4,s=19),q(p=6,s=18),q(t=2,s=18),q(p=9,s=17)]
    assert pass_extras(pool,100)==[pool[2],pool[3]]

def test_originals_are_unchanged_and_truncation_is_explicit():
    originals=[q(s=1)];saved=copy.deepcopy(originals)
    pools=[dict(passing=[q(p=100+i,s=50),q(p=10+i,s=40)],snapshot_id=str(i),partition='chunk0',detection_pass=i) for i in range(16)]
    extras,receipt=reservoir(pools,originals,100)
    assert originals==saved and len(extras)==12 and len(receipt['truncated'])==4
    assert all(e['origin']=='R1_EXTRA' for e in extras)

def test_injected_arrays_and_config_have_separate_keys():
    t=np.arange(20.);f=np.ones(20);e=np.ones(20)*.1
    first=array_key(t,f,e,config={'window':.75})
    f[3]=.99
    assert first!=array_key(t,f,e,config={'window':.75})
    assert first!=array_key(t,np.ones(20),e,config={'window':1.})

def test_replay_requires_complete_matching_snapshot_and_uses_same_selection():
    p=dict(complete=True,input_key='a',config_key='c',snapshot_id='s',snapshot_array_key='h',
           partition='chunk0',detection_pass=1,passing=[q(),q(p=6,s=9)])
    assert replay([p],[],100,'a','c')==reservoir([p],[],100)
    for field,value in [('complete',False),('input_key','injected'),('config_key','d'),('snapshot_id',None)]:
        with pytest.raises(ValueError):replay([dict(p,**{field:value})],[],100,'a','c')

def test_versioned_detector_is_identical_except_observer():
    # Structural guard covers every unchanged gate, mask, limit and branch.
    import inspect
    from tesshunter.pipeline import _detect_planets as old
    from tesshunter.p11_5_detector import _detect_planets as new
    code=inspect.getsource(new)
    code=code.replace('    observer=None,\n','').replace('    observer_seconds = 0.0\n','')
    code=code.replace('time.perf_counter() - observer_seconds','time.perf_counter()')
    code=code.replace('        if observer is not None:\n            callback_start = time.perf_counter()\n            observer(lc_clean, working_lc, resolved_pool, _idx + 1)\n            observer_seconds += time.perf_counter() - callback_start\n','')
    assert code.strip()==inspect.getsource(old).strip()

def test_observer_preserves_real_ordinary_mask_trajectory(monkeypatch,tmp_path):
    import lightkurve as lk
    from tesshunter import pipeline as old,p11_5_detector as new
    from tesshunter.p11_5_search import PoolRecorder
    t=np.arange(0,30,.02);lc=lk.LightCurve(time=t,flux=np.ones(len(t)),flux_err=np.full(len(t),.01))
    calls=[]
    def bls(curve,**kw):
        if kw['top_n']==3:return None,None,pd.DataFrame()
        calls.append(np.array(curve.time.value))
        n=len([a for a in calls])
        p=3. if n%2 else 7.
        return None,None,pd.DataFrame([dict(q(p=p,s=15),depth_ppt=2.,event_completeness=1.,n_transits_observed=5),
            dict(q(p=11,s=14),depth_ppt=2.,event_completeness=1.,n_transits_observed=3)])
    monkeypatch.setattr(old.bls_search,'run_bls',bls)
    monkeypatch.setattr(old.bls_search,'resolve_aliases_for_candidate',lambda lc,row,**kw:(row,pd.DataFrame()))
    monkeypatch.setattr(old.preprocessing,'bin_lightcurve',lambda lc,**kw:lc)
    for module in (old,new):
        monkeypatch.setattr(module,'_anchor_plausibility',lambda *a:(True,{}))
        monkeypatch.setattr(module,'_duration_is_railed',lambda *a,**kw:False)
    kw=dict(period_min=.5,period_max=15,duration_min=.02,duration_max=.2,max_planets=2,bin_minutes=None,
        top_n=16,n_periods=None,snr_min=4.,snr_min_resolved=4.,min_event_completeness=.5,min_composite_score=0,
        min_transits=3,mask_width_factor=2,artifact_periods=[],known_periods={},rank_by='snr')
    a,_=old._detect_planets(lc,notes=[],**kw);original_calls=[x.copy() for x in calls];calls.clear()
    recorder=PoolRecorder(tmp_path/'snapshots','i','c');recorder.start_partition('stitch')
    b,_=new._detect_planets(lc,notes=[],observer=recorder,**kw);recorder.close()
    assert a==b and len(b)==2 and len(calls)==2
    assert all(np.array_equal(x,y) for x,y in zip(original_calls,calls))
    assert [p['period_days'] for p in b]==[3.,7.]
    assert len(recorder.pools)==2 and recorder.pools[1]['snapshot_points']<len(lc)
    assert np.array_equal(recorder.restore(recorder.pools[1])[0],calls[1])
    # The alternative at P=11 is retained as evidence and never contributes a mask.
    extras,_=replay(recorder.pools,b,30,'i','c');assert extras[0]['period_days']==11
