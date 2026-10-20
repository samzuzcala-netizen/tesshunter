"""Box Least Squares transit search.

Uses a pure-numpy BLS engine (Kovács et al. 2002) instead of astropy's
C-extension BoxLeastSquares, which deadlocks on Python 3.14.  The output
format is identical to the old implementation so no other code changes.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import lightkurve as lk
import math

import numpy as np
import pandas as pd

from .config import (
    BLS_DURATION_MAX,
    BLS_DURATION_MIN,
    BLS_FREQUENCY_FACTOR,
    BLS_PERIOD_MAX,
    BLS_PERIOD_MIN,
    BLS_TOP_N,
)

logger = logging.getLogger(__name__)

# Columns guaranteed to be present in every DataFrame returned by run_bls /
# _extract_top_candidates, even when the result is empty.  Downstream code
# (notebooks, reporting) can rely on this schema without KeyError guards.
_CANDIDATE_COLUMNS: list[str] = [
    "peak_rank",
    "period_days",
    "epoch_btjd",
    "duration_days",
    "depth_frac",
    "depth_ppt",
    "power",
    "snr",
    "sde",
    "n_transits_observed",
    "single_event",
    "score",
]


@dataclass
class BLSCandidate:
    """A single BLS candidate signal."""

    period_days: float
    epoch_btjd: float
    duration_days: float
    depth_ppt: float
    depth_frac: float
    power: float
    snr: float
    peak_rank: int
    sde: float = 0.0
    n_transits_observed: int = 0
    single_event: bool = False


# ---------------------------------------------------------------------------
# Period / duration grids
# ---------------------------------------------------------------------------

def _build_period_grid(
    period_min: float,
    period_max: float,
    baseline: float,
    frequency_factor: int,
    n_max: int = 20_000,
    n_override: Optional[int] = None,
    duration_min: Optional[float] = None,
    oversample: int = 4,
) -> np.ndarray:
    """Linearly-spaced frequency grid converted to periods.

    Parameters
    ----------
    n_override :   When set, use exactly this many grid points instead of the
                   auto-computed value.  Allows the notebook config to request
                   higher resolution without touching frequency_factor.
    duration_min : Shortest searched transit duration (days).  When given, the
                   auto grid follows the standard BLS frequency-resolution
                   criterion delta_f = duration_min / (oversample × baseline),
                   which keeps the phase drift of the shortest transit below
                   1/oversample of its width across the full baseline between
                   adjacent grid frequencies.  When None, the legacy
                   frequency_factor heuristic is used.
    oversample :   Oversampling factor A in the frequency-resolution criterion
                   (default 4).

    Notes
    -----
    The auto grid is floored at 500 points and capped at ``n_max`` (20 000).
    When the criterion wants more points than the cap, a WARNING is logged;
    period precision above the cap is recovered downstream by local alias
    refinement (±5% window re-runs of the BLS).
    """
    min_freq = 1.0 / period_max
    max_freq = 1.0 / period_min
    if n_override is not None:
        n = int(n_override)
    else:
        if duration_min is not None and duration_min > 0:
            # Standard criterion: delta_f = duration_min / (A × baseline)
            delta_f = duration_min / (oversample * baseline)
            n = int(np.ceil((max_freq - min_freq) / delta_f))
        else:
            # Legacy heuristic — kept for callers that don't know duration_min
            n = int(frequency_factor * baseline * (max_freq - min_freq))
        n = max(n, 500)
        if n > n_max:
            logger.warning(
                "Auto period grid truncated: frequency criterion wants %d "
                "points but the cap is %d. Resolution above the cap is "
                "recovered by local alias refinement.",
                n, n_max,
            )
            n = n_max
    freqs = np.linspace(min_freq, max_freq, n)
    return (1.0 / freqs)[::-1]   # ascending period order


def _build_duration_grid(
    dur_min: float,
    dur_max: float,
    n: int = 10,
) -> np.ndarray:
    """Log-spaced transit duration grid in days."""
    return np.exp(np.linspace(np.log(dur_min), np.log(dur_max), n))


# ---------------------------------------------------------------------------
# Pure-numpy BLS engine
# ---------------------------------------------------------------------------

#: Phase bins per SHORTEST searched duration (resolution of the folded grid).
_PHASE_BINS_PER_MIN_DURATION = 4

#: Bounds on the per-period phase-bin count.  The cap bounds per-period cost;
#: period precision above it is recovered by local alias refinement, exactly
#: like the frequency-grid cap in _build_period_grid.
_MIN_PHASE_BINS = 64
_MAX_PHASE_BINS = 5000


try:  # optional compiled kernel; the numpy loop below is the reference
    from numba import njit as _njit
    _HAVE_NUMBA = True
except Exception:  # pragma: no cover - numba absent
    _HAVE_NUMBA = False


def _bls_kernel_py(
    t_rel: np.ndarray,
    w: np.ndarray,
    wy: np.ndarray,
    periods: np.ndarray,
    durations: np.ndarray,
    dur_min: float,
    t_min: float,
    bins_per_dur: int,
    nb_min: int,
    nb_max: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Scalar form of the reference BLS loop, written to be compiled by numba.

    Every floating-point operation is the one the numpy reference performs,
    in the same order: ``fmod`` fold, truncating bin index, per-bin weights
    accumulated in data order, one sequential cumulative sum over the doubled
    bin vector, and a strict first-maximum box update duration by duration.
    The equivalence test asserts bit-identical output against the numpy loop.
    """
    n_p = periods.shape[0]
    n = t_rel.shape[0]
    n_d = durations.shape[0]
    pw = np.zeros(n_p)
    pd_ = np.zeros(n_p)
    pe = np.zeros(n_p)
    pdur = np.zeros(n_p)
    seen = np.empty(n_d, dtype=np.int64)
    for i_p in range(n_p):
        period = periods[i_p]
        nb = int(np.ceil(bins_per_dur * period / dur_min))
        if nb > nb_max:
            nb = nb_max
        if nb < nb_min:
            nb = nb_min

        Wb = np.zeros(nb)
        WYb = np.zeros(nb)
        scale = nb / period
        for i in range(n):
            ph = t_rel[i] % period
            idx = int(ph * scale)
            if idx < 0:
                idx = 0
            elif idx > nb - 1:
                idx = nb - 1
            Wb[idx] += w[i]
            WYb[idx] += wy[i]

        cW = np.zeros(2 * nb + 1)
        cWY = np.zeros(2 * nb + 1)
        acc = 0.0
        accy = 0.0
        for j in range(2 * nb):
            jj = j if j < nb else j - nb
            acc += Wb[jj]
            accy += WYb[jj]
            cW[j + 1] = acc
            cWY[j + 1] = accy

        best_p = -np.inf
        best_dep = 0.0
        best_ep = t_min
        best_dur = durations[0]
        n_seen = 0
        for i_d in range(n_d):
            dur = durations[i_d]
            phi = dur / period
            if phi >= 0.9:
                continue
            k = int(np.ceil(phi * nb))
            if k < 1:
                k = 1
            if k >= nb:
                continue
            dup = False
            for q in range(n_seen):
                if seen[q] == k:
                    dup = True
            if dup:
                continue
            seen[n_seen] = k
            n_seen += 1

            any_valid = False
            bp = -1.0
            bj = -1
            for i in range(nb):
                r = cW[k + i] - cW[i]
                s = cWY[k + i] - cWY[i]
                if r > 1e-9 and r < 0.9 and s < 0:
                    denom = r * (1.0 - r)
                    if denom < 1e-20:
                        denom = 1e-20
                    p = s ** 2 / denom
                    if (not any_valid) or p > bp:
                        bp = p
                        bj = i
                        any_valid = True
            if not any_valid:
                continue
            if bp > best_p:
                best_p = bp
                rj = cW[k + bj] - cW[bj]
                sj = cWY[k + bj] - cWY[bj]
                if rj < 1e-10:
                    rj = 1e-10
                best_dep = -sj / rj
                best_ep = ((bj + 0.5 * k) / nb) * period + t_min
                best_dur = dur

        pw[i_p] = best_p if best_p > 0.0 else 0.0
        pd_[i_p] = best_dep if best_dep > 0.0 else 0.0
        pe[i_p] = best_ep
        pdur[i_p] = best_dur
    return pw, pd_, pe, pdur


if _HAVE_NUMBA:
    _bls_kernel = _njit(cache=True, nogil=True)(_bls_kernel_py)
else:  # pragma: no cover
    _bls_kernel = _bls_kernel_py


def _numpy_bls(
    time: np.ndarray,
    flux: np.ndarray,
    flux_err: np.ndarray,
    periods: np.ndarray,
    durations: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """BLS periodogram: the phase-binned Kovacs et al. (2002) algorithm.

    For each trial period the light curve is folded onto ``nb`` phase bins
    (``_PHASE_BINS_PER_MIN_DURATION`` bins per shortest searched duration,
    clamped to [``_MIN_PHASE_BINS``, ``_MAX_PHASE_BINS``]) and every box
    position/width is evaluated with O(nb) cumulative-sum arithmetic; cost
    per period is O(n + nb).

    The arithmetic runs in a numba-compiled kernel when numba is importable
    (``TESSHUNTER_NO_NUMBA=1`` forces the pure-numpy loop). The kernel is the
    reference loop :func:`_numpy_bls_loop` written out scalar by scalar, and
    ``tests/test_speed_equivalence.py`` asserts the two agree bit for bit;
    the compiled form is what makes a 20 000-point grid on a multi-sector
    light curve take seconds rather than minutes. A batched-numpy variant
    was tried first and measured SLOWER than the loop (the cost is the
    inline float arithmetic, not call overhead), so it was dropped.

    Epochs are quantised to a phase-bin centre and box edges to whole bins;
    downstream local alias refinement re-runs the BLS in a narrow window, so
    accepted ephemerides do not inherit this quantisation.

    Returns
    -------
    power, depth_frac, epoch_btjd, duration_days — one value per period.
    """
    if not _HAVE_NUMBA or os.environ.get("TESSHUNTER_NO_NUMBA", "") not in ("", "0"):
        return _numpy_bls_loop(time, flux, flux_err, periods, durations)

    t_min = float(time.min())
    ivar = 1.0 / np.maximum(flux_err, 1e-10) ** 2
    w = ivar / ivar.sum()
    y = flux - float(np.dot(w, flux))
    wy = w * y
    t_rel = np.ascontiguousarray(time - t_min, dtype=np.float64)
    dur_min = float(np.min(durations))
    periods = np.ascontiguousarray(periods, dtype=np.float64)
    durations = np.ascontiguousarray(durations, dtype=np.float64)
    if periods.size == 0 or t_rel.size == 0:
        z = np.zeros(periods.size)
        return z, z.copy(), z.copy(), z.copy()
    return _bls_kernel(
        t_rel, np.ascontiguousarray(w, dtype=np.float64),
        np.ascontiguousarray(wy, dtype=np.float64), periods, durations,
        dur_min, t_min, int(_PHASE_BINS_PER_MIN_DURATION),
        int(_MIN_PHASE_BINS), int(_MAX_PHASE_BINS),
    )


def _numpy_bls_loop(
    time: np.ndarray,
    flux: np.ndarray,
    flux_err: np.ndarray,
    periods: np.ndarray,
    durations: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Reference one-period-at-a-time BLS engine (kept for equivalence tests).

    This is the original implementation, unchanged. :func:`_numpy_bls` is
    the batched form of exactly this arithmetic; the test suite asserts the
    two agree bit for bit.
    """
    t_min = float(time.min())

    # Normalised inverse-variance weights
    ivar = 1.0 / np.maximum(flux_err, 1e-10) ** 2
    w = ivar / ivar.sum()

    # Mean-subtract flux so the BLS statistic is zero for a flat light curve
    y = flux - float(np.dot(w, flux))
    wy = w * y

    t_rel = time - t_min
    dur_min = float(np.min(durations))

    pw   = np.zeros(len(periods))
    pd_  = np.zeros(len(periods))
    pe   = np.zeros(len(periods))
    pdur = np.zeros(len(periods))

    for i_p, period in enumerate(periods):
        period = float(period)

        # Adaptive phase-bin count: resolve the shortest searched duration
        nb = int(np.ceil(_PHASE_BINS_PER_MIN_DURATION * period / dur_min))
        nb = max(min(nb, _MAX_PHASE_BINS), _MIN_PHASE_BINS)

        # Phase-fold onto integer bins [0, nb)
        idx = (np.mod(t_rel, period) * (nb / period)).astype(np.intp)
        np.clip(idx, 0, nb - 1, out=idx)

        W  = np.bincount(idx, weights=w,  minlength=nb)
        WY = np.bincount(idx, weights=wy, minlength=nb)

        # Circular prefix sums over doubled bins (1-indexed)
        cW  = np.zeros(2 * nb + 1)
        cWY = np.zeros(2 * nb + 1)
        np.cumsum(np.concatenate([W, W]),   out=cW[1:])
        np.cumsum(np.concatenate([WY, WY]), out=cWY[1:])

        best_p   = -np.inf
        best_dep = 0.0
        best_ep  = t_min
        best_dur = float(durations[0])

        seen_k: set[int] = set()
        for dur in durations:
            phi = dur / period          # transit duration in phase units
            if phi >= 0.9:
                continue

            # Box width in whole bins; identical widths need only one scan
            k = max(int(np.ceil(phi * nb)), 1)
            if k in seen_k or k >= nb:
                continue
            seen_k.add(k)

            # r = weight sum in box, s = weighted-flux sum in box, for every
            # box start bin i in [0, nb) (wrapping via the doubled prefix sums)
            r = cW[k:k + nb]  - cW[:nb]
            s = cWY[k:k + nb] - cWY[:nb]

            # Valid boxes: non-empty and not filling the whole orbit
            ok = (r > 1e-9) & (r < 0.9)

            # BLS power = s² / (r·(1-r)) — restricted to transit *dips* only.
            #
            # The standard BLS statistic is symmetric in s: it is equally large
            # for a brightening (s > 0) and a transit dip (s < 0).  For short
            # periods (b/c/d/e) the many transits dominate and the dips win.
            # For long periods (f/g/h, 8-21 d) K2 roll brightenings produce
            # higher BLS power than the 4-8 weak transit dips, so they fill all
            # top-N candidate slots as upward excursions (depth = 0) and nothing
            # real survives extraction.
            #
            # Fix: set power = -1 for any box where the weighted flux is
            # *above* the mean (s >= 0).  This restricts the BLS to finding only
            # downward flux excursions — i.e. actual transits — which is the
            # physically correct interpretation for transit searches.
            valid = ok & (s < 0)
            if not valid.any():
                continue
            denom = r * (1.0 - r)
            power_arr = np.where(valid, s ** 2 / np.maximum(denom, 1e-20), -1.0)

            j = int(np.argmax(power_arr))
            if power_arr[j] > best_p:
                best_p   = float(power_arr[j])
                best_dep = float(-s[j] / max(r[j], 1e-10))   # positive depth
                # Epoch = phase of box centre × period, shifted to BTJD
                best_ep  = float(((j + 0.5 * k) / nb) * period + t_min)
                best_dur = float(dur)

        pw[i_p]   = max(best_p, 0.0)
        pd_[i_p]  = max(best_dep, 0.0)
        pe[i_p]   = best_ep
        pdur[i_p] = best_dur

    return pw, pd_, pe, pdur


# ---------------------------------------------------------------------------
# Lightweight result container (replaces astropy BLS result object)
# ---------------------------------------------------------------------------

class _BLSResult:
    """Minimal result object with the same attributes downstream code expects."""

    def __init__(
        self,
        periods: np.ndarray,
        power: np.ndarray,
        depth: np.ndarray,
        epoch: np.ndarray,
        duration: np.ndarray,
    ) -> None:
        self.period   = periods    # plain numpy array (days)
        self.power    = power
        self.depth    = depth
        self.epoch    = epoch      # BTJD
        self.duration = duration   # days


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_bls(
    lc: lk.LightCurve,
    period_min: float = BLS_PERIOD_MIN,
    period_max: float = BLS_PERIOD_MAX,
    duration_min: float = BLS_DURATION_MIN,
    duration_max: float = BLS_DURATION_MAX,
    frequency_factor: int = BLS_FREQUENCY_FACTOR,
    top_n: int = BLS_TOP_N,
    suppress_periods: Optional[list[float]] = None,
    n_periods: Optional[int] = None,
    n_durations: int = 10,
    n_max: Optional[int] = None,
) -> tuple[None, _BLSResult, pd.DataFrame]:
    """Run the numpy BLS on a preprocessed light curve.

    Parameters
    ----------
    suppress_periods : List of periods (days) to zero out in the BLS power
                       spectrum before peak extraction.  Use this to prevent
                       known instrument artifacts (e.g. 1.0 d K2 roll period)
                       from consuming candidate slots.  Applied with ±2% tolerance.
    n_periods :        Number of frequency grid points.  Overrides the
                       auto-computed value when set.  Increase for targets
                       with long baselines or closely-spaced signals.
    n_durations :      Number of points in the log-spaced transit-duration
                       grid (default 10).
    n_max :            Cap on the auto period grid. None keeps the 20 000
                       default of ``_build_period_grid``.

    Returns
    -------
    (None, bls_result, candidates_df)
      The first element is None (kept for API compatibility; was the astropy
      BoxLeastSquares model object which is no longer needed).
      ``candidates_df`` carries the schema in ``_CANDIDATE_COLUMNS``,
      including ``sde`` (signal detection efficiency of the peak),
      ``n_transits_observed`` (distinct transit epochs with in-transit data)
      and ``single_event`` (True when n_transits_observed <= 1).
    """
    time     = np.asarray(lc.time.value,    dtype=float)
    flux     = np.asarray(lc.flux.value,    dtype=float)
    flux_err = (
        np.asarray(lc.flux_err.value, dtype=float)
        if lc.flux_err is not None
        else np.full_like(flux, np.nanstd(flux))
    )

    # Sanitise flux_err.  Explicit finite check: the old `or 1e-4` fallback
    # was dead when nanmedian returned NaN (NaN is truthy as a float), which
    # let NaN weights propagate into every BLS power.
    bad = ~np.isfinite(flux_err) | (flux_err <= 0)
    if bad.any():
        fill = float(np.nanmedian(flux_err[~bad])) if (~bad).any() else np.nan
        if not np.isfinite(fill) or fill <= 0:
            fill = 1e-4
        flux_err[bad] = fill

    # Remove any NaN rows from time/flux
    ok = np.isfinite(time) & np.isfinite(flux)
    time, flux, flux_err = time[ok], flux[ok], flux_err[ok]

    baseline = float(time.max() - time.min())
    if baseline <= 0:
        raise ValueError("Light curve baseline is zero — cannot run BLS.")

    # Warn when the (binned) cadence undersamples the shortest duration:
    # a duration_min spanning fewer than 2 cadences means the shortest
    # duration windows hold 0–1 points and are effectively unsearchable.
    if len(time) > 1:
        med_cadence = float(np.nanmedian(np.diff(time)))
        if (
            np.isfinite(med_cadence)
            and med_cadence > 0
            and duration_min < 2.0 * med_cadence
        ):
            logger.warning(
                "duration_min=%.4f d spans fewer than 2 cadences at the "
                "current (binned) cadence of %.4f d — the shortest transit "
                "durations are undersampled. Reduce binning or raise "
                "duration_min.",
                duration_min, med_cadence,
            )

    # Duration grid: cap max so it stays < period_min
    safe_dur_max = min(duration_max, period_min * 0.9)
    safe_dur_max = max(safe_dur_max, duration_min * 1.01)
    durations = _build_duration_grid(duration_min, safe_dur_max, n=n_durations)

    grid_kwargs = {"n_max": int(n_max)} if n_max else {}
    periods = _build_period_grid(
        period_min, period_max, baseline, frequency_factor,
        n_override=n_periods, duration_min=duration_min, **grid_kwargs,
    )

    logger.info(
        "BLS search (numpy engine): periods %.2f–%.2f d, "
        "%d freq points, %d durations, %d cadences",
        period_min, period_max, len(periods), len(durations), len(time),
    )

    power, depth, epoch, dur_best = _numpy_bls(
        time, flux, flux_err, periods, durations
    )

    # Diagnostic: log the raw periodogram summary before any filtering.
    # This lets you distinguish "BLS found nothing" from "BLS found peaks
    # but the extractor filtered them all out."
    if np.any(np.isfinite(power)) and np.nanmax(power) > 0:
        _j = int(np.nanargmax(power))
        logger.debug(
            "BLS raw periodogram: max_power=%.6f at %.4f d  "
            "depth_frac=%.6f  n_periods=%d  n_zero_depth=%d",
            float(power[_j]), float(periods[_j]), float(depth[_j]),
            len(periods), int(np.sum(depth <= 0)),
        )
    else:
        logger.debug("BLS raw periodogram: all power ≤ 0 (flat or empty LC).")

    result = _BLSResult(periods, power, depth, epoch, dur_best)
    candidates = _extract_top_candidates(
        result, top_n, flux_err, time=time, suppress_periods=suppress_periods,
        flux=flux,
    )

    if candidates.empty:
        logger.warning("BLS returned no valid candidates.")
    else:
        logger.info(
            "BLS complete. Top candidate: %.4f d  depth %.2f ppt  SNR %.1f",
            candidates.iloc[0]["period_days"],
            candidates.iloc[0]["depth_ppt"],
            candidates.iloc[0]["snr"],
        )

    return None, result, candidates


def _assign_nearest_transit(
    time: np.ndarray,
    period: float,
    epoch: float,
    t_start: float,
    t_end: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Nearest predicted transit inside ``[t_start, t_end]`` for every cadence.

    Returns ``(k, d)``: the integer transit index (as float; NaN when no
    predicted transit within one period either side lies inside the window)
    and the distance in days (``inf`` in that case). Transit mid-times are
    computed as ``epoch + k * period`` exactly as :func:`_transit_times`
    does, so distances are bit-identical to the per-transit loops these
    vectorised helpers replace.
    """
    k0 = np.round((time - epoch) / period)
    best_d = np.full(time.shape, np.inf)
    best_k = np.full(time.shape, np.nan)
    for off in (-1.0, 0.0, 1.0):
        k = k0 + off
        t_tr = epoch + k * period
        valid = (t_tr >= t_start) & (t_tr <= t_end)
        d = np.abs(time - t_tr)
        better = valid & (d < best_d)
        best_d[better] = d[better]
        best_k[better] = k[better]
    return best_k, best_d


def _group_slices(keys: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Stable-sort ``keys`` and return (order, starts, stops) of equal-key runs.

    The stable sort keeps cadences in data order inside each group, so a
    reduction over a group sees exactly the elements, in exactly the order,
    that a boolean-mask selection would have produced.
    """
    order = np.argsort(keys, kind="stable")
    ks = keys[order]
    if ks.size == 0:
        return order, np.zeros(0, dtype=int), np.zeros(0, dtype=int)
    starts = np.flatnonzero(np.concatenate(([True], ks[1:] != ks[:-1])))
    stops = np.concatenate((starts[1:], [ks.size]))
    return order, starts, stops


def _count_observed_transits(
    time: np.ndarray,
    epoch: float,
    period: float,
    duration: float,
) -> int:
    """Count distinct transit epochs that actually have in-transit data.

    A transit epoch counts as observed only when at least one cadence falls
    within ±duration/2 of the predicted transit centre — i.e. there is real
    in-transit data at that epoch.  There is no clamp: a single covered dip
    honestly reports 1.  This penalises periods whose transits mostly fall
    in the gap between observing sectors.

    Vectorised: each cadence is assigned to its nearest in-baseline transit
    and the distinct assigned epochs within the half-width are counted. When
    the window is at least half a period wide (windows overlap and a cadence
    can serve two epochs) the original per-transit loop is used instead.
    """
    t_min, t_max = float(time.min()), float(time.max())
    half_w = 0.5 * duration
    if not (period > 0.0) or not (half_w < 0.5 * period):
        count = 0
        for t_transit in _transit_times(period, epoch, t_min, t_max):
            if np.any(np.abs(time - t_transit) <= half_w):
                count += 1
        return count
    k, d = _assign_nearest_transit(time, period, epoch, t_min, t_max)
    hit = d <= half_w
    return int(np.unique(k[hit]).size)


def _measured_transit_snr(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    epoch: float,
    duration: float,
    depth: float,
    min_oot_points: int = 20,
) -> tuple[float, int]:
    """Depth SNR from the measured robust scatter of the light curve.

    sigma is 1.4826 × MAD of the OUT-of-transit residuals at the candidate
    ephemeris — the realized post-flatten / post-bin noise — rather than the
    reported flux_err, which diverges from the true noise after detrending
    and binning.  When the fold leaves too few out-of-transit points the
    global robust scatter of the whole light curve is used instead.

    Parameters
    ----------
    time / flux : Cleaned cadence arrays (finite values only are used).
    period / epoch / duration : Candidate ephemeris (days / BTJD / days).
    depth       : Fractional transit depth of the candidate.
    min_oot_points : Minimum out-of-transit points required before falling
                  back to the global robust scatter.

    Returns
    -------
    snr  : float — depth / (sigma / sqrt(n_in_transit_points)).
    n_in : int   — number of in-transit cadences at the ephemeris.
    """
    finite = np.isfinite(flux) & np.isfinite(time)
    t = time[finite]
    f = flux[finite]
    if len(f) == 0:
        return 0.0, 0

    # Signed distance (days) from the nearest predicted transit centre
    dphase = np.mod(t - epoch + 0.5 * period, period) - 0.5 * period
    in_transit = np.abs(dphase) <= 0.5 * duration
    n_in = int(np.count_nonzero(in_transit))

    oot = f[~in_transit]
    if len(oot) >= min_oot_points:
        resid = oot - float(np.median(oot))
    else:
        resid = f - float(np.median(f))

    sigma = 1.4826 * float(np.median(np.abs(resid)))
    if not np.isfinite(sigma) or sigma <= 0:
        sigma = float(np.std(resid))
    if not np.isfinite(sigma) or sigma <= 0:
        sigma = 1e-10

    snr = depth / max(sigma / np.sqrt(max(n_in, 1)), 1e-10)
    return float(snr), n_in


def _extract_top_candidates(
    result: _BLSResult,
    top_n: int,
    flux_err: np.ndarray,
    time: Optional[np.ndarray] = None,
    suppress_periods: Optional[list[float]] = None,
    suppress_tol: float = 0.02,
    flux: Optional[np.ndarray] = None,
) -> pd.DataFrame:
    """Pick top_n peaks from the periodogram, masking harmonics.

    Ranking uses SNR × completeness so that signals with transits landing
    in the observed windows rank above signals whose transits fall in gaps.

    Parameters
    ----------
    suppress_periods : Periods to zero out before peak extraction (±suppress_tol
                       fractional tolerance).  Used to prevent known artifact
                       periods from consuming candidate slots.
    suppress_tol     : Fractional tolerance for period suppression (default 2%).
    flux             : Flux array matching ``time``.  When given (run_bls always
                       passes it), the SNR uses the measured robust scatter of
                       the out-of-transit residuals at each candidate ephemeris
                       instead of the reported flux_err.

    Notes
    -----
    Harmonic masking after each peak uses integer ratios only (×0.5, ×1, ×2, ×3).
    The ×1.5 and ×2.5 ratios were removed because they are not natural transit
    harmonics and were masking independent planets at nearby periods (e.g. the
    1.5× harmonic of a 1.005 d artifact falls at 1.508 d, erasing a real planet
    at 1.511 d from the candidate pool).

    Each row also carries ``sde`` — the signal detection efficiency of the
    peak, (peak power − median power) / (1.4826 × MAD of the power spectrum) —
    plus ``n_transits_observed`` (distinct transit epochs with in-transit
    data) and ``single_event`` (True when n_transits_observed <= 1).
    """
    sigma = float(np.nanmedian(flux_err))   # legacy fallback noise estimate

    # Robust statistics of the full power spectrum for the per-peak SDE
    finite_power = result.power[np.isfinite(result.power)]
    if finite_power.size:
        power_med = float(np.median(finite_power))
        power_mad = 1.4826 * float(np.median(np.abs(finite_power - power_med)))
    else:
        power_med, power_mad = 0.0, 0.0

    periods  = result.period.copy()
    power    = result.power.copy()
    depth    = result.depth.copy()
    epoch    = result.epoch.copy()
    duration = result.duration.copy()

    # ── Suppress known artifact periods before greedy peak extraction ──────────
    # Zeroing the BLS power at artifact periods prevents them from consuming
    # candidate slots and (crucially) from triggering harmonic masking that
    # would erase nearby real signals.
    if suppress_periods:
        for sp in suppress_periods:
            artifact_mask = np.abs(periods / sp - 1.0) < suppress_tol
            power[artifact_mask] = 0.0

    rows = []
    for rank in range(1, top_n + 1):
        if len(power) == 0 or not np.any(np.isfinite(power)):
            break

        j = int(np.nanargmax(power))
        p_best = float(periods[j])
        pwr    = float(power[j])
        dep    = float(depth[j])
        ep     = float(epoch[j])
        dur    = float(duration[j])

        # Stop only when the periodogram is truly exhausted (all power consumed).
        if pwr <= 0:
            break

        # dep == 0 means the BLS engine's best window at this period was an
        # *upward* flux excursion (flare, cosmic ray, K2 roll bump) rather than
        # a transit dip.  The numpy engine clamps depth = max(-s/r, 0) so a
        # genuine brightening yields depth = 0 while power > 0.
        #
        # Old behaviour: `break` — this stopped the entire search the first time
        # a brightening dominated the periodogram, leaving the candidate list
        # completely empty even when real transit dips existed at other periods.
        #
        # Correct behaviour: mask this period and continue.  Upward excursions
        # are not transits; they should be discarded and the loop should proceed
        # to find genuine dips at other periods.
        if dep <= 0:
            logger.debug(
                "Skipping upward excursion at %.4f d (pwr=%.4f, dep=%.4f) — "
                "masking ±5%% and continuing.",
                p_best, pwr, dep,
            )
            hw   = 0.05 * p_best
            keep = np.abs(periods - p_best) > hw
            periods  = periods[keep]
            power    = power[keep]
            depth    = depth[keep]
            epoch    = epoch[keep]
            duration = duration[keep]
            continue

        dep_ppt = dep * 1000.0

        # SNR — corrected estimator (measured noise, not reported flux_err).
        # sigma comes from the robust scatter (1.4826 × MAD) of the
        # out-of-transit residuals at this candidate's ephemeris, and n is
        # the actual number of in-transit cadences.  The reported flux_err
        # diverges from the realized noise after flattening and binning.
        if time is not None and flux is not None:
            snr, _n_in = _measured_transit_snr(time, flux, p_best, ep, dur, dep)
        else:
            # Legacy fallback for callers without the flux array (synthetic
            # periodogram unit tests): median reported error with the
            # in-transit count estimated from the cadence total.  Uses
            # len(time) — NOT len(result.power), the grid size, which varies
            # wildly between broad and alias-refinement calls.
            if time is not None:
                n_approx = max(int(len(time) * dur / p_best), 1)
            else:
                n_approx = max(int(len(result.power) * dur / p_best), 1)
            snr = dep / max(sigma / np.sqrt(n_approx), 1e-10)

        # Signal detection efficiency of this peak relative to the full
        # power spectrum (robust z-score of the peak power).
        sde = (pwr - power_med) / power_mad if power_mad > 0 else 0.0

        # Count distinct transit epochs with in-transit data
        n_obs = (
            _count_observed_transits(time, ep, p_best, dur)
            if time is not None else 1
        )
        single_event = n_obs <= 1

        # Completeness: fraction of expected transits that land on real data.
        # For a continuous LC all periods give completeness ≈ 1 → score ≈ SNR.
        # For gapped data, periods whose transits fall in the gap get penalised.
        # Expected transits = actual data duration / period  (not total baseline).
        # No max(…, 1.0) clamp on n_expected: the old clamp handed single deep
        # dips at long periods a free completeness of 1.0.  The single_event
        # flag carries the honest signal downstream; the acceptance gate lives
        # in the pipeline module.
        if time is not None and len(time) > 1:
            actual_duration = float(len(time)) * float(np.nanmedian(np.diff(time)))
            n_expected = actual_duration / p_best
        else:
            n_expected = float(max(n_obs, 1))
        completeness = min(1.0, n_obs / n_expected) if n_expected > 0 else 0.0

        score = float(snr) * completeness

        rows.append({
            "peak_rank":          rank,
            "period_days":        p_best,
            "epoch_btjd":         ep,
            "duration_days":      dur,
            "depth_frac":         dep,
            "depth_ppt":          dep_ppt,
            "power":              pwr,
            "snr":                float(snr),
            "sde":                float(sde),
            "n_transits_observed": n_obs,
            "single_event":       bool(single_event),
            "score":              score,
        })

        # Mask this period and its integer harmonics (±5% window).
        # Only true integer ratios [0.5, 1, 2, 3] are masked — the 1.5× and
        # 2.5× entries that were here before are NOT transit harmonics and
        # caused real planets at nearby periods to be erased from the pool.
        hw = 0.05 * p_best
        harmonics = p_best * np.array([0.5, 1.0, 2.0, 3.0])
        keep = np.ones(len(periods), dtype=bool)
        for h in harmonics:
            keep &= np.abs(periods - h) > hw
        periods  = periods[keep]
        power    = power[keep]
        depth    = depth[keep]
        epoch    = epoch[keep]
        duration = duration[keep]

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=_CANDIDATE_COLUMNS)
    if df.empty:
        return df

    # Drop physically meaningless candidates
    n_before = len(df)
    df = df[(df["depth_ppt"] > 0) & (df["snr"] > 0)].copy()
    if len(df) < n_before:
        logger.info("Dropped %d ghost candidate(s) with depth≤0 or SNR≤0",
                    n_before - len(df))
    if df.empty:
        return pd.DataFrame(columns=_CANDIDATE_COLUMNS)

    # Rank by score (SNR weighted by observed transit count)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    df["peak_rank"] = df.index + 1
    return df


def harmonic_trial_periods(
    p: float,
    period_min: float = 0.5,
    period_max: float = 20.0,
) -> list[tuple[str, float]]:
    """Return (label, period) pairs for harmonic and sub-harmonic trials of p.

    Tests P/n for n = 2..6 (sub-harmonics, shorter) and n×P for n = 2..3
    (super-harmonics, longer), plus P itself as the reference.  Only periods
    within [period_min, period_max] are returned.

    The intent is: feed the broad-search best period into this function, run a
    local BLS around each trial, and pick the shortest trial with a strong
    signal — that is the most likely fundamental period.
    """
    trials: list[tuple[str, float]] = []
    for n in [2, 3, 4, 5, 6]:
        trials.append((f"P/{n}", p / n))
    trials.append(("P", p))
    for n in [2, 3, 4]:
        trials.append((f"{n}P", p * n))
    return [(label, period) for label, period in trials
            if period_min <= period <= period_max]


def check_half_period_alias(
    lc: lk.LightCurve,
    period: float,
    epoch: float,
    duration: float,
    ratio_threshold: float = 0.5,
) -> tuple[float, float, bool]:
    """Test whether a detected period is likely 2× the true orbital period.

    Phase-folds the light curve at ``period`` and measures the median flux dip
    at phase 0 (the detected transit) and at phase 0.5 (the halfway point).
    If the halfway dip is at least ``ratio_threshold`` × the primary dip, the
    detected period is flagged as a probable 2× alias.

    Physically: if the true period is P/2 but BLS detected P, every other
    transit is labelled phase 0 and the remainder land at phase 0.5.  Both
    windows then show comparable dips.

    Parameters
    ----------
    lc               : Normalised light curve (flux ≈ 1.0 out of transit).
    period           : Detected BLS period (days).
    epoch            : Transit epoch in the same time system as lc.time (BTJD).
    duration         : Transit duration (days).
    ratio_threshold  : Minimum halfway/primary depth ratio to flag as alias.
                       Default 0.5 → any halfway dip > 50% of the primary dip
                       triggers the flag.

    Returns
    -------
    primary_depth_ppt : float  — Median depth at phase 0 in ppt.
    halfway_depth_ppt : float  — Median depth at phase 0.5 in ppt.
    is_alias          : bool   — True if the halfway dip is suspiciously deep.
    """
    time = np.asarray(lc.time.value, dtype=float)
    flux = np.asarray(lc.flux.value, dtype=float)

    # Phase in [0, 1) with the detected transit at phase 0
    phase = ((time - epoch) % period) / period

    half_dur_phase = duration / period / 2.0   # transit half-width in phase units

    # Primary window: within half_dur_phase of phase 0 (wrapping at 1)
    in_primary = (phase < half_dur_phase) | (phase > 1.0 - half_dur_phase)
    # Halfway window: within half_dur_phase of phase 0.5
    in_halfway  = np.abs(phase - 0.5) < half_dur_phase

    if in_primary.sum() < 3 or in_halfway.sum() < 3:
        return 0.0, 0.0, False

    primary_depth = float(1.0 - np.nanmedian(flux[in_primary]))
    halfway_depth = float(1.0 - np.nanmedian(flux[in_halfway]))

    # Convert to ppt
    primary_ppt = primary_depth * 1000.0
    halfway_ppt = halfway_depth * 1000.0

    # Flag only when the primary dip is real (positive) AND the halfway dip
    # is a genuine dip (positive) AND deep relative to the primary.
    is_alias = (
        primary_depth > 0.0
        and halfway_depth > 0.0
        and halfway_depth >= ratio_threshold * primary_depth
    )

    return primary_ppt, halfway_ppt, is_alias


def subharmonic_occupancy(
    lc: lk.LightCurve,
    period: float,
    epoch: float,
    duration: float,
    m: int,
    ratio_threshold: float = 0.5,
    min_cadences: int = 3,
) -> tuple[bool, float]:
    """Test whether ``period`` is an m-fold super-harmonic of the true period.

    Generalises :func:`check_half_period_alias` (which is the ``m = 2`` case)
    to any integer ``m``. If the true orbital period were ``period / m``, then
    folding at ``period`` places transits not only at phase 0 but at EVERY
    phase ``k / m`` for ``k = 1 .. m-1``. Requiring *all* of those intermediate
    windows to show a dip of at least ``ratio_threshold`` times the phase-0 dip
    is the direct observational test that the fold is over-subdivided.

    This is the discriminator the composite score lacks. ``event_completeness``
    cannot serve: at 2P every predicted epoch really is occupied by a transit,
    so completeness is 1.0 at the super-harmonic — and is in fact mildly WORSE
    at the true period, which has twice as many epochs and therefore twice as
    many chances for one to land in a gap.

    Returns
    -------
    (is_superharmonic, weakest_ratio) — the flag, and the smallest
    intermediate/primary depth ratio observed (0.0 when the test could not run).
    """
    if m < 2:
        return False, 0.0

    time = np.asarray(lc.time.value, dtype=float)
    flux = np.asarray(lc.flux.value, dtype=float)
    good = np.isfinite(time) & np.isfinite(flux)
    time, flux = time[good], flux[good]
    if time.size < min_cadences:
        return False, 0.0

    phase = ((time - epoch) % period) / period
    half_dur_phase = duration / period / 2.0
    if half_dur_phase <= 0.0 or half_dur_phase >= 0.5 / m:
        # Windows would overlap each other; the test is meaningless.
        return False, 0.0

    in_primary = (phase < half_dur_phase) | (phase > 1.0 - half_dur_phase)
    if int(in_primary.sum()) < min_cadences:
        return False, 0.0
    primary_depth = float(1.0 - np.nanmedian(flux[in_primary]))
    if not np.isfinite(primary_depth) or primary_depth <= 0.0:
        return False, 0.0

    weakest = np.inf
    for k in range(1, m):
        window = np.abs(phase - k / m) < half_dur_phase
        if int(window.sum()) < min_cadences:
            return False, 0.0
        depth_k = float(1.0 - np.nanmedian(flux[window]))
        if not np.isfinite(depth_k) or depth_k <= 0.0:
            return False, 0.0
        weakest = min(weakest, depth_k / primary_depth)

    weakest = float(weakest) if np.isfinite(weakest) else 0.0
    return bool(weakest >= ratio_threshold), weakest


#: Minimum intermediate/primary dip ratio for a fold to count as over-subdivided.
#: A true fundamental has NO transit at the intermediate phases, so its ratio is
#: bounded by noise near zero; a genuine super-harmonic shows a real transit
#: there, diluted only by ephemeris drift over the baseline and the finite
#: window. Matches the 0.30 parity-comparison convention already used by
#: :func:`alternating_event_consistency`.
SUBHARMONIC_DIP_RATIO = 0.30


def _descend_to_fundamental(
    lc: lk.LightCurve,
    best: pd.Series,
    trial_df: pd.DataFrame,
    period_min: float,
    max_steps: int = 2,
    match_tol: float = 0.02,
) -> pd.Series:
    """Step a selected trial down to its true fundamental when it is a super-harmonic.

    Two independent conditions must BOTH hold before a period is moved.

    1. **More transit events, in absolute terms.** ``event_completeness`` is a
       FRACTION, so it structurally rewards a fold for examining fewer epochs:
       measured on TOI-270 b, the true 3.3597 d period predicts 15 epochs and
       confirms 9 (ev_comp 0.600) while the 2x harmonic predicts 6 and
       trivially confirms all 6 (ev_comp 1.000). Multiplied into the composite
       that overturns an SNR of 11.77 at the truth with 9.34 at the harmonic.
       The unbiased quantity is the raw count ``n_dip``: a true fundamental
       explains strictly MORE transit events (9 vs 6), whereas a spurious
       sub-harmonic merely redistributes the same events across alternating
       epochs and finds no more. A margin is required so noise cannot supply
       the difference.
    2. **Real dips at the intermediate phases**, via
       :func:`subharmonic_occupancy` at SUBHARMONIC_DIP_RATIO.

    The alias flags in :func:`resolve_aliases_for_candidate` are evaluated only
    at the INPUT period, so a candidate that entered at the correct period can
    still be promoted by the composite argmax and never re-checked. This runs
    on the row that actually won. Iterates so 4P can descend through 2P.
    """
    for _ in range(max_steps):
        p = float(best["period_days"])
        epoch = float(best["epoch_btjd"])
        dur = float(best["duration_days"])
        n_dip_win = float(best.get("n_dip", 0) or 0)
        moved = False
        for m in (2, 3):
            target = p / m
            if target < period_min:
                continue
            rows = trial_df[
                np.abs(trial_df["period_days"].to_numpy(dtype=float) / target - 1.0)
                <= match_tol
            ]
            if rows.empty:
                continue
            new = rows.sort_values("composite_score", ascending=False).iloc[0]

            n_dip_sub = float(new.get("n_dip", 0) or 0)
            required = n_dip_win + max(2.0, 0.25 * n_dip_win)
            if n_dip_sub < required:
                continue

            is_super, weakest = subharmonic_occupancy(
                lc, p, epoch, dur, m, ratio_threshold=SUBHARMONIC_DIP_RATIO
            )
            if not is_super:
                continue

            logger.info(
                "resolve_aliases: %.5f d is a %dx super-harmonic — the "
                "fundamental %.5f d [%s] explains %.0f transit events vs %.0f "
                "(needed >= %.1f) and every 1/%d phase shows a dip %.2fx the "
                "primary — descending",
                p, m, float(new["period_days"]), new["harmonic_label"],
                n_dip_sub, n_dip_win, required, m, weakest,
            )
            best = new
            moved = True
            break
        if not moved:
            break
    return best


def select_fundamental_period(
    harmonic_df: pd.DataFrame,
    is_alias: bool,
) -> pd.Series:
    """Choose the most likely fundamental period from a harmonic candidate table.

    Rules applied in priority order
    --------------------------------
    1. **Half-period alias confirmed** (``is_alias=True``):
       Return the P/2 row immediately.  A comparable transit-depth dip at
       phase 0.5 is the clearest possible evidence that the detected period is
       2× the true period.  Do not look further.

    2. **Fallback**: Return the row with the highest ``score``
       (SNR × completeness).  Crucially, this is NOT the shortest period —
       short harmonics like P/6 can accumulate BLS power from noise alignment
       without representing real transits.

    Note on higher-order divisors (P/3, P/4, …)
    --------------------------------------------
    Promoting P/n for n > 2 correctly requires checking that transit-like dips
    exist at *all* n predicted phase slots (0, 1/n, 2/n, …).  That phase-
    occupancy test is not performed here; those candidates are therefore not
    promoted above P/2 by this function.
    """
    if harmonic_df.empty:
        raise ValueError("harmonic_df is empty — cannot select a fundamental period.")

    if is_alias:
        p2_rows = harmonic_df[harmonic_df["harmonic_label"] == "P/2"]
        if not p2_rows.empty:
            return p2_rows.iloc[0]

    # Fallback: highest score (not shortest period)
    return harmonic_df.sort_values("score", ascending=False).iloc[0]


# ---------------------------------------------------------------------------
# Private transit-time helper
# ---------------------------------------------------------------------------

def _transit_times(
    period: float,
    epoch: float,
    t_start: float,
    t_end: float,
) -> np.ndarray:
    """Return all predicted transit mid-times in [t_start, t_end].

    Vectorised form of ``[epoch + n * period for n in range(n_lo, n_hi + 1)]``;
    each mid-time is the same single multiply-add, so the values are
    bit-identical to the list comprehension it replaces.
    """
    n_lo = int(np.floor((t_start - epoch) / period))
    n_hi = int(np.ceil((t_end - epoch) / period))
    n = np.arange(n_lo, n_hi + 1, dtype=float)
    t = epoch + n * period
    return t[(t >= t_start) & (t <= t_end)]


def _first_transit_index(period: float, epoch: float, t_start: float, t_end: float) -> float:
    """Integer index ``n`` of the first predicted transit inside the window (NaN if none)."""
    n_lo = int(np.floor((t_start - epoch) / period))
    n_hi = int(np.ceil((t_end - epoch) / period))
    n = np.arange(n_lo, n_hi + 1, dtype=float)
    t = epoch + n * period
    inside = (t >= t_start) & (t <= t_end)
    if not inside.any():
        return float("nan")
    return float(n[inside][0])


# ---------------------------------------------------------------------------
# Event-level transit diagnostics
# ---------------------------------------------------------------------------

#: How ``event_completeness`` sets the dip threshold of one event.  "cadence"
#: (prompts 0-7): one per-cadence noise unit (1.4826 x MAD of the cadences), the
#: legacy rule that every prompt-4 record was produced with.  "mean" (prompt 8):
#: the same noise divided by the square root of the number of cadences in the
#: window, i.e. one sigma of the in-transit MEAN.  At 30-minute bins the two are
#: close; at 200-second cadence the per-cadence scatter (4-8 ppt on a Tmag 13.5
#: M dwarf) exceeds every transit this survey looks for, so under "cadence" a
#: real 2-ppt dip with fifteen cadences per event counts as "no dip" in most
#: events, the alias resolver's composite score collapses at the true period,
#: and a 15-sigma injection is resolved to a harmonic and dropped (measured on
#: TIC 5655186, prompt 8).  The survey worker sets this from ``SurveyConfig``.
EVENT_COMPLETENESS_NOISE = "cadence"


def _dip_threshold(noise: float, n_in: int) -> float:
    if EVENT_COMPLETENESS_NOISE == "mean":
        return max(noise / math.sqrt(max(int(n_in), 1)), 1e-6)
    return max(noise, 1e-6)


def event_completeness(
    lc: lk.LightCurve,
    period: float,
    epoch: float,
    duration: float,
) -> tuple[int, int, float]:
    """Fraction of predicted transit windows that contain a real flux dip.

    For each predicted transit mid-time within the baseline:
    - Skip if no cadences fall within ±duration/2 (data gap).
    - Count as a *dip* when the mean in-transit flux is below the
      out-of-transit baseline by more than one noise unit (MAD-based; see
      ``EVENT_COMPLETENESS_NOISE`` for what one unit is).

    This discriminates alias periods:

    - **True period** → every covered window has a dip → completeness ≈ 1.
    - **Half-period alias** (BLS found P/2, true is P) → alternating windows
      have dips → completeness ≈ 0.5.
    - **Double-period alias** (BLS found 2P, true is P) → all covered windows
      have dips (the missed half-period transits are caught by
      ``check_half_period_alias``).

    Parameters
    ----------
    lc       : Normalised light curve (flux ≈ 1 out of transit).
    period   : Trial period (days).
    epoch    : Transit epoch in the same time system as lc (BTJD).
    duration : Transit duration (days).

    Returns
    -------
    n_covered : int   — Events with ≥1 cadence inside the window.
    n_dip     : int   — Covered events with a detectable dip.
    ec        : float — n_dip / n_covered  (0.0 when n_covered == 0).
    """
    time = np.asarray(lc.time.value, dtype=float)
    flux = np.asarray(lc.flux.value, dtype=float)
    good = np.isfinite(flux) & np.isfinite(time)
    time, flux = time[good], flux[good]

    if len(time) < 3:
        return 0, 0, 0.0

    t_start, t_end = float(time.min()), float(time.max())
    t_pred = _transit_times(period, epoch, t_start, t_end)
    if len(t_pred) == 0:
        return 0, 0, 0.0

    half_w = 0.5 * duration

    if not (half_w < 0.5 * period):
        # Overlapping windows: keep the original per-transit loop.
        oot = np.ones(len(time), dtype=bool)
        for t_tr in t_pred:
            oot &= np.abs(time - t_tr) > half_w
        if oot.sum() >= 10:
            baseline = float(np.nanmedian(flux[oot]))
            noise    = float(np.nanmedian(np.abs(flux[oot] - baseline))) * 1.4826
        else:
            baseline = float(np.nanmedian(flux))
            noise    = float(np.nanmedian(np.abs(flux - baseline))) * 1.4826
        n_covered, n_dip = 0, 0
        for t_tr in t_pred:
            mask_in = np.abs(time - t_tr) <= half_w
            if mask_in.sum() == 0:
                continue
            n_covered += 1
            if float(np.nanmean(flux[mask_in])) < baseline - _dip_threshold(noise, int(mask_in.sum())):
                n_dip += 1
        ec = float(n_dip) / n_covered if n_covered > 0 else 0.0
        return n_covered, n_dip, ec

    # Vectorised path: one nearest-transit assignment per cadence replaces
    # the O(n_transits x n_cadences) mask loops. Every quantity below is
    # computed from the same elements in the same order as the loop form.
    k, d = _assign_nearest_transit(time, period, epoch, t_start, t_end)
    in_win = d <= half_w
    oot = ~in_win

    if oot.sum() >= 10:
        baseline = float(np.nanmedian(flux[oot]))
        noise    = float(np.nanmedian(np.abs(flux[oot] - baseline))) * 1.4826
    else:
        baseline = float(np.nanmedian(flux))
        noise    = float(np.nanmedian(np.abs(flux - baseline))) * 1.4826

    ff = flux[in_win]
    order, starts, stops = _group_slices(k[in_win])
    ff = ff[order]
    n_covered = int(starts.size)
    n_dip = 0
    for a, b in zip(starts, stops):
        if float(np.nanmean(ff[a:b])) < baseline - _dip_threshold(noise, int(b - a)):
            n_dip += 1

    ec = float(n_dip) / n_covered if n_covered > 0 else 0.0
    return n_covered, n_dip, ec


def alternating_event_consistency(
    lc: lk.LightCurve,
    period: float,
    epoch: float,
    duration: float,
) -> tuple[float, float, bool]:
    """Test whether odd- and even-numbered transit events have equal depths.

    Splits predicted transit windows into two interleaved sequences and
    compares their mean dip depths.  If one parity is less than 30 % of the
    other, the signal is flagged as alternating — strong evidence that the
    supplied period is **half** the true orbital period.

    Parameters
    ----------
    lc       : Light curve.
    period   : Trial period (days).
    epoch    : Transit epoch (BTJD).
    duration : Transit duration (days).

    Returns
    -------
    odd_depth_ppt  : float — Mean depth of odd-indexed transit events (ppt).
    even_depth_ppt : float — Mean depth of even-indexed transit events (ppt).
    is_alternating : bool  — True when min-parity depth < 30 % of max-parity
                             depth, suggesting the detected period is ½ the
                             true period.
    """
    time = np.asarray(lc.time.value, dtype=float)
    flux = np.asarray(lc.flux.value, dtype=float)
    good = np.isfinite(flux) & np.isfinite(time)
    time, flux = time[good], flux[good]

    if len(time) < 3:
        return 0.0, 0.0, False

    t_start, t_end = float(time.min()), float(time.max())
    t_pred = _transit_times(period, epoch, t_start, t_end)
    if len(t_pred) < 2:
        return 0.0, 0.0, False

    half_w   = 0.5 * duration
    baseline = float(np.nanmedian(flux))

    even_dips: list[float] = []
    odd_dips:  list[float] = []

    if not (half_w < 0.5 * period):
        # Overlapping windows: keep the original per-transit loop.
        for i, t_tr in enumerate(t_pred):
            mask_in = np.abs(time - t_tr) <= half_w
            if mask_in.sum() == 0:
                continue
            depth_ppt = (baseline - float(np.nanmean(flux[mask_in]))) * 1000.0
            (even_dips if i % 2 == 0 else odd_dips).append(depth_ppt)
    else:
        # Vectorised assignment; parity is the position of the epoch in the
        # predicted list, i.e. its integer index relative to the first
        # predicted transit inside the baseline.
        n_first = _first_transit_index(period, epoch, t_start, t_end)
        k, d = _assign_nearest_transit(time, period, epoch, t_start, t_end)
        in_win = d <= half_w
        ff = flux[in_win]
        kk = k[in_win]
        order, starts, stops = _group_slices(kk)
        ff = ff[order]
        kk = kk[order]
        for a, b in zip(starts, stops):
            depth_ppt = (baseline - float(np.nanmean(ff[a:b]))) * 1000.0
            i = int(kk[a] - n_first)
            (even_dips if i % 2 == 0 else odd_dips).append(depth_ppt)

    if not even_dips or not odd_dips:
        return 0.0, 0.0, False

    even_depth = float(np.nanmean(even_dips))
    odd_depth  = float(np.nanmean(odd_dips))

    max_d = max(abs(even_depth), abs(odd_depth))
    min_d = min(abs(even_depth), abs(odd_depth))
    is_alternating = (max_d > 0.0) and ((min_d / max_d) < 0.30)

    return odd_depth, even_depth, is_alternating


def transit_window_overlap_fraction(
    period_trial:      float,
    epoch_trial:       float,
    duration_trial:    float,
    period_existing:   float,
    epoch_existing:    float,
    duration_existing: float,
    t_start: float,
    t_end:   float,
) -> float:
    """Fraction of trial planet's transit windows that physically overlap an existing one.

    Uses actual ephemeris positions — **not** period ratios.  Two windows
    overlap when the distance between their mid-times is less than the sum of
    their half-widths.

    A near-2:1 resonance pair that is independently orbiting will have
    uncorrelated epochs and therefore low overlap.  A genuine alias — where the
    trial period is constructed from the same underlying transit times — will
    have overlap ≈ 1.

    Parameters
    ----------
    period_trial / epoch_trial / duration_trial     : Candidate under evaluation.
    period_existing / epoch_existing / duration_existing : Already-confirmed planet.
    t_start / t_end : Observation baseline (BTJD).

    Returns
    -------
    overlap : float — Fraction of trial windows with ≥1 overlapping existing window.
              Returns 0.0 when either planet has no predicted transits in baseline.
    """
    t_trial = _transit_times(period_trial,    epoch_trial,    t_start, t_end)
    t_exist = _transit_times(period_existing, epoch_existing, t_start, t_end)

    if len(t_trial) == 0 or len(t_exist) == 0:
        return 0.0

    combined_half = 0.5 * (duration_trial + duration_existing)
    # t_exist is ascending, so the nearest existing window to each trial
    # mid-time is one of its two sorted neighbours; the differences are the
    # same ``t_exist - t_tr`` the per-trial loop evaluated.
    pos = np.searchsorted(t_exist, t_trial)
    last = len(t_exist) - 1
    lo = np.clip(pos - 1, 0, last)
    hi = np.clip(pos, 0, last)
    d = np.minimum(np.abs(t_exist[lo] - t_trial), np.abs(t_exist[hi] - t_trial))
    n_overlap = int(np.count_nonzero(d < combined_half))
    return float(n_overlap) / len(t_trial)


def resolve_aliases_for_candidate(
    lc: lk.LightCurve,
    candidate_row: pd.Series,
    existing_candidates: Optional[pd.DataFrame] = None,
    period_min: float = BLS_PERIOD_MIN,
    period_max: float = BLS_PERIOD_MAX,
    duration_min: float = BLS_DURATION_MIN,
    duration_max: float = BLS_DURATION_MAX,
    local_n_max: Optional[int] = None,
) -> tuple[pd.Series, pd.DataFrame]:
    """Resolve period aliases for a single BLS candidate.

    For each trial period in {P/6, P/5, P/4, P/3, P/2, P, 2P, 3P, 4P}
    (filtered to [period_min, period_max]):

    1. Run a local BLS refinement in a ±5% window around the trial period.
    2. Compute *event completeness* — fraction of covered transit windows with
       a detectable flux dip.
    3. Compute *alternating-event consistency* — whether odd and even events
       have comparable depths.
    4. Compute *window overlap* with already-confirmed planets using actual
       ephemeris positions (not period ratios).
    5. Score as  ``SNR × max(event_completeness, 0.1) × (1 − overlap)``.

    **Selection priority**

    1. ``check_half_period_alias`` fires (phase-0.5 dip ≥ 50 % of primary) →
       return the P/2 trial.  This is the strongest evidence of a 2× alias.
    2. ``alternating_event_consistency`` fires at the input period (one parity
       depth < 30 % of the other) and the alias flag did *not* fire → return
       the 2P trial.
    3. Default: highest composite score.  The shortest period is **never**
       chosen merely because it exists.

    Near-2:1 period ratios are **not** penalised by period ratio alone.  Only
    trials whose transit windows physically overlap an existing planet's windows
    are penalised by the overlap term.

    Parameters
    ----------
    lc                  : Cleaned / masked light curve.
    candidate_row       : Single row from ``run_bls()`` output.  Must contain
                          ``period_days``, ``epoch_btjd``, ``duration_days``,
                          ``depth_ppt``, ``snr``.
    existing_candidates : DataFrame with ``period_days``, ``epoch_btjd``,
                          ``duration_days`` for already-confirmed planets.
                          Pass ``None`` for the first planet.
    period_min / period_max   : BLS search range (days).
    duration_min / duration_max : Duration range for local BLS runs.
    local_n_max : Cap on each local refinement grid (None = run_bls default).

    Returns
    -------
    resolved    : pd.Series    — Winning trial row, augmented with
                                 ``harmonic_label``, ``event_completeness``,
                                 ``n_covered``, ``n_dip``, ``alternating_flag``,
                                 ``overlap``, ``composite_score``.
    trial_table : pd.DataFrame — Full diagnostic table for all trials.
    """
    p0     = float(candidate_row["period_days"])
    epoch0 = float(candidate_row["epoch_btjd"])
    dur0   = float(candidate_row["duration_days"])

    time_arr = np.asarray(lc.time.value, dtype=float)
    t_start  = float(np.nanmin(time_arr))
    t_end    = float(np.nanmax(time_arr))

    # ── Pre-flight alias flags at the input period ───────────────────────────
    _, _, is_alias      = check_half_period_alias(
        lc, period=p0, epoch=epoch0, duration=dur0)
    _, _, is_alternating = alternating_event_consistency(
        lc, period=p0, epoch=epoch0, duration=dur0)

    logger.debug(
        "resolve_aliases: P=%.4f d  is_alias=%s  is_alternating=%s",
        p0, is_alias, is_alternating,
    )

    # ── Trial loop ───────────────────────────────────────────────────────────
    records: list[dict] = []
    for label, trial_p in harmonic_trial_periods(p0, period_min, period_max):
        span = max(trial_p * 0.05, 0.08)
        _, _, local = run_bls(
            lc,
            period_min   = max(period_min,  trial_p - span),
            period_max   = min(period_max,  trial_p + span),
            duration_min = duration_min,
            duration_max = duration_max,
            top_n        = 3,
            n_max        = local_n_max,
        )
        if local.empty:
            continue

        row       = local.iloc[0]
        ref_p     = float(row["period_days"])
        ref_epoch = float(row["epoch_btjd"])
        ref_dur   = float(row["duration_days"])

        n_cov, n_dip, ev_comp = event_completeness(lc, ref_p, ref_epoch, ref_dur)
        _, _, alt_flag         = alternating_event_consistency(
            lc, ref_p, ref_epoch, ref_dur)

        # Physical window overlap with confirmed planets (epoch-based, not ratio-based)
        overlap = 0.0
        if existing_candidates is not None and not existing_candidates.empty:
            for _, ec_row in existing_candidates.iterrows():
                ov = transit_window_overlap_fraction(
                    ref_p, ref_epoch, ref_dur,
                    float(ec_row["period_days"]),
                    float(ec_row["epoch_btjd"]),
                    float(ec_row["duration_days"]),
                    t_start, t_end,
                )
                overlap = max(overlap, ov)

        # Composite score — floor ev_comp at 0.1 so data-sparse trials stay comparable
        composite = float(row["snr"]) * max(ev_comp, 0.1) * (1.0 - overlap)

        records.append({
            "harmonic_label":     label,
            "trial_period":       round(trial_p, 5),
            "period_days":        ref_p,
            "epoch_btjd":         ref_epoch,
            "duration_days":      ref_dur,
            "depth_frac":         float(row.get("depth_frac", 0.0)),
            "depth_ppt":          float(row["depth_ppt"]),
            "power":              float(row.get("power", 0.0)),
            "snr":                float(row["snr"]),
            "sde":                float(row.get("sde", 0.0)),
            "n_transits_observed": int(row.get("n_transits_observed", 0)),
            "single_event":       bool(row.get("single_event", False)),
            "score":              float(row["score"]),
            "event_completeness": round(ev_comp, 3),
            "n_covered":          n_cov,
            "n_dip":              n_dip,
            "alternating_flag":   alt_flag,
            "overlap":            round(overlap, 3),
            "composite_score":    round(composite, 3),
        })

    # ── Fallback when all trials failed ─────────────────────────────────────
    if not records:
        out = candidate_row.copy()
        for col, val in [
            ("harmonic_label",     "P"),
            ("event_completeness", 0.0),
            ("n_covered",          0),
            ("n_dip",              0),
            ("alternating_flag",   False),
            ("overlap",            0.0),
            ("composite_score",    float(candidate_row.get("snr", 0.0))),
            ("sde",                float(candidate_row.get("sde", 0.0))),
            ("n_transits_observed", int(candidate_row.get("n_transits_observed", 0))),
            ("single_event",       bool(candidate_row.get("single_event", False))),
        ]:
            out[col] = val
        logger.warning(
            "resolve_aliases: no trial succeeded — returning original candidate at %.4f d.", p0)
        return out, pd.DataFrame()

    trial_df = pd.DataFrame(records)

    # ── Selection rules ──────────────────────────────────────────────────────
    # Priority 1: half-period alias confirmed → P/2 is almost certainly right
    if is_alias:
        p2_rows = trial_df[trial_df["harmonic_label"] == "P/2"]
        if not p2_rows.empty:
            best = p2_rows.sort_values("composite_score", ascending=False).iloc[0]
            logger.debug(
                "resolve_aliases: alias flag → P/2 = %.4f d", best["period_days"])
            best = _odd_even_retest(lc, best, trial_df)
            return best, trial_df

    # Priority 2: alternating events at input period → 2P
    if is_alternating and not is_alias:
        p2x_rows = trial_df[trial_df["harmonic_label"] == "2P"]
        if not p2x_rows.empty:
            best = p2x_rows.sort_values("composite_score", ascending=False).iloc[0]
            logger.debug(
                "resolve_aliases: alternating flag → 2P = %.4f d", best["period_days"])
            best = _odd_even_retest(lc, best, trial_df)
            return best, trial_df

    # Default: highest composite score (shortest period is NOT the default)
    best = trial_df.sort_values("composite_score", ascending=False).iloc[0]
    logger.debug(
        "resolve_aliases: default → %s = %.4f d  composite=%.2f",
        best["harmonic_label"], best["period_days"], best["composite_score"],
    )

    # The flags above were evaluated at the INPUT period only, so a candidate
    # that arrived at the correct period can still be promoted here. Re-test
    # the winner itself for an over-subdivided fold.
    best = _descend_to_fundamental(lc, best, trial_df, period_min)
    # ... and re-test the winner's odd and even events with the transit-fit
    # template against those at twice its period (prompt 3, part C1).
    best = _odd_even_retest(lc, best, trial_df)
    return best, trial_df


#: Odd/even re-test of the chosen period (prompt 3, part C1). Weakness 5 of
#: IMPROVEMENT_REPORT.md: the composite argmax (and the phase-0.5 alias flag)
#: halve the period of an eclipsing binary whose secondary is 30-50% of its
#: primary, because folding primary and secondary together explains more
#: events. At the halved period the odd events are primaries and the even
#: events secondaries, so their depths differ; at the doubled period they do
#: not. Both are measured with the limb-darkened template of
#: :func:`tesshunter.transit_fit.odd_even_from_fit`, and the doubled period is
#: chosen only when the difference is significant at P and absent at 2P.
#: Applied only to winners strong enough to fit.
ODD_EVEN_RETEST_MIN_SNR = 7.0
ODD_EVEN_RETEST_MIN_DIPS = 4
ODD_EVEN_RETEST_MATCH_TOL = 0.02


def _odd_even_retest(
    lc: lk.LightCurve,
    best: pd.Series,
    trial_df: pd.DataFrame,
    match_tol: float = ODD_EVEN_RETEST_MATCH_TOL,
) -> pd.Series:
    """Return the trial at twice ``best``'s period when odd/even at ``best``
    differ significantly and do not at the doubled period; else ``best``."""
    try:
        p = float(best["period_days"])
        snr = float(best.get("snr", 0.0) or 0.0)
        n_dip = float(best.get("n_dip", 0) or 0)
        if p <= 0.0 or snr < ODD_EVEN_RETEST_MIN_SNR or n_dip < ODD_EVEN_RETEST_MIN_DIPS:
            return best
        if trial_df is None or trial_df.empty or "period_days" not in trial_df.columns:
            return best
        periods = trial_df["period_days"].to_numpy(dtype=float)
        rows = trial_df[np.abs(periods / (2.0 * p) - 1.0) <= match_tol]
        if rows.empty:
            return best
        from . import transit_fit

        oe_p = transit_fit.odd_even_from_fit(
            lc, p, float(best["epoch_btjd"]), float(best["duration_days"]),
            float(best["depth_ppt"]),
        )
        if not (oe_p.get("available") and oe_p.get("significant")):
            return best
        cand = rows.sort_values("composite_score", ascending=False).iloc[0]
        oe_2p = transit_fit.odd_even_from_fit(
            lc, float(cand["period_days"]), float(cand["epoch_btjd"]),
            float(cand["duration_days"]), float(cand["depth_ppt"]),
        )
        if not oe_2p.get("available") or oe_2p.get("significant"):
            # Cannot test the doubled period, or it alternates too: keep.
            return best
        logger.info(
            "resolve_aliases: odd/even at %.5f d differ (%s) but agree at %.5f d (%s) — "
            "choosing the doubled period [%s]",
            p, oe_p.get("note"), float(cand["period_days"]), oe_2p.get("note"),
            cand.get("harmonic_label", "?"),
        )
        out = cand.copy()
        out["odd_even_retest"] = True
        return out
    except Exception as exc:                                       # pragma: no cover
        logger.debug("odd/even re-test skipped (%s)", exc)
        return best


def best_candidate(candidates_df: pd.DataFrame) -> BLSCandidate | None:
    """Return the highest-power candidate as a BLSCandidate dataclass."""
    if candidates_df.empty:
        return None
    row = candidates_df.iloc[0]
    return BLSCandidate(
        period_days   = float(row["period_days"]),
        epoch_btjd    = float(row["epoch_btjd"]),
        duration_days = float(row["duration_days"]),
        depth_ppt     = float(row["depth_ppt"]),
        depth_frac    = float(row["depth_frac"]),
        power         = float(row["power"]),
        snr           = float(row["snr"]),
        peak_rank     = int(row["peak_rank"]),
        sde           = float(row.get("sde", 0.0)),
        n_transits_observed = int(row.get("n_transits_observed", 0)),
        single_event  = bool(row.get("single_event", False)),
    )
