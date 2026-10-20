"""A late payload cannot bypass the fixed owner deadline or lose its evidence."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest


def load():
    protocol = Path(__file__).resolve().parents[1]/'protocol'
    names = ('common', 'reconcile_operational')
    old = {name: sys.modules.get(name) for name in names}
    try:
        for name in names:
            spec = importlib.util.spec_from_file_location(name, protocol/(name+'.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        spec = importlib.util.spec_from_file_location('deadline_precedence', protocol/'reconcile_operational_v2.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in old.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def fixture(tmp_path, controller_status='TIMEOUT', payload_status='COMPLETE'):
    root = tmp_path/'p11/p11_5'
    root.mkdir(parents=True)
    runtime = dict(candidate_id='c1', series_id='s1', tic_id=1,
                   input_key='input-1', raw_index_sha256='raw-1')
    original = dict(**runtime, stage='A', status=payload_status,
        runtime_manifest_sha256='runtime-1', source_hashes={'source.py':'source-1'},
        measurement={'decision':'PASS', 'diagnostic_value':42},
        wall_seconds=1194.4, cpu_seconds=1180.0,
        policy_decisions={'D25_E6':{'status':'PASS'}})
    output = root/'output.json'
    output.write_text(json.dumps(original, indent=3)+'\n', encoding='utf-8')
    controller = root/'controller.json'
    controller.write_text(json.dumps(dict(status=controller_status, key='c1',
        wall_seconds=1202.4, measured_process_tree_cpu_seconds=1187.0)), encoding='utf-8')
    archive = root/'archive/original.json'
    return root, runtime, output, controller, archive


def apply(m, values):
    root, runtime, output, controller, archive = values
    return m.reconcile_completed_timeout(output, archive, controller, runtime,
        'runtime-1', {'source.py':'source-1'}, root=root)


def test_late_complete_is_unknown_and_exact_original_bytes_survive(tmp_path):
    m=load(); values=fixture(tmp_path); root,runtime,output,controller,archive=values
    before=output.read_bytes()
    row=apply(m,values); resolved=json.loads(output.read_text())
    assert archive.read_bytes()==before
    assert row['original_bytes_preserved']
    assert resolved['status']=='TIMEOUT'
    assert resolved['measurement']==dict(decision='ERROR',gate='UNKNOWN',status='TIMEOUT')
    assert resolved['policy_decisions']=={}
    assert resolved['measurement_available'] is False
    assert resolved['wall_seconds']==1202.4 and resolved['cpu_seconds']==1187.0
    assert resolved['original_payload_wall_seconds']==1194.4
    protocol=Path(__file__).resolve().parents[1]/'protocol'
    spec=importlib.util.spec_from_file_location('deadline_scoring',protocol/'score_common.py')
    scoring=importlib.util.module_from_spec(spec); spec.loader.exec_module(scoring)
    s=dict(status='COMPLETE',measurement=dict(gate='PASS'))
    b=dict(status='COMPLETE',measurement=dict(decision='PASS'))
    c=dict(status='COMPLETE',policy_decisions={'D25_E6':{'status':'PASS'}})
    assert not scoring.u10(resolved,s)
    assert scoring.ordered(resolved,s,b,c,'S0',25,6)=='UNRESOLVED'
    assert apply(m,values) is None
    assert archive.read_bytes()==before


@pytest.mark.parametrize('controller_status,payload_status',
                         [('COMPLETE','COMPLETE'),('TIMEOUT','TIMEOUT')])
def test_nonconflicting_statuses_remain_byte_identical(tmp_path,controller_status,payload_status):
    m=load(); values=fixture(tmp_path,controller_status,payload_status)
    before=values[2].read_bytes()
    assert apply(m,values) is None
    assert values[2].read_bytes()==before
    assert not values[4].exists()


def test_identity_mismatch_refuses_mutation(tmp_path):
    m=load(); values=fixture(tmp_path); before=values[2].read_bytes()
    values[1]['input_key']='different-input'
    with pytest.raises(ValueError,match='identity differs'):
        apply(m,values)
    assert values[2].read_bytes()==before and not values[4].exists()


def test_existing_archive_mismatch_refuses_mutation(tmp_path):
    m=load(); values=fixture(tmp_path); before=values[2].read_bytes()
    values[4].parent.mkdir(); values[4].write_bytes(b'other evidence')
    with pytest.raises(ValueError,match='Preserved late-output bytes differ'):
        apply(m,values)
    assert values[2].read_bytes()==before


def test_active_owner_blocks_reconciliation(tmp_path,monkeypatch):
    m=load(); root=tmp_path/'p11_5'; (root/'manifests').mkdir(parents=True)
    (root/'manifests/controller_owner.json').write_text('{}')
    monkeypatch.setattr(m,'ROOT',root)
    with pytest.raises(RuntimeError,match='owner closes'):
        m.main()
