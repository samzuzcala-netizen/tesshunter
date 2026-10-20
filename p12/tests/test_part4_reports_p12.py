"""Part 4 and Part 6 report rules on synthetic trees: TTT scoring, the closing sentence, the completeness page."""
import csv
import json
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


def test_ttt_scoring_counts_family_submits_end_to_end_and_at_d(tmp_path, monkeypatch):
    import plan_part2_p12 as P2
    import report_ttt_p12 as T
    repo = tmp_path
    root, data = repo / 'p12', repo / 'data/survey/p12'
    _patch(monkeypatch, (P2, T), repo)
    with (root / 'manifests').mkdir(parents=True) or (root / 'manifests/ttt_negatives.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['tic_id']); w.writeheader()
        for t in (11, 12, 13):
            w.writerow(dict(tic_id=t))
    for t in (11, 12):
        write(root / f'results/native_noise/archival/tic{t}.json', dict(status='INPUT_ELIGIBLE'))
    lock = dict(jobs=[dict(job_id='tenk_tic11', status='COMPLETE', accepted=[dict(candidate_id='tic11_p01', period_days=4.0),
                                                                           dict(candidate_id='tic11_p02', period_days=3.1)]),
                      dict(job_id='tenk_tic12', status='COMPLETE', accepted=[dict(candidate_id='tic12_p01', period_days=1.0)])])
    write(root / 'manifests/neg_ttt_search_predictions_lock.json', lock)
    write(root / 'manifests/neg_ttt_search_predictions_lock_seal.json', dict(sha256=sha(root / 'manifests/neg_ttt_search_predictions_lock.json')))
    cases = []
    for tic, cid, period in ((11, 'tic11_p01', 4.0), (11, 'tic11_p02', 3.1), (12, 'tic12_p01', 1.0)):
        case_root = data / f'funnel/neg_tenk/cases/{cid}'
        runtime = root / f'manifests/runtime/neg_tenk/{cid}.json'
        write(runtime, dict(tic_id=tic, candidate=dict(period_days=period), root=case_root.relative_to(repo).as_posix()))
        cases.append(dict(candidate_id=cid, tic_id=tic, runtime=runtime.relative_to(repo).as_posix()))
    write(root / 'manifests/part4/neg_tenk_cases.json', dict(cases=cases))
    ok = lambda d: dict(status='COMPLETE', measurement=dict(decision=d))
    gate = lambda g: dict(status='COMPLETE', measurement=dict(gate=g))
    for cid, s, b in (('tic11_p01', 'PASS', 'PASS'), ('tic11_p02', 'PASS', 'PASS'), ('tic12_p01', 'FAIL', 'FAIL')):
        write(root / f'results/funnel/neg_tenk/A/{cid}.json', ok('PASS'))
        write(root / f'results/funnel/neg_tenk/S/{cid}.json', gate(s))
        write(root / f'results/funnel/neg_tenk/B/{cid}.json', ok(b))
    write(root / 'results/funnel/neg_tenk/C_closure_neg_ttt_C.json', dict(rows=[dict(candidate_id=c, decision='PASS') for c in
                                                                                  ('tic11_p01', 'tic11_p02', 'tic12_p01')]))
    for cid, key, verdict in (('tic11_p01', 'tic11_P4.0000', 'SUBMIT'), ('tic11_p02', 'tic11_P3.1000', 'SUBMIT'), ('tic12_p01', 'tic12_P1.0000', 'SUBMIT')):
        write(root / f'results/funnel/neg_tenk_D/D/{cid}.json', dict(status='COMPLETE'))
        write(data / f'funnel/neg_tenk/cases/{cid}/stageD/{key}.json', dict(tiers=dict(verdict=verdict, conditions={}), redacted=True))
    # binary periods: tic11 at 2.0 d (4.0 is its 2x alias, 3.1 is off-family), tic12 at 1.0 d
    write(data / 'negatives/truth/ttt_ephemerides.json', dict(records=[dict(tic_id=11, period_days=2.0), dict(tic_id=12, period_days=1.0)]))
    (repo / 'docs/packets/audit_p12/neg_tenk/k').mkdir(parents=True)
    (repo / 'docs/packets/audit_p12/neg_tenk/k/packet.md').write_text('x')
    result = T.score('ttt')
    lb1a, lb1b = result['clauses']['LB1a'], result['clauses']['LB1b']
    assert result['N1'] == 2 and lb1a['number'] == 1 and not lb1a['decisive']  # tic12 failed S and B: not end to end
    assert result['N1_D'] == 2 and lb1b['number'] == 2
    star11 = next(s for s in result['stars'] if s['tic_id'] == 11)
    assert star11['non_family_submits'] == ['tic11_p02']
    assert next(s for s in result['stars'] if s['tic_id'] == 13)['search'] == 'NOT_SEARCHED'
    assert (repo / 'docs/packets/audit_p12/neg_ttt/k/packet.md').exists()


def test_closing_sentence_items_follow_the_registered_rule(tmp_path, monkeypatch):
    import report_completeness_p12 as R
    repo = tmp_path
    _patch(monkeypatch, (R,), repo)
    config = read(Path(__file__).resolve().parents[1] / 'protocol/config.json')
    write(repo / 'p12/protocol/config.json', config)
    table = dict(tables=dict(radius=[dict(bin=[1.0, 1.41], n=100, through_S=9)]))
    window = dict(windows=[dict(window_days=1.0, retention=0.96, noise_ratio_1h=1.02)])
    bar = dict(clauses=[dict(clause='LB3', decisive=False)])
    close = R.closing(table, window, dict(families_above_5d_with_deficit=31), bar)
    assert len(close['items']) == 4 and close['sentence'].startswith('The registered P12 work on these inputs is complete')
    none = R.closing(dict(tables=dict(radius=[dict(bin=[1.0, 1.41], n=100, through_S=40)])),
                     dict(windows=[dict(window_days=1.0, retention=0.94, noise_ratio_1h=1.0)]),
                     dict(families_above_5d_with_deficit=3), dict(clauses=[dict(clause='LB3', decisive=True)]))
    assert len(none['items']) == 1 and 'new sectors beyond 105' in none['items'][0]
