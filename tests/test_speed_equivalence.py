"""P2 speed work: the compiled BLS kernel and the vectorised transit-epoch
helpers must reproduce the original per-period and per-transit loops EXACTLY.

Every reference implementation below is the pre-P2 code, copied verbatim
(``_ref_*``). The tests draw random multi-sector, gapped light curves and
random ephemerides and assert bit-for-bit agreement wherever the new code
claims it (BLS engine, transit-time lists, observed-transit counts, event
completeness, alternating consistency, window overlap, small-bin binning),
and near-agreement where the only difference is float summation order
(bins holding eight or more cadences).
"""

import numpy as np
import lightkurve as lk
import pytest
from astropy import units as u
from astropy.time import Time

from tesshunter import bls_search as bls
from tesshunter import preprocessing as pp


# ── Reference implementations (pre-P2 code, verbatim) ─────────────────────────

def _ref_transit_times(period, epoch, t_start, t_end):
    n_lo = int(np.floor((t_start - epoch) / period))
    n_hi = int(np.ceil((t_end - epoch) / period))
    t = np.array([epoch + n * period for n in range(n_lo, n_hi + 1)], dtype=float)
    return t[(t >= t_start) & (t <= t_end)]


def _ref_count_observed_transits(time, epoch, period, duration):
    t_min, t_max = float(time.min()), float(time.max())
    half_w = 0.5 * duration
    count = 0
    for t_transit in _ref_transit_times(period, epoch, t_min, t_max):
        if np.any(np.abs(time - t_transit) <= half_w):
            count += 1
    return count


def _ref_event_completeness(time, flux, period, epoch, duration):
    good = np.isfinite(flux) & np.isfinite(time)
    time, flux = time[good], flux[good]
    if len(time) < 3:
        return 0, 0, 0.0
    t_start, t_end = float(time.min()), float(time.max())
    t_pred = _ref_transit_times(period, epoch, t_start, t_end)
    if len(t_pred) == 0:
        return 0, 0, 0.0
    half_w = 0.5 * duration
    oot = np.ones(len(time), dtype=bool)
    for t_tr in t_pred:
        oot &= np.abs(time - t_tr) > half_w
    if oot.sum() >= 10:
        baseline = float(np.nanmedian(flux[oot]))
        noise = float(np.nanmedian(np.abs(flux[oot] - baseline))) * 1.4826
    else:
        baseline = float(np.nanmedian(flux))
        noise = float(np.nanmedian(np.abs(flux - baseline))) * 1.4826
    threshold = max(noise, 1e-6)
    n_covered, n_dip = 0, 0
    for t_tr in t_pred:
        mask_in = np.abs(time - t_tr) <= half_w
        if mask_in.sum() == 0:
            continue
        n_covered += 1
        if float(np.nanmean(flux[mask_in])) < baseline - threshold:
            n_dip += 1
    ec = float(n_dip) / n_covered if n_covered > 0 else 0.0
    return n_covered, n_dip, ec


def _ref_alternating(time, flux, period, epoch, duration):
    good = np.isfinite(flux) & np.isfinite(time)
    time, flux = time[good], flux[good]
    if len(time) < 3:
        return 0.0, 0.0, False
    t_start, t_end = float(time.min()), float(time.max())
    t_pred = _ref_transit_times(period, epoch, t_start, t_end)
    if len(t_pred) < 2:
        return 0.0, 0.0, False
    half_w = 0.5 * duration
    baseline = float(np.nanmedian(flux))
    even_dips, odd_dips = [], []
    for i, t_tr in enumerate(t_pred):
        mask_in = np.abs(time - t_tr) <= half_w
        if mask_in.sum() == 0:
            continue
        depth_ppt = (baseline - float(np.nanmean(flux[mask_in]))) * 1000.0
        (even_dips if i % 2 == 0 else odd_dips).append(depth_ppt)
    if not even_dips or not odd_dips:
        return 0.0, 0.0, False
    even_depth = float(np.nanmean(even_dips))
    odd_depth = float(np.nanmean(odd_dips))
    max_d = max(abs(even_depth), abs(odd_depth))
    min_d = min(abs(even_depth), abs(odd_depth))
    is_alternating = (max_d > 0.0) and ((min_d / max_d) < 0.30)
    return odd_depth, even_depth, is_alternating


def _ref_overlap(pt, et, dt, pe, ee, de, t_start, t_end):
    t_trial = _ref_transit_times(pt, et, t_start, t_end)
    t_exist = _ref_transit_times(pe, ee, t_start, t_end)
    if len(t_trial) == 0 or len(t_exist) == 0:
        return 0.0
    combined_half = 0.5 * (dt + de)
    n_overlap = sum(
        1 for t_tr in t_trial
        if np.any(np.abs(t_exist - t_tr) < combined_half)
    )
    return float(n_overlap) / len(t_trial)


def _ref_bin(time, flux, flux_err, bin_minutes):
    bin_days = bin_minutes / 1440.0
    t_min, t_max = time.min(), time.max()
    edges = np.arange(t_min, t_max + bin_days, bin_days)
    bt, bf, be = [], [], []
    for i in range(len(edges) - 1):
        mask = (time >= edges[i]) & (time < edges[i + 1])
        if mask.sum() < 1:
            continue
        f = flux[mask]
        e = flux_err[mask]
        finite = np.isfinite(f) & np.isfinite(e) & (e > 0)
        if finite.sum() < 1:
            continue
        w = 1.0 / e[finite] ** 2
        bf.append(float(np.sum(w * f[finite]) / np.sum(w)))
        be.append(float(1.0 / np.sqrt(np.sum(w))))
        bt.append(float(0.5 * (edges[i] + edges[i + 1])))
    return np.array(bt), np.array(bf), np.array(be)


# ── Random data ───────────────────────────────────────────────────────────────

def _gapped_time(rng, n_sectors=3, cadence_min=10.0, sector_gap_days=None):
    """Sorted, gapped, multi-sector time array with random dropouts."""
    dt = cadence_min / 1440.0
    pieces = []
    t0 = 1000.0 + rng.uniform(0, 5)
    for s in range(n_sectors):
        n = int(27.0 / dt)
        t = t0 + np.arange(n) * dt
        keep = rng.uniform(size=n) > 0.05          # random dropouts
        # one orbit gap in the middle of each sector
        keep &= ~((t - t0 > 12.5) & (t - t0 < 14.0))
        pieces.append(t[keep])
        t0 += 27.4 + (sector_gap_days if sector_gap_days is not None else rng.choice([0.0, 300.0, 900.0]))
    return np.concatenate(pieces)


def _box_flux(rng, time, period, epoch, duration, depth, noise):
    phase = ((time - epoch + 0.5 * period) % period) - 0.5 * period
    flux = np.ones(time.size)
    flux[np.abs(phase) <= 0.5 * duration] -= depth
    return flux + rng.normal(0.0, noise, time.size)


CASES = [dict(seed=s) for s in range(12)]


@pytest.mark.parametrize("case", CASES)
def test_transit_epoch_helpers_match_loops(case):
    rng = np.random.default_rng(case["seed"])
    time = _gapped_time(rng, n_sectors=int(rng.integers(1, 4)))
    for _ in range(6):
        period = float(rng.uniform(0.5, 40.0))
        epoch = float(rng.uniform(time.min() - period, time.min() + period))
        duration = float(rng.uniform(0.02, min(0.4, 0.45 * period)))
        flux = _box_flux(rng, time, period, epoch, duration, 0.003, 0.001)

        assert np.array_equal(
            bls._transit_times(period, epoch, float(time.min()), float(time.max())),
            _ref_transit_times(period, epoch, float(time.min()), float(time.max())),
        )
        assert bls._count_observed_transits(time, epoch, period, duration) == \
            _ref_count_observed_transits(time, epoch, period, duration)

        lc = lk.LightCurve(time=Time(time, format="btjd", scale="tdb"),
                           flux=flux * u.dimensionless_unscaled)
        new = bls.event_completeness(lc, period, epoch, duration)
        ref = _ref_event_completeness(time, flux, period, epoch, duration)
        assert new == ref, f"event_completeness {new} != {ref}"

        new_a = bls.alternating_event_consistency(lc, period, epoch, duration)
        ref_a = _ref_alternating(time, flux, period, epoch, duration)
        assert new_a == ref_a, f"alternating {new_a} != {ref_a}"

        # Overlap against a random second ephemeris (and against itself)
        p2 = float(rng.uniform(0.5, 40.0))
        e2 = float(rng.uniform(time.min(), time.min() + p2))
        d2 = float(rng.uniform(0.02, 0.3))
        t_s, t_e = float(time.min()), float(time.max())
        assert bls.transit_window_overlap_fraction(period, epoch, duration, p2, e2, d2, t_s, t_e) == \
            _ref_overlap(period, epoch, duration, p2, e2, d2, t_s, t_e)
        assert bls.transit_window_overlap_fraction(period, epoch, duration, period, epoch, duration, t_s, t_e) == \
            _ref_overlap(period, epoch, duration, period, epoch, duration, t_s, t_e)


def test_epoch_helpers_fall_back_when_windows_overlap():
    """duration >= period: the vectorised path must defer to the loop form."""
    rng = np.random.default_rng(99)
    time = _gapped_time(rng, n_sectors=1)
    flux = 1.0 + rng.normal(0, 1e-3, time.size)
    period, epoch, duration = 0.3, float(time.min()) + 0.1, 0.35
    lc = lk.LightCurve(time=Time(time, format="btjd", scale="tdb"),
                       flux=flux * u.dimensionless_unscaled)
    assert bls._count_observed_transits(time, epoch, period, duration) == \
        _ref_count_observed_transits(time, epoch, period, duration)
    assert bls.event_completeness(lc, period, epoch, duration) == \
        _ref_event_completeness(time, flux, period, epoch, duration)
    assert bls.alternating_event_consistency(lc, period, epoch, duration) == \
        _ref_alternating(time, flux, period, epoch, duration)


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_jit_bls_is_bit_identical_to_loop(seed):
    """The compiled BLS kernel reproduces the numpy one-period loop exactly.

    The period grid deliberately spans phase-bin counts from the floor (64)
    to the cap (5000), includes durations that trip the phi >= 0.9 and
    k >= nb skips, and repeats a box width so the seen-k dedup is exercised.
    """
    rng = np.random.default_rng(seed)
    time = _gapped_time(rng, n_sectors=int(rng.integers(1, 4)), cadence_min=30.0)
    period_true = float(rng.uniform(1.0, 8.0))
    flux = _box_flux(rng, time, period_true, time.min() + 0.7, 0.12, 0.004, 0.001)
    flux_err = np.full(time.size, 0.001) * rng.uniform(0.8, 1.2, time.size)

    dur_min = 0.02
    periods = np.concatenate([
        np.linspace(0.25, 0.6, 37),              # nb at the 64 floor
        np.linspace(1.0, 12.0, 140),             # adaptive nb
        np.linspace(25.0, 60.0, 30),             # nb at the 5000 cap
    ])
    durations = np.array([dur_min, 0.0201, 0.05, 0.12, 0.3, 0.5, 0.6])

    out_new = bls._numpy_bls(time, flux, flux_err, periods, durations)
    out_ref = bls._numpy_bls_loop(time, flux, flux_err, periods, durations)
    for name, a, b in zip(("power", "depth", "epoch", "duration"), out_new, out_ref):
        assert np.array_equal(a, b), f"{name} differs: max |diff| = {np.max(np.abs(a - b))}"
    # sanity: the peak sits on the injected period or one of its low-order
    # harmonics (a coarse test grid can prefer 2P or P/2)
    j = int(np.argmax(out_new[0]))
    ratio = periods[j] / period_true
    assert any(abs(ratio / h - 1.0) < 0.1 for h in (1 / 3, 0.5, 1.0, 2.0, 3.0)), ratio


def test_jit_bls_handles_tiny_and_single_period_grids():
    rng = np.random.default_rng(7)
    time = _gapped_time(rng, n_sectors=1, cadence_min=30.0)
    flux = 1.0 + rng.normal(0, 1e-3, time.size)
    flux_err = np.full(time.size, 1e-3)
    for periods in (np.array([2.0]), np.array([0.7, 3.3, 9.9]), np.zeros(0)):
        out_new = bls._numpy_bls(time, flux, flux_err, periods, np.array([0.05, 0.1]))
        out_ref = bls._numpy_bls_loop(time, flux, flux_err, periods, np.array([0.05, 0.1]))
        for a, b in zip(out_new, out_ref):
            assert np.array_equal(a, b)


def test_run_bls_end_to_end_unchanged_by_kernel(monkeypatch):
    """run_bls through the compiled kernel and through the numpy loop give
    the same candidate table."""
    rng = np.random.default_rng(3)
    time = _gapped_time(rng, n_sectors=2, cadence_min=10.0, sector_gap_days=0.0)
    flux = _box_flux(rng, time, 3.7, time.min() + 1.1, 0.1, 0.005, 0.001)
    lc = lk.LightCurve(time=Time(time, format="btjd", scale="tdb"),
                       flux=flux * u.dimensionless_unscaled,
                       flux_err=np.full(time.size, 1e-3) * u.dimensionless_unscaled)
    _, _, c_new = bls.run_bls(lc, period_min=1.0, period_max=10.0,
                              duration_min=0.04, duration_max=0.3, top_n=5)
    monkeypatch.setattr(bls, "_numpy_bls", bls._numpy_bls_loop)
    _, _, c_ref = bls.run_bls(lc, period_min=1.0, period_max=10.0,
                              duration_min=0.04, duration_max=0.3, top_n=5)
    assert len(c_new) == len(c_ref)
    for col in ("period_days", "epoch_btjd", "duration_days", "depth_ppt", "power", "snr"):
        assert np.array_equal(c_new[col].to_numpy(), c_ref[col].to_numpy()), col


def _lc_from(time, flux, err):
    return lk.LightCurve(time=Time(time, format="btjd", scale="tdb"),
                         flux=flux * u.dimensionless_unscaled,
                         flux_err=err * u.dimensionless_unscaled)


def test_bin_lightcurve_bit_identical_for_small_bins():
    """10-min bins on 2-min data (<= 5 cadences per bin): exact agreement."""
    rng = np.random.default_rng(11)
    time = _gapped_time(rng, n_sectors=2, cadence_min=2.0)
    flux = 1.0 + rng.normal(0, 1e-3, time.size)
    err = 1e-3 * rng.uniform(0.5, 1.5, time.size)
    # sprinkle non-finite / non-positive errors and NaN flux
    err[rng.integers(0, time.size, 30)] = 0.0
    err[rng.integers(0, time.size, 30)] = np.nan
    flux[rng.integers(0, time.size, 30)] = np.nan
    lc = _lc_from(time, flux, err)
    binned = pp.bin_lightcurve(lc, bin_minutes=10.0)
    bt, bf, be = _ref_bin(time, flux, err, 10.0)
    assert np.array_equal(binned.time.value, bt)
    assert np.array_equal(binned.flux.value, bf)
    assert np.array_equal(binned.flux_err.value, be)


def test_bin_lightcurve_agrees_for_large_bins():
    """30-min bins on 2-min data (up to 15 per bin): equal to float rounding."""
    rng = np.random.default_rng(12)
    time = _gapped_time(rng, n_sectors=1, cadence_min=2.0)
    flux = 1.0 + rng.normal(0, 1e-3, time.size)
    err = 1e-3 * rng.uniform(0.5, 1.5, time.size)
    lc = _lc_from(time, flux, err)
    binned = pp.bin_lightcurve(lc, bin_minutes=30.0)
    bt, bf, be = _ref_bin(time, flux, err, 30.0)
    assert np.array_equal(binned.time.value, bt)
    assert np.allclose(binned.flux.value, bf, rtol=0, atol=1e-14)
    assert np.allclose(binned.flux_err.value, be, rtol=1e-14, atol=0)


def test_bin_lightcurve_drops_cadence_on_final_edge():
    """A cadence sitting exactly on the last edge belongs to no half-open bin
    in either implementation."""
    time = np.arange(0.0, 10.0 + 1e-12, 1.0)      # 0..10 inclusive
    flux = np.ones(time.size)
    err = np.ones(time.size) * 1e-3
    lc = _lc_from(time + 1000.0, flux, err)
    binned = pp.bin_lightcurve(lc, bin_minutes=1440.0)
    bt, bf, be = _ref_bin(time + 1000.0, flux, err, 1440.0)
    assert np.array_equal(binned.time.value, bt)
    assert np.array_equal(binned.flux.value, bf)
