"""Preliminary false-positive vetting checks.

Every candidate signal is assumed to be a false positive until evidence
accumulates otherwise. These checks are necessary but NOT sufficient for
confirmation — follow-up observations are required.

Verdict tiers (from most to least confident)
─────────────────────────────────────────────
  likely known planet / TOI         — target is in the TOI or confirmed-planet catalog
  promising planet candidate         — all checks clean, catalog confirms no prior flag
  unverified candidate               — checks clean but catalog was unavailable
  ambiguous / manual vetting required — one or more soft risk flags
  likely false positive              — hard veto triggered (depth, SNR, or joint EB evidence)

Hard vetoes (any one → "likely false positive"):
  • depth veto — radius-aware when the stellar radius is known: implied
    companion radius > 2.5 R_Jup (stellar-companion regime).  When the radius
    is unknown the legacy absolute threshold applies: depth > 100 ppt.
  • SNR > 1 000      (four-digit SNR is unphysical; stellar activity or systematic)
  • secondary eclipse + odd/even asymmetry both detected (two independent EB markers)

High-risk soft flags (any two *independent* → FP; any one → ambiguous;
the depth- and SNR-based flags share the same amplitude cause and therefore
count as ONE flag when both are present):
  • large depth — radius-aware when the stellar radius is known
    (implied companion radius 1.5–2.5 R_Jup); otherwise depth 30–100 ppt
  • SNR 100–1 000               (very elevated — stellar activity territory)
  • period near stellar-rotation harmonic
  • secondary eclipse detected  (when not paired with odd/even flag). With a
    transit fit the secondary is compared with the deepest secondary an
    irradiated planet could show at the FITTED a/R* (dayside thermal emission
    plus reflected light, TESS band); above twice that bound it is a stellar
    eclipse and stacks, within it the flag is raised but does not stack.
  • significant odd/even depth mismatch (when not paired with secondary
    flag); the median-based test OR the transit-fit template test (4 sigma
    against the event-to-event scatter, 25% of the mean, 3 events per parity)
  • V-shaped transit (t_flat/t_total < 0.15 — grazing-EB signature)
  • a/R* inconsistent with the star: the density the transit shape implies
    differs from the catalog density by more than a factor 3 and the profile
    delta chi2 of holding a/R* at the catalog value exceeds 9 (diluted
    eclipse, grazing stellar companion, blend)

Medium flags (two or more → ambiguous; one → noted but not verdict-changing):
  • duration/period ratio high
  • single sector only
  • per-unit transit depths disagree by > 3σ across observing units
  • V-shape tendency (t_flat/t_total 0.15–0.3)
  • catalog lookup failed
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

import lightkurve as lk
import numpy as np

from .utils import phase_fold

logger = logging.getLogger(__name__)

# ── Verdict labels ────────────────────────────────────────────────────────────
VERDICT_KNOWN     = "likely known planet / TOI"
VERDICT_PROMISING = "promising planet candidate"
VERDICT_UNVERIFIED = "unverified candidate"
VERDICT_AMBIGUOUS = "ambiguous / manual vetting required"
VERDICT_FP        = "likely false positive"

# ── Hard-veto thresholds ──────────────────────────────────────────────────────
DEPTH_HARD_VETO_PPT = 100.0    # > 10 % flux drop → impossible for a planet
SNR_HARD_VETO       = 1_000.0  # 4-digit+ SNR → systematic or stellar variability

# ── Soft / high-risk thresholds ───────────────────────────────────────────────
DEPTH_HIGH_RISK_PPT = 30.0     # 3–10 % depth → EB / background-eclipser territory
SNR_HIGH_RISK       = 100.0    # > 100 → elevated; worth flagging

# ── Radius-aware depth thresholds (used when the stellar radius is known) ─────
RJUP_IN_REARTH        = 11.209  # 1 R_Jup in Earth radii
RADIUS_HARD_VETO_RJUP = 2.5     # implied companion radius above this → stellar regime
RADIUS_HIGH_RISK_RJUP = 1.5     # 1.5–2.5 R_Jup → inflated-planet / brown-dwarf territory

#: LEGACY fallback (used only when no transit fit is available): a secondary
#: eclipse shallower than this FRACTION OF THE PRIMARY, on a companion already
#: measured to be planet-sized, is treated as dayside emission rather than a
#: stellar eclipse. The period-aware test below replaces it whenever the fit
#: supplies a/R* and Rp/R*.
PLANETARY_SECONDARY_MAX_RATIO = 0.10

#: Period-aware secondary test (prompt 3, part C1). The deepest secondary an
#: irradiated planet can show is its dayside thermal emission at zero heat
#: redistribution and zero Bond albedo plus reflected light at geometric
#: albedo 1, both evaluated at the FITTED a/R* and Rp/R* in the TESS band.
#: A measured secondary deeper than SECONDARY_BOUND_MARGIN times that bound
#: cannot be a planet's and is a stellar eclipse.
SECONDARY_BOUND_MARGIN = 2.0
SECONDARY_REDISTRIBUTION_F = 2.0 / 3.0     # dayside-only (maximum) T_day = Teff sqrt(R/a) f^1/4
SECONDARY_MAX_GEOMETRIC_ALBEDO = 1.0
TESS_BAND_NM = (600.0, 1000.0)

#: a/R* consistency (from tesshunter.transit_fit): the density implied by the
#: transit shape against the catalog density; flagged as high risk.
A_RS_INCONSISTENT_NOTE = (
    "transit shape implies a stellar density inconsistent with the catalog star"
)

#: The transit-fit odd/even comparison replaces the median-based one when
#: both parities have at least this many events (matches
#: transit_fit.ODD_EVEN_MIN_EVENTS).
_ODD_EVEN_MIN_EVENTS_FOR_SUPERSEDE = 3

# ── V-shape (trapezoid-fit) thresholds ────────────────────────────────────────
V_SHAPE_MEDIUM_RATIO = 0.30    # t_flat/t_total below this → medium risk
V_SHAPE_HIGH_RATIO   = 0.15    # below this → high risk (grazing-EB signature)

# ── Robust statistics ─────────────────────────────────────────────────────────
MAD_TO_SIGMA        = 1.4826   # Gaussian MAD → σ conversion factor
RED_NOISE_INFLATION = 2.0      # inflation factor for correlated (red) noise
GAP_SPLIT_DAYS      = 1.0      # time gap that separates observing units
SECTOR_DEPTH_SIGMA  = 3.0      # per-unit depth disagreement threshold (σ)

# ── Rotation-harmonic detection ───────────────────────────────────────────────
ROTATION_HARMONIC_RATIOS = [0.5, 1.0, 2.0, 3.0, 4.0]
ROTATION_HARMONIC_TOL    = 0.03   # fractional tolerance (3 %)

# ── Geometry check ────────────────────────────────────────────────────────────
MAX_DURATION_FRACTION = 0.10   # duration/period; above this is suspect
ODD_EVEN_SIGMA_THRESHOLD = 2.5  # σ difference to flag odd/even mismatch


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class VettingResult:
    """Collected false-positive flags and a summary verdict.

    Flag categories
    ───────────────
    hard_veto_flags  — any entry → VERDICT_FP regardless of other checks
    high_risk_flags  — two or more → VERDICT_FP; one → VERDICT_AMBIGUOUS
    medium_flags     — two or more → VERDICT_AMBIGUOUS; one → noted only
    """

    # ── Signal parameters ─────────────────────────────────────────────────────
    depth_ppt:           float = 0.0
    duration_days:       float = 0.0
    period_days:         float = 0.0
    snr:                 float = 0.0
    n_sectors:           int   = 0
    stellar_radius_rsun: Optional[float] = None
    estimated_radius_rearth: Optional[float] = None

    # ── Individual check outcomes ─────────────────────────────────────────────
    depth_too_deep:            bool  = False   # > DEPTH_HARD_VETO_PPT
    depth_large:               bool  = False   # > DEPTH_HIGH_RISK_PPT (but ≤ hard veto)
    snr_absurd:                bool  = False   # > SNR_HARD_VETO
    snr_high:                  bool  = False   # > SNR_HIGH_RISK (but ≤ hard veto)
    duration_fraction_high:    bool  = False
    odd_even_mismatch:         bool  = False
    secondary_eclipse_detected: bool = False
    #: Secondary shallow enough, on a companion small enough, to be planetary
    #: dayside emission. Does NOT suppress the flag - see
    #: _effective_high_risk_count.
    secondary_is_planetary: bool = False
    single_sector_only:        bool  = False
    sector_depth_mismatch:     bool  = False   # per-unit depths disagree > 3σ
    near_rotation_harmonic:    bool  = False
    rotation_harmonic_ratio:   float = 0.0
    catalog_ok:                bool  = True

    # ── Numeric diagnostics ───────────────────────────────────────────────────
    odd_even_delta_sigma:  float = 0.0
    secondary_depth_ppt:   float = 0.0
    duration_period_frac:  float = 0.0
    implied_radius_rjup:   Optional[float] = None   # implied companion radius
    v_shape_ratio:         Optional[float] = None   # t_flat/t_total from trapezoid fit
    v_shape_flag:          Optional[str]   = None   # 'none' | 'medium' | 'high'

    # ── Transit-fit derived diagnostics (prompt 3) ────────────────────────────
    fit_available:          bool = False
    fit_rp_rs:              Optional[float] = None
    fit_a_rs:               Optional[float] = None
    fit_b:                  Optional[float] = None
    fit_rp_rearth:          Optional[float] = None
    fit_rp_rearth_err:      Optional[float] = None
    fit_duration_days:      Optional[float] = None
    a_rs_star:              Optional[float] = None
    a_rs_ratio:             Optional[float] = None
    density_ratio:          Optional[float] = None
    density_dchi2:          Optional[float] = None
    a_rs_inconsistent:      bool = False
    fit_grazing:            bool = False
    #: deepest secondary an irradiated planet could show at the fitted a/R*
    secondary_planet_bound_ppt: Optional[float] = None
    #: measured secondary exceeds SECONDARY_BOUND_MARGIN x the planet bound
    secondary_is_stellar:   bool = False
    odd_even_fit_sigma:     Optional[float] = None
    odd_even_fit_significant: bool = False
    #: fitted depth over its statistical error; below FIT_MIN_DEPTH_SIGMA the
    #: model does not see the box signal (fit_no_dip)
    fit_depth_sigma:        Optional[float] = None
    fit_no_dip:             bool = False
    #: elevated SNR demoted to a medium flag because the fit confirms a clean dip
    snr_high_demoted:       bool = False

    # ── Flag lists (populated by run_vetting) ─────────────────────────────────
    hard_veto_flags: list[str] = field(default_factory=list)
    high_risk_flags: list[str] = field(default_factory=list)
    medium_flags:    list[str] = field(default_factory=list)

    # ── New-style flag aliases (rendered by reporting via getattr) ────────────
    flags_hard:   list = field(default_factory=list)
    flags_high:   list = field(default_factory=list)
    flags_medium: list = field(default_factory=list)

    # ── Human-readable notes (one per check) ──────────────────────────────────
    notes:   list[str] = field(default_factory=list)
    verdict: str       = VERDICT_AMBIGUOUS

    # TODO: placeholders for future checks
    centroid_shift:         Optional[float] = None   # requires TPF
    contamination_fraction: Optional[float] = None   # requires Gaia DR3 cone search

    def __post_init__(self) -> None:
        # Alias the new-style flag fields to the legacy lists (same objects)
        # so an append through either name stays in sync.
        if not self.flags_hard:
            self.flags_hard = self.hard_veto_flags
        if not self.flags_high:
            self.flags_high = self.high_risk_flags
        if not self.flags_medium:
            self.flags_medium = self.medium_flags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def median_error(
    values: np.ndarray,
    n: int,
    red_noise_factor: float = RED_NOISE_INFLATION,
) -> float:
    """Standard error of a median of ``n`` points, from a robust scatter sample.

    The per-point scatter is estimated as ``1.4826 × MAD`` of ``values``
    (typically the out-of-transit flux or centroid sample); the error on a
    median of ``n`` such points is that scatter divided by ``sqrt(n)``.  The
    result is multiplied by ``red_noise_factor`` (default 2) to account for
    correlated (red) noise, which white-noise statistics underestimate.

    Parameters
    ----------
    values:
        Sample from which the robust per-point scatter (MAD) is estimated.
    n:
        Number of points entering the median whose error is required.
    red_noise_factor:
        Multiplicative inflation for correlated noise.

    Returns
    -------
    float
        ``1.4826 × MAD(values) / sqrt(n) × red_noise_factor``; 0.0 when the
        inputs are degenerate (empty sample or ``n <= 0``).
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0 or n <= 0:
        return 0.0
    mad = float(np.median(np.abs(arr - np.median(arr))))
    return MAD_TO_SIGMA * mad / np.sqrt(n) * red_noise_factor


def implied_companion_radius_rjup(
    depth_ppt: float,
    stellar_radius_rsun: float,
) -> Optional[float]:
    """Implied companion radius in Jupiter radii from depth and stellar radius.

    Uses ``Rp = Rs × sqrt(depth_fraction)`` via
    :func:`tesshunter.utils.estimate_planet_radius`.  Returns ``None`` when
    the inputs are invalid (non-positive depth or radius).
    """
    from .utils import estimate_planet_radius
    r_earth = estimate_planet_radius(depth_ppt / 1000.0, stellar_radius_rsun)
    if r_earth is None:
        return None
    return float(r_earth) / RJUP_IN_REARTH


def _planck_band_ratio(t_planet: float, t_star: float,
                       band_nm: tuple[float, float] = TESS_BAND_NM, n: int = 200) -> float:
    """Ratio of band-integrated Planck intensities B(T_planet) / B(T_star)."""
    if t_planet <= 0 or t_star <= 0:
        return 0.0
    h, c, kb = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    lam = np.linspace(band_nm[0], band_nm[1], n) * 1e-9

    def planck(T):
        x = h * c / (lam * kb * T)
        return 1.0 / np.expm1(np.clip(x, 1e-6, 700.0)) / lam ** 5

    num = np.trapezoid(planck(t_planet), lam)
    den = np.trapezoid(planck(t_star), lam)
    return float(num / den) if den > 0 else 0.0


def planetary_secondary_bound_ppt(
    rp_rs: float,
    a_rs: float,
    teff: float,
    *,
    redistribution_f: float = SECONDARY_REDISTRIBUTION_F,
    albedo: float = SECONDARY_MAX_GEOMETRIC_ALBEDO,
) -> tuple[float, float, float, float]:
    """Deepest secondary an irradiated planet can produce, in ppt.

    Returns (bound_ppt, thermal_ppt, reflected_ppt, t_day_K). Thermal: the
    dayside at ``T_day = Teff sqrt(R*/a) f^(1/4)`` with f = 2/3 (no heat
    redistribution, zero Bond albedo, the hottest possible dayside) radiating
    into the TESS band; reflected: geometric albedo ``albedo`` times
    (Rp/a)^2. Both are upper limits, so their sum is a bound, not a
    prediction.
    """
    if rp_rs <= 0 or a_rs <= 1.0 or teff <= 0:
        return 0.0, 0.0, 0.0, 0.0
    t_day = teff * math.sqrt(1.0 / a_rs) * redistribution_f ** 0.25
    thermal = rp_rs ** 2 * _planck_band_ratio(t_day, teff)
    reflected = albedo * (rp_rs / a_rs) ** 2
    return float((thermal + reflected) * 1000.0), float(thermal * 1000.0), float(reflected * 1000.0), float(t_day)


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

def check_depth(
    depth_ppt: float,
    stellar_radius_rsun: Optional[float] = None,
) -> tuple[bool, bool, str]:
    """Return (hard_veto, high_risk, note).

    When ``stellar_radius_rsun`` is supplied the thresholds are radius-aware:

    hard_veto  → implied companion radius > RADIUS_HARD_VETO_RJUP (2.5 R_Jup)
    high_risk  → implied radius RADIUS_HIGH_RISK_RJUP–RADIUS_HARD_VETO_RJUP

    Without a stellar radius the legacy absolute thresholds apply:

    hard_veto  → depth > DEPTH_HARD_VETO_PPT (impossible for planet)
    high_risk  → depth > DEPTH_HIGH_RISK_PPT (EB / contamination territory)
    """
    if stellar_radius_rsun is not None and stellar_radius_rsun > 0 and depth_ppt > 0:
        r_rjup = implied_companion_radius_rjup(depth_ppt, stellar_radius_rsun)
        if r_rjup is not None:
            if r_rjup > RADIUS_HARD_VETO_RJUP:
                return True, True, (
                    f"HARD VETO — implied companion radius {r_rjup:.2f} R_Jup "
                    f"(depth {depth_ppt:.1f} ppt, R_star = {stellar_radius_rsun:.2f} R_Sun) "
                    f"exceeds {RADIUS_HARD_VETO_RJUP} R_Jup. This is the stellar-companion "
                    "regime — likely eclipsing binary or background eclipser."
                )
            if r_rjup > RADIUS_HIGH_RISK_RJUP:
                return False, True, (
                    f"LARGE COMPANION — implied radius {r_rjup:.2f} R_Jup "
                    f"(depth {depth_ppt:.1f} ppt, R_star = {stellar_radius_rsun:.2f} R_Sun) "
                    f"is in the {RADIUS_HIGH_RISK_RJUP}–{RADIUS_HARD_VETO_RJUP} R_Jup range: "
                    "inflated planet, brown dwarf, or eclipsing binary."
                )
            return False, False, (
                f"Implied companion radius {r_rjup:.2f} R_Jup "
                f"(depth {depth_ppt:.1f} ppt, R_star = {stellar_radius_rsun:.2f} R_Sun) "
                "is within the planet regime."
            )
    if depth_ppt > DEPTH_HARD_VETO_PPT:
        return True, True, (
            f"HARD VETO — depth {depth_ppt:.1f} ppt ({depth_ppt/10:.1f} %) exceeds "
            f"{DEPTH_HARD_VETO_PPT:.0f} ppt. No planet can block this fraction of a "
            "stellar disk. Likely eclipsing binary, background eclipser, or data artifact."
        )
    if depth_ppt > DEPTH_HIGH_RISK_PPT:
        return False, True, (
            f"LARGE DEPTH — {depth_ppt:.1f} ppt ({depth_ppt/10:.1f} %) exceeds "
            f"{DEPTH_HIGH_RISK_PPT:.0f} ppt. Possible eclipsing binary or background "
            "contamination. Only a very large planet or brown dwarf would produce this."
        )
    return False, False, f"Depth {depth_ppt:.1f} ppt is within the planet regime."


def check_snr(snr: float) -> tuple[bool, bool, str]:
    """Return (hard_veto, high_risk, note).

    SNR > SNR_HARD_VETO  → hard veto (unphysical for a transiting planet)
    SNR > SNR_HIGH_RISK  → high-risk flag (stellar activity / systematic territory)
    """
    if snr > SNR_HARD_VETO:
        return True, True, (
            f"HARD VETO — SNR {snr:.0f} exceeds {SNR_HARD_VETO:.0f}. "
            "Four-digit or five-digit BLS SNR is unphysical for a transiting planet. "
            "Likely cause: stellar variability / rotation fitted as transit signal, "
            "or data systematics (scattered light, momentum dumps)."
        )
    if snr > SNR_HIGH_RISK:
        return False, True, (
            f"HIGH SNR — {snr:.0f} exceeds {SNR_HIGH_RISK:.0f}. "
            "Elevated SNR can indicate stellar activity masquerading as a transit. "
            "Inspect the folded light curve carefully."
        )
    return False, False, f"SNR {snr:.1f} is within the expected range for a planet signal."


def check_rotation_harmonic(
    period_days: float,
    rotation_period_days: float,
) -> tuple[bool, float, str]:
    """Flag if the candidate period is near a harmonic of the stellar rotation period.

    Returns (flagged, harmonic_ratio_matched, note).
    """
    for r in ROTATION_HARMONIC_RATIOS:
        expected = rotation_period_days * r
        if abs(period_days - expected) / expected < ROTATION_HARMONIC_TOL:
            return True, r, (
                f"ROTATION HARMONIC — period {period_days:.4f} d is within "
                f"{ROTATION_HARMONIC_TOL*100:.0f} % of {r}× the stellar rotation period "
                f"({rotation_period_days:.3f} d → expected {expected:.4f} d). "
                "Stellar rotation and its harmonics are the most common false positives "
                "for active stars in BLS searches."
            )
    return False, 0.0, (
        f"Period {period_days:.4f} d is not near a harmonic of stellar rotation "
        f"({rotation_period_days:.3f} d)."
    )


def check_duration_fraction(duration_days: float, period_days: float) -> tuple[bool, float, str]:
    """Flag if transit duration is an implausibly large fraction of the period."""
    frac = duration_days / max(period_days, 1e-6)
    if frac > MAX_DURATION_FRACTION:
        return True, frac, (
            f"Duration/period = {frac:.3f} exceeds {MAX_DURATION_FRACTION} — "
            "may indicate a grazing EB, stellar variability, or a systematics artifact."
        )
    return False, frac, f"Duration/period = {frac:.3f} is geometrically acceptable."


def check_odd_even(
    lc: lk.LightCurve,
    period_days: float,
    epoch_btjd: float,
    duration_days: float,
) -> tuple[bool, float, str]:
    """Compare odd vs. even transit depths.

    A significant difference suggests an eclipsing binary (primary + secondary
    at half the apparent period). Returns (flagged, delta_sigma, note).
    """
    time = lc.time.value
    flux = lc.flux.value
    phase = phase_fold(time, period_days, epoch_btjd)
    half_dur = duration_days / period_days / 2.0

    in_transit = np.abs(phase) < half_dur
    n_period   = np.round((time - epoch_btjd) / period_days).astype(int)

    odd_depths, even_depths = [], []
    for idx in np.where(in_transit)[0]:
        n     = n_period[idx]
        depth = 1.0 - flux[idx]
        (odd_depths if n % 2 else even_depths).append(depth)

    if len(odd_depths) < 3 or len(even_depths) < 3:
        return False, 0.0, "Insufficient cadences to compare odd/even depths."

    odd_med  = float(np.median(odd_depths))
    even_med = float(np.median(even_depths))
    se = np.sqrt(
        (np.std(odd_depths) ** 2 / len(odd_depths))
        + (np.std(even_depths) ** 2 / len(even_depths))
    )
    if se < 1e-10:
        return False, 0.0, "Odd/even test: degenerate scatter."

    delta_sigma = abs(odd_med - even_med) / se
    flagged     = delta_sigma > ODD_EVEN_SIGMA_THRESHOLD
    note = (
        f"Odd depth {odd_med*1000:.2f} ppt, even depth {even_med*1000:.2f} ppt, "
        f"delta = {delta_sigma:.1f}σ."
    )
    if flagged:
        note += (
            " FLAGGED — significant odd/even asymmetry. Primary interpretation: "
            "eclipsing binary at half the apparent period. Also consider: BLS period "
            "slightly off, or noisy in-transit cadences in one sector."
        )
    return flagged, float(delta_sigma), note


def check_secondary_eclipse(
    lc: lk.LightCurve,
    period_days: float,
    epoch_btjd: float,
    duration_days: float,
) -> tuple[bool, float, str]:
    """Look for a secondary eclipse near phase 0.5 (half-period offset).

    A secondary eclipse is a strong indicator of an eclipsing binary.
    The measured secondary depth is a *median* of N cadences, so it is
    compared against the error on that median —
    ``1.4826 × MAD(OOT flux) / sqrt(N)`` inflated by a factor of 2 for red
    noise — rather than the per-point scatter (which is ~sqrt(N) too
    insensitive).  Returns (flagged, secondary_depth_ppt, note).
    """
    time  = lc.time.value
    flux  = lc.flux.value
    phase = phase_fold(time, period_days, epoch_btjd)
    half_dur_phase = duration_days / period_days / 2.0

    near_secondary = np.abs(np.abs(phase) - 0.5) < half_dur_phase * 1.5
    out_of_transit  = np.abs(phase) > half_dur_phase * 2.0

    if near_secondary.sum() < 3:
        return False, 0.0, "Insufficient cadences near phase 0.5 to test for secondary eclipse."

    n_sec     = int(near_secondary.sum())
    sec_depth = 1.0 - float(np.median(flux[near_secondary]))
    sigma_med = median_error(flux[out_of_transit], n_sec)
    if sigma_med <= 0:
        return False, 0.0, "Secondary-eclipse test: degenerate out-of-transit scatter."
    threshold = 3.0 * sigma_med

    flagged = sec_depth > threshold
    note = (
        f"Secondary eclipse depth at phase 0.5: {sec_depth*1000:.2f} ppt "
        f"(3σ median-error threshold: {threshold*1000:.2f} ppt over "
        f"{n_sec} cadences, red-noise inflation ×{RED_NOISE_INFLATION:.0f})."
    )
    if flagged:
        note += " FLAGGED — secondary eclipse detected; consistent with eclipsing binary."
    return flagged, float(sec_depth * 1000.0), note


def check_v_shape(
    lc: lk.LightCurve,
    period_days: float,
    epoch_btjd: float,
    duration_days: float,
    n_bins: int = 41,
) -> tuple[Optional[float], str, str]:
    """Fit a trapezoid to the folded transit and flag V-shaped events.

    Grazing eclipsing binaries produce V-shaped (triangular) events with no
    flat bottom, whereas a full planetary transit spends most of the event at
    full depth.  The folded light curve is binned and a trapezoid (total
    duration, flat-bottom duration, depth) is fitted by a grid search over
    shape with the depth solved analytically by linear least squares.

    Parameters
    ----------
    lc:
        Cleaned, normalised light curve.
    period_days, epoch_btjd, duration_days:
        Candidate ephemeris from BLS.
    n_bins:
        Number of phase bins across ±1.5 durations.

    Returns
    -------
    tuple
        ``(t_flat_over_t_total, flag, note)`` where ``flag`` is ``'none'``,
        ``'medium'`` (ratio < V_SHAPE_MEDIUM_RATIO) or ``'high'``
        (ratio < V_SHAPE_HIGH_RATIO).  The ratio is ``None`` when the fit is
        not possible (insufficient cadences or no significant dip).
    """
    if duration_days <= 0 or period_days <= 0:
        return None, "none", "V-shape check skipped — invalid ephemeris."

    try:
        time = np.asarray(lc.time.value, dtype=float)
        flux = np.asarray(lc.flux.value, dtype=float)
    except Exception as exc:
        return None, "none", f"V-shape check skipped — could not read light curve ({exc})."

    finite = np.isfinite(time) & np.isfinite(flux)
    time, flux = time[finite], flux[finite]
    if time.size == 0:
        return None, "none", "V-shape check skipped — empty light curve."

    # ── Fold: time from mid-transit in days ───────────────────────────────────
    phase_days = phase_fold(time, period_days, epoch_btjd) * period_days
    window = 1.5 * duration_days
    sel = np.abs(phase_days) < window
    if sel.sum() < 20:
        return None, "none", (
            f"V-shape check skipped — only {int(sel.sum())} cadences within "
            "±1.5 durations of mid-transit."
        )

    # ── Bin the folded curve (median per bin) ─────────────────────────────────
    x, y    = phase_days[sel], flux[sel]
    edges   = np.linspace(-window, window, n_bins + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    idx     = np.digitize(x, edges) - 1
    bx, by  = [], []
    for b in range(n_bins):
        in_bin = idx == b
        if in_bin.any():
            bx.append(centers[b])
            by.append(float(np.median(y[in_bin])))
    bx, by = np.asarray(bx), np.asarray(by)
    if bx.size < 10:
        return None, "none", f"V-shape check skipped — only {bx.size} populated phase bins."

    # ── Grid search over trapezoid shape; depth by least squares ──────────────
    best_sse, best_ratio, best_depth, best_t_total = np.inf, None, 0.0, 0.0
    for t_total in duration_days * np.linspace(0.5, 1.6, 12):
        half_total = t_total / 2.0
        for ratio in np.linspace(0.0, 0.95, 20):
            half_flat = ratio * half_total
            ax = np.abs(bx)
            w  = np.zeros_like(bx)
            w[ax <= half_flat] = 1.0
            ramp = (ax > half_flat) & (ax < half_total)
            w[ramp] = (half_total - ax[ramp]) / max(half_total - half_flat, 1e-12)
            denom = float(np.sum(w * w))
            if denom <= 0:
                continue
            depth = max(float(np.sum(w * (1.0 - by)) / denom), 0.0)
            sse = float(np.sum((by - (1.0 - depth * w)) ** 2))
            if sse < best_sse:
                best_sse, best_ratio, best_depth, best_t_total = sse, ratio, depth, t_total

    if best_ratio is None or best_depth <= 0:
        return None, "none", "V-shape check inconclusive — no significant dip in the folded curve."

    # ── Require the dip to stand above the binned scatter ─────────────────────
    oot = np.abs(bx) > best_t_total / 2.0
    scatter = 0.0
    if oot.sum() >= 5:
        oot_med = np.median(by[oot])
        scatter = MAD_TO_SIGMA * float(np.median(np.abs(by[oot] - oot_med)))
    if scatter > 0 and best_depth < 2.0 * scatter:
        return None, "none", (
            f"V-shape check inconclusive — fitted depth {best_depth*1000:.2f} ppt "
            f"is below 2× the binned scatter ({scatter*1000:.2f} ppt)."
        )

    if best_ratio < V_SHAPE_HIGH_RATIO:
        flag = "high"
    elif best_ratio < V_SHAPE_MEDIUM_RATIO:
        flag = "medium"
    else:
        flag = "none"

    note = (
        f"V-shape check: t_flat/t_total = {best_ratio:.2f} "
        f"(trapezoid fit: depth {best_depth*1000:.2f} ppt, t_total {best_t_total:.3f} d)."
    )
    if flag == "high":
        note += (
            f" FLAGGED (high) — ratio < {V_SHAPE_HIGH_RATIO}: V-shaped event, "
            "classic grazing eclipsing-binary signature."
        )
    elif flag == "medium":
        note += (
            f" FLAGGED (medium) — ratio < {V_SHAPE_MEDIUM_RATIO}: event tends "
            "toward V-shape; inspect the folded light curve."
        )
    else:
        note += " Flat-bottomed event — consistent with a full (non-grazing) transit."
    return float(best_ratio), flag, note


def check_sector_consistency(
    n_sectors: int,
    lc: Optional[lk.LightCurve] = None,
    period_days: Optional[float] = None,
    epoch_btjd: Optional[float] = None,
    duration_days: Optional[float] = None,
    depth_ppt: Optional[float] = None,
) -> tuple[bool, str]:
    """Flag single-sector signals and per-unit transit-depth disagreement.

    With only ``n_sectors`` supplied this reproduces the legacy count-only
    behaviour.  When ``lc`` and the candidate ephemeris are also given and at
    least two observing units are present, the light curve is split on time
    gaps > ``GAP_SPLIT_DAYS`` and the transit depth is measured per chunk at
    the candidate ephemeris; a pairwise disagreement above
    ``SECTOR_DEPTH_SIGMA`` σ (σ from :func:`median_error`, i.e. the error on a
    median with red-noise inflation) is flagged.

    Parameters
    ----------
    n_sectors:
        Number of observing units (TESS sectors / K2 campaigns) contributing.
    lc:
        Cleaned, normalised light curve (optional; enables the depth test).
    period_days, epoch_btjd, duration_days:
        Candidate ephemeris (optional; required for the depth test).
    depth_ppt:
        Overall candidate depth in ppt (informational only).

    Returns
    -------
    tuple
        ``(flagged, note)``.  ``flagged`` is True for a single-sector signal
        or a > 3σ per-unit depth disagreement.
    """
    if n_sectors < 2:
        return True, "Signal observed in only 1 sector — consistency across sectors not confirmed."

    base_note = f"Signal observed across {n_sectors} sector(s)."
    if lc is None or period_days is None or epoch_btjd is None or duration_days is None:
        return False, base_note

    try:
        time = np.asarray(lc.time.value, dtype=float)
        flux = np.asarray(lc.flux.value, dtype=float)
    except Exception:
        return False, base_note

    order = np.argsort(time)
    time, flux = time[order], flux[order]
    finite = np.isfinite(time) & np.isfinite(flux)
    time, flux = time[finite], flux[finite]
    if time.size < 40:
        return False, base_note

    # ── Split on gaps > GAP_SPLIT_DAYS into observing-unit chunks ─────────────
    gap_idx = np.where(np.diff(time) > GAP_SPLIT_DAYS)[0]
    starts  = np.concatenate([[0], gap_idx + 1])
    ends    = np.concatenate([gap_idx + 1, [time.size]])

    half_dur_phase = duration_days / period_days / 2.0
    depths, sigmas = [], []
    for s, e in zip(starts, ends):
        t, f = time[s:e], flux[s:e]
        if t.size < 20:
            continue
        ph = phase_fold(t, period_days, epoch_btjd)
        in_tr = np.abs(ph) < half_dur_phase
        oot   = np.abs(ph) > half_dur_phase * 2.0
        if in_tr.sum() < 3 or oot.sum() < 10:
            continue
        sig = median_error(f[oot], int(in_tr.sum()))
        if sig <= 0:
            continue
        depths.append(1.0 - float(np.median(f[in_tr])))
        sigmas.append(sig)

    if len(depths) < 2:
        return False, base_note + (
            " Per-unit depth comparison not possible "
            "(insufficient in-transit coverage per unit)."
        )

    # ── Maximum pairwise disagreement ─────────────────────────────────────────
    max_sigma = 0.0
    for i in range(len(depths)):
        for j in range(i + 1, len(depths)):
            z = abs(depths[i] - depths[j]) / np.sqrt(sigmas[i] ** 2 + sigmas[j] ** 2)
            max_sigma = max(max_sigma, z)

    depth_str = ", ".join(
        f"{d*1000:.2f}±{s*1000:.2f} ppt" for d, s in zip(depths, sigmas)
    )
    if max_sigma > SECTOR_DEPTH_SIGMA:
        return True, base_note + (
            f" FLAGGED — per-unit depths disagree ({depth_str}; "
            f"max {max_sigma:.1f}σ > {SECTOR_DEPTH_SIGMA:.0f}σ). Depth should be "
            "achromatic and stable; disagreement suggests systematics or blends."
        )
    return False, base_note + (
        f" Per-unit depths consistent ({depth_str}; max {max_sigma:.1f}σ)."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_vetting(
    lc: lk.LightCurve,
    period_days: float,
    epoch_btjd: float,
    duration_days: float,
    depth_ppt: float,
    n_sectors: int,
    snr: float = 0.0,
    stellar_radius_rsun: Optional[float] = None,
    stellar_rotation_period_days: Optional[float] = None,
    is_known_toi: bool = False,
    catalog_ok: bool = True,
    fit=None,
    stellar=None,
) -> VettingResult:
    """Run all available false-positive checks and assign a verdict.

    ``fit`` (a :class:`tesshunter.transit_fit.TransitFit`, or its dict) and
    ``stellar`` (a :class:`tesshunter.stellar.StellarParams`) enable the
    prompt-3 checks: the period-aware secondary-eclipse test at the fitted
    a/R*, the a/R* consistency flag, the fit-based odd/even comparison and
    the fitted planet radius.

    Parameters
    ----------
    lc:
        Cleaned, normalised light curve.
    period_days:
        Best-fit BLS period.
    epoch_btjd:
        Best-fit transit epoch (BTJD).
    duration_days:
        Best-fit transit duration.
    depth_ppt:
        Transit depth in parts per thousand.
    n_sectors:
        Number of TESS sectors contributing data.
    snr:
        BLS signal-to-noise ratio of the candidate.
    stellar_radius_rsun:
        Stellar radius (from TIC or ExoFOP), if available.
    stellar_rotation_period_days:
        Stellar rotation period in days, if known (e.g. from TIC ``Prot`` column).
        Used to check whether the candidate period is a rotation harmonic.
    is_known_toi:
        True if the target is already in the TOI catalog.
    catalog_ok:
        False if the catalog crossmatch failed (network error).
        A failed crossmatch demotes the verdict from "promising" to "unverified".
    """
    result = VettingResult(
        depth_ppt           = depth_ppt,
        duration_days       = duration_days,
        period_days         = period_days,
        snr                 = snr,
        n_sectors           = n_sectors,
        stellar_radius_rsun = stellar_radius_rsun,
        catalog_ok          = catalog_ok,
    )

    # ── 1. Depth check (radius-aware when stellar radius is known) ────────────
    result.depth_too_deep, result.depth_large, note = check_depth(
        depth_ppt, stellar_radius_rsun=stellar_radius_rsun
    )
    result.notes.append(note)

    # ── 2. SNR check ──────────────────────────────────────────────────────────
    result.snr_absurd, result.snr_high, note = check_snr(snr)
    result.notes.append(note)

    # ── 3. Duration/period ratio ──────────────────────────────────────────────
    result.duration_fraction_high, result.duration_period_frac, note = check_duration_fraction(
        duration_days, period_days
    )
    result.notes.append(note)

    # ── 4. Odd/even depth comparison ──────────────────────────────────────────
    result.odd_even_mismatch, result.odd_even_delta_sigma, note = check_odd_even(
        lc, period_days, epoch_btjd, duration_days
    )
    result.notes.append(note)

    # ── 5. Secondary eclipse search ───────────────────────────────────────────
    result.secondary_eclipse_detected, result.secondary_depth_ppt, note = check_secondary_eclipse(
        lc, period_days, epoch_btjd, duration_days
    )
    result.notes.append(note)

    # ── 6. V-shape (trapezoid) check ──────────────────────────────────────────
    result.v_shape_ratio, result.v_shape_flag, note = check_v_shape(
        lc, period_days, epoch_btjd, duration_days
    )
    result.notes.append(note)

    # ── 7. Sector consistency (count + per-unit depth agreement) ──────────────
    consistency_flag, note = check_sector_consistency(
        n_sectors,
        lc=lc,
        period_days=period_days,
        epoch_btjd=epoch_btjd,
        duration_days=duration_days,
        depth_ppt=depth_ppt,
    )
    result.single_sector_only    = n_sectors < 2
    result.sector_depth_mismatch = bool(consistency_flag and n_sectors >= 2)
    result.notes.append(note)

    # ── 8. Stellar-rotation harmonic ──────────────────────────────────────────
    if stellar_rotation_period_days is not None and stellar_rotation_period_days > 0:
        result.near_rotation_harmonic, result.rotation_harmonic_ratio, note = (
            check_rotation_harmonic(period_days, stellar_rotation_period_days)
        )
        result.notes.append(note)
    else:
        result.notes.append(
            "Stellar rotation period not supplied — rotation-harmonic check skipped."
        )

    # ── 9. Estimated planet radius ────────────────────────────────────────────
    if stellar_radius_rsun is not None and stellar_radius_rsun > 0:
        from .utils import estimate_planet_radius
        result.estimated_radius_rearth = estimate_planet_radius(
            depth_ppt / 1000.0, stellar_radius_rsun
        )
        result.implied_radius_rjup = implied_companion_radius_rjup(
            depth_ppt, stellar_radius_rsun
        )
        if result.estimated_radius_rearth is not None:
            result.notes.append(
                f"Estimated planet radius: {result.estimated_radius_rearth:.2f} R_Earth "
                f"({result.implied_radius_rjup:.2f} R_Jup; "
                f"R_star = {stellar_radius_rsun:.2f} R_Sun, depth = {depth_ppt:.2f} ppt)."
            )

    # ── 10. Transit-fit derived checks (prompt 3) ─────────────────────────────
    fit_d = _fit_as_dict(fit)
    fit_ok = bool(fit_d and fit_d.get("success"))
    result.fit_available = fit_ok
    teff = float(stellar.teff) if (stellar is not None and getattr(stellar, "teff", None)) else None
    if fit_ok:
        result.fit_rp_rs = fit_d.get("rp_rs")
        result.fit_a_rs = fit_d.get("a_rs")
        result.fit_b = fit_d.get("b")
        result.fit_rp_rearth = fit_d.get("rp_rearth")
        result.fit_rp_rearth_err = fit_d.get("rp_rearth_err")
        result.fit_duration_days = fit_d.get("duration_days")
        result.a_rs_star = fit_d.get("a_rs_star")
        result.a_rs_ratio = fit_d.get("a_rs_ratio")
        result.density_ratio = fit_d.get("density_ratio")
        result.density_dchi2 = fit_d.get("density_dchi2")
        result.a_rs_inconsistent = bool(fit_d.get("a_rs_inconsistent"))
        result.fit_grazing = bool(fit_d.get("grazing"))
        d_err = float(fit_d.get("depth_err_white") or fit_d.get("depth_err") or 0.0)
        if d_err > 0.0:
            from .transit_fit import FIT_MIN_DEPTH_SIGMA
            result.fit_depth_sigma = float(fit_d.get("depth_ppt", 0.0)) / d_err
            result.fit_no_dip = bool(result.fit_depth_sigma < FIT_MIN_DEPTH_SIGMA)
        oe = fit_d.get("odd_even") or {}
        if oe.get("available"):
            result.odd_even_fit_sigma = float(oe.get("delta_sigma", 0.0))
            result.odd_even_fit_significant = bool(oe.get("significant"))
            result.notes.append(f"Odd/even from the transit-fit template: {oe.get('note')}.")
        result.notes.append(
            f"Transit fit: Rp/R* = {fit_d.get('rp_rs', 0):.4f} +/- {fit_d.get('rp_rs_err', 0):.4f}, "
            f"a/R* = {fit_d.get('a_rs', 0):.2f} +/- {fit_d.get('a_rs_err', 0):.2f}, "
            f"b = {fit_d.get('b', 0):.2f} +/- {fit_d.get('b_err', 0):.2f}, "
            f"T14 = {24 * float(fit_d.get('duration_days', 0)):.2f} h, "
            f"depth = {fit_d.get('depth_ppt', 0):.3f} +/- {fit_d.get('depth_err', 0):.3f} ppt "
            f"({fit_d.get('method')}, LD {fit_d.get('ld_source')})."
        )
        if fit_d.get("rp_rearth") is not None:
            result.notes.append(
                f"Fitted planet radius: {fit_d['rp_rearth']:.2f} +/- {fit_d.get('rp_rearth_err') or 0:.2f} R_Earth "
                f"({fit_d.get('rp_rjup') or 0:.3f} R_Jup)."
            )
            # The fitted radius supersedes the sqrt(depth) estimate.
            result.estimated_radius_rearth = float(fit_d["rp_rearth"])
            if fit_d.get("rp_rjup") is not None:
                result.implied_radius_rjup = float(fit_d["rp_rjup"])
        if fit_d.get("consistency_note"):
            result.notes.append(f"a/R* consistency: {fit_d['consistency_note']}")
        if result.fit_grazing:
            result.notes.append(
                f"Fitted geometry is grazing (b + Rp/R* = "
                f"{float(fit_d.get('b', 0)) + float(fit_d.get('rp_rs', 0)):.2f} > 1)."
            )
        # Period-aware secondary bound at the fitted a/R*
        if teff is not None and fit_d.get("a_rs") and fit_d.get("rp_rs"):
            bound, therm, refl, t_day = planetary_secondary_bound_ppt(
                float(fit_d["rp_rs"]), float(fit_d["a_rs"]), teff)
            result.secondary_planet_bound_ppt = bound
            result.secondary_is_stellar = bool(
                result.secondary_eclipse_detected
                and result.secondary_depth_ppt > SECONDARY_BOUND_MARGIN * bound
            )
            result.notes.append(
                f"Deepest planetary secondary at the fitted a/R* = {float(fit_d['a_rs']):.2f}: "
                f"{bound:.4f} ppt (thermal {therm:.4f} ppt at T_day <= {t_day:.0f} K, "
                f"reflected {refl:.4f} ppt at A_g = {SECONDARY_MAX_GEOMETRIC_ALBEDO:.0f}); "
                f"measured {result.secondary_depth_ppt:.4f} ppt."
            )
    elif fit_d:
        result.notes.append(f"Transit fit did not converge: {fit_d.get('message')}.")

    # Centroid and contamination checks live in centroid.py / contamination.py
    # (they need network access); append their flags to the flag lists and call
    # recompute_verdict() to fold them into the verdict.

    # ── Classify flags by severity ────────────────────────────────────────────
    hard_veto = result.hard_veto_flags
    high_risk = result.high_risk_flags
    medium    = result.medium_flags

    # Odd/even: when the transit-fit template comparison has enough events
    # (ODD_EVEN_MIN_EVENTS per parity) it SUPERSEDES the median-based check
    # for the flag: same quantity, better estimator (per-event depths against
    # the event-to-event scatter instead of per-point depths against the
    # white-noise scatter, which fired at 3-6 "sigma" on WASP-39 b, WASP-14 b
    # and KELT-11 b while the template test read 0.5-1.3 sigma). The
    # median-based number stays in the notes. With too few events the
    # median-based flag stands.
    oe_fit = fit_d.get("odd_even") or {}
    fit_oe_usable = bool(
        oe_fit.get("available")
        and min(int(oe_fit.get("n_odd", 0)), int(oe_fit.get("n_even", 0))) >= _ODD_EVEN_MIN_EVENTS_FOR_SUPERSEDE
    )
    if fit_oe_usable:
        if result.odd_even_mismatch != result.odd_even_fit_significant:
            result.notes.append(
                f"Odd/even flag set by the transit-fit template comparison "
                f"({result.odd_even_fit_sigma:.1f} sigma, {oe_fit.get('n_odd')}/{oe_fit.get('n_even')} events), "
                f"superseding the median-based test ({result.odd_even_delta_sigma:.1f} sigma)."
            )
        result.odd_even_mismatch = bool(result.odd_even_fit_significant)
        result.odd_even_delta_sigma = float(result.odd_even_fit_sigma or 0.0)
    elif result.odd_even_fit_significant and not result.odd_even_mismatch:
        result.odd_even_mismatch = True
        result.odd_even_delta_sigma = max(result.odd_even_delta_sigma, result.odd_even_fit_sigma or 0.0)
        result.notes.append(
            "Odd/even mismatch raised by the transit-fit template comparison "
            f"({result.odd_even_fit_sigma:.1f} sigma)."
        )

    # Elevated SNR was a proxy for "variability fitted as a transit". When the
    # fit confirms a transit-shaped, density-consistent, non-grazing dip and
    # no eclipsing-binary marker is present (no stellar secondary, no odd/even
    # mismatch) that cause is tested directly, so the SNR flag drops to
    # medium; it stays high risk when no fit is available or any of those
    # tests is not clean.
    result.snr_high_demoted = bool(
        result.snr_high and not result.snr_absurd and result.fit_available
        and not result.fit_no_dip and not result.a_rs_inconsistent and not result.fit_grazing
        and not result.secondary_is_stellar and not result.odd_even_mismatch
    )

    # Hard vetoes
    if result.depth_too_deep:
        if result.implied_radius_rjup is not None:
            hard_veto.append(
                f"implied companion radius {result.implied_radius_rjup:.2f} R_Jup "
                f"> {RADIUS_HARD_VETO_RJUP} R_Jup — stellar-companion regime"
            )
        else:
            hard_veto.append(
                f"depth {depth_ppt:.1f} ppt ({depth_ppt/10:.1f}%) — impossible for planet"
            )
    if result.snr_absurd:
        hard_veto.append(
            f"SNR {snr:.0f} — unphysical (stellar activity or systematic)"
        )
    if result.secondary_eclipse_detected and result.odd_even_mismatch:
        hard_veto.append(
            f"secondary eclipse + odd/even mismatch ({result.odd_even_delta_sigma:.1f}σ) "
            "— two independent EB markers"
        )

    # High-risk soft flags
    if result.depth_large and not result.depth_too_deep:
        if result.implied_radius_rjup is not None:
            high_risk.append(
                f"implied companion radius {result.implied_radius_rjup:.2f} R_Jup "
                f"({RADIUS_HIGH_RISK_RJUP}–{RADIUS_HARD_VETO_RJUP} R_Jup — inflated "
                "planet / brown dwarf / EB territory)"
            )
        else:
            high_risk.append(
                f"large depth {depth_ppt:.1f} ppt (EB / contamination territory)"
            )
    if result.snr_high and not result.snr_absurd:
        if result.snr_high_demoted:
            # A note, not a flag: the fit has tested what the SNR was a proxy
            # for. (As a medium flag it stacked with the legacy per-unit-depth
            # flag into "ambiguous" on 9 of the 18 adversarial planets.)
            result.notes.append(
                f"Elevated SNR {snr:.0f}: the transit fit confirms a transit-shaped, "
                f"density-consistent dip with no eclipsing-binary marker, so the SNR is "
                f"noted and not flagged."
            )
        else:
            high_risk.append(f"elevated SNR {snr:.0f} (stellar activity possible)")
    if result.near_rotation_harmonic:
        high_risk.append(
            f"period {period_days:.4f} d ≈ {result.rotation_harmonic_ratio}× "
            f"stellar rotation ({stellar_rotation_period_days:.3f} d)"
        )
    if result.secondary_eclipse_detected and not result.odd_even_mismatch:
        # The flag is ALWAYS raised - the measurement is real and a reader must
        # see it. What the tests below decide is only whether it may STACK with
        # another high-risk flag into an automatic false-positive verdict; see
        # _effective_high_risk_count.
        #
        # Period-aware test (prompt 3): with a transit fit and a Teff, the
        # secondary is compared with the deepest secondary an irradiated planet
        # could show at the FITTED a/R* (dayside thermal emission plus
        # reflected light). Above SECONDARY_BOUND_MARGIN times that bound the
        # secondary is a stellar eclipse and stacks; within it, it is
        # consistent with a planet and does not. This replaces the legacy
        # fixed-ratio-plus-radius exemption, which stays only as the fallback
        # when no fit is available (radius alone cannot separate a gas giant
        # from a late-M companion; both are ~1-1.2 R_Jup).
        high_risk.append(
            f"secondary eclipse at phase 0.5 ({result.secondary_depth_ppt:.2f} ppt)"
        )
        if result.secondary_planet_bound_ppt is not None:
            bound = result.secondary_planet_bound_ppt
            stellar_secondary = result.secondary_depth_ppt > SECONDARY_BOUND_MARGIN * bound
            planet_sized = (
                result.implied_radius_rjup is None
                or result.implied_radius_rjup <= RADIUS_HARD_VETO_RJUP
            )
            result.secondary_is_stellar = bool(stellar_secondary)
            result.secondary_is_planetary = bool((not stellar_secondary) and planet_sized)
            if stellar_secondary:
                result.notes.append(
                    f"Secondary eclipse {result.secondary_depth_ppt:.3f} ppt exceeds "
                    f"{SECONDARY_BOUND_MARGIN:.0f}x the deepest planetary secondary "
                    f"({bound:.4f} ppt) at the fitted a/R* = {result.fit_a_rs:.2f}: a stellar "
                    f"eclipse. Stacks with any other high-risk flag."
                )
            else:
                result.notes.append(
                    f"Secondary eclipse {result.secondary_depth_ppt:.3f} ppt is within "
                    f"{SECONDARY_BOUND_MARGIN:.0f}x the deepest planetary secondary "
                    f"({bound:.4f} ppt) at the fitted a/R* = {result.fit_a_rs:.2f}: consistent "
                    f"with planetary dayside emission. Flagged for manual vetting, but not "
                    f"stacked into an automatic false-positive verdict."
                )
        else:
            secondary_ratio = (
                result.secondary_depth_ppt / depth_ppt if depth_ppt > 0.0 else float("inf")
            )
            planetary_secondary = (
                0.0 < secondary_ratio <= PLANETARY_SECONDARY_MAX_RATIO
                and result.implied_radius_rjup is not None
                and result.implied_radius_rjup <= RADIUS_HIGH_RISK_RJUP
            )
            result.secondary_is_planetary = bool(planetary_secondary)
            if planetary_secondary:
                result.notes.append(
                    f"Secondary eclipse at phase 0.5 is {result.secondary_depth_ppt:.2f} ppt, "
                    f"{100.0 * secondary_ratio:.1f}% of the {depth_ppt:.2f} ppt primary, on an "
                    f"implied {result.implied_radius_rjup:.2f} R_Jup companion — consistent with "
                    f"planetary dayside emission (legacy ratio test; no transit fit available). "
                    f"Flagged, but not stacked with the elevated-SNR flag into an automatic "
                    f"false-positive verdict. NOTE: an implied radius near 1 R_Jup does not by "
                    f"itself exclude a late-M or brown-dwarf companion."
                )
    if result.odd_even_mismatch and not result.secondary_eclipse_detected:
        high_risk.append(
            f"odd/even depth asymmetry ({result.odd_even_delta_sigma:.1f}σ)"
        )
    if result.a_rs_inconsistent:
        high_risk.append(
            f"{A_RS_INCONSISTENT_NOTE} (density ratio {result.density_ratio:.2f}, "
            f"profile delta chi2 {result.density_dchi2:.0f}, "
            f"{(fit_d.get('density_dchi2_eff') or 0):.0f} after red-noise beta "
            f"{(fit_d.get('beta_red_noise') or 1):.2f}) — diluted eclipse, grazing "
            f"stellar companion or blend"
        )
    if result.fit_no_dip:
        high_risk.append(
            f"limb-darkened fit finds no significant transit at the BLS ephemeris "
            f"({result.fit_depth_sigma:.1f} sigma) — box signal is not transit-shaped"
        )
    if result.v_shape_flag == "high":
        high_risk.append(
            f"V-shaped transit (t_flat/t_total = {result.v_shape_ratio:.2f} "
            f"< {V_SHAPE_HIGH_RATIO}) — grazing-EB signature"
        )

    # Medium flags
    if result.duration_fraction_high:
        medium.append(f"high duration/period ratio ({result.duration_period_frac:.3f})")
    if result.single_sector_only:
        medium.append("single sector only — consistency not confirmed")
    if result.sector_depth_mismatch:
        medium.append(
            f"per-unit transit depths disagree by > {SECTOR_DEPTH_SIGMA:.0f}σ "
            "across observing units"
        )
    if result.v_shape_flag == "medium":
        medium.append(
            f"V-shape tendency (t_flat/t_total = {result.v_shape_ratio:.2f} "
            f"< {V_SHAPE_MEDIUM_RATIO})"
        )
    if not catalog_ok:
        medium.append("catalog lookup failed — TOI/confirmed-planet status unknown")

    # ── Assign verdict ────────────────────────────────────────────────────────
    # Depth- and SNR-based high-risk flags stem from the same amplitude cause,
    # so the pair counts as one flag and never auto-FPs on its own (V1).
    n_high_eff = _effective_high_risk_count(result)
    if hard_veto:
        result.verdict = VERDICT_FP
        if is_known_toi:
            result.notes.append(
                "NOTE: target is a known TOI but hard-veto flags are present — "
                "likely a period or depth mismatch with the catalogued planet."
            )
    elif is_known_toi and not high_risk:
        result.verdict = VERDICT_KNOWN
    elif n_high_eff >= 2:
        result.verdict = VERDICT_FP
    elif len(high_risk) >= 1:
        result.verdict = VERDICT_AMBIGUOUS
    elif not catalog_ok:
        result.verdict = VERDICT_UNVERIFIED
    elif len(medium) >= 2:
        result.verdict = VERDICT_AMBIGUOUS
    elif is_known_toi:
        result.verdict = VERDICT_KNOWN   # known TOI with medium flags only
    else:
        result.verdict = VERDICT_PROMISING

    logger.info(
        "Vetting verdict: %s  |  hard=%d  high_risk=%d  medium=%d",
        result.verdict, len(hard_veto), len(high_risk), len(medium),
    )
    return result


def _fit_as_dict(fit) -> dict:
    """Accept a TransitFit, its dict form, or None."""
    if fit is None:
        return {}
    if isinstance(fit, dict):
        return fit
    if hasattr(fit, "to_dict"):
        return fit.to_dict()
    return {}


def _effective_high_risk_count(result: VettingResult) -> int:
    """Count high-risk flags, merging the depth- and SNR-based pair into one.

    Both flags stem from the same amplitude cause (a strong signal), so when
    both are present they contribute a single effective flag — the pair alone
    must not stack to an automatic false-positive verdict (V1).
    """
    n = len(result.high_risk_flags)
    depth_flagged = result.depth_large and not result.depth_too_deep
    snr_flagged   = (result.snr_high and not result.snr_absurd
                     and not getattr(result, "snr_high_demoted", False))
    if depth_flagged and snr_flagged and n >= 2:
        n -= 1
    # Same principle for an ultra-hot planet: a secondary that an irradiated
    # planet CAN produce (within the period-aware bound, or the legacy ratio
    # test without a fit) is a view of the same object as its bright, deep
    # transit, not an independent false-positive indicator, so it never
    # stacks with another flag into an automatic FP verdict. The flag itself
    # is retained, so the candidate still lands on "ambiguous" rather than
    # "promising" - a genuine EB is never cleared, only spared the automatic
    # veto. (Prompt 3: it used to de-stack only against the SNR flag; with
    # the SNR flag demoted, WASP-121 b's 0.08 ppt dayside secondary stacked
    # with its inflated-radius flag into a false-positive verdict.)
    if getattr(result, "secondary_is_planetary", False) and n >= 2:
        n -= 1
    return n


#: Pixel-level checks (prompt 3, part E): the in-transit centroid shift and
#: the nearby-star contamination check are the tests that see a blend the
#: light curve cannot. A flagged centroid is a high-risk flag; a
#: contamination result with HIGH-risk neighbours is high risk, with only
#: MEDIUM-risk neighbours a medium flag.
CENTROID_FLAG_PREFIX = "in-transit centroid shift"
CONTAMINATION_FLAG_PREFIX = "nearby star could produce the signal"


#: TRICERATOPS nearby-false-positive probability at or above this is a
#: high-risk flag of its own; below it, a contamination HIGH-risk neighbour
#: (the legacy geometric test, which flags any star that could physically
#: produce the depth through PRF leakage) is demoted to medium because the
#: aperture-weighted TRICERATOPS scenarios have examined that same star and
#: found it wanting. TOI-270 c: contamination "1 high-risk neighbour",
#: NFPP 1e-77 with the SPOC apertures.
NFPP_HIGH_RISK = 0.1
NFPP_FLAG_PREFIX = "TRICERATOPS nearby false-positive probability"

#: A flagged centroid shift is high risk only at this significance or above;
#: below it, it is a medium flag. Measured on the adversarial set: the
#: flagged known planets sat at 3.3-7.5 sigma with shifts of 0.003-0.025 px
#: (bright stars, so any systematic is "significant"), the flagged blends
#: and eclipsing binaries at 4.3-14.9 sigma with 0.004-0.025 px, i.e. the
#: significance alone does NOT separate the classes and the threshold only
#: keeps the least significant planet flags from stacking [A]. The centroid
#: module itself (P0 code) is the weak link here; see HANDOFF_P3 "Still open".
CENTROID_HIGH_RISK_SIGMA = 4.0


def apply_pixel_checks(
    result: VettingResult,
    centroid=None,
    contamination=None,
    is_known_toi: bool = False,
    fpp=None,
) -> str:
    """Append centroid / contamination / NFPP flags to ``result`` and recompute its verdict.

    ``centroid`` is a :class:`tesshunter.centroid.CentroidResult` (or dict),
    ``contamination`` a :class:`tesshunter.contamination.ContaminationResult`
    (or dict) and ``fpp`` a :class:`tesshunter.fpp.FPPResult` (or dict); any
    may be None or unavailable, in which case a note is added and nothing
    changes for that check. Returns the new verdict (also stored on
    ``result.verdict``). Idempotent: flags already present are not added twice.
    """
    def _g(obj, key, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    if centroid is None:
        result.notes.append("Centroid check not run.")
    elif not _g(centroid, "available", False):
        result.notes.append(f"Centroid check not available: {_g(centroid, 'note', '')}")
    else:
        shift = float(_g(centroid, "total_shift_px", 0.0) or 0.0)
        sig = float(_g(centroid, "sigma", 0.0) or 0.0)
        arcsec = float(_g(centroid, "shift_arcsec", 0.0) or 0.0)
        result.centroid_shift = shift
        text = (f"{CENTROID_FLAG_PREFIX} {shift:.3f} px ({arcsec:.1f} arcsec, {sig:.1f} sigma) "
                f"over {_g(centroid, 'n_sectors_used', 0)} sector(s)")
        if _g(centroid, "flagged", False):
            already = any(f.startswith(CENTROID_FLAG_PREFIX)
                          for f in result.high_risk_flags + result.medium_flags)
            if not already:
                if sig >= CENTROID_HIGH_RISK_SIGMA:
                    result.high_risk_flags.append(text + " — signal may sit on a neighbour")
                else:
                    result.medium_flags.append(text + f" (below {CENTROID_HIGH_RISK_SIGMA:.0f} sigma)")
        result.notes.append("Centroid: " + text + (" FLAGGED." if _g(centroid, "flagged", False) else " (pass)."))

    nfpp = None
    fpp_ok = bool(fpp is not None and _g(fpp, "available", False))
    if fpp_ok:
        nfpp = _g(fpp, "nfpp", None)
        fppv = _g(fpp, "fpp", None)
        result.notes.append(
            f"TRICERATOPS: FPP {fppv if fppv is None else format(float(fppv), '.4f')}, "
            f"NFPP {nfpp if nfpp is None else format(float(nfpp), '.2e')}."
        )
        if nfpp is not None and float(nfpp) >= NFPP_HIGH_RISK:
            text = f"{NFPP_FLAG_PREFIX} {float(nfpp):.3f} >= {NFPP_HIGH_RISK}"
            if not any(f.startswith(NFPP_FLAG_PREFIX) for f in result.high_risk_flags):
                result.high_risk_flags.append(text)
    elif fpp is not None:
        result.notes.append(f"TRICERATOPS not available: {_g(fpp, 'error', '')}")

    if contamination is None:
        result.notes.append("Contamination check not run.")
    elif not _g(contamination, "available", False):
        result.notes.append(f"Contamination check not available: {_g(contamination, 'note', '')}")
    else:
        n_high = len(_g(contamination, "high_risk_neighbours", []) or [])
        n_med = len(_g(contamination, "medium_risk_neighbours", []) or [])
        n_chk = int(_g(contamination, "n_neighbours_checked", 0) or 0)
        text = (f"{CONTAMINATION_FLAG_PREFIX}: {n_high} high-risk and {n_med} medium-risk "
                f"neighbour(s) of {n_chk} checked")
        nfpp_clears = bool(fpp_ok and nfpp is not None and float(nfpp) < NFPP_HIGH_RISK)
        if nfpp_clears:
            # TRICERATOPS has weighed every one of these stars with the real
            # aperture and found no nearby scenario: note only, no flag.
            text += f"; cleared by TRICERATOPS NFPP {float(nfpp):.2e} with the real aperture"
        elif n_high > 0:
            if not any(f.startswith(CONTAMINATION_FLAG_PREFIX) for f in result.high_risk_flags):
                result.high_risk_flags.append(text)
        elif n_med > 0:
            if not any(f.startswith(CONTAMINATION_FLAG_PREFIX) for f in result.medium_flags):
                result.medium_flags.append(text)
        result.notes.append("Contamination: " + text + ".")

    result.verdict = recompute_verdict(result, is_known_toi=is_known_toi)
    return result.verdict


def vetting_result_from_dict(d: dict) -> VettingResult:
    """Rebuild a VettingResult from ``asdict`` output (a pipeline result's
    ``vetting[i]["result"]``); unknown keys are ignored."""
    known = set(VettingResult.__dataclass_fields__)
    payload = {k: v for k, v in (d or {}).items() if k in known}
    r = VettingResult(**payload)
    # keep the alias lists pointing at the same objects
    r.flags_hard = r.hard_veto_flags
    r.flags_high = r.high_risk_flags
    r.flags_medium = r.medium_flags
    return r


def recompute_verdict(result: VettingResult, is_known_toi: bool = False) -> str:
    """Re-derive the verdict string from the current flag lists.

    Call this after appending centroid / contamination flags to
    ``result.hard_veto_flags``, ``result.high_risk_flags``, or
    ``result.medium_flags`` (or their ``flags_*`` aliases).
    """
    hard_veto = result.hard_veto_flags
    high_risk = result.high_risk_flags
    medium    = result.medium_flags
    catalog_ok = result.catalog_ok
    n_high_eff = _effective_high_risk_count(result)

    if hard_veto:
        return VERDICT_FP
    elif is_known_toi and not high_risk:
        return VERDICT_KNOWN
    elif n_high_eff >= 2:
        return VERDICT_FP
    elif len(high_risk) >= 1:
        return VERDICT_AMBIGUOUS
    elif not catalog_ok:
        return VERDICT_UNVERIFIED
    elif len(medium) >= 2:
        return VERDICT_AMBIGUOUS
    elif is_known_toi:
        return VERDICT_KNOWN
    else:
        return VERDICT_PROMISING
