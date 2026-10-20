"""Unit tests for ``tesshunter.ranking``: the v2 survivor score.

The frozen P4 score is not touched by any of this - it is tested nowhere here
and changed nowhere in the package.  What these tests pin is that v2 rewards the
two things the audit measures (kept-event SNR and how many independent sectors
show the dip), subtracts the star-level penalties, and goes to zero when the
full-phase secondary scan says the companion is stellar.
"""

import pytest

from tesshunter import audit_rules as R
from tesshunter.ranking import (
    V2_AEN_SIG,
    V2_IPD_MULTI_PEAK,
    V2_RUWE,
    gaia_penalty_flags,
    independent_sectors,
    score_v2,
)


def _ev(sector, sigma, excluded=False, observed=True):
    return {"n": sector, "sector": sector, "observed": observed, "excluded": excluded,
            "det_depth_ppt": sigma * 0.1, "det_depth_err_ppt": 0.1}


CLEAN_GAIA = {"ruwe": 1.0, "ipd_frac_multi_peak": 0.0, "astrometric_excess_noise_sig": 1.0,
              "non_single_star": 0}


# ── the sector term ──────────────────────────────────────────────────────────

def test_only_kept_events_above_two_sigma_count_towards_the_sector_term():
    evs = [_ev(1, 5.0), _ev(2, 1.0), _ev(3, 5.0, excluded=True), _ev(4, 3.0)]
    s = independent_sectors(evs)
    assert s["sectors_showing_the_dip"] == [1, 4]      # 2 is too weak, 3 was removed
    assert s["n_sectors_with_kept_events"] == 3        # sector 3 has no kept event
    assert s["sigma_per_event"] == R.V2_SECTOR_EVENT_SIGMA


def test_two_events_in_the_same_sector_count_once():
    s = independent_sectors([_ev(1, 5.0), {"n": 2, "sector": 1, "observed": True, "excluded": False,
                                           "det_depth_ppt": 1.0, "det_depth_err_ppt": 0.1}])
    assert s["n_sectors_showing_the_dip"] == 1


def test_unobserved_epochs_are_ignored_by_the_sector_term():
    assert independent_sectors([_ev(1, 5.0, observed=False)])["n_sectors_showing_the_dip"] == 0


# ── the Gaia penalties ───────────────────────────────────────────────────────

def test_each_gaia_penalty_fires_at_its_own_threshold():
    assert gaia_penalty_flags(CLEAN_GAIA) == []
    assert len(gaia_penalty_flags({**CLEAN_GAIA, "ruwe": V2_RUWE})) == 1
    assert gaia_penalty_flags({**CLEAN_GAIA, "ruwe": V2_RUWE - 0.01}) == []
    assert len(gaia_penalty_flags({**CLEAN_GAIA, "ipd_frac_multi_peak": V2_IPD_MULTI_PEAK})) == 1
    assert len(gaia_penalty_flags({**CLEAN_GAIA, "astrometric_excess_noise_sig": V2_AEN_SIG})) == 1
    assert gaia_penalty_flags({**CLEAN_GAIA, "astrometric_excess_noise_sig": V2_AEN_SIG - 1}) == []
    assert len(gaia_penalty_flags({**CLEAN_GAIA, "non_single_star": 3})) == 1


def test_the_v2_excess_noise_threshold_is_deliberately_far_above_stage_bs():
    # Stage B flags at 2 (it flags, never kills); v2 penalises only at 100, so the
    # penalty separates the list instead of moving every row down together.
    assert V2_AEN_SIG > R.B_AEN_SIG
    assert gaia_penalty_flags({**CLEAN_GAIA, "astrometric_excess_noise_sig": 50.0}) == []


def test_all_four_gaia_penalties_can_stack():
    bad = {"ruwe": 11.6, "ipd_frac_multi_peak": 95.0,
           "astrometric_excess_noise_sig": 1560.0, "non_single_star": 1}
    assert len(gaia_penalty_flags(bad)) == 4


# ── the score ────────────────────────────────────────────────────────────────

def test_a_strong_multi_sector_signal_on_a_clean_star_scores_near_the_maximum():
    evs = [_ev(s, 5.0) for s in (1, 2, 3, 4, 5)]
    s = score_v2(60.0, evs, CLEAN_GAIA, {"flag": False}, "PASS")
    assert s["S_sectors"] == 1.0
    assert s["S_snr2"] == 1.0                          # 60 is above the saturation of 20
    assert s["score_v2"] == pytest.approx(2.0)


def test_the_snr_term_saturates_and_is_monotonic_below_it():
    a = score_v2(3.0, [_ev(1, 5.0)], CLEAN_GAIA, None, "PASS")
    b = score_v2(10.0, [_ev(1, 5.0)], CLEAN_GAIA, None, "PASS")
    c = score_v2(R.V2_SNR_SATURATION, [_ev(1, 5.0)], CLEAN_GAIA, None, "PASS")
    d = score_v2(500.0, [_ev(1, 5.0)], CLEAN_GAIA, None, "PASS")
    assert a["S_snr2"] < b["S_snr2"] < c["S_snr2"]
    assert c["S_snr2"] == pytest.approx(1.0)
    assert d["S_snr2"] == 1.0


def test_a_signal_in_one_sector_scores_below_the_same_signal_in_four():
    one = score_v2(30.0, [_ev(1, 5.0)], CLEAN_GAIA, None, "PASS")
    four = score_v2(30.0, [_ev(s, 5.0) for s in (1, 2, 3, 4)], CLEAN_GAIA, None, "PASS")
    assert four["score_v2"] > one["score_v2"]
    assert one["S_sectors"] == pytest.approx(0.25)
    assert four["S_sectors"] == 1.0


def test_each_gaia_flag_costs_a_quarter_and_a_deep_host_costs_a_half():
    evs = [_ev(s, 5.0) for s in (1, 2, 3, 4)]
    clean = score_v2(60.0, evs, CLEAN_GAIA, {"flag": False}, "PASS")
    one_flag = score_v2(60.0, evs, {**CLEAN_GAIA, "ruwe": 3.2}, {"flag": False}, "PASS")
    host = score_v2(60.0, evs, CLEAN_GAIA, {"flag": True}, "PASS")
    assert clean["score_v2"] - one_flag["score_v2"] == pytest.approx(R.V2_GAIA_FLAG_PENALTY)
    assert clean["score_v2"] - host["score_v2"] == pytest.approx(R.V2_DEEP_HOST_PENALTY)


def test_a_failing_secondary_gate_zeroes_the_score_however_strong_the_signal():
    evs = [_ev(s, 50.0) for s in range(1, 9)]
    s = score_v2(600.0, evs, CLEAN_GAIA, {"flag": False}, "FAIL")
    assert s["score_v2"] == 0.0
    assert s["zeroed_by_secondary_gate"] is True
    assert s["raw_before_floor_and_gate"] == pytest.approx(2.0)   # the terms are still recorded


def test_the_score_never_goes_below_zero_from_penalties_alone():
    s = score_v2(1.0, [], {"ruwe": 11.6, "ipd_frac_multi_peak": 95.0,
                           "astrometric_excess_noise_sig": 1560.0, "non_single_star": 1},
                 {"flag": True}, "PASS")
    assert s["score_v2"] == 0.0
    assert s["raw_before_floor_and_gate"] < 0


def test_a_missing_snr_or_gate_is_handled_without_crashing():
    s = score_v2(None, [], None, None, None)
    assert s["score_v2"] == 0.0
    assert s["S_snr2"] == 0.0
    assert s["zeroed_by_secondary_gate"] is False


def test_the_record_carries_every_threshold_that_produced_it():
    s = score_v2(20.0, [_ev(1, 5.0)], CLEAN_GAIA, {"flag": False}, "PASS")
    th = s["thresholds"]
    assert th["ruwe"] == V2_RUWE
    assert th["astrometric_excess_noise_sig"] == V2_AEN_SIG
    assert th["gaia_flag_penalty"] == R.V2_GAIA_FLAG_PENALTY
    assert th["deep_host_penalty"] == R.V2_DEEP_HOST_PENALTY
    assert s["snr_saturation"] == R.V2_SNR_SATURATION
    assert s["sectors_saturation"] == R.V2_SECTORS_SATURATION
