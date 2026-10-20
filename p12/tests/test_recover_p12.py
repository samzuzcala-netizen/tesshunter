import pytest
import recover_p12 as recover
from p12_common import write,read,sha


def test_interrupted_phase_preserves_costs_and_complete_results(tmp_path,monkeypatch):
    root=tmp_path/'p12';folder=root/'results/controllers/dummy'
    (root/'manifests').mkdir(parents=True);folder.mkdir(parents=True)
    monkeypatch.setattr(recover,'REPO',tmp_path);monkeypatch.setattr(recover,'ROOT',root)
    monkeypatch.setattr(recover,'identity_alive',lambda row:False)
    monkeypatch.setattr(recover,'terminate_owned',lambda row:None)
    source=root/'fixture.py';source.write_text('# fixture')
    jobs=[dict(job_id=name,attempt=1,result_path='p12/results/'+name+'.json') for name in ('done','interrupted','pending')]
    owner=dict(pid=999999,create_time=1,command=['gone'],phase='dummy',started_utc='2026-09-22T20:00:00+00:00')
    write(folder/'launch.json',dict(owner=owner,frozen_jobs=jobs,source_hashes={'p12/fixture.py':sha(source)},jobs_sha256='a'*64))
    write(root/'manifests/controller_owner.json',owner)
    write(root/'results/done.json',{'fixture':True})
    done=dict(job_id='done',attempt=1,status='COMPLETE',wall_seconds=10,cpu_seconds=3,
              result_path='p12/results/done.json',result_sha256=sha(root/'results/done.json'))
    write(folder/'attempts/done.json',done);sealed=sha(folder/'attempts/done.json')
    write(folder/'started/interrupted.json',dict(job_id='interrupted',attempt=1,pid=999998,create_time=2,
        command=['gone'],started_utc='2026-09-22T20:00:00+00:00'))
    write(folder/'progress.json',dict(utc='2026-09-22T20:00:30+00:00',queue_hours=.5,
        workers=[dict(job_id='interrupted',elapsed_seconds=30,cpu_seconds=7,process_tree=[])]))
    write(root/'manifests/resource_ledger.json',dict(new_queue_hours=2,intervals=[dict(phase='previous',hours=2)]))
    result=recover.reconcile('dummy')
    assert result['status']=='RECONCILED' and result['resume_jobs']==2
    assert sha(folder/'attempts/done.json')==sealed
    assert read(folder/'attempts/interrupted.json')['status']=='INTERRUPTED_UNKNOWN'
    assert read(folder/'attempts/interrupted.json')['cpu_seconds']==7
    assert read(root/'manifests/resource_ledger.json')['new_queue_hours']==2.5
    assert not (root/'manifests/controller_owner.json').exists()


def test_recycled_owner_stops_without_reconciliation(tmp_path,monkeypatch):
    root=tmp_path/'p12';folder=root/'results/controllers/dummy';folder.mkdir(parents=True)
    monkeypatch.setattr(recover,'ROOT',root);monkeypatch.setattr(recover,'identity_alive',lambda row:False)
    write(folder/'launch.json',{'owner':{'pid':1,'create_time':1,'command':['old'],'phase':'dummy'}})
    write(root/'manifests/controller_owner.json',{'pid':1,'create_time':2,'command':['new'],'phase':'dummy'})
    with pytest.raises(RuntimeError,match='RECYCLED_OWNER'):
        recover.reconcile('dummy')


def test_owner_without_launch_fails_closed(tmp_path,monkeypatch):
    monkeypatch.setattr(recover,'ROOT',tmp_path/'p12')
    with pytest.raises(RuntimeError,match='STOP-5 MISSING_LAUNCH'):
        recover.reconcile('incomplete_startup')
