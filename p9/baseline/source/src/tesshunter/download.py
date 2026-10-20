"""Download TESS light curves from MAST via Lightkurve or direct HTTPS fallback."""

from __future__ import annotations

import logging
import os
import re
import warnings
from pathlib import Path
from typing import Optional

import lightkurve as lk
import numpy as np

from .config import LIGHTKURVE_CACHE
from .utils import ensure_dirs

logger = logging.getLogger(__name__)

# BTJD = BJD - BTJD_OFFSET  (TESS Barycentric Julian Date reference epoch)
_BTJD_OFFSET = 2_457_000.0

# Author priority for per-unit deduplication (lower rank wins).
# Unknown-but-present authors rank 3; missing AUTHOR meta ranks 4.
_TESS_AUTHOR_RANK = {"SPOC": 0, "TESS-SPOC": 1, "QLP": 2}
_K2_AUTHOR_RANK = {"K2": 0, "EVEREST": 1, "K2SFF": 2}


def _to_btjd(t_val: np.ndarray) -> np.ndarray:
    """Normalize a time array to BTJD.

    Some Lightkurve download paths return times in full BJD (~2 459 000) rather
    than BTJD (~1 300).  This function detects and corrects that so that
    stitching never mixes two time systems.
    """
    t_val = np.asarray(t_val, dtype=float)
    median = float(np.nanmedian(t_val))
    if median > 2_400_000:
        logger.debug(
            "Time array appears to be full BJD (median=%.1f); converting to BTJD",
            median,
        )
        t_val = t_val - _BTJD_OFFSET
    return t_val


def _configure_cache() -> None:
    ensure_dirs(LIGHTKURVE_CACHE)
    lk.conf.cache_dir = str(LIGHTKURVE_CACHE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_and_download(
    target: str | int,
    flux_type: str = "PDCSAP_FLUX",
    mission: str = "TESS",
    exptime: Optional[int] = 120,
    sector: Optional[int | list[int]] = None,
    max_sectors: Optional[int] = None,
) -> lk.LightCurveCollection | None:
    """Search MAST and download TESS light curves for a target.

    Parameters
    ----------
    target:      TIC ID (int) or resolvable name ("WASP-126").
    flux_type:   "PDCSAP_FLUX" (default) or "SAP_FLUX".
    exptime:     Cadence seconds. Default 120 (2-min SPOC). Use None for any.
    sector:      Restrict to specific sector(s).
    max_sectors: Cap number of sectors downloaded.

    Returns
    -------
    LightCurveCollection, or None if nothing could be downloaded.
    """
    _configure_cache()
    target_str = f"TIC {target}" if isinstance(target, int) else str(target)
    logger.info("Searching MAST for %s (exptime=%s, sector=%s)", target_str, exptime, sector)

    search_kwargs: dict = {"mission": mission}
    if exptime is not None:
        search_kwargs["exptime"] = exptime
    if sector is not None:
        search_kwargs["sector"] = sector

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = lk.search_lightcurve(target_str, **search_kwargs)
    except Exception as exc:
        if _is_network_error(exc):
            lcc = _load_cached_lightcurves(target_str, mission)
            if lcc is not None:
                logger.warning(
                    "MAST search failed with a network error (%s); using OFFLINE "
                    "cache-first mode — %d cached light curve(s) for %s",
                    exc, len(lcc), target_str,
                )
                lcc.tesshunter_events = [{
                    "event": "offline_cache_mode",
                    "detail": f"MAST search failed ({exc}); "
                              f"loaded {len(lcc)} cached file(s)",
                }]
                return lcc
        logger.error("MAST search failed for %s: %s", target_str, exc)
        return None

    if len(result) == 0:
        logger.warning("No light curves found for %s", target_str)
        return None

    if max_sectors is not None and len(result) > max_sectors:
        logger.info("Capping to %d of %d products", max_sectors, len(result))
        result = result[:max_sectors]

    logger.info("Attempting to download %d product(s)...", len(result))

    good: list[lk.LightCurve] = []
    n_failed = 0
    for i in range(len(result)):
        lc = _download_one(result, i, flux_type)
        if lc is not None:
            good.append(lc)
        else:
            n_failed += 1

    if not good:
        logger.error("All %d download attempts failed for %s", len(result), target_str)
        return None

    if n_failed:
        logger.warning("%d product(s) failed; continuing with %d good sector(s)",
                       n_failed, len(good))

    lcc = lk.LightCurveCollection(good)
    logger.info("Downloaded %d light curve(s) for %s", len(lcc), target_str)
    return lcc


# ---------------------------------------------------------------------------
# Product metadata helpers (dedup + provenance)
# ---------------------------------------------------------------------------

def _get_author(lc: lk.LightCurve) -> str | None:
    """Return the pipeline author from a light curve's meta, or None if absent."""
    meta = getattr(lc, "meta", {}) or {}
    for key in ("AUTHOR", "author", "PROVENANCE_NAME", "provenance_name"):
        val = meta.get(key)
        if val is not None:
            val = str(val).strip()
            if val and val.lower() != "none":
                return val
    return None


def _get_unit_number(lc: lk.LightCurve, mission: str = "TESS") -> int | None:
    """Return the observing unit number (sector/campaign/quarter) or None."""
    mission_up = mission.upper()
    if mission_up == "TESS":
        keys: tuple[str, ...] = ("SECTOR", "sector")
    elif mission_up == "K2":
        keys = ("CAMPAIGN", "campaign")
    elif mission_up in ("KEPLER", "K"):
        keys = ("QUARTER", "quarter")
    else:
        keys = ("SECTOR", "sector", "CAMPAIGN", "campaign", "QUARTER", "quarter")

    meta = getattr(lc, "meta", {}) or {}
    for key in keys:
        val = meta.get(key)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
    return None


def _estimate_cadence_s(lc: lk.LightCurve) -> float | None:
    """Estimate the cadence in seconds from the time column (fallback: TIMEDEL meta)."""
    try:
        t_val = np.asarray(lc.time.value, dtype=float)
        if len(t_val) >= 3:
            diffs = np.diff(t_val)
            diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
            if len(diffs) > 0:
                return float(np.median(diffs) * 86400.0)
    except Exception:
        pass
    meta = getattr(lc, "meta", {}) or {}
    timedel = meta.get("TIMEDEL")
    if timedel is not None:
        try:
            return float(timedel) * 86400.0
        except (TypeError, ValueError):
            pass
    return None


def _product_priority_key(lc: lk.LightCurve, mission: str = "TESS") -> tuple:
    """Sort key for choosing the best product within one observing unit.

    Lower is better: (author rank, SPOC cadence distance from 120 s,
    negative finite-cadence count).
    """
    rank_map = _K2_AUTHOR_RANK if mission.upper() == "K2" else _TESS_AUTHOR_RANK
    author = _get_author(lc)
    if author is None:
        rank = 4
    else:
        rank = rank_map.get(author.upper(), 3)

    cadence_penalty = 0.0
    if rank == 0 and mission.upper() != "K2":
        # Among SPOC products prefer 2-min cadence over 20-s.
        cadence = _estimate_cadence_s(lc)
        cadence_penalty = abs(cadence - 120.0) if cadence is not None else 1e9

    try:
        n_finite = int(np.isfinite(np.asarray(lc.flux.value, dtype=float)).sum())
    except Exception:
        n_finite = 0

    return (rank, cadence_penalty, -n_finite)


def dedupe_collection(
    lcc: lk.LightCurveCollection,
    mission: str = "TESS",
    max_units: Optional[int] = None,
) -> lk.LightCurveCollection:
    """Keep one best product per observing unit, then cap to distinct units.

    MAST searches routinely return the same sector from several pipelines
    (SPOC, TESS-SPOC, QLP, ...). Stitching those duplicates double-counts
    cadences, so this picks a single winner per unit using author priority:

    * TESS: SPOC (2-min preferred) > TESS-SPOC > QLP > other HLSPs
    * K2:   K2 > EVEREST > K2SFF > other

    Products with missing AUTHOR meta rank last. Products whose unit number
    cannot be determined are kept as pseudo-units after all numbered units
    (so a ``max_units`` cap counts them only if room remains).

    Parameters
    ----------
    lcc:
        Input collection (or any iterable of LightCurves).
    mission:
        "TESS", "K2", or "Kepler" — selects the unit meta key and priority table.
    max_units:
        Keep at most this many DISTINCT observing units (sorted by unit
        number, ascending). None keeps all.

    Returns
    -------
    LightCurveCollection with one product per unit, sorted by unit number.
    """
    products = list(lcc)
    groups: dict[int, list[lk.LightCurve]] = {}
    unknown: list[lk.LightCurve] = []
    for lc in products:
        unit = _get_unit_number(lc, mission)
        if unit is None:
            unknown.append(lc)
        else:
            groups.setdefault(unit, []).append(lc)

    ordered_units = sorted(groups)
    if max_units is not None and len(ordered_units) > max_units:
        logger.info(
            "Capping to first %d of %d distinct observing units",
            max_units, len(ordered_units),
        )
        ordered_units = ordered_units[:max_units]

    winners: list[lk.LightCurve] = []
    for unit in ordered_units:
        candidates = groups[unit]
        best = min(candidates, key=lambda p: _product_priority_key(p, mission))
        if len(candidates) > 1:
            logger.info(
                "Unit %d: %d duplicate products; keeping author=%s",
                unit, len(candidates), _get_author(best) or "unknown",
            )
        winners.append(best)

    if unknown:
        if max_units is None:
            winners.extend(unknown)
        else:
            room = max(0, max_units - len(ordered_units))
            winners.extend(unknown[:room])
        logger.debug("%d product(s) had no unit number in meta", len(unknown))

    if len(winners) != len(products):
        logger.info(
            "Deduplicated %d products -> %d (one per observing unit)",
            len(products), len(winners),
        )
    return lk.LightCurveCollection(winners)


# ---------------------------------------------------------------------------
# Unit-aware normalisation
# ---------------------------------------------------------------------------

def _robust_std(x: np.ndarray) -> float:
    """Robust standard deviation via 1.4826 * MAD (0.0 for constant input)."""
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return 0.0
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def _local_scatter(flux: np.ndarray) -> float:
    """Robust point-to-point scatter: 1.4826 * median(|diff|) / sqrt(2).

    Differencing removes slow trends and (mostly) transits, so unlike a
    global std this is not inflated by astrophysical signal.
    """
    finite = flux[np.isfinite(flux)]
    if len(finite) < 3:
        return float("nan")
    diffs = np.abs(np.diff(finite))
    diffs = diffs[np.isfinite(diffs)]
    if len(diffs) == 0:
        return float("nan")
    return float(1.4826 * np.median(diffs) / np.sqrt(2.0))


def _normalise_product(lc: lk.LightCurve) -> tuple[np.ndarray, np.ndarray] | None:
    """Normalise one product to relative flux (median ~ 1.0), unit-aware.

    Branches
    --------
    * Magnitudes (flux unit contains "mag", or author CDIPS):
      ``flux = 10**(-0.4 * (m - median(m)))``.
    * ppm-style flux (unit contains "ppm"): ``flux = 1 + x / 1e6``.
    * Zero-centered flux in an unknown unit (|median| < 1e-10): SKIP the
      product with a warning — dividing by a near-zero median produces garbage.
    * Anything else: divide by the median as before.

    Missing/all-NaN flux_err is filled with a robust local scatter estimate
    (never a global std, which is inflated by transits).

    Returns
    -------
    (flux_norm, err_norm) arrays, or None if the product must be skipped.
    """
    flux = np.asarray(lc.flux.value, dtype=float).copy()
    finite = np.isfinite(flux)
    label = f"unit={_get_unit_number(lc)} author={_get_author(lc) or 'unknown'}"
    if finite.sum() < 10:
        logger.warning("Skipping product (%s): fewer than 10 finite cadences", label)
        return None

    unit_str = str(getattr(lc.flux, "unit", "") or "").lower()
    author = (_get_author(lc) or "").upper()
    med = float(np.nanmedian(flux[finite]))

    err: np.ndarray | None = None
    if lc.flux_err is not None:
        err_raw = np.asarray(lc.flux_err.value, dtype=float)
        if np.any(np.isfinite(err_raw)):
            err = err_raw

    if "mag" in unit_str or author == "CDIPS":
        # Instrumental magnitudes: convert to relative flux. A transit
        # (fainter, m > median) must map to flux < 1, never a brightening.
        logger.info("Product (%s) is in magnitudes; converting to relative flux", label)
        flux_norm = 10.0 ** (-0.4 * (flux - med))
        err_norm = (
            np.abs(flux_norm * 0.4 * np.log(10.0) * err) if err is not None else None
        )
    elif "ppm" in unit_str:
        # Zero-centered ppm flux (TASOC-style): relative flux offset in ppm.
        logger.info("Product (%s) is ppm-style flux; converting via 1 + x/1e6", label)
        flux_norm = 1.0 + flux / 1e6
        err_norm = np.abs(err / 1e6) if err is not None else None
    elif abs(med) < max(1e-10, 3.0 * _robust_std(flux[finite])):
        # Zero-centered flux in an unknown unit. NOTE: the median of noisy
        # zero-centered data is ~scatter/sqrt(N), never exactly 0, so the
        # test must be scatter-relative — a bare |med| < 1e-10 check lets
        # these products through to a divide-by-near-zero. Normalising by
        # the median (or any guess) would corrupt it. Skip and say so.
        logger.warning(
            "Skipping product (%s): zero-centered flux with unknown unit '%s' "
            "(median=%.3g) — cannot normalise safely",
            label, unit_str or "dimensionless", med,
        )
        return None
    else:
        flux_norm = flux / med
        err_norm = np.abs(err / med) if err is not None else None

    # Fill missing / non-finite errors with a robust LOCAL scatter estimate.
    scatter = _local_scatter(flux_norm)
    if err_norm is None:
        err_norm = np.full(len(flux_norm), scatter)
    else:
        bad = ~np.isfinite(err_norm)
        if bad.any():
            err_norm = err_norm.copy()
            err_norm[bad] = scatter

    return flux_norm, err_norm


def stitch_collection(
    lcc: lk.LightCurveCollection,
    dedupe: bool = True,
    max_units: Optional[int] = None,
    mission: str = "TESS",
) -> lk.LightCurve:
    """Normalise each product to median=1.0, then concatenate into one LightCurve.

    Bypasses Lightkurve's lcc.stitch() to avoid unit-mismatch issues between
    sectors that arrive in electrons/s versus ppm/relative-flux formats.
    Normalisation is unit-aware (magnitudes, ppm, zero-centered products are
    handled explicitly — see :func:`_normalise_product`).

    Parameters
    ----------
    lcc:
        Collection of light curves to stitch.
    dedupe:
        If True (default), first reduce the collection to one best product
        per observing unit via :func:`dedupe_collection` so duplicate
        pipeline copies of the same sector are never double-counted.
    max_units:
        Cap on DISTINCT observing units (not raw products). None = no cap.
    mission:
        Mission name used for unit lookup and author priority.

    Returns
    -------
    A single stitched LightCurve. Its ``meta`` records provenance:
    ``meta["TESSHUNTER_PROVENANCE"]`` is a list of one dict per stitched
    product ({"unit", "author", "n_cadences", "cadence_s"}) and
    ``meta["TESSHUNTER_UNITS"]`` is the sorted distinct unit list.
    ``meta["SECTOR"]`` stays 'multi' for backward compatibility.
    """
    from astropy import units as u

    if dedupe:
        lcc = dedupe_collection(lcc, mission=mission, max_units=max_units)
    elif max_units is not None:
        # No author dedup requested, but still cap on distinct units.
        known_units = sorted(
            {un for lc in lcc if (un := _get_unit_number(lc, mission)) is not None}
        )
        keep_units = set(known_units[:max_units])
        capped = [
            lc for lc in lcc
            if (_get_unit_number(lc, mission) in keep_units
                or _get_unit_number(lc, mission) is None)
        ]
        lcc = lk.LightCurveCollection(capped)

    all_time, all_flux, all_err = [], [], []
    provenance: list[dict] = []
    n_skipped = 0

    for lc in lcc:
        normed = _normalise_product(lc)
        if normed is None:
            n_skipped += 1
            continue
        flux_norm, err_norm = normed

        all_time.append(_to_btjd(lc.time.value))
        all_flux.append(flux_norm)
        all_err.append(err_norm)
        provenance.append({
            "unit": _get_unit_number(lc, mission),
            "author": _get_author(lc) or "unknown",
            "n_cadences": int(len(flux_norm)),
            "cadence_s": _estimate_cadence_s(lc),
        })

    if not all_time:
        logger.error("No usable sectors after normalisation; returning first sector raw")
        return lcc[0]

    if n_skipped:
        logger.warning("Skipped %d sector(s) with unusable flux", n_skipped)

    # Concatenate and sort by time
    t_cat = np.concatenate(all_time)
    f_cat = np.concatenate(all_flux)
    e_cat = np.concatenate(all_err)
    order = np.argsort(t_cat)
    t_cat, f_cat, e_cat = t_cat[order], f_cat[order], e_cat[order]

    # Always output in BTJD — prevents format mismatches from producing
    # multi-million-day baselines when some sectors arrive as full BJD.
    from astropy.time import Time as AstropyTime
    time_obj = AstropyTime(t_cat, format="btjd", scale="tdb")

    result = lk.LightCurve(
        time=time_obj,
        flux=f_cat * u.dimensionless_unscaled,
        flux_err=e_cat * u.dimensionless_unscaled,
    )
    result.meta["SECTOR"] = "multi"
    result.meta["TESSHUNTER_PROVENANCE"] = provenance
    result.meta["TESSHUNTER_UNITS"] = sorted(
        {p["unit"] for p in provenance if p["unit"] is not None}
    )

    baseline = float(t_cat[-1] - t_cat[0])
    logger.info(
        "Stitched %d sectors → %d cadences spanning %.1f days"
        "  (BTJD %.1f – %.1f, median flux ~1.0)",
        len(all_time), len(t_cat), baseline, float(t_cat[0]), float(t_cat[-1]),
    )
    return result


def sectors_available(lcc: lk.LightCurveCollection) -> list[int]:
    """Return a sorted list of sector numbers present in the collection."""
    sectors = []
    for lc in lcc:
        meta = getattr(lc, "meta", {})
        sec = meta.get("SECTOR") or meta.get("sector")
        if sec is not None:
            try:
                sectors.append(int(sec))
            except (TypeError, ValueError):
                pass
    return sorted(set(sectors))


def get_tic_id_from_name(name: str) -> int | None:
    """Attempt to resolve a target name to a TIC ID via a MAST search."""
    _configure_cache()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = lk.search_lightcurve(name, mission="TESS")
        if len(result) > 0:
            raw = str(result.table["target_name"][0])
            if raw.upper().startswith("TIC"):
                return int(raw.upper().replace("TIC", "").strip())
    except Exception as exc:
        logger.warning("Could not resolve TIC ID for '%s': %s", name, exc)
    return None


def search_and_download_lc(
    target: str | int,
    mission: str = "TESS",
    sector: Optional[int | list[int]] = None,
    campaign: Optional[int | list[int]] = None,
    quarter: Optional[int | list[int]] = None,
    author: Optional[str | list[str]] = None,
    exptime: str | int | None = "auto",
    quality_bitmask: str = "default",
    max_results: Optional[int] = None,
) -> lk.LightCurveCollection | None:
    """Mission-aware search and download from MAST via Lightkurve.

    Supports TESS (sectors), K2 (campaigns), and Kepler (quarters).
    Tries a batch ``download_all()`` first; falls back to individual
    downloads on failure.

    Parameters
    ----------
    target:
        TIC ID (int), EPIC ID string ("EPIC 200164267"), KIC ID string,
        or any name resolvable by SIMBAD / MAST ("TRAPPIST-1").
    mission:
        "TESS", "K2", or "Kepler".
    sector:
        TESS-only — specific sector number(s), or None for all available.
    campaign:
        K2-only — specific campaign number(s), or None for all available.
    quarter:
        Kepler-only — specific quarter number(s), or None for all available.
    author:
        Preferred pipeline author ("K2SFF", "EVEREST", "SPOC", etc.).
        None lets Lightkurve choose the default for the mission.
    exptime:
        Cadence filter. Default "auto": author SPOC implies 120 s
        (2-min cadence); any other author (or None) applies no exptime
        filter so all cadences are searched and product selection happens
        later via :func:`dedupe_collection` priority. An explicit value
        ("long", "short", int seconds, or None for any) is honoured as-is.
    quality_bitmask:
        Lightkurve quality mask: "default", "hard", or "hardest".
    max_results:
        Cap the number of results to download (None = no cap).

    Returns
    -------
    LightCurveCollection, or None if nothing could be downloaded.
    Any fallback taken (author-filter drop, offline cache mode, individual
    downloads) is recorded on the returned collection as
    ``lcc.tesshunter_events`` — a list of {"event", "detail"} dicts
    (empty list when no fallback fired).
    """
    _configure_cache()
    target_str = f"TIC {target}" if isinstance(target, int) else str(target)
    mission_up = mission.upper()
    events: list[dict] = []

    # ── Resolve the "auto" exptime sentinel (cadence-aware search) ─────────────
    if isinstance(exptime, str) and exptime.lower() == "auto":
        author_str = author if isinstance(author, str) else None
        if author_str is not None and author_str.strip().upper() == "SPOC":
            exptime_eff: str | int | None = 120
            logger.debug("exptime='auto': author SPOC -> exptime=120 s")
        else:
            exptime_eff = None
            logger.debug(
                "exptime='auto': no exptime filter (author=%s); "
                "selection deferred to dedupe priority", author,
            )
    else:
        exptime_eff = exptime

    logger.info(
        "Searching MAST for %s  mission=%s  exptime=%s",
        target_str, mission, exptime_eff,
    )

    # ── Build search kwargs ────────────────────────────────────────────────────
    search_kwargs: dict = {"mission": mission}
    if mission_up == "TESS" and sector is not None:
        search_kwargs["sector"] = sector
    elif mission_up == "K2" and campaign is not None:
        search_kwargs["campaign"] = campaign
    elif mission_up == "KEPLER" and quarter is not None:
        search_kwargs["quarter"] = quarter
    if author is not None:
        search_kwargs["author"] = author
    if exptime_eff is not None:
        search_kwargs["exptime"] = exptime_eff

    # ── MAST search (with offline cache-first fallback on network errors) ─────
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = lk.search_lightcurve(target_str, **search_kwargs)
    except Exception as exc:
        if _is_network_error(exc):
            lcc = _load_cached_lightcurves(target_str, mission)
            if lcc is not None:
                logger.warning(
                    "MAST search failed with a network error (%s); using OFFLINE "
                    "cache-first mode — %d cached light curve(s) for %s",
                    exc, len(lcc), target_str,
                )
                events.append({
                    "event": "offline_cache_mode",
                    "detail": f"MAST search failed ({exc}); "
                              f"loaded {len(lcc)} cached file(s)",
                })
                lcc.tesshunter_events = events
                return lcc
        logger.error("MAST search failed for %s: %s", target_str, exc)
        return None

    if len(result) == 0:
        logger.warning("No light curves found for %s (%s)", target_str, mission)
        if author is not None:
            # Retry without the author filter — not all targets exist in every
            # pipeline. NEVER silent: log at WARNING and record the event.
            logger.warning(
                "Search returned 0 rows for author=%r; retrying WITHOUT the "
                "author filter — products from other pipelines may be returned",
                author,
            )
            events.append({
                "event": "author_drop_retry",
                "detail": f"search returned 0 rows for author={author!r} "
                          f"(mission={mission}, exptime={exptime_eff}); "
                          f"retried without author filter",
            })
            search_kwargs_retry = {k: v for k, v in search_kwargs.items() if k != "author"}
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = lk.search_lightcurve(target_str, **search_kwargs_retry)
            except Exception as exc2:
                logger.error("Retry search failed: %s", exc2)
                return None
        if len(result) == 0:
            return None

    if max_results is not None and len(result) > max_results:
        logger.info("Capping to %d of %d products", max_results, len(result))
        result = result[:max_results]

    logger.info("Found %d product(s) — attempting batch download...", len(result))

    # ── Strategy 1: download_all() (batch) ────────────────────────────────────
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lcc = result.download_all(quality_bitmask=quality_bitmask)
        if lcc is not None and len(lcc) > 0:
            logger.info("Batch download succeeded: %d light curve(s)", len(lcc))
            lcc.tesshunter_events = events
            return lcc
    except Exception as exc:
        logger.debug("Batch download_all() failed (%s) — falling back to individual", exc)
        events.append({
            "event": "individual_download_fallback",
            "detail": f"batch download_all() failed: {exc}",
        })

    # ── Strategy 2: individual downloads ──────────────────────────────────────
    logger.info("Trying individual downloads...")
    lcc = _download_individually(result, quality_bitmask)
    if lcc is not None:
        lcc.tesshunter_events = events
    return lcc


def observing_units_available(
    lcc: lk.LightCurveCollection,
    mission: str = "TESS",
) -> list[int]:
    """Return sorted list of sector / campaign / quarter numbers in the collection.

    The mission parameter selects which metadata key to look for:

    * TESS   → ``SECTOR``
    * K2     → ``CAMPAIGN``
    * Kepler → ``QUARTER``
    """
    mission_up = mission.upper()
    if mission_up == "TESS":
        keys: tuple[str, ...] = ("SECTOR", "sector")
    elif mission_up == "K2":
        keys = ("CAMPAIGN", "campaign")
    elif mission_up in ("KEPLER", "K"):
        keys = ("QUARTER", "quarter")
    else:
        keys = ("SECTOR", "sector", "CAMPAIGN", "campaign", "QUARTER", "quarter")

    units: list[int] = []
    for lc in lcc:
        meta = getattr(lc, "meta", {})
        for key in keys:
            val = meta.get(key)
            if val is not None:
                try:
                    units.append(int(val))
                    break
                except (TypeError, ValueError):
                    pass

    return sorted(set(units))


# ---------------------------------------------------------------------------
# Internal download helpers (Strategy 1 → 2 → 3)
# ---------------------------------------------------------------------------

def _download_one(result, index: int, flux_type: str) -> lk.LightCurve | None:
    """Try three strategies to obtain one light curve, returning the first that works."""

    # Strategy 1: Lightkurve standard download with flux_column
    lc = _lk_download(result, index, flux_type)
    if lc is not None:
        return lc

    # Strategy 2: Lightkurve download without flux_column, select column afterwards
    lc = _lk_download_no_col(result, index, flux_type)
    if lc is not None:
        return lc

    # Strategy 3: Direct HTTPS download + astropy.io.fits read (bypasses LK reader)
    lc = _direct_download(result, index, flux_type)
    if lc is not None:
        return lc

    logger.warning("All strategies failed for product %d", index + 1)
    return None


def _lk_download(result, index: int, flux_type: str) -> lk.LightCurve | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lc = result[index].download(flux_column=flux_type)
        return lc
    except Exception as exc:
        logger.debug("LK strategy 1 failed for product %d: %s", index + 1, exc)
        return None


def _lk_download_no_col(result, index: int, flux_type: str) -> lk.LightCurve | None:
    """Download without specifying flux_column; re-select column if needed."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lc = result[index].download()
        if lc is None:
            return None
        # If flux_type column is available as an attribute, rebuild the LC
        col_lower = flux_type.lower()
        if hasattr(lc, col_lower) and col_lower != "flux":
            from astropy import units as u
            col_data = getattr(lc, col_lower)
            err_attr = col_lower + "_err"
            err_data = getattr(lc, err_attr, None)
            lc2 = lk.LightCurve(
                time=lc.time,
                flux=col_data,
                flux_err=err_data,
            )
            lc2.meta.update(lc.meta)
            return lc2
        return lc
    except Exception as exc:
        logger.debug("LK strategy 2 failed for product %d: %s", index + 1, exc)
        return None


def _is_spoc_tess_product(row, filename: str) -> bool:
    """True if a search-result row is a SPOC TESS product the direct-download
    MAST URL scheme (``mast:TESS/product/...``) can actually fetch.

    HLSP (TESS-SPOC, QLP, ...) and K2/Kepler products live under different
    MAST URIs, so the fallback must not be attempted for them.
    """
    fname = filename.lower()
    looks_spoc = fname.startswith("tess") and fname.endswith("_lc.fits")

    col_names = row.colnames if hasattr(row, "colnames") else list(row.keys())

    author = None
    for col in ("author", "provenance_name"):
        if col in col_names:
            val = str(row[col]).strip()
            if val and val.lower() != "none":
                author = val
                break

    obs = None
    for col in ("obs_collection", "project", "mission"):
        if col in col_names:
            val = str(row[col]).strip()
            if val and val.lower() != "none":
                obs = val
                break

    if author is not None and author.upper() != "SPOC":
        return False
    if obs is not None and "TESS" not in obs.upper():
        return False
    return looks_spoc


def _direct_download(result, index: int, flux_type: str) -> lk.LightCurve | None:
    """Download the FITS file via HTTPS and read it with astropy.io.fits directly.

    Only attempted for SPOC TESS products (the hardcoded MAST URL scheme is
    wrong for HLSP/K2 products). Downloads go to a temp file first and are
    atomically renamed into the cache, so a truncated transfer can never
    poison the cache; a cached file that fails to parse is deleted.
    """
    try:
        import requests
    except ImportError:
        logger.debug("requests not available; skipping direct download strategy")
        return None

    try:
        row = result.table[index]

        # Find the filename in whatever column is present
        filename = _get_filename_from_row(row)
        if not filename:
            logger.debug("Could not determine filename for product %d", index + 1)
            return None

        if not _is_spoc_tess_product(row, filename):
            logger.debug(
                "Product %d (%s) is not a SPOC TESS product; "
                "direct-download fallback does not apply", index + 1, filename,
            )
            return None

        # MAST public download URL (SPOC TESS products only — checked above)
        url = f"https://mast.stsci.edu/api/v0.1/Download/file?uri=mast:TESS/product/{filename}"
        dest = LIGHTKURVE_CACHE / filename
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Download if not already cached: write to a temp file, then rename
        # atomically so partial downloads never land at the final path.
        if not dest.exists() or dest.stat().st_size < 1000:
            logger.info("Direct download: %s", filename)
            tmp = dest.with_name(dest.name + ".part")
            try:
                headers = {"User-Agent": "tesshunter/0.1"}
                r = requests.get(url, headers=headers, timeout=120, stream=True)
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
                os.replace(tmp, dest)
            finally:
                tmp.unlink(missing_ok=True)

        # Read the FITS file with astropy; a cache entry that cannot be
        # parsed is deleted so it gets re-downloaded next time.
        lc = _read_tess_spoc_fits(dest, flux_type)
        if lc is None:
            logger.warning("Deleting unreadable cached file %s", dest.name)
            dest.unlink(missing_ok=True)
        return lc

    except Exception as exc:
        logger.warning("Direct download strategy failed for product %d: %s", index + 1, exc)
        return None


def _get_filename_from_row(row) -> str | None:
    """Extract the FITS filename from a Lightkurve search-result table row."""
    col_names = row.colnames if hasattr(row, "colnames") else list(row.keys())
    for col in ("productFilename", "filename", "dataFilename", "obs_id"):
        if col in col_names:
            val = str(row[col]).strip()
            if val and val.lower() != "none" and val.lower().endswith(".fits"):
                return val
    # Try to reconstruct from the URI column
    for col in ("dataURI", "dataurl", "uri"):
        if col in col_names:
            uri = str(row[col]).strip()
            if uri:
                return uri.split("/")[-1]
    return None


def _read_tess_spoc_fits(filepath: Path, flux_type: str) -> lk.LightCurve | None:
    """Parse a TESS SPOC _lc.fits file using astropy.io.fits.

    Applies the default QUALITY bitmask and drops NaN flux, matching what
    the Lightkurve reader would do.

    Returns a LightCurve with flux and flux_err set to the requested column.
    """
    import astropy.io.fits as fits
    from astropy.time import Time
    from astropy import units as u

    try:
        with fits.open(str(filepath), memmap=False) as hdul:
            # Find the LIGHTCURVE extension
            ext_names = [h.name.upper() for h in hdul]
            if "LIGHTCURVE" in ext_names:
                ext = ext_names.index("LIGHTCURVE")
            elif len(hdul) > 1:
                ext = 1
            else:
                logger.warning("No LIGHTCURVE extension in %s", filepath.name)
                return None

            data = hdul[ext].data
            primary_hdr = hdul[0].header
            col_names = [c.name.upper() for c in data.columns]

            time_raw = np.array(data["TIME"], dtype=float)

            # Flux column selection
            flux_col = flux_type.upper()
            err_col = flux_col + "_ERR"
            if flux_col not in col_names:
                # Fall back to whatever is available
                for candidate in ("PDCSAP_FLUX", "SAP_FLUX", "FLUX"):
                    if candidate in col_names:
                        flux_col = candidate
                        err_col = flux_col + "_ERR"
                        logger.info("flux_type '%s' not found; using '%s'", flux_type, flux_col)
                        break

            flux_raw = np.array(data[flux_col], dtype=float)
            flux_err_raw = (
                np.array(data[err_col], dtype=float)
                if err_col in col_names
                else np.full_like(flux_raw, np.nan)
            )

            # Keep rows with finite time AND finite flux, and apply the
            # default QUALITY bitmask (the Lightkurve reader does both;
            # this fallback must not silently skip them).
            valid = np.isfinite(time_raw) & np.isfinite(flux_raw)
            if "QUALITY" in col_names:
                quality = np.asarray(data["QUALITY"], dtype=np.int64)
                try:
                    from lightkurve.utils import TessQualityFlags
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        quality_ok = TessQualityFlags.create_quality_mask(
                            quality, bitmask="default"
                        )
                except Exception:
                    quality_ok = quality == 0
                n_flagged = int((~quality_ok).sum())
                if n_flagged:
                    logger.debug(
                        "Dropping %d quality-flagged cadence(s) from %s",
                        n_flagged, filepath.name,
                    )
                valid &= quality_ok
            if valid.sum() < 10:
                logger.warning("Too few valid cadences in %s", filepath.name)
                return None

            time_obj = Time(time_raw[valid], format="btjd", scale="tdb")
            lc = lk.LightCurve(
                time=time_obj,
                flux=flux_raw[valid] * u.electron / u.s,
                flux_err=flux_err_raw[valid] * u.electron / u.s,
            )
            lc.meta["SECTOR"] = primary_hdr.get("SECTOR", 0)
            lc.meta["TICID"] = primary_hdr.get("TICID", 0)
            lc.meta["filename"] = filepath.name
            logger.debug("Read %d cadences from %s", valid.sum(), filepath.name)
            return lc

    except Exception as exc:
        logger.warning("astropy FITS read failed for %s: %s", filepath.name, exc)
        return None


def _download_individually(
    result,
    quality_bitmask: str = "default",
) -> lk.LightCurveCollection | None:
    """Download each search result one at a time; return a collection of successes."""
    good: list[lk.LightCurve] = []
    n_failed = 0

    for i in range(len(result)):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                lc = result[i].download(quality_bitmask=quality_bitmask)
            if lc is not None:
                good.append(lc)
            else:
                n_failed += 1
        except Exception as exc:
            logger.debug("Individual download failed for product %d: %s", i + 1, exc)
            n_failed += 1

    if not good:
        logger.error("All %d individual download attempts failed", len(result))
        return None

    if n_failed:
        logger.warning(
            "%d product(s) failed; continuing with %d good LC(s)",
            n_failed, len(good),
        )

    return lk.LightCurveCollection(good)


# ---------------------------------------------------------------------------
# Offline cache-first fallback (used when the MAST search hits a network error)
# ---------------------------------------------------------------------------

def _is_network_error(exc: BaseException) -> bool:
    """Heuristically decide whether an exception is network-related.

    Checks the exception type (ConnectionError, TimeoutError, requests
    exceptions) and message keywords, walking the ``__cause__``/``__context__``
    chain so wrapped errors are recognised too.
    """
    network_types: tuple[type, ...] = (ConnectionError, TimeoutError)
    try:
        import requests
        network_types = network_types + (requests.exceptions.RequestException,)
    except ImportError:
        pass

    keywords = (
        "connection", "timed out", "timeout", "network", "unreachable",
        "getaddrinfo", "name or service not known", "max retries",
        "remote end closed", "ssl", "resolve", "temporary failure",
        "502", "503", "504",
    )

    seen: set[int] = set()
    e: BaseException | None = exc
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        if isinstance(e, network_types):
            return True
        msg = str(e).lower()
        if any(k in msg for k in keywords):
            return True
        e = e.__cause__ or e.__context__
    return False


def _load_cached_lightcurves(
    target_str: str,
    mission: str = "TESS",
) -> lk.LightCurveCollection | None:
    """Scan the Lightkurve cache for FITS files matching a target and load them.

    Matches on the numeric part of the target identifier (TIC/EPIC/KIC id),
    which appears — possibly zero-padded — in every mission product filename.
    Name-based targets ("WASP-126") cannot be matched offline and return None.

    Returns
    -------
    LightCurveCollection of readable cached files, or None if none matched.
    """
    m = re.search(r"(\d{5,})", target_str)
    if m is None:
        logger.debug(
            "Cannot match '%s' against the cache (no numeric id of >= 5 digits)",
            target_str,
        )
        return None
    ident = m.group(1)
    mission_up = mission.upper()

    if not LIGHTKURVE_CACHE.exists():
        return None

    matches: list[Path] = []
    for path in sorted(LIGHTKURVE_CACHE.rglob("*.fits")):
        fname = path.name.lower()
        if ident not in fname:
            continue
        if mission_up == "TESS" and "tess" not in fname:
            continue
        if mission_up == "K2" and not any(k in fname for k in ("ktwo", "k2", "everest")):
            continue
        if mission_up == "KEPLER" and "kplr" not in fname:
            continue
        matches.append(path)

    if not matches:
        logger.debug("No cached FITS files match id %s (mission=%s)", ident, mission)
        return None

    good: list[lk.LightCurve] = []
    for path in matches:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                lc = lk.read(str(path))
            good.append(lc)
        except Exception as exc:
            logger.debug("lk.read failed for cached file %s: %s", path.name, exc)
            # SPOC-style files can still be parsed by the direct FITS reader.
            if path.name.lower().endswith("_lc.fits"):
                lc = _read_tess_spoc_fits(path, "PDCSAP_FLUX")
                if lc is not None:
                    good.append(lc)

    if not good:
        logger.debug("All %d cached matches failed to load", len(matches))
        return None

    logger.info(
        "Loaded %d of %d cached FITS file(s) for id %s from %s",
        len(good), len(matches), ident, LIGHTKURVE_CACHE,
    )
    return lk.LightCurveCollection(good)
