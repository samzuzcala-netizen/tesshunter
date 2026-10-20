"""Prompt 3 part A: the limb-darkened transit fit, its density test and the
odd/even template comparison. Synthetic batman injections, no network."""

import numpy as np
import pytest

from tesshunter import limb_darkening, stellar, survey, transit_fit as tf

U = (0.35, 0.25)
STAR = stellar.StellarParams(teff=5500.0, logg=4.5, radius=1.0, radius_err=0.05,
                             mass=1.0, mass_err=0.08, source="user")


def _curve(period, t0, rp, a_rs, b, cadence_min=2.0, baseline=54.0, noise=8e-4, seed=1,
           sec_depth=0.0):
    rng = np.random.default_rng(seed)
    t = 1000.0 + np.arange(0.0, baseline, cadence_min / 1440.0)
    keep = np.ones(t.size, bool)
    for g0, g1 in [(12.5, 14.0), (26.0, 28.5), (40.0, 41.2)]:
        keep &= ~((t - 1000.0 >= g0) & (t - 1000.0 < g1))
    t = t[keep]
    f = survey.transit_model(t, period=period, t0=t0, rp_rs=rp, b=b, a_rs=a_rs, u=U,
                             exp_time_days=cadence_min / 1440.0)
    if sec_depth > 0:
        dur = tf.transit_duration_t14(period, a_rs, b, rp)
        ph = ((t - t0 - 0.5 * period + 0.5 * period) % period) - 0.5 * period
        f[np.abs(ph) <= 0.5 * dur] -= sec_depth
    f = f + rng.normal(0.0, noise, t.size)
    return t, f, np.full(t.size, noise)


class _LC:
    """Minimal lightkurve-like container for the quick-fit entry points."""
    def __init__(self, t, f, e):
        self.time = type("T", (), {"value": t})()
        self.flux = type("F", (), {"value": f})()
        self.flux_err = type("E", (), {"value": e})()


def test_limb_darkening_tables_are_present_and_interpolate():
    assert limb_darkening.tables_available()
    sun = limb_darkening.quadratic_ld(5800.0, 4.4)
    assert sun.source == "claret2017_atlas" and sun.interpolated
    assert 0.2 < sun.u1 < 0.45 and 0.15 < sun.u2 < 0.4
    m = limb_darkening.quadratic_ld(3300.0, 4.9)
    assert m.source == "claret2017_phoenix"
    d = limb_darkening.quadratic_ld(None, None)
    assert d.teff_used == limb_darkening.DEFAULT_TEFF


def test_fit_recovers_injected_parameters_at_high_snr():
    P, t0, rp, a, b = 3.3, 1001.2, 0.08, 10.0, 0.3
    t, f, e = _curve(P, t0, rp, a, b)
    t14 = tf.transit_duration_t14(P, a, b, rp)
    fit = tf.fit_transit(t, f, e, period=P * 1.0003, t0=t0 + 0.2 * t14, duration=1.3 * t14,
                         depth_ppt=5.0, exp_time_days=2.0 / 1440.0, stellar=STAR)
    assert fit.success
    assert abs(fit.period - P) < 5e-4
    assert abs(fit.t0 - t0) < 0.002
    assert abs(fit.rp_rs - rp) < 0.003
    assert abs(fit.a_rs - a) < 1.0
    assert abs(fit.duration_days - t14) < 0.01
    d_max, _ = tf._model_depths(U, P, rp, a, b, t14)
    assert abs(fit.depth_ppt - d_max * 1000.0) < 0.15
    assert fit.depth_mean_ppt < fit.depth_ppt
    assert fit.rp_rearth is not None and abs(fit.rp_rearth - rp * 109.076) < 1.0
    assert not fit.a_rs_inconsistent
    assert fit.delta_bic > 100
    assert fit.odd_even["available"] and not fit.odd_even["significant"]


def test_density_prior_is_adopted_when_the_data_cannot_reject_it():
    """A low-SNR small planet must not be flagged and must keep a sane radius."""
    P, t0, rp, a, b = 7.45, 1002.7, 0.02, 20.0, 0.5
    t, f, e = _curve(P, t0, rp, a, b, noise=5e-4, baseline=81.0)
    t14 = tf.transit_duration_t14(P, a, b, rp)
    fit = tf.fit_transit(t, f, e, period=P, t0=t0, duration=t14, depth_ppt=0.4,
                         exp_time_days=2.0 / 1440.0, stellar=STAR)
    assert fit.success
    assert not fit.a_rs_inconsistent
    assert fit.density_dchi2 is not None and fit.density_dchi2 < tf.DENSITY_DCHI2_MIN
    assert fit.density_prior_adopted
    assert abs(fit.rp_rs - rp) < 0.004


def test_diluted_eclipse_is_flagged_inconsistent_with_the_star():
    """A 20%-deep eclipse on a companion star diluted x100 keeps its long
    ingress: the fit needs a star far less dense than the catalog one."""
    P, t0, rp, a, b = 3.1, 1001.5, 0.45, 5.0, 0.3
    t, f, e = _curve(P, t0, rp, a, b, baseline=54.0)
    f = 1.0 - (1.0 - f) / 100.0
    t14 = tf.transit_duration_t14(P, a, b, rp)
    fit = tf.fit_transit(t, f, e / 100.0, period=P, t0=t0, duration=t14, depth_ppt=2.0,
                         exp_time_days=2.0 / 1440.0, stellar=STAR)
    assert fit.success
    assert fit.a_rs_inconsistent
    assert fit.a_rs_direction == "low"
    assert fit.density_ratio < 1.0 / tf.DENSITY_RATIO_MAX
    assert fit.density_dchi2 > tf.DENSITY_DCHI2_MIN


def test_odd_even_template_separates_an_eb_folded_at_half_period():
    P_eb, t0 = 4.4, 1001.0
    t, f, e = _curve(P_eb, t0, 0.12, 8.0, 0.2, cadence_min=10.0, baseline=81.0, noise=1e-3,
                     sec_depth=0.006)
    t14 = tf.transit_duration_t14(P_eb, 8.0, 0.2, 0.12)
    lc = _LC(t, f, e)
    at_half = tf.odd_even_from_fit(lc, P_eb / 2.0, t0, t14, 14.0)
    at_true = tf.odd_even_from_fit(lc, P_eb, t0, t14, 14.0)
    assert at_half["available"] and at_half["significant"]
    assert at_half["delta_sigma"] > 10
    assert at_true["available"] and not at_true["significant"]


def test_fit_fails_cleanly_on_degenerate_input():
    t = np.linspace(1000.0, 1001.0, 10)
    fit = tf.fit_transit(t, np.ones(10), None, period=2.0, t0=1000.5, duration=0.1)
    assert not fit.success and fit.message


def test_stellar_density_and_a_rs_round_trip():
    rho, err, how = STAR.density_cgs()
    assert abs(rho - stellar.RHO_SUN_CGS) < 1e-6 and err > 0 and how == "mass_radius"
    a, a_err, _ = STAR.a_over_rs(365.25)
    assert abs(a - 215.0) < 1.5           # 1 AU in solar radii
    assert abs(stellar.density_from_a_rs(a, 365.25) - rho) < 1e-3
    sp = stellar.StellarParams(radius=0.5, mass=0.5)
    _, e2, how2 = sp.density_cgs()
    assert "assumed" in how2 and e2 > 0


def test_tic_cache_is_read_offline(tmp_path):
    import json
    p = tmp_path / "tic123.json"
    p.write_text(json.dumps({"tic_id": 123, "teff": 5000.0, "radius": 0.9, "mass": 0.9,
                             "source": "tic", "_fetched_epoch": 0.0}), encoding="utf-8")
    sp = stellar.fetch_tic_params(123, cache_dir=tmp_path, offline=True)
    assert sp is not None and sp.teff == 5000.0 and sp.notes  # stale note
    assert stellar.fetch_tic_params(999, cache_dir=tmp_path, offline=True) is None
