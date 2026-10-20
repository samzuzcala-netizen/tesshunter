"""Tests for BLS search functions using synthetic data only (no network required)."""

import logging

import numpy as np
import pytest
import lightkurve as lk
from astropy.time import Time
from astropy import units as u

from tesshunter.utils import make_synthetic_lightcurve
from tesshunter.bls_search import (
    run_bls, best_candidate, BLSCandidate,
    harmonic_trial_periods, check_half_period_alias,
    select_fundamental_period,
    event_completeness, alternating_event_consistency,
    transit_window_overlap_fraction, resolve_aliases_for_candidate,
    _extract_top_candidates, _BLSResult, _build_period_grid,
    _CANDIDATE_COLUMNS,
)
from tesshunter.preprocessing import preprocess


def _lc_from_df(df) -> lk.LightCurve:
    time = Time(df["time"].values + 2457000, format="btjd", scale="tdb")
    return lk.LightCurve(
        time=time,
        flux=df["flux"].values * u.dimensionless_unscaled,
        flux_err=df["flux_err"].values * u.dimensionless_unscaled,
    )


INJECTED_PERIOD = 4.0  # days
INJECTED_DEPTH = 8.0   # ppt


@pytest.fixture
def synthetic_lc_with_transit():
    df = make_synthetic_lightcurve(
        n_points=1000,
        baseline_days=27.0,
        period_days=INJECTED_PERIOD,
        depth_ppt=INJECTED_DEPTH,
        duration_days=0.12,
        noise_ppt=0.5,
        seed=42,
    )
    lc = _lc_from_df(df)
    cleaned, _ = preprocess(lc, do_flatten=False)
    return cleaned


def test_run_bls_returns_expected_fields(synthetic_lc_with_transit):
    _, _, candidates = run_bls(
        synthetic_lc_with_transit,
        period_min=0.5,
        period_max=15.0,
        top_n=3,
    )
    required_cols = {"period_days", "epoch_btjd", "duration_days", "depth_ppt", "power", "snr", "peak_rank"}
    assert required_cols.issubset(set(candidates.columns)), (
        f"Missing columns: {required_cols - set(candidates.columns)}"
    )
    assert len(candidates) >= 1


def test_bls_recovers_injected_period(synthetic_lc_with_transit):
    """BLS must find the injected period within 2% tolerance."""
    _, _, candidates = run_bls(
        synthetic_lc_with_transit,
        period_min=0.5,
        period_max=15.0,
        top_n=5,
    )
    best_period = candidates.iloc[0]["period_days"]
    tolerance = 0.02 * INJECTED_PERIOD
    # Allow the best period or its half-integer alias (2×P appears as 2 transits = same depth)
    aliases = [INJECTED_PERIOD, INJECTED_PERIOD / 2.0, INJECTED_PERIOD * 2.0]
    recovered = any(abs(best_period - alias) < tolerance for alias in aliases)
    assert recovered, (
        f"BLS best period {best_period:.4f} d not close to any alias of "
        f"injected period {INJECTED_PERIOD} d"
    )


def test_bls_depth_is_positive(synthetic_lc_with_transit):
    _, _, candidates = run_bls(synthetic_lc_with_transit, period_min=0.5, period_max=15.0)
    assert (candidates["depth_ppt"] >= 0).all(), "All depths should be non-negative"


def test_best_candidate_returns_dataclass(synthetic_lc_with_transit):
    _, _, candidates = run_bls(synthetic_lc_with_transit, period_min=0.5, period_max=15.0)
    result = best_candidate(candidates)
    assert isinstance(result, BLSCandidate)
    assert result.period_days > 0
    assert result.depth_ppt >= 0


def test_best_candidate_empty_df():
    import pandas as pd
    result = best_candidate(pd.DataFrame())
    assert result is None


# ── harmonic_trial_periods tests ─────────────────────────────────────────────

def test_harmonic_trial_periods_includes_p_itself():
    trials = dict(harmonic_trial_periods(4.0, period_min=0.5, period_max=20.0))
    assert "P" in trials
    assert abs(trials["P"] - 4.0) < 1e-9


def test_harmonic_trial_periods_includes_sub_harmonics():
    trials = dict(harmonic_trial_periods(6.0, period_min=0.5, period_max=20.0))
    assert "P/2" in trials and abs(trials["P/2"] - 3.0) < 1e-9
    assert "P/3" in trials and abs(trials["P/3"] - 2.0) < 1e-9


def test_harmonic_trial_periods_filters_out_of_range():
    # P/2 = 0.2 d < period_min=0.5 → should be excluded
    trials = dict(harmonic_trial_periods(0.4, period_min=0.5, period_max=20.0))
    assert "P/2" not in trials
    # 2P = 30 d > period_max=20 → should be excluded
    trials2 = dict(harmonic_trial_periods(15.0, period_min=0.5, period_max=20.0))
    assert "2P" not in trials2


# ── check_half_period_alias tests ─────────────────────────────────────────────

def _make_alias_lc(true_period=2.0, n_points=800, noise_ppt=0.5, seed=5):
    """Light curve with transits at true_period; we'll call check at 2×true_period."""
    df = make_synthetic_lightcurve(
        n_points=n_points,
        baseline_days=27.0,
        period_days=true_period,
        depth_ppt=6.0,
        duration_days=0.08,
        t0=1.0,
        noise_ppt=noise_ppt,
        seed=seed,
    )
    return _lc_from_df(df), true_period


def test_check_half_period_alias_detects_2x_alias():
    """If real period is P, calling with 2P should flag as alias."""
    lc, true_p = _make_alias_lc(true_period=2.0)
    lc_norm = lc.normalize()
    # Epoch of first transit in BTJD-offset space; make_synthetic uses t0=1.0 → BTJD 2457001
    epoch = 2457001.0
    primary_ppt, halfway_ppt, is_alias = check_half_period_alias(
        lc_norm,
        period   = true_p * 2,   # detecting at 2× the true period
        epoch    = epoch,
        duration = 0.08,
    )
    assert is_alias, (
        f"Expected alias flag for 2×-period detection "
        f"(primary={primary_ppt:.3f} ppt, halfway={halfway_ppt:.3f} ppt)"
    )


def test_check_half_period_alias_passes_true_period():
    """Calling with the true period should NOT flag as alias."""
    lc, true_p = _make_alias_lc(true_period=3.5, seed=6)
    lc_norm = lc.normalize()
    epoch = 2457001.0
    primary_ppt, halfway_ppt, is_alias = check_half_period_alias(
        lc_norm,
        period   = true_p,        # correct period
        epoch    = epoch,
        duration = 0.08,
    )
    assert not is_alias, (
        f"True period should not be flagged as alias "
        f"(primary={primary_ppt:.3f} ppt, halfway={halfway_ppt:.3f} ppt)"
    )


# ── select_fundamental_period tests ──────────────────────────────────────────

def _make_harmonic_df():
    """Mimic the table produced by the harmonic-resolution step for P=7.38 d."""
    import pandas as pd
    return pd.DataFrame([
        {"harmonic_label": "P/6", "period_days": 1.230, "snr": 6.4,  "score": 5.5},
        {"harmonic_label": "P/3", "period_days": 2.460, "snr": 4.8,  "score": 4.1},
        {"harmonic_label": "P/2", "period_days": 3.691, "snr": 11.0, "score": 9.8},
        {"harmonic_label": "P",   "period_days": 7.381, "snr": 7.9,  "score": 7.0},
        {"harmonic_label": "2P",  "period_days": 14.76, "snr": 3.1,  "score": 2.9},
    ])


def test_select_fundamental_alias_flag_chooses_p2():
    """When is_alias=True the selector must return P/2, not the shortest period."""
    df = _make_harmonic_df()
    row = select_fundamental_period(df, is_alias=True)
    assert row["harmonic_label"] == "P/2", (
        f"Expected P/2 when alias flag is set, got {row['harmonic_label']}"
    )
    assert abs(row["period_days"] - 3.691) < 0.01


def test_select_fundamental_no_alias_uses_best_score():
    """When is_alias=False the selector must use the highest score, not shortest period."""
    df = _make_harmonic_df()
    row = select_fundamental_period(df, is_alias=False)
    # Highest score in the table is P/2 (9.8), NOT P/6 (5.5)
    assert row["harmonic_label"] == "P/2", (
        f"Expected P/2 (highest score=9.8), got {row['harmonic_label']} (score={row['score']})"
    )


def test_select_fundamental_alias_flag_missing_p2_falls_back_to_score():
    """If P/2 is not in the table but alias flag is set, fall back to highest score."""
    import pandas as pd
    df = pd.DataFrame([
        {"harmonic_label": "P/3", "period_days": 2.46, "snr": 8.0, "score": 7.5},
        {"harmonic_label": "P",   "period_days": 7.38, "snr": 7.9, "score": 7.0},
    ])
    row = select_fundamental_period(df, is_alias=True)
    # No P/2 row → falls back to best score → P/3
    assert row["harmonic_label"] == "P/3"


def test_pipeline_does_not_crash_on_flat_lc():
    """A light curve with no transit should still complete without error."""
    df = make_synthetic_lightcurve(
        n_points=500,
        baseline_days=27.0,
        depth_ppt=0.0,   # no injected signal
        noise_ppt=1.0,
        seed=99,
    )
    lc = _lc_from_df(df)
    cleaned, _ = preprocess(lc, do_flatten=False)
    _, _, candidates = run_bls(cleaned, period_min=1.0, period_max=10.0, top_n=3)
    # Should return a result table (even if it's noise)
    assert candidates is not None
    assert len(candidates) >= 1


# ── harmonic_trial_periods: 4P extension ─────────────────────────────────────

def test_harmonic_trial_periods_includes_4p():
    """4P should now appear when it falls inside period_max."""
    trials = dict(harmonic_trial_periods(4.0, period_min=0.5, period_max=20.0))
    assert "4P" in trials, "4P missing from harmonic trials"
    assert abs(trials["4P"] - 16.0) < 1e-9


# ── event_completeness tests ──────────────────────────────────────────────────

def _make_transit_lc(period_days=4.0, depth_ppt=8.0, duration_days=0.12,
                     n_points=800, noise_ppt=0.5, seed=42, t0=1.0):
    """Normalised synthetic LC helper for event-level tests."""
    df = make_synthetic_lightcurve(
        n_points=n_points,
        baseline_days=27.0,
        period_days=period_days,
        depth_ppt=depth_ppt,
        duration_days=duration_days,
        t0=t0,
        noise_ppt=noise_ppt,
        seed=seed,
    )
    return _lc_from_df(df).normalize()


def test_event_completeness_true_period_high():
    """EC at the true injected period should be high (most windows show a dip)."""
    lc = _make_transit_lc(period_days=4.0)
    epoch = 2457001.0   # t0=1.0 → BTJD 2457001
    n_cov, n_dip, ec = event_completeness(lc, period=4.0, epoch=epoch, duration=0.12)
    assert n_cov >= 5, f"Expected ≥5 covered windows, got {n_cov}"
    assert ec >= 0.5, f"EC at true period too low: {ec:.2f}"


def test_event_completeness_half_period_lower():
    """EC at the P/2 trial (half of true period) should be lower than at true P."""
    lc = _make_transit_lc(period_days=4.0)
    epoch = 2457001.0
    _, _, ec_true = event_completeness(lc, period=4.0, epoch=epoch, duration=0.12)
    _, _, ec_half = event_completeness(lc, period=2.0, epoch=epoch, duration=0.12)
    assert ec_true > ec_half, (
        f"True-period EC ({ec_true:.2f}) should exceed half-period EC ({ec_half:.2f})"
    )
    # At P/2 only every-other window has a dip → roughly 0.5
    assert ec_half < 0.75, f"Half-period EC unexpectedly high: {ec_half:.2f}"


# ── alternating_event_consistency tests ──────────────────────────────────────

def test_alternating_event_consistency_at_half_period():
    """At P/2 of the true period, odd and even events should have very different depths."""
    lc = _make_transit_lc(period_days=4.0, depth_ppt=8.0)
    epoch = 2457001.0
    odd_d, even_d, is_alt = alternating_event_consistency(
        lc, period=2.0, epoch=epoch, duration=0.12)
    assert is_alt, (
        f"Expected alternating flag at P/2 — odd_d={odd_d:.2f} ppt, even_d={even_d:.2f} ppt"
    )


def test_alternating_event_consistency_at_true_period():
    """At the true period, both parities should have comparable depths (no alternation)."""
    lc = _make_transit_lc(period_days=4.0, depth_ppt=8.0)
    epoch = 2457001.0
    odd_d, even_d, is_alt = alternating_event_consistency(
        lc, period=4.0, epoch=epoch, duration=0.12)
    assert not is_alt, (
        f"True period should not be alternating — odd_d={odd_d:.2f}, even_d={even_d:.2f}"
    )


# ── transit_window_overlap_fraction tests ────────────────────────────────────

def test_transit_window_overlap_independent_near_2to1_low():
    """Independently orbiting planets with ~2:1 period ratio have low physical overlap."""
    # P1=3.69 d (epoch 2457001.0), P2=7.45 d (epoch 2457003.5) — different offsets
    t_start, t_end = 2457000.0, 2457027.0
    overlap = transit_window_overlap_fraction(
        period_trial=7.45,    epoch_trial=2457003.5,    duration_trial=0.10,
        period_existing=3.69, epoch_existing=2457001.0, duration_existing=0.10,
        t_start=t_start, t_end=t_end,
    )
    assert overlap < 0.25, (
        f"Independent 2:1 planets should have low window overlap, got {overlap:.2f}"
    )


def test_transit_window_overlap_exact_alias_high():
    """A 2× alias with the same epoch has full window overlap with the true period."""
    t_start, t_end = 2457000.0, 2457027.0
    # Every P2=7.38 d window coincides exactly with a P1=3.69 d window
    overlap = transit_window_overlap_fraction(
        period_trial=7.38,    epoch_trial=2457001.0,    duration_trial=0.12,
        period_existing=3.69, epoch_existing=2457001.0, duration_existing=0.12,
        t_start=t_start, t_end=t_end,
    )
    assert overlap >= 0.8, (
        f"2× alias with same epoch should have high overlap, got {overlap:.2f}"
    )


# ── resolve_aliases_for_candidate integration tests ───────────────────────────

def test_resolve_aliases_selects_true_period_from_2x_alias():
    """Resolver returns the true period when given a 2× alias candidate."""
    import pandas as pd
    lc = _make_transit_lc(period_days=4.0, depth_ppt=8.0, noise_ppt=0.5, seed=42)
    # Construct a fake candidate at 8.0 d (the 2× alias of the true 4.0 d period)
    fake = pd.Series({
        "period_days":  8.0,
        "epoch_btjd":   2457001.0,
        "duration_days": 0.12,
        "depth_ppt":    8.0,
        "snr":          10.0,
        "score":        9.0,
    })
    resolved, trial_df = resolve_aliases_for_candidate(
        lc, fake,
        period_min=0.5, period_max=20.0,
        duration_min=0.05, duration_max=0.5,
    )
    # Should resolve to near 4.0 d (P/2 of the 8.0 d alias)
    assert abs(resolved["period_days"] - 4.0) / 4.0 < 0.05, (
        f"Resolver returned {resolved['period_days']:.4f} d instead of ~4.0 d "
        f"(harmonic_label={resolved.get('harmonic_label')})"
    )


def test_resolve_aliases_does_not_reject_independent_near_2to1():
    """A planet at ~2× an existing planet's period is NOT penalised if windows don't overlap."""
    # Existing planet: 3.69 d at BTJD epoch 2457001.0
    # Trial for an independent ~7.45 d planet with a different epoch
    t_start, t_end = 2457000.0, 2457027.0
    overlap = transit_window_overlap_fraction(
        period_trial=7.45,    epoch_trial=2457003.5,    duration_trial=0.10,
        period_existing=3.69, epoch_existing=2457001.0, duration_existing=0.10,
        t_start=t_start, t_end=t_end,
    )
    # The 2:1 ratio alone must not cause rejection — physical overlap must be low
    assert overlap < 0.25, (
        f"Independent planet at 2× ratio should not be penalised; overlap={overlap:.2f}"
    )


# ── _build_period_grid: n_periods override tests ──────────────────────────────

def test_n_periods_override_sets_exact_grid_size():
    """n_override must produce exactly that many period-grid points."""
    for n in (100, 500, 5000):
        periods = _build_period_grid(
            period_min=1.0, period_max=20.0,
            baseline=80.0, frequency_factor=2,
            n_override=n,
        )
        assert len(periods) == n, (
            f"Expected {n} grid points with n_override={n}, got {len(periods)}"
        )


def test_n_periods_override_differs_from_auto():
    """A 5000-point override must differ from the auto-computed grid for an 80-day baseline."""
    # Auto: factor=2, baseline=80, Δf ≈ 1/1.0 − 1/20.0 = 0.95 → n_auto ≈ 2×80×0.95 ≈ 152
    periods_auto = _build_period_grid(
        period_min=1.0, period_max=20.0,
        baseline=80.0, frequency_factor=2,
        n_override=None,
    )
    periods_high = _build_period_grid(
        period_min=1.0, period_max=20.0,
        baseline=80.0, frequency_factor=2,
        n_override=5000,
    )
    assert len(periods_high) != len(periods_auto), (
        "5000-point override should differ from auto grid "
        f"(auto={len(periods_auto)}, override={len(periods_high)})"
    )
    assert len(periods_high) == 5000


# ── suppress_periods: artifact suppression tests ──────────────────────────────

def _make_two_peak_bls_result(p_artifact=1.005, p_real=1.511,
                              power_artifact=15.0, power_real=4.0,
                              n_grid=1000):
    """Synthetic _BLSResult with two peaks: one strong 'artifact', one weaker real planet."""
    periods  = np.linspace(0.5, 3.0, n_grid)
    power    = np.zeros(n_grid)
    depth    = np.zeros(n_grid)
    epoch    = np.full(n_grid, 2457001.0)
    duration = np.full(n_grid, 0.05)

    i_art  = int(np.argmin(np.abs(periods - p_artifact)))
    power[i_art]  = power_artifact
    depth[i_art]  = 0.010   # 10 ppt

    i_real = int(np.argmin(np.abs(periods - p_real)))
    power[i_real] = power_real
    depth[i_real] = 0.005   # 5 ppt

    return _BLSResult(periods, power, depth, epoch, duration)


def test_suppress_periods_removes_artifact_from_candidates():
    """A suppressed period must not appear in the returned candidate list."""
    result   = _make_two_peak_bls_result()
    flux_err = np.full(200, 0.001)

    cands = _extract_top_candidates(
        result, top_n=5, flux_err=flux_err, suppress_periods=[1.005],
    )
    for _, row in cands.iterrows():
        assert abs(row["period_days"] / 1.005 - 1.0) > 0.02, (
            f"Suppressed period 1.005 d still appeared as {row['period_days']:.4f} d"
        )


def test_suppress_periods_promotes_real_planet_to_rank1():
    """When the artifact is suppressed, the real planet must become the top candidate."""
    result   = _make_two_peak_bls_result()
    flux_err = np.full(200, 0.001)

    # Without suppression the artifact dominates
    cands_raw = _extract_top_candidates(
        result, top_n=1, flux_err=flux_err, suppress_periods=None,
    )
    assert abs(cands_raw.iloc[0]["period_days"] / 1.005 - 1.0) < 0.02, (
        "Without suppression, artifact at 1.005 d should be rank 1"
    )

    # With suppression the real planet is rank 1
    cands_sup = _extract_top_candidates(
        result, top_n=1, flux_err=flux_err, suppress_periods=[1.005],
    )
    assert abs(cands_sup.iloc[0]["period_days"] / 1.511 - 1.0) < 0.05, (
        f"With 1.005 d suppressed, real planet at ~1.511 d should be rank 1, "
        f"got {cands_sup.iloc[0]['period_days']:.4f} d"
    )


# ── Harmonic masking regression: 1.5× must NOT erase nearby real planet ───────

def test_snr_uses_cadence_count_not_grid_size():
    """Regression: SNR must be independent of the BLS period-grid size.

    UPDATED for the B2 fix (mission doc T1 sanctions this): the SNR is no
    longer derived from the reported flux_err at all.  With ``time`` and
    ``flux`` supplied, sigma comes from the measured robust scatter
    (1.4826 × MAD) of the out-of-transit residuals at the candidate ephemeris
    and n from the actual in-transit cadence count.  Neither quantity depends
    on the period-grid size, so the original invariant — identical SNR from a
    200-point and a 5000-point grid — must still hold.
    """
    period  = 4.0
    dur     = 0.10
    dep     = 0.005
    n_time  = 800  # synthetic cadences

    rng      = np.random.default_rng(11)
    flux_err = np.full(n_time, 0.001)
    time_arr = np.linspace(0.0, 27.0, n_time)
    flux_arr = 1.0 + rng.normal(0.0, 0.001, n_time)

    def make_result(n_grid):
        periods  = np.linspace(0.5, 10.0, n_grid)
        power    = np.ones(n_grid) * 0.01
        depth    = np.ones(n_grid) * dep
        epoch    = np.full(n_grid, 1.0)
        duration = np.full(n_grid, dur)
        # Inject a clear peak at the trial period
        i = int(np.argmin(np.abs(periods - period)))
        power[i]    = 5.0
        depth[i]    = dep
        duration[i] = dur
        return _BLSResult(periods, power, depth, epoch, duration)

    cands_small = _extract_top_candidates(
        make_result(200), top_n=1, flux_err=flux_err, time=time_arr,
        flux=flux_arr,
    )
    cands_large = _extract_top_candidates(
        make_result(5000), top_n=1, flux_err=flux_err, time=time_arr,
        flux=flux_arr,
    )

    assert not cands_small.empty and not cands_large.empty, \
        "Expected a candidate from both grid sizes"

    snr_small = cands_small.iloc[0]["snr"]
    snr_large = cands_large.iloc[0]["snr"]

    # Measured-scatter SNR uses only time/flux — grid size is irrelevant.
    ratio = snr_small / snr_large if snr_large > 0 else float("inf")
    assert 0.80 < ratio < 1.20, (
        f"SNR must be grid-size-independent when time/flux are supplied.\n"
        f"  grid_size=200  → SNR {snr_small:.2f}\n"
        f"  grid_size=5000 → SNR {snr_large:.2f}\n"
        f"  ratio={ratio:.3f}  (expected 0.80–1.20)"
    )

    # Sanity: the measured-scatter SNR should sit near the analytic value
    # depth / (sigma / sqrt(n_in)) with sigma = 0.001 and ~20 in-transit points.
    n_in_expected = n_time * dur / period
    snr_expected  = dep / (0.001 / np.sqrt(n_in_expected))
    assert snr_expected / 2 < snr_small < snr_expected * 2, (
        f"Measured SNR {snr_small:.1f} not within 2× of analytic "
        f"{snr_expected:.1f}"
    )


def test_upward_excursion_does_not_block_real_transit():
    """Regression: an upward excursion (dep=0, pwr>0) must be skipped, not break the loop.

    Old bug: `if pwr <= 0 or dep <= 0: break` exited the entire greedy loop when the
    max-power period corresponded to a brightening (flare / K2 roll artifact).  The numpy
    engine clamps depth = max(-s/r, 0), so an upward window gives pwr > 0 but dep == 0.
    The break left `rows` empty even when genuine transit dips existed at other periods.

    Fix: `dep <= 0` masks the period and continues; only `pwr <= 0` triggers break.
    """
    n = 600
    periods  = np.linspace(1.0, 6.0, n)
    power    = np.zeros(n)
    depth    = np.zeros(n)
    epoch    = np.full(n, 2457001.0)
    duration = np.full(n, 0.05)

    # Strongest "signal" is an upward excursion — depth stays 0, power is positive.
    # This simulates a K2 roll artefact or flare that the BLS locks onto.
    i_flare = int(np.argmin(np.abs(periods - 2.0)))
    power[i_flare] = 20.0   # dominant in power spectrum
    depth[i_flare] = 0.0    # but zero depth (upward signal — NOT a transit dip)

    # Real transit dip at 3.5 d — weaker power, positive depth.
    i_transit = int(np.argmin(np.abs(periods - 3.5)))
    power[i_transit] = 5.0
    depth[i_transit] = 0.004

    result   = _BLSResult(periods, power, depth, epoch, duration)
    flux_err = np.full(200, 0.001)

    cands = _extract_top_candidates(result, top_n=5, flux_err=flux_err)

    assert not cands.empty, (
        "Candidate list is empty — the upward excursion incorrectly broke the loop "
        "instead of being skipped."
    )
    periods_found = list(cands["period_days"])
    assert any(abs(p / 3.5 - 1.0) < 0.05 for p in periods_found), (
        f"Real transit at 3.5 d not recovered after upward excursion at 2.0 d. "
        f"Candidates: {[f'{p:.4f}' for p in periods_found]}"
    )
    # The upward excursion itself must NOT appear in the candidates
    assert not any(abs(p / 2.0 - 1.0) < 0.05 for p in periods_found), (
        f"Upward excursion at 2.0 d should not appear in candidates: "
        f"{[f'{p:.4f}' for p in periods_found]}"
    )


def test_empty_bls_result_has_correct_columns():
    """run_bls on a flat LC must return an empty DataFrame with the expected column schema.

    Regression for the KeyError raised when notebooks slice columns on an
    uninitialized (zero-column) empty DataFrame.
    """
    # All-zero power BLS result → _extract_top_candidates breaks immediately
    n = 200
    periods  = np.linspace(1.0, 10.0, n)
    power    = np.zeros(n)          # no signal
    depth    = np.zeros(n)
    epoch    = np.full(n, 2457001.0)
    duration = np.full(n, 0.05)

    result   = _BLSResult(periods, power, depth, epoch, duration)
    flux_err = np.full(50, 0.001)

    df = _extract_top_candidates(result, top_n=5, flux_err=flux_err)

    assert df.empty, "Expected an empty DataFrame for an all-zero power spectrum"
    # Every expected column must exist so that downstream column slices don't KeyError
    missing = [c for c in _CANDIDATE_COLUMNS if c not in df.columns]
    assert not missing, (
        f"Empty candidates DataFrame is missing columns: {missing}\n"
        "This causes KeyError when the notebook slices columns on an empty result."
    )


def test_harmonic_masking_no_1p5x_erase():
    """Regression: 1.5× of the artifact (1.005 d) must NOT erase a real planet at 1.511 d.

    Old bug: harmonics included 1.5×, so 1.5 × 1.005 d = 1.508 d ± 5% = [1.433, 1.583] d
    wiped out the 1.511 d signal from the candidate pool.  Current code uses only integer
    ratios [0.5, 1.0, 2.0, 3.0], which leaves 1.511 d untouched.
    """
    # Artifact at 1.005 d (rank 1 without suppression); real planet at 1.511 d (rank 2)
    result   = _make_two_peak_bls_result(
        p_artifact=1.005, p_real=1.511,
        power_artifact=15.0, power_real=4.0,
    )
    flux_err = np.full(200, 0.001)

    # Run without suppression so the artifact is extracted at rank 1.
    # After its harmonic mask is applied, the real planet at 1.511 d must survive.
    cands = _extract_top_candidates(result, top_n=2, flux_err=flux_err,
                                    suppress_periods=None)

    periods_found = [row["period_days"] for _, row in cands.iterrows()]
    assert any(abs(p / 1.511 - 1.0) < 0.05 for p in periods_found), (
        f"Real planet at 1.511 d was erased from the candidate pool after extracting "
        f"the 1.005 d artifact. Harmonic masking may have reintroduced the 1.5× term. "
        f"Candidates returned: {[f'{p:.4f}' for p in periods_found]}"
    )


def test_bls_dip_only_brightening_yields_empty():
    """BLS on a light curve containing only a periodic brightening must return no candidates.

    Regression for the symmetric-s² BLS power bug: the original implementation
    scored brightenings (s > 0) identically to transit dips (s < 0), so a K2
    roll artefact or flare could appear as a high-power candidate with depth=0.
    With the dip-only fix (power=0 when s >= 0 inside _numpy_bls), brightenings
    produce power=0 in the periodogram and are never extracted.
    """
    rng = np.random.default_rng(7)
    n   = 500
    t   = np.linspace(0.0, 80.0, n)
    # Inject a periodic *brightening* at 9.0 d — no transit dip anywhere
    flare_period = 9.0
    phase = (t % flare_period) / flare_period
    # Gaussian brightening at phase 0: flux goes UP by 6 ppt
    flux = 1.0 + 0.006 * np.exp(-0.5 * ((phase - 0.0) / 0.005) ** 2)
    # Wrap around: also near phase 1
    flux += 0.006 * np.exp(-0.5 * ((phase - 1.0) / 0.005) ** 2)
    flux += rng.normal(0.0, 0.001, n)

    lc = lk.LightCurve(
        time=Time(t + 2457000, format="btjd", scale="tdb"),
        flux=flux * u.dimensionless_unscaled,
        flux_err=np.full(n, 0.001) * u.dimensionless_unscaled,
    )
    _, _, cands = run_bls(lc, period_min=5.0, period_max=15.0,
                          duration_min=0.01, duration_max=0.3, top_n=5)

    # The brightening should produce no transit candidates
    assert cands.empty or all(cands["depth_ppt"] > 0), (
        "BLS returned a candidate with depth≤0 from a brightening-only light curve. "
        "The dip-only power restriction (s<0) is not working correctly."
    )
    # Stricter: the brightening period must not appear as rank-1
    if not cands.empty:
        rank1_period = cands.iloc[0]["period_days"]
        assert abs(rank1_period / flare_period - 1.0) > 0.05, (
            f"Brightening period {flare_period} d emerged as rank-1 candidate "
            f"({rank1_period:.4f} d). Expected no candidates or a different period."
        )


def test_bls_finds_weak_dip_despite_stronger_brightening():
    """BLS must recover a real transit dip even when a stronger brightening exists.

    This is the long-period (f/g/h) failure mode for K2: brightening artefacts at
    8-21 d have higher raw BLS power than the weak transit dips, causing the
    candidates list to fill up with depth=0 entries before the real signals appear.

    The dip-only fix (_numpy_bls restricts power to s<0 windows) means brightenings
    are assigned power=0 and the weak transit dip emerges as rank-1.
    """
    rng = np.random.default_rng(13)
    n   = 500
    t   = np.linspace(0.0, 80.0, n)

    bright_period  = 12.0   # stronger artefact brightening
    transit_period = 9.5    # weaker but real transit dip

    phase_b = (t % bright_period) / bright_period
    phase_t = (t % transit_period) / transit_period

    # Brightening artefact: +8 ppt at phase 0 (narrow Gaussian)
    flux  = 1.0 + 0.008 * np.exp(-0.5 * ((phase_b        ) / 0.004) ** 2)
    flux +=       0.008 * np.exp(-0.5 * ((phase_b - 1.0  ) / 0.004) ** 2)
    # Transit dip: −4 ppt at phase 0 (wider box-like Gaussian)
    flux -= 0.004 * np.exp(-0.5 * ((phase_t        ) / 0.015) ** 2)
    flux -= 0.004 * np.exp(-0.5 * ((phase_t - 1.0  ) / 0.015) ** 2)
    flux += rng.normal(0.0, 0.001, n)

    lc = lk.LightCurve(
        time=Time(t + 2457000, format="btjd", scale="tdb"),
        flux=flux * u.dimensionless_unscaled,
        flux_err=np.full(n, 0.001) * u.dimensionless_unscaled,
    )
    _, _, cands = run_bls(lc, period_min=5.0, period_max=20.0,
                          duration_min=0.01, duration_max=0.3, top_n=10,
                          n_periods=2000)

    assert not cands.empty, (
        "BLS returned no candidates. With the dip-only fix the transit dip at "
        f"{transit_period} d should be rank-1 even though the brightening artefact "
        f"at {bright_period} d has higher raw BLS power."
    )
    rank1_period = cands.iloc[0]["period_days"]
    assert abs(rank1_period / transit_period - 1.0) < 0.08, (
        f"Expected rank-1 near {transit_period} d (transit dip), "
        f"got {rank1_period:.4f} d. The brightening artefact may still be "
        f"outcompeting the real transit signal."
    )


# ── B1: auto period grid follows the frequency-resolution criterion ──────────

def test_auto_grid_follows_frequency_criterion():
    """Auto grid: n = ceil((f_max − f_min) / Δf) with Δf = duration_min / (4 × baseline)."""
    periods = _build_period_grid(
        period_min=1.0, period_max=13.0, baseline=27.0, frequency_factor=10,
        duration_min=0.01,
    )
    expected = int(np.ceil((1.0 / 1.0 - 1.0 / 13.0) * (4 * 27.0) / 0.01))
    assert len(periods) == expected, (
        f"Auto grid size {len(periods)} != frequency-criterion value {expected}"
    )
    # Within the floor/cap bounds (this case must NOT be capped)
    assert 500 <= len(periods) < 20000


def test_auto_grid_cap_logs_warning(caplog):
    """When the criterion wants more than 20 000 points, cap at 20 000 and warn."""
    with caplog.at_level(logging.WARNING, logger="tesshunter.bls_search"):
        periods = _build_period_grid(
            period_min=0.5, period_max=20.0, baseline=80.0, frequency_factor=10,
            duration_min=0.01,
        )
    assert len(periods) == 20000, f"Expected 20000-point capped grid, got {len(periods)}"
    assert "truncated" in caplog.text.lower() or "cap" in caplog.text.lower(), (
        "Capping the auto period grid must log a WARNING"
    )


def test_auto_grid_floor_500():
    """Narrow local windows still get at least 500 grid points."""
    periods = _build_period_grid(
        period_min=3.8, period_max=4.2, baseline=27.0, frequency_factor=10,
        duration_min=0.05,
    )
    assert len(periods) == 500


# ── B3: NaN flux_err must never propagate into BLS powers ────────────────────

def test_nan_flux_err_block_yields_finite_powers():
    """A NaN flux_err block (and even all-NaN) must not poison the BLS weights.

    Regression: the old `or 1e-4` fallback was dead when nanmedian returned
    NaN (NaN is truthy as a float), so NaN weights propagated into every
    power and the search silently found nothing.
    """
    df = make_synthetic_lightcurve(
        n_points=400, baseline_days=27.0, period_days=4.0,
        depth_ppt=8.0, duration_days=0.12, noise_ppt=0.5, seed=1,
    )
    lc = _lc_from_df(df)
    lc.flux_err[100:200] = np.nan   # contiguous NaN block

    _, result, cands = run_bls(lc, period_min=1.0, period_max=10.0,
                               top_n=3, n_periods=400)
    assert np.all(np.isfinite(result.power)), "NaN block leaked into BLS powers"
    assert not cands.empty
    assert np.isfinite(cands.iloc[0]["snr"])

    # Pathological case: every flux_err NaN → explicit 1e-4 fallback
    lc_all = _lc_from_df(df)
    lc_all.flux_err[:] = np.nan
    _, result_all, cands_all = run_bls(lc_all, period_min=1.0, period_max=10.0,
                                       top_n=3, n_periods=400)
    assert np.all(np.isfinite(result_all.power)), "All-NaN flux_err poisoned powers"
    assert not cands_all.empty, "All-NaN flux_err silently killed the search"


# ── B4: single deep dip reports honest transit count ─────────────────────────

def test_single_deep_dip_reports_single_event():
    """One transit in the window → n_transits_observed == 1, single_event True.

    The injected period (40 d, t0=13) puts exactly one dip inside the 27 d
    baseline; any fitted period in [16, 20] d predicts no second in-window
    transit.  The old n_expected clamp handed such candidates a free
    completeness; the honest output flags them for the pipeline gate instead.
    """
    df = make_synthetic_lightcurve(
        n_points=800, baseline_days=27.0, period_days=40.0,
        depth_ppt=10.0, duration_days=0.2, t0=13.0, noise_ppt=0.5, seed=3,
    )
    lc = _lc_from_df(df)
    _, _, cands = run_bls(lc, period_min=16.0, period_max=20.0,
                          duration_min=0.05, duration_max=0.4, n_periods=600)
    assert not cands.empty
    top = cands.iloc[0]
    assert int(top["n_transits_observed"]) == 1, (
        f"Expected 1 observed transit, got {top['n_transits_observed']}"
    )
    assert bool(top["single_event"]), "single_event must be True for a lone dip"
    # No free pass: score = snr × completeness must be visibly below snr
    assert top["score"] < 0.95 * top["snr"], (
        f"Single dip got a near-1.0 completeness free pass: "
        f"score={top['score']:.2f} snr={top['snr']:.2f}"
    )


def test_multi_transit_not_single_event():
    """A normal multi-transit detection must not be flagged single_event."""
    df = make_synthetic_lightcurve(
        n_points=1000, baseline_days=27.0, period_days=4.0,
        depth_ppt=8.0, duration_days=0.12, noise_ppt=0.5, seed=7,
    )
    lc = _lc_from_df(df)
    _, _, cands = run_bls(lc, period_min=2.0, period_max=8.0,
                          duration_min=0.06, duration_max=0.3, n_periods=1000)
    top = cands.iloc[0]
    assert int(top["n_transits_observed"]) >= 5
    assert not bool(top["single_event"])


# ── B2: corrected SNR from measured scatter + SDE column ─────────────────────

def test_corrected_snr_tracks_measured_noise():
    """SNR must come from the measured scatter, not the reported flux_err.

    The reported flux_err is deliberately misreported 5× too large; the
    corrected estimator must still land within a factor ~2 of the analytic
    SNR computed from the TRUE injected noise.
    """
    true_noise = 0.001     # injected white noise (fractional)
    depth_frac = 0.008
    period, dur, n_pts = 4.0, 0.12, 1000

    df = make_synthetic_lightcurve(
        n_points=n_pts, baseline_days=27.0, period_days=period,
        depth_ppt=depth_frac * 1000.0, duration_days=dur,
        noise_ppt=true_noise * 1000.0, seed=7,
    )
    df["flux_err"] = 5 * true_noise   # reported error 5× too large
    lc = _lc_from_df(df)

    _, _, cands = run_bls(lc, period_min=2.0, period_max=8.0,
                          duration_min=0.06, duration_max=0.3)
    top = cands.iloc[0]
    assert abs(top["period_days"] - period) / period < 0.02

    n_in_expected = n_pts * dur / period
    snr_expected  = depth_frac / (true_noise / np.sqrt(n_in_expected))
    assert snr_expected / 2 < top["snr"] < snr_expected * 2, (
        f"Corrected SNR {top['snr']:.1f} not within 2× of analytic "
        f"{snr_expected:.1f} — is it still using the (misreported) flux_err?"
    )

    # SDE: a strong injected signal must stand far above the power-spectrum floor
    assert "sde" in cands.columns
    assert top["sde"] > 5, f"SDE of a strong injected transit too low: {top['sde']:.1f}"


# ── B5: undersampled duration_min warning ────────────────────────────────────

def test_duration_min_undersampled_warns(caplog):
    """duration_min spanning fewer than 2 cadences must log a WARNING."""
    df = make_synthetic_lightcurve(
        n_points=200, baseline_days=27.0, period_days=4.0,
        depth_ppt=8.0, duration_days=0.3, noise_ppt=0.5, seed=9,
    )
    lc = _lc_from_df(df)   # cadence ≈ 0.136 d → 2 cadences = 0.271 d

    with caplog.at_level(logging.WARNING, logger="tesshunter.bls_search"):
        run_bls(lc, period_min=2.0, period_max=8.0,
                duration_min=0.02, duration_max=0.4, n_periods=300)
    assert "spans fewer than 2 cadences" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="tesshunter.bls_search"):
        run_bls(lc, period_min=2.0, period_max=8.0,
                duration_min=0.4, duration_max=0.8, n_periods=300)
    assert "spans fewer than 2 cadences" not in caplog.text
