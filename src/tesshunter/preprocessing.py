"""Light curve cleaning, normalisation, and detrending."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import lightkurve as lk
import numpy as np
from lightkurve.utils import KeplerQualityFlags, TessQualityFlags

from .config import SIGMA_CLIP_SIGMA

logger = logging.getLogger(__name__)

# ── Detrending window defaults ────────────────────────────────────────────────

#: Default Savitzky-Golay window expressed in DAYS (used when window_days=None).
DEFAULT_WINDOW_DAYS = 1.0

#: Gap threshold, in units of the median cadence, that splits a light curve
#: into contiguous segments. Matches lightkurve's flatten(break_tolerance=5).
SEGMENT_BREAK_TOLERANCE = 5

#: Smallest legal Savitzky-Golay window (odd, and > polyorder=2).
MIN_WINDOW_CADENCES = 5

#: Parameters for which a deprecation warning has already been logged.
_deprecation_warned: set[str] = set()


def _warn_deprecated_once(param: str, message: str) -> None:
    """Log a deprecation warning for ``param`` once per process."""
    if param not in _deprecation_warned:
        _deprecation_warned.add(param)
        logger.warning(message)


@dataclass
class PreprocessingRecord:
    """Metadata describing what was applied to a light curve."""

    original_cadences: int = 0
    after_nan_removal: int = 0
    after_quality_mask: int = 0
    after_sigma_clip: int = 0
    normalised: bool = False
    flattened: bool = False
    flatten_window_length: Optional[float] = None
    sigma_clip_sigma: float = SIGMA_CLIP_SIGMA
    effective_window_days: Optional[float] = None
    effective_window_cadences: Optional[int] = None
    median_branch_segments: int = 0
    flatten_error: Optional[str] = None
    quality_masked_cadences: int = 0
    notes: list[str] = field(default_factory=list)


def remove_nans(lc: lk.LightCurve) -> lk.LightCurve:
    """Drop cadences where flux or time is NaN."""
    mask = np.isfinite(lc.flux.value) & np.isfinite(lc.time.value)
    return lc[mask]


def apply_quality_mask(lc: lk.LightCurve, bitmask: str = "default") -> lk.LightCurve:
    """Remove cadences flagged in the light curve's QUALITY column.

    Builds a boolean mask with the mission-appropriate Lightkurve quality-flag
    class (``TessQualityFlags`` for TESS or unknown missions,
    ``KeplerQualityFlags`` for Kepler/K2) via ``create_quality_mask``, which
    returns True for GOOD cadences; flagged cadences are dropped. Light curves
    without a quality column (e.g. synthetic data, some HLSPs) pass through
    unchanged.

    Parameters
    ----------
    lc      : Light curve, optionally carrying a 'quality' column.
    bitmask : 'none', 'default', 'hard', or 'hardest' (Lightkurve semantics).
              'none' skips masking entirely.

    Returns
    -------
    lk.LightCurve with flagged cadences removed.
    """
    if bitmask == "none":
        return lc

    quality_col = next(
        (name for name in getattr(lc, "colnames", []) if name.lower() == "quality"),
        None,
    )
    if quality_col is None:
        logger.info("apply_quality_mask: no quality column present — nothing to mask")
        return lc

    quality = np.asarray(getattr(lc[quality_col], "value", lc[quality_col]))
    if np.ma.isMaskedArray(quality):
        quality = quality.filled(0)
    if not np.issubdtype(quality.dtype, np.integer):
        quality = np.nan_to_num(quality, nan=0.0).astype(np.int64)

    mission = str(lc.meta.get("MISSION") or lc.meta.get("TELESCOP") or "").upper()
    if "KEPLER" in mission or "K2" in mission:
        flags_cls = KeplerQualityFlags
    else:
        flags_cls = TessQualityFlags  # TESS, or unknown mission (TESS assumed)

    try:
        good = flags_cls.create_quality_mask(quality_array=quality, bitmask=bitmask)
    except Exception as exc:
        logger.warning("Quality mask application failed: %s", exc)
        return lc

    n_removed = int(np.sum(~good))
    if n_removed > 0:
        logger.info(
            "Quality mask (%s, bitmask=%s) removed %d/%d flagged cadences",
            flags_cls.__name__, bitmask, n_removed, len(lc),
        )
    return lc[good]


def normalise(lc: lk.LightCurve) -> lk.LightCurve:
    """Normalise flux to a median of 1.0."""
    return lc.normalize()


def sigma_clip_lightcurve(
    lc: lk.LightCurve,
    sigma: float = SIGMA_CLIP_SIGMA,
) -> lk.LightCurve:
    """Remove upward outlier cadences (cosmic rays, saturation) via sigma clipping.

    Clips only the UPPER tail so that transit dips are never removed — transits
    are negative excursions and must be preserved for BLS.

    Uses a pure-numpy iterative implementation to avoid astropy masked-array
    compatibility issues on Python 3.14 / numpy 2.x.
    """
    flux = lc.flux.value
    keep = np.isfinite(flux)

    for _ in range(5):
        f = flux[keep]
        if len(f) < 10:
            break
        med = np.nanmedian(f)
        std = np.nanstd(f)
        if std < 1e-15:
            break
        upper = med + sigma * std
        new_keep = keep & (flux <= upper)
        if new_keep.sum() == keep.sum():
            break
        keep = new_keep

    mask = keep
    n_removed = int(np.sum(~mask))
    if n_removed > 0:
        logger.debug("Sigma clip removed %d cadences (sigma=%.1f)", n_removed, sigma)
    return lc[mask]


def bin_lightcurve(
    lc: lk.LightCurve,
    bin_minutes: Optional[float] = 10.0,
) -> lk.LightCurve:
    """Bin the light curve into time bins of width bin_minutes.

    ``bin_minutes`` of ``None`` or ``<= 0`` returns the light curve unchanged
    (the native-cadence search of prompt 8).

    Reduces cadence count dramatically (e.g. 2-min → 10-min = 5× fewer points),
    making BLS searches on large multi-sector datasets tractable.

    The binned flux is the inverse-variance weighted mean per bin.
    """
    from astropy import units as u
    from astropy.time import Time

    time = lc.time.value
    flux = lc.flux.value
    flux_err = lc.flux_err.value if lc.flux_err is not None else np.full_like(flux, 1e-4)

    if len(lc) == 0:
        logger.warning("bin_lightcurve: received empty light curve — returning as-is")
        return lc
    if bin_minutes is None or float(bin_minutes) <= 0.0:
        # Native-cadence search (prompt 8): no re-gridding at all, so the
        # cadences the search sees are exactly the cadences the vetting sees.
        logger.info("bin_lightcurve: bin_minutes=%r, returning the %d cadences unbinned", bin_minutes, len(lc))
        return lc

    bin_days = bin_minutes / 1440.0
    t_min, t_max = time.min(), time.max()
    edges = np.arange(t_min, t_max + bin_days, bin_days)
    n_bins = len(edges) - 1

    # Vectorised binning. Each cadence is placed in the bin with
    # edges[i] <= t < edges[i + 1] (searchsorted side="right"), which is the
    # same half-open interval the original per-bin mask loop used; cadences
    # at or beyond the last edge fall in no bin, exactly as before. Weighted
    # sums are accumulated per bin in data order, so for bins holding fewer
    # than eight cadences the result is bit-identical to the loop's np.sum
    # (which is a plain sequential sum below that size); larger bins agree
    # to the last bit or two of the mantissa.
    time = np.asarray(time, dtype=float)
    flux = np.asarray(flux, dtype=float)
    flux_err = np.asarray(flux_err, dtype=float)
    if n_bins >= 1:
        idx = np.searchsorted(edges, time, side="right") - 1
        use = (idx >= 0) & (idx < n_bins)
        use &= np.isfinite(flux) & np.isfinite(flux_err) & (flux_err > 0)
        idx_u = idx[use]
        w = 1.0 / flux_err[use] ** 2
        sum_w = np.bincount(idx_u, weights=w, minlength=n_bins)
        sum_wf = np.bincount(idx_u, weights=w * flux[use], minlength=n_bins)
        count = np.bincount(idx_u, minlength=n_bins)
        keep = count > 0
        bf = sum_wf[keep] / sum_w[keep]
        be = 1.0 / np.sqrt(sum_w[keep])
        bt = (0.5 * (edges[:-1] + edges[1:]))[keep]
    else:
        bt = bf = be = np.zeros(0)

    if len(bt) < 10:
        logger.warning("Binning produced too few points; returning unbinned LC")
        return lc

    time_obj = lc.time.__class__(np.array(bt), format=lc.time.format, scale=lc.time.scale)
    binned = lk.LightCurve(
        time=time_obj,
        flux=np.array(bf) * u.dimensionless_unscaled,
        flux_err=np.array(be) * u.dimensionless_unscaled,
    )
    binned.meta.update(lc.meta)
    logger.info(
        "Binned %d → %d cadences (%.0f-min bins)",
        len(lc), len(binned), bin_minutes,
    )
    return binned


def mask_transits(
    lc: lk.LightCurve,
    period: float,
    epoch: float,
    duration: float,
    width_factor: float = 2.5,
) -> lk.LightCurve:
    """Remove cadences that fall inside predicted transit windows.

    Computes the phase of each cadence relative to the nearest transit centre
    and discards any that land within ``width_factor × duration`` of phase zero.
    The default factor of 2.5 masks ±2.5 transit durations around each centre,
    giving generous coverage of ingress and egress while keeping the bulk of the
    out-of-transit baseline.

    Parameters
    ----------
    lc           : Light curve to mask.
    period       : Orbital period of the signal to remove (days).
    epoch        : Transit mid-point epoch (same time system as lc.time, e.g. BTJD).
    duration     : Transit duration (days).
    width_factor : Mask half-width in units of ``duration``.
                   Default 2.5 ⇒ masked window spans ±2.5 × duration around
                   each transit centre.

    Returns
    -------
    lk.LightCurve with in-transit cadences removed.
    """
    time = np.asarray(lc.time.value, dtype=float)

    # Phase relative to transit centre, in days, folded to (-period/2, +period/2]
    phase_days = ((time - epoch + 0.5 * period) % period) - 0.5 * period

    # Keep cadences that lie outside the masked window
    keep = np.abs(phase_days) > width_factor * duration

    n_removed = int(np.sum(~keep))
    logger.debug(
        "mask_transits P=%.5f d: removed %d/%d cadences (%.1f%%)",
        period, n_removed, len(time), 100.0 * n_removed / max(len(time), 1),
    )
    return lc[keep]


# ── Flatten window computation ────────────────────────────────────────────────

def _find_segments(
    time: np.ndarray,
    break_tolerance: int = SEGMENT_BREAK_TOLERANCE,
) -> list[tuple[int, int]]:
    """Split ``time`` into contiguous ``[start, stop)`` index runs.

    A new segment starts wherever the gap to the previous cadence exceeds
    ``break_tolerance`` times the median cadence, matching the segmentation
    done inside Lightkurve's flatten().
    """
    n = len(time)
    if n < 2:
        return [(0, n)]
    dt = np.diff(time)
    med = float(np.nanmedian(dt))
    if not np.isfinite(med) or med <= 0:
        return [(0, n)]
    cut = np.where(dt > break_tolerance * med)[0] + 1
    starts = np.concatenate(([0], cut))
    stops = np.concatenate((cut, [n]))
    return [(int(s), int(e)) for s, e in zip(starts, stops)]


def _count_median_branch_segments(
    time_used: np.ndarray,
    window_cadences: int,
    break_tolerance: int = SEGMENT_BREAK_TOLERANCE,
) -> tuple[int, int]:
    """Count segments Lightkurve's flatten() would median-subtract, not detrend.

    Mirrors the lightkurve 2.6.0 condition
    ``window_length > (h - l) or (h - l) < break_tolerance`` applied to the
    cadences actually used in the trend fit.

    Returns
    -------
    (n_median_branch_segments, n_segments_total)
    """
    segments = _find_segments(time_used, break_tolerance)
    n_median = sum(
        1 for start, stop in segments
        if window_cadences > (stop - start) or (stop - start) < break_tolerance
    )
    return n_median, len(segments)


def compute_flatten_window(
    time: np.ndarray,
    window_days: Optional[float] = None,
    max_transit_duration_days: Optional[float] = None,
    break_tolerance: int = SEGMENT_BREAK_TOLERANCE,
) -> tuple[int, float, float]:
    """Convert a detrending window from days into an odd cadence count.

    Parameters
    ----------
    time                      : Cadence mid-times in days.
    window_days               : Requested window in days.
                                None → ``DEFAULT_WINDOW_DAYS`` (1.0 day).
    max_transit_duration_days : Longest transit duration that will be searched.
                                When given, the window is raised to at least
                                3x this value (if the segment bound allows) so
                                transits are not absorbed into the trend.
    break_tolerance           : Gap threshold in median-cadence units used to
                                define contiguous segments (Lightkurve uses 5).

    Returns
    -------
    (window_cadences, effective_window_days, median_cadence_days) where
    ``effective_window_days = window_cadences * median_cadence_days``.

    Notes
    -----
    The effective window is capped at half the time span of the shortest
    contiguous segment, so Lightkurve's flatten() never silently substitutes
    a per-segment median for a segment that could have been detrended.
    Two segment classes are EXCLUDED from this bound so that data slivers
    cannot drag the window down for the whole light curve (real quality-masked
    SPOC data contains many 10-16 min slivers that would otherwise collapse a
    1-day window to ``MIN_WINDOW_CADENCES`` everywhere):

    * segments with fewer than ``break_tolerance`` cadences — Lightkurve
      median-subtracts those regardless of the window choice;
    * segments spanning less than ``6 × max_transit_duration_days`` (when
      given) — half their span could not fit a transit-safe window (at least
      3 × the longest searched duration), so a window bounded by them would
      track and remove the transits it is supposed to preserve; those
      segments are better median-divided (:func:`flatten` handles them per
      segment).

    Excluded segments are still reported via ``median_branch_segments``.
    The result is forced to an odd integer >= ``MIN_WINDOW_CADENCES`` as
    required by the Savitzky-Golay filter.  :func:`flatten` chooses its
    windows PER SEGMENT; this function returns the single-window equivalent
    for callers that need one number.
    """
    time = np.asarray(time, dtype=float)
    requested = DEFAULT_WINDOW_DAYS if window_days is None else float(window_days)

    dt_med = float(np.nanmedian(np.diff(time))) if len(time) > 1 else float("nan")
    if not np.isfinite(dt_med) or dt_med <= 0:
        dt_med = 2.0 / 1440.0  # fallback: 2 minutes
        logger.warning(
            "compute_flatten_window: could not measure cadence; assuming 2 min"
        )

    # Segment bound: half the span of the shortest contiguous segment that is
    # long enough to be meaningfully detrended (see Notes for the exclusions).
    # A segment may only constrain the bound if HALF its span still fits a
    # transit-safe window (>= 3x the longest searched duration); otherwise a
    # single ~0.5 d fragment forces a transit-eating window on the whole LC
    # even when nearly all data sits in multi-day segments.
    min_span = (
        6.0 * float(max_transit_duration_days)
        if max_transit_duration_days is not None else 0.0
    )
    seg_bound = float("inf")
    for start, stop in _find_segments(time, break_tolerance):
        if stop - start < break_tolerance:
            continue  # median-branched by lightkurve regardless of window
        span = time[stop - 1] - time[start]
        if span < min_span:
            continue  # too short for a transit-safe window; median-divided
        seg_bound = min(seg_bound, 0.5 * span)

    effective = min(requested, seg_bound)
    if max_transit_duration_days is not None:
        effective = max(
            effective, min(3.0 * float(max_transit_duration_days), seg_bound)
        )
    if not np.isfinite(effective) or effective <= 0:
        effective = requested

    window_cadences = max(int(round(effective / dt_med)), MIN_WINDOW_CADENCES)
    if window_cadences % 2 == 0:
        window_cadences += 1  # savgol requires an odd window
    return window_cadences, window_cadences * dt_med, dt_med


def flatten(
    lc: lk.LightCurve,
    window_length: Optional[float] = None,   # DEPRECATED — ignored
    method: str = "savgol",   # kept as parameter for API compat; only savgol used
    window_days: Optional[float] = None,
    transit_mask: Optional[np.ndarray] = None,
    max_transit_duration_days: Optional[float] = None,
) -> tuple[lk.LightCurve, lk.LightCurve]:
    """Detrend using a Savitzky-Golay filter via Lightkurve's flatten().

    The window is expressed in DAYS via ``window_days`` and converted to
    cadences using the measured median cadence; see compute_flatten_window()
    for the per-segment clamping rules.

    Parameters
    ----------
    lc            : Light curve to detrend.
    window_length : DEPRECATED. The old "fraction of a 27-day sector" window
                    is ignored; a deprecation warning is logged once. Use
                    ``window_days`` instead.
    method        : Unused; kept for API compatibility (savgol only).
    window_days   : Savitzky-Golay window in days. None → 1.0-day default.
    transit_mask  : Boolean array with the same length as ``lc``. True marks
                    IN-TRANSIT cadences that are EXCLUDED from the trend fit.
                    Passed directly to Lightkurve's ``flatten(mask=...)``: in
                    lightkurve 2.6.0, flux values where mask is True are not
                    used to fit the trend (the trend is interpolated across
                    them), which is exactly the polarity used here.
    max_transit_duration_days : Longest searched transit duration (days); the
                    window is raised to at least 3x this when the segment
                    bound allows, so transits survive detrending.

    Returns
    -------
    (flat, trend). On failure the RAW (undetrended) light curve is returned
    for both elements and the failure is indicated in the returned meta:
    ``flat.meta['FLATTEN_FAILED']`` is True and
    ``flat.meta['FLATTEN_ERROR']`` holds the exception text. On success
    FLATTEN_FAILED is False. In both cases the meta records
    FLATTEN_WINDOW_DAYS, FLATTEN_WINDOW_CADENCES, FLATTEN_N_SEGMENTS, and
    FLATTEN_MEDIAN_BRANCH_SEGMENTS.
    """
    if window_length is not None:
        _warn_deprecated_once(
            "flatten.window_length",
            "flatten(window_length=...) is deprecated and ignored; "
            "use window_days (a window in days) instead.",
        )

    time = np.asarray(lc.time.value, dtype=float)
    flux = np.asarray(lc.flux.value, dtype=float)

    if transit_mask is not None:
        transit_mask = np.asarray(transit_mask, dtype=bool)
        if transit_mask.shape != time.shape:
            raise ValueError(
                f"transit_mask length {transit_mask.size} does not match "
                f"light curve length {time.size}"
            )

    window_cadences, effective_window_days, dt_med = compute_flatten_window(
        time,
        window_days=window_days,
        max_transit_duration_days=max_transit_duration_days,
    )

    # Mirror the fit mask lightkurve builds on its first iteration so we can
    # count segments that would silently fall back to a per-segment median.
    with np.errstate(invalid="ignore"):
        used = np.isfinite(flux)
        used &= np.nan_to_num(np.abs(flux - np.nanmedian(flux))) <= 3.0 * np.nanstd(flux)
    if transit_mask is not None:
        used &= ~transit_mask
    median_branch, n_segments = _count_median_branch_segments(
        time[used], window_cadences
    )
    if median_branch > 0:
        logger.warning(
            "Flatten: %d/%d segment(s) shorter than the %d-cadence window will "
            "be median-subtracted, not detrended.",
            median_branch, n_segments, window_cadences,
        )

    diagnostics = {
        "FLATTEN_WINDOW_DAYS": effective_window_days,
        "FLATTEN_WINDOW_CADENCES": window_cadences,
        "FLATTEN_N_SEGMENTS": n_segments,
        "FLATTEN_MEDIAN_BRANCH_SEGMENTS": median_branch,
    }
    logger.debug(
        "Flattening: window=%.3f days (%d cadences, median cadence %.5f d)",
        effective_window_days, window_cadences, dt_med,
    )

    try:
        flat, trend = lc.flatten(
            window_length=window_cadences,
            polyorder=2,
            return_trend=True,
            mask=transit_mask,
        )
    except Exception as exc:
        logger.warning(
            "Flatten FAILED (%s); returning raw, undetrended light curve.", exc
        )
        failed = lc.copy()
        failed.meta["FLATTEN_FAILED"] = True
        failed.meta["FLATTEN_ERROR"] = f"{type(exc).__name__}: {exc}"
        failed.meta.update(diagnostics)
        return failed, failed

    flat.meta["FLATTEN_FAILED"] = False
    flat.meta.update(diagnostics)
    return flat, trend


def preprocess(
    lc: lk.LightCurve,
    sigma: float = SIGMA_CLIP_SIGMA,
    do_flatten: bool = True,
    flatten_window: Optional[float] = None,   # DEPRECATED — ignored
    flatten_method: str = "savgol",
    window_days: Optional[float] = None,
    transit_mask: Optional[np.ndarray] = None,
    max_transit_duration_days: Optional[float] = None,
) -> tuple[lk.LightCurve, PreprocessingRecord]:
    """Run the full preprocessing chain and return a cleaned light curve.

    Steps applied in order:
      1. Quality-flag masking (drops cadences flagged in the QUALITY column)
      2. Remove NaNs
      3. Sigma-clip outliers
      4. Normalise to median=1
      5. (optional) Flatten stellar variability

    Parameters
    ----------
    lc             : Light curve to clean.
    sigma          : Upper-tail sigma-clip threshold.
    do_flatten     : Whether to detrend with flatten().
    flatten_window : DEPRECATED. The old "fraction of baseline" value is
                     ignored (its 27-day-constant math was broken); a
                     deprecation warning is logged once. Use ``window_days``.
    flatten_method : Forwarded to flatten() (savgol only).
    window_days    : Detrending window in days, forwarded to flatten().
                     None → 1.0-day default.
    transit_mask   : Boolean array aligned with the INPUT ``lc``; True marks
                     in-transit cadences to exclude from the trend fit. It is
                     re-aligned automatically after cleaning steps drop
                     cadences, then forwarded to flatten().
    max_transit_duration_days : Forwarded to flatten(); raises the window to
                     at least 3x the longest searched transit duration.

    Returns
    -------
    (cleaned_lc, record) — record documents every step for the report.
    """
    rec = PreprocessingRecord()
    rec.original_cadences = len(lc)
    rec.sigma_clip_sigma = sigma

    if flatten_window is not None:
        _warn_deprecated_once(
            "preprocess.flatten_window",
            "preprocess(flatten_window=...) is deprecated and ignored; "
            "use window_days (a window in days) instead.",
        )
        rec.notes.append(
            "flatten_window argument is deprecated and was ignored (use window_days)"
        )

    # Keep the input timestamps so a caller-supplied transit mask can be
    # re-aligned after cleaning steps drop cadences.
    tm_input: Optional[np.ndarray] = None
    orig_time: Optional[np.ndarray] = None
    if transit_mask is not None:
        tm_input = np.asarray(transit_mask, dtype=bool)
        if len(tm_input) != len(lc):
            logger.warning(
                "preprocess: transit_mask length %d != light curve length %d "
                "— mask ignored", len(tm_input), len(lc),
            )
            tm_input = None
        else:
            orig_time = np.asarray(lc.time.value, dtype=float).copy()

    had_quality = any(
        name.lower() == "quality" for name in getattr(lc, "colnames", [])
    )
    n_before_quality = len(lc)
    lc = apply_quality_mask(lc)
    rec.after_quality_mask = len(lc)
    rec.quality_masked_cadences = n_before_quality - len(lc)
    if not had_quality:
        rec.notes.append("No quality column present; quality masking skipped")
    elif rec.quality_masked_cadences > 0:
        rec.notes.append(
            f"Quality mask removed {rec.quality_masked_cadences} flagged cadences"
        )

    lc = remove_nans(lc)
    rec.after_nan_removal = len(lc)

    lc = sigma_clip_lightcurve(lc, sigma=sigma)
    rec.after_sigma_clip = len(lc)

    lc = normalise(lc)
    rec.normalised = True

    if do_flatten:
        tm_current: Optional[np.ndarray] = None
        if tm_input is not None:
            survived = np.isin(orig_time, np.asarray(lc.time.value, dtype=float))
            tm_current = tm_input[survived]
            if len(tm_current) != len(lc):
                logger.warning(
                    "preprocess: could not re-align transit_mask after cleaning "
                    "— mask ignored"
                )
                tm_current = None

        lc, _ = flatten(
            lc,
            method=flatten_method,
            window_days=window_days,
            transit_mask=tm_current,
            max_transit_duration_days=max_transit_duration_days,
        )
        failed = bool(lc.meta.get("FLATTEN_FAILED", False))
        rec.flattened = not failed
        rec.flatten_error = lc.meta.get("FLATTEN_ERROR") if failed else None
        rec.effective_window_days = lc.meta.get("FLATTEN_WINDOW_DAYS")
        rec.effective_window_cadences = lc.meta.get("FLATTEN_WINDOW_CADENCES")
        rec.median_branch_segments = int(
            lc.meta.get("FLATTEN_MEDIAN_BRANCH_SEGMENTS", 0)
        )
        rec.flatten_window_length = rec.effective_window_days  # legacy field: now days
        if failed:
            rec.notes.append(
                f"WARNING: flatten FAILED ({rec.flatten_error}); "
                "light curve is NOT detrended"
            )
        elif rec.median_branch_segments > 0:
            rec.notes.append(
                f"{rec.median_branch_segments} segment(s) were median-subtracted "
                f"(shorter than the {rec.effective_window_cadences}-cadence window)"
            )

    n_dropped = rec.original_cadences - len(lc)
    rec.notes.append(
        f"Removed {n_dropped} cadences ({100*n_dropped/max(rec.original_cadences,1):.1f}%)"
    )

    logger.info(
        "Preprocessing complete: %d → %d cadences", rec.original_cadences, len(lc)
    )
    return lc, rec
