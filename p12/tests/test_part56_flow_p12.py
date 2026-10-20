"""Part 4e, 5c and 6 generators on synthetic trees: specificity page, completeness page, handoff, final collect/stage."""
import csv
import json
import sys
from pathlib import Path

import pytest

from p12_common import write, read, sha

P12 = Path(__file__).resolve().parents[1]
if (P12 / 'work/dev').is_dir() and str(P12 / 'work/dev') not in sys.path:
    sys.path.append(str(P12 / 'work/dev'))
CONFIG = read(P12 / 'protocol/config.json')


def _patch(monkeypatch, modules, repo):
    for module in modules:
        for name, value in (('REPO', repo), ('ROOT', repo / 'p12'), ('DATA', repo / 'data/survey/p12')):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)


def _clause(name, number, n, decisive, holds):
    return dict(clause=name, number=number, N=n, wilson95=[0.0, 0.3], threshold='x', decisive=decisive, holds=holds)


def test_specificity_page_writes_every_section(tmp_path, monkeypatch):
    import plan_part2_p12 as P2
    import report_specificity_p12 as S
    repo = tmp_path
    root = repo / 'p12'
    _patch(monkeypatch, (P2, S), repo)
    rate = lambda k, n: dict(k=k, n=n, fraction=k / n if n else None, wilson95=[0.0, 0.5] if n else [None, None])
    write(root / 'results/part4/launch_bar.json', dict(bar_met=False, rule='r', what_N_can_detect='w',
          clauses=[dict(_clause('LB1a', 0, 1, False, None), printed='NOT MEASURED')]))
    table = dict(targets=1, N1=1, N1_D=0, stars_reaching_of_N1={'A': rate(1, 1)}, candidate_counts={'A': 2}, reached_D=[], stars=[])
    write(root / 'results/part4/ttt_table.json', table)
    write(root / 'results/part4/p9_negatives_table.json', dict(LB2a=_clause('LB2a', 0, 13, True, True),
          LB2b=_clause('LB2b', 0, 2, False, None), rows=[dict(tic_id=5, at_D=[dict(key='k', verdict='KILL', fired=['K8'])])]))
    write(root / 'results/part4/p9_positives_table.json', dict(blind=dict(n_D=0, n_signals=13),
          ephemeris_assisted=dict(n_fit=6, LB3=_clause('LB3', 0, 6, True, True))))
    write(root / 'results/part2/photometry_decision.json', dict(decision='KEEP_ARCHIVAL'))
    write(root / 'results/funnel/cal_archival/C_closure_neg_fa_C.json', dict(rows=[dict(candidate_id='fa_tic7_p01', tic_id=7, decision='PASS')]))
    write(root / 'results/funnel/neg_fa_D/D/fa_tic7_p01.json', dict(status='COMPLETE', verdicts={'p12.0': dict(verdict='HOLD', deciding_condition='H5')}))
    sidecar = repo / 'data/survey/p12/catalogs/spoc_tce/spoc_tce.ephemerides.csv'
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text('tceid,ticid,tce_period,tce_depth\n1,5,2.0,300\n')
    write(root / 'manifests/sidecar_p12.json', dict(path=sidecar.relative_to(repo).as_posix()))
    S.build()
    text = (root / 'results/SPECIFICITY_P12.md').read_text(encoding='utf-8')
    for part in ('## The launch bar', 'Set (i)', 'LB2a 0 / 13', 'Ephemeris-assisted (LB3', 'natural load', 'Zero-compute'):
        assert part in text
    assert read(root / 'results/part4/fa_natural_table.json')['counts']['HOLD'] == 1


def test_completeness_page_and_closing_sentence(tmp_path, monkeypatch):
    import report_completeness_p12 as R
    repo = tmp_path
    root = repo / 'p12'
    _patch(monkeypatch, (R,), repo)
    write(root / 'protocol/config.json', CONFIG)
    bins = lambda edges: [dict(bin=list(e), n=10, recovered=5, through_S=4, whole=3) for e in edges]
    write(root / 'results/part2/photometry_decision.json', dict(decision='KEEP_ARCHIVAL'))
    write(root / 'results/part2/COMPLETENESS_ARM_A.json', dict(levels=[dict(level='search only', through=5, n=10, logistic=None)],
          policy_loss=dict(level='policy loss', n=3, of_total=13), tables=dict(radius=bins(CONFIG['completeness']['radius_bins_re']),
          period=bins(CONFIG['completeness']['period_bins_days']), tmag=bins(CONFIG['completeness']['tmag_bins']), rotation=[]),
          C_retention_30_sample=dict(PASS=20), false_alarms=dict(per_star=dict(A=0.1))))
    write(root / 'results/part4/launch_bar.json', dict(clauses=[dict(clause='LB3', decisive=True)]))
    close = R.build()
    text = (root / 'results/COMPLETENESS_P12.md').read_text(encoding='utf-8')
    assert R.SCOPE in text and 'At radius 1 to 1.41 Re' in text and 'The registered P12 work on these inputs is complete' in text
    assert close['items'] == ['pixel-level photometry, the only untested input change with a measured noise lever'] or len(close['items']) >= 1


def test_final_collect_and_stage_planners(tmp_path, monkeypatch):
    import plan_part2_p12 as P2
    import plan_part5_p12 as P5
    repo = tmp_path
    root, data = repo / 'p12', repo / 'data/survey/p12'
    _patch(monkeypatch, (P2, P5), repo)
    monkeypatch.setattr(P5, 'E1', root / 'manifests/targets_ext_E1.csv')
    monkeypatch.setattr(P5, 'E1_STARS', root / 'manifests/part5/e1_targets.csv')
    monkeypatch.setattr(P2, '_sources', lambda: {})
    monkeypatch.setattr(P2, '_stars', lambda: {1: dict(radius_rsun=0.3, mass_msun=0.3, teff_k=3300.0, tmag=13.0, ra_deg=1.0, dec_deg=2.0)})
    monkeypatch.setattr(P2, '_write_jobs', lambda phase, jobs: write(root / f'manifests/{phase}_jobs.json', jobs) or root / f'manifests/{phase}_jobs.json')
    write(root / 'manifests/decision_point_1.json', dict(tier='CORE'))
    write(root / 'manifests/eligibility_p12.json', dict(per_star={'1': dict(status='INPUT_ELIGIBLE')}))
    write(root / 'results/part2/photometry_decision.json', dict(decision='KEEP_ARCHIVAL'))
    planet = dict(planet_num=1, search='s', period_days=2.5, epoch_btjd=3000.0, duration_days=0.05, depth_ppt=2.0, snr=12.0,
                  n_transits_observed=9, stitch_snr=10.0, stitch_n_transits=9, stitch_epoch_consistent=True)
    result = repo / 'data/survey/p12/final/runs/survey_p10/results/tic1.json'
    write(result, dict(status='ok', tic_id=1, result=dict(planets=[planet, dict(planet, planet_num=2, stitch_snr=3.0)])))
    lock = root / 'manifests/final_predictions_lock.json'
    write(lock, dict(jobs=[dict(job_id='tic1', tic_id=1, status='COMPLETE', result_path=result.relative_to(repo).as_posix(), accepted=[])]))
    write(root / 'manifests/final_predictions_lock_seal.json', dict(sha256=sha(lock)))
    collected = P5.collect()
    assert collected['counts'] == dict(stars_complete=1, unknown=0, accepted=2, pregate=1)
    runtime = read(repo / collected['cases'][0]['runtime'])
    assert runtime['population_tier'] == 'core' and runtime['products'] == dict(kind='policy', arm='archival')
    assert (data / 'final/funnel/survivors.csv').exists()
    P5.stage('A', 'final_A')
    jobs = read(root / 'manifests/final_A_jobs.json')
    assert [j['job_id'] for j in jobs] == ['tic1_p01'] and jobs[0]['arguments'][1] == 'A'


def test_extension_report_and_handoff(tmp_path, monkeypatch):
    import plan_part2_p12 as P2
    import report_extension_p12 as X
    import report_handoff_p12 as HF
    import report_audit_p12 as AU
    repo = tmp_path
    root = repo / 'p12'
    _patch(monkeypatch, (P2, X, HF, AU), repo)
    monkeypatch.setattr(X, 'OUTCOMES', root / 'results/part5/injection_outcomes_ext.csv')
    monkeypatch.setattr(HF, 'HANDOFF', repo / 'HANDOFF_P12.md')
    monkeypatch.setattr(AU, 'HANDOFF', repo / 'HANDOFF_P12.md')
    write(root / 'protocol/config.json', CONFIG)
    rows = [dict(job_id=f'ext{i:05d}_tic9', tic_id=9, status='recovered' if i < 3 else 'missed', snr_expected=10 + i, period=1.0 + i,
                 rp_earth=1.5, tmag=13.2) for i in range(6)]
    (root / 'results/part5').mkdir(parents=True)
    with X.OUTCOMES.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    cases = [dict(candidate_id=r['job_id'], kind='injection', pregate=True) for r in rows[:3]] + [dict(candidate_id='fa_tic9_p01', kind='false_alarm', pregate=True)]
    write(root / 'manifests/part5/ext_cal_cases.json', dict(cases=cases, counts=dict(false_alarm_accepted=4, unknown=0)))
    (root / 'manifests/part5/ext_cal_hosts.csv').write_text('tic_id\n9\n')
    for r in rows[:2]:
        write(root / f"results/funnel/ext_cal/A/{r['job_id']}.json", dict(status='COMPLETE', measurement=dict(decision='PASS')))
        write(root / f"results/funnel/ext_cal/S/{r['job_id']}.json", dict(status='COMPLETE', measurement=dict(gate='PASS')))
    result = X.build()
    assert result['n_injections'] == 6 and result['levels'][0]['through'] == 3 and result['levels'][-1]['through'] == 2
    assert (root / 'results/COMPLETENESS_EXT.md').exists()
    (root / 'manifests').mkdir(exist_ok=True)
    (root / 'manifests/exposure_ledger.jsonl').write_text('{"reader": "x"}\n')
    write(root / 'manifests/decision_point_1.json', dict(tier='E1', approved_utc='t'))
    (repo / 'HANDOFF_P12.md').write_text('# PART 1 CLOSED\nresume here: x\nkeep\n')
    state = HF.build()
    text = (repo / 'HANDOFF_P12.md').read_text(encoding='utf-8')
    assert text.startswith('# HANDOFF_P12. Final state: STOPPED_BEFORE_FINAL_SEARCH') and 'resume here' not in text and 'keep' in text
