"""Preserve the yield algorithm while enforcing P10 provenance and population bounds."""
import ast
import csv
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'p10/protocol'))
E = importlib.import_module('p10_expected_yield_engine')
P = importlib.import_module('run_part2d_yield_projection')


def test_original_numerical_functions_are_unchanged():
    def functions(path):
        return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(path.read_text(encoding='utf-8')).body
                if isinstance(n, ast.FunctionDef)}
    original = functions(ROOT / 'scripts/p8_expected_yield.py')
    adapter = functions(ROOT / 'p10/protocol/p10_expected_yield_engine.py')
    for name in ('star_noise', 'box_fraction', 'remaining_fraction', 'ld_shape_factor', 'logistic'):
        assert adapter[name] == original[name]


def test_fresh_import_defaults_are_p10_and_missing_noise_fails_closed(tmp_path):
    code = f"""import sys,json
from pathlib import Path
sys.path.insert(0, {str(ROOT / 'p10/protocol')!r})
import p10_expected_yield_engine as E
assert 'p10/results/' in E.P8.as_posix()
assert E.CONFIG == 'survey_p10'
assert E.COMPLETENESS.name == 'completeness_p10.json'
E.P8=Path({str(tmp_path)!r})
class Config:
    def ingest_key(self): return 'test'
try: E.cached_star_noise(123,Config())
except RuntimeError: pass
else: raise AssertionError('Missing original input was silently replaced')
assert not list(E.P8.rglob('*.json'))
print('verified')
"""
    result = subprocess.run([sys.executable, '-B', '-c', code], text=True, capture_output=True, check=True)
    assert 'verified' in result.stdout


def test_integration_uses_fixed_prior_and_labels_legacy_rule(tmp_path, monkeypatch):
    rows = [{'tic_id': i, 'radius_rsun': .3, 'mass_msun': .3, 'teff_k': 3300,
             'contamination_ratio': .05} for i in (1, 2)]
    targets = tmp_path / 'targets.csv'
    with targets.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    noise = {'sigma': .005, 'n_cad': 40000, 'cadence_days': 200 / 86400,
             'span_days': 500, 'data_days': 40000 * 200 / 86400, 'n_sectors': 4, 'rot': None}
    monkeypatch.setattr(E, 'measure_population_noise', lambda *a, **k: {1: noise, 2: noise})
    comp = tmp_path / 'completeness.json'
    comp.write_text(json.dumps({'generated_utc': 'synthetic', 'rules_version': 'p10.0',
        'n_injections': 12, 'n_stars': 2,
        'levels': {'search_only': {'logistic': {'a': -2, 'b': 1}},
                   'full_funnel_with_pregate': {'logistic': {'a': -4, 'b': 1}}},
        'false_alarms': {'stageA_pass_and_secondary_per_star': 1 / 12}}))
    output = tmp_path / 'yield.json'
    E.main(['--targets', str(targets), '--completeness', str(comp), '--out', str(output)])
    result = json.loads(output.read_text())
    assert result['config'] == 'survey_p10'
    assert result['n_stars_with_prepared_curve'] == 2
    assert all(value == .03 for row in result['prior_completeness'].values() for value in row.values())
    for row in result['expected_new_signals'].values():
        assert row['low'] == row['mid'] == row['high'] > 0
    assert result['expected_new_signals']['through_funnel']['mid'] == pytest.approx(
        .97 * result['detectable_planets_total']['funnel'])
    assert 'decision' not in result and 'stop_rule' not in result
    assert result['p8_legacy_yield_diagnostic_not_p10_decision']['stop'] is True


def test_population_range_uses_missing_noise_bound_and_full_fa_denominator():
    result = P.population_range(20., 30., 2 / 300, 2531)
    assert result['signal_expectation_range'] == [20., 50.]
    assert result['C_load_expectation_range'] == pytest.approx([36.873333333333335, 66.87333333333333])
    for bad in (-1, float('nan'), float('inf')):
        with pytest.raises(ValueError):
            P.population_range(20., bad, 2 / 300, 2531)


@pytest.mark.parametrize('field,value', [('sigma', 0), ('n_cad', 1), ('data_days', float('nan'))])
def test_invalid_original_noise_is_rejected(field, value):
    noise = {'sigma': .005, 'n_cad': 40000, 'cadence_days': 200 / 86400,
             'span_days': 500, 'data_days': 40000 * 200 / 86400, 'n_sectors': 4}
    noise[field] = value
    with pytest.raises(ValueError):
        P.validate_noise(noise)
