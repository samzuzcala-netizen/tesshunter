from types import SimpleNamespace
import os
import pytest
import p12_common as C


def test_p12_data_junction_and_cache_redirect():
    assert C.assert_data_root().drive.casefold() == 'd:'
    module = SimpleNamespace(AUDIT_CACHE=None)
    assert C.redirect_audit_cache(module).resolve().drive.casefold() == 'd:'
    assert os.environ['LIGHTKURVE_CACHE'] == str(module.AUDIT_CACHE)


def test_registered_keys_and_no_queue_cap():
    cfg = C.config()
    assert cfg['deadlines_seconds'] == dict(download=600, verify=600, search=3600, A=1200,
        S=300, B=300, C=12240, C_retry=36000, D=5400, cutout=240, neighbours=900, prepare=1200)
    assert cfg['workers'] == dict(download=4, neighbours=2, verify=8, search=24, A=24, S=24, B=24, C=3, D=2)
    assert cfg['budget'] == dict(c_free_floor_bytes=25000000000, d_free_floor_bytes=50000000000)
    assert cfg['forecast_margin'] == 1.25 and cfg['maximum_cores'] == 24
    assert cfg['bootstrap']['seed'] == 2026092001 and cfg['engineering_seed'] == 2026092002
    assert cfg['sector_policy_sha256'] == C.sha(C.REPO / cfg['sector_policy_path'])


def test_immutable_receipt_and_replace_retry(tmp_path, monkeypatch):
    path = tmp_path / 'receipt.json'
    C.write(path, {'v': 1})
    with pytest.raises(FileExistsError):
        C.write(path, {'v': 2})
    original = C.os.replace
    calls = []
    def replacement(src, dst):
        calls.append((src, dst))
        if len(calls) < 3:
            raise PermissionError('fixture contention')
        return original(src, dst)
    monkeypatch.setattr(C.os, 'replace', replacement)
    monkeypatch.setattr(C.time, 'sleep', lambda _: None)
    C.write(path, {'v': 3}, replace=True)
    assert C.read(path) == {'v': 3} and len(calls) == 3
