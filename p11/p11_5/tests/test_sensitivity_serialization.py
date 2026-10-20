"""Regression coverage for NumPy scalar diagnostic flags at the JSON boundary."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


def load():
    path = Path(__file__).resolve().parents[1] / 'protocol/sensitivity_tables_v2.py'
    spec = importlib.util.spec_from_file_location('sensitivity_serialization', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nested_numpy_flags_and_numbers_preserve_native_json_values():
    m = load()
    source = dict(logistic=dict(snr50=np.float64(12.5),
        snr50_outside_observed_range=np.bool_(False)),
        rows=[np.int64(109), np.uint64(2**63 + 7), np.bool_(True)], missing=None)
    result = json.loads(json.dumps(m.native_json(source), allow_nan=False))
    assert result == dict(logistic=dict(snr50=12.5,
        snr50_outside_observed_range=False), rows=[109, 2**63 + 7, True], missing=None)
    assert isinstance(source['logistic']['snr50_outside_observed_range'], np.bool_)


@pytest.mark.parametrize('value', [np.float64(float('nan')), np.float64(float('inf'))])
def test_nonfinite_values_remain_rejected(value):
    with pytest.raises(ValueError):
        json.dumps(load().native_json(dict(value=value)), allow_nan=False)


def test_writer_adapter_preserves_destination_options_result_and_restores_writer():
    m = load()
    writes = []
    def writer(path, value, **kwargs):
        writes.append((path, json.dumps(value, allow_nan=False), kwargs))
        return 'written'
    module = SimpleNamespace(write=writer)
    module.main = lambda: module.write('frozen-diagnostics.json',
        dict(flag=np.bool_(True)), replace=False)
    assert m.run_diagnostics(module) == 'written'
    assert writes == [('frozen-diagnostics.json', '{"flag": true}', {'replace': False})]
    assert module.write is writer


def test_failed_output_is_not_suppressed_and_original_writer_is_restored():
    m = load()
    def writer(*args, **kwargs):
        raise FileExistsError('Existing evidence')
    module = SimpleNamespace(write=writer)
    module.main = lambda: module.write('existing.json', dict(flag=np.bool_(False)))
    with pytest.raises(FileExistsError, match='Existing evidence'):
        m.run_diagnostics(module)
    assert module.write is writer
