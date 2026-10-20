"""Tests for the post-vetting depth re-measurement pass.

The pass exists because the shipped depth is the raw BLS box depth, never
re-measured against the data after detrending, while the two-pass flatten
protects only ONE candidate — so every other planet is partly divided out by a
trend fitted through its own transits.

Its safety property is what most of these tests assert: it runs after detection
and after vetting, so it may only move a depth. It must never touch an
ephemeris and must always fall back to the BLS depth rather than fail.
"""

import numpy as np
import lightkurve as lk
import pytest
from astropy.time import Time
from astropy import units as u

import tesshunter.pipeline as pl


def _raw_lc(signals, baseline=50.0, cadence_min=2.0, noise_ppt=0.4,
            var_amp_ppt=0.0, var_period=7.3, seed=5):
    """Un-preprocessed light curve in plain BTJD floats.

    Times are used directly as the ephemeris frame, so epochs in these tests
    need no offset bookkeeping.
    """
    n = int(baseline * 1440.0 / cadence_min)
    t = 1000.0 + np.arange(n) * (cadence_min / 1440.0)
    flux = np.ones(n)
    if var_amp_ppt:
        flux += (var_amp_ppt / 1000.0) * np.sin(2 * np.pi * (t - t[0]) / var_period)
    for (period, t0, dur, depth_ppt) in signals:
        phase = ((t - t0 + 0.5 * period) % period) - 0.5 * period
        flux[np.abs(phase) <= 0.5 * dur] -= depth_ppt / 1000.0
    flux += np.random.default_rng(seed).normal(0.0, noise_ppt / 1000.0, n)
    lc = lk.LightCurve(
        time=Time(t, format="btjd", scale="tdb"),
        flux=flux * u.dimensionless_unscaled,
        flux_err=np.full(n, noise_ppt / 1000.0) * u.dimensionless_unscaled,
    )
    lc.meta["SECTOR"] = 1
    lc.meta["AUTHOR"] = "SPOC"
    return lc


def _planet(period, t0, dur, depth_ppt, num=1):
    return {"planet_num": num, "period_days": period, "epoch_btjd": t0,
            "duration_days": dur, "depth_ppt": depth_ppt}


# ── the depth estimator itself ────────────────────────────────────────────────

def test_measure_depth_recovers_an_injected_box():
    lc = _raw_lc([(5.0, 1002.0, 0.10, 3.0)], var_amp_ppt=0.0, noise_ppt=0.2)
    t = np.asarray(lc.time.value, float)
    f = np.asarray(lc.flux.value, float)
    d = pl._measure_depth_at_ephemeris(t, f, 5.0, 1002.0, 0.10)
    assert d is not None
    assert abs(d - 3.0) / 3.0 < 0.10


def test_measure_depth_returns_none_without_enough_baseline():
    t = np.linspace(0.0, 1.0, 50)
    f = np.ones_like(t)
    assert pl._measure_depth_at_ephemeris(t, f, 100.0, 0.5, 0.05) is None


def test_measure_depth_declines_when_the_baseline_is_inside_the_transit():
    """The failure the contamination guard exists for.

    When the FITTED duration badly underestimates the true T14, the
    out-of-transit annulus (0.75-2.5 x fitted duration) lands inside the real
    transit. The baseline is then depressed by more than the depth being
    claimed, and the pass must decline rather than ship a badly wrong number.
    """
    # True transit is 0.30 d wide; the "fitted" duration handed in is 0.06 d,
    # so the annulus spans 0.045-0.15 d from centre - entirely in transit.
    lc = _raw_lc([(6.0, 1002.0, 0.30, 5.0)], noise_ppt=0.1)
    t = np.asarray(lc.time.value, float)
    f = np.asarray(lc.flux.value, float)
    assert pl._measure_depth_at_ephemeris(t, f, 6.0, 1002.0, 0.06) is None
    # with the correct duration it measures fine
    ok = pl._measure_depth_at_ephemeris(t, f, 6.0, 1002.0, 0.30)
    assert ok is not None and abs(ok - 5.0) / 5.0 < 0.15


def test_measure_depth_tolerates_a_slightly_offset_local_baseline():
    """A local baseline is SUPPOSED to absorb residual trend; a small offset
    from the global median must not trigger the guard."""
    lc = _raw_lc([(5.0, 1002.0, 0.10, 3.0)], var_amp_ppt=8.0, noise_ppt=0.3)
    t = np.asarray(lc.time.value, float)
    f = np.asarray(lc.flux.value, float)
    assert pl._measure_depth_at_ephemeris(t, f, 5.0, 1002.0, 0.10) is not None


def test_measure_depth_is_insensitive_to_a_residual_slope():
    """A LOCAL baseline is the point: a leftover trend must cancel."""
    lc = _raw_lc([(5.0, 1002.0, 0.10, 3.0)], noise_ppt=0.1)
    t = np.asarray(lc.time.value, float)
    f = np.asarray(lc.flux.value, float)
    f_sloped = f * (1.0 + 0.002 * (t - t.mean()) / (t.max() - t.min()))
    d_flat = pl._measure_depth_at_ephemeris(t, f, 5.0, 1002.0, 0.10)
    d_slope = pl._measure_depth_at_ephemeris(t, f_sloped, 5.0, 1002.0, 0.10)
    assert abs(d_slope - d_flat) < 0.15


# ── the pass ──────────────────────────────────────────────────────────────────

def test_remeasure_beats_an_attenuated_bls_depth():
    """Truth 3.0 ppt; the stored BLS depth is attenuated to 1.6."""
    lc = _raw_lc([(5.0, 1002.0, 0.10, 3.0)], var_amp_ppt=10.0, noise_ppt=0.4)
    planets = [_planet(5.0, 1002.0, 0.10, 1.6)]
    n = pl._remeasure_depths(lc, planets, sigma_clip=4.0, window_days=None,
                             duration_max=0.15, mask_width_factor=7.0, notes=[])
    assert n == 1
    p = planets[0]
    # Prompt 3: the limb-darkened fit now supplies the depth when it converges;
    # the flat-bottom estimator is the fallback and is still recorded.
    assert p["depth_source"] in ("fit", "remeasured")
    assert p["depth_ppt_bls"] == 1.6
    assert abs(p["depth_ppt"] - 3.0) < abs(1.6 - 3.0)
    assert abs(p["depth_ppt_flat"] - 3.0) < abs(1.6 - 3.0)
    assert p["fit"]["success"]


def test_remeasure_helps_the_unprotected_second_planet():
    """Two planets; only one can ever be protected by the two-pass flatten."""
    lc = _raw_lc([(5.0, 1002.0, 0.10, 4.0), (11.3, 1004.0, 0.12, 2.5)],
                 var_amp_ppt=12.0, noise_ppt=0.4)
    planets = [_planet(5.0, 1002.0, 0.10, 4.0, 1),
               _planet(11.3, 1004.0, 0.12, 1.2, 2)]
    n = pl._remeasure_depths(lc, planets, sigma_clip=4.0, window_days=None,
                             duration_max=0.15, mask_width_factor=7.0, notes=[])
    assert n == 2
    assert abs(planets[1]["depth_ppt"] - 2.5) < abs(1.2 - 2.5)


def test_remeasure_never_moves_an_ephemeris():
    lc = _raw_lc([(5.0, 1002.0, 0.10, 3.0)])
    planets = [_planet(5.0, 1002.0, 0.10, 3.0)]
    before = {k: planets[0][k] for k in ("period_days", "epoch_btjd", "duration_days")}
    pl._remeasure_depths(lc, planets, sigma_clip=4.0, window_days=None,
                         duration_max=0.15, mask_width_factor=7.0, notes=[])
    for k, v in before.items():
        assert planets[0][k] == v


def test_remeasure_degrades_on_an_ultra_short_period():
    """A period so short there is no local out-of-transit baseline to use.

    The estimator must decline and the BLS depth must survive untouched — this
    is the WASP-18-class geometry that crashed the shipped pipeline.
    """
    lc = _raw_lc([(5.0, 1002.0, 0.10, 3.0)])
    planets = [_planet(0.30, 1000.5, 0.12, 9.0)]
    n = pl._remeasure_depths(lc, planets, sigma_clip=4.0, window_days=None,
                             duration_max=0.15, mask_width_factor=7.0, notes=[])
    assert n == 0
    assert planets[0]["depth_ppt"] == 9.0
    assert planets[0]["depth_source"] == "bls"


def test_remeasure_skips_and_notes_when_the_union_mask_swallows_the_lc():
    """Many planets whose masks together cover almost everything."""
    lc = _raw_lc([(5.0, 1002.0, 0.10, 3.0)])
    planets = [_planet(0.5 + 0.13 * i, 1000.2 + 0.05 * i, 0.14, 5.0, i + 1)
               for i in range(6)]
    notes = []
    n = pl._remeasure_depths(lc, planets, sigma_clip=4.0, window_days=None,
                             duration_max=0.15, mask_width_factor=7.0, notes=notes)
    assert n == 0
    assert all(p["depth_ppt"] == 5.0 for p in planets)
    assert any("skipped" in s for s in notes)


def test_remeasure_handles_no_planets():
    lc = _raw_lc([(5.0, 1002.0, 0.10, 3.0)])
    assert pl._remeasure_depths(lc, [], sigma_clip=4.0, window_days=None,
                                duration_max=0.15, mask_width_factor=7.0,
                                notes=[]) == 0


def test_remeasure_keeps_bls_depth_when_estimator_declines():
    """A period with no usable local baseline: the flat-bottom estimator must
    decline (n == 0, no flat depth). Prompt 3: the transit fit may still
    succeed here, because it fits the baseline jointly and locates the real
    0.10-day transit inside the 4-day box; when it does, its depth (near the
    3.0 ppt truth) is shipped, otherwise the BLS depth survives untouched."""
    lc = _raw_lc([(5.0, 1002.0, 0.10, 3.0)], baseline=6.0)
    planets = [_planet(5.0, 1002.0, 4.0, 7.7)]     # duration ~ the whole orbit
    n = pl._remeasure_depths(lc, planets, sigma_clip=4.0, window_days=None,
                             duration_max=0.15, mask_width_factor=0.01, notes=[])
    assert n == 0
    p = planets[0]
    assert p["depth_ppt_flat"] is None
    assert p["depth_ppt_bls"] == 7.7
    if p["depth_source"] == "fit":
        assert abs(p["depth_ppt"] - 3.0) < abs(7.7 - 3.0)
    else:
        assert p["depth_source"] == "bls" and p["depth_ppt"] == 7.7
