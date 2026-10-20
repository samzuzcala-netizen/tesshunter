"""Project the closed P10 calibration using only verified original P8 noise.

This does not open Part 3 targets or evaluate any real-candidate outcome.
The original population has a measured model estimate; the unmeasured
additional population has a conservative geometric bound, not a point estimate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'src'), str(REPO / 'p10/protocol')]
OUT = REPO / 'p10/results/part2d_calibration_20260912'
MODEL = OUT / 'yield_model'
CAL = REPO / 'data/survey/p10/part2d/calibration'
ENGINE = REPO / 'p10/protocol/p10_expected_yield_engine.py'
FROZEN = '01bd29efc1b4b57eb6fcc99f340f515c0c2cae2e0162a2e9f96beef92b678f19'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def section_zero_sha():
    raw = (REPO / 'HANDOFF_P10.md').read_bytes()
    section = raw.split(b'## 0. Pre-registered decision rules', 1)[1].split(b'## 1. Part 0: housekeeping', 1)[0]
    return hashlib.sha256(section).hexdigest()


def validate_noise(noise):
    for name in ('sigma', 'n_cad', 'cadence_days', 'span_days', 'data_days', 'n_sectors'):
        value = noise[name]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'Invalid original noise field: {name}')
    if noise['n_cad'] < 100 or int(noise['n_cad']) != noise['n_cad']:
        raise ValueError('Invalid cadence count')


def population_range(measured, additional_upper, fa_rate, population):
    values = (measured, additional_upper, fa_rate, population)
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('Projection requires finite nonnegative inputs')
    fa = fa_rate * population
    return {'signal_expectation_range': [measured, measured + additional_upper],
            'false_alarm_expectation': fa,
            'C_load_expectation_range': [measured + fa, measured + additional_upper + fa]}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    from tesshunter import survey

    assert not MODEL.exists(), 'Exclusive projection: preserve and review any existing run'
    assert section_zero_sha() == FROZEN
    assert not (OUT / 'calibration.lock').exists()
    assert not (OUT / 'calibration_checked.lock').exists()
    assert read(OUT / 'calibration_checked_state.json')['status'] == 'calibration_complete_review_required'
    closed_path = OUT / 'full_calibration_closed_seal_20260912.json'
    closed = read(closed_path)
    assert closed['status'] == 'full_calibration_closed_verified'
    comp_path = CAL / 'completeness_p10.json'
    sealed_files = {entry['path']: entry for entry in closed['files']}
    assert sha(comp_path) == sealed_files[comp_path.relative_to(REPO).as_posix()]['sha256']
    comp = read(comp_path)
    assert comp['rules_version'] == 'p10.0' and comp['config'] == 'survey_p10'
    assert comp['n_injections'] == 2100 and comp['n_stars'] == 300
    cfg = survey.get_config('survey_p10')
    original_cfg = survey.get_config('survey_p8')
    assert cfg.ingest_key() == original_cfg.ingest_key() == '3d160359ad'
    assert cfg.period_min == original_cfg.period_min == .5
    assert cfg.period_max == original_cfg.period_max == 30.
    targets_path = REPO / 'data/survey/targets_p8.csv'
    rows = list(csv.DictReader(targets_path.open(newline='', encoding='utf-8')))
    assert len(rows) == len({r['tic_id'] for r in rows}) == 2000
    summary_path = REPO / 'data/survey/p8/noise_summary_p8.json'
    original_summary = read(summary_path)
    assert original_summary['n_targets'] == original_summary['n_measured'] == 2000
    assert original_summary['failed_after_retry'] == []
    assert original_summary['config'] == original_cfg.to_dict()
    sources = [ENGINE, Path(__file__), REPO / 'scripts/p8_expected_yield.py']
    sources.extend(REPO / 'src/tesshunter' / name for name in
                   ('survey.py', 'survey_yield.py', 'occurrence_grids.py', 'survey_p8.py', 'audit_rules.py'))
    inputs = [targets_path, summary_path, comp_path, closed_path,
              OUT / 'yield_engine_routing.json', OUT / 'geometric_C_load_bound.json']
    originals = {}
    for row in rows:
        name = f"tic{int(row['tic_id'])}_{cfg.ingest_key()}.json"
        original = REPO / 'data/survey/p8/noise_p8' / name
        validate_noise(read(original))
        originals[original] = sha(original)
    source_hashes = {p.relative_to(REPO).as_posix(): sha(p) for p in sources}
    input_hashes = {p.relative_to(REPO).as_posix(): sha(p) for p in inputs}
    MODEL.mkdir()
    noise_dir = MODEL / 'noise_p10'
    noise_dir.mkdir()
    copies = []
    for original, digest in originals.items():
        destination = noise_dir / original.name
        with destination.open('xb') as stream:
            stream.write(original.read_bytes())
        assert sha(destination) == digest
        copies.append({'original': original.relative_to(REPO).as_posix(),
                       'copy': destination.relative_to(REPO).as_posix(), 'sha256': digest})
    manifest = {'utc': utc(), 'status': 'verified_original_noise_copied',
                'population': 'Original 2000 P8 targets; no additional target measurement',
                'claimed_fraction_all_classes': .03, 'period_band_days': [.5, 30.],
                'ingest_key': cfg.ingest_key(), 'full_section_0_sha256': FROZEN,
                'sources_sha256': source_hashes, 'inputs_sha256': input_hashes,
                'noise_copies': copies}
    save(MODEL / 'manifest.json', manifest)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', OMP_NUM_THREADS='1',
               NUMEXPR_NUM_THREADS='1', BLIS_NUM_THREADS='1',
               LIGHTKURVE_CACHE=str(REPO / 'data/cache/lightkurve'))
    started = time.perf_counter()
    command = [sys.executable, '-B', str(ENGINE), '--workers', '4']
    print(f'{utc()} verified 2000 noise copies; running original numerical yield model', flush=True)
    with (MODEL / 'engine.log').open('x', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    save(MODEL / 'execution.json', {'utc': utc(), 'command': command, 'returncode': result.returncode,
                                  'seconds': time.perf_counter() - started})
    assert result.returncode == 0, 'Yield engine failed; inspect the preserved log'
    for group in (source_hashes, input_hashes):
        for path, digest in group.items():
            assert sha(REPO / path) == digest, path
    for entry in copies:
        assert sha(REPO / entry['original']) == sha(REPO / entry['copy']) == entry['sha256']
    assert section_zero_sha() == FROZEN
    engine_path = MODEL / 'expected_yield_p10_engine.json'
    result = read(engine_path)
    json.dumps(result, allow_nan=False)
    assert result['config'] == 'survey_p10'
    assert result['n_targets'] == result['n_stars_with_prepared_curve'] == 2000
    assert result['n_stars_without'] == 0
    assert {p['tic_id'] for p in result['per_star']} == {int(r['tic_id']) for r in rows}
    assert result['prior_completeness'] == {c: {level: .03 for level in ('low', 'mid', 'high')} for c in ('A', 'B', 'C')}
    assert result['calibration']['rules_version'] == 'p10.0'
    assert result['recovery_curves']['central_through_funnel'] == comp['levels']['full_funnel_with_pregate']['logistic']
    sums = result['expected_new_signals']
    for group in sums.values():
        assert group['low'] == group['mid'] == group['high']
    bound = read(OUT / 'geometric_C_load_bound.json')
    measured = sums['through_funnel']['mid']
    assert 0 <= measured <= bound['original_2000_perfect_recovery_signal_bound']
    fa_rate = comp['false_alarms']['stageA_pass_and_secondary_per_star']
    assert fa_rate == 2 / 300
    projection = population_range(measured, bound['any_531_additional_perfect_recovery_signal_bound'], fa_rate, 2531)
    projection.update({'utc': utc(), 'status': 'closed_projection_verified',
        'engine_sha256': sha(engine_path), 'manifest_sha256': sha(MODEL / 'manifest.json'),
        'original_population': 2000, 'maximum_unmeasured_additions': 531, 'projection_population': 2531,
        'claimed_fraction': .03, 'central_model': result['occurrence']['model'],
        'recovery_level': 'full_funnel_with_pregate',
        'original_2000_new_signals': measured,
        'original_2000_search_only_new_signals': sums['search_only']['mid'],
        'original_2000_HU19_sensitivity_new_signals': sums['through_funnel_hu19']['mid'],
        'additional_signal_upper_bound': bound['any_531_additional_perfect_recovery_signal_bound'],
        'all_source_input_and_original_noise_hashes_unchanged': True,
        'limitations': [
            'The range bounds missing prepared-noise measurements for the additional population; it is not a confidence interval or a realized-count bound.',
            'The additional bound uses the largest 531 weights of the entire 1837-star bare-SPOC source pool; this does not adopt a Part 3 selection.',
            'The frozen central DC15 model and empirical FA rate are used for the rule. HU19 is a separately reported sensitivity, not a substituted stop criterion.',
            'The three legacy low/mid/high keys are identical because the claimed fraction is fixed at 0.03; they are not uncertainty limits.',
            'The original engine retains an explicitly renamed P8 legacy yield diagnostic; it never determines P10 continuation.',
            'Later B/C/D survival and final candidate yield remain unmeasured; the calibrated signal expectation is through pre-gate, A and S.'
        ]})
    save(OUT / 'expected_yield_projection_p10.json', projection)
    save(MODEL / 'closed_seal.json', {'utc': utc(), 'status': 'yield_model_closed_verified',
        'original_noise_unchanged': True, 'source_and_input_hashes_unchanged': True,
        'files': [{'path': p.relative_to(REPO).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                  for p in sorted(MODEL.rglob('*')) if p.is_file()]})
    print(json.dumps(projection, indent=2), flush=True)


if __name__ == '__main__':
    main()
