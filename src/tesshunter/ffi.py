"""FFI light-curve products (QLP, TESS-SPOC) as first-class survey inputs.

The benchmark path (SPOC 2-minute products, ``search_target``) is untouched.
This module is the survey's ingestion layer and is only used when a caller
asks for it (``tesshunter.survey``):

* **flux column per author** — QLP ships ``sap_flux`` (raw aperture) and a
  spline-detrended flux (``kspsap_flux`` in sectors 1-55, ``det_flux`` from
  sector 56); lightkurve's reader loads ``sap_flux`` by default. TESS-SPOC and
  SPOC use PDCSAP. Which QLP column the survey searches is a config choice
  recorded in the provenance of every stitched curve.
* **quality per author** — lightkurve applies the TESS "default" bitmask to
  every product. QLP additionally marks low-precision cadences (bit 13 in
  sectors 1-55, bit 31 from sector 56; scattered-light dominated) which the
  default mask keeps; the survey can drop them.
* **per-segment edge trimming** — the first and last ``edge_trim_minutes``
  of every contiguous segment (sector, orbit, or post-gap run) can be
  removed so that scattered-light ramps at orbit edges do not become box
  dips after detrending.
* **per-product normalisation and a common cadence** — each product is
  normalised to median 1 by :func:`tesshunter.download._normalise_product`
  through :func:`tesshunter.download.stitch_collection`; products with a
  cadence finer than ``target_cadence_minutes`` are binned to it first so a
  stitched curve never mixes 2-minute and 30-minute sampling (the flatten
  window is expressed in cadences and would otherwise be wrong for one of
  them).

Nothing here decides which sectors exist or which product wins a sector;
that is :func:`tesshunter.download.dedupe_collection` (SPOC > TESS-SPOC >
QLP), applied before any of the above.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Optional

import lightkurve as lk
import numpy as np

from . import preprocessing
from .download import (
    _estimate_cadence_s,
    _get_author,
    _get_unit_number,
    _local_scatter,
    dedupe_collection,
    stitch_collection,
)

#: Bump whenever ingestion behaviour changes; hashed into the stitched-cache
#: key so curves built by an older ingestion are never served.
INGEST_VERSION = 3

logger = logging.getLogger(__name__)

#: Authors the survey ingests. Anything else (CDIPS, TASOC, TGLC, eleanor,
#: ...) is dropped with a provenance note: their normalisation and quality
#: conventions differ and none is needed for the chosen stratum (every
#: stratum-3 star has a QLP light curve; half also have TESS-SPOC).
SURVEY_AUTHORS: tuple[str, ...] = ("SPOC", "TESS-SPOC", "QLP")

#: QLP low-precision quality bit by sector range (QLP data product
#: description; mirrored in lightkurve's QLP reader).
QLP_LOW_PRECISION_BIT_S1_55 = 2 ** 12
QLP_LOW_PRECISION_BIT_S56_PLUS = 2 ** 30

#: First sector in which QLP renamed the detrended columns ``det_*``.
QLP_DET_FROM_SECTOR = 56


@dataclass
class ProductPrep:
    """What ingestion did to one product (goes into the stitched provenance)."""

    unit: Optional[int]
    author: str
    flux_column: str
    flux_err_column: Optional[str]
    n_cadences_in: int
    n_after_quality: int
    n_after_trim: int
    n_after_bin: int
    cadence_s_native: Optional[float]
    cadence_s_out: Optional[float]
    binned: bool
    notes: list[str]


def _qlp_columns(sector: int, qlp_flux: str) -> tuple[str, str]:
    """(flux column, flux_err column) for a QLP product of ``sector``."""
    det = "det_flux" if sector >= QLP_DET_FROM_SECTOR else "kspsap_flux"
    err = det + "_err"
    if qlp_flux == "sap":
        return "sap_flux", err          # QLP provides no SAP error column
    if qlp_flux in ("kspsap", "det", "detrended"):
        return det, err
    raise ValueError(f"unknown qlp_flux {qlp_flux!r} (use 'sap' or 'kspsap')")


def _column(lc: lk.LightCurve, name: str):
    """Case-insensitive column lookup; returns the column or None."""
    for col in lc.colnames:
        if col.lower() == name.lower():
            return lc[col]
    return None


def select_flux_column(
    lc: lk.LightCurve,
    *,
    qlp_flux: str = "sap",
    qlp_low_precision_mask: bool = True,
) -> tuple[lk.LightCurve, ProductPrep] | tuple[None, ProductPrep]:
    """Rebuild one product on the author-appropriate flux column and quality.

    Returns ``(lc, prep)``; ``lc`` is None when the author is not a survey
    author or the product carries no usable flux.
    """
    author = (_get_author(lc) or "unknown").upper()
    unit = _get_unit_number(lc, "TESS")
    n_in = len(lc)
    notes: list[str] = []
    prep = ProductPrep(
        unit=unit, author=author, flux_column="flux", flux_err_column="flux_err",
        n_cadences_in=n_in, n_after_quality=n_in, n_after_trim=n_in, n_after_bin=n_in,
        cadence_s_native=_estimate_cadence_s(lc), cadence_s_out=None, binned=False,
        notes=notes,
    )
    if author not in SURVEY_AUTHORS:
        notes.append(f"author {author} is not a survey author; product dropped")
        return None, prep

    flux_col = "flux"
    err_col: Optional[str] = "flux_err"
    keep = np.ones(n_in, dtype=bool)

    if author == "QLP":
        sector = int(lc.meta.get("SECTOR", 0) or 0)
        want_flux, want_err = _qlp_columns(sector, qlp_flux)
        if _column(lc, want_flux) is not None:
            flux_col = want_flux
        else:
            notes.append(f"QLP column {want_flux} absent; using reader default 'flux'")
        if _column(lc, want_err) is not None:
            err_col = want_err
        else:
            notes.append(f"QLP error column {want_err} absent; using reader default 'flux_err'")
        if qlp_low_precision_mask:
            q = _column(lc, "quality")
            if q is not None:
                qv = np.asarray(getattr(q, "value", q))
                qv = np.nan_to_num(qv.astype(float), nan=0.0).astype(np.int64)
                bit = (QLP_LOW_PRECISION_BIT_S56_PLUS if sector >= QLP_DET_FROM_SECTOR
                       else QLP_LOW_PRECISION_BIT_S1_55)
                keep = (qv & bit) == 0
                notes.append(
                    f"QLP low-precision bit {bit} removed {int((~keep).sum())} of {n_in} cadences"
                )
            else:
                notes.append("QLP product has no quality column; low-precision mask skipped")
    else:
        # SPOC / TESS-SPOC: lightkurve's default is pdcsap_flux; state it.
        origin = str(lc.meta.get("FLUX_ORIGIN", "") or "").lower()
        if origin and origin != "pdcsap_flux":
            pdc = _column(lc, "pdcsap_flux")
            if pdc is not None:
                flux_col = "pdcsap_flux"
                err_col = "pdcsap_flux_err" if _column(lc, "pdcsap_flux_err") is not None else "flux_err"
                notes.append(f"reader loaded {origin}; switched to pdcsap_flux")
        else:
            flux_col = "pdcsap_flux" if origin == "pdcsap_flux" else "flux"

    flux = _column(lc, flux_col)
    if flux is None:
        flux = lc.flux
        flux_col = "flux"
    err = _column(lc, err_col) if err_col else None
    if err is None:
        err = lc.flux_err
        err_col = "flux_err" if lc.flux_err is not None else None

    fv = np.asarray(getattr(flux, "value", flux), dtype=float)
    if np.isfinite(fv[keep]).sum() < 10:
        notes.append("fewer than 10 finite cadences after quality; product dropped")
        prep.flux_column = flux_col
        prep.flux_err_column = err_col
        prep.n_after_quality = int(keep.sum())
        return None, prep

    # Usable errors are required downstream (the inverse-variance binner
    # silently returns the UNBINNED curve without them, which is how a
    # 200-second QLP sector with an all-NaN det_flux_err column once reached
    # the flatten next to 30-minute sectors). Fill missing or non-positive
    # errors with the robust local scatter of the flux, in the flux's units.
    ev = (np.asarray(getattr(err, "value", err), dtype=float).copy()
          if err is not None else np.full(fv.shape, np.nan))
    bad = ~np.isfinite(ev) | (ev <= 0)
    if bad.any():
        scatter = _local_scatter(fv[keep])
        if not np.isfinite(scatter) or scatter <= 0:
            scatter = float(np.nanstd(fv[keep])) or 1e-3
        ev[bad] = scatter
        notes.append(
            f"{int(bad.sum())} of {n_in} error values missing or non-positive; filled with the "
            f"local point-to-point scatter ({scatter:.3g})"
        )
        err_col = (err_col or "none") + "+local_scatter"
    flux_unit = getattr(flux, "unit", None)
    err_q = ev[keep] * flux_unit if flux_unit is not None else ev[keep]

    new = lk.LightCurve(time=lc.time[keep], flux=flux[keep], flux_err=err_q)
    new.meta.update(lc.meta)
    new.meta["TESSHUNTER_FLUX_COLUMN"] = flux_col
    prep.flux_column = flux_col
    prep.flux_err_column = err_col
    prep.n_after_quality = len(new)
    prep.n_after_trim = len(new)
    prep.n_after_bin = len(new)
    return new, prep


def trim_segment_edges(
    lc: lk.LightCurve,
    trim_minutes: float,
    break_tolerance: int = preprocessing.SEGMENT_BREAK_TOLERANCE,
    min_segment_minutes: Optional[float] = None,
    edge_gap_days: float = 0.5,
) -> tuple[lk.LightCurve, int]:
    """Drop the first and last ``trim_minutes`` of a product's data runs, but
    only at edges that border a real observing gap.

    Scattered-light ramps live at the start and end of an orbit (the
    product's first and last cadence, and either side of any gap longer than
    ``edge_gap_days``). A short hole cut by the quality mask inside an orbit
    has no such ramp, so trimming there would only discard data: measured on
    40 stars, trimming at every segment split cost 4.3% of all cadences, much
    of it around quality-mask holes. Runs shorter than ``min_segment_minutes``
    (default 3 x trim) that sit between two real gaps are removed whole.

    Returns ``(trimmed_lc, n_removed)``. ``trim_minutes <= 0`` is a no-op.
    """
    if trim_minutes <= 0 or len(lc) == 0:
        return lc, 0
    time = np.asarray(lc.time.value, dtype=float)
    trim_d = trim_minutes / 1440.0
    min_seg_d = (min_segment_minutes / 1440.0) if min_segment_minutes is not None else 3.0 * trim_d
    # Runs bounded by REAL gaps (longer than edge_gap_days) or the product ends.
    cut = np.flatnonzero(np.diff(time) > edge_gap_days) + 1
    starts = np.concatenate(([0], cut))
    stops = np.concatenate((cut, [time.size]))
    keep = np.zeros(time.size, dtype=bool)
    for start, stop in zip(starts, stops):
        seg = time[start:stop]
        if seg.size == 0:
            continue
        span = seg[-1] - seg[0]
        if span < min_seg_d:
            continue
        inner = (seg - seg[0] >= trim_d) & (seg[-1] - seg >= trim_d)
        keep[start:stop] = inner
    n_removed = int((~keep).sum())
    return lc[keep], n_removed


def bin_to_cadence(
    lc: lk.LightCurve,
    target_cadence_minutes: float,
    min_ratio: float = 1.5,
) -> tuple[lk.LightCurve, bool]:
    """Bin a product to ``target_cadence_minutes`` when its cadence is finer.

    Products whose native cadence is already within ``min_ratio`` of the
    target (e.g. 30-minute FFIs against a 30-minute target) are returned
    unchanged so their timestamps are not re-gridded.
    """
    cad_s = _estimate_cadence_s(lc)
    if cad_s is None or cad_s <= 0:
        return lc, False
    if target_cadence_minutes * 60.0 / cad_s < min_ratio:
        return lc, False
    binned = preprocessing.bin_lightcurve(lc, bin_minutes=target_cadence_minutes)
    if len(binned) == len(lc):          # bin_lightcurve refused (too few points)
        return lc, False
    return binned, True


def prepare_products(
    lcc: lk.LightCurveCollection,
    *,
    qlp_flux: str = "sap",
    qlp_low_precision_mask: bool = True,
    edge_trim_minutes: float = 0.0,
    target_cadence_minutes: Optional[float] = 30.0,
    max_units: Optional[int] = None,
) -> tuple[list[lk.LightCurve], list[ProductPrep]]:
    """Dedupe, then select flux/quality, trim edges and bin every product.

    Returns the prepared light curves (ready for
    :func:`tesshunter.download.stitch_collection` with ``dedupe=False``) and
    one :class:`ProductPrep` per input product, including the dropped ones.
    """
    kept = dedupe_collection(lcc, mission="TESS", max_units=max_units)
    prepared: list[lk.LightCurve] = []
    preps: list[ProductPrep] = []
    for lc in kept:
        new, prep = select_flux_column(
            lc, qlp_flux=qlp_flux, qlp_low_precision_mask=qlp_low_precision_mask,
        )
        preps.append(prep)
        if new is None:
            continue
        if edge_trim_minutes > 0:
            new, n_trim = trim_segment_edges(new, edge_trim_minutes)
            prep.n_after_trim = len(new)
            if n_trim:
                prep.notes.append(f"edge trim {edge_trim_minutes:g} min removed {n_trim} cadences")
            if len(new) < 10:
                prep.notes.append("fewer than 10 cadences after edge trim; product dropped")
                continue
        if target_cadence_minutes:
            new, did_bin = bin_to_cadence(new, target_cadence_minutes)
            prep.binned = did_bin
            cad_out = _estimate_cadence_s(new)
            if cad_out is not None and target_cadence_minutes * 60.0 / cad_out >= 1.5:
                # Binning was required and did not happen: never let a finer
                # cadence into the stitch (the flatten window is in cadences).
                prep.notes.append(
                    f"cadence {cad_out:.0f} s could not be binned to {target_cadence_minutes:g} min; "
                    "product dropped"
                )
                continue
        prep.n_after_bin = len(new)
        prep.cadence_s_out = _estimate_cadence_s(new)
        prepared.append(new)
    return prepared, preps


def stitch_prepared(
    prepared: list[lk.LightCurve],
    preps: list[ProductPrep],
) -> lk.LightCurve:
    """Stitch prepared products; attach the ingestion record to ``meta``.

    Raises ``ValueError`` when the products' cadences differ by more than a
    factor 1.5: a mixed-cadence stitch makes the flatten's cadence-count
    window wrong for part of the curve and splits the coarser part into
    single-cadence segments that are median-divided to exactly 1.0.
    """
    cads = [c for c in (_estimate_cadence_s(p) for p in prepared) if c is not None and c > 0]
    if len(cads) >= 2 and max(cads) / min(cads) > 1.5:
        raise ValueError(
            f"refusing to stitch products of inconsistent cadence: {sorted(round(c) for c in cads)} s"
        )
    lcc = lk.LightCurveCollection(prepared)
    stitched = stitch_collection(lcc, dedupe=False, max_units=None, mission="TESS")
    stitched.meta["TESSHUNTER_INGEST"] = [asdict(p) for p in preps]
    return stitched
