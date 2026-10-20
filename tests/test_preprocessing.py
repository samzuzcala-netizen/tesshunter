"""Tests for preprocessing functions using synthetic data only (no network required)."""

import numpy as np
import pytest
import lightkurve as lk
from astropy.time import Time
from astropy import units as u

from tesshunter.utils import make_synthetic_lightcurve
from tesshunter.preprocessing import (
    apply_quality_mask,
    compute_flatten_window,
    flatten,
    remove_nans,
    normalise,
    sigma_clip_lightcurve,
    preprocess,
    mask_transits,
)


def _lc_from_df(df) -> lk.LightCurve:
    """Helper: build a LightCurve from a synthetic DataFrame."""
    time = Time(df["time"].values + 2457000, format="btjd", scale="tdb")
    return lk.LightCurve(
        time=time,
        flux=df["flux"].values * u.dimensionless_unscaled,
        flux_err=df["flux_err"].values * u.dimensionless_unscaled,
    )


@pytest.fixture
def synthetic_lc():
    df = make_synthetic_lightcurve(n_points=500, noise_ppt=1.0, seed=0)
    return _lc_from_df(df)


@pytest.fixture
def lc_with_nans(synthetic_lc):
    lc = synthetic_lc.copy()
    # Inject NaNs at known positions
    flux_arr = lc.flux.value.copy()
    flux_arr[[10, 50, 200]] = np.nan
    lc = lk.LightCurve(
        time=lc.time,
        flux=flux_arr * u.dimensionless_unscaled,
        flux_err=lc.flux_err,
    )
    return lc, [10, 50, 200]


def test_remove_nans_removes_all_nans(lc_with_nans):
    lc, nan_indices = lc_with_nans
    assert np.any(~np.isfinite(lc.flux.value)), "Test setup: should have NaNs"
    cleaned = remove_nans(lc)
    assert np.all(np.isfinite(cleaned.flux.value)), "All NaNs should be removed"
    assert len(cleaned) == len(lc) - len(nan_indices)


def test_remove_nans_preserves_clean_data(synthetic_lc):
    original_len = len(synthetic_lc)
    cleaned = remove_nans(synthetic_lc)
    assert len(cleaned) == original_len, "No cadences should be dropped from clean data"


def test_normalise_median_is_one(synthetic_lc):
    normed = normalise(synthetic_lc)
    median = np.nanmedian(normed.flux.value)
    assert abs(median - 1.0) < 0.01, f"Normalised median should be ~1.0, got {median:.4f}"


def test_sigma_clip_removes_upward_outliers():
    """sigma_clip_lightcurve clips only the upper tail to preserve transit dips."""
    df = make_synthetic_lightcurve(n_points=500, noise_ppt=1.0, seed=1)
    lc = _lc_from_df(df)
    flux_arr = lc.flux.value.copy()
    flux_arr[100] = 3.0    # large upward spike — should be removed
    flux_arr[200] = 0.99   # shallow downward dip — should be kept (simulates transit)
    lc_out = lk.LightCurve(
        time=lc.time,
        flux=flux_arr * u.dimensionless_unscaled,
        flux_err=lc.flux_err,
    )
    lc_out = normalise(lc_out)
    cleaned = sigma_clip_lightcurve(lc_out, sigma=4.0)
    # Upward spike should have been removed
    assert len(cleaned) < len(lc_out), "Upward spike cadence should be removed"
    # Flux max should now be close to 1.0 (spike gone)
    assert np.nanmax(cleaned.flux.value) < 1.5, "Upward spike should be clipped"
    # Downward dip (transit-like) should still be present
    assert np.nanmin(cleaned.flux.value) < 1.0, "Downward dips must be preserved for BLS"


def test_preprocess_returns_shorter_lc(synthetic_lc):
    original_len = len(synthetic_lc)
    cleaned, record = preprocess(synthetic_lc, do_flatten=False)
    # After preprocessing, length should be ≤ original
    assert len(cleaned) <= original_len
    assert record.original_cadences == original_len
    assert record.normalised is True


def test_preprocess_record_tracks_steps(synthetic_lc):
    _, record = preprocess(synthetic_lc, sigma=4.0, do_flatten=True)
    assert record.flattened is True
    assert record.sigma_clip_sigma == 4.0
    assert len(record.notes) > 0


# ── mask_transits tests ───────────────────────────────────────────────────────

def _lc_with_known_period(period=3.5, n_points=1000, noise_ppt=0.5):
    """Synthetic LC with a known-period transit signal injected."""
    df = make_synthetic_lightcurve(
        n_points=n_points,
        baseline_days=27.0,
        period_days=period,
        depth_ppt=5.0,
        duration_days=0.1,
        t0=2457001.0,   # epoch in BTJD-offset days; _lc_from_df adds 2457000
        noise_ppt=noise_ppt,
        seed=7,
    )
    return _lc_from_df(df), period, 2457001.0, 0.1   # lc, period, epoch_btjd, duration


def test_mask_transits_removes_in_transit_cadences():
    """mask_transits should remove cadences inside predicted transit windows."""
    lc, period, epoch, duration = _lc_with_known_period()
    lc_masked = mask_transits(lc, period=period, epoch=epoch, duration=duration)
    # Some cadences must have been removed
    assert len(lc_masked) < len(lc), "mask_transits should remove in-transit cadences"


def test_mask_transits_preserves_oot_cadences():
    """Out-of-transit cadences must survive masking."""
    lc, period, epoch, duration = _lc_with_known_period()
    lc_masked = mask_transits(lc, period=period, epoch=epoch, duration=duration,
                               width_factor=2.5)
    # With duration=0.1 d and period=3.5 d, masked fraction ≈ 2*2.5*0.1/3.5 ≈ 14%
    # So at least 80% of cadences should survive
    assert len(lc_masked) > 0.80 * len(lc), "Most OOT cadences should survive masking"


def test_mask_transits_wider_factor_removes_more():
    """A larger width_factor must remove more cadences than a smaller one."""
    lc, period, epoch, duration = _lc_with_known_period()
    lc_narrow = mask_transits(lc, period=period, epoch=epoch, duration=duration,
                               width_factor=1.0)
    lc_wide   = mask_transits(lc, period=period, epoch=epoch, duration=duration,
                               width_factor=4.0)
    assert len(lc_wide) < len(lc_narrow), "Wider mask must remove more cadences"


# ── flatten window computation tests ─────────────────────────────────────────

TWO_MIN = 2.0 / 1440.0  # 2-minute cadence in days


def _uniform_lc(baseline_days=10.0, cadence_days=TWO_MIN, noise=5e-4, seed=11):
    """Uniform-cadence LightCurve with tiny gaussian noise around 1.0."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, baseline_days, cadence_days)
    time = Time(t + 2457000, format="btjd", scale="tdb")
    flux = 1.0 + rng.normal(0, noise, len(t))
    return lk.LightCurve(
        time=time,
        flux=flux * u.dimensionless_unscaled,
        flux_err=np.full(len(t), noise) * u.dimensionless_unscaled,
    )


def test_compute_flatten_window_conversion_math():
    """window_days is converted to cadences using the measured median cadence."""
    time = np.arange(0, 10, TWO_MIN)  # 2-min cadence, 10 days, no gaps
    n_cad, eff_days, med_cad = compute_flatten_window(time, window_days=1.0)
    assert abs(med_cad - TWO_MIN) < 1e-12, "Median cadence should be 2 minutes"
    # 1.0 day / 2 min = 720 cadences, forced odd -> 721
    assert n_cad == 721, f"Expected 721 cadences for a 1-day window, got {n_cad}"
    assert abs(eff_days - n_cad * TWO_MIN) < 1e-9, "eff_days must equal n_cad*cadence"


def test_compute_flatten_window_default_is_one_day():
    """window_days=None must fall back to the 1.0-day default."""
    time = np.arange(0, 10, TWO_MIN)
    n_default, _, _ = compute_flatten_window(time, window_days=None)
    n_one_day, _, _ = compute_flatten_window(time, window_days=1.0)
    assert n_default == n_one_day == 721


def test_window_clamped_to_half_shortest_segment():
    """A large gap must clamp the window to half the shortest segment."""
    dt = 10.0 / 1440.0  # 10-min cadence
    # Two segments: 3 days and 10 days, separated by a 3-day gap
    time = np.concatenate([np.arange(0, 3, dt), np.arange(6, 16, dt)])
    n_cad, eff_days, _ = compute_flatten_window(time, window_days=4.0)
    assert eff_days <= 1.5 + dt, f"Window must clamp to ~1.5 d, got {eff_days:.3f} d"
    assert eff_days > 1.3, f"Window clamped too hard: {eff_days:.3f} d"
    assert n_cad % 2 == 1, "Savgol window must be odd"
    assert n_cad >= 5, "Savgol window must be >= 5 cadences"


def test_window_raised_for_max_transit_duration():
    """The window is raised to >= 3x the longest searched transit duration."""
    time = np.arange(0, 10, TWO_MIN)
    _, eff_days, _ = compute_flatten_window(
        time, window_days=0.2, max_transit_duration_days=0.3
    )
    assert 0.85 < eff_days < 0.95, (
        f"Window should be raised to ~0.9 d (3x0.3), got {eff_days:.3f} d"
    )


def test_preprocess_records_effective_window():
    """preprocess() must record the effective window in days and cadences."""
    lc = _uniform_lc()
    _, rec = preprocess(lc, do_flatten=True, window_days=1.0)
    assert rec.flattened is True
    assert rec.effective_window_cadences == 721
    assert rec.effective_window_days is not None
    assert abs(rec.effective_window_days - 721 * TWO_MIN) < 1e-6
    assert rec.median_branch_segments == 0, (
        "No segment should fall into lightkurve's per-segment-median branch"
    )


def test_flatten_window_deprecated_and_ignored():
    """Explicit flatten_window is ignored: no more 27-day-constant math."""
    lc = _uniform_lc()
    _, rec = preprocess(lc, do_flatten=True, flatten_window=0.5)
    # Old math: 0.5 * 27 d = 13.5 d window. New logic: 1.0-day default.
    assert rec.effective_window_days is not None
    assert rec.effective_window_days < 2.0, (
        f"flatten_window must be ignored; got {rec.effective_window_days:.2f} d window"
    )
    assert any("deprecated" in note for note in rec.notes)


# ── flatten failure honesty tests ────────────────────────────────────────────

def test_flatten_failure_sets_flattened_false(monkeypatch):
    """If lightkurve's flatten raises, the record must say so honestly."""
    def boom(self, *args, **kwargs):
        raise RuntimeError("savgol exploded")

    monkeypatch.setattr(lk.LightCurve, "flatten", boom)
    lc = _uniform_lc()
    cleaned, rec = preprocess(lc, do_flatten=True)
    assert rec.flattened is False, "flattened must be False when flatten fails"
    assert rec.flatten_error is not None and "savgol exploded" in rec.flatten_error
    assert any("flatten FAILED" in note for note in rec.notes)
    # The raw (undetrended) light curve is still returned, with an indicator
    assert len(cleaned) > 0
    assert cleaned.meta.get("FLATTEN_FAILED") is True


# ── quality mask tests ───────────────────────────────────────────────────────

def _lc_with_quality(n=500, n_flagged=6):
    """Uniform LC carrying a TESS-style quality column with flagged cadences."""
    t = np.arange(n) * TWO_MIN
    time = Time(t + 2457000, format="btjd", scale="tdb")
    quality = np.zeros(n, dtype=np.int32)
    flagged = np.linspace(10, n - 10, n_flagged).astype(int)
    quality[flagged] = 1  # AttitudeTweak — part of the default TESS bitmask
    lc = lk.LightCurve(
        time=time,
        flux=np.ones(n) * u.dimensionless_unscaled,
        flux_err=np.full(n, 1e-3) * u.dimensionless_unscaled,
    )
    lc["quality"] = quality
    lc.meta["MISSION"] = "TESS"
    return lc, n_flagged


def test_quality_mask_removes_flagged_cadences():
    """apply_quality_mask must drop cadences flagged in the quality column."""
    lc, n_flagged = _lc_with_quality()
    out = apply_quality_mask(lc)
    assert len(out) == len(lc) - n_flagged, (
        f"Expected {n_flagged} flagged cadences removed, "
        f"got {len(lc) - len(out)}"
    )


def test_preprocess_counts_quality_masked_cadences():
    """preprocess() wires in the quality mask and counts removed cadences."""
    lc, n_flagged = _lc_with_quality()
    _, rec = preprocess(lc, do_flatten=False)
    assert rec.quality_masked_cadences == n_flagged
    assert rec.after_quality_mask == len(lc) - n_flagged


def test_quality_mask_noop_without_quality_column(synthetic_lc):
    """Light curves without a quality column pass through unchanged, with a note."""
    out = apply_quality_mask(synthetic_lc)
    assert len(out) == len(synthetic_lc)
    _, rec = preprocess(synthetic_lc, do_flatten=False)
    assert rec.quality_masked_cadences == 0
    assert any("quality" in note.lower() and "skip" in note.lower()
               for note in rec.notes)


# ── transit mask passthrough tests ───────────────────────────────────────────

def test_flatten_transit_mask_passthrough(monkeypatch):
    """transit_mask must reach lightkurve's flatten(mask=...) unchanged.

    lightkurve 2.6.0 semantics: mask=True marks points NOT used to fit the
    trend, which matches our 'True = in-transit, exclude from fit' polarity.
    """
    captured = {}
    original = lk.LightCurve.flatten

    def spy(self, **kwargs):
        captured.update(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(lk.LightCurve, "flatten", spy)
    lc = _uniform_lc()
    tm = np.zeros(len(lc), dtype=bool)
    tm[100:150] = True
    flat, _ = flatten(lc, transit_mask=tm)
    assert "mask" in captured
    assert np.array_equal(captured["mask"], tm)
    assert flat.meta.get("FLATTEN_FAILED") is False


def test_flatten_transit_mask_length_mismatch_raises():
    """A wrong-length transit_mask is a caller bug and must raise."""
    lc = _uniform_lc()
    with pytest.raises(ValueError):
        flatten(lc, transit_mask=np.zeros(len(lc) + 5, dtype=bool))


def test_preprocess_realigns_transit_mask_after_cleaning():
    """preprocess() must re-align the transit mask after cadences are dropped."""
    lc = _uniform_lc()
    flux_arr = lc.flux.value.copy()
    flux_arr[[5, 25]] = np.nan  # will be dropped by remove_nans
    lc = lk.LightCurve(
        time=lc.time,
        flux=flux_arr * u.dimensionless_unscaled,
        flux_err=lc.flux_err,
    )
    tm = np.zeros(len(lc), dtype=bool)
    tm[200:260] = True
    cleaned, rec = preprocess(lc, do_flatten=True, transit_mask=tm)
    assert rec.flattened is True, "Flatten must succeed with a re-aligned mask"
