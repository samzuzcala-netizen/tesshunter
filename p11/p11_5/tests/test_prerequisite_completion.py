"""Completion planning must not rerun censored science or drop descendants."""
import importlib.util
from pathlib import Path
import sys


def load():
    protocol = Path(__file__).resolve().parents[1]/'protocol'
    old = sys.modules.get('common')
    try:
        spec = importlib.util.spec_from_file_location('common', protocol/'common.py')
        common = importlib.util.module_from_spec(spec)
        sys.modules['common'] = common
        spec.loader.exec_module(common)
        spec = importlib.util.spec_from_file_location('p11_5_prerequisite_completion', protocol/'prerequisite_completion.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old is None:
            sys.modules.pop('common', None)
        else:
            sys.modules['common'] = old


def test_timeout_is_terminal_and_never_retried():
    m=load()
    assert m.required_missing({}, {'A':dict(status='TIMEOUT')}) == []
    assert m.required_missing({}, {'A':dict(status='INPUT_ERROR')}) == []


def test_missing_b_after_s_timeout_is_completed_without_s_retry():
    m=load()
    records={'A':dict(status='COMPLETE',measurement=dict(decision='PASS')),
             'S':dict(status='TIMEOUT')}
    assert m.required_missing({}, records) == ['B']
    records['B']=dict(status='INPUT_ERROR')
    assert m.required_missing({}, records) == []


def test_engineering_rejected_a_with_ephemeris_retains_isolated_controls():
    m=load()
    records={'A':dict(status='COMPLETE',measurement=dict(decision='FAIL',chosen_ephemeris='survey'))}
    assert m.required_missing({}, records) == []
    assert m.required_missing(dict(engineering_label='native_control'), records) == ['S','B']


def test_missing_a_is_planned_before_descendants():
    assert load().required_missing({}, {}) == ['A']
