import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import stage_d_worker_p12 as W
from p12_common import sha


class FakeA(SimpleNamespace):
    pass


def _fake_audit(root, calls):
    A = FakeA(RULES_VERSION='p10.0')
    A.cache_matches = lambda record: record.get('rules_version') == 'p10.0'
    A._ephemeris = lambda tic, period, source='survey': dict(period=period, t0=100.0, duration=0.08, source='survey', ref_depth_ppt=2.0)

    def fit_step(tic, period, force=False, max_iter=2000):
        eph = A._ephemeris(tic, period)
        calls.append(eph)
        return dict(rules_version='p10.0', ephemeris_start=eph, adopted={'period': eph['period']})
    A.fit_step = fit_step
    A.jdump = lambda path, obj: (Path(path).parent.mkdir(parents=True, exist_ok=True), Path(path).write_text(json.dumps(obj)))
    return A


def _stage_c(root, key, decision, blind=None):
    (root / 'stageC').mkdir(parents=True, exist_ok=True)
    (root / 'stageC' / f'{key}.json').write_text(json.dumps(dict(rules_version='p10.0', decision=decision, blind=blind)))


def test_fit_is_seeded_from_the_stage_c_accepted_alias(tmp_path):
    key, calls = 'tic7_P2.0000', []
    A = _fake_audit(tmp_path, calls)
    _stage_c(tmp_path, key, 'PASS', dict(period=4.0001, T0_btjd=101.0, duration_days=0.1, depth=0.997))
    seed = W._install_fit_seed(A, tmp_path, key, 7, 2.0)
    assert seed['seed']['ephemeris']['period'] == 4.0001 and seed['seed']['ephemeris']['source'] == 'stageC.blind'
    fit = A.fit_step(7, 2.0, force=True)
    assert calls[-1]['period'] == 4.0001 and fit['fit_input'] == seed['seed']
    assert A._ephemeris(7, 2.0)['period'] == 2.0          # restored after the fit
    assert A._p8_fit_input(7, 2.0) == seed['seed']        # downstream consistency checks agree
    written = json.loads((tmp_path / 'fit' / f'{key}.json').read_text())
    assert written['fit_input']['stage_c_sha256'] == sha(tmp_path / 'stageC' / f'{key}.json')


def test_unresolved_stage_c_is_seeded_from_the_survey_with_the_forced_record(tmp_path):
    key, calls = 'tic8_P3.0000', []
    A = _fake_audit(tmp_path, calls)
    _stage_c(tmp_path, key, 'UNRESOLVED')
    (tmp_path / 'tls').mkdir()
    forced = dict(rules_version='p10.0', inputs={'products': []}, forced={'depth': 0.998, 'period': 3.0})
    (tmp_path / 'tls' / f'{key}_forced.json').write_text(json.dumps(forced))
    seed = W._install_fit_seed(A, tmp_path, key, 8, 3.0)
    assert seed['tls_substitute'] is True and seed['seed']['version'] == 'p12-unresolved-1'
    substitute = json.loads((tmp_path / 'tls' / f'{key}.json').read_text())
    assert substitute['forced'] == forced['forced'] and 'UNRESOLVED' in substitute['d_side_substitute']
    A.fit_step(8, 3.0, force=True)
    assert calls[-1]['period'] == 3.0 and 'UNRESOLVED' in calls[-1]['source']


def test_stage_c_fail_or_stale_record_is_not_seeded(tmp_path):
    A = _fake_audit(tmp_path, [])
    _stage_c(tmp_path, 'tic9_P1.0000', 'FAIL')
    with pytest.raises(ValueError, match='not eligible'):
        W._install_fit_seed(A, tmp_path, 'tic9_P1.0000', 9, 1.0)
    (tmp_path / 'stageC' / 'tic9_P1.0000.json').write_text(json.dumps(dict(rules_version='p8.0', decision='PASS')))
    with pytest.raises(ValueError, match='does not match'):
        W._install_fit_seed(A, tmp_path, 'tic9_P1.0000', 9, 1.0)


def test_p8_store_plumbing_keeps_the_historical_fit_path(tmp_path):
    A = _fake_audit(tmp_path, [])
    A.RULES_VERSION = 'p8.0'
    original = A.fit_step
    assert W._install_fit_seed(A, tmp_path, 'k', 1, 1.0) is None and A.fit_step is original


def test_neighbour_input_is_the_referenced_table_annotated_with_candidate_depths(tmp_path, monkeypatch):
    monkeypatch.setattr(W, 'REPO', tmp_path)
    table = tmp_path / 'tables' / 'tic5.json'
    table.parent.mkdir()
    table.write_text(json.dumps({'ra': 1.0, 'dec': 2.0, 'gaia': {'target': {'source_id': 1},
                                 'neighbours': [{'max_observed_depth_ppt_total_eclipse': 3.0}]}}))
    root = tmp_path / 'case'
    root.mkdir()
    (root / 'survivors.csv').write_text('tic_id,depth_ppt\n5,2.0\n')
    A = _fake_audit(root, [])
    runtime = dict(tic_id=5, star=dict(radius_rsun=.3, mass_msun=.3, teff_k=3300, tmag=13, ra_deg=1, dec_deg=2),
                   neighbours_reference=dict(path='tables/tic5.json', sha256=sha(table)))
    W._patch_inputs(A, runtime, root)
    nb = A.neighbours_step(5)
    assert nb['candidate_depths_ppt'] == [2.0] and nb['gaia']['neighbours'][0]['can_produce_candidate_depths_total_eclipse'] == [True]
    assert A.stellar_from_cache(5)['radius'] == .3 and A.stellar_from_cache(6) == {}
    with pytest.raises(RuntimeError):
        A.neighbours_step(6)
    table.write_text('{}')
    with pytest.raises(RuntimeError, match='changed'):
        W._patch_inputs(A, runtime, root)
