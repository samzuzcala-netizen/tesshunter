from types import SimpleNamespace
import hashlib
import pytest
import checkin_p12 as checkin
import continuation_p12 as continuation
import final_shutdown_p12 as shutdown
from p12_common import write,read


@pytest.fixture
def supervised(tmp_path,monkeypatch):
    root=tmp_path/'p12';data=tmp_path/'newdata';data.mkdir()
    for name in ('manifests','protocol','logs','results/controllers'):
        (root/name).mkdir(parents=True)
    config={'budget':{'c_free_floor_bytes':25e9,'d_free_floor_bytes':50e9}}
    write(root/'protocol/config.json',config)
    for module in (checkin,continuation,shutdown):
        monkeypatch.setattr(module,'ROOT',root);monkeypatch.setattr(module,'REPO',tmp_path)
    monkeypatch.setattr(checkin,'DATA',data)
    monkeypatch.setattr(checkin.shutil,'disk_usage',lambda path:SimpleNamespace(free=100e9))
    monkeypatch.setattr(checkin,'identity_alive',lambda row:True)
    owner={'pid':123,'create_time':1,'command':['fixture']}
    current=dict(phase='dummy',owner=owner,status='RUNNING',workers=[],completed=0,pending=1,unknowns=0,queue_hours=0)
    write(root/'progress.json',current);write(root/'manifests/controller_owner.json',owner)
    return tmp_path,root,current


def close(root,current,**values):
    (root/'manifests/controller_owner.json').unlink(missing_ok=True)
    write(root/'results/controllers'/current['phase']/'closure.json',
        dict(status='CLOSED',all_owned_workers_closed=True,source_hashes_unchanged=True,**values))


@pytest.mark.parametrize('trigger,expected',[
    ('healthy','SLEEP'),('closed','ADVANCE dummy'),('missing_owner','PAUSE OWNER_GONE_WITHOUT_CLOSURE'),
    ('storage','PAUSE STORAGE_WITHIN_3GB'),('user_stop','PAUSE STOP-4 USER_STOP'),
    ('integrity','PAUSE STOP-1 INTEGRITY_FAILURE'),('pilot','PAUSE decision_point_1'),
])
def test_checkin_trigger_table(supervised,monkeypatch,trigger,expected):
    repo,root,current=supervised
    if trigger=='closed':close(root,current)
    elif trigger=='missing_owner':monkeypatch.setattr(checkin,'identity_alive',lambda row:False)
    elif trigger=='storage':
        monkeypatch.setattr(checkin.shutil,'disk_usage',lambda path:SimpleNamespace(free=27e9 if path==repo else 100e9))
    elif trigger=='user_stop':(root/'manifests/USER_STOP').touch()
    elif trigger=='integrity':write(root/'results/active_integrity_failure.json',{})
    elif trigger=='pilot':
        current['phase']='pilot_A';write(root/'progress.json',current,replace=True);close(root,current)
    assert checkin.checkin()==expected
    assert read(root/'logs/last_checkin.json')['per_case_science_opened'] is False
    assert (repo/'RESUME_P12.md').exists()


def test_stall_stops_only_owned_worker_then_pauses(supervised,monkeypatch):
    repo,root,current=supervised
    worker={'job_id':'sleepy','pid':234,'create_time':2,'command':['fixture_worker'],'cpu_seconds':10}
    current['workers']=[worker];write(root/'progress.json',current,replace=True)
    write(root/'logs/last_checkin.json',dict(workers=[worker]))
    monkeypatch.setattr(checkin,'_sample_cpu',lambda row:10)
    stopped=[];monkeypatch.setattr(checkin,'terminate_owned',lambda row:stopped.append(row['job_id']))
    assert checkin.checkin()=='SLEEP' and stopped==['sleepy']
    assert checkin.checkin()=='PAUSE WORKER_STALLED_TWO_CHECKS' and stopped==['sleepy']


def test_printed_checkin_contract(supervised,capsys):
    checkin.main()
    assert capsys.readouterr().out=='SLEEP\n'


def test_sequence_skips_false_branch_without_reordering():
    sequence={'phases':[
        {'name':'ttt','kind':'controller','part':4,'depends_on':[]},
        {'name':'p9_blind','kind':'controller','part':4,'depends_on':['ttt']},
        {'name':'p9_assisted','kind':'controller','part':4,'depends_on':['p9_blind']},
        {'name':'natural','kind':'controller','part':4,'depends_on':['p9_assisted']},
        {'name':'extension','kind':'controller','part':5,'depends_on':['natural'],
         'condition':{'path':'decision.json','field':'tier','in':['E1','E2']}},
        {'name':'final','kind':'controller','part':5,'depends_on':['extension']},
    ]}
    assert continuation.next_phase(sequence,'ttt',{})['phase']=='p9_blind'
    assert continuation.next_phase(sequence,'p9_blind',{})['phase']=='p9_assisted'
    assert continuation.next_phase(sequence,'p9_assisted',{})['phase']=='natural'
    assert continuation.next_phase(sequence,'natural',{})['action']=='PAUSE'
    result=continuation.next_phase(sequence,'natural',{'decision.json':{'tier':'core'}})
    assert result['phase']=='final' and result['skipped']==['extension']


def test_sequence_rejects_forward_dependency():
    with pytest.raises(ValueError,match='Dependency'):
        continuation.next_phase([{'name':'bad','kind':'controller','depends_on':['later']}],None,{})


def test_shutdown_absent_routine_and_historical_paused(supervised,monkeypatch):
    repo,root,current=supervised
    (root/'manifests/controller_owner.json').unlink()
    automations=repo/'automation-fixtures'
    for ident in ('prompt-10-3-hourly-check-in','continue-local-p10-execution'):
        path=automations/ident/'automation.toml';path.parent.mkdir(parents=True)
        path.write_text('status = "PAUSED"\nprompt = "fixture"\n')
    monkeypatch.setattr(shutdown,'AUTOMATIONS',automations)
    monkeypatch.setattr(shutdown,'_science_processes',lambda:[])
    result=shutdown.verify_shutdown()
    assert result['status']=='DISABLED_VERIFIED'
    assert result['routine']['configured_status']=='ABSENT_NOT_ARMED'
    assert result['checkin_count']==0


def test_shutdown_active_routine_refused(supervised,monkeypatch):
    repo,root,current=supervised
    (root/'manifests/controller_owner.json').unlink()
    automations=repo/'automation-fixtures'
    for ident,status in [('prompt-10-3-hourly-check-in','PAUSED'),('continue-local-p10-execution','PAUSED'),('prompt-12-hourly-check-in','ACTIVE')]:
        path=automations/ident/'automation.toml';path.parent.mkdir(parents=True)
        path.write_text('status = "'+status+'"\nprompt = "fixture"\n')
    monkeypatch.setattr(shutdown,'AUTOMATIONS',automations)
    with pytest.raises(RuntimeError,match='ROUTINE_ACTIVE'):
        shutdown.verify_shutdown()
