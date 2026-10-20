import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'protocol'))
from retention_analysis_v1 import sequence,HostStatistics,search_table,funnel_table,interpretation_rule

def summary(ids=(),status=None):
    return dict(status=status or ('RECOVERED_EXACT' if ids else 'NOT_RECOVERED'),
        recovered_candidate_ids=list(ids),exact_candidate_ids=list(ids),alias_candidate_ids=[])

def test_unknown_path_cannot_become_later_failure():
    d={'A':{'a':'OPERATIONAL_UNKNOWN','b':'PASS'},'S':{'b':'FAIL'}}
    s=sequence(summary(['a','b']),{'a','b'},d,set())
    assert s['states']==dict(search='PASS',pre_gate='PASS',A='PASS',S='UNKNOWN',B='UNKNOWN',C='UNKNOWN')

def test_any_full_pass_path_overrides_other_unknown_and_S_hold_carries():
    d={'A':{'a':'OPERATIONAL_UNKNOWN','b':'PASS'},'S':{'b':'HOLD'},'B':{'b':'PASS'},'C':{'b':'PASS'}}
    s=sequence(summary(['a','b']),{'a','b'},d,{'b'})
    assert set(s['states'].values())=={'PASS'}
    assert s['passing_candidates']['C']==['b']

def test_not_run_C_is_unmeasured_and_search_failure_is_terminal():
    d={stage:{'a':'PASS'} for stage in ('A','S','B')}
    assert sequence(summary(['a']),{'a'},d,set())['states']['C']=='NOT_RUN'
    assert set(sequence(summary(),set(),{},set())['states'].values())=={'FAIL'}
    assert set(sequence(summary(status='OPERATIONAL_UNKNOWN'),set(),{},set())['states'].values())=={'UNKNOWN'}

def test_all_paths_must_fail_for_known_failure():
    s=sequence(summary(['a','b']),{'a','b'},{'A':{'a':'FAIL','b':'FAIL'}},set())
    assert s['states']['A']=='FAIL' and s['states']['C']=='FAIL'

def test_whole_host_duplicate_rows_share_resample():
    w=np.array([[2,0],[1,1],[0,2]])
    stats=HostStatistics([10,20],w)
    value=stats.ratio([10,10],[10,10,20])
    assert value['fraction']==pytest.approx(2/3)
    assert value['ci95']==pytest.approx(np.percentile([1,2/3,0],[2.5,97.5]))
    assert stats.ratio([],[])['fraction'] is None
    assert stats.difference([10],[10],[10,20])['ci95']==[0,0]
    with pytest.raises(ValueError):stats.ratio([10,10],[10])
    assert stats.ratio([10,10],[10],allow_rate=True)['fraction']==2

def observation(host,presence='PRESENT',inside=True,recovered=True):
    s=summary(['a'] if recovered else [],None if inside else 'OUTSIDE_DOMAIN')
    return dict(tic_id=host,presence=presence,in_band=inside,mixed_domain_membership=False,
        presets={'survey_p10':s},sequence=sequence(s,{'a'},{st:{'a':'PASS'} for st in ('A','S','B')},set()))

def test_absent_outside_and_unknown_do_not_enter_present_retention_denominator():
    rows=[observation(10),observation(20,recovered=False),observation(20,'ABSENT',recovered=False),
          observation(10,inside=False),observation(20,'OPERATIONAL_UNKNOWN',recovered=False)]
    stats=HostStatistics([10,20],np.array([[2,0],[1,1],[0,2]]))
    table=search_table(rows,'survey_p10',stats)
    assert table['recovery_present']['numerator']==1 and table['recovery_present']['denominator']==2
    assert table['n_outside']==1 and table['forced_unknown']==1
    assert sum(r['numerator'] for r in table['matrix'].values())==3
    funnel=funnel_table(rows,stats)
    assert funnel['search']['cumulative']['denominator']==2
    assert funnel['C']['n_not_run']==1 and funnel['C']['conditional']['denominator']==0
    assert funnel['C']['cumulative']['denominator']==1

def test_H_strict_threshold_power_and_unidentified_fit():
    assert interpretation_rule(40,{'status':'IDENTIFIED','snr50':13},10)==('DID_NOT_FIRE',False)
    assert interpretation_rule(40,{'status':'IDENTIFIED','snr50':13.001},10)==('OPTIMISTIC',True)
    assert interpretation_rule(39,{'status':'IDENTIFIED','snr50':100},10)==('NOT_POWERED',False)
    assert interpretation_rule(60,{'status':'UNIDENTIFIED'},10)==('UNIDENTIFIED',False)
