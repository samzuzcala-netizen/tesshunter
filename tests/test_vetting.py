"""Tests for vetting, V-shape, median-error, and contamination checks (no network)."""

import numpy as np
import pytest
import lightkurve as lk
from astropy.time import Time
from astropy import units as u

from tesshunter.utils import make_synthetic_lightcurve, phase_fold
from tesshunter.vetting import (
    run_vetting,
    check_depth,
    check_v_shape,
    check_secondary_eclipse,
    check_sector_consistency,
    median_error,
    implied_companion_radius_rjup,
    VERDICT_FP,
    VERDICT_AMBIGUOUS,
    RADIUS_HARD_VETO_RJUP,
    V_SHAPE_HIGH_RATIO,
    V_SHAPE_MEDIUM_RATIO,
)
from tesshunter.contamination import (
    estimate_aperture_radius_px,
    classify_neighbour,
    _prf_leakage,
)


def _lc_from_df(df) -> lk.LightCurve:
    time = Time(df["time"].values + 2457000, format="btjd", scale="tdb")
    return lk.LightCurve(
        time=time,
        flux=df["flux"].values * u.dimensionless_unscaled,
        flux_err=df["flux_err"].values * u.dimensionless_unscaled,
    )


def _lc_from_arrays(t, flux, err=0.001) -> lk.LightCurve:
    return lk.LightCurve(
        time=Time(t + 2457000, format="btjd", scale="tdb"),
        flux=flux * u.dimensionless_unscaled,
        flux_err=np.full(t.size, err) * u.dimensionless_unscaled,
    )


# ── V1: radius-aware depth veto ───────────────────────────────────────────────

def test_radius_aware_veto_hot_jupiter_around_m_dwarf():
    """Depth 110 ppt around a 0.3 R_Sun star implies ~1 R_Jup — NOT hard-vetoed."""
    r_rjup = implied_companion_radius_rjup(110.0, 0.3)
    assert r_rjup is not None and r_rjup < RADIUS_HARD_VETO_RJUP, (
        f"110 ppt around 0.3 R_Sun implies {r_rjup:.2f} R_Jup — planet-sized"
    )
    hard, high, note = check_depth(110.0, stellar_radius_rsun=0.3)
    assert not hard, f"Hot Jupiter around M dwarf must not be hard-vetoed: {note}"
    assert not high, f"~1 R_Jup should not even be high-risk: {note}"


def test_depth_veto_without_radius_keeps_legacy_behavior():
    """Same 110 ppt depth with unknown stellar radius keeps the old ppt veto."""
    hard, high, note = check_depth(110.0)
    assert hard, f"Without a stellar radius, depth > 100 ppt must hard-veto: {note}"


def test_radius_aware_hard_veto_for_stellar_companion():
    """80 ppt around a 1.35 R_Sun star implies > 2.5 R_Jup — hard veto."""
    r_rjup = implied_companion_radius_rjup(80.0, 1.35)
    assert r_rjup > RADIUS_HARD_VETO_RJUP
    hard, _, _ = check_depth(80.0, stellar_radius_rsun=1.35)
    assert hard, "Implied stellar-companion radius must hard-veto"


def test_run_vetting_radius_aware_not_fp():
    """run_vetting with Rs=0.3 and depth 110 ppt must not auto-FP the candidate."""
    df = make_synthetic_lightcurve(
        n_points=2000, baseline_days=27.0, period_days=3.5,
        depth_ppt=110.0, duration_days=0.1, t0=1.0, noise_ppt=0.5, seed=3,
    )
    lc = _lc_from_df(df)
    result = run_vetting(
        lc, period_days=3.5, epoch_btjd=2457001.0, duration_days=0.1,
        depth_ppt=110.0, n_sectors=2, snr=50.0, stellar_radius_rsun=0.3,
    )
    assert result.verdict != VERDICT_FP, (
        f"Hot Jupiter around M dwarf mislabeled FP: hard={result.hard_veto_flags}, "
        f"high={result.high_risk_flags}"
    )
    assert result.implied_radius_rjup == pytest.approx(0.968, abs=0.02)
    assert not result.depth_too_deep


def test_run_vetting_no_radius_same_depth_is_fp():
    """The same light curve without a stellar radius keeps the old FP verdict."""
    df = make_synthetic_lightcurve(
        n_points=2000, baseline_days=27.0, period_days=3.5,
        depth_ppt=110.0, duration_days=0.1, t0=1.0, noise_ppt=0.5, seed=3,
    )
    lc = _lc_from_df(df)
    result = run_vetting(
        lc, period_days=3.5, epoch_btjd=2457001.0, duration_days=0.1,
        depth_ppt=110.0, n_sectors=2, snr=50.0,
    )
    assert result.verdict == VERDICT_FP
    assert result.depth_too_deep


def test_depth_and_snr_flags_do_not_stack_to_fp():
    """Depth- and SNR-based high-risk flags share one amplitude cause → ambiguous."""
    df = make_synthetic_lightcurve(
        n_points=2000, baseline_days=27.0, period_days=3.5,
        depth_ppt=50.0, duration_days=0.1, t0=1.0, noise_ppt=0.5, seed=4,
    )
    lc = _lc_from_df(df)
    result = run_vetting(
        lc, period_days=3.5, epoch_btjd=2457001.0, duration_days=0.1,
        depth_ppt=50.0, n_sectors=2, snr=200.0,
    )
    assert result.depth_large and result.snr_high, "Test setup: both flags expected"
    assert len(result.high_risk_flags) == 2
    assert result.verdict == VERDICT_AMBIGUOUS, (
        f"Depth+SNR pair alone must not auto-FP, got {result.verdict}"
    )


# ── Flag lists (contract for reporting) ───────────────────────────────────────

def test_flags_lists_populated_and_aliased():
    """flags_hard/high/medium are populated and stay in sync with legacy lists."""
    df = make_synthetic_lightcurve(
        n_points=1500, baseline_days=27.0, period_days=3.5,
        depth_ppt=110.0, duration_days=0.1, t0=1.0, noise_ppt=0.5, seed=5,
    )
    lc = _lc_from_df(df)
    result = run_vetting(
        lc, period_days=3.5, epoch_btjd=2457001.0, duration_days=0.1,
        depth_ppt=110.0, n_sectors=1, snr=10.0, catalog_ok=False,
    )
    # Hard veto (no radius, 110 ppt) → flags_hard populated
    assert result.flags_hard, "flags_hard must contain the depth hard veto"
    assert result.flags_hard is result.hard_veto_flags
    assert result.flags_high is result.high_risk_flags
    assert result.flags_medium is result.medium_flags
    # Medium flags: single sector + catalog failure
    assert any("single sector" in f for f in result.flags_medium)
    assert any("catalog" in f for f in result.flags_medium)
    # Every flag entry is a human-readable string
    for flag_list in (result.flags_hard, result.flags_high, result.flags_medium):
        assert all(isinstance(f, str) and f for f in flag_list)


# ── V2: median-error math ─────────────────────────────────────────────────────

def test_median_error_math():
    """sigma_median = 1.4826 × MAD / sqrt(N) × red-noise inflation (2)."""
    values = np.array([0.0, 1.0] * 50)   # median 0.5, MAD exactly 0.5
    expected = 1.4826 * 0.5 / np.sqrt(25) * 2.0
    assert median_error(values, 25) == pytest.approx(expected, rel=1e-12)
    # red_noise_factor scales linearly
    assert median_error(values, 25, red_noise_factor=1.0) == pytest.approx(
        expected / 2.0, rel=1e-12
    )
    # degenerate inputs
    assert median_error(np.array([]), 25) == 0.0
    assert median_error(values, 0) == 0.0


def test_secondary_eclipse_uses_median_error():
    """A 2 ppt secondary in 1 ppt/point noise is invisible to the old per-point
    3σ threshold (3 ppt) but obvious against the error on a median of N points."""
    rng = np.random.default_rng(11)
    n = 4000
    t = np.linspace(0.0, 27.0, n)
    period, dur = 3.0, 0.15
    ph = phase_fold(t, period, 1.0)
    flux = np.ones(n)
    flux[np.abs(ph) < dur / period / 2] -= 0.008                    # primary 8 ppt
    flux[np.abs(np.abs(ph) - 0.5) < dur / period / 2] -= 0.002      # secondary 2 ppt
    flux += rng.normal(0, 0.001, n)                                  # 1 ppt/point noise
    lc = _lc_from_arrays(t, flux)
    flagged, sec_ppt, note = check_secondary_eclipse(lc, period, 2457001.0, dur)
    assert flagged, (
        f"2 ppt secondary must be flagged with median-error stats: {note}"
    )
    assert 1.0 < sec_ppt < 3.0


def test_secondary_eclipse_control_not_flagged():
    """Without a secondary eclipse the check must stay quiet."""
    rng = np.random.default_rng(12)
    n = 4000
    t = np.linspace(0.0, 27.0, n)
    period, dur = 3.0, 0.15
    ph = phase_fold(t, period, 1.0)
    flux = np.ones(n)
    flux[np.abs(ph) < dur / period / 2] -= 0.008
    flux += rng.normal(0, 0.001, n)
    lc = _lc_from_arrays(t, flux)
    flagged, _, note = check_secondary_eclipse(lc, period, 2457001.0, dur)
    assert not flagged, f"No secondary present but check flagged: {note}"


# ── V3: V-shape check ─────────────────────────────────────────────────────────

def _v_shaped_lc(seed=21, depth=0.010, period=3.5, dur=0.12, noise=0.0005):
    """Synthetic LC with a triangular (V-shaped) dip — grazing-EB-like."""
    rng = np.random.default_rng(seed)
    n = 4000
    t = np.linspace(0.0, 27.0, n)
    pd_days = phase_fold(t, period, 1.0) * period
    triangle = np.clip(1.0 - np.abs(pd_days) / (dur / 2), 0.0, 1.0)
    flux = 1.0 - depth * triangle + rng.normal(0, noise, n)
    return _lc_from_arrays(t, flux, err=noise), period, 2457001.0, dur


def test_v_shape_flags_triangle_as_high():
    lc, period, epoch, dur = _v_shaped_lc()
    ratio, flag, note = check_v_shape(lc, period, epoch, dur)
    assert ratio is not None and ratio < V_SHAPE_HIGH_RATIO, note
    assert flag == "high", f"Triangular dip must flag high: {note}"


def test_v_shape_passes_flat_bottomed_box():
    df = make_synthetic_lightcurve(
        n_points=4000, baseline_days=27.0, period_days=3.5,
        depth_ppt=10.0, duration_days=0.12, t0=1.0, noise_ppt=0.5, seed=22,
    )
    lc = _lc_from_df(df)
    ratio, flag, note = check_v_shape(lc, 3.5, 2457001.0, 0.12)
    assert ratio is not None and ratio >= V_SHAPE_MEDIUM_RATIO, note
    assert flag == "none", f"Flat-bottomed transit must not flag: {note}"


def test_v_shape_wired_into_run_vetting():
    """A V-shaped event adds a high-risk flag but is not an auto-FP alone."""
    lc, period, epoch, dur = _v_shaped_lc()
    result = run_vetting(
        lc, period_days=period, epoch_btjd=epoch, duration_days=dur,
        depth_ppt=10.0, n_sectors=2, snr=20.0,
    )
    assert result.v_shape_flag == "high"
    assert result.v_shape_ratio is not None and result.v_shape_ratio < V_SHAPE_HIGH_RATIO
    assert any("V-shaped" in f for f in result.high_risk_flags)
    assert result.verdict == VERDICT_AMBIGUOUS, (
        f"Single V-shape flag must give ambiguous, not {result.verdict}"
    )


def test_v_shape_graceful_on_insufficient_data():
    """Too few in-window cadences → (None, 'none', explanatory note)."""
    t = np.linspace(0.0, 27.0, 30)
    flux = np.ones(30)
    lc = _lc_from_arrays(t, flux)
    ratio, flag, note = check_v_shape(lc, 3.5, 2457001.0, 0.05)
    assert ratio is None
    assert flag == "none"
    assert note


# ── V4: aperture-aware contamination ──────────────────────────────────────────

def test_aperture_radius_ramp():
    """Brighter target → bigger aperture; 1.5–2.5 px linear ramp."""
    assert estimate_aperture_radius_px(4.0) == 2.5
    assert estimate_aperture_radius_px(14.0) == 1.5
    assert estimate_aperture_radius_px(9.0) == pytest.approx(2.0)
    radii = [estimate_aperture_radius_px(m) for m in np.linspace(4, 15, 12)]
    assert all(a >= b for a, b in zip(radii, radii[1:])), "must be non-increasing"


def test_prf_leakage_is_full_inside_aperture():
    """A neighbour inside the aperture leaks 100% of its flux."""
    assert _prf_leakage(1.0 * 21.0, r_aperture_px=2.0) == 1.0
    # Outside the aperture the Gaussian falls off with distance beyond the edge
    outside = _prf_leakage(4.0 * 21.0, r_aperture_px=2.0)
    assert 0.0 < outside < 1.0
    assert outside == pytest.approx(np.exp(-0.5 * (2.0 / 1.5) ** 2))


def test_neighbour_inside_aperture_never_ruled_out():
    """A faint star 1 px away contributes ~100% of its flux — never RULED_OUT."""
    nb = classify_neighbour(
        sep_arcsec=21.0,          # 1 px
        tmag_neighbour=17.5,      # very faint (ΔTmag = 7.5)
        target_tmag=10.0,
        depth_ppt=1.0,
    )
    assert nb.leakage_fraction == 1.0, "Inside the aperture leakage must be 100%"
    assert nb.risk_level != "RULED_OUT", (
        "Neighbour within r_aperture + 1 px must never get RULED_OUT status"
    )


def test_distant_faint_neighbour_still_ruled_out():
    """Far outside the aperture the physically-impossible tier still applies."""
    nb = classify_neighbour(
        sep_arcsec=5.5 * 21.0,    # 5.5 px, aperture ≈ 1.8 px at Tmag 10
        tmag_neighbour=17.5,
        target_tmag=10.0,
        depth_ppt=1.0,
    )
    assert nb.risk_level == "RULED_OUT"


def test_close_viable_contaminant_is_high_risk():
    """A moderately faint star inside the aperture is a HIGH-risk contaminant."""
    nb = classify_neighbour(
        sep_arcsec=21.0,          # 1 px
        tmag_neighbour=14.0,      # ΔTmag = 4 → flux ratio ~2.5%
        target_tmag=10.0,
        depth_ppt=5.0,
    )
    assert nb.risk_level == "HIGH", (
        f"Expected HIGH, got {nb.risk_level} "
        f"(corrected depth {nb.leakage_corrected_depth_ppt:.0f} ppt)"
    )
    assert nb.is_viable_contaminant


# ── V5: per-unit depth consistency ────────────────────────────────────────────

def _two_chunk_lc(depth1, depth2, seed=31, period=3.0, dur=0.15, noise=0.0005):
    """LC with two observing units separated by a 2-day gap."""
    rng = np.random.default_rng(seed)
    t = np.concatenate([np.linspace(0.0, 12.0, 1200), np.linspace(14.0, 26.0, 1200)])
    ph = phase_fold(t, period, 1.0)
    in_tr = np.abs(ph) < dur / period / 2
    flux = np.ones(t.size)
    flux[in_tr & (t < 13.0)] -= depth1
    flux[in_tr & (t > 13.0)] -= depth2
    flux += rng.normal(0, noise, t.size)
    return _lc_from_arrays(t, flux, err=noise), period, 2457001.0, dur


def test_sector_consistency_count_only_legacy():
    """Without the new kwargs the old count-only behaviour is unchanged."""
    flagged, note = check_sector_consistency(1)
    assert flagged and "only 1 sector" in note
    flagged, note = check_sector_consistency(3)
    assert not flagged


def test_sector_consistency_flags_depth_mismatch():
    lc, period, epoch, dur = _two_chunk_lc(0.005, 0.015)
    flagged, note = check_sector_consistency(
        2, lc=lc, period_days=period, epoch_btjd=epoch,
        duration_days=dur, depth_ppt=10.0,
    )
    assert flagged, f"5 vs 15 ppt per-unit depths must flag: {note}"
    assert "disagree" in note


def test_sector_consistency_passes_consistent_depths():
    lc, period, epoch, dur = _two_chunk_lc(0.010, 0.010)
    flagged, note = check_sector_consistency(
        2, lc=lc, period_days=period, epoch_btjd=epoch,
        duration_days=dur, depth_ppt=10.0,
    )
    assert not flagged, f"Consistent depths wrongly flagged: {note}"


def test_sector_depth_mismatch_wired_into_run_vetting():
    lc, period, epoch, dur = _two_chunk_lc(0.005, 0.015)
    result = run_vetting(
        lc, period_days=period, epoch_btjd=epoch, duration_days=dur,
        depth_ppt=10.0, n_sectors=2, snr=20.0,
    )
    assert result.sector_depth_mismatch
    assert any("disagree" in f for f in result.flags_medium)
    assert not result.single_sector_only
