import pytest
from common import write,sha
import lock_predictions as L
from full_funnel_plan import stage_allowed


def candidate(num=1):
    return dict(planet_num=num,period_days=2.5,epoch_btjd=2450.25,duration_days=.12,depth_ppt=3.,stitch_snr=9.4,search='whole_long')


def test_prediction_lock_retains_native_fields_partition_and_budget_flag():
    q=candidate();out=L.normalize(42,dict(result=dict(planets=[q]),searches=[dict(label='whole_long',budget_exhausted=True)]))[0]
    assert out['epoch_btjd']==q['epoch_btjd'] and out['period_days']==q['period_days'] and out['duration_days']==q['duration_days']
    assert out['depth_ppt']==q['depth_ppt'] and out['stitch_snr']==q['stitch_snr']
    assert out['partition_budget_exhausted'] is True and out['raw_candidate']==q


@pytest.mark.parametrize('bad',['epoch_btjd','period_days','duration_days','depth_ppt'])
def test_malformed_prediction_cannot_lock(bad):
    q=candidate();q[bad]=None
    with pytest.raises(RuntimeError):L.normalize(42,{'result':{'planets':[q]}})


def test_duplicate_prediction_identity_cannot_lock():
    with pytest.raises(RuntimeError):L.normalize(42,{'result':{'planets':[candidate(),candidate()]}})


def test_both_prediction_locks_required_and_tamper_detected(tmp_path,monkeypatch):
    root=tmp_path/'p10/part3';monkeypatch.setattr(L,'ROOT',root);monkeypatch.setattr(L,'REPO',tmp_path)
    a=root/'manifests/allocation.json';write(a,dict(preset_sequence=['survey_p10','survey_p8']))
    for preset in ['survey_p10','survey_p8']:
        p=root/f'manifests/predictions_{preset}.json';write(p,dict(status='LOCKED',preset=preset))
        if preset=='survey_p8':
            with pytest.raises(FileNotFoundError):L.both_locked()
        write(p.with_name(p.stem+'_seal.json'),dict(sha256=sha(p),allocation_sha256=sha(a)))
    assert len(L.both_locked())==2
    p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(RuntimeError):L.both_locked()


def settled(decision,stage='A'):
    return dict(status='COMPLETE',measurement={('gate' if stage=='S' else 'decision'):decision})


def test_sequential_dispatch_preserves_secondary_hold_and_unknowns():
    assert stage_allowed('S',settled('PASS'))
    assert not stage_allowed('S',settled('FAIL'))
    assert not stage_allowed('S',dict(status='OPERATIONAL_UNKNOWN',measurement={'decision':'PASS'}))
    assert stage_allowed('B',settled('PASS'),settled('HOLD','S'))
    assert not stage_allowed('B',settled('PASS'),settled('FAIL','S'))
    assert not stage_allowed('B',settled('PASS'),None)
