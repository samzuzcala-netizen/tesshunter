"""Reproduce the metadata-schema guard defect and protect phase-boundary recovery."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_saved_stage_a_schema_passes_without_mutating_bytes_and_numeric_changes_fail(tmp_path):
    script=r'''
import json,sys
from pathlib import Path
R=Path(sys.argv[1]);tmp=Path(sys.argv[2]);sys.path.insert(0,str(R/'p10/protocol'))
import run_part2d_calibration_checked as K
import p10_funnel_calibration as F
import audit_p5 as A
from tesshunter.survey import get_config
F.set_rules('p10.0')
j=dict(rank=1,tic_id=42,period=2.0,epoch_btjd=3.0,duration_days=.1,depth_ppt=3.0,
       stitch_snr=8.0,stitch_n_transits=4,n_units=2,tmag=13.0)
key=F.V.kkey(j['tic_id'],j['period'])
for folder in ('stageA','prep','tls'):(tmp/folder).mkdir()
(tmp/'prep'/(key+'.json')).write_text('{}');(tmp/'tls'/(key+'_lc.npz')).write_bytes(b'fixture')
p=tmp/'stageA'/(key+'.json')
r=dict(key=key,rank=1,tic_id=42,rules_version='p10.0',survey_preset='survey_p10',
       input_config=A.input_config_for(get_config('survey_p10')),decision='PASS',seconds=1.0,
       survey={k:j[k] for k in ('period','epoch_btjd','duration_days','depth_ppt','stitch_snr','stitch_n_transits','n_units','tmag')},
       thresholds=F.V.THRESHOLDS['stageA'])
p.write_text(json.dumps(r));before=p.read_bytes()
try:K._original_check_record(p,'A',j)
except RuntimeError as exc:assert str(exc)=='Stage A thresholds differ'
else:raise AssertionError('Did not reproduce the original schema guard defect')
K.check_record(p,'A',j);assert p.read_bytes()==before
for field,value in [('min_kept_events',4),('min_kept_event_snr',8.0),('min_p_const',.01)]:
    bad=json.loads(before);bad['thresholds'][field]=value;p.write_text(json.dumps(bad))
    try:K.check_record(p,'A',j)
    except RuntimeError as exc:assert str(exc)=='Stage A thresholds differ'
    else:raise AssertionError(field)
print('Original defect reproduced; correct saved schema accepted unchanged; altered numerical cuts rejected')
'''
    env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONIOENCODING='utf-8')
    p=subprocess.run([sys.executable,'-B','-c',script,str(ROOT),str(tmp_path)],capture_output=True,text=True,env=env)
    assert p.returncode==0,p.stdout+p.stderr


def test_incomplete_a_is_never_skipped_to_launch_secondary(tmp_path,monkeypatch):
    sys.path.insert(0,str(ROOT/'p10/protocol'))
    import run_part2d_calibration_checked as K
    monkeypatch.setattr(K,'OUT',tmp_path)
    monkeypatch.setattr(K,'STATE',tmp_path/'checked_state.json')
    monkeypatch.setattr(K,'LOCK',tmp_path/'checked.lock')
    monkeypatch.setattr(K,'MANIFEST',tmp_path/'correction.json')
    monkeypatch.setattr(K.C,'STATE',tmp_path/'original_state.json')
    K.MANIFEST.write_text('{}')
    K.STATE.write_text(json.dumps(dict(status='registered_wait_required')))
    K.C.STATE.write_text(json.dumps(dict(status='stopped_review_required',previous_state=dict(phase='fa_a'),
                              error='fa_a contains unsettled or invalid records')))
    (tmp_path/'fa_a_complete.json').write_text(json.dumps(dict(census=dict(invalid=[dict(error="RuntimeError('Stage A thresholds differ')")]))))
    monkeypatch.setattr(K,'verify',lambda:({},dict(wait_for=[])))
    monkeypatch.setattr(K.C,'require_free',lambda:None)
    monkeypatch.setattr(K.C,'phase_census',lambda *args:dict(complete=False,settled=708,expected=709))
    def unexpected(*args,**kwargs):raise AssertionError('A worker must not launch before all A records validate')
    monkeypatch.setattr(K.subprocess,'Popen',unexpected)
    with pytest.raises(RuntimeError,match='Cannot skip an incomplete'):
        K.wait_and_run()
    assert not K.LOCK.exists()
    assert json.loads(K.STATE.read_text())['status']=='stopped_review_required'
