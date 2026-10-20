"""Nearby-star contamination check via TIC cone search.

Physics
───────
For a neighbour to mimic the observed transit depth via dilution, its light
must actually reach the target's photometric aperture.  The photometric
aperture is not a point: it spans roughly 1.5–2.5 px depending on target
brightness, so a neighbour *inside* the aperture contributes essentially all
of its flux.  We estimate the aperture radius from the target Tmag (linear
ramp, see :func:`estimate_aperture_radius_px`) and evaluate the Gaussian PRF
at the distance *beyond the aperture edge*.  The PRF is modelled with a
Gaussian of σ = 1.5 px (≈ 31 arcsec), a conservatively *broad* choice that
errs on the side of flagging more rather than less.

For each neighbour the leakage-corrected undiluted depth is:

    depth_true = depth_obs × (1 + 1 / (flux_ratio × leakage_fraction))

where  flux_ratio = 10^{−0.4 × ΔTmag}
and    leakage_fraction = exp(−0.5 × (max(0, sep_px − r_aperture_px) / σ_px)²)

If depth_true > 1000 ppt (> 100 % of the star's light) the neighbour is
*physically ruled out* — it cannot produce the signal regardless of eclipse
depth.  We report it as checked-and-cleared, not as a flag.  Neighbours
within ``r_aperture + 1 px`` are NEVER ruled out: aperture-placement
uncertainty means their light genuinely enters the photometry.

Risk tiers (for genuinely viable contaminants)
──────────────────────────────────────────────
  HIGH   sep < 3 px  AND  leakage-corrected EB-compatible depth
  MEDIUM sep 3–6 px  AND  leakage-corrected EB-compatible depth
  INFO   sep > 6 px  OR   depth < EB threshold after leakage correction

Verdict impact
──────────────
  HIGH   → added to high_risk_flags  (counts toward ambiguous / FP verdict)
  MEDIUM → added to medium_flags only
  INFO   → printed, no verdict impact
  RULED_OUT → printed as "checked and cleared"

A contamination flag alone (without a centroid offset) should therefore
produce at most "ambiguous / manual vetting required", not "likely FP".
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_SEARCH_RADIUS_ARCSEC = 126.0   # 6 × TESS pixel = 2 aperture radii
TESS_PIXEL_SCALE_ARCSEC      = 21.0
PRF_SIGMA_PX                 = 1.5    # Gaussian σ; conservative (broad) PRF model
EB_DEPTH_THRESHOLD_PPT       = 100.0  # > 10 % undiluted depth = EB-compatible
IMPOSSIBLE_DEPTH_PPT         = 1_000.0  # > 100 % = physically impossible
MAX_DELTA_TMAG               = 8.0    # ignore stars fainter than this (< 0.07 % flux)

# Separation thresholds (pixels) for risk tiering
SEP_HIGH_RISK_PX   = 3.0   # inside / on edge of typical TESS aperture
SEP_MEDIUM_RISK_PX = 6.0   # PRF wings still potentially significant

# ── Aperture model (V4) ───────────────────────────────────────────────────────
# The SPOC photometric aperture grows with target brightness.  We approximate
# its radius with a linear ramp in Tmag: 2.5 px for Tmag ≤ 6, 1.5 px for
# Tmag ≥ 12, linear in between (brighter target → bigger aperture).
APERTURE_RADIUS_BRIGHT_PX = 2.5
APERTURE_RADIUS_FAINT_PX  = 1.5
APERTURE_TMAG_BRIGHT      = 6.0
APERTURE_TMAG_FAINT       = 12.0
APERTURE_MARGIN_PX        = 1.0   # never rule out within r_aperture + this margin


def estimate_aperture_radius_px(tmag: float) -> float:
    """Approximate photometric-aperture radius in pixels from target Tmag.

    Linear ramp: ``APERTURE_RADIUS_BRIGHT_PX`` (2.5 px) for
    Tmag ≤ ``APERTURE_TMAG_BRIGHT`` (6), ``APERTURE_RADIUS_FAINT_PX`` (1.5 px)
    for Tmag ≥ ``APERTURE_TMAG_FAINT`` (12), interpolated in between.  This is
    a deliberately simple model of the SPOC optimal-aperture size, which
    grows for brighter (more saturated / broader-PSF) targets.
    """
    if not np.isfinite(tmag):
        return APERTURE_RADIUS_FAINT_PX
    frac = np.clip(
        (tmag - APERTURE_TMAG_BRIGHT) / (APERTURE_TMAG_FAINT - APERTURE_TMAG_BRIGHT),
        0.0, 1.0,
    )
    return float(
        APERTURE_RADIUS_BRIGHT_PX
        - frac * (APERTURE_RADIUS_BRIGHT_PX - APERTURE_RADIUS_FAINT_PX)
    )


# ── PRF leakage model ─────────────────────────────────────────────────────────

def _prf_leakage(sep_arcsec: float, pixel_scale: float = TESS_PIXEL_SCALE_ARCSEC,
                 sigma_px: float = PRF_SIGMA_PX,
                 r_aperture_px: float = 0.0) -> float:
    """Fraction of a neighbour's total flux that enters the on-target aperture.

    Uses a Gaussian PRF model evaluated at the distance beyond the aperture
    edge, ``max(0, sep_px − r_aperture_px)`` — a neighbour inside the aperture
    leaks 100 % of its flux.  σ = 1.5 px is conservatively broad for TESS, so
    we over-estimate leakage slightly (safer than under-estimating it).
    """
    sep_px = sep_arcsec / pixel_scale
    eff_sep_px = max(0.0, sep_px - r_aperture_px)
    return float(np.exp(-0.5 * (eff_sep_px / sigma_px) ** 2))


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class NeighbourStar:
    """One nearby star evaluated by the contamination check."""
    tic_id:                    Optional[int]
    separation_arcsec:         float
    separation_px:             float
    tmag:                      float
    delta_tmag:                float          # > 0 → neighbour is fainter
    flux_ratio:                float          # F_neighbour / F_target (total)
    leakage_fraction:          float          # fraction entering aperture
    effective_flux_in_aperture: float         # flux_ratio × leakage_fraction
    raw_undiluted_depth_ppt:   float          # depth ignoring PRF (old formula)
    leakage_corrected_depth_ppt: float        # physically correct estimate
    risk_level:                str            # "HIGH" | "MEDIUM" | "INFO" | "RULED_OUT"
    is_viable_contaminant:     bool           # leakage-corrected depth < IMPOSSIBLE


@dataclass
class ContaminationResult:
    """Output of :func:`run_contamination_check`."""
    available:                bool  = False
    search_radius_arcsec:     float = DEFAULT_SEARCH_RADIUS_ARCSEC
    aperture_radius_px:       float = 0.0   # estimated photometric aperture radius
    n_neighbours_checked:     int   = 0
    n_ruled_out:              int   = 0     # physically impossible at that separation
    flagged:                  bool  = False  # True only for HIGH or MEDIUM risk
    high_risk_neighbours:     list[NeighbourStar] = field(default_factory=list)
    medium_risk_neighbours:   list[NeighbourStar] = field(default_factory=list)
    info_neighbours:          list[NeighbourStar] = field(default_factory=list)
    ruled_out_neighbours:     list[NeighbourStar] = field(default_factory=list)
    all_neighbours:           list[NeighbourStar] = field(default_factory=list)
    note:                     str   = ""


# ── Per-neighbour classification (pure, network-free) ─────────────────────────

def classify_neighbour(
    sep_arcsec: float,
    tmag_neighbour: float,
    target_tmag: float,
    depth_ppt: float,
    pixel_scale_arcsec: float = TESS_PIXEL_SCALE_ARCSEC,
    aperture_radius_px: Optional[float] = None,
    tic_id: Optional[int] = None,
) -> NeighbourStar:
    """Evaluate one neighbour star and assign a contamination risk tier.

    Pure function (no network) so the tiering logic is directly testable.

    Parameters
    ----------
    sep_arcsec:
        Separation between neighbour and target in arcseconds.
    tmag_neighbour, target_tmag:
        TESS magnitudes of the neighbour and the target.
    depth_ppt:
        Observed transit depth in parts per thousand.
    pixel_scale_arcsec:
        Pixel scale in arcsec / pixel.
    aperture_radius_px:
        Photometric aperture radius in pixels; ``None`` derives it from the
        target Tmag via :func:`estimate_aperture_radius_px`.
    tic_id:
        Optional TIC ID recorded on the result.

    Returns
    -------
    :class:`NeighbourStar`
        Neighbours within ``aperture_radius + APERTURE_MARGIN_PX`` are never
        assigned ``RULED_OUT`` (V4) — their light genuinely enters the
        aperture, so at most they are reported as ``INFO``.
    """
    r_ap = (
        estimate_aperture_radius_px(target_tmag)
        if aperture_radius_px is None else float(aperture_radius_px)
    )
    delta_tmag = tmag_neighbour - target_tmag   # positive → neighbour is fainter
    flux_ratio = 10.0 ** (-0.4 * delta_tmag)

    sep_px   = sep_arcsec / pixel_scale_arcsec
    leakage  = _prf_leakage(sep_arcsec, pixel_scale_arcsec, PRF_SIGMA_PX,
                            r_aperture_px=r_ap)
    eff_flux = flux_ratio * leakage   # effective flux ratio in aperture

    # ── Undiluted depths ──────────────────────────────────────────────────────
    # Raw (old formula — ignores PRF; over-estimates contamination risk)
    raw_depth = depth_ppt * (1.0 + 1.0 / flux_ratio) if flux_ratio > 0 else np.inf

    # Leakage-corrected (physically correct)
    if eff_flux > 1e-12:
        corrected_depth = depth_ppt * (1.0 + 1.0 / eff_flux)
    else:
        corrected_depth = np.inf   # essentially zero leakage

    # ── Risk tier ─────────────────────────────────────────────────────────────
    in_aperture = sep_px < (r_ap + APERTURE_MARGIN_PX)
    if corrected_depth >= IMPOSSIBLE_DEPTH_PPT:
        if in_aperture:
            # V4: never RULED_OUT inside (or within 1 px of) the aperture —
            # the star's light demonstrably enters the photometry.
            risk, viable = "INFO", False
        else:
            risk, viable = "RULED_OUT", False
    elif corrected_depth >= EB_DEPTH_THRESHOLD_PPT:
        # Viable contaminant — tier by separation
        viable = True
        if sep_px < SEP_HIGH_RISK_PX:
            risk = "HIGH"
        elif sep_px < SEP_MEDIUM_RISK_PX:
            risk = "MEDIUM"
        else:
            risk = "INFO"   # distant but mathematically non-zero
    else:
        # Leakage-corrected depth is sub-EB even if the star is 100% eclipsed
        risk, viable = "INFO", False

    return NeighbourStar(
        tic_id                     = tic_id,
        separation_arcsec          = sep_arcsec,
        separation_px              = sep_px,
        tmag                       = tmag_neighbour,
        delta_tmag                 = delta_tmag,
        flux_ratio                 = flux_ratio,
        leakage_fraction           = leakage,
        effective_flux_in_aperture = eff_flux,
        raw_undiluted_depth_ppt    = float(raw_depth),
        leakage_corrected_depth_ppt = float(corrected_depth),
        risk_level                 = risk,
        is_viable_contaminant      = viable,
    )


# ── Public function ───────────────────────────────────────────────────────────

def run_contamination_check(
    ra: float,
    dec: float,
    target_tmag: float,
    depth_ppt: float,
    search_radius_arcsec: float = DEFAULT_SEARCH_RADIUS_ARCSEC,
    pixel_scale_arcsec: float = TESS_PIXEL_SCALE_ARCSEC,
    aperture_radius_px: Optional[float] = None,
) -> ContaminationResult:
    """Query the TIC for nearby stars and assess contamination risk.

    Parameters
    ----------
    ra, dec:
        Target coordinates in decimal degrees (J2000).
    target_tmag:
        TESS magnitude of the target star.
    depth_ppt:
        Observed transit depth in parts per thousand.
    search_radius_arcsec:
        Cone-search radius in arcseconds (default 126 arcsec ≈ 6 TESS px).
    pixel_scale_arcsec:
        Pixel scale of the telescope in arcsec / pixel (default TESS = 21).
    aperture_radius_px:
        Photometric aperture radius in pixels; ``None`` (default) estimates
        it from the target Tmag via :func:`estimate_aperture_radius_px`.

    Returns
    -------
    :class:`ContaminationResult`
        Never raises; sets ``available=False`` on any network failure.
    """
    r_ap = (
        estimate_aperture_radius_px(target_tmag)
        if aperture_radius_px is None else float(aperture_radius_px)
    )
    try:
        from astroquery.mast import Catalogs

        logger.info(
            "Contamination: cone search %.5f %.5f r=%.0f arcsec",
            ra, dec, search_radius_arcsec,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tbl = Catalogs.query_region(
                f"{ra} {dec}",
                radius=search_radius_arcsec / 3600.0,
                catalog="TIC",
            )

    except Exception as exc:
        logger.warning("Contamination: TIC cone search failed: %s", exc)
        return ContaminationResult(
            available=False,
            search_radius_arcsec=search_radius_arcsec,
            aperture_radius_px=r_ap,
            note=f"TIC cone search failed: {exc}",
        )

    if tbl is None or len(tbl) == 0:
        return ContaminationResult(
            available=True,
            search_radius_arcsec=search_radius_arcsec,
            aperture_radius_px=r_ap,
            note=(
                f"No stars found in TIC within {search_radius_arcsec:.0f} arcsec "
                "— contamination check inconclusive."
            ),
        )

    neighbours: list[NeighbourStar] = []

    for row in tbl:
        # ── Tmag ──────────────────────────────────────────────────────────────
        try:
            tmag_n = float(row["Tmag"])
            if not np.isfinite(tmag_n):
                continue
        except (TypeError, ValueError, KeyError):
            continue

        # ── Separation ────────────────────────────────────────────────────────
        try:
            sep_arcsec = float(row["dstArcSec"])
        except (TypeError, ValueError, KeyError):
            sep_arcsec = 0.0

        if sep_arcsec < 2.0:
            continue   # this is the target itself

        # ── Brightness cut ────────────────────────────────────────────────────
        delta_tmag = tmag_n - target_tmag   # positive → neighbour is fainter
        if delta_tmag > MAX_DELTA_TMAG:
            continue   # contributes < 0.07 % of target flux — negligible

        # ── TIC ID ────────────────────────────────────────────────────────────
        try:
            tic_n = int(row["ID"])
        except (TypeError, ValueError, KeyError):
            tic_n = None

        # ── Aperture-aware PRF evaluation and risk tiering (V4) ───────────────
        neighbours.append(classify_neighbour(
            sep_arcsec         = sep_arcsec,
            tmag_neighbour     = tmag_n,
            target_tmag        = target_tmag,
            depth_ppt          = depth_ppt,
            pixel_scale_arcsec = pixel_scale_arcsec,
            aperture_radius_px = r_ap,
            tic_id             = tic_n,
        ))

    neighbours.sort(key=lambda s: s.separation_arcsec)

    high_risk   = [s for s in neighbours if s.risk_level == "HIGH"]
    medium_risk = [s for s in neighbours if s.risk_level == "MEDIUM"]
    info        = [s for s in neighbours if s.risk_level == "INFO"]
    ruled_out   = [s for s in neighbours if s.risk_level == "RULED_OUT"]
    flagged     = len(high_risk) > 0 or len(medium_risk) > 0

    # ── Build summary note ────────────────────────────────────────────────────
    lines = []
    n_total = len(neighbours)
    n_ro    = len(ruled_out)

    if n_total == 0:
        lines.append(
            f"No stars brighter than ΔTmag < {MAX_DELTA_TMAG} found within "
            f"{search_radius_arcsec:.0f} arcsec — contamination unlikely."
        )
    else:
        lines.append(
            f"{n_total} neighbour(s) checked within {search_radius_arcsec:.0f} arcsec "
            f"(σ_PRF = {PRF_SIGMA_PX} px = {PRF_SIGMA_PX * pixel_scale_arcsec:.0f} arcsec; "
            f"aperture radius ≈ {r_ap:.1f} px from Tmag {target_tmag:.1f})."
        )
        if n_ro:
            lines.append(
                f"  {n_ro} star(s) ruled out — insufficient PRF leakage into the "
                f"aperture to produce the {depth_ppt:.2f} ppt signal at their separation."
            )
        for s in ruled_out[:3]:
            lines.append(
                f"    TIC {s.tic_id}  sep={s.separation_arcsec:.1f}\" "
                f"({s.separation_px:.1f} px)  ΔTmag={s.delta_tmag:+.1f}  "
                f"leakage={s.leakage_fraction*100:.2g}%  "
                f"corrected depth={s.leakage_corrected_depth_ppt:.0f} ppt "
                f"(> {IMPOSSIBLE_DEPTH_PPT:.0f} ppt threshold → not viable)"
            )

        for label, group, colour in [
            ("HIGH-RISK",   high_risk,   "FLAGGED"),
            ("MEDIUM-RISK", medium_risk, "FLAGGED"),
            ("INFO",        info,        "noted"),
        ]:
            if group:
                lines.append(
                    f"  {len(group)} {label} neighbour(s) [{colour}]:"
                )
                for s in group[:5]:
                    lines.append(
                        f"    TIC {s.tic_id}  sep={s.separation_arcsec:.1f}\" "
                        f"({s.separation_px:.1f} px)  "
                        f"Tmag={s.tmag:.1f} (Δ{s.delta_tmag:+.1f})  "
                        f"leakage={s.leakage_fraction*100:.2g}%  "
                        f"corrected undiluted depth = {s.leakage_corrected_depth_ppt:.0f} ppt"
                    )

    if not flagged and n_total > 0:
        lines.append(
            f"No viable contaminants found after PRF-leakage correction — "
            "contamination unlikely from known TIC sources."
        )

    note = "\n".join(lines)

    logger.info(
        "Contamination: %d checked, %d ruled_out, %d high, %d medium, %d info",
        n_total, n_ro, len(high_risk), len(medium_risk), len(info),
    )
    return ContaminationResult(
        available               = True,
        search_radius_arcsec    = search_radius_arcsec,
        aperture_radius_px      = r_ap,
        n_neighbours_checked    = n_total,
        n_ruled_out             = n_ro,
        flagged                 = flagged,
        high_risk_neighbours    = high_risk,
        medium_risk_neighbours  = medium_risk,
        info_neighbours         = info,
        ruled_out_neighbours    = ruled_out,
        all_neighbours          = neighbours,
        note                    = note,
    )
