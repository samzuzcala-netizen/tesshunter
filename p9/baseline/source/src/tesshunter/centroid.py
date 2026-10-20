"""Centroid-shift vetting via Target Pixel Files.

During a genuine on-target transit the photometric centroid (flux-weighted
centre of the TPF) stays put.  If it moves, the dip is coming from a nearby
star that leaked into the aperture — a classic background-EB signature.

Pixel scales
────────────
  TESS   : 21 arcsec / pixel
  Kepler : 3.98 arcsec / pixel
  K2     : 3.98 arcsec / pixel

Decision rules
──────────────
  shift > 0.5 px   OR   shift > 3 σ  →  flagged

where σ is the error on the in-transit *median* centroid:
``1.4826 × MAD(OOT centroids) / sqrt(N_in)`` inflated ×2 for red noise
(per-point scatter would be ~sqrt(N) too insensitive).

Up to two sectors are analysed (inverse-variance-weighted combination) and
SPOC TPFs are preferred in the MAST search.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .utils import phase_fold
from .vetting import median_error

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_PIXEL_SCALE = {"TESS": 21.0, "KEPLER": 3.98, "K2": 3.98}   # arcsec / pixel
_SHIFT_FLAG_PX   = 0.5    # pixels
_SIGMA_THRESHOLD = 3.0    # σ of in-transit median-centroid error
_MAX_SECTORS_USED = 2     # V6: analyse up to two sectors when available


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CentroidResult:
    """Output of :func:`run_centroid_check`."""
    available:        bool  = False   # False if TPF could not be obtained
    col_shift_px:     float = 0.0
    row_shift_px:     float = 0.0
    total_shift_px:   float = 0.0
    shift_arcsec:     float = 0.0    # total shift converted to sky distance
    shift_err_px:     float = 0.0    # error on the shift (median error, ×2 red noise)
    sigma:            float = 0.0    # shift / median-centroid error
    n_in_transit:     int   = 0
    n_out_transit:    int   = 0
    n_sectors_used:   int   = 0
    sectors_used:     list  = field(default_factory=list)
    pixel_scale_arcsec: float = 21.0
    flagged:          bool  = False
    note:             str   = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pixel_scale(mission: str) -> float:
    return _PIXEL_SCALE.get(mission.upper(), 21.0)


def _as_float_array(x) -> np.ndarray:
    """Strip Astropy Quantity units if present and return a plain float array."""
    try:
        return np.asarray(x.value, dtype=float)
    except AttributeError:
        return np.asarray(x, dtype=float)


def _tpf_unit_label(tpf) -> str:
    """Short label for the observing unit of a TPF (e.g. ``S14``, ``C12``)."""
    for attr in ("sector", "campaign", "quarter"):
        value = getattr(tpf, attr, None)
        if value is not None:
            return f"{attr[0].upper()}{value}"
    return "unknown"


def _search_tpf(lk, target_str: str, mission: str, s):
    """Search MAST for a TPF, preferring SPOC products for TESS (V6)."""
    search_kwargs: dict = {"mission": mission}
    m_up = mission.upper()
    if m_up == "TESS" and s is not None:
        search_kwargs["sector"] = s
    elif m_up == "K2" and s is not None:
        search_kwargs["campaign"] = s
    elif m_up == "KEPLER" and s is not None:
        search_kwargs["quarter"] = s

    if m_up == "TESS":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            search = lk.search_targetpixelfile(target_str, author="SPOC", **search_kwargs)
        if len(search) > 0:
            return search
        logger.info(
            "Centroid: no SPOC TPF for %s (sector=%s); retrying without author preference",
            target_str, s,
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return lk.search_targetpixelfile(target_str, **search_kwargs)


def _measure_tpf(
    tpf,
    period_days: float,
    epoch_btjd: float,
    duration_days: float,
    px_scale: float,
) -> CentroidResult:
    """Measure the in- vs out-of-transit centroid offset for a single TPF."""
    # ── Extract centroids ─────────────────────────────────────────────────────
    try:
        centroid_col, centroid_row = tpf.estimate_centroids()
        times    = _as_float_array(tpf.time)
        col_vals = _as_float_array(centroid_col)
        row_vals = _as_float_array(centroid_row)
    except Exception as exc:
        return CentroidResult(
            available=False, pixel_scale_arcsec=px_scale,
            note=f"Centroid estimation failed: {exc}",
        )

    # ── Phase-fold and split in / out of transit ───────────────────────────────
    phase         = phase_fold(times, period_days, epoch_btjd)
    half_dur_ph   = (duration_days / period_days) / 2.0
    finite        = np.isfinite(col_vals) & np.isfinite(row_vals)
    in_transit    = finite & (np.abs(phase) < half_dur_ph)
    out_transit   = finite & (np.abs(phase) > half_dur_ph * 2.0)

    n_in  = int(in_transit.sum())
    n_out = int(out_transit.sum())

    if n_in < 3:
        return CentroidResult(
            available=True, pixel_scale_arcsec=px_scale,
            n_in_transit=n_in, n_out_transit=n_out,
            note=(
                f"Only {n_in} in-transit cadences in this TPF sector — "
                "insufficient for centroid test.  Try a sector with more transits."
            ),
        )
    if n_out < 10:
        return CentroidResult(
            available=True, pixel_scale_arcsec=px_scale,
            n_in_transit=n_in, n_out_transit=n_out,
            note=f"Only {n_out} out-of-transit cadences — centroid baseline too short.",
        )

    # ── Centroid difference ────────────────────────────────────────────────────
    col_in  = float(np.nanmedian(col_vals[in_transit]))
    col_out = float(np.nanmedian(col_vals[out_transit]))
    row_in  = float(np.nanmedian(row_vals[in_transit]))
    row_out = float(np.nanmedian(row_vals[out_transit]))

    col_shift      = col_in - col_out
    row_shift      = row_in - row_out
    total_shift_px = float(np.sqrt(col_shift ** 2 + row_shift ** 2))
    shift_arcsec   = total_shift_px * px_scale

    # ── Significance: error on the in-transit median centroid (V2) ─────────────
    # σ_median = 1.4826 × MAD(OOT) / sqrt(N_in), inflated ×2 for red noise.
    sigma_col = median_error(col_vals[out_transit], n_in)
    sigma_row = median_error(row_vals[out_transit], n_in)
    shift_err = float(np.sqrt((sigma_col ** 2 + sigma_row ** 2) / 2.0))
    sigma     = total_shift_px / max(shift_err, 1e-9)

    flagged = (total_shift_px > _SHIFT_FLAG_PX) or (sigma > _SIGMA_THRESHOLD)

    note = (
        f"Centroid shift: Δcol = {col_shift:+.3f} px, Δrow = {row_shift:+.3f} px, "
        f"total = {total_shift_px:.3f} px ({shift_arcsec:.1f} arcsec), "
        f"significance = {sigma:.1f}σ  "
        f"({n_in} in-transit, {n_out} OOT cadences, "
        f"1 px = {px_scale:.0f} arcsec)."
    )
    return CentroidResult(
        available=True,
        col_shift_px=col_shift,
        row_shift_px=row_shift,
        total_shift_px=total_shift_px,
        shift_arcsec=shift_arcsec,
        shift_err_px=shift_err,
        sigma=sigma,
        n_in_transit=n_in,
        n_out_transit=n_out,
        n_sectors_used=1,
        pixel_scale_arcsec=px_scale,
        flagged=flagged,
        note=note,
    )


def _flag_suffix(flagged: bool) -> str:
    if flagged:
        return (
            "  FLAGGED — centroid moves during transit.  "
            "Signal likely originates from a nearby contaminating source."
        )
    return "  Centroid consistent with on-target transit."


# ── Public function ───────────────────────────────────────────────────────────

def run_centroid_check(
    target,
    mission: str,
    sector,
    period_days: float,
    epoch_btjd: float,
    duration_days: float,
) -> CentroidResult:
    """Download up to two TPF sectors and measure in-transit centroid offset.

    Parameters
    ----------
    target:
        TIC ID (int) or resolvable name.
    mission:
        ``"TESS"``, ``"K2"``, or ``"Kepler"``.
    sector:
        Sector (TESS), campaign (K2), or quarter (Kepler) to use.
        Up to the first two elements are used when a list is supplied (V6);
        SPOC products are preferred in the MAST search.
    period_days, epoch_btjd, duration_days:
        Best-fit transit parameters from BLS.

    Returns
    -------
    :class:`CentroidResult`
        Never raises; sets ``available=False`` on any failure.  When two
        sectors yield usable measurements they are combined with
        inverse-variance weights.
    """
    import lightkurve as lk

    px_scale   = _pixel_scale(mission)
    target_str = f"TIC {target}" if isinstance(target, int) else str(target)

    # ── Use up to _MAX_SECTORS_USED sectors / campaigns / quarters ─────────────
    if isinstance(sector, (list, tuple)):
        sectors = list(sector[:_MAX_SECTORS_USED]) if len(sector) else [None]
    else:
        sectors = [sector]

    # ── Search & download TPFs (SPOC preferred) ────────────────────────────────
    tpfs: list = []
    problems: list[str] = []
    try:
        for s in sectors:
            if len(tpfs) >= _MAX_SECTORS_USED:
                break
            logger.info("Centroid: searching TPF for %s (sector=%s)", target_str, s)
            search = _search_tpf(lk, target_str, mission, s)
            if search is None or len(search) == 0:
                problems.append(f"No Target Pixel File found on MAST (sector={s}).")
                continue
            # When no sector was specified, one search can supply both products.
            n_take = min(len(search), _MAX_SECTORS_USED - len(tpfs)) if s is None else 1
            for i in range(n_take):
                logger.info("Centroid: downloading TPF (%d/%d)…",
                            len(tpfs) + 1, _MAX_SECTORS_USED)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    tpf = search[i].download()
                if tpf is None:
                    problems.append("TPF download returned None.")
                else:
                    tpfs.append(tpf)
    except Exception as exc:
        logger.warning("Centroid: TPF search/download failed: %s", exc)
        problems.append(f"TPF download failed: {exc}")

    if not tpfs:
        return CentroidResult(
            available=False, pixel_scale_arcsec=px_scale,
            note=" ".join(problems) or "No Target Pixel File found on MAST.",
        )

    # ── Measure each sector ────────────────────────────────────────────────────
    measurements: list[CentroidResult] = []
    for tpf in tpfs:
        res = _measure_tpf(tpf, period_days, epoch_btjd, duration_days, px_scale)
        res.sectors_used = [_tpf_unit_label(tpf)]
        measurements.append(res)

    valid = [
        m for m in measurements
        if m.available and m.n_in_transit >= 3 and m.n_out_transit >= 10
        and m.shift_err_px > 0
    ]

    if not valid:
        # Keep the old graceful behaviour: return the first (most informative)
        # per-sector outcome with the remaining problems appended.
        first = measurements[0]
        extra = [m.note for m in measurements[1:]] + problems
        if extra:
            first.note = " ".join([first.note] + extra).strip()
        return first

    if len(valid) == 1:
        result = valid[0]
        result.note += _flag_suffix(result.flagged)
        logger.info(
            "Centroid: shift=%.3f px (%.1f arcsec), %.1fσ, flagged=%s (1 sector)",
            result.total_shift_px, result.shift_arcsec, result.sigma, result.flagged,
        )
        return result

    # ── Combine sectors with inverse-variance weights ──────────────────────────
    weights = np.array([1.0 / m.shift_err_px ** 2 for m in valid])
    cols    = np.array([m.col_shift_px for m in valid])
    rows    = np.array([m.row_shift_px for m in valid])

    col_shift      = float(np.sum(weights * cols) / np.sum(weights))
    row_shift      = float(np.sum(weights * rows) / np.sum(weights))
    total_shift_px = float(np.sqrt(col_shift ** 2 + row_shift ** 2))
    shift_arcsec   = total_shift_px * px_scale
    shift_err      = float(np.sqrt(1.0 / np.sum(weights)))
    sigma          = total_shift_px / max(shift_err, 1e-9)
    n_in           = sum(m.n_in_transit for m in valid)
    n_out          = sum(m.n_out_transit for m in valid)
    sectors_used   = [label for m in valid for label in m.sectors_used]
    flagged        = (total_shift_px > _SHIFT_FLAG_PX) or (sigma > _SIGMA_THRESHOLD)

    note = (
        f"Centroid shift (weighted over {len(valid)} sectors: "
        f"{', '.join(sectors_used)}): "
        f"Δcol = {col_shift:+.3f} px, Δrow = {row_shift:+.3f} px, "
        f"total = {total_shift_px:.3f} px ({shift_arcsec:.1f} arcsec), "
        f"significance = {sigma:.1f}σ  "
        f"({n_in} in-transit, {n_out} OOT cadences, "
        f"1 px = {px_scale:.0f} arcsec)."
    ) + _flag_suffix(flagged)

    logger.info(
        "Centroid: shift=%.3f px (%.1f arcsec), %.1fσ, flagged=%s (%d sectors)",
        total_shift_px, shift_arcsec, sigma, flagged, len(valid),
    )
    return CentroidResult(
        available=True,
        col_shift_px=col_shift,
        row_shift_px=row_shift,
        total_shift_px=total_shift_px,
        shift_arcsec=shift_arcsec,
        shift_err_px=shift_err,
        sigma=sigma,
        n_in_transit=n_in,
        n_out_transit=n_out,
        n_sectors_used=len(valid),
        sectors_used=sectors_used,
        pixel_scale_arcsec=px_scale,
        flagged=flagged,
        note=note,
    )
