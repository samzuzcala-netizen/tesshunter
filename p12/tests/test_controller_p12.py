import json
from pathlib import Path
import shutil
import pytest
import controller_p12 as controller
from p12_common import write, read, sha


@pytest.fixture
def fixture_root(tmp_path, monkeypatch):
    root = tmp_path / 'p12'; data = tmp_path / 'newdata'
    for name in ('protocol', 'manifests', 'results', 'tests', 'logs'):
        (root / name).mkdir(parents=True)
    data.mkdir()
    config = dict(budget={'c_free_floor_bytes':0, 'd_free_floor_bytes':0},
                  supervision={'progress_seconds':.03})
    write(root / 'protocol/config.json', config)
    dummy = root / 'tests/A_dummy_worker.py'
    shutil.copyfile(Path(__file__).with_name('A_dummy_worker.py'), dummy)
    monkeypatch.setattr(controller, 'REPO', tmp_path)
    monkeypatch.setattr(controller, 'ROOT', root)
    monkeypatch.setattr(controller, 'DATA', data)
    monkeypatch.setattr(controller, '_other_python', lambda: [])
    monkeypatch.setattr(controller, '_apply_allocation', lambda: ([0], {'fixture':True}))
    return tmp_path, root, dummy


def make_job(repo, dummy, mode='complete', jid='fixture'):
    destination = repo / 'p12/results' / (jid + '.json')
    return dict(job_id=jid, attempt=1, arguments=[dummy.relative_to(repo).as_posix(),mode,str(destination)],
                result_path=destination.relative_to(repo).as_posix(),
                source_hashes={dummy.relative_to(repo).as_posix():sha(dummy)})


def test_complete_result_and_durable_identity(fixture_root):
    repo, root, dummy = fixture_root
    result = controller.run_phase('dummy_complete', [make_job(repo,dummy)], 1, 5)
    assert result['status']=='CLOSED' and result['unknowns']==0
    record=read(root/'results/controllers/dummy_complete/attempts/fixture.json')
    assert record['result_sha256']==sha(repo/record['result_path'])
    assert record['deadline_s']==5 and record['attempt']==1 and record['command']
    assert not (root/'manifests/controller_owner.json').exists()


def test_exclusive_owner(fixture_root):
    repo, root, dummy = fixture_root
    write(root/'manifests/controller_owner.json',controller.identity(controller.psutil.Process()))
    with pytest.raises(RuntimeError,match='EXCLUSIVE_OWNER'):
        controller.run_phase('dummy', [make_job(repo,dummy)],1,5)
    assert not (root/'results/controllers/dummy').exists()


def test_timeout_closes_grandchildren(fixture_root):
    repo, root, dummy = fixture_root
    job=make_job(repo,dummy,'tree')
    result=controller.run_phase('dummy_tree',[job],1,2)
    assert result['status']=='CLOSED' and result['all_owned_workers_closed']
    attempt=read(root/'results/controllers/dummy_tree/attempts/fixture.json')
    assert attempt['status']=='TIMEOUT'
    child=read(repo/job['result_path'])
    assert not controller.identity_alive(child)
    assert all(not controller.identity_alive(p) for p in attempt['process_tree'])


def test_exact_command_identity_prevents_kill(fixture_root):
    row=controller.identity(controller.psutil.Process())
    row['command']=['unrelated invocation']
    controller.terminate_owned(row)
    assert controller.psutil.Process().is_running()


def test_sampled_child_closed_after_parent_exits(fixture_root):
    repo, root, dummy = fixture_root
    job=make_job(repo,dummy,'orphan')
    result=controller.run_phase('dummy_parent_exits',[job],1,5)
    assert result['status']=='CLOSED' and result['all_owned_workers_closed']
    child=read(repo/job['result_path'])
    assert not controller.identity_alive(child)


def test_missing_worker_hash_refused(fixture_root):
    repo, root, dummy=fixture_root
    job=make_job(repo,dummy);job['source_hashes']={}
    with pytest.raises(RuntimeError,match='nonempty'):
        controller.run_phase('dummy_bad',[job],1,1)
    assert not (root/'manifests/controller_owner.json').exists()


def test_retry_manifest_only_operational_unknown(fixture_root):
    repo, root, dummy=fixture_root
    jobs=[make_job(repo,dummy,'complete','ok'),make_job(repo,dummy,'error','err')]
    result=controller.run_phase('dummy_original',jobs,1,5)
    assert result['unknowns']==1
    retry=controller.build_retry('dummy_retry','dummy_original')
    rows=read(retry)
    assert [r['job_id'] for r in rows]==['err'] and rows[0]['attempt']==2
    assert rows[0]['original_receipt_sha256']
    receipt=root/'results/controllers/dummy_original/attempts/err.json'
    record=read(receipt);record['attempt']=2;write(receipt,record,replace=True)
    with pytest.raises(RuntimeError,match='one recorded retry'):
        controller.build_retry('dummy_third','dummy_original')


def test_D_storage_floor_refused(fixture_root, monkeypatch):
    repo,root,dummy=fixture_root
    config=read(root/'protocol/config.json')
    config['budget']['d_free_floor_bytes']=10**30
    write(root/'protocol/config.json',config,replace=True)
    with pytest.raises(RuntimeError,match='STORAGE_D'):
        controller.run_phase('dummy_disk',[make_job(repo,dummy)],1,1)


def test_registered_post_part0_phase_requires_registration(fixture_root,monkeypatch):
    import register_p12
    repo,root,dummy=fixture_root
    write(root/'manifests/phase_sequence.json',{'phases':[{'name':'cal_search','part':2},{'name':'verify_core','part':0}]})
    calls=[]
    monkeypatch.setattr(register_p12,'verify',lambda:calls.append('verified') or {'status':'PASS'})
    assert controller._registration('verify_core') is None and not calls
    assert controller._registration('cal_search')['status']=='PASS' and calls==['verified']
    with pytest.raises(RuntimeError,match='absent from registered'):
        controller._registration('unregistered')
