"""Prompt 3 part C1/C2: the period-aware secondary-eclipse test and the a/R*
consistency flag inside run_vetting, driven by a TransitFit dict."""

import numpy as np
import lightkurve as lk
from astropy.time import Time
from astropy import units as u

from tesshunter import stellar
from tesshunter.vetting import (
    SECONDARY_BOUND_MARGIN,
    VERDICT_FP,
    VERDICT_PROMISING,
    planetary_secondary_bound_ppt,
    run_vetting,
)


def _eclipsing_lc(period, t0, duration, primary_ppt, secondary_ppt,
                  baseline=27.0, cadence_min=2.0, noise_ppt=0.05, seed=4):
    n = int(baseline * 1440.0 / cadence_min)
    t = 1000.0 + np.arange(n) * (cadence_min / 1440.0)
    flux = np.ones(n)
    ph = ((t - t0 + 0.5 * period) % period) - 0.5 * period
    flux[np.abs(ph) <= 0.5 * duration] -= primary_ppt / 1000.0
    ph_sec = ((t - t0 - 0.5 * period + 0.5 * period) % period) - 0.5 * period
    flux[np.abs(ph_sec) <= 0.5 * duration] -= secondary_ppt / 1000.0
    flux += np.random.default_rng(seed).normal(0.0, noise_ppt / 1000.0, n)
    return lk.LightCurve(
        time=Time(t, format="btjd", scale="tdb"),
        flux=flux * u.dimensionless_unscaled,
        flux_err=np.full(n, noise_ppt / 1000.0) * u.dimensionless_unscaled,
    )


def _fit(rp_rs, a_rs, **kw):
    d = {"success": True, "method": "least_squares", "rp_rs": rp_rs, "rp_rs_err": 0.001,
         "a_rs": a_rs, "a_rs_err": 0.1, "b": 0.3, "b_err": 0.05, "duration_days": 0.08,
         "depth_ppt": 1000.0 * rp_rs ** 2, "depth_err": 0.01, "ld_source": "test",
         "rp_rearth": rp_rs * 1.35 * 109.076, "rp_rearth_err": 0.1,
         "rp_rjup": rp_rs * 1.35 * 9.7311, "a_rs_star": a_rs, "a_rs_ratio": 1.0,
         "density_ratio": 1.0, "density_dchi2": 0.0, "a_rs_inconsistent": False,
         "grazing": False, "consistency_note": "test", "odd_even": {"available": False}}
    d.update(kw)
    return d


STAR = stellar.StellarParams(teff=6226.0, logg=4.26, radius=1.35, radius_err=0.07,
                             mass=1.2, mass_err=0.17, source="user")
W18 = dict(period=0.9414525, t0=1000.4, duration=0.0854, primary_ppt=8.93, snr=733.0)


def test_secondary_bound_scales_with_separation():
    b_close, th_close, refl_close, t_close = planetary_secondary_bound_ppt(0.097, 3.5, 6226.0)
    b_far, th_far, refl_far, t_far = planetary_secondary_bound_ppt(0.097, 12.0, 6226.0)
    assert b_close > 10 * b_far
    assert t_close > t_far
    assert th_close > 0 and refl_close > 0
    assert planetary_secondary_bound_ppt(0.1, 0.5, 5000.0) == (0.0, 0.0, 0.0, 0.0)


def test_ultra_hot_jupiter_secondary_within_bound_does_not_stack():
    lc = _eclipsing_lc(W18["period"], W18["t0"], W18["duration"], W18["primary_ppt"], 0.07)
    res = run_vetting(lc, W18["period"], W18["t0"], W18["duration"], W18["primary_ppt"],
                      n_sectors=2, snr=W18["snr"], stellar_radius_rsun=1.35,
                      fit=_fit(0.097, 3.5), stellar=STAR)
    assert res.fit_available and res.secondary_planet_bound_ppt is not None
    assert res.secondary_eclipse_detected
    assert res.secondary_is_stellar is False
    assert res.secondary_is_planetary is True
    assert [f for f in res.high_risk_flags if "secondary" in f.lower()]
    assert res.verdict != VERDICT_FP


def test_late_m_companion_at_five_days_is_a_stellar_secondary():
    """Same 0.5 ppt secondary that the legacy ratio test exempted: at a/R* = 12
    an irradiated planet cannot produce it, so it stacks into an FP."""
    P = 5.0
    lc = _eclipsing_lc(P, 1000.6, 0.12, W18["primary_ppt"], 0.5)
    res = run_vetting(lc, P, 1000.6, 0.12, W18["primary_ppt"], n_sectors=2, snr=W18["snr"],
                      stellar_radius_rsun=1.35, fit=_fit(0.097, 12.0), stellar=STAR)
    assert res.secondary_eclipse_detected
    assert res.secondary_depth_ppt > SECONDARY_BOUND_MARGIN * res.secondary_planet_bound_ppt
    assert res.secondary_is_stellar is True
    assert res.secondary_is_planetary is False
    assert res.verdict == VERDICT_FP


def test_secondary_with_odd_even_is_still_a_hard_veto():
    lc = _eclipsing_lc(W18["period"], W18["t0"], W18["duration"], W18["primary_ppt"], 3.0)
    res = run_vetting(lc, W18["period"], W18["t0"], W18["duration"], W18["primary_ppt"],
                      n_sectors=2, snr=W18["snr"], stellar_radius_rsun=1.35,
                      fit=_fit(0.097, 3.5, odd_even={"available": True, "significant": True,
                                                     "delta_sigma": 12.0, "note": "test"}),
                      stellar=STAR)
    assert res.odd_even_mismatch
    assert res.hard_veto_flags and res.verdict == VERDICT_FP


def test_a_rs_inconsistent_is_a_high_risk_flag():
    lc = _eclipsing_lc(4.0, 1000.6, 0.12, 2.0, 0.0)
    res = run_vetting(lc, 4.0, 1000.6, 0.12, 2.0, n_sectors=2, snr=30.0,
                      stellar_radius_rsun=1.35,
                      fit=_fit(0.045, 2.5, a_rs_inconsistent=True, density_ratio=0.05,
                               density_dchi2=200.0, a_rs_star=12.0, a_rs_ratio=0.2),
                      stellar=STAR)
    assert res.a_rs_inconsistent
    assert any("density" in f for f in res.high_risk_flags)
    assert res.verdict != VERDICT_PROMISING


def test_clean_planet_with_fit_is_promising_and_reports_fitted_radius():
    lc = _eclipsing_lc(4.0, 1000.6, 0.12, 2.0, 0.0)
    res = run_vetting(lc, 4.0, 1000.6, 0.12, 2.0, n_sectors=2, snr=30.0,
                      stellar_radius_rsun=1.35, fit=_fit(0.045, 12.0), stellar=STAR)
    assert res.verdict == VERDICT_PROMISING
    assert abs(res.estimated_radius_rearth - 0.045 * 1.35 * 109.076) < 1e-6
    assert any("Transit fit" in n for n in res.notes)


def test_template_odd_even_supersedes_the_point_based_test():
    """A bright hot Jupiter whose in-transit POINT depths differ by parity at
    5 sigma (limb-darkened shape plus red noise) but whose per-event template
    depths agree must not carry an odd/even flag."""
    lc = _eclipsing_lc(3.0, 1000.6, 0.12, 20.0, 0.0)
    res = run_vetting(lc, 3.0, 1000.6, 0.12, 20.0, n_sectors=2, snr=250.0,
                      stellar_radius_rsun=1.35,
                      fit=_fit(0.14, 8.0, odd_even={"available": True, "significant": False,
                                                    "delta_sigma": 0.8, "n_odd": 4, "n_even": 4,
                                                    "note": "test"}),
                      stellar=STAR)
    res.odd_even_mismatch = True   # pretend the legacy test fired; recompute via a fresh call
    res2 = run_vetting(lc, 3.0, 1000.6, 0.12, 20.0, n_sectors=2, snr=250.0,
                       stellar_radius_rsun=1.35,
                       fit=_fit(0.14, 8.0, odd_even={"available": True, "significant": False,
                                                     "delta_sigma": 0.8, "n_odd": 4, "n_even": 4,
                                                     "note": "test"}),
                       stellar=STAR)
    assert res2.odd_even_mismatch is False
    assert not any("odd/even" in f for f in res2.high_risk_flags)
    # elevated SNR becomes a note because the fit is clean
    assert res2.snr_high and res2.snr_high_demoted
    assert not any("elevated SNR" in f for f in res2.medium_flags + res2.high_risk_flags)
    assert any("Elevated SNR" in n for n in res2.notes)


def test_elevated_snr_stays_high_risk_when_the_fit_sees_no_dip():
    lc = _eclipsing_lc(3.0, 1000.6, 0.12, 20.0, 0.0)
    res = run_vetting(lc, 3.0, 1000.6, 0.12, 20.0, n_sectors=2, snr=250.0,
                      stellar_radius_rsun=1.35,
                      fit=_fit(0.14, 8.0, depth_ppt=0.3, depth_err=0.2, depth_err_white=0.2),
                      stellar=STAR)
    assert res.fit_no_dip and not res.snr_high_demoted
    assert any("elevated SNR" in f for f in res.high_risk_flags)
    assert any("no significant transit" in f for f in res.high_risk_flags)


def test_no_fit_keeps_the_legacy_ratio_exemption():
    lc = _eclipsing_lc(W18["period"], W18["t0"], W18["duration"], W18["primary_ppt"], 0.07)
    res = run_vetting(lc, W18["period"], W18["t0"], W18["duration"], W18["primary_ppt"],
                      n_sectors=2, snr=W18["snr"], stellar_radius_rsun=1.35)
    assert not res.fit_available
    assert res.secondary_is_planetary is True
    assert res.verdict != VERDICT_FP
