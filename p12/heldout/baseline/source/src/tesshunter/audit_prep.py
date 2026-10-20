"""Preprocessing of an audit light curve: mask, normalise, detrend, clip, bin.

This is ``docs/AUDIT.md`` section 1 step 2, ported out of ``scripts/audit_p5.py``
unchanged.  Everything here is pure: arrays and metadata dicts in, arrays and
dicts out.  No MAST, no file paths, no globals.

A "product" is one downloaded light curve, given as a dict with the arrays
``time``, ``flux``, ``flux_err``, ``quality`` (and, for the event rules,
``sap_flux``, ``sap_flux_err``, ``sap_bkg``) plus the metadata ``sector``,
``author``, ``cadence_s``, ``t_start``, ``t_end``.

The prompt-7 option is ``transit_mask``: the biweight is fitted with the
in-transit cadences removed from the trend, so the detrend cannot absorb part
of the transit.  It is off unless a mask is supplied, and the legacy call path
never supplies one.
"""
from __future__ import annotations

import math

import numpy as np

from .audit_rules import (
    BIN_MIN_POINTS_FOR_SCATTER,
    DEEP_CLIP_DEPTH_MULTIPLE,
    DEEP_CLIP_MAD_MULTIPLE,
    ISOLATED_DIP_SIGMA,
    ISOLATED_NEIGHBOUR_SIGMA,
    MASK_DURATIONS_EITHER_SIDE,
    MIN_POINTS_PER_PRODUCT,
    Q_DEFAULT,
    QLP_FLAG_SECTOR_SPLIT,
    QLP_LOW_PRECISION_S1_55,
    QLP_LOW_PRECISION_S56,
    UPWARD_CLIP_SIGMA,
    WOTAN_BREAK_TOLERANCE,
    WOTAN_EDGE_CUTOFF,
    WOTAN_METHOD,
    WOTAN_WINDOW_MAX_DAYS,
    WOTAN_WINDOW_MIN_DAYS,
    WOTAN_WINDOW_T14_MULTIPLE,
)

__all__ = [
    "product_bitmask", "expected_t14_hours", "detrend_window_days",
    "transit_mask", "clean_and_detrend", "bin_lc", "clip_binned", "prepare_series",
]


def product_bitmask(product: dict, base: int = Q_DEFAULT) -> int:
    """Default TESS bitmask, plus QLP's own low-precision flag.

    QLP sets the low-precision bit at 2^12 in sectors 1-55 and at 2^30 from
    sector 56; the survey's ``ffi.py`` masks the same bit.
    """
    if product.get("author") == "QLP":
        split = QLP_LOW_PRECISION_S56 if int(product["sector"]) >= QLP_FLAG_SECTOR_SPLIT else QLP_LOW_PRECISION_S1_55
        return base | split
    return base


def expected_t14_hours(period: float, rstar: float, mstar: float,
                       k: float = 0.05, b: float = 0.0) -> float:
    """Circular-orbit total duration for a central transit (hours)."""
    G = 6.674e-8
    a_cm = (G * mstar * 1.989e33 * (period * 86400.0) ** 2 / (4 * math.pi ** 2)) ** (1 / 3)
    a_rs = a_cm / (rstar * 6.957e10)
    x = max(0.0, (1 + k) ** 2 - b ** 2)
    return period * 24.0 / math.pi * math.asin(min(1.0, math.sqrt(x) / a_rs))


def detrend_window_days(t14_hours: float) -> float:
    """The wotan window: 3 x T14, floored at 0.75 d and capped at 1.5 d."""
    return float(min(WOTAN_WINDOW_MAX_DAYS,
                     max(WOTAN_WINDOW_MIN_DAYS, WOTAN_WINDOW_T14_MULTIPLE * t14_hours / 24.0)))


def transit_mask(t: np.ndarray, period: float, t0: float, duration: float,
                 n_durations: float = MASK_DURATIONS_EITHER_SIDE) -> np.ndarray:
    """True where a cadence lies within ``n_durations`` of a predicted mid-time.

    Prompt-7 option 3.  The mask is phase-based, so it covers every predicted
    epoch over the whole baseline, observed or not.
    """
    if not (period > 0 and duration > 0):
        return np.zeros(np.shape(t), dtype=bool)
    dt = np.abs(((np.asarray(t, dtype=float) - t0 + 0.5 * period) % period) - 0.5 * period)
    return dt < n_durations * duration


def clean_and_detrend(products: list[dict], window_days: float, bitmask: int = Q_DEFAULT,
                      flux_key: str = "flux", err_key: str = "flux_err",
                      mask_fn=None) -> dict:
    """Quality-mask, normalise per product, wotan biweight per product, concatenate.

    ``mask_fn`` (prompt-7 option 3) is called as ``mask_fn(time)`` and must
    return a boolean array marking the cadences to keep OUT of the trend fit;
    wotan evaluates the trend at every cadence anyway, so the trend is
    interpolated across the masked stretches.  ``None`` is the legacy path.
    """
    from wotan import flatten
    from . import biweight_precision
    T, F, E, S, TR = [], [], [], [], []
    per_product = []
    for p in products:
        t, f, e, q = p["time"], p[flux_key], p[err_key], p["quality"]
        ok = np.isfinite(t) & np.isfinite(f) & ((q & product_bitmask(p, bitmask)) == 0) & (f > 0)
        t, f, e = t[ok], f[ok], e[ok]
        if len(t) < MIN_POINTS_PER_PRODUCT:
            per_product.append({"sector": p["sector"], "author": p["author"], "n_used": int(len(t)), "dropped": True})
            continue
        med = np.nanmedian(f)
        f = f / med
        e = e / med if np.all(np.isfinite(e)) else np.full_like(f, np.nan)
        if not np.all(np.isfinite(e)):
            # QLP >= s56 ships NaN errors; use the robust point-to-point scatter
            e = np.full_like(f, 1.4826 * np.nanmedian(np.abs(np.diff(f))) / math.sqrt(2))
        n_masked_transit = 0
        precision_guard = biweight_precision.needs_precision_guard(f)
        if precision_guard:
            m = None if mask_fn is None else np.asarray(mask_fn(t), dtype=bool)
            n_masked_transit = int(m.sum()) if m is not None else 0
            flat, trend = biweight_precision.flatten(t, f, window_days, WOTAN_BREAK_TOLERANCE,
                                                     WOTAN_EDGE_CUTOFF, mask=m)
        elif mask_fn is None:
            flat, trend = flatten(t, f, method=WOTAN_METHOD, window_length=window_days,
                                  break_tolerance=WOTAN_BREAK_TOLERANCE,
                                  edge_cutoff=WOTAN_EDGE_CUTOFF, return_trend=True)
        else:
            m = np.asarray(mask_fn(t), dtype=bool)
            n_masked_transit = int(m.sum())
            flat, trend = flatten(t, f, method=WOTAN_METHOD, window_length=window_days,
                                  break_tolerance=WOTAN_BREAK_TOLERANCE,
                                  edge_cutoff=WOTAN_EDGE_CUTOFF, return_trend=True, mask=m)
        ok2 = np.isfinite(flat)
        # upward outliers only (flares, cosmic rays); dips are what we are looking for
        resid = flat[ok2] - 1.0
        mad = 1.4826 * np.nanmedian(np.abs(resid - np.nanmedian(resid)))
        up = np.zeros_like(flat, dtype=bool)
        up[ok2] = resid > UPWARD_CLIP_SIGMA * mad
        ok2 &= ~up
        # ISOLATED single-cadence dips: a point more than 6 sigma low whose two neighbours are both within
        # 2 sigma of the baseline. No transit at P >= 0.5 d around these stars lasts one cadence (>= 40 min
        # for the smallest star at the shortest period), so these are instrumental and would otherwise hand
        # TLS single-bin "transits" of arbitrary depth.
        idx = np.where(ok2)[0]
        r = flat[idx] - 1.0
        iso = np.zeros(len(idx), dtype=bool)
        if len(idx) > 3:
            low = r[1:-1] < -ISOLATED_DIP_SIGMA * mad
            nb_ok = (r[:-2] > -ISOLATED_NEIGHBOUR_SIGMA * mad) & (r[2:] > -ISOLATED_NEIGHBOUR_SIGMA * mad)
            iso[1:-1] = low & nb_ok
        ok2[idx[iso]] = False
        T.append(t[ok2]); F.append(flat[ok2]); E.append(e[ok2])
        S.append(np.full(ok2.sum(), p["sector"])); TR.append(trend[ok2])
        rec = {"sector": p["sector"], "author": p["author"], "n_used": int(ok2.sum()),
               "n_masked_quality": int((~ok).sum()), "n_clipped_up": int(up.sum()),
               "n_isolated_clipped": int(iso.sum()),
               "scatter_ppt": round(1000 * mad, 3), "dropped": False}
        if mask_fn is not None:
            rec["n_masked_from_trend"] = n_masked_transit
        if precision_guard:
            rec["biweight_precision_guard"] = "absolute FTOL limited by float64 spacing; same window and estimator"
        per_product.append(rec)
    t = np.concatenate(T); f = np.concatenate(F); e = np.concatenate(E)
    s = np.concatenate(S); tr = np.concatenate(TR)
    o = np.argsort(t)
    return {"time": t[o], "flux": f[o], "flux_err": e[o], "sector": s[o], "trend": tr[o],
            "per_product": per_product}


def bin_lc(t: np.ndarray, f: np.ndarray, e: np.ndarray,
           minutes: float | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fixed-width time bins; the bin error is the in-bin scatter where there
    are at least three points, else the propagated per-cadence error."""
    if minutes is None:
        return t, f, e
    w = minutes / 1440.0
    idx = np.floor((t - t[0]) / w).astype(int)
    uniq, inv = np.unique(idx, return_inverse=True)
    n = np.bincount(inv)
    tb = np.bincount(inv, weights=t) / n
    fb = np.bincount(inv, weights=f) / n
    f2 = np.bincount(inv, weights=f * f) / n
    var = np.maximum(f2 - fb * fb, 0.0)
    eb_prop = np.sqrt(np.bincount(inv, weights=e * e)) / n
    eb = np.where(n >= BIN_MIN_POINTS_FOR_SCATTER, np.sqrt(var / np.maximum(n - 1, 1)), eb_prop)
    eb = np.where(eb > 0, eb, eb_prop)
    keep = n >= 1
    return tb[keep], fb[keep], eb[keep]


def clip_binned(tb: np.ndarray, fb: np.ndarray, eb: np.ndarray,
                ref_depth: float) -> dict:
    """The two clips applied to the binned series before any search.

    1. isolated single-bin dips (the same rule as on the cadences: one 30-min
       bin cannot be a transit at these periods);
    2. bins deeper than 3 x the candidate depth or 10 MAD, whichever is
       larger, so a binary host's eclipses or multi-cadence garbage cannot
       dominate the spectrum the candidate is being tested in.
    """
    rb = fb - 1.0
    madb = 1.4826 * np.nanmedian(np.abs(rb - np.nanmedian(rb)))
    isob = np.zeros(len(fb), dtype=bool)
    if len(fb) > 3:
        isob[1:-1] = ((rb[1:-1] < -ISOLATED_DIP_SIGMA * madb)
                      & (rb[:-2] > -ISOLATED_NEIGHBOUR_SIGMA * madb)
                      & (rb[2:] > -ISOLATED_NEIGHBOUR_SIGMA * madb))
    n_isolated_bins = int(isob.sum())
    tb, fb, eb = tb[~isob], fb[~isob], eb[~isob]
    deep_thr = max(DEEP_CLIP_DEPTH_MULTIPLE * ref_depth, DEEP_CLIP_MAD_MULTIPLE * madb)
    deep = (fb - 1.0) < -deep_thr
    n_deep_clipped = int(deep.sum())
    tb, fb, eb = tb[~deep], fb[~deep], eb[~deep]
    return {"time": tb, "flux": fb, "flux_err": eb, "mad": float(madb),
            "n_isolated_bins_clipped": n_isolated_bins,
            "deep_clip_threshold_ppt": round(1000 * deep_thr, 2),
            "n_deep_clipped": n_deep_clipped}


def prepare_series(products: list[dict], window_days: float, bin_minutes: float | None,
                   ref_depth: float, mask_ranges: list | None = None,
                   mask_fn=None) -> dict:
    """Detrend, mask, bin and clip one candidate's whole baseline.

    Returns the unbinned detrended series, the binned search series, and every
    counter the audit records.  ``mask_ranges`` are BTJD ranges removed after
    the detrend (documented systematics); ``mask_fn`` is the prompt-7
    transit-masked detrend (option 3).
    """
    det = clean_and_detrend(products, window_days, mask_fn=mask_fn)
    n_masked = 0
    if mask_ranges:
        keep = np.ones(len(det["time"]), dtype=bool)
        for lo, hi in mask_ranges:
            keep &= ~((det["time"] >= lo) & (det["time"] <= hi))
        n_masked = int((~keep).sum())
        for k_ in ("time", "flux", "flux_err", "sector", "trend"):
            det[k_] = det[k_][keep]
    tb, fb, eb = bin_lc(det["time"], det["flux"], det["flux_err"], bin_minutes)
    clipped = clip_binned(tb, fb, eb, ref_depth)
    return {
        "unbinned": det,
        "binned": {"time": clipped["time"], "flux": clipped["flux"], "flux_err": clipped["flux_err"]},
        "counters": {
            "n_unbinned": int(len(det["time"])), "n_binned": int(len(clipped["time"])),
            "n_unbinned_masked": n_masked,
            "n_isolated_clipped": int(sum(pp.get("n_isolated_clipped", 0) for pp in det["per_product"])),
            "n_isolated_bins_clipped": clipped["n_isolated_bins_clipped"],
            "deep_clip_threshold_ppt": clipped["deep_clip_threshold_ppt"],
            "n_deep_clipped": clipped["n_deep_clipped"],
            "n_masked_from_trend": int(sum(pp.get("n_masked_from_trend", 0) for pp in det["per_product"])),
        },
        "per_product": det["per_product"],
    }
