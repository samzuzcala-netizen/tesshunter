"""An incremental health view must expose changed and newly arrived failures."""
import importlib.util
from pathlib import Path
import sys
import pytest


def load():
    protocol=Path(__file__).resolve().parents[1]/'protocol'
    old_path=list(sys.path);old_common=sys.modules.get('common')
    try:
        sys.path.insert(0,str(protocol))
        spec=importlib.util.spec_from_file_location('common',protocol/'common.py')
        common=importlib.util.module_from_spec(spec);sys.modules['common']=common;spec.loader.exec_module(common)
        spec=importlib.util.spec_from_file_location('p11_5_test_health_v2',protocol/'allocation_health_v2.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:]=old_path
        if old_common is None:sys.modules.pop('common',None)
        else:sys.modules['common']=old_common


@pytest.fixture
def monitor(tmp_path,monkeypatch):
    m=load();repo=tmp_path/'repo';root=repo/'p11/p11_5';folder=root/'results/controllers/fixture'
    folder.mkdir(parents=True)
    monkeypatch.setattr(m,'REPO',repo);monkeypatch.setattr(m,'ROOT',root)
    return m,folder


def test_cached_case_and_new_or_removed_attempts(monitor):
    m,folder=monitor
    m.write(folder/'search_1.json',dict(job_id='search_1',status='COMPLETE',command=[]))
    first=m.terminal_snapshot(folder,{})
    assert first['counts']=={'COMPLETE':1} and first['cache_misses']==1
    again=m.terminal_snapshot(folder,first['entries'])
    assert again['counts']==first['counts'] and again['cache_hits']==1 and again['cache_misses']==0
    m.write(folder/'search_2.json',dict(job_id='search_2',status='TIMEOUT',command=[]))
    second=m.terminal_snapshot(folder,again['entries'])
    assert second['counts']=={'COMPLETE':1,'TIMEOUT':1} and second['cache_hits']==1 and second['cache_misses']==1
    (folder/'search_1.json').unlink()
    third=m.terminal_snapshot(folder,second['entries'])
    assert third['counts']=={'TIMEOUT':1} and 'search_1.json' not in third['entries']


def test_changed_measurement_cannot_hide_internal_failure(monitor):
    m,folder=monitor
    runtime=m.ROOT/'manifests/runtime_funnel/case.json'
    measurement=m.ROOT/'results/funnel/A/case.json'
    m.write(runtime,dict(candidate_id='case'))
    m.write(measurement,dict(status='COMPLETE'))
    m.write(folder/'A_case.json',dict(job_id='A_case',status='COMPLETE',
        command=['p11/p11_5/protocol/funnel_worker.py','A',runtime.relative_to(m.REPO).as_posix()]))
    first=m.terminal_snapshot(folder,{})
    assert first['counts']=={'COMPLETE':1}
    m.write(measurement,dict(status='INPUT_ERROR',reason='Synthetic incomplete measurement'),replace=True)
    second=m.terminal_snapshot(folder,first['entries'])
    assert second['counts']=={'INPUT_ERROR':1} and second['cache_misses']==1


def test_changed_attempt_receipt_invalidates_cached_status(monitor):
    m,folder=monitor;path=folder/'search_1.json'
    m.write(path,dict(job_id='search_1',status='COMPLETE',command=[]))
    first=m.terminal_snapshot(folder,{})
    m.write(path,dict(job_id='search_1',status='TIMEOUT',command=[],reason='Synthetic terminal correction'),replace=True)
    second=m.terminal_snapshot(folder,first['entries'])
    assert second['counts']=={'TIMEOUT':1} and second['cache_misses']==1
