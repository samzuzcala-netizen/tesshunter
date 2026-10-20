"""Part 5f and Part 6 report generators on a small synthetic tree (no real record is read)."""
import csv
import json
import sys
from pathlib import Path

import pytest

from p12_common import write, read

P12 = Path(__file__).resolve().parents[1]
for extra in (P12 / 'work/dev',):
    if extra.is_dir() and str(extra) not in sys.path:
        sys.path.append(str(extra))


def _csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        w = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def tree(tmp_path, monkeypatch):
    """Two core stars and one E1 star: tic1 (one SUBMIT tier 2 and one S rejection), tic2 (no signal), tic3 (UNKNOWN)."""
    repo = tmp_path
    root = repo / 'p12'
    data = repo / 'data/survey/p12'
    import plan_part2_p12 as P2
    import candidate_list_p12 as CL
    import report_natural_load_p12 as NL
    import report_audit_p12 as AU
    for module in (P2, CL, NL, AU):
        for name, value in (('REPO', repo), ('ROOT', root), ('DATA', data)):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)
    monkeypatch.setattr(AU, 'AUDIT', repo / 'docs/AUDIT_P12.md')
    monkeypatch.setattr(AU, 'HANDOFF', repo / 'HANDOFF_P12.md')
    _csv(root / 'manifests/targets_p12_core.csv', [dict(tic_id=1, source_set='p8_2000'), dict(tic_id=2, source_set='p10_436')],
         ['tic_id', 'source_set'])
    write(root / 'manifests/eligibility_p12.json', dict(per_star={'1': dict(status='INPUT_ELIGIBLE'), '2': dict(status='INPUT_ELIGIBLE'),
                                                                  '9': dict(status='INPUT_INELIGIBLE')}))
    acc = lambda tic, n, p: dict(candidate_id=f'tic{tic}_p{n:02d}', planet_num=n, period_days=p, epoch_btjd=3000.0, duration_days=0.05,
                                 depth_ppt=2.0, stitch_snr=12.0, partition_budget_exhausted=False)
    write(root / 'manifests/final_predictions_lock.json', dict(jobs=[
        dict(job_id='tic1', tic_id=1, status='COMPLETE', accepted=[acc(1, 1, 2.5), acc(1, 2, 7.0)]),
        dict(job_id='tic2', tic_id=2, status='COMPLETE', accepted=[]),
        dict(job_id='tic3', status='OPERATIONAL_UNKNOWN', accepted=[])]))
    cases = []
    for cid, period in (('tic1_p01', 2.5), ('tic1_p02', 7.0)):
        case_root = data / f'funnel/final/cases/{cid}'
        runtime = root / f'manifests/runtime/final/{cid}.json'
        write(runtime, dict(tic_id=1, candidate=dict(period_days=period), root=case_root.relative_to(repo).as_posix(), population_tier='core'))
        cases.append(dict(candidate_id=cid, tic_id=1, kind='final', runtime=runtime.relative_to(repo).as_posix(), pregate=True))
    write(root / 'manifests/part5/final_cases.json', dict(cases=cases))
    ok = lambda d: dict(status='COMPLETE', measurement=dict(decision=d))
    gate = lambda g: dict(status='COMPLETE', measurement=dict(gate=g))
    write(root / 'results/funnel/final/A/tic1_p01.json', ok('PASS'))
    write(root / 'results/funnel/final/S/tic1_p01.json', gate('PASS'))
    write(root / 'results/funnel/final/B/tic1_p01.json', ok('PASS'))
    write(root / 'results/funnel/final/A/tic1_p02.json', ok('PASS'))
    write(root / 'results/funnel/final/S/tic1_p02.json', gate('FAIL'))
    write(root / 'results/funnel/final/C_closure_final_C.json', dict(rows=[dict(candidate_id='tic1_p01', tic_id=1, decision='PASS')]))
    write(root / 'results/funnel/final_D/D/tic1_p01.json', dict(status='OPERATIONAL_UNKNOWN', verdicts={}))
    write(root / 'results/funnel/final_D_retry/D/tic1_p01.json', dict(status='COMPLETE', packet='docs/packets/audit_p12/tic1_P2.5000',
                                                                     verdicts={'p12.0': dict(verdict='SUBMIT')}))
    tiers = dict(verdict='SUBMIT', deciding_condition=None, candidate_tier=dict(candidate_tier=2), validation_status='candidate',
                 conditions=dict(K0=dict(fired=False), H5=dict(fired=False)), not_measurable=['K9'], flags=dict(F7='SPOC TCE x'))
    write(data / 'funnel/final/cases/tic1_p01/stageD/tic1_P2.5000.json',
          dict(tiers=tiers, fit=dict(adopted=dict(period=2.5, period_err=1e-5, t0_btjd=3000.0, t0_err=1e-3, t14_hours=1.2))))
    return repo, root, CL, NL, AU


def test_candidate_list_prefers_the_completed_retry_and_labels_every_row(tmp_path, monkeypatch):
    repo, root, CL, NL, AU = tree(tmp_path, monkeypatch)
    rows = CL.build()
    by = {(r['tic_id'], r.get('candidate_id')): r for r in rows}
    assert by[(1, 'tic1_p01')]['verdict'] == 'SUBMIT tier 2' and by[(1, 'tic1_p01')]['packet']
    assert by[(1, 'tic1_p02')]['verdict'].startswith('REJECT_S')
    assert by[(2, None)]['verdict'] == 'NO_ACCEPTED_SIGNAL'
    assert by[(3, None)]['verdict'] == 'UNKNOWN'
    assert by[(9, None)]['verdict'] == 'INPUT_INELIGIBLE'
    assert by[(1, 'tic1_p01')]['fit_period_err'] == 1e-5
    summary = read(root / 'results/candidates_p12_summary.json')
    assert summary['by_verdict']['SUBMIT tier 2'] == 1


def test_natural_load_groups_and_counts(tmp_path, monkeypatch):
    repo, root, CL, NL, AU = tree(tmp_path, monkeypatch)
    result = NL.build()
    g = result['groups']
    assert g['p8_2000']['totals']['pregate'] == 2 and g['p8_2000']['totals']['A'] == 2 and g['p8_2000']['totals']['S'] == 1
    assert g['p8_2000']['totals']['B'] == 1 and g['p8_2000']['totals']['C_pass'] == 1
    assert g['p10_436']['searched_complete'] == 1 and g['E1']['unknown'] == 1


def test_audit_page_one_orders_the_list_and_states_the_bar(tmp_path, monkeypatch):
    repo, root, CL, NL, AU = tree(tmp_path, monkeypatch)
    CL.build()
    clause = lambda name, n, decisive, holds, printed: dict(clause=name, number=0, N=n, wilson95=[0, .2], threshold='x',
                                                            decisive=decisive, holds=holds, printed=printed)
    write(root / 'results/part4/launch_bar.json', dict(bar_met=False, clauses=[clause('LB1a', 1, False, None, 'NOT MEASURED'),
          clause('LB2a', 13, True, True, 'HOLDS')], failing=[], not_decisive=['LB1a'], what_N_can_detect='x', adjacent_LB1c=None))
    write(root / 'results/closing_sentence.json', dict(sentence='The registered P12 work on these inputs is complete; X.'))
    (repo / 'docs').mkdir(exist_ok=True)
    state = AU.build()
    text = (repo / 'docs/AUDIT_P12.md').read_text(encoding='utf-8')
    lines = text.splitlines()
    assert lines[0].startswith('# AUDIT_P12. Final state: STOPPED_') and 'provisional' in lines[0]
    assert lines[1].startswith('Launch bar not met: clause LB1a') and 'submission is not recommended' in lines[2]
    assert 'Tier 2: pixel-supported candidates' in text and '| 1 | 2.50000 |' in text
    assert 'validated planet' in text and 'The registered P12 work' in text
    for word in ('discovered', 'confirmed'):
        assert word not in text.lower().replace('not confirmed', '').replace('confirmation', '')
