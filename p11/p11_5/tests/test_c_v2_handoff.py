"""Corrected C may reuse predecessors only under exact frozen identity."""
import importlib.util
from pathlib import Path
import sys
import pytest

def load_worker():
    root=Path(__file__).resolve().parents[1]/'protocol';sys.path.insert(0,str(root))
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    common=load('p11_5_c2_test_common',root/'common.py')
    previous=sys.modules.get('common');sys.modules['common']=common
    try:return load('p11_5_c2_worker_test',root/'c_v2_worker.py')
    finally:
        if previous is None:sys.modules.pop('common',None)
        else:sys.modules['common']=previous

@pytest.fixture
def handoff(tmp_path,monkeypatch):
    module=load_worker();root=tmp_path/'p11/p11_5'
    monkeypatch.setattr(module,'REPO',tmp_path);monkeypatch.setattr(module,'ROOT',root)
    for name,value in [('runtime.json',{'candidate_id':'fixture'}),('prepared.npz',{}),('metadata.json',{}),('source.py',{})]:
        module.write(tmp_path/name,value)
    registration=root/'manifests/C_v2_correctness_registration.json';module.write(registration,{})
    stages={}
    for stage in ('A','S','B'):
        path=root/f'results/funnel/{stage}/fixture.json';module.write(path,{'stage':stage});stages[stage]=module.sha(path)
    value=dict(candidate_id='fixture',runtime_path='runtime.json',runtime_sha256=module.sha(tmp_path/'runtime.json'),
        prepared_path='prepared.npz',prepared_sha256=module.sha(tmp_path/'prepared.npz'),
        prep_metadata_path='metadata.json',prep_metadata_sha256=module.sha(tmp_path/'metadata.json'),
        stage_hashes=stages,source_hashes={'source.py':module.sha(tmp_path/'source.py')},
        correction_registration_sha256=module.sha(registration))
    return module,value,tmp_path

def test_exact_predecessors_are_reusable(handoff):
    module,value,_=handoff
    assert module.validate_handoff(value)=={'candidate_id':'fixture'}

@pytest.mark.parametrize('path',['prepared.npz','p11/p11_5/results/funnel/A/fixture.json','source.py'])
def test_changed_native_arrays_fit_or_source_cannot_reuse(handoff,path):
    module,value,directory=handoff;(directory/path).write_text('changed')
    with pytest.raises(ValueError,match='changed'):module.validate_handoff(value)
