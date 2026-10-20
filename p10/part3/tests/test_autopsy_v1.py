import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'protocol'))
from autopsy_worker_v1 import period_kind,trace_census,log_census

def test_trace_witness_is_distinct_from_final_selection():
    rows=[dict(event='broad_bls',partition='stitch',**{'pass':1},candidates=[
        dict(period_days=7,peak_rank=1,snr=30),dict(period_days=2,peak_rank=2,snr=20)])]
    r=trace_census([json.dumps(x) for x in rows],2)
    assert r['near_trial_count']==1 and len(r['broad_rank_competition'])==1
    assert period_kind(4,2)=='2:1' and period_kind(3,2) is None

def test_logged_gate_survivor_and_selection_witness():
    log='''search_light_curve: TIC 42 stitch
Detection pass 1 (planet 1)
[2.000 d -> 2.000 d] SNR 10 composite 5.00 n_transits 6 PASS
Accepted planet 1: [P] P = 7.000 d composite 6.00
'''
    r=log_census(log,2)
    assert len(r['selection_witnesses'])==1
    assert not log_census(log.replace('6 PASS','6 FAIL'),2)['selection_witnesses']
