"""Numerical fallback for wotan 1.10 windows whose flux scale exceeds its absolute FTOL.

The ordinary audit path still calls wotan unchanged. Rare malformed QLP fluxes can put a
two-point window's centre near 1e10, where float64 spacing already exceeds wotan's 1e-6
stopping tolerance. Its uncapped loop can then oscillate forever. This fallback keeps its
window boundaries and estimator, stopping at the larger of FTOL and floating-point precision.

Window and estimator conventions follow wotan 1.10 (Michael Hippke, MIT license; see
third_party/wotan.LICENSE). No exposure, time, flux, or quality bit is removed by this guard.
"""
from __future__ import annotations

import numpy as np


def needs_precision_guard(flux: np.ndarray) -> bool:
    from wotan.constants import FTOL
    return bool(np.max(np.abs(flux), initial=0.0) * np.finfo(float).eps >= FTOL)


def location(data: np.ndarray) -> float:
    from wotan.constants import FTOL
    from wotan.location_estimates import location_iter
    centre = float(np.median(data))
    mad = float(np.median(np.abs(data - centre)))
    # The estimator's inlier support bounds the centre. A huge rejected outlier alone
    # need not change the ordinary implementation or its rounding.
    if (abs(centre) + 5.0 * mad) * np.finfo(float).eps < FTOL:
        return float(location_iter(data, 5.0, 1))
    if mad == 0:
        return centre
    inverse_scale = 1.0 / (5.0 * mad)
    for _ in range(1000):
        distance = data - centre
        scaled = distance * inverse_scale
        inlier = np.abs(scaled) < 1.0
        weight = (1.0 - scaled[inlier] ** 2) ** 2
        total = float(weight.sum())
        if total <= 0 or not np.isfinite(total):
            raise ValueError("biweight has no finite inlier weight")
        new = centre + float(np.sum(distance[inlier] * weight) / total)
        tolerance = max(FTOL, 4.0 * np.finfo(float).eps * max(abs(centre), abs(new)))
        if not np.isfinite(new):
            raise ValueError("biweight centre is not finite")
        if abs(new - centre) <= tolerance:
            return new
        centre = new
    raise ValueError("biweight did not converge after 1000 iterations")


def flatten(time: np.ndarray, flux: np.ndarray, window_length: float,
            break_tolerance: float, edge_cutoff: float, mask=None) -> tuple[np.ndarray, np.ndarray]:
    from wotan.gaps import get_gaps_indexes
    time, flux = np.asarray(time, dtype=float), np.asarray(flux, dtype=float)
    excluded = np.zeros(len(time), dtype=bool) if mask is None else np.asarray(mask, dtype=bool)
    trend = np.full(len(time), np.nan)
    half = window_length / 2.0
    edge = min(edge_cutoff, half)
    gaps = get_gaps_indexes(time, break_tolerance)
    for start, end in zip(gaps[:-1], gaps[1:]):
        tt, ff, mm = time[start:end], flux[start:end], excluded[start:end]
        if not len(tt):
            continue
        lower_edge, upper_edge = tt.min() + edge, tt.max() - edge
        for i, centre in enumerate(tt):
            if not (lower_edge <= centre <= upper_edge):
                continue
            lo = np.searchsorted(tt, centre - half, side="left")
            # Match wotan 1.10's exclusive upper slice, including its last-index cap.
            hi = min(np.searchsorted(tt, centre + half, side="left"), len(tt) - 1)
            window = ff[lo:hi][~mm[lo:hi]]
            if len(window):
                trend[start + i] = location(window)
    trend[trend == 0] = np.nan
    return flux / trend, trend
