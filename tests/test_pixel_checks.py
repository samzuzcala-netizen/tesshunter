"""Prompt 3 part E: folding the centroid and contamination checks into the verdict."""

from tesshunter.vetting import (
    VERDICT_AMBIGUOUS,
    VERDICT_FP,
    VERDICT_PROMISING,
    VettingResult,
    apply_pixel_checks,
    vetting_result_from_dict,
)
from dataclasses import asdict


def _clean():
    return VettingResult(depth_ppt=1.0, duration_days=0.1, period_days=3.0, snr=20.0, n_sectors=2,
                         verdict=VERDICT_PROMISING)


def test_unavailable_checks_change_nothing():
    r = _clean()
    v = apply_pixel_checks(r, {"available": False, "note": "no TPF"}, None)
    assert v == VERDICT_PROMISING and not r.high_risk_flags and not r.medium_flags
    assert any("not available" in n for n in r.notes) and any("not run" in n for n in r.notes)


def test_flagged_centroid_is_high_risk_and_stacks_with_high_contamination():
    r = _clean()
    cen = {"available": True, "flagged": True, "total_shift_px": 0.42, "sigma": 5.1, "shift_arcsec": 8.8,
           "n_sectors_used": 2}
    v = apply_pixel_checks(r, cen, None)
    assert v == VERDICT_AMBIGUOUS and len(r.high_risk_flags) == 1
    con = {"available": True, "flagged": True, "high_risk_neighbours": [1], "medium_risk_neighbours": [],
           "n_neighbours_checked": 5}
    v = apply_pixel_checks(r, cen, con)
    assert v == VERDICT_FP and len(r.high_risk_flags) == 2     # idempotent on the centroid flag


def test_medium_contamination_is_a_medium_flag():
    r = _clean()
    con = {"available": True, "flagged": True, "high_risk_neighbours": [], "medium_risk_neighbours": [1, 2],
           "n_neighbours_checked": 5}
    v = apply_pixel_checks(r, {"available": True, "flagged": False, "total_shift_px": 0.01, "sigma": 0.5,
                               "shift_arcsec": 0.2, "n_sectors_used": 1}, con)
    assert v == VERDICT_PROMISING and len(r.medium_flags) == 1 and not r.high_risk_flags


def test_low_nfpp_clears_a_high_risk_contamination_neighbour():
    r = _clean()
    con = {"available": True, "flagged": True, "high_risk_neighbours": [1], "medium_risk_neighbours": [2],
           "n_neighbours_checked": 13}
    v = apply_pixel_checks(r, None, con, fpp={"available": True, "fpp": 0.08, "nfpp": 1e-77})
    assert v == VERDICT_PROMISING
    assert not r.high_risk_flags and not r.medium_flags
    assert any("cleared by TRICERATOPS NFPP" in n for n in r.notes)
    assert any("TRICERATOPS: FPP 0.0800" in n for n in r.notes)


def test_centroid_below_four_sigma_is_a_medium_flag():
    r = _clean()
    cen = {"available": True, "flagged": True, "total_shift_px": 0.003, "sigma": 3.6, "shift_arcsec": 0.06,
           "n_sectors_used": 2}
    v = apply_pixel_checks(r, cen, None)
    assert v == VERDICT_PROMISING and not r.high_risk_flags and len(r.medium_flags) == 1
    r2 = _clean()
    cen["sigma"] = 4.3
    assert apply_pixel_checks(r2, cen, None) == VERDICT_AMBIGUOUS and len(r2.high_risk_flags) == 1


def test_high_nfpp_is_its_own_high_risk_flag():
    r = _clean()
    v = apply_pixel_checks(r, None, None, fpp={"available": True, "fpp": 0.9, "nfpp": 0.6})
    assert v == VERDICT_AMBIGUOUS and any("nearby false-positive probability" in f for f in r.high_risk_flags)
    # unavailable TRICERATOPS leaves the contamination flag at high risk
    r2 = _clean()
    con = {"available": True, "flagged": True, "high_risk_neighbours": [1], "medium_risk_neighbours": [],
           "n_neighbours_checked": 3}
    v2 = apply_pixel_checks(r2, None, con, fpp={"available": False, "error": "no cutout"})
    assert v2 == VERDICT_AMBIGUOUS and len(r2.high_risk_flags) == 1


def test_round_trip_from_dict_keeps_alias_lists_in_sync():
    r = _clean()
    r.high_risk_flags.append("x")
    r2 = vetting_result_from_dict(asdict(r))
    assert r2.high_risk_flags == ["x"] and r2.flags_high is r2.high_risk_flags
    r2.flags_high.append("y")
    assert r2.high_risk_flags == ["x", "y"]
