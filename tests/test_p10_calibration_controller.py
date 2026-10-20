"""Reject incomplete or mismatched science before a full calibration is counted."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('p10_calibration_controller_test', ROOT/'p10/protocol/run_part2d_calibration.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


@pytest.mark.parametrize('snapshot', [dict(processes=[{'pid':42}], inaccessible_pids=[]),
                                    dict(processes=[], inaccessible_pids=[42])])
def test_live_or_uninspectable_workers_prevent_launch(snapshot, monkeypatch):
    monkeypatch.setattr(C,'process_snapshot',lambda:snapshot)
    with pytest.raises(RuntimeError,match='Live computation or incomplete'):
        C.require_free()


def test_existing_owner_lock_is_preserved(tmp_path, monkeypatch):
    lock=tmp_path/'calibration.lock';lock.write_text('original owner')
    monkeypatch.setattr(C,'LOCK',lock)
    monkeypatch.setattr(C,'process_snapshot',lambda:dict(processes=[],inaccessible_pids=[]))
    with pytest.raises(RuntimeError,match='Existing calibration lock'):
        C.require_free()
    assert lock.read_text()=='original owner'


def test_changed_frozen_input_is_rejected(tmp_path, monkeypatch):
    p=tmp_path/'input.json';p.write_text('original')
    hashes={'input.json':C.sha(p)}
    monkeypatch.setattr(C,'REPO',tmp_path)
    C.verify_hashes(hashes)
    p.write_text('changed')
    with pytest.raises(RuntimeError,match='Frozen source/input changed'):
        C.verify_hashes(hashes)


def test_only_early_calibration_phases_are_dispatched():
    assert C.PHASES==('fa_a','fa_s','injection_as','analyze')
    for phase in C.PHASES:
        command=C.phase_command(phase)
        assert '--rules' in command and command[command.index('--rules')+1]=='p10.0'
        assert not any(x in command for x in ('stageB','stageC','stageD','--force'))
        assert Path(command[2]).parent==ROOT/'p10/protocol'


def test_record_identity_rule_preset_and_a_linkage_rejections(tmp_path):
    script=r'''
import json,sys,copy
from pathlib import Path
root=Path(sys.argv[1]);tmp=Path(sys.argv[2]);sys.path.insert(0,str(root/'p10/protocol'))
import run_part2d_calibration as C
import p10_funnel_calibration as F
import audit_p5 as A
from tesshunter.survey import get_config
j=dict(rank=1,tic_id=42,period=2.0,depth_ppt=3.0)
p=tmp/'tic42_P2.0000.json'
r=dict(key=p.stem,rank=1,tic_id=42,rules_version='p10.0',survey_preset='survey_p10',
       input_config=A.input_config_for(get_config('survey_p10')),gate='PASS',seconds=1.0,
       survey_period=2.0,survey_depth_ppt=3.0,thresholds=F.R.thresholds(F.R.P10_RULES)['secondary'],
       stageA_decision='PASS',stageA_sample=False)
p.write_text(json.dumps(r));C.check_record(p,'S',j,'PASS')
for field,value in [('tic_id',99),('rules_version','p8.0'),('survey_preset',None),('gate','SKIP'),
                    ('seconds',-1),('survey_period',4.0),('stageA_sample',True),('input_config',{})]:
    bad=copy.deepcopy(r);bad[field]=value;p.write_text(json.dumps(bad))
    try:C.check_record(p,'S',j,'PASS')
    except RuntimeError:pass
    else:raise AssertionError(field)
p.write_text(json.dumps(r))
try:C.check_record(p,'S',j,None)
except RuntimeError:pass
else:raise AssertionError('S accepted without a settled A record')
print('Rejected identity, rules, preset, unfinished gate, timing, ephemeris, sample and ingest mismatches')
'''
    result=subprocess.run([sys.executable,'-B','-c',script,str(ROOT),str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
