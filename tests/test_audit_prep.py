"""Unit tests for ``tesshunter.audit_prep``: one test per preprocessing rule.

Every test asserts that a rule fires exactly when its documented condition holds
and NOT otherwise: a cadence one sigma inside the clip stays, one sigma outside
goes.  The light curves are synthetic and in plain BTJD, matching the helpers in
``tests/test_pipeline.py``.
"""

import math

import numpy as np
import pytest

from tesshunter import audit_rules as R
from tesshunter.audit_prep import (
    bin_lc,
    clean_and_detrend,
    clip_binned,
    detrend_window_days,
    expected_t14_hours,
    prepare_series,
    product_bitmask,
    transit_mask,
)

wotan = pytest.importorskip("wotan", reason="the audit detrend needs wotan")


# ── helpers ───────────────────────────────────────────────────────────────────

def _product(n=2000, cadence_min=10.0, t_start=1000.0, sector=1, author="SPOC",
             noise_ppt=1.0, seed=7, level=1.0, signals=()):
    """One synthetic product in the shape ``audit_p5.load_products`` returns."""
    rng = np.random.default_rng(seed)
    dt = cadence_min / 1440.0
    t = t_start + np.arange(n) * dt
    f = np.ones(n)
    for (period, t0, dur, depth_ppt) in signals:
        ph = ((t - t0 + 0.5 * period) % period) - 0.5 * period
        f[np.abs(ph) <= 0.5 * dur] -= depth_ppt / 1000.0
    f = f * level + rng.normal(0.0, noise_ppt / 1000.0, n) * level
    return {"time": t, "flux": f, "flux_err": np.full(n, noise_ppt / 1000.0 * level),
            "sap_flux": f.copy(), "sap_flux_err": np.full(n, noise_ppt / 1000.0 * level),
            "sap_bkg": np.full(n, 100.0), "quality": np.zeros(n, dtype=int),
            "sector": sector, "author": author, "cadence_s": cadence_min * 60.0,
            "flux_column": "pdcsap_flux", "t_start": float(t[0]), "t_end": float(t[-1])}


# ── the QLP low-precision flag ────────────────────────────────────────────────

def test_product_bitmask_adds_qlp_low_precision_bit_before_and_after_sector_56():
    assert product_bitmask({"author": "QLP", "sector": 55}) == R.Q_DEFAULT | 2 ** 12
    assert product_bitmask({"author": "QLP", "sector": 56}) == R.Q_DEFAULT | 2 ** 30
    assert product_bitmask({"author": "QLP", "sector": 1}) == R.Q_DEFAULT | 2 ** 12


def test_product_bitmask_leaves_spoc_products_at_the_default_mask():
    for author in ("SPOC", "TESS-SPOC"):
        assert product_bitmask({"author": author, "sector": 60}) == R.Q_DEFAULT
        assert product_bitmask({"author": author, "sector": 3}) == R.Q_DEFAULT


def test_product_bitmask_honours_a_non_default_base():
    assert product_bitmask({"author": "QLP", "sector": 60}, base=R.Q_HARD) == R.Q_HARD | 2 ** 30


# ── the detrend window ────────────────────────────────────────────────────────

def test_detrend_window_is_three_t14_between_its_floor_and_its_cap():
    assert detrend_window_days(2.0) == pytest.approx(R.WOTAN_WINDOW_MIN_DAYS)      # 0.25 d < floor
    assert detrend_window_days(8.0) == pytest.approx(1.0)                          # 3 x 8 h = 1.0 d
    assert detrend_window_days(20.0) == pytest.approx(R.WOTAN_WINDOW_MAX_DAYS)     # 2.5 d > cap


def test_expected_t14_grows_with_period_and_matches_a_hand_computation():
    # a solar analogue at 10 d: a/R* = (G M P^2 / 4 pi^2)^(1/3) / R*
    p, rstar, mstar = 10.0, 1.0, 1.0
    G = 6.674e-8
    a_rs = (G * mstar * 1.989e33 * (p * 86400.0) ** 2 / (4 * math.pi ** 2)) ** (1 / 3) / (rstar * 6.957e10)
    want = p * 24.0 / math.pi * math.asin(math.sqrt(1.05 ** 2) / a_rs)
    assert expected_t14_hours(p, rstar, mstar) == pytest.approx(want)
    assert expected_t14_hours(20.0, 1.0, 1.0) > expected_t14_hours(10.0, 1.0, 1.0)


# ── the transit mask (prompt-7 option 3) ─────────────────────────────────────

def test_transit_mask_covers_one_duration_either_side_of_every_mid_time():
    t = np.linspace(1000.0, 1030.0, 30001)
    m = transit_mask(t, period=10.0, t0=1002.0, duration=0.2)
    # inside: |t - tc| < 0.2 at every epoch of the baseline
    for tc in (1002.0, 1012.0, 1022.0):
        assert m[np.argmin(np.abs(t - tc))]
        assert m[np.argmin(np.abs(t - (tc + 0.19)))]
        assert not m[np.argmin(np.abs(t - (tc + 0.21)))]
    assert 0 < m.sum() < len(t)


def test_transit_mask_is_empty_for_a_degenerate_ephemeris():
    t = np.linspace(1000.0, 1010.0, 1001)
    assert not transit_mask(t, 0.0, 1000.0, 0.1).any()
    assert not transit_mask(t, 10.0, 1000.0, 0.0).any()


# ── clean_and_detrend: the quality mask ──────────────────────────────────────

def test_quality_mask_drops_exactly_the_flagged_cadences():
    p = _product()
    p["quality"][100:150] = R.Q_DESAT
    out = clean_and_detrend([p], 0.75)
    assert out["per_product"][0]["n_masked_quality"] == 50


def test_quality_mask_drops_qlp_low_precision_cadences_only_for_qlp():
    q = _product(author="QLP", sector=60)
    q["quality"][:80] = 2 ** 30
    assert clean_and_detrend([q], 0.75)["per_product"][0]["n_masked_quality"] == 80
    s = _product(author="TESS-SPOC", sector=60)
    s["quality"][:80] = 2 ** 30          # not in the default mask, so SPOC keeps them
    assert clean_and_detrend([s], 0.75)["per_product"][0]["n_masked_quality"] == 0


def test_a_product_with_fewer_than_fifty_usable_cadences_is_dropped():
    p = _product(n=2000)
    p["quality"][:1960] = R.Q_DESAT      # 40 left, below MIN_POINTS_PER_PRODUCT
    out = clean_and_detrend([p, _product(sector=2)], 0.75)
    assert out["per_product"][0]["dropped"] is True
    assert out["per_product"][0]["n_used"] == 40
    assert set(np.unique(out["sector"])) == {2}


# ── clean_and_detrend: the clips ─────────────────────────────────────────────

def test_upward_clip_removes_a_flare_and_keeps_a_three_sigma_point():
    p = _product(noise_ppt=1.0, seed=3)
    p["flux"][500] += 0.020              # +20 sigma
    p["flux"][700] += 0.003              # +3 sigma, inside the 4-sigma clip
    out = clean_and_detrend([p], 0.75)
    assert out["per_product"][0]["n_clipped_up"] == 1


def test_isolated_single_cadence_dip_is_removed_but_a_real_short_transit_is_not():
    p = _product(noise_ppt=1.0, seed=5)
    p["flux"][900] -= 0.020              # one cadence, -20 sigma, neighbours normal
    out = clean_and_detrend([p], 0.75)
    assert out["per_product"][0]["n_isolated_clipped"] == 1
    q = _product(noise_ppt=1.0, seed=5)
    q["flux"][900:906] -= 0.020          # six cadences: a transit, not an isolated dip
    out2 = clean_and_detrend([q], 0.75)
    assert out2["per_product"][0]["n_isolated_clipped"] == 0


def test_isolated_dip_rule_spares_a_dip_whose_neighbour_is_also_low():
    p = _product(noise_ppt=1.0, seed=11)
    p["flux"][900] -= 0.020
    p["flux"][901] -= 0.005              # neighbour more than 2 sigma low: not isolated
    assert clean_and_detrend([p], 0.75)["per_product"][0]["n_isolated_clipped"] == 0


def test_products_are_normalised_to_their_own_median_before_the_detrend():
    bright = _product(level=50000.0, sector=1, seed=2)
    faint = _product(level=300.0, sector=2, seed=2)
    out = clean_and_detrend([bright, faint], 0.75)
    assert np.nanmedian(out["flux"]) == pytest.approx(1.0, abs=2e-4)
    assert out["flux"].min() > 0.9 and out["flux"].max() < 1.1


def test_nan_flux_errors_fall_back_to_the_point_to_point_scatter():
    p = _product(noise_ppt=2.0, seed=9)
    p["flux_err"] = np.full(len(p["time"]), np.nan)
    out = clean_and_detrend([p], 0.75)
    assert np.all(np.isfinite(out["flux_err"]))
    assert out["flux_err"][0] == pytest.approx(0.002, rel=0.25)


def test_the_concatenated_series_is_sorted_in_time_across_products():
    out = clean_and_detrend([_product(sector=2, t_start=1100.0), _product(sector=1, t_start=1000.0)], 0.75)
    assert np.all(np.diff(out["time"]) >= 0)


# ── the transit-masked detrend (prompt-7 option 3) ───────────────────────────

def test_masked_detrend_recovers_more_of_a_transit_than_the_unmasked_one():
    # a 5 ppt, 4-hour transit every 3 d on a slowly varying star: the biweight window is
    # 0.75 d, so the unmasked trend follows part of the transit down and eats depth.
    per, t0, dur, depth = 3.0, 1000.5, 4.0 / 24.0, 5.0
    p = _product(n=8640, cadence_min=5.0, noise_ppt=0.2, seed=4,
                 signals=((per, t0, dur, depth),))
    p["flux"] += 0.004 * np.sin(2 * np.pi * (p["time"] - 1000.0) / 7.0)

    def depth_of(det):
        m = transit_mask(det["time"], per, t0, dur, n_durations=0.35)
        return 1000 * (np.median(det["flux"][~m]) - np.mean(det["flux"][m]))

    plain = depth_of(clean_and_detrend([dict(p)], 0.75))
    masked = depth_of(clean_and_detrend([dict(p)], 0.75,
                                        mask_fn=lambda tt: transit_mask(tt, per, t0, dur)))
    assert plain < depth                       # the unmasked detrend absorbs part of it
    assert masked > plain
    assert masked == pytest.approx(depth, rel=0.10)


def test_masked_detrend_records_how_many_cadences_it_kept_out_of_the_trend():
    p = _product(n=4000, cadence_min=10.0, noise_ppt=1.0, seed=6)
    out = clean_and_detrend([p], 0.75, mask_fn=lambda tt: transit_mask(tt, 3.0, 1000.5, 0.2))
    rec = out["per_product"][0]
    assert rec["n_masked_from_trend"] > 0
    assert rec["n_masked_from_trend"] < len(p["time"])


# ── bin_lc ───────────────────────────────────────────────────────────────────

def test_bin_lc_bins_to_the_requested_width_and_averages_within_the_bin():
    t = 1000.0 + np.arange(120) * (2.0 / 1440.0)          # 2-min cadence, 4 hours
    f = np.ones(120)
    f[:15] = 0.5                                          # the first 30-min bin
    e = np.full(120, 1e-3)
    tb, fb, eb = bin_lc(t, f, e, 30.0)
    assert len(tb) == 8
    assert fb[0] == pytest.approx(0.5)
    assert fb[1] == pytest.approx(1.0)


def test_bin_error_is_the_in_bin_scatter_when_the_bin_is_full_and_propagated_when_it_is_not():
    rng = np.random.default_rng(0)
    t = 1000.0 + np.arange(60) * (1.0 / 1440.0)
    f = 1.0 + rng.normal(0, 1e-3, 60)
    e = np.full(60, 1e-6)                                  # deliberately far too small
    _, _, eb = bin_lc(t, f, e, 30.0)
    assert eb[0] > 1e-5                                    # scatter, not the propagated error
    t2 = np.array([1000.0, 1000.0 + 40.0 / 1440.0])        # two bins of one point each
    _, _, eb2 = bin_lc(t2, np.ones(2), np.full(2, 1e-3), 30.0)
    assert eb2[0] == pytest.approx(1e-3)


# ── clip_binned ──────────────────────────────────────────────────────────────

def test_isolated_binned_dip_is_clipped():
    rng = np.random.default_rng(1)
    tb = 1000.0 + np.arange(400) * (30.0 / 1440.0)
    fb = 1.0 + rng.normal(0, 1e-4, 400)
    fb[200] -= 0.002                                       # one bin, ~20 sigma
    out = clip_binned(tb, fb, np.full(400, 1e-4), ref_depth=0.05)
    assert out["n_isolated_bins_clipped"] == 1


def test_deep_clip_threshold_is_three_times_the_depth_or_ten_mad_whichever_is_larger():
    rng = np.random.default_rng(2)
    tb = 1000.0 + np.arange(600) * (30.0 / 1440.0)
    fb = 1.0 + rng.normal(0, 1e-4, 600)
    fb[100:110] -= 0.030                                   # an eclipse, 30 ppt
    eb = np.full(600, 1e-4)
    deep = clip_binned(tb, fb, eb, ref_depth=0.002)        # 3 x 2 ppt = 6 ppt < 30 ppt
    assert deep["n_deep_clipped"] == 10
    assert deep["deep_clip_threshold_ppt"] == pytest.approx(6.0, abs=0.5)
    shallow = clip_binned(tb, fb, eb, ref_depth=0.020)     # 3 x 20 ppt = 60 ppt > 30 ppt
    assert shallow["n_deep_clipped"] == 0


def test_deep_clip_floor_is_ten_mad_when_the_candidate_depth_is_tiny():
    rng = np.random.default_rng(3)
    tb = 1000.0 + np.arange(600) * (30.0 / 1440.0)
    fb = 1.0 + rng.normal(0, 1e-3, 600)
    out = clip_binned(tb, fb, np.full(600, 1e-3), ref_depth=0.0)
    assert out["deep_clip_threshold_ppt"] == pytest.approx(10.0, rel=0.2)


# ── prepare_series ───────────────────────────────────────────────────────────

def test_prepare_series_reports_every_counter_the_records_carry():
    out = prepare_series([_product(sector=1), _product(sector=2, t_start=1030.0, seed=8)],
                         0.75, 30.0, ref_depth=0.005)
    c = out["counters"]
    for k in ("n_unbinned", "n_binned", "n_unbinned_masked", "n_isolated_clipped",
              "n_isolated_bins_clipped", "deep_clip_threshold_ppt", "n_deep_clipped"):
        assert k in c
    assert c["n_binned"] < c["n_unbinned"]
    assert len(out["binned"]["time"]) == c["n_binned"]


def test_prepare_series_removes_the_masked_btjd_ranges_and_counts_them():
    p = _product(n=2000, cadence_min=10.0)
    out = prepare_series([p], 0.75, 30.0, 0.005, mask_ranges=[(1002.0, 1004.0)])
    assert out["counters"]["n_unbinned_masked"] > 0
    t = out["unbinned"]["time"]
    assert not ((t >= 1002.0) & (t <= 1004.0)).any()
