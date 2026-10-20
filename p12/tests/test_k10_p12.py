import json
import shutil
from pathlib import Path

import pytest

import k10_p12 as K
from p12_common import ROOT as REAL_ROOT


def _record(n_obs, n_exc, sap):
    events = [dict(observed=True, excluded=False, sector=s) for s in (60, 61)]
    return dict(decision='PASS', chosen_ephemeris='survey', per_ephemeris={'survey': dict(
        n_observed=n_obs, n_excluded=n_exc, events=events,
        det_kept={'weighted_mean_depth_ppt': 2.0, 'err_ppt': .1}, sap_kept={'weighted_mean_depth_ppt': sap, 'err_ppt': .1})})


def _tree(tmp_path, artefact, injections_fire, n_inj=100):
    repo = tmp_path
    root = repo / 'p12'
    (root / 'protocol').mkdir(parents=True)
    shutil.copyfile(REAL_ROOT / 'protocol/config.json', root / 'protocol/config.json')
    p8 = repo / 'data/survey/p8/stageA'
    p8.mkdir(parents=True)
    (repo / 'data/survey/p8/review_p8.json').write_text(json.dumps({k: {} for k in K.ARTEFACT_KILLS + K.HOLDS}))
    for key in K.ARTEFACT_KILLS + K.HOLDS:
        fires = key in artefact
        (p8 / f'{key}.json').write_text(json.dumps(_record(11, 8 if fires else 1, 1.8)))
    for i in range(n_inj):
        d = repo / f'data/survey/p10/part2d/calibration/inj_funnel/inj{i:05d}_tic{1000 + i}/stageA'
        d.mkdir(parents=True)
        fires = i < injections_fire
        (d / f'tic{1000 + i}_P1.0000.json').write_text(json.dumps(_record(10, 9 if fires else 0, 1.8)))
    for key in K.P9_NAMED:
        d = repo / f'p9/results/blind/tic{K._tic(key)}/stageA'
        d.mkdir(parents=True)
        (d / f'{key}.json').write_text(json.dumps(_record(10, 0, 1.8)))
    return repo, root


def test_k10_kill_when_the_or_fires_on_the_key_record_and_three_artefacts(tmp_path, monkeypatch):
    repo, root = _tree(tmp_path, artefact=K.ARTEFACT_KILLS[:3], injections_fire=2)
    monkeypatch.setattr(K, 'REPO', repo); monkeypatch.setattr(K, 'ROOT', root)
    monkeypatch.setattr('rules_p12.ROOT', root)
    result = K.calibrate()
    assert result['word'] == 'K10_KILL' and 'K10e' in result['or_variants']
    assert result['table']['K10e']['c']['k'] == 2 and result['artefact_kills_fired'] == 3


def test_k10_flag_when_the_injection_bar_excludes_the_variant(tmp_path, monkeypatch):
    repo, root = _tree(tmp_path, artefact=K.ARTEFACT_KILLS, injections_fire=5)
    monkeypatch.setattr(K, 'REPO', repo); monkeypatch.setattr(K, 'ROOT', root)
    monkeypatch.setattr('rules_p12.ROOT', root)
    result = K.calibrate()
    assert 'K10e' not in result['eligible_variants'] and result['word'] == 'K10_FLAG'
    assert (root / 'manifests/exposure_ledger.jsonl').read_text().count('Part 1c K10 calibration') == 6 + 6 + 100 + 12
