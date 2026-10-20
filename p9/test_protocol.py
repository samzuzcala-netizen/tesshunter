"""Meaningful boundary and bypass checks; no astrophysical outcome fixtures."""
import copy, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from common import *

def test_frozen_source_integrity():
    expected=read(P9/'baseline/source_hashes.json')
    assert all(sha(BASE/k)==v for k,v in expected.items())

def test_execution_manifest_has_no_answers():
    import csv
    allowed={'tic_id','radius_rsun','mass_msun','teff_k','tmag','ra_deg','dec_deg'}
    for p in (P9/'manifests').glob('*_execution.csv'):
        assert set(next(csv.reader(p.open()))) <= allowed

def test_guard_blocks_truth_and_historical_packets():
    code="from runner import restrict_inputs; from common import *; restrict_inputs(); open(P9/'truth/sampling_frame.csv')"
    p=subprocess.run([sys.executable,'-c',code],cwd=P9,capture_output=True,text=True)
    assert p.returncode != 0 and 'P9 execution read/write boundary' in p.stderr

def test_catalogue_bypass_cannot_rescue_scientific_fit_failure():
    frozen_imports()
    import revet_p6 as V
    rec={'crossmatch':{'star':{'status':'REJECT'}},'fit':{'adopted':{'delta_chi2_vs_flat':3}}}
    assert V.provisional_verdict(rec)[0]=='KILL'
    x=copy.deepcopy(rec);x['crossmatch']['star'].pop('status')
    assert V.provisional_verdict(x)[0]=='KILL'
    x['fit']={'adopted':{'delta_chi2_vs_flat':100},'uncertainty_issues':['geometry']}
    assert V.provisional_verdict(x)[0]=='HOLD'

def test_sampling_host_assignment_unique():
    import pandas as pd
    df=pd.read_csv(P9/'truth/selection_priority.csv')
    assert df.tic_id.is_unique
    pilot=pd.read_csv(P9/'truth/pilot_selection.csv')
    assert len(pilot)==6

def test_signal_match_rejects_other_planet_and_long_baseline_drift():
    import numpy as np
    from scoring import match_signal
    times=np.arange(0,100,200/86400)
    truth={'period':5.,'epoch_btjd':1.,'duration_hours':2.4}
    assert match_signal(times,truth,dict(period=5.,t0=1.,duration=.1))['matched']
    assert not match_signal(times,truth,dict(period=3.,t0=1.,duration=.1))['matched']
    assert not match_signal(times,truth,dict(period=5.04,t0=1.,duration=.1))['matched']
    assert not match_signal(times,truth,dict(period=5.,t0=2.,duration=.1))['matched']

def test_half_period_is_an_alias_not_exact_recovery():
    import numpy as np
    from scoring import match_signal
    times=np.arange(0,100,200/86400)
    truth={'period':5.,'epoch_btjd':1.,'duration_hours':2.4}
    candidate=dict(period=2.5,t0=1.,duration=.1)
    assert not match_signal(times,truth,candidate)['matched']
    assert match_signal(times,truth,candidate,ratio=.5)['matched']

def test_zero_small_sample_is_not_perfect_certainty():
    from scoring import wilson
    assert wilson(0,3)[1]>.5
    assert wilson(3,3)[0]<.5
    import pandas as pd
    from metrics import estimate
    empty=estimate(pd.DataFrame())
    assert empty['gates']['C']['rate'] is None
    assert empty['gates']['D_submit']['host_any_possible_survival_exact95_envelope']==[None,None]

def test_scoring_refuses_to_open_truth_before_locks(tmp_path,monkeypatch):
    import scoring
    import pytest
    monkeypatch.setattr(scoring,'P9',tmp_path)
    write(tmp_path/'manifests/pilot_ids.json',[123])
    with pytest.raises(RuntimeError,match='Truth remains closed'):scoring.run('pilot')

def test_cluster_counts_and_conditional_product_include_pregate():
    import pandas as pd
    from metrics import estimate
    from scoring import GATES
    rows=[]
    for tic,passes in [(1,8),(1,8),(2,2),(3,0)]:
        rows.append(dict(tic_id=tic,stratum='test',**{g:i<passes for i,g in enumerate(GATES)}))
    e=estimate(pd.DataFrame(rows))
    assert e['n_hosts']==3 and e['n_signals']==4
    assert e['gates']['A']['conditional_n']==3
    assert e['conditional_product_checks']['D_useful']['conditional_product']==.5

def test_corrected_twomin_inventory_agrees_with_cached_list():
    cv=read(P9/'manifests/coverage_corrected.json')
    assert 63 in cv['335590096']['twomin']

def test_timeout_is_unknown_not_scientific_rejection():
    import pandas as pd
    from metrics import estimate
    from scoring import GATES
    rows=[dict(tic_id=1,stratum='test',operational=None,**{g:True for g in GATES}),
      dict(tic_id=2,stratum='test',operational='A',**{g:g in ('search','pre') for g in GATES}),
      dict(tic_id=3,stratum='test',operational=None,**{g:False for g in GATES})]
    e=estimate(pd.DataFrame(rows))
    assert e['gates']['C']['n_operational_unknown']==1
    assert e['gates']['C']['scientific_rate_bounds']==[1/3,2/3]
    assert e['gates']['A']['scientific_conditional_rate_bounds']==[.5,1.]
    assert e['gates']['D_useful']['scientific_conditional_rate_bounds']==[.5,1.]
