"""The measured P8 selection, its boundaries, and unchanged legacy defaults."""
import json

import numpy as np
import pytest

from tesshunter import audit_rules as R, audit_prep, event_vet, secondary, star_vet


def test_frozen_p8_selection_and_version():
    rules = R.P8_RULES
    assert rules.version == 'p8.0'
    assert rules == R.DEFAULT_RULES.with_options(exact_t14_record=True)
    assert rules.secondary_gate == 'bound'
    assert rules.transit_masked_detrend and rules.inflated_depth_consistency
    assert rules.depth_consistency_errors == 'inflated'
    assert rules.depth_consistency_p_min == 1e-3 and rules.beta_max == 5.0
    assert R.LEGACY_RULES.version == 'p6.2' and R.DEFAULT_RULES.version == 'p7.0'
    assert R.RULES_VERSION == 'p7.0'
    assert rules.with_options(beta_max=3).version == 'p8.0-partial'


def test_p8_depth_threshold_passes_at_boundary_and_fails_just_below():
    threshold = R.P8_RULES.depth_consistency_p_min
    stats = {'n': 5, 'snr': 10.0, 'top_event_share_of_snr2': 0.3,
             'snr_without_top_event': 8.0, 'weighted_mean_depth_ppt': 1.0,
             'p_const': threshold, 'err_ppt': 0.1}
    assert event_vet.stagea_criteria(stats, 1.0, p_min=threshold)['all_passed']
    stats['p_const'] = np.nextafter(threshold, 0.0)
    assert not event_vet.stagea_criteria(stats, 1.0, p_min=threshold)['all_passed']


def test_p8_reads_inflated_errors_and_retains_both_p_values():
    events = [{'n': i, 'sector': 1, 'det_depth_ppt': depth, 'det_depth_err_ppt': 0.2}
              for i, depth in enumerate([1.0, 3.0, 1.0, 3.0])]
    stats = event_vet.kept_event_stats(events, 'det', {1: R.P8_RULES.beta_max},
                                     gate_errors=R.P8_RULES.depth_consistency_errors)
    assert stats['p_const'] == stats['p_const_inflated']
    assert stats['p_const_white'] < R.P8_RULES.depth_consistency_p_min < stats['p_const']


def test_p8_bound_gate_passes_at_three_sigma_and_fails_just_above_on_a_variable_scan():
    def gate(depth):
        return secondary.apply_gate(depth, 0.25, 0.25, 50, True,
                                    R.P8_RULES.secondary_gate, R.P8_RULES.secondary_quiet_max_dips)['gate']
    assert gate(1.0) == 'PASS'
    assert gate(np.nextafter(1.0, np.inf)) == 'FAIL'


@pytest.mark.parametrize('duration,clipped', [(0.38, False), (0.5, True)])
def test_p8_beta_cap_on_correlated_flux(duration, clipped):
    t = np.arange(4000) * 200.0 / 86400.0
    flux = 1.0 + np.repeat([-0.001, 0.001], 2000)
    sectors = np.ones(len(t), dtype=int)
    in_transit = np.zeros(len(t), dtype=bool)
    raw = event_vet.sector_beta(t, flux, sectors, in_transit, duration, {1: 200.0}, beta_max=100.0)[1]
    selected = event_vet.sector_beta(t, flux, sectors, in_transit, duration, {1: 200.0},
                                    beta_max=R.P8_RULES.beta_max)[1]
    assert (raw > R.P8_RULES.beta_max) == clipped
    assert selected == (R.P8_RULES.beta_max if clipped else raw)


def test_p8_mask_excludes_the_boundary_and_includes_points_just_inside():
    assert R.P8_RULES.transit_masked_detrend
    edge = R.MASK_DURATIONS_EITHER_SIDE * 0.125
    points = np.array([-edge, -edge + 1e-9, edge - 1e-9, edge, edge + 1e-9])
    assert audit_prep.transit_mask(points, 2.0, 0.0, 0.125).tolist() == [False, True, True, False, False]


def test_p8_stage_b_window_survives_json_without_rounding():
    t14 = 1.23456789123
    record = star_vet.phase_independent_test([], 5.0, 1.0, t14, exact=R.P8_RULES.exact_t14_record)
    restored = json.loads(json.dumps(record))
    assert restored['t14_hours'] == t14 and restored['window_days'] == t14 / 24.0
    legacy = star_vet.phase_independent_test([], 5.0, 1.0, t14)
    assert legacy['t14_hours'] == round(t14, 3) and legacy['window_days'] == round(t14 / 24.0, 5)
