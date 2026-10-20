import csv
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import rules_p12 as rules
from p12_common import REPO
from ledger_helper import ledger_once
from stats_p12 import wilson


def _modules():
    return rules._modules()


def test_sealed_p10_rederivation_reproduces_byte_for_byte_with_overlay_loaded(tmp_path):
    rules.install()
    sys.path[:0] = [str(REPO / 'scripts'), str(REPO / 'src')]
    import p10_tier_rederivation as H
    with (REPO / 'p10/results/tier_rederivation.csv').open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            root = 'data/survey/p8' if row['set'] == 'P8' else f"p9/results/blind/tic{row['tic_id']}"
            ledger_once(int(row['tic_id']), 'Part 1 test: seen record re-scored under p10.0 with the overlay', root,
                        'test_rules_p12 reproduction', row['set'])
    H.main(['--out', str(tmp_path)])
    for name in ('tier_rederivation.json', 'tier_rederivation.csv'):
        assert (tmp_path / name).read_bytes() == (REPO / 'p10/results' / name).read_bytes(), name


def _k8_fit(ratio):
    return {'adopted': {'rp_rearth': 2.0, 'b': 0.3, 'rp_rs': 0.05}, 'delta_chi2_prior_minus_free': 40.0,
            'uncertainty_issues': [], 'free_fit': {'rho_fit_cgs': ratio * 10.0}, 'stellar': {'rho_cgs': 10.0}}


@pytest.mark.parametrize('ratio,p10,p12', [(2.4, True, False), (2.49, True, False), (2.51, True, True), (0.49, True, True), (1.9, False, False)])
def test_a1_density_guard_fires_and_just_not_fires(ratio, p10, p12):
    R, T = _modules()
    assert T.k8_companion(_k8_fit(ratio))['fired'] is p10
    with rules.amended() as (Ra, Ta):
        assert Ta.k8_companion(_k8_fit(ratio))['fired'] is p12
    assert R.TIER_DENSITY_RATIO_RANGE == (0.5, 2.0)


@pytest.mark.parametrize('sigma,p10,p12', [(3.1, True, False), (3.49, True, False), (3.51, True, True), (2.9, False, False)])
def test_a2_odd_even_fires_and_just_not_fires(sigma, p10, p12):
    R, T = _modules()
    fit = {'odd_even': {'sigma': sigma, 'odd': {'n_transits': 16}, 'even': {'n_transits': 14}}}
    assert T.k6_odd_even(fit)['fired'] is p10
    with rules.amended() as (Ra, Ta):
        assert Ta.k6_odd_even(fit)['fired'] is p12
    assert R.TIER_ODD_EVEN_SIGMA == 3.0


def test_h5_and_h6_on_synthetic_inputs():
    one = {'K9': {'disagreement': [{'sector': 60, 'fired': True}, {'sector': 61, 'fired': False}, {'sector': 62, 'fired': None}]}}
    two = {'K9': {'disagreement': [{'sector': 60, 'fired': True}, {'sector': 61, 'fired': True}]}}
    none = {'K9': {'disagreement': [{'sector': 60, 'fired': None}]}}
    assert rules.h5(one)['fired'] is True and rules.h5(two)['fired'] is False and rules.h5(none)['fired'] is None
    assert rules.h6({'decision': 'UNRESOLVED'})['fired'] is True
    assert rules.h6({'decision': 'PASS'})['fired'] is False and rules.h6(None)['fired'] is None


def _centroid(err, shift, n=2):
    return {'centroid': {'per_sector': [dict(sector=56 + i, available=True, n_in=5, n_out=30, shift_err_px=err,
                                             total_shift_px=shift) for i in range(n)]}}


def test_a6_centroid_route_refuses_wide_region_and_capable_neighbour():
    far = {'gaia': {'neighbours': [dict(source_id=1, delta_mag=2.0, sep_px=3.0)]}}
    near = {'gaia': {'neighbours': [dict(source_id=2, delta_mag=2.0, sep_px=0.5)]}}
    faint_near = {'gaia': {'neighbours': [dict(source_id=3, delta_mag=12.0, sep_px=0.5)]}}
    wide = rules.centroid_support(_centroid(0.7, 0.1), far, 5.0)
    assert {r['status'] for r in wide['per_sector']} == {'target_consistent_unlocalised'} and wide['n_informative'] == 0
    blocked = rules.centroid_support(_centroid(0.2, 0.1), near, 5.0)
    assert blocked['n_informative'] == 0 and blocked['per_sector'][0]['capable_neighbours_in_region'] == [2]
    assert rules.centroid_support(_centroid(0.2, 0.1), far, 5.0)['n_informative'] == 2
    assert rules.centroid_support(_centroid(0.2, 0.1), faint_near, 5.0)['n_informative'] == 2
    offset = rules.centroid_support(_centroid(0.1, 0.5), far, 5.0)
    assert {r['status'] for r in offset['per_sector']} == {'offset'}


def _stagea(n_obs, n_exc, det, det_err, sap, sap_err, sectors):
    events = [dict(observed=True, excluded=False, sector=s) for s in sectors]
    return {'chosen_ephemeris': 'survey', 'per_ephemeris': {'survey': {
        'n_observed': n_obs, 'n_excluded': n_exc, 'events': events,
        'det_kept': {'weighted_mean_depth_ppt': det, 'err_ppt': det_err},
        'sap_kept': {'weighted_mean_depth_ppt': sap, 'err_ppt': sap_err}}}}


def test_k10_variants_fire_just_not_fire_and_not_measurable():
    v = rules.k10(_stagea(11, 8, 2.0, .1, 0.5, .1, [60, 61]))
    assert v['K10e']['fired'] is True and v['K10s']['fired'] is True
    assert rules.k10(_stagea(10, 5, 2.0, .1, 1.5, .1, [60, 61]))['K10e']['fired'] is False
    assert rules.k10(_stagea(3, 3, 2.0, .1, 0.5, .1, [60, 61]))['K10e']['fired'] is None
    assert rules.k10(_stagea(10, 1, 2.0, .1, 1.01, .1, [60, 61]))['K10s']['fired'] is False
    assert rules.k10(_stagea(10, 1, 2.0, .5, 0.5, .5, [60, 61]))['K10s']['fired'] is False
    assert rules.k10(_stagea(10, 1, 2.0, .1, 0.5, .1, [60]))['K10s']['fired'] is False
    assert rules.k10(_stagea(10, 1, 2.0, None, 0.5, .1, [60, 61]))['K10s']['fired'] is None
    both = rules.k10(_stagea(11, 8, 2.0, .1, 0.5, .1, [60, 61]))
    assert rules.k10_or(both, ['K10e']) is True and rules.k10_or(both, []) is None


def test_install_registers_p12_and_amendments_restore():
    R, T = _modules()
    receipt = rules.install()
    assert R.NAMED_RULES['p12.0'] is R.P10_RULES and len(receipt['install_hash']) == 64
    with rules.amended():
        assert R.TIER_DENSITY_RATIO_RANGE == (0.5, 2.5) and R.TIER_ODD_EVEN_SIGMA == 3.5
    assert R.TIER_DENSITY_RATIO_RANGE == (0.5, 2.0) and R.TIER_ODD_EVEN_SIGMA == 3.0


def test_historical_rule_sources_unchanged():
    # git's clean filter normalises line endings, so an unchanged checkout hashes to its HEAD blob.
    for name in ('src/tesshunter/verdict_tiers.py', 'src/tesshunter/audit_rules.py', 'scripts/p10_tier_rederivation.py'):
        working = subprocess.run(['git', 'hash-object', name], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
        head = subprocess.run(['git', 'rev-parse', 'HEAD:' + name], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
        assert working == head, name


def test_d_worker_refuses_unregistered_options():
    import stage_d_worker_p12 as D
    base = dict(phase='final_D', redact_catalogue=False, product_source='policy', route='normal', rules=['p12.0'])
    D.refuse(base)
    with pytest.raises(RuntimeError, match='neg_'):
        D.refuse(dict(base, redact_catalogue=True))
    D.refuse(dict(base, phase='neg_ttt_D', redact_catalogue=True, route='forced_negatives'))
    with pytest.raises(RuntimeError, match='plumbing_d'):
        D.refuse(dict(base, product_source='p8_store'))
    for phase in ('bar_p9_eph', 'neg_ttt_D', 'final_D'):
        with pytest.raises(RuntimeError, match='plumbing_d'):
            D.refuse(dict(base, phase=phase, product_source='p8_store'))
    D.refuse(dict(base, phase='plumbing_d', product_source='p8_store', rules=['p10.0', 'p12.0']))


def test_wilson_bounds_printed_beside_the_bar():
    assert round(wilson(0, 30)[1], 3) == 0.114 and round(wilson(1, 30)[1], 3) == 0.167
    assert round(wilson(0, 13)[1], 3) == 0.228 and round(wilson(0, 5)[1], 3) == 0.434
