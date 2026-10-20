"""Packing cannot escape isolated data or silently accept changed evidence."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest


def load():
    protocol=Path(__file__).resolve().parents[1]/'protocol'
    names=('common','model_storage')
    old={name:sys.modules.get(name) for name in names}
    try:
        for name in names:
            spec=importlib.util.spec_from_file_location(name,protocol/(name+'.py'))
            module=importlib.util.module_from_spec(spec);sys.modules[name]=module
            spec.loader.exec_module(module)
        spec=importlib.util.spec_from_file_location('pack_worker',protocol/'model_pack_worker.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    finally:
        for name,value in old.items():
            if value is None:sys.modules.pop(name,None)
            else:sys.modules[name]=value


def plan(m,tmp_path):
    root=tmp_path/'p11/p11_5';data=tmp_path/'data/survey/p11/p11_5'
    case=root/'results/funnel/C_v2/c1.json';archive=data/'c_models_v2/c1.npz'
    case.parent.mkdir(parents=True);archive.parent.mkdir(parents=True)
    case.write_text(json.dumps(dict(candidate_id='c1',status='COMPLETE')))
    archive.write_bytes(b'unchanged logical model container')
    value=dict(candidate_id='c1',stage='C_v2',case_path=case.relative_to(tmp_path).as_posix(),
        case_sha256=m.sha(case),archive_path=archive.relative_to(tmp_path).as_posix(),
        archive_sha256=m.sha(archive),source_hashes={})
    return value,dict(repo=tmp_path,root=root,data=data)


def test_exact_registered_case_and_archive_are_accepted(tmp_path):
    m=load();value,paths=plan(m,tmp_path)
    assert m.validate_plan(value,**paths)=='c1'


@pytest.mark.parametrize('field',['case_path','archive_path'])
def test_paths_outside_isolated_scope_are_refused(tmp_path,field):
    m=load();value,paths=plan(m,tmp_path);value[field]='../historical/file'
    with pytest.raises(ValueError,match='scope'):
        m.validate_plan(value,**paths)


def test_changed_archive_is_refused_without_mutation(tmp_path):
    m=load();value,paths=plan(m,tmp_path)
    archive=tmp_path/value['archive_path'];archive.write_bytes(b'changed')
    with pytest.raises(ValueError,match='bytes changed'):
        m.validate_plan(value,**paths)
    assert archive.read_bytes()==b'changed'


def test_nonruntime_truth_field_is_refused(tmp_path):
    m=load();value,paths=plan(m,tmp_path);value['truth']={'period':3}
    with pytest.raises(ValueError,match='schema'):
        m.validate_plan(value,**paths)
