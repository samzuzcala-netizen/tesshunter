"""Unit tests for ``tesshunter.star_vet``: the star-level tests, one test per rule.

The Stage B window test excludes a period only when BOTH its conditions hold -
the deepest transit-length window is shallower than depth/3 AND the noise of a
window mean is below depth/5 - so each is exercised on its own.  The long-period
test (prompt-7 option 4) is checked to apply only where Stage B (i) has no power.

Synthetic light curves in plain BTJD, as in ``tests/test_pipeline.py``.
"""

import numpy as np
import pytest

from tesshunter import audit_rules as R
from tesshunter.star_vet import (
    deep_event_hosts,
    deepest_window,
    gaia_flag_digest,
    long_period_window_test,
    phase_independent_test,
)


def _sector(sector=1, cadence_min=2.0, span_days=25.0, t_start=1000.0, noise_ppt=0.5,
            seed=1, author="SPOC", signals=()):
    rng = np.random.default_rng(seed)
    dt = cadence_min / 1440.0
    t = np.arange(t_start, t_start + span_days, dt)
    f = 1.0 + rng.normal(0, noise_ppt / 1000.0, len(t))
    for (period, t0, dur, depth_ppt) in signals:
        ph = ((t - t0 + 0.5 * period) % period) - 0.5 * period
        f[np.abs(ph) <= 0.5 * dur] -= depth_ppt / 1000.0
    return {"sector": sector, "author": author, "cadence_s": cadence_min * 60.0,
            "time": t, "flux": f}


# ── the deepest running window ───────────────────────────────────────────────

def test_deepest_window_finds_an_injected_dip_at_its_own_depth():
    s = _sector(signals=((5.0, 1002.0, 0.2, 8.0),), noise_ppt=0.2)
    w = deepest_window(s["time"], s["flux"], 0.2, s["cadence_s"] / 86400.0)
    assert w["deepest_depth_ppt"] == pytest.approx(8.0, rel=0.15)
    assert w["window_noise_ppt"] < 1.0


def test_deepest_window_of_a_flat_sector_is_consistent_with_noise():
    s = _sector(noise_ppt=0.5, seed=4)
    w = deepest_window(s["time"], s["flux"], 0.2, s["cadence_s"] / 86400.0)
    assert abs(w["deepest_depth_ppt"]) < 0.5


def test_deepest_window_returns_none_when_there_are_too_few_cadences():
    assert deepest_window(np.linspace(1000, 1001, 5), np.ones(5), 0.2, 0.01) is None


def test_deepest_window_requires_a_window_to_be_sixty_per_cent_full():
    s = _sector(span_days=2.0)
    # a window ten times longer than the sector can never be filled
    assert deepest_window(s["time"], s["flux"], 20.0, s["cadence_s"] / 86400.0) is None


# ── Stage B (i): the phase-independent test ──────────────────────────────────

def test_a_sensitive_sector_with_no_dip_excludes_the_period():
    s = _sector(span_days=25.0, noise_ppt=0.3)          # spans 5 periods of a 5 d candidate
    res = phase_independent_test([s], period=5.0, depth_ppt=10.0, t14_hours=4.8)
    assert res["sectors"][0]["tested"] is True
    assert res["sectors"][0]["excludes_period"] is True
    assert res["excluded"] is True
    assert res["excluding_sectors"] == [1]


def test_a_sector_that_shows_the_transit_does_not_exclude_the_period():
    s = _sector(span_days=25.0, noise_ppt=0.3, signals=((5.0, 1002.0, 0.2, 10.0),))
    res = phase_independent_test([s], period=5.0, depth_ppt=10.0, t14_hours=4.8)
    assert res["sectors"][0]["excludes_period"] is False
    assert res["excluded"] is False


def test_a_sector_too_noisy_to_see_the_depth_does_not_exclude_the_period():
    s = _sector(span_days=25.0, noise_ppt=60.0, seed=9)  # window noise above depth/5
    res = phase_independent_test([s], period=5.0, depth_ppt=1.0, t14_hours=4.8)
    row = res["sectors"][0]
    assert row["tested"] is True
    assert row["window_noise_ppt"] >= R.B_NOISE_FRAC * 1.0
    assert row["excludes_period"] is False
    assert res["excluded"] is False


def test_a_sector_slower_than_ten_minutes_is_not_tested():
    s = _sector(cadence_min=30.0, span_days=25.0)
    res = phase_independent_test([s], period=5.0, depth_ppt=10.0, t14_hours=4.8)
    assert res["sectors"][0]["tested"] is False
    assert "cadence" in res["sectors"][0]["why"]
    assert res["n_sectors_tested"] == 0


def test_a_sector_spanning_fewer_than_one_and_a_half_periods_is_not_tested():
    s = _sector(span_days=25.0)
    res = phase_independent_test([s], period=20.0, depth_ppt=10.0, t14_hours=4.8)
    assert res["sectors"][0]["tested"] is False
    assert "periods" in res["sectors"][0]["why"]


def test_one_excluding_sector_is_enough_even_when_another_shows_the_dip():
    a = _sector(sector=1, span_days=25.0, noise_ppt=0.3, signals=((5.0, 1002.0, 0.2, 10.0),))
    b = _sector(sector=2, span_days=25.0, t_start=1100.0, noise_ppt=0.3, seed=2)
    res = phase_independent_test([a, b], period=5.0, depth_ppt=10.0, t14_hours=4.8)
    assert res["n_sectors_excluding"] == 1
    assert res["excluded"] is True


def test_the_survey_duration_column_is_recorded_but_never_decides():
    s = _sector(span_days=25.0, noise_ppt=0.3, signals=((5.0, 1002.0, 0.05, 10.0),))
    res = phase_independent_test([s], period=5.0, depth_ppt=10.0, t14_hours=4.8,
                                 survey_duration_days=0.05)
    row = res["sectors"][0]
    assert row["deepest_depth_ppt_at_survey_duration"] > row["deepest_depth_ppt"]
    assert res["survey_duration_over_t14"] == pytest.approx(0.25)
    # the decision used the T14 column: a 1.2 h transit diluted into a 4.8 h window
    assert row["excludes_period"] is (row["deepest_depth_ppt"] < R.B_DEPTH_FRAC * 10.0)


# ── prompt-7 option 4: the long-period window test ───────────────────────────

def _ev(n, sector, excluded):
    return {"n": n, "tc_btjd": 1000.0 + n, "sector": sector, "observed": True,
            "excluded": excluded, "artefact_classes": ["pdc_gap"] if excluded else []}


def test_the_long_period_test_applies_only_where_stage_b_has_no_power():
    events = [_ev(0, 1, True), _ev(1, 2, True)]
    long_p = long_period_window_test(events, {1: 25.0, 2: 25.0}, period=60.0)
    assert long_p["applies"] is True
    short_p = long_period_window_test(events, {1: 25.0, 2: 25.0}, period=5.0)
    assert short_p["applies"] is False
    assert short_p["flag"] is False                       # never flags where Stage B can test


def test_a_candidate_removed_in_most_of_its_sectors_is_flagged_not_killed():
    events = [_ev(0, 1, True), _ev(1, 2, True), _ev(2, 3, True), _ev(3, 4, False)]
    res = long_period_window_test(events, {1: 25.0, 2: 25.0, 3: 25.0, 4: 25.0}, period=60.0)
    assert res["n_sectors_with_an_observed_epoch"] == 4
    assert res["n_sectors_with_every_observed_epoch_removed"] == 3
    assert res["fraction_of_sectors_fully_removed"] == pytest.approx(0.75)
    assert res["flag"] is True


def test_a_candidate_whose_epochs_mostly_survive_is_not_flagged():
    events = [_ev(0, 1, False), _ev(1, 2, False), _ev(2, 3, True)]
    res = long_period_window_test(events, {1: 25.0, 2: 25.0, 3: 25.0}, period=60.0)
    assert res["fraction_of_sectors_fully_removed"] == pytest.approx(1 / 3, abs=1e-3)
    assert res["flag"] is False


def test_a_sector_counts_as_fully_removed_only_when_every_epoch_in_it_went():
    events = [_ev(0, 1, True), _ev(1, 1, False), _ev(2, 2, True)]
    res = long_period_window_test(events, {1: 25.0, 2: 25.0}, period=60.0)
    per = {d["sector"]: d for d in res["per_sector"]}
    assert per[1]["all_removed"] is False and per[1]["n_observed"] == 2
    assert per[2]["all_removed"] is True


def test_unobserved_epochs_are_not_counted_by_the_long_period_test():
    events = [_ev(0, 1, True), {"n": 1, "observed": False, "reason": "no product covers the epoch"}]
    res = long_period_window_test(events, {1: 25.0}, period=60.0)
    assert res["n_sectors_with_an_observed_epoch"] == 1


# ── Stage B (iii): a deep accepted candidate on the same star ────────────────

def test_a_thirty_ppt_candidate_on_the_star_flags_a_binary_host():
    rows = [{"period_days": 2.0, "depth_ppt": 40.0, "verdict": "likely false positive"},
            {"period_days": 65.0, "depth_ppt": 1.5}]
    d = deep_event_hosts(rows, depth_ppt=1.5, period=65.0)
    assert d["flag"] is True
    assert d["n_deep"] == 1
    assert d["deepest_ppt"] == 40.0


def test_a_candidate_five_times_deeper_flags_even_below_thirty_ppt():
    rows = [{"period_days": 2.0, "depth_ppt": 6.0}, {"period_days": 65.0, "depth_ppt": 1.0}]
    assert deep_event_hosts(rows, depth_ppt=1.0, period=65.0)["flag"] is True
    assert deep_event_hosts(rows, depth_ppt=2.0, period=65.0)["flag"] is False   # 6 < 5 x 2


def test_the_candidate_itself_never_counts_as_its_own_deep_host():
    rows = [{"period_days": 65.0, "depth_ppt": 50.0}]
    d = deep_event_hosts(rows, depth_ppt=50.0, period=65.0)
    assert d["n_deep"] == 0
    assert d["flag"] is False


def test_deep_event_hosts_survives_an_unparsable_depth():
    rows = [{"period_days": 2.0, "depth_ppt": ""}, {"period_days": 3.0, "depth_ppt": 40.0}]
    assert deep_event_hosts(rows, depth_ppt=1.0, period=65.0)["n_deep"] == 1


# ── Stage B (ii): the Gaia / SIMBAD / VSX digest ─────────────────────────────

def _nb(**target):
    base = {"ruwe": 1.0, "ipd_frac_multi_peak": 0.0, "astrometric_excess_noise_sig": 0.5,
            "phot_variable_flag": "NOT_AVAILABLE", "non_single_star": 0, "duplicated_source": False,
            "best_class_name": None, "radial_velocity_error": None, "rv_nb_transits": None,
            "rv_amplitude_robust": None}
    base.update(target)
    return {"gaia": {"n_within_1arcmin": 3, "target_match": "tic_gaia_id", "target": base,
                     "n_neighbours_that_could_produce_depth_total_eclipse_within_63arcsec": 0},
            "simbad": {"objects": []}, "vsx": {"n_within_1arcmin": 0, "objects": []}}


def test_a_clean_star_raises_no_gaia_flag():
    assert gaia_flag_digest(_nb(), 2.0)["flags"] == []


def test_ruwe_above_one_point_four_flags_and_one_point_three_does_not():
    assert any("RUWE" in f for f in gaia_flag_digest(_nb(ruwe=1.5), 2.0)["flags"])
    assert gaia_flag_digest(_nb(ruwe=1.3), 2.0)["flags"] == []


def test_multi_peak_fraction_above_ten_per_cent_flags():
    assert any("multi_peak" in f for f in gaia_flag_digest(_nb(ipd_frac_multi_peak=12.0), 2.0)["flags"])
    assert gaia_flag_digest(_nb(ipd_frac_multi_peak=8.0), 2.0)["flags"] == []


def test_astrometric_excess_noise_significance_above_two_flags():
    assert any("excess_noise" in f for f in
               gaia_flag_digest(_nb(astrometric_excess_noise_sig=3.0), 2.0)["flags"])
    assert gaia_flag_digest(_nb(astrometric_excess_noise_sig=1.9), 2.0)["flags"] == []


def test_non_single_star_and_the_variable_flag_each_raise_their_own_flag():
    assert any("non_single_star" in f for f in gaia_flag_digest(_nb(non_single_star=3), 2.0)["flags"])
    v = gaia_flag_digest(_nb(phot_variable_flag="VARIABLE", best_class_name="SOLAR_LIKE"), 2.0)
    assert any("VARIABLE" in f and "SOLAR_LIKE" in f for f in v["flags"])


def test_a_gaia_rv_amplitude_counts_only_above_four_times_its_per_epoch_error():
    loud = _nb(rv_amplitude_robust=100.0, radial_velocity_error=1.0, rv_nb_transits=16)
    quiet = _nb(rv_amplitude_robust=5.0, radial_velocity_error=1.0, rv_nb_transits=16)
    d_loud, d_quiet = gaia_flag_digest(loud, 2.0), gaia_flag_digest(quiet, 2.0)
    assert d_loud["rv_expected_peak_to_peak"] == pytest.approx(16.0)   # 4 x 1 x sqrt(16)
    assert d_loud["rv_above_noise_expectation"] is True
    assert d_quiet["rv_above_noise_expectation"] is False
    assert d_quiet["flags"] == []


def test_a_neighbour_bright_enough_to_make_the_depth_and_a_vsx_entry_both_flag():
    n = _nb()
    n["gaia"]["n_neighbours_that_could_produce_depth_total_eclipse_within_63arcsec"] = 2
    n["vsx"] = {"n_within_1arcmin": 1, "objects": [{"Type": "ROT"}]}
    flags = gaia_flag_digest(n, 2.0)["flags"]
    assert any("neighbour(s) within 3 px" in f for f in flags)
    assert any("VSX entry" in f and "ROT" in f for f in flags)


def test_the_digest_survives_a_gaia_query_that_failed():
    d = gaia_flag_digest({"gaia": {"error": "TimeoutError"}}, 2.0)
    assert d["gaia_error"] == "TimeoutError"
    assert d["flags"] == []
