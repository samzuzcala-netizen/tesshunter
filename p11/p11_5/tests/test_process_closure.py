"""Closure checks must distinguish Windows launchers from unfinished science."""
import importlib.util
import sys
from pathlib import Path


directory = Path(__file__).resolve().parents[1] / 'protocol'
old_common = sys.modules.pop('common', None)
sys.path.insert(0, str(directory))
try:
    spec = importlib.util.spec_from_file_location('p115_integrity_closure_tests', directory/'integrity.py')
    I = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(I)
finally:
    sys.path.pop(0)
    sys.modules.pop('common', None)
    if old_common is not None:
        sys.modules['common'] = old_common


def process(pid, command, created=100.):
    return dict(pid=pid, create_time=created, cmdline=command)


def test_windows_redirector_is_allowed_but_identical_sibling_is_not():
    arguments = ['p11/p11_5/protocol/integrity.py', 'final']
    me = process(10, ['python.exe', *arguments])
    launcher = process(9, ['python.exe', *arguments], 99.)
    sibling = process(11, ['python.exe', *arguments], 101.)
    remaining, verifiers = I.remaining_protocol_processes(me, [launcher], [me, launcher, sibling])
    assert remaining == [sibling]
    assert {p['pid'] for p in verifiers} == {9, 10}


def test_scientific_ancestor_and_other_helper_remain_blockers():
    me = process(10, ['python.exe', 'p11/p11_5/protocol/integrity.py', 'final'])
    owner = process(9, ['python.exe', 'p11/p11_5/protocol/controller_v2.py', 'jobs.json'])
    helper = process(12, ['python.exe', 'p11/p11_5/protocol/model_storage.py', 'batch'])
    unrelated = process(13, ['python.exe', 'unrelated_user_project.py'])
    remaining, _ = I.remaining_protocol_processes(me, [owner], [me, owner, helper, unrelated])
    assert remaining == [owner, helper]


def test_creation_time_prevents_a_reused_pid_from_being_excluded():
    arguments = ['p11/p11_5/protocol/integrity.py', 'final']
    me = process(10, ['python.exe', *arguments])
    ancestor = process(9, ['python.exe', *arguments], 99.)
    reused = process(9, ['python.exe', *arguments], 102.)
    remaining, _ = I.remaining_protocol_processes(me, [ancestor], [me, reused])
    assert remaining == [reused]


def test_windows_path_separators_and_empty_commands():
    assert I.is_protocol_python(process(1, ['python.exe', r'p11\p11_5\protocol\funnel_worker.py']))
    assert not I.is_protocol_python(process(1, []))
    assert not I.is_protocol_python(process(1, ['powershell.exe', 'p11/p11_5/protocol/helper.py']))
