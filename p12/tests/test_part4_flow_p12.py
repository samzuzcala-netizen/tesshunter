"""Part 4 planners and the LB3 scorer on synthetic trees (no real record read)."""
import csv
import sys
from pathlib import Path

import pytest

from p12_common import write, read, sha

P12 = Path(__file__).resolve().parents[1]
if (P12 / 'work/dev').is_dir() and str(P12 / 'work/dev') not in sys.path:
    sys.path.append(str(P12 / 'work/dev'))


def _patch(monkeypatch, modules, repo):
    for module in modules:
        for name, value in (('REPO', repo), ('ROOT', repo / 'p12'), ('DATA', repo / 'data/survey/p12')):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)


def test_forced_route_planners_and_d_runtimes(tmp_path, monkeypatch):
    import plan_part2_p12 as P2
    import plan_part4_p12 as P4
    repo = tmp_path
    root = repo / 'p12'
    _patch(monkeypatch, (P2, P4), repo)
    monkeypatch.setattr(P2, '_sources', lambda: {})
    monkeypatch.setattr(P2, '_write_jobs', lambda phase, jobs: write(root / f'manifests/{phase}_jobs.json', jobs) or root / f'manifests/{phase}_jobs.json')
    (root / 'manifests').mkdir(parents=True)
    with (root / 'manifests/ttt_negatives.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['tic_id', 'rad', 'mass', 'Teff', 'Tmag', 'ra', 'dec']); w.writeheader()
        w.writerow(dict(tic_id=21, rad=0.3, mass=0.3, Teff=3300, Tmag=13.2, ra=10.0, dec=-40.0))
    planet = dict(planet_num=1, search='s', period_days=2.0, epoch_btjd=3000.0, duration_days=0.05, depth_ppt=9.0, snr=30.0,
                  n_transits_observed=9, stitch_snr=30.0, stitch_n_transits=9, stitch_epoch_consistent=True)
    result = repo / 'data/survey/p12/negatives/tenk/runs/survey_p10/results/tenk_tic21.json'
    write(result, dict(status='ok', tic_id=21, result=dict(planets=[planet])))
    lock = root / 'manifests/neg_ttt_search_predictions_lock.json'
    write(lock, dict(jobs=[dict(job_id='tenk_tic21', status='COMPLETE', result_path=result.relative_to(repo).as_posix(), accepted=[])]))
    write(root / 'manifests/neg_ttt_search_predictions_lock_seal.json', dict(sha256=sha(lock)))
    collected = P4.cases('ttt', 'neg_ttt_search')
    assert collected['label'] == 'neg_tenk' and [c['candidate_id'] for c in collected['cases']] == ['tic21_p01']
    runtime = read(repo / collected['cases'][0]['runtime'])
    assert runtime['route'] == 'forced_negatives' and runtime['population_tier'] == 'negative_ttt_domain'
    assert 'ttt' not in collected['cases'][0]['runtime'] and 'tenk' in runtime['root']
    P4.stage('A', 'ttt', 'neg_ttt_A', 'neg_ttt_search')
    ok = lambda d: dict(status='COMPLETE', measurement=dict(decision=d))
    write(root / 'results/funnel/neg_tenk/A/tic21_p01.json', ok('PASS'))
    write(root / 'results/funnel/neg_tenk/S/tic21_p01.json', dict(status='COMPLETE', measurement=dict(gate='FAIL')))
    P4.stage('B', 'ttt', 'neg_ttt_B', 'neg_ttt_search')
    assert [j['job_id'] for j in read(root / 'manifests/neg_ttt_B_jobs.json')] == ['tic21_p01']  # B recorded whatever S said
    P4.c('ttt', 'neg_ttt_C', 'neg_ttt_search')
    c_runtime = read(repo / read(root / 'manifests/neg_ttt_C_jobs.json')[0]['arguments'][1])
    assert c_runtime['route'] == 'forced_negatives'
    write(root / 'results/funnel/neg_tenk/C_closure_neg_ttt_C.json', dict(rows=[dict(candidate_id='tic21_p01', label='neg_tenk', decision='UNRESOLVED')]))
    import crossmatch_p12
    monkeypatch.setattr(crossmatch_p12, 'crossmatch_step', lambda row: dict(status='CLEAN', tic_id=row['tic_id']))
    import stage_d_plan_p12
    monkeypatch.setattr(stage_d_plan_p12, 'HISTORICAL', ())
    P4.d('ttt', 'neg_ttt_D', 'neg_ttt_C')
    job = read(root / 'manifests/neg_ttt_D_jobs.json')[0]
    runtime = read(repo / job['arguments'][1])
    retry = read(repo / job['retry_arguments'][1])
    assert runtime['phase'] == 'neg_ttt_D' and retry['phase'] == 'neg_ttt_D_retry' and runtime['redact_catalogue']
    assert 'ttt' not in job['arguments'][1] and 'ttt' not in job['result_path'] and 'ttt' not in job['retry_result_path']
    assert runtime['packet_subtree'] == 'neg_tenk'


def test_lb3_counts_k6_k8_k10_on_converged_fits(tmp_path, monkeypatch):
    import ephemeris_assisted_p12 as E
    repo = tmp_path
    root = repo / 'p12'
    _patch(monkeypatch, (E,), repo)
    monkeypatch.setattr(E, 'ASSISTED', repo / 'p12/heldout/results/assisted')
    signals = []
    for i, fired in enumerate((['K0'], ['K0', 'K8'], [], ['K6'], ['K0'], [])):
        key = f'tic{i}_P1.0000'
        signals.append(dict(truth_id=f's{i}', tic_id=i, key=key))
        write(root / f'results/funnel/bar_p9_eph/D/{key}.json', dict(status='COMPLETE'))
        conditions = {n: dict(fired=(n in fired)) for n in ('K0', 'K6', 'K8', 'H3')}
        fit = dict(adopted=dict(period=1.0)) if i != 5 else dict(error='no convergence')
        write(E.ASSISTED / key / 'stageD' / f'{key}.json', dict(tiers=dict(verdict='KILL' if fired else 'SUBMIT', conditions=conditions), fit=fit))
    write(root / 'manifests/bar_p9_eph_signals.json', dict(signals=signals))
    table = E.score()['ephemeris_assisted']
    assert table['n_fit'] == 5 and table['LB3']['number'] == 2 and table['LB3']['decisive'] and not table['LB3']['holds']
