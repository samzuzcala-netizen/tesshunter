"""Prompt 3 part C: gate 7's second condition, gate 6 anchors that may not
carve, and the alias resolver's odd/even re-test."""

import numpy as np
import pandas as pd
import lightkurve as lk
from astropy.time import Time
from astropy import units as u

import tesshunter.pipeline as pl
from tesshunter import bls_search, stellar, survey, transit_fit as tf


def _lc(t, f, e):
    return lk.LightCurve(
        time=Time(t, format="btjd", scale="tdb"),
        flux=f * u.dimensionless_unscaled,
        flux_err=e * u.dimensionless_unscaled,
    )


def _batman_lc(period, t0, rp, a_rs, b, cadence_min=10.0, baseline=54.0, noise=1e-3,
               seed=3, sec_depth=0.0):
    rng = np.random.default_rng(seed)
    t = 1000.0 + np.arange(0.0, baseline, cadence_min / 1440.0)
    f = survey.transit_model(t, period=period, t0=t0, rp_rs=rp, b=b, a_rs=a_rs,
                             u=(0.35, 0.25), exp_time_days=cadence_min / 1440.0)
    if sec_depth > 0:
        dur = tf.transit_duration_t14(period, a_rs, b, rp)
        ph = ((t - t0 - 0.5 * period + 0.5 * period) % period) - 0.5 * period
        f[np.abs(ph) <= 0.5 * dur] -= sec_depth
    f = f + rng.normal(0.0, noise, t.size)
    return _lc(t, f, np.full(t.size, noise))


STAR = stellar.StellarParams(teff=5500.0, logg=4.5, radius=1.0, radius_err=0.05,
                             mass=1.0, mass_err=0.08, source="user")


# ── gate 7 ───────────────────────────────────────────────────────────────────

def test_gate7_second_condition_thresholds():
    assert pl._box_rp_rs(52.4) > pl.GATE7_MIN_RP_RS      # TRAPPIST-1 catastrophic box
    assert pl._box_rp_rs(95.5) > pl.GATE7_MIN_RP_RS
    assert pl._box_rp_rs(10.0) < pl.GATE7_MIN_RP_RS      # a 1% box stays
    assert pl.GATE7_MIN_RP_RS == tf.MAX_PLANET_RP_RS == 0.2


# ── gate 6 anchors ───────────────────────────────────────────────────────────

def test_ringing_neighbour_ignores_non_carving_anchors():
    accepted = [
        {"planet_num": 1, "period_days": 5.0, "carves_exclusion_zone": False},
        {"planet_num": 2, "period_days": 9.0},
    ]
    assert pl._ringing_neighbour(5.1, accepted) is None
    assert pl._ringing_neighbour(9.2, accepted)["planet_num"] == 2
    accepted[0]["carves_exclusion_zone"] = True
    assert pl._ringing_neighbour(5.1, accepted)["planet_num"] == 1


def test_anchor_plausibility_lets_a_planet_carve_and_not_a_deep_eclipse():
    P, t0 = 3.3, 1001.2
    lc = _batman_lc(P, t0, 0.08, 10.0, 0.3)
    t14 = tf.transit_duration_t14(P, 10.0, 0.3, 0.08)
    planet = {"period_days": P, "epoch_btjd": t0, "duration_days": t14, "depth_ppt": 6.5}
    carve, info = pl._anchor_plausibility(lc, planet, STAR)
    assert carve and info["success"] and info["rp_rs"] < 0.2

    lc_eb = _batman_lc(P, t0, 0.35, 6.0, 0.2, noise=2e-3)
    t14 = tf.transit_duration_t14(P, 6.0, 0.2, 0.35)
    eb = {"period_days": P, "epoch_btjd": t0, "duration_days": t14, "depth_ppt": 120.0}
    carve, info = pl._anchor_plausibility(lc_eb, eb, STAR)
    assert not carve and "Rp/R*" in info["reason"]


def test_anchor_plausibility_failure_keeps_the_old_behaviour():
    t = np.linspace(1000.0, 1000.5, 8)
    lc = _lc(t, np.ones(8), np.full(8, 1e-3))
    carve, info = pl._anchor_plausibility(lc, {"period_days": 2.0, "epoch_btjd": 1000.2,
                                               "duration_days": 0.1, "depth_ppt": 1.0}, None)
    assert carve and not info["success"]


# ── alias resolver odd/even re-test ──────────────────────────────────────────

def _trial_row(period, epoch, duration, depth, snr, label, n_dip):
    return {"harmonic_label": label, "trial_period": period, "period_days": period,
            "epoch_btjd": epoch, "duration_days": duration, "depth_frac": depth / 1000.0,
            "depth_ppt": depth, "power": 1e-6, "snr": snr, "sde": 8.0,
            "n_transits_observed": n_dip, "single_event": False, "score": snr,
            "event_completeness": 1.0, "n_covered": n_dip, "n_dip": n_dip,
            "alternating_flag": False, "overlap": 0.0, "composite_score": snr}


def test_odd_even_retest_moves_an_eb_from_half_period_to_its_true_period():
    P_eb, t0 = 4.4, 1001.0
    lc = _batman_lc(P_eb, t0, 0.12, 8.0, 0.2, baseline=81.0, sec_depth=0.006)
    t14 = tf.transit_duration_t14(P_eb, 8.0, 0.2, 0.12)
    half = pd.Series(_trial_row(P_eb / 2.0, t0, t14, 11.0, 40.0, "P/2", 36))
    trial_df = pd.DataFrame([half.to_dict(), _trial_row(P_eb, t0, t14, 16.0, 30.0, "P", 18)])
    chosen = bls_search._odd_even_retest(lc, half, trial_df)
    assert abs(float(chosen["period_days"]) - P_eb) < 1e-9
    assert bool(chosen.get("odd_even_retest"))


def test_odd_even_retest_keeps_a_true_fundamental():
    P, t0 = 3.3, 1001.2
    lc = _batman_lc(P, t0, 0.08, 10.0, 0.3, baseline=81.0)
    t14 = tf.transit_duration_t14(P, 10.0, 0.3, 0.08)
    best = pd.Series(_trial_row(P, t0, t14, 6.5, 40.0, "P", 24))
    trial_df = pd.DataFrame([best.to_dict(), _trial_row(2 * P, t0, t14, 6.5, 30.0, "2P", 12)])
    chosen = bls_search._odd_even_retest(lc, best, trial_df)
    assert abs(float(chosen["period_days"]) - P) < 1e-9
    assert not chosen.get("odd_even_retest", False)


def test_odd_even_retest_skips_weak_or_unpaired_winners():
    P, t0 = 3.3, 1001.2
    lc = _batman_lc(P, t0, 0.08, 10.0, 0.3)
    t14 = tf.transit_duration_t14(P, 10.0, 0.3, 0.08)
    weak = pd.Series(_trial_row(P, t0, t14, 6.5, 5.0, "P", 24))
    trial_df = pd.DataFrame([weak.to_dict(), _trial_row(2 * P, t0, t14, 6.5, 4.0, "2P", 12)])
    assert bls_search._odd_even_retest(lc, weak, trial_df) is weak
    strong = pd.Series(_trial_row(P, t0, t14, 6.5, 40.0, "P", 24))
    assert bls_search._odd_even_retest(lc, strong, pd.DataFrame([strong.to_dict()])) is strong
