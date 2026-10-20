import json
import subprocess
import sys
import pytest
import lock_predictions_p12 as L
from p12_common import write,read,sha
from B_fixtures import roots,REAL_REPO


def entry(tmp_path,runtime,digest):
    return subprocess.run([sys.executable,str(REAL_REPO/'p12/tests/B_search_entry.py'),str(tmp_path),str(runtime),digest],
        cwd=REAL_REPO,capture_output=True,text=True,timeout=60)


def test_worker_refuses_runtime_hash_before_science(tmp_path):
    path=tmp_path/'fixture_runtime.json';path.write_text('{}')
    result=entry(tmp_path,path,'0'*64)
    assert result.returncode!=0 and 'Runtime manifest differs' in result.stderr
    assert (tmp_path/'p12/results/search_io/fixture_runtime.jsonl').exists()


def test_worker_guard_blocks_synthetic_truth_runtime(tmp_path):
    path=tmp_path/'data/survey/p12/calibration/truth/synthetic.json';path.parent.mkdir(parents=True);path.write_text('{}')
    result=entry(tmp_path,path,sha(path))
    assert result.returncode==86
    log=tmp_path/'p12/results/search_io/synthetic.jsonl'
    assert any(json.loads(line)['denied'] for line in log.read_text().splitlines())


def setup_lock(monkeypatch,tmp_path,status='COMPLETE'):
    repo,root,_=roots(monkeypatch,tmp_path,L)
    monkeypatch.setattr(L,'verify',lambda:None)
    phase='fixture_search';job_id='fixture_case'
    code=repo/'fixture_source.py';code.write_text('pass\n');sources={'fixture_source.py':sha(code)}
    prepared=repo/'data/survey/p12/fixture/native.npz';prepared.parent.mkdir(parents=True);prepared.write_bytes(b'fixture-array')
    write(prepared.with_suffix('.json'),dict(ingest_key='fixture'))
    runtime_path=root/'manifests/fixture_case.json'
    runtime=dict(tic_id=1,preset='survey_p10',job_id=job_id,run='data/survey/p12/fixture/runs/survey_p10',
        prepared_path=prepared.relative_to(repo).as_posix(),prepared_sha256=sha(prepared),provenance_sha256=sha(prepared.with_suffix('.json')),
        source_hashes=sources,ingest_key='fixture',star={})
    write(runtime_path,runtime)
    result_path=repo/'data/survey/p12/fixture/result.json'
    write(result_path,dict(status='ok',result=dict(planets=[dict(planet_num=1,period_days=2.,epoch_btjd=.2,duration_days=.1,depth_ppt=1.,stitch_snr=10.)]),searches=[]))
    log=root/'results/search_io/fixture_case.jsonl';log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(json.dumps(dict(path=str(prepared.resolve()),denied=False,mode='r'))+'\n')
    receipt_path=root/'results/search_receipts/fixture_case.json'
    receipt=dict(runtime,status='COMPLETE',runtime_manifest_path=runtime_path.relative_to(repo).as_posix(),runtime_manifest_sha256=sha(runtime_path),
        result_path=result_path.relative_to(repo).as_posix(),result_sha256=sha(result_path),trace_path=None,trace_sha256=None,
        file_access_log=log.relative_to(repo).as_posix())
    write(receipt_path,receipt)
    job=dict(job_id=job_id,attempt=1,arguments=['p12/protocol/blind_search_worker_p12.py',runtime_path.relative_to(repo).as_posix(),sha(runtime_path)],
        result_path=receipt_path.relative_to(repo).as_posix(),source_hashes=sources)
    jobs_path=root/'manifests/fixture_search_jobs.json';write(jobs_path,[job])
    folder=root/f'results/controllers/{phase}'
    write(folder/'launch.json',dict(frozen_jobs=[job],jobs_path=jobs_path.relative_to(repo).as_posix(),jobs_sha256=sha(jobs_path),source_hashes=sources))
    write(folder/'closure.json',dict(status='CLOSED',pending=0,all_owned_workers_closed=True,source_hashes_unchanged=True))
    write(folder/f'attempts/{job_id}.json',dict(job_id=job_id,status=status,attempt=1,result_path=receipt_path.relative_to(repo).as_posix(),result_sha256=sha(receipt_path)))
    return repo,root,phase,prepared,log,folder


def test_lock_requires_closure_and_preserves_unknowns(monkeypatch,tmp_path):
    repo,root,phase,prepared,log,folder=setup_lock(monkeypatch,tmp_path,'TIMEOUT')
    seal=L.lock(phase)
    assert seal['jobs']==1 and seal['unknowns']==1 and seal['accepted']==0
    assert read(repo/seal['path'])['operational_unknown_job_ids']==['fixture_case']


def test_lock_complete_and_idempotent_seal(monkeypatch,tmp_path):
    repo,root,phase,prepared,log,folder=setup_lock(monkeypatch,tmp_path)
    seal=L.lock(phase)
    assert seal['accepted']==1 and seal['unknowns']==0
    assert L.lock(phase)==seal


def test_lock_changed_prepared_refused(monkeypatch,tmp_path):
    repo,root,phase,prepared,log,folder=setup_lock(monkeypatch,tmp_path)
    prepared.write_bytes(b'changed')
    with pytest.raises(RuntimeError,match='Prepared input hash'):L.lock(phase)


def test_lock_guarded_open_fails_even_when_no_worker_receipt(monkeypatch,tmp_path):
    repo,root,phase,prepared,log,folder=setup_lock(monkeypatch,tmp_path,'OPERATIONAL_UNKNOWN')
    attempt=read(folder/'attempts/fixture_case.json');attempt['result_path']=None
    write(folder/'attempts/fixture_case.json',attempt,replace=True)
    log.write_text(json.dumps(dict(path=str(repo/'p9/truth/synthetic.csv'),mode='r',denied=True))+'\n')
    with pytest.raises(RuntimeError,match='STOP-4'):L.lock(phase)


def test_lock_nonclosed_phase_refused(monkeypatch,tmp_path):
    repo,root,phase,prepared,log,folder=setup_lock(monkeypatch,tmp_path)
    closure=read(folder/'closure.json');closure['pending']=1;write(folder/'closure.json',closure,replace=True)
    with pytest.raises(RuntimeError,match='did not close'):L.lock(phase)


def add_retry(repo,root,phase,folder):
    original=read(folder/'launch.json')['frozen_jobs'][0]
    runtime=read(repo/original['arguments'][1]);runtime['run']+='-attempt2'
    runtime_path=root/'manifests/fixture_case_a2.json';write(runtime_path,runtime)
    receipt=read(repo/original['result_path']);receipt.update(run=runtime['run'],
        runtime_manifest_path=runtime_path.relative_to(repo).as_posix(),runtime_manifest_sha256=sha(runtime_path),
        file_access_log='p12/results/search_io/fixture_case_a2.jsonl')
    new_result=repo/'data/survey/p12/fixture/result_a2.json';write(new_result,read(repo/receipt['result_path']))
    receipt.update(result_path=new_result.relative_to(repo).as_posix(),result_sha256=sha(new_result))
    receipt_path=root/'results/search_receipts/fixture_case_a2.json';write(receipt_path,receipt)
    log=root/'results/search_io/fixture_case_a2.jsonl'
    log.write_text(json.dumps(dict(path=str(repo/runtime['prepared_path']),mode='r',denied=False))+'\n')
    job=dict(original,attempt=2,retry_of=phase,original_receipt_sha256=sha(folder/'attempts/fixture_case.json'),
        arguments=[original['arguments'][0],runtime_path.relative_to(repo).as_posix(),sha(runtime_path)],result_path=receipt_path.relative_to(repo).as_posix())
    path=root/'manifests/fixture_retry_jobs.json';write(path,[job]);retry=root/f'results/controllers/{phase}_retry'
    write(retry/'launch.json',dict(frozen_jobs=[job],jobs_path=path.relative_to(repo).as_posix(),jobs_sha256=sha(path),
        source_hashes=original['source_hashes'],retry_of=phase))
    write(retry/'closure.json',dict(status='CLOSED',pending=0,all_owned_workers_closed=True,source_hashes_unchanged=True,retry_of=phase))
    write(retry/'attempts/fixture_case.json',dict(job_id='fixture_case',status='COMPLETE',attempt=2,result_path=receipt_path.relative_to(repo).as_posix(),result_sha256=sha(receipt_path)))


def test_lock_merges_one_immutable_attempt2(monkeypatch,tmp_path):
    repo,root,phase,prepared,log,folder=setup_lock(monkeypatch,tmp_path,'TIMEOUT')
    add_retry(repo,root,phase,folder)
    result=L.lock(phase)
    assert result['jobs']==1 and result['unknowns']==0 and result['accepted']==1


def test_original_forbidden_read_cannot_be_erased_by_retry(monkeypatch,tmp_path):
    repo,root,phase,prepared,log,folder=setup_lock(monkeypatch,tmp_path,'TIMEOUT')
    add_retry(repo,root,phase,folder)
    log.write_text(json.dumps(dict(path=str(repo/'p9/truth/synthetic.csv'),mode='r',denied=True))+'\n')
    with pytest.raises(RuntimeError,match='STOP-4'):L.lock(phase)
