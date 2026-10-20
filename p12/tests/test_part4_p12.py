"""Parts 3 to 6 modules: the held-out harness edits, the superseded D modules, the planners' pure rules, the
launch bar, the reports' rules. Synthetic inputs only, except the read-only P9 raw input index (not truth)."""
import csv
import hashlib
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from p12_common import REPO, ROOT, read, write, sha

P12 = Path(__file__).resolve().parents[1]
for extra in (P12 / 'work/dev/supersede', P12 / 'work/dev'):
    if extra.is_dir() and str(extra) not in sys.path:
        sys.path.append(str(extra))
HELDOUT = P12 / 'heldout' if (P12 / 'heldout/runner.py').exists() else P12 / 'work/dev/heldout'
if str(HELDOUT) not in sys.path:
    sys.path.insert(0, str(HELDOUT))

import common as HC
import runner as HR
import scoring as HS
import metrics as HM


# --- harness edit (6): the harness's own input selection ---------------------------------------------------

def test_selection_applies_the_frozen_sector_policy():
    chosen = HC.select_products(172421004)
    sectors = [p['sector'] for p in chosen['selected']]
    assert all(56 <= s <= 105 for s in sectors)
    assert any('s1751' in d['file'] and 'outside' in d['reason'] for d in chosen['dropped'])
    policy = read(REPO / 'p10/part3/manifests/sector_policy_effective.json')
    assert not any(p['author'] == 'QLP' and p['sector'] in policy['excluded_qlp'] for p in chosen['selected'])
    assert len(set(sectors)) == len(sectors)


def test_selection_prefers_spoc_then_tess_spoc_then_qlp():
    chosen = HC.select_products(239275865)
    by_sector = {p['sector']: p['author'] for p in chosen['selected']}
    assert by_sector[74] == 'SPOC'
    assert all(d['reason'] for d in chosen['dropped'])


# --- harness edits (3), (4), (5), (8) -------------------------------------------------------------------------

def test_routes_replace_the_requirements_table():
    forced, normal = HR.REQUIREMENTS['negatives'], HR.REQUIREMENTS['normal']
    assert forced['C'] == [('stageA', 'decision', {'PASS'})]
    assert normal['C'] == [('stageB', 'decision', {'PASS'})]
    assert forced['D'] == normal['D'] == [('stageC', 'decision', {'PASS', 'UNRESOLVED'})]
    assert HR.DEADLINES['C'] == 12240 and HR.DEADLINES['C_retry'] == 36000 and HR.DEADLINES['D'] == 5400
    assert HR.WORKERS['search'] == HR.WORKERS['A'] == 4 and HR.WORKERS['C'] == HR.WORKERS['D'] == 2


def test_boundary_allows_p12_outputs_and_blocks_truth():
    assert HR.blocked(REPO / 'p9/truth/final_truth.csv')
    assert HR.blocked(REPO / 'data/survey/audit_lc/tic1/index.json')
    assert HR.blocked(REPO / 'docs/packets/audit_p8/x.md')
    assert not HR.blocked(REPO / 'data/survey/p12/heldout/lightkurve/x.fits')
    assert not HR.blocked(REPO / 'docs/packets/audit_p12/neg_p9/k/packet.md')
    assert not HR.blocked(REPO / 'p9/inputs/raw/tic1/index.json')


def test_dispatch_copy_refuses():
    import dispatch
    with pytest.raises(SystemExit):
        dispatch.main()


# --- harness edit (7): scoring -------------------------------------------------------------------------------

def test_match_signal_is_the_p9_matcher():
    sys.path.insert(0, str(REPO / 'p9'))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('p9_scoring_original', REPO / 'p9/scoring.py')
        original = importlib.util.module_from_spec(spec)
        sys.modules['common_p9_shadow'] = original
        source = (REPO / 'p9/scoring.py').read_text(encoding='utf-8')
        start = source.index('def observed_centers'); end = source.index('def wilson')
        namespace = dict(np=np, math=__import__('math'))
        exec(source[start:end], namespace)
    finally:
        sys.path.remove(str(REPO / 'p9'))
    t = np.arange(0, 60, 200 / 86400)
    truth = dict(period=3.0, epoch_btjd=1.2, duration_hours=2.0)
    for cand in (dict(period=3.0, t0=1.21, duration=0.08), dict(period=6.0, t0=1.2, duration=0.08), dict(period=3.1, t0=1.2, duration=0.08)):
        for ratio in (1, 2, 0.5):
            assert HS.match_signal(t, truth, cand, ratio) == namespace['match_signal'](t, truth, cand, ratio)


def test_negative_tables_count_end_to_end_and_at_d():
    scored = []
    for i in range(13):
        fam = [dict(candidate_key=f'k{i}', D_submit=(i == 0))]
        at_d = [dict(key=f'k{i}', reached_D=i < 6, submit_equivalent=i in (0, 1))]
        scored.append(dict(truth_id=f'n{i}', tic_id=i, label='negative', subtype='EB', eligibility='eligible',
                           negative_family_traces=fam, negative_family_gates={g: False for g in HS.GATES},
                           negative_family_at_D=at_d))
    table = HM.negatives(scored)
    assert table['LB2a']['number'] == 1 and table['LB2a']['N'] == 13 and table['LB2a']['holds']
    assert table['LB2b']['N'] == 6 and table['LB2b']['number'] == 2 and table['LB2b']['decisive'] and not table['LB2b']['holds']


# --- superseded D worker, pixels, plan check -----------------------------------------------------------------

def _worker():
    import importlib
    import stage_d_worker_p12 as W
    return W


def _runtime(**kw):
    base = dict(phase='final_D', redact_catalogue=False, product_source='policy', route='normal', rules=['p12.0'])
    base.update(kw)
    return base


def test_d_worker_registers_the_heldout_source_and_the_assisted_route():
    W = _worker()
    W.refuse(_runtime(phase='neg_p9_D', product_source='heldout', redact_catalogue=True, route='forced_negatives'))
    W.refuse(_runtime(phase='bar_p9_eph', product_source='heldout', route='ephemeris_assisted'))
    with pytest.raises(RuntimeError):
        W.refuse(_runtime(product_source='heldout'))
    with pytest.raises(RuntimeError):
        W.refuse(_runtime(phase='neg_p9_D', product_source='heldout', route='ephemeris_assisted'))
    with pytest.raises(RuntimeError):
        W.refuse(_runtime(redact_catalogue=True))


def test_bounded_gaia_query_abandons_a_stalled_call():
    import stage_d_pixels_p12 as P
    if not hasattr(P, '_bounded'):
        pytest.skip('superseding pixels module not installed on this path')
    started = time.perf_counter()
    with pytest.raises(TimeoutError):
        P._bounded(lambda: time.sleep(30), 0.2)
    assert time.perf_counter() - started < 5
    assert P._bounded(lambda: 7, 1.0) == 7
    with pytest.raises(ValueError):
        P._bounded(lambda: (_ for _ in ()).throw(ValueError('x')), 1.0)


def test_gaia_positions_falls_back_from_the_row_cap(tmp_path, monkeypatch):
    import stage_d_pixels_p12 as P
    if not hasattr(P, 'GAIA_SYNC_ROW_CAP'):
        pytest.skip('superseding pixels module not installed on this path')
    from astropy.table import Table

    class Job:
        def __init__(self, n):
            self.n = n

        def get_results(self):
            return Table(dict(source_id=np.arange(self.n), ra=np.zeros(self.n), dec=np.zeros(self.n), pmra=np.zeros(self.n),
                              pmdec=np.zeros(self.n), phot_g_mean_mag=np.ones(self.n), phot_rp_mean_mag=np.ones(self.n)))

    class FakeGaia:
        @staticmethod
        def launch_job(query, dump_to_file=False):
            return Job(P.GAIA_SYNC_ROW_CAP)

        @staticmethod
        def launch_job_async(query, dump_to_file=False):
            return Job(3)
    import types
    monkeypatch.setitem(sys.modules, 'astroquery.gaia', types.SimpleNamespace(Gaia=FakeGaia))
    record = P.gaia_positions(10.0, 20.0, tmp_path / 'g.json')
    assert len(record['objects']) == 3
    assert [a['status'] for a in record['attempts']] == ['ROW_CAP', 'COMPLETE']


def test_plumbing_updates_apply_only_to_live_measurements(tmp_path, monkeypatch):
    import stage_d_plan_p12 as S
    if not hasattr(S, '_expectations'):
        pytest.skip('superseding plan module not installed on this path')
    path = tmp_path / 'updates.json'
    monkeypatch.setattr(S, 'UPDATES', path)
    write(path, dict(updates=[dict(key='tic144277542_P12.9812', rules='p10.0', original=['SUBMIT', None], cause_class='LIVE_MEASUREMENT',
                                   observed=dict(verdict='KILL', deciding='K9', fired=['K9']))]))
    expected, updates = S._expectations()
    assert expected['tic144277542_P12.9812']['p10.0'][:2] == ('KILL', 'K9')
    write(path, dict(updates=[dict(key='tic144277542_P12.9812', rules='p10.0', original=['SUBMIT', None], cause_class='DEFECT',
                                   observed=dict(verdict='KILL', deciding='K9'))]), replace=True)
    with pytest.raises(RuntimeError):
        S._expectations()


# --- ledger pricing ------------------------------------------------------------------------------------------

def test_ledger_kinds_and_worker_scaling(tmp_path, monkeypatch):
    import ledger_p12 as L
    assert L._job_kind('bar_p9_eph', [dict(arguments=['p12/protocol/ephemeris_assisted_p12.py', 'run'])]) == 'D'
    assert L._job_kind('final_novelty', [dict(arguments=['p12/protocol/novelty_p12.py', '--online'])]) == 'novelty'
    root = tmp_path / 'p12'
    (root / 'manifests').mkdir(parents=True)
    forecast = read(ROOT / 'manifests/forecast_p12.json')
    write(root / 'manifests/forecast_p12.json', dict(unit_costs=forecast['unit_costs'], forecast_margin=1.25, phases={}))
    write(root / 'manifests/phase_sequence.json', dict(phases=[dict(name='neg_p9_A', workers=4), dict(name='neg_tenk_neighbours', workers=2)]))
    jobs = root / 'manifests/jobs.json'
    write(jobs, [dict(job_id=f'j{i}', arguments=['p12/protocol/funnel_stage_p12.py', 'A']) for i in range(10)])
    monkeypatch.setattr(L, 'ROOT', root)
    row = L.price_phase('neg_p9_A', jobs)
    assert row['kind'] == 'A' and row['base_queue_hours'] == pytest.approx(15.5 * 24 * 3 / 3600)  # 10 jobs, 4 workers: 3 rounds
    write(root / 'manifests/phase_sequence.json', dict(phases=[dict(name='plumbing_d_rerun', workers=2), dict(name='neg_tenk_neighbours', workers=2)]), replace=True)
    write(jobs, [dict(job_id='k', arguments=['p12/protocol/stage_d_worker_p12.py', 'r'])], replace=True)
    assert L.price_phase('plumbing_d_rerun', jobs)['base_queue_hours'] == pytest.approx(7.5 * 2 / 60)  # one job alone: its own wall
    write(root / 'manifests/phase_sequence.json', dict(phases=[dict(name='neg_tenk_neighbours', workers=2)]), replace=True)
    write(jobs, [dict(job_id='n', arguments=['p12/protocol/neighbours_set_p12.py', 'e1'], stars=1000)], replace=True)
    row = L.price_phase('neg_tenk_neighbours', jobs)
    assert row['kind'] == 'neighbours' and row['base_queue_hours'] == pytest.approx(1000 * 16.5 * 60 * 2 / 2000 / 3600)


def test_scorer_recognises_set_prefixed_false_alarm_jobs():
    import re
    source = (Path(sys.modules['ledger_p12'].__file__).parent / 'score_injections_p12.py').read_text(encoding='utf-8')
    if '(?:[a-z]+_)?tic' not in source:
        pytest.skip('superseding scorer not installed on this path')
    assert re.fullmatch(r'(?:[a-z]+_)?tic\d+', 'extfa_tic123') and re.fullmatch(r'(?:[a-z]+_)?tic\d+', 'tic5')
    assert not re.fullmatch(r'(?:[a-z]+_)?tic\d+', 'ext00001_tic5')


# --- planners, launch bar, reports ---------------------------------------------------------------------------

def test_ttt_family_ratios():
    import report_ttt_p12 as T
    assert T.family(4.0, 2.0) == 2 and T.family(2.0, 2.0) == 1 and T.family(1.0, 3.0) == pytest.approx(1 / 3)
    assert T.family(2.05, 2.0) is None and T.family(2.019, 2.0) == 1


def test_extension_sample_is_ordered_by_the_registered_hash():
    tics = [5, 17, 300, 12345]
    order = sorted(tics, key=lambda t: hashlib.sha256(f'20260920:ext_cal:{t}'.encode()).hexdigest())
    assert order == sorted(tics, key=lambda t: hashlib.sha256(('20260920:ext_cal:' + str(t)).encode()).hexdigest())


def test_injection_spec_copy_writes_two_per_star(tmp_path):
    import subprocess
    script = next(p for p in (P12 / 'protocol/make_injection_spec_p12.py', P12 / 'work/dev/make_injection_spec_p12.py') if p.exists())
    sample = tmp_path / 's.csv'
    with sample.open('w', newline='') as stream:
        w = csv.DictWriter(stream, fieldnames=['tic_id', 'radius_rsun', 'mass_msun', 'teff_k', 'tmag', 'ra_deg', 'dec_deg'])
        w.writeheader()
        for t in (11, 22, 33):
            w.writerow(dict(tic_id=t, radius_rsun=0.4, mass_msun=0.4, teff_k=3400, tmag=13, ra_deg=1, dec_deg=2))
    spec = tmp_path / 'injections_x.csv'
    subprocess.run([sys.executable, str(script), '--sample', str(sample), '--n-stars', '3', '--per-star', '2', '--seed', '20260920',
                    '--rp-earth-min', '1', '--rp-earth-max', '4', '--period-bins', '0.5,30,4', '--sample-out', str(tmp_path / 'o.csv'),
                    '--spec-out', str(spec)], check=True, capture_output=True, cwd=REPO)
    rows = list(csv.DictReader(spec.open()))
    assert len(rows) == 6 and all(r['job_id'].startswith('ext') for r in rows)
    assert all(1 <= float(r['rp_earth']) <= 4 and 0.5 <= float(r['period']) <= 30 for r in rows)


def test_launch_bar_rule(tmp_path, monkeypatch):
    import launch_bar_p12 as B
    part4 = tmp_path / 'p12/results/part4'
    part4.mkdir(parents=True)
    clause = lambda name, number, n, decisive, holds: dict(clause=name, number=number, N=n, wilson95=[0, .1], threshold='x', decisive=decisive, holds=holds)
    write(part4 / 'ttt_table.json', dict(clauses=dict(LB1a=clause('LB1a', 0, 1, False, None), LB1b=clause('LB1b', 0, 0, False, None))))
    write(part4 / 'p9_negatives_table.json', dict(LB2a=clause('LB2a', 0, 13, True, True), LB2b=clause('LB2b', 0, 2, False, None)))
    write(part4 / 'p9_positives_table.json', dict(ephemeris_assisted=dict(LB3=clause('LB3', 0, 6, True, True))))
    monkeypatch.setattr(B, 'ROOT', tmp_path / 'p12')
    monkeypatch.setattr(B, 'lb4', lambda: dict(clause='LB4', number=0.95, N=100, threshold='>= 0.90', decisive=True, holds=True))
    result = B.build()
    assert result['bar_met'] is False and 'LB1a' in result['not_decisive'] and not result['failing']
    printed = {c['clause']: c['printed'] for c in result['clauses']}
    assert printed['LB1a'] == 'NOT MEASURED' and printed['LB2a'] == 'HOLDS' and printed['LB4'] == 'HOLDS'


def test_audit_state_and_transit_windows():
    import report_audit_p12 as R
    good = dict(freeze_exists=True, freeze_predates_every_launch=True, final_search_closed=True, every_B_passer_has_C=True,
                every_C_case_has_D=True, integrity_entry_zero=True, integrity_final_zero=True, routine_disabled_verified=True)
    assert R.state(dict(good, bar_met=False)) == 'FINAL_SEARCH_DELIVERED_BAR_NOT_MET'
    assert R.state(dict(good, bar_met=True)) == 'FINAL_SEARCH_DELIVERED_BAR_MET'
    assert R.state(dict(good, integrity_final_zero=False)) == 'STOPPED_AFTER_FINAL_SEARCH_INCOMPLETE'
    assert R.state(dict(good, final_search_closed=False, integrity_final_zero=None)) == 'STOPPED_BEFORE_FINAL_SEARCH'
    row = dict(fit_period='2.0', fit_t0_btjd='3000.0', fit_t14_hours='2.4', fit_period_err='1e-5', fit_t0_err='1e-3')
    assert R._next_transits(row, 3100.1).count('BTJD') == 3
    assert 'exceeds' in R._next_transits(dict(row, fit_period_err='0.1'), 3100.1)


def test_readiness_names_every_script_of_a_row():
    import readiness_p12 as G
    row = dict(script='p12/protocol/a.py', planner=dict(script='p12/heldout/runner.py', args=['plan', 'p12/protocol/b.py']))
    assert G._named(row) == ['p12/protocol/a.py', 'p12/heldout/runner.py', 'p12/protocol/b.py']


def test_c_routes_follow_the_registered_upstream():
    import stage_c_worker_p12 as C
    a = lambda d: dict(status='COMPLETE', measurement=dict(decision=d))
    s = lambda g: dict(status='COMPLETE', measurement=dict(gate=g))
    C.validate_upstream('injection_sample', dict(A=a('PASS'), S=s('HOLD')))
    C.validate_upstream('forced_negatives', dict(A=a('PASS'), S=s('FAIL'), B=a('FAIL')))
    C.validate_upstream('normal', dict(A=a('PASS'), S=s('PASS'), B=a('PASS')))
    for route, upstream in (('normal', dict(A=a('PASS'), S=s('PASS'))), ('injection_sample', dict(A=a('PASS'), S=s('FAIL'))),
                            ('forced_negatives', dict(A=a('FAIL'))), ('other', dict(A=a('PASS')))):
        with pytest.raises(RuntimeError):
            C.validate_upstream(route, upstream)
