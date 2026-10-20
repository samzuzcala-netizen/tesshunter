"""Unit tests for ``tesshunter.event_vet``: one test per removal rule.

Each rule is exercised twice - once with its documented condition met and once
just inside it - so the tests pin the threshold, not only the direction.  A
momentum dump within one duration removes the event; one just outside does not.
A dip absent from SAP removes; the same dip present in SAP does not.

The light curves are synthetic and in plain BTJD, matching the helpers in
``tests/test_pipeline.py``.
"""

import numpy as np
import pytest

from tesshunter import audit_rules as R
from tesshunter.event_vet import (
    advisory_flags,
    classes_of,
    event_table,
    kept_event_stats,
    measure_event,
    predicted_epochs,
    sector_beta,
    summarise_events,
    weighted_mean,
)

TC = 1005.0
DUR = 0.2              # 4.8 h; "within one duration" is max(DUR, 0.25) = 0.25 d for a dump
DEPTH = 0.005          # 5 ppt


def _product(t_start=1000.0, t_end=1010.0, cadence_min=10.0, sector=1, author="SPOC",
             noise_ppt=0.3, seed=1, sap_level=20000.0, dip_ppt=5.0, sap_dip_ppt=None,
             bkg=100.0):
    """One product covering ``TC``, with the dip present in both fluxes by default."""
    rng = np.random.default_rng(seed)
    dt = cadence_min / 1440.0
    t = np.arange(t_start, t_end, dt)
    n = len(t)
    inb = np.abs(t - TC) < DUR / 2
    pdc = 1.0 + rng.normal(0, noise_ppt / 1000.0, n)
    pdc[inb] -= dip_ppt / 1000.0
    sap = np.ones(n) + rng.normal(0, noise_ppt / 1000.0, n)
    sap[inb] -= (dip_ppt if sap_dip_ppt is None else sap_dip_ppt) / 1000.0
    return {"time": t, "flux": pdc, "flux_err": np.full(n, noise_ppt / 1000.0),
            "sap_flux": sap * sap_level, "sap_flux_err": np.full(n, noise_ppt / 1000.0 * sap_level),
            "sap_bkg": np.full(n, bkg), "quality": np.zeros(n, dtype=int),
            "sector": sector, "author": author, "cadence_s": cadence_min * 60.0,
            "flux_column": "pdcsap_flux", "t_start": float(t[0]), "t_end": float(t[-1])}


def _detrended(p, dip_ppt=5.0, noise_ppt=0.3, seed=2):
    """The whole-baseline detrended corrected series the audit measures ``det_depth`` in."""
    rng = np.random.default_rng(seed)
    t = p["time"]
    f = 1.0 + rng.normal(0, noise_ppt / 1000.0, len(t))
    f[np.abs(t - TC) < DUR / 2] -= dip_ppt / 1000.0
    return t, f


def _measure(p, **kw):
    t_det, f_det = _detrended(p, **kw)
    return measure_event(p, TC, DUR, DEPTH, t_det, f_det, epoch=0)


# ── which epochs are predicted, and which are observed ───────────────────────

def test_predicted_epochs_covers_every_mid_time_inside_the_baseline():
    assert list(predicted_epochs(1000.0, 1030.0, 10.0, 1002.0)) == [0, 1, 2]
    assert list(predicted_epochs(1000.0, 1009.9, 10.0, 1002.0)) == [0]
    assert list(predicted_epochs(1003.0, 1004.0, 10.0, 1002.0)) == []


def test_an_epoch_with_less_than_half_its_transit_observed_is_not_observed():
    p = _product(t_start=TC + 0.012, t_end=1010.0)    # only the second half of the egress
    ev = _measure(p)
    assert ev["coverage_in_transit"] < R.EVENT_MIN_COVERAGE
    assert ev["observed"] is False
    assert "coverage" in ev["reason"]


def test_an_epoch_covered_by_more_than_half_its_transit_is_observed():
    p = _product(t_start=TC - 0.04, t_end=1010.0)     # 0.14 d of the 0.2 d transit
    ev = _measure(p)
    assert ev["coverage_in_transit"] > R.EVENT_MIN_COVERAGE
    assert ev["observed"] is True


def test_an_epoch_no_product_covers_is_recorded_as_unobserved():
    a = _product(t_start=1000.0, t_end=1002.0)
    b = _product(t_start=1008.0, t_end=1010.0, seed=3)
    t_det = np.concatenate([a["time"], b["time"]])
    f_det = np.concatenate([a["flux"], b["flux"]])
    evs = event_table([a, b], t_det, f_det, period=10.0, t0=TC, duration=DUR, ref_depth=DEPTH)
    assert len(evs) == 1
    assert evs[0]["observed"] is False
    assert evs[0]["reason"] == "no product covers the epoch"


def test_a_clean_event_survives_every_rule():
    ev = _measure(_product())
    assert ev["observed"] is True
    assert ev["excluded"] is False, ev["exclusion_reasons"]
    assert ev["det_depth_ppt"] == pytest.approx(5.0, abs=0.5)
    assert ev["sap_depth_ppt"] == pytest.approx(5.0, abs=0.5)


# ── rule 1: momentum dump within one duration ────────────────────────────────

def test_momentum_dump_within_one_duration_removes_the_event():
    p = _product()
    p["quality"][np.abs(p["time"] - (TC + 0.22)) < 0.01] = R.Q_DESAT   # 0.22 d < max(DUR, 0.25)
    ev = _measure(p)
    assert ev["desat_within_one_duration"] is True
    assert "momentum dump within one duration" in ev["exclusion_reasons"]


def test_a_momentum_dump_just_outside_one_duration_does_not_remove_the_event():
    p = _product()
    p["quality"][np.abs(p["time"] - (TC + 0.30)) < 0.01] = R.Q_DESAT   # 0.30 d > 0.25 d
    ev = _measure(p)
    assert ev["desat_within_one_duration"] is False
    assert ev["excluded"] is False, ev["exclusion_reasons"]


# ── rule 2: sector or orbit edge within one duration ─────────────────────────

def test_an_event_within_one_duration_of_a_sector_edge_is_removed():
    p = _product(t_start=TC - 0.15, t_end=1010.0)      # 0.15 d < max(DUR, 0.2) from the start
    ev = _measure(p)
    assert ev["edge_within_one_duration"] is True
    assert any("sector/orbit edge" in r for r in ev["exclusion_reasons"])


def test_an_event_within_one_duration_of_an_orbit_gap_is_removed():
    p = _product()
    keep = ~((p["time"] > TC + 0.25) & (p["time"] < TC + 0.9))        # a 0.65 d gap
    for k in ("time", "flux", "flux_err", "sap_flux", "sap_flux_err", "sap_bkg", "quality"):
        p[k] = p[k][keep]
    ev = _measure(p)
    assert ev["edge_distance_days"] == pytest.approx(0.25, abs=0.02)
    assert ev["excluded"] is False                                     # 0.25 d > 0.2 d: kept
    p2 = _product()
    keep2 = ~((p2["time"] > TC + 0.15) & (p2["time"] < TC + 0.9))      # gap starts 0.15 d away
    for k in ("time", "flux", "flux_err", "sap_flux", "sap_flux_err", "sap_bkg", "quality"):
        p2[k] = p2[k][keep2]
    ev2 = _measure(p2)
    assert ev2["edge_within_one_duration"] is True


# ── rule 3: a PDC gap within one duration ────────────────────────────────────

def test_a_pdc_gap_within_one_duration_removes_the_event_even_when_sap_is_continuous():
    p = _product()
    p["flux"][(p["time"] > TC + 0.15) & (p["time"] < TC + 0.9)] = np.nan   # PDC cut it, SAP did not
    ev = _measure(p)
    assert ev["pdc_gap_within_one_duration"] is True
    assert ev["edge_within_one_duration"] is False
    assert any("PDC gap" in r for r in ev["exclusion_reasons"])


def test_a_pdc_gap_further_than_one_duration_away_does_not_remove_the_event():
    p = _product()
    p["flux"][(p["time"] > TC + 0.30) & (p["time"] < TC + 0.9)] = np.nan
    ev = _measure(p)
    assert ev["pdc_gap_within_one_duration"] is False
    assert ev["excluded"] is False, ev["exclusion_reasons"]


# ── rule 4: quality-flagged in-transit cadences ──────────────────────────────

def test_more_than_twenty_per_cent_of_in_transit_cadences_flagged_removes_the_event():
    p = _product()
    inb = np.where(np.abs(p["time"] - TC) < DUR / 2)[0]
    p["quality"][inb[: int(0.35 * len(inb))]] = 1          # bit 1 is in the default mask
    ev = _measure(p)
    assert ev["frac_in_transit_quality_flagged"] > R.QUALITY_FLAG_FRACTION
    assert any("quality-flagged" in r for r in ev["exclusion_reasons"])


def test_ten_per_cent_of_in_transit_cadences_flagged_does_not_remove_the_event():
    p = _product()
    inb = np.where(np.abs(p["time"] - TC) < DUR / 2)[0]
    p["quality"][inb[: max(1, int(0.10 * len(inb)))]] = 1
    ev = _measure(p)
    assert ev["frac_in_transit_quality_flagged"] <= R.QUALITY_FLAG_FRACTION
    assert ev["excluded"] is False, ev["exclusion_reasons"]


# ── rule 5: scattered-light flags near the event ─────────────────────────────

def test_more_than_twenty_per_cent_of_near_transit_cadences_straylight_flagged_removes():
    p = _product()
    near = np.where(np.abs(p["time"] - TC) < max(DUR, R.NEAR_EVENT_MIN_DAYS))[0]
    p["quality"][near[: int(0.40 * len(near))]] = 2048
    ev = _measure(p)
    assert ev["frac_straylight_flagged_within_one_duration"] > R.STRAYLIGHT_FLAG_FRACTION
    assert any("scattered-light flag" in r for r in ev["exclusion_reasons"])


def test_a_tenth_of_near_transit_cadences_straylight_flagged_does_not_remove():
    p = _product()
    near = np.where(np.abs(p["time"] - TC) < max(DUR, R.NEAR_EVENT_MIN_DAYS))[0]
    p["quality"][near[: int(0.10 * len(near))]] = 2048
    ev = _measure(p)
    assert ev["excluded"] is False, ev["exclusion_reasons"]


# ── rule 6: the SAP baseline ramp ────────────────────────────────────────────

def test_a_sap_baseline_changing_by_more_than_one_depth_across_the_event_removes_it():
    p = _product()
    p["sap_flux"] = p["sap_flux"] * (1.0 + 0.10 * (p["time"] - TC))    # 20 ppt across 0.2 d
    ev = _measure(p)
    assert ev["baseline_change_across_event_over_depth"] > R.SAP_RAMP_OVER_DEPTH
    assert any("SAP baseline changes" in r for r in ev["exclusion_reasons"])


def test_a_gentle_sap_slope_below_one_depth_does_not_remove_the_event():
    p = _product()
    p["sap_flux"] = p["sap_flux"] * (1.0 + 0.01 * (p["time"] - TC))    # 2 ppt across 0.2 d
    ev = _measure(p)
    assert ev["baseline_change_across_event_over_depth"] < R.SAP_RAMP_OVER_DEPTH
    assert ev["excluded"] is False, ev["exclusion_reasons"]


# ── rule 7: the scattered-light (background) ramp ────────────────────────────

def test_background_above_twice_the_sector_median_and_doubling_removes_the_event():
    p = _product()
    near = np.abs(p["time"] - TC) < 0.7
    p["sap_bkg"] = np.full(len(p["time"]), 100.0)
    p["sap_bkg"][near] = 100.0 + 900.0 * (p["time"][near] - (TC - 0.7)) / 1.4
    ev = _measure(p)
    assert ev["bkg_in_over_sector_median"] > R.BKG_OVER_SECTOR_MEDIAN
    assert ev["bkg_change_across_window_over_median"] > R.BKG_CHANGE_OVER_MEDIAN
    assert any("scattered-light ramp" in r for r in ev["exclusion_reasons"])


def test_a_high_but_flat_background_does_not_remove_the_event():
    p = _product(bkg=100.0)
    p["sap_bkg"][np.abs(p["time"] - TC) < 0.7] = 500.0     # 5 x the median, but not ramping
    ev = _measure(p)
    assert ev["bkg_in_over_sector_median"] > R.BKG_OVER_SECTOR_MEDIAN
    assert not any("scattered-light ramp" in r for r in ev["exclusion_reasons"])


def test_a_ramping_but_low_background_does_not_remove_the_event():
    p = _product()
    near = np.abs(p["time"] - TC) < 0.7
    p["sap_bkg"][near] = 100.0 + 60.0 * (p["time"][near] - (TC - 0.7)) / 1.4   # ramps, never 2x
    ev = _measure(p)
    assert not any("scattered-light ramp" in r for r in ev["exclusion_reasons"])


# ── rule 8: the raw-SAP test ─────────────────────────────────────────────────

def test_a_dip_significant_in_the_corrected_flux_and_absent_in_sap_is_removed():
    p = _product(dip_ppt=5.0, sap_dip_ppt=0.2)             # SAP sees 4% of it
    ev = _measure(p, dip_ppt=5.0)
    assert ev["det_depth_ppt"] / ev["det_depth_err_ppt"] > R.SAP_ABSENT_MIN_SIGMA
    assert ev["sap_depth_ppt"] < R.SAP_ABSENT_RATIO * ev["det_depth_ppt"]
    assert any("not in SAP" in r for r in ev["exclusion_reasons"])


def test_a_dip_the_sap_flux_confirms_is_kept():
    p = _product(dip_ppt=5.0, sap_dip_ppt=4.5)             # SAP sees 90% of it
    ev = _measure(p, dip_ppt=5.0)
    assert ev["sap_depth_ppt"] > R.SAP_ABSENT_RATIO * ev["det_depth_ppt"]
    assert ev["excluded"] is False, ev["exclusion_reasons"]


def test_a_shallow_dip_below_five_sigma_is_never_removed_by_the_sap_test():
    # the rule only applies to a > 5 sigma corrected dip; a marginal one is left alone
    p = _product(dip_ppt=0.05, sap_dip_ppt=0.0, noise_ppt=3.0)
    ev = _measure(p, dip_ppt=0.05, noise_ppt=3.0)
    assert abs(ev["det_depth_ppt"] / ev["det_depth_err_ppt"]) < R.SAP_ABSENT_MIN_SIGMA
    assert not any("not in SAP" in r for r in ev["exclusion_reasons"])


def test_the_sap_test_is_skipped_when_the_product_has_no_sap_flux():
    p = _product(dip_ppt=5.0, sap_dip_ppt=0.0)
    p["sap_flux"] = np.full(len(p["time"]), np.nan)        # QLP without SAP: falls back to PDC
    ev = _measure(p, dip_ppt=5.0)
    assert ev["flux_used"] == "pdcsap_flux"
    assert not any("not in SAP" in r for r in ev["exclusion_reasons"])


# ── the artefact-class map ───────────────────────────────────────────────────

def test_every_removal_reason_maps_back_to_exactly_one_artefact_class():
    cases = {
        "momentum dump within one duration": "momentum_dump",
        "sector/orbit edge 0.10 d away": "sector_orbit_edge",
        "35% of in-transit cadences quality-flagged": "quality_flagged",
        "SAP baseline changes by more than one depth across the event (ramp)": "sap_baseline_ramp",
        "scattered-light ramp (background > 2 x sector median and doubling across the window)":
            "scattered_light_ramp",
        "40% of cadences within one duration carry the scattered-light flag": "scattered_light_flag",
        "corrected flux has a PDC gap 0.15 d away (event abuts a stretch PDC removed)": "pdc_gap",
        "dip present in corrected flux (5.00 ppt) but not in SAP (0.20 +/- 0.10 ppt)":
            "dip_absent_in_sap",
    }
    for reason, cls in cases.items():
        assert classes_of([reason]) == [cls], reason
    assert classes_of([]) == []


# ── the kept-event statistics ────────────────────────────────────────────────

def _fake_events(depths, errs, sectors=None):
    return [{"n": i, "sector": (sectors[i] if sectors else 1), "observed": True, "excluded": False,
             "det_depth_ppt": d, "det_depth_err_ppt": e}
            for i, (d, e) in enumerate(zip(depths, errs))]


def test_weighted_mean_is_inverse_variance_weighted():
    m, e = weighted_mean(np.array([1.0, 3.0]), np.array([1.0, 1.0]))
    assert m == pytest.approx(2.0)
    assert e == pytest.approx(1 / np.sqrt(2))
    m2, _ = weighted_mean(np.array([1.0, 3.0]), np.array([0.1, 1.0]))
    assert m2 == pytest.approx(1.0198, abs=1e-3)          # the precise event dominates


def test_kept_event_stats_reports_depth_snr_top_share_and_leave_one_out():
    s = kept_event_stats(_fake_events([1.0, 1.0, 1.0, 1.0], [0.1] * 4), "det")
    assert s["n"] == 4
    assert s["weighted_mean_depth_ppt"] == pytest.approx(1.0)
    assert s["snr"] == pytest.approx(20.0, abs=0.1)
    assert s["top_event_share_of_snr2"] == pytest.approx(0.25)
    assert s["snr_without_top_event"] == pytest.approx(17.32, abs=0.05)


def test_one_dominant_event_shows_up_as_a_top_share_above_one_half():
    s = kept_event_stats(_fake_events([10.0, 0.1, 0.1], [0.1, 0.1, 0.1]), "det")
    assert s["top_event_share_of_snr2"] > R.A_MAX_TOP_SHARE
    assert s["top_event_n"] == 0
    assert s["snr_without_top_event"] < s["snr"]


def test_depth_consistency_p_value_separates_constant_from_varying_depths():
    same = kept_event_stats(_fake_events([1.0, 1.02, 0.98, 1.01], [0.1] * 4), "det")
    assert same["p_const"] > R.A_P_CONST
    varying = kept_event_stats(_fake_events([1.0, 5.0, 0.2, 3.0], [0.05] * 4), "det")
    assert varying["p_const"] < R.A_P_CONST


def test_odd_even_comparison_is_reported_when_both_parities_have_events():
    s = kept_event_stats(_fake_events([1.0, 2.0, 1.0, 2.0], [0.05] * 4), "det")
    assert s["odd_even"]["sigma"] > 5
    only_even = kept_event_stats([{"n": 0, "sector": 1, "det_depth_ppt": 1.0, "det_depth_err_ppt": 0.1},
                                  {"n": 2, "sector": 1, "det_depth_ppt": 1.0, "det_depth_err_ppt": 0.1}], "det")
    assert only_even["odd_even"] is None


def test_kept_event_stats_is_empty_when_nothing_was_measurable():
    assert kept_event_stats([], "det") == {"n": 0}
    assert kept_event_stats([{"n": 0, "det_depth_ppt": None}], "det") == {"n": 0}


# ── the red-noise inflation (prompt-7 option 2) ──────────────────────────────

def test_beta_inflation_raises_the_p_value_and_records_both():
    evs = _fake_events([1.0, 1.4, 0.6, 1.2], [0.05] * 4)
    white = kept_event_stats(evs, "det")
    infl = kept_event_stats(evs, "det", beta_by_sector={1: 4.0})
    assert white["p_const"] < R.A_P_CONST                    # white errors call it inconsistent
    assert infl["p_const_white"] == white["p_const"]
    assert infl["p_const_inflated"] > white["p_const"]
    assert infl["p_const"] == infl["p_const_inflated"]       # the gate uses the inflated one
    assert infl["snr_inflated"] == pytest.approx(white["snr"] / 4.0, rel=1e-6)
    assert infl["beta_median"] == 4.0


def test_beta_one_leaves_the_statistics_untouched():
    evs = _fake_events([1.0, 1.4, 0.6, 1.2], [0.05] * 4)
    a = kept_event_stats(evs, "det")
    b = kept_event_stats(evs, "det", beta_by_sector={1: 1.0})
    assert b["p_const_inflated"] == pytest.approx(a["p_const"])
    assert b["snr_inflated"] == pytest.approx(a["snr"])


def test_beta_is_one_for_white_noise_and_larger_for_correlated_noise():
    rng = np.random.default_rng(0)
    n = 4000
    t = 1000.0 + np.arange(n) * (10.0 / 1440.0)
    sec = np.ones(n, dtype=int)
    no_transit = np.zeros(n, dtype=bool)
    white = 1.0 + rng.normal(0, 1e-3, n)
    b_white = sector_beta(t, white, sec, no_transit, DUR, {1: 600.0})
    assert b_white[1] == pytest.approx(1.0, abs=0.25)
    red = 1.0 + np.convolve(rng.normal(0, 1e-3, n + 200), np.ones(200) / 20.0, mode="same")[:n]
    b_red = sector_beta(t, red, sec, no_transit, DUR, {1: 600.0})
    assert b_red[1] > b_white[1]
    assert R.BETA_MIN <= b_red[1] <= R.BETA_MAX


def test_beta_is_clipped_to_its_documented_range():
    # a 30-day sine binned into 0.67-day bins: the bin means keep almost all the variance the
    # white expectation divides by sqrt(96), so the raw ratio is ~10 and the clip must bite.
    rng = np.random.default_rng(1)
    n = 6000
    t = 1000.0 + np.arange(n) * (10.0 / 1440.0)
    slow = 1.0 + 0.05 * np.sin(2 * np.pi * (t - 1000.0) / 30.0) + rng.normal(0, 1e-5, n)
    b = sector_beta(t, slow, np.ones(n, dtype=int), np.zeros(n, dtype=bool), 2.0, {1: 600.0})
    assert b[1] == R.BETA_MAX


# ── the summary and its advisory flags ───────────────────────────────────────

def test_summarise_events_counts_predicted_observed_excluded_and_kept():
    p = _product()
    t_det, f_det = _detrended(p)
    evs = event_table([p], t_det, f_det, period=10.0, t0=TC, duration=DUR, ref_depth=DEPTH)
    s = summarise_events(evs, {"period": 10.0, "t0": TC, "duration": DUR, "source": "test"})
    assert s["n_predicted_in_span"] == len(evs)
    assert s["n_observed"] + sum(1 for e in evs if not e.get("observed")) == len(evs)
    assert s["n_kept"] == s["n_observed"] - s["n_excluded"]
    assert s["ephemeris"]["source"] == "test"


def test_advisory_flags_fire_on_a_weak_or_one_event_signal():
    weak = advisory_flags({"n": 4, "snr": 3.0, "top_event_share_of_snr2": 0.9,
                           "snr_without_top_event": 1.0, "p_const": 1e-9}, 10, 6)
    assert any("SNR of kept events" in f for f in weak)
    assert any("carries > 50%" in f for f in weak)
    assert any("more than half" in f for f in weak)
    clean = advisory_flags({"n": 8, "snr": 20.0, "top_event_share_of_snr2": 0.2,
                            "snr_without_top_event": 18.0, "p_const": 0.4}, 10, 2)
    assert clean == []
