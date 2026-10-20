"""Canonical end-to-end search pipeline: download → preprocess → detect → vet.

This module is the single entry point that ties the fixed stages together:

1. **Download** — :func:`tesshunter.download.search_and_download_lc` with the
   cadence-aware ``exptime="auto"`` default, then
   :func:`tesshunter.download.stitch_collection` with per-unit deduplication.
   Provenance (products used, units, fallback events) is preserved.
2. **Preprocess** — :func:`tesshunter.preprocessing.preprocess` with the
   window-in-days flatten logic, followed by an optional TWO-PASS flatten:
   a broad BLS on the first-pass product finds the strongest candidate, an
   in-transit mask at that ephemeris is built over the PRE-flatten light
   curve, and preprocessing is re-run with ``transit_mask=`` so the transit
   is not absorbed into the trend (defect P4).
3. **Detect** — the iterative gate/alias loop ported from
   ``scripts/_cell_loop_src.py`` (gates 1–4, per-candidate alias resolution,
   artifact-period skips), plus a new ``n_transits_observed >= min_transits``
   acceptance gate (defect B4) and robustness stops for masked-out light
   curves (a mask wider than the period must never crash the pipeline).
4. **Vet** — :func:`tesshunter.vetting.run_vetting` for EVERY accepted planet,
   with ``snr`` and ``catalog_ok`` actually passed.
5. **Report** (optional) — a markdown report for planet 1 and a summary-CSV
   upsert for every planet with its real per-planet verdict (defect R3).
   Report failures never kill the search result.

The YAML configuration story (``configs/search_targets.yaml``) is implemented
by :func:`load_search_config` and :func:`search_targets_from_config`.
"""

from __future__ import annotations

import inspect
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import lightkurve as lk
import numpy as np
import pandas as pd

from . import bls_search, preprocessing, transit_fit, vetting
from .config import CANDIDATES_DIR, CONFIGS_DIR
from .stellar import StellarParams, fetch_tic_params
from .download import (
    observing_units_available,
    search_and_download_lc,
    stitch_collection,
)

logger = logging.getLogger(__name__)

# ── Robustness constants ──────────────────────────────────────────────────────

#: Minimum finite cadences the working light curve must retain before another
#: detection pass is attempted — below this the loop stops cleanly.
MIN_WORKING_CADENCES = 50

#: If masking an accepted planet would remove more than this fraction of the
#: working light curve, the loop stops AFTER accepting the planet (a mask
#: wider than the period must never crash the pipeline or empty the LC).
MAX_MASK_REMOVAL_FRACTION = 0.90

#: Fractional tolerance for artifact-period skipping (matches the 2% rule in
#: the notebook loop and the run_bls suppress_periods default).
ARTIFACT_PERIOD_TOL = 0.02

#: The two-pass flatten mask half-width is capped at this fraction of the
#: candidate period so a wide mask never covers the entire phase-folded orbit.
MAX_FLATTEN_MASK_PHASE = 0.40

#: Fractional period tolerance for the post-accept ratio-1 neighbourhood veto.
#: A later candidate within this fraction of an ALREADY ACCEPTED period is
#: residual ringing around that planet, not a new planet.
#:
#: Deliberately ratio-1 ONLY — harmonics are NEVER suppressed. Real planetary
#: systems are resonant: in this dev set alone TOI-270 d/c = 2.010,
#: L 98-59 d/c = 2.019, TRAPPIST-1 g/e = 2.025 and HD 63433 c/b = 2.890, so
#: suppressing low-order harmonics of accepted periods would veto genuine,
#: currently-recovered planets.
#:
#: 5% is bounded on both sides by measurement: the widest true ringing pair in
#: the dev set is 3.54% (TOI-700), while no two real planets in any dev system
#: are within 34% of each other, and a tolerance sweep through the frozen
#: scorer first destroys a real detection at 8%.
RINGING_PERIOD_TOL = 0.05

#: A fitted transit duration sitting on the search grid's lower bound is not a
#: measured duration — it is the optimiser pinned against a rail. Vetoed only
#: when the rail is itself unresolvable, i.e. ``duration_min`` spans fewer than
#: MIN_CADENCES_PER_DURATION binned cadences, so a genuinely short but resolved
#: transit is never rejected.
MIN_CADENCES_PER_DURATION = 2.0

#: Relative tolerance for "the fitted duration equals the grid floor".
DURATION_RAIL_TOL = 1e-6

#: Extra detection passes allowed beyond ``max_planets`` so that passes spent
#: masking a vetoed (non-planet) signal do not consume the planet budget.
#: This is only a COUNT bound; the binding safety limit is the wall-clock
#: deadline below, because a pass count has no relation to a runtime budget.
MAX_VETO_PASSES = 4

#: Safety factor applied to the measured cost of the slowest completed pass
#: when deciding whether another pass fits inside ``time_budget_s``. Passes
#: are near-constant in cost (masking removes only a few percent of cadences),
#: so the previous worst pass is a good predictor; the margin covers variance.
PASS_COST_SAFETY = 1.25

#: Fraction of a caller-supplied per-target budget that detection may use, the
#: remainder reserving time for vetting, depth re-measurement and serialisation.
DETECT_BUDGET_FRACTION = 0.85

#: A fitted transit longer than this fraction of its period is not a transit
#: geometry the fit can be trusted on; the box depth is kept (prompt 3).
MAX_FIT_DURATION_FRACTION = 0.25

#: The fitted T14 must lie within this range of the BLS box duration for the
#: fitted depth to be shipped (the flat-bottom / box depth is kept otherwise).
FIT_DURATION_RATIO_RANGE = (0.2, 4.0)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

def _to_native(obj: Any) -> Any:
    """Recursively convert numpy scalars/arrays and Paths to JSON-able types."""
    if isinstance(obj, dict):
        return {str(k): _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (bool, int, float, str)) or obj is None:
        return obj
    return str(obj)


def _default_timings() -> dict:
    return {"download": 0.0, "preprocess": 0.0, "detect": 0.0, "vet": 0.0}


@dataclass
class SearchTargetResult:
    """Structured result of one :func:`search_target` run.

    ``to_dict()`` returns a plain-python (json.dumps-able) mapping with the
    stable key contract used by external consumers:

    * ``planets`` — one dict per accepted planet (``planet_num``,
      ``period_days``, ``epoch_btjd``, ``duration_days``, ``depth_ppt``,
      ``power``, ``snr``, ``sde``, ``event_completeness``,
      ``n_transits_observed``, ``single_event``, ``harmonic_label``,
      ``verdict``).
    * ``vetting`` — one dict per accepted planet (``planet_num``,
      ``verdict``, ``flags_hard``, ``flags_high``, ``flags_medium``,
      ``notes``, ``result``).
    * ``provenance`` — ``products``, ``units_used``, ``units_all``,
      ``fallback_events``, ``n_products_downloaded``.
    * ``prep`` — the preprocessing record plus two-pass flatten metadata.
    * ``timings`` — seconds per stage (``download``, ``preprocess``,
      ``detect``, ``vet``).
    * ``n_cadences_raw`` / ``n_cadences_clean`` — cadence counts before and
      after preprocessing.
    """

    target: Any = ""
    mission: str = "TESS"
    planets: list = field(default_factory=list)
    vetting: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    prep: dict = field(default_factory=dict)
    timings: dict = field(default_factory=_default_timings)
    n_cadences_raw: int = 0
    n_cadences_clean: int = 0
    n_sectors: int = 0
    params: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    report_path: Optional[str] = None
    crossmatch: dict = field(default_factory=dict)
    stellar: Optional[dict] = None
    #: The stitched and the cleaned light curves (lightkurve objects), kept
    #: for the FPP and packet stages; never serialised by ``to_dict``.
    lc_raw: Any = field(default=None, repr=False, compare=False)
    lc_clean: Any = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict:
        """Return a plain-python dict safe for ``json.dumps``."""
        return _to_native({
            "stellar": self.stellar,
            "target": self.target,
            "mission": self.mission,
            "planets": self.planets,
            "vetting": self.vetting,
            "provenance": self.provenance,
            "prep": self.prep,
            "timings": self.timings,
            "n_cadences_raw": self.n_cadences_raw,
            "n_cadences_clean": self.n_cadences_clean,
            "n_sectors": self.n_sectors,
            "params": self.params,
            "notes": self.notes,
            "report_path": self.report_path,
            "crossmatch": self.crossmatch,
        })


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _numeric_id(target: str | int) -> Optional[int]:
    """Extract a numeric catalog id (TIC/EPIC/KIC) from a target identifier."""
    if isinstance(target, (int, np.integer)):
        return int(target)
    m = re.search(r"(\d{5,})", str(target))
    return int(m.group(1)) if m else None


def _is_artifact_period(period: float, artifact_periods: list[float]) -> bool:
    """True when ``period`` is within ARTIFACT_PERIOD_TOL of a known artifact."""
    return any(
        abs(period / bad - 1.0) < ARTIFACT_PERIOD_TOL for bad in artifact_periods
    )


def _build_transit_mask(
    time: np.ndarray,
    period: float,
    epoch: float,
    duration: float,
    width_factor: float,
) -> np.ndarray:
    """Boolean in-transit mask at an ephemeris (True = in transit).

    The half-width is ``width_factor × duration`` (mirroring
    :func:`tesshunter.preprocessing.mask_transits`), capped at
    ``MAX_FLATTEN_MASK_PHASE × period`` so the mask never swallows the entire
    phase-folded orbit for short-period planets.
    """
    half_width = min(width_factor * duration, MAX_FLATTEN_MASK_PHASE * period)
    phase_days = ((time - epoch + 0.5 * period) % period) - 0.5 * period
    return np.abs(phase_days) <= half_width


def _n_finite_cadences(lc: lk.LightCurve) -> int:
    """Number of cadences with finite flux."""
    return int(np.isfinite(np.asarray(lc.flux.value, dtype=float)).sum())


def _ringing_neighbour(
    period: float,
    accepted: list[dict],
    tol: float = RINGING_PERIOD_TOL,
) -> Optional[dict]:
    """The accepted planet whose period is within ``tol`` of ``period``, if any.

    Ratio-1 only: a harmonic of an accepted period is NOT a neighbour, because
    real planetary systems are commonly in low-order resonance and suppressing
    harmonics would veto genuine planets.
    """
    for planet in accepted:
        # Prompt 3, part C2 (weakness 1): an accepted candidate whose transit
        # fit is not planet-shaped (Rp/R* above MAX_PLANET_RP_RS, or an a/R*
        # inconsistent with the star) may not carve an exclusion zone, so a
        # real planet a few percent away in period is not vetoed as its
        # ringing. The flag is set by _anchor_plausibility at acceptance.
        if not planet.get("carves_exclusion_zone", True):
            continue
        p_acc = float(planet.get("period_days", 0.0) or 0.0)
        if p_acc > 0.0 and abs(period / p_acc - 1.0) <= tol:
            return planet
    return None


def _duration_is_railed(
    duration: float,
    duration_min: float,
    binned_cadence_days: float,
    min_cadences: float = MIN_CADENCES_PER_DURATION,
) -> bool:
    """True when a fitted duration is pinned on an UNRESOLVABLE grid floor.

    Two conditions must both hold: the search's ``duration_min`` is shorter
    than ``min_cadences`` binned cadences (so no duration that short can be
    measured at all), and the fitted duration sits on that floor. A genuinely
    short transit that the cadence CAN resolve is never railed.
    """
    if binned_cadence_days <= 0.0 or duration_min <= 0.0:
        return False
    if duration_min >= min_cadences * binned_cadence_days:
        return False
    return duration <= duration_min * (1.0 + DURATION_RAIL_TOL)


#: Gate 7 second condition (prompt 3, part C3; weakness 2 of
#: IMPROVEMENT_REPORT.md): a railed duration alone is not sufficient evidence.
#: The veto also requires the box depth to imply Rp/R* above this, which
#: still removes the catastrophic TRAPPIST-1 candidates (52-96 ppt boxes,
#: Rp/R* 0.23-0.31) while sparing a genuinely short, shallow transit.
GATE7_MIN_RP_RS = transit_fit.MAX_PLANET_RP_RS

class ExposureAwareGate7:
    """[K1] Gate 7 at the candidate's own cadence, installed for one search by ``survey.run_job`` when
    ``SurveyConfig.exposure_aware`` (the K1 presets); nothing changes outside the ``with`` block.

    The prompt-2 rule compares ``duration_min`` with the median cadence of the whole binned series; on a
    mixed 1800/600/200-s series that is the 200-s cadence even for an event carried by 1800-s data.
    Inside the block, ``bls_search.resolve_aliases_for_candidate`` is wrapped to remember the last
    resolved candidate and its light curve, and this module's ``_duration_is_railed`` (looked up at call
    time by ``_detect_planets``) compares instead with the median native cadence of that candidate's
    in-transit cadences (``_in_transit_cadence_days``).  ``_detect_planets`` itself is not edited: the
    P11.5 structural test pins its source to its versioned copy in ``p11_5_detector``."""

    def __enter__(self):
        from . import bls_search as _bls
        self._bls = _bls
        self._orig_railed = globals()["_duration_is_railed"]
        self._orig_resolve = _bls.resolve_aliases_for_candidate
        last: dict = {}
        orig_resolve, orig_railed = self._orig_resolve, self._orig_railed

        def resolve(*args, **kwargs):
            out = orig_resolve(*args, **kwargs)
            lc = args[0] if args else kwargs.get("lc")
            last["time"] = np.asarray(lc.time.value, dtype=float) if lc is not None else None
            last["resolved"] = out[0] if isinstance(out, tuple) else out
            return out

        def railed(duration, duration_min, binned_cadence_days, min_cadences=MIN_CADENCES_PER_DURATION):
            cadence = binned_cadence_days
            r = last.get("resolved")
            if r is not None and last.get("time") is not None and abs(float(r["duration_days"]) - float(duration)) < 1e-12:
                c = _in_transit_cadence_days(last["time"], float(r["period_days"]), float(r["epoch_btjd"]),
                                             float(r["duration_days"]))
                if c > 0:
                    cadence = c
            self.last_cadence_days = cadence
            return orig_railed(duration, duration_min, cadence, min_cadences)

        _bls.resolve_aliases_for_candidate = resolve
        globals()["_duration_is_railed"] = railed
        return self

    def __exit__(self, *exc):
        self._bls.resolve_aliases_for_candidate = self._orig_resolve
        globals()["_duration_is_railed"] = self._orig_railed
        return False


def _in_transit_cadence_days(time: np.ndarray, period: float, epoch: float, duration: float) -> float:
    """[K1] Median native cadence of the cadences within ``duration / 2`` of a predicted mid-time:
    each in-transit cadence contributes the gap to its nearest neighbour in the whole series."""
    t = np.sort(np.asarray(time, dtype=float)[np.isfinite(time)])
    if t.size < 3 or not (period > 0 and duration > 0):
        return 0.0
    d = np.abs(((t - epoch + 0.5 * period) % period) - 0.5 * period)
    inside = np.flatnonzero(d <= 0.5 * duration)
    if inside.size == 0:
        return 0.0
    gaps = np.diff(t)
    left = np.concatenate(([np.inf], gaps))
    right = np.concatenate((gaps, [np.inf]))
    nn = np.minimum(left, right)[inside]
    nn = nn[np.isfinite(nn) & (nn > 0)]
    return float(np.median(nn)) if nn.size else 0.0


def _box_rp_rs(depth_ppt: float) -> float:
    """Rp/R* implied by a box depth (sqrt of the fractional depth)."""
    return float(np.sqrt(max(float(depth_ppt), 0.0) / 1000.0))


def _anchor_plausibility(
    lc_binned: lk.LightCurve,
    planet: dict,
    stellar: Optional[StellarParams],
) -> tuple[bool, dict]:
    """Decide whether an accepted candidate may carve a gate-6 exclusion zone.

    A cheap fixed-period transit fit on the working (binned) light curve. The
    candidate carves unless the fit says it is not planet-shaped: Rp/R* above
    ``transit_fit.MAX_PLANET_RP_RS`` or an a/R* inconsistent with the star
    (needs stellar parameters). Any failure keeps the previous behaviour
    (carve), so a broken fit can never widen the search.
    """
    try:
        fit = transit_fit.quick_fit(
            lc_binned, float(planet["period_days"]), float(planet["epoch_btjd"]),
            float(planet["duration_days"]), float(planet["depth_ppt"]), stellar=stellar,
        )
    except Exception as exc:                                      # pragma: no cover
        logger.debug("anchor plausibility fit failed (%s); carving", exc)
        return True, {"success": False, "message": str(exc)}
    info = {
        "success": bool(fit.success), "rp_rs": fit.rp_rs, "a_rs": fit.a_rs, "b": fit.b,
        "a_rs_star": fit.a_rs_star, "density_ratio": fit.density_ratio,
        "density_dchi2": fit.density_dchi2, "a_rs_inconsistent": bool(fit.a_rs_inconsistent),
        "grazing": bool(fit.grazing), "message": fit.message,
    }
    if not fit.success:
        return True, info
    too_big = fit.rp_rs > transit_fit.MAX_PLANET_RP_RS
    carve = not (too_big or fit.a_rs_inconsistent)
    info["reason"] = (
        "" if carve else
        (f"Rp/R* {fit.rp_rs:.3f} > {transit_fit.MAX_PLANET_RP_RS}" if too_big
         else f"a/R* inconsistent with the star (density ratio {fit.density_ratio:.2f})")
    )
    return carve, info


def _resolve_stellar(
    stellar_params,
    tic_id: Optional[int],
    fetch: bool,
    stellar_radius_rsun: Optional[float],
) -> Optional[StellarParams]:
    """Stellar parameters for the fit: caller-supplied, else the cached TIC.

    ``stellar_radius_rsun`` (the legacy kwarg) fills in a missing radius and,
    on its own, still produces a container so Rp can be reported.
    """
    stellar: Optional[StellarParams] = None
    if isinstance(stellar_params, StellarParams):
        stellar = stellar_params
    elif isinstance(stellar_params, dict):
        stellar = StellarParams.from_dict(stellar_params)
    elif fetch and tic_id is not None:
        try:
            stellar = fetch_tic_params(int(tic_id))
        except Exception as exc:                                  # pragma: no cover
            logger.warning("stellar parameter lookup failed (%s)", exc)
            stellar = None
    if stellar is None and stellar_radius_rsun:
        stellar = StellarParams(radius=float(stellar_radius_rsun), source="caller_radius")
    elif stellar is not None and (stellar.radius is None or stellar.radius <= 0) and stellar_radius_rsun:
        stellar.radius = float(stellar_radius_rsun)
        stellar.notes.append("radius from the caller")
    return stellar


def _measure_depth_at_ephemeris(
    time_arr: np.ndarray,
    flux: np.ndarray,
    period: float,
    epoch: float,
    duration: float,
    *,
    core_frac: float = 0.4,
    gap_frac: float = 0.75,
    baseline_frac: float = 2.5,
    min_in: int = 3,
    min_out: int = 10,
    baseline_ref: float = 1.0,
    max_baseline_contamination: float = 0.5,
) -> Optional[float]:
    """Transit depth in ppt from a LOCAL out-of-transit baseline, or None.

    Two deliberate choices, each fixing a distinct bias in the BLS box depth:

    * the transit CORE (``|phase| <= core_frac x duration``) is used, so
      partially-illuminated ingress/egress cadences do not dilute the depth the
      way a box fitted at or beyond the true T14 does;
    * the baseline is LOCAL (``gap_frac..baseline_frac x duration`` either
      side), so any residual long-timescale trend cancels instead of biasing
      the depth.

    Medians throughout — one outlying cadence must never set a depth.
    """
    phase = ((time_arr - epoch + 0.5 * period) % period) - 0.5 * period
    a = np.abs(phase)
    in_transit = a <= core_frac * duration
    out_transit = (a >= gap_frac * duration) & (a <= baseline_frac * duration)
    if int(in_transit.sum()) < min_in or int(out_transit.sum()) < min_out:
        return None
    f_in = float(np.nanmedian(flux[in_transit]))
    f_out = float(np.nanmedian(flux[out_transit]))
    if not (np.isfinite(f_in) and np.isfinite(f_out)) or f_out <= 0.0:
        return None

    depth = f_out - f_in
    if depth <= 0.0:
        return None

    # Contamination guard. The baseline annulus is placed relative to the
    # FITTED duration; when that badly underestimates the true T14 the annulus
    # lands INSIDE the transit, the "baseline" is itself depressed, and the
    # depth comes out silently and badly wrong.
    #
    # The test is deliberately LOCAL: it compares the inner half of the annulus
    # against the outer half. Out of transit those are level, whatever the star
    # is doing on longer timescales. Inside the transit the flux climbs steeply
    # outward, so a gradient comparable to the depth itself is the signature.
    #
    # An earlier version of this guard compared the annulus against the light
    # curve's GLOBAL median and was wrong for exactly the stars this pass helps
    # most: on spotted, active HD 63433 the local baseline legitimately sits
    # well below the global median - absorbing residual trend is the whole
    # reason the baseline is local - and the guard threw away a measurement
    # that had cut that planet's depth error from 101% to 31%.
    mid = 0.5 * (gap_frac + baseline_frac) * duration
    inner = out_transit & (a < mid)
    outer = out_transit & (a >= mid)
    if int(inner.sum()) >= 3 and int(outer.sum()) >= 3:
        gradient = float(np.nanmedian(flux[outer]) - np.nanmedian(flux[inner]))
        if np.isfinite(gradient) and gradient > max_baseline_contamination * depth:
            return None

    return depth / f_out * 1000.0


def _remeasure_depths(
    lc_raw: lk.LightCurve,
    planets: list[dict],
    *,
    sigma_clip: float,
    window_days: Optional[float],
    duration_max: float,
    mask_width_factor: float,
    notes: list[str],
    stellar: Optional[StellarParams] = None,
    do_fit: bool = True,
    lc_fallback: Optional[lk.LightCurve] = None,
) -> int:
    """Characterise accepted planets on an all-transits-masked flatten.

    When the union of the accepted transit masks would cover more than
    MAX_MASK_REMOVAL_FRACTION of the cadences (an ultra-short-period
    candidate under a 7-duration mask: WASP-18 b, GPX-1 b) no all-masked
    flatten can be built; the transit fit then runs on ``lc_fallback`` (the
    two-pass flatten the search used) when one is supplied, so vetting still
    gets a fit, and the depth estimator is skipped as before.

    Prompt 3, part A: the flat-bottom estimator below is kept only as the
    fallback; when ``do_fit`` is set every planet gets a limb-darkened
    transit fit (:func:`tesshunter.transit_fit.fit_transit`) on the same
    unbinned, all-masked flatten, its result is stored on the planet row as
    ``fit`` and its maximum model depth becomes ``depth_ppt``
    (``depth_source = "fit"``). The BLS box depth stays in ``depth_ppt_bls``
    and the flat-bottom measurement in ``depth_ppt_flat``.

    The shipped depth is the raw BLS box depth, never re-measured against the
    data after detrending, and the two-pass flatten protects only ONE
    candidate — so every other planet is partially divided out by a trend
    fitted through its own transits. Here the trend is re-fitted with EVERY
    accepted ephemeris masked, and depth is measured on UNBINNED cadences so
    binning no longer smears short transits.

    Runs after detection AND after vetting, so it cannot change which planets
    are found or how they are labelled. Every failure path keeps the BLS depth.

    Returns the number of planets whose depth was replaced.
    """
    if not planets:
        return 0
    try:
        t_raw = np.asarray(lc_raw.time.value, dtype=float)
        union = np.zeros(t_raw.shape, dtype=bool)
        for p in planets:
            union |= _build_transit_mask(
                t_raw, float(p["period_days"]), float(p["epoch_btjd"]),
                float(p["duration_days"]), mask_width_factor,
            )
        frac = float(union.mean()) if union.size else 1.0
        if frac > MAX_MASK_REMOVAL_FRACTION:
            notes.append(
                f"Depth re-measurement skipped: masking all {len(planets)} accepted "
                f"planet(s) would cover {100.0 * frac:.0f}% of cadences"
            )
            if do_fit and lc_fallback is not None:
                n_fb = _fit_planets_on(lc_fallback, planets, stellar=stellar)
                notes.append(
                    f"Transit fit run on the search's two-pass flatten instead for "
                    f"{n_fb}/{len(planets)} planet(s) (depth kept from the BLS box)"
                )
            return 0

        lc2, rec2 = preprocessing.preprocess(
            lc_raw, sigma=sigma_clip, do_flatten=True, window_days=window_days,
            transit_mask=union, max_transit_duration_days=duration_max,
        )
        if not rec2.flattened:
            notes.append(
                "Depth re-measurement skipped: mask-all flatten failed "
                f"({rec2.flatten_error})"
            )
            return 0

        t = np.asarray(lc2.time.value, dtype=float)
        f = np.asarray(lc2.flux.value, dtype=float)
        try:
            e = np.asarray(lc2.flux_err.value, dtype=float)
            if e.shape != t.shape:
                e = None
        except Exception:
            e = None
        ok = np.isfinite(t) & np.isfinite(f)
        t, f = t[ok], f[ok]
        if e is not None:
            e = e[ok]
        cadence_days = float(np.median(np.diff(np.sort(t)))) if t.size > 1 else None

        # The light curve's own out-of-transit level, used by the contamination
        # guard. A median over the whole curve is dominated by out-of-transit
        # cadences for any plausible transit duty cycle.
        baseline_ref = float(np.nanmedian(f)) if f.size else 1.0
        if not np.isfinite(baseline_ref) or baseline_ref <= 0.0:
            baseline_ref = 1.0

        n_done = 0
        n_fit = 0
        for p in planets:
            if "depth_ppt_bls" not in p:      # never clobber the original on a re-run
                p["depth_ppt_bls"] = float(p["depth_ppt"])

            # Exclude the OTHER accepted planets' transits before measuring
            # this one. The local baseline annulus reaches 2.5 transit
            # durations either side, which in a compact multi-planet system
            # regularly catches a sibling's transit and depresses the very
            # baseline the depth is measured against.
            others = np.zeros(t.shape, dtype=bool)
            for q in planets:
                if q is p:
                    continue
                others |= _build_transit_mask(
                    t, float(q["period_days"]), float(q["epoch_btjd"]),
                    float(q["duration_days"]), 1.0,
                )
            if others.any():
                t_p, f_p = t[~others], f[~others]
                e_p = e[~others] if e is not None else None
            else:
                t_p, f_p, e_p = t, f, e

            d = _measure_depth_at_ephemeris(
                t_p, f_p, float(p["period_days"]), float(p["epoch_btjd"]),
                float(p["duration_days"]), baseline_ref=baseline_ref,
            )
            flat_ok = d is not None and np.isfinite(d) and d > 0.0
            p["depth_ppt_flat"] = float(d) if flat_ok else None
            if flat_ok:
                p["depth_ppt"] = float(d)
                p["depth_source"] = "remeasured"
                n_done += 1
            else:
                p["depth_source"] = "bls"

            if not do_fit:
                continue
            # ── Limb-darkened transit fit (prompt 3, part A) ──────────────────
            try:
                fit = transit_fit.fit_transit(
                    t_p, f_p, e_p,
                    period=float(p["period_days"]), t0=float(p["epoch_btjd"]),
                    duration=float(p["duration_days"]),
                    depth_ppt=float(p["depth_ppt"]),
                    exp_time_days=cadence_days, stellar=stellar,
                )
            except Exception as exc:                              # pragma: no cover
                logger.warning("Transit fit failed for planet %s (%s)", p.get("planet_num"), exc)
                p["fit"] = {"success": False, "message": str(exc)}
                continue
            p["fit"] = fit.to_dict()
            # The fitted depth replaces the box depth only for a transit-like
            # geometry: a converged fit with a real dip, Rp/R* off its upper
            # bound and a duration below MAX_FIT_DURATION_FRACTION of the
            # period (an ephemeris with no out-of-transit baseline, such as a
            # 0.3-day "planet" with a 0.12-day duration, keeps the BLS depth).
            bls_dur = float(p["duration_days"])
            usable = (
                fit.depth_significant and fit.duration_days > 0.0
                and fit.rp_rs < 0.85
                and fit.duration_days < MAX_FIT_DURATION_FRACTION * float(p["period_days"])
                # the fit must describe the SAME event the search found: a
                # duration far from the box duration (HD 63433 c's fit ran to
                # a 29-hour transit on rotation residuals) is not trusted
                and FIT_DURATION_RATIO_RANGE[0] * bls_dur <= fit.duration_days <= FIT_DURATION_RATIO_RANGE[1] * bls_dur
            )
            if fit.success and not usable:
                p["fit_depth_rejected"] = (
                    "insignificant" if not fit.depth_significant else "geometry"
                )
            if usable:
                p["depth_ppt"] = float(fit.depth_ppt)
                p["depth_source"] = "fit"
                p["depth_ppt_err"] = float(fit.depth_err)
                p["rp_rs"] = float(fit.rp_rs)
                p["a_rs"] = float(fit.a_rs)
                p["impact_b"] = float(fit.b)
                p["duration_fit_days"] = float(fit.duration_days)
                p["rp_rearth"] = fit.rp_rearth
                p["a_rs_inconsistent"] = bool(fit.a_rs_inconsistent)
                n_fit += 1
        if n_done or n_fit:
            notes.append(
                f"Depth characterised for {len(planets)} planet(s) on an all-transits-masked, "
                f"unbinned flatten ({100.0 * frac:.0f}% of cadences held out of the trend "
                f"fit): {n_fit} from the limb-darkened transit fit, "
                f"{n_done - n_fit if n_done >= n_fit else 0} from the local flat-bottom "
                f"estimator, the rest from the BLS box"
            )
        return n_done
    except Exception as exc:                                  # pragma: no cover
        notes.append(f"Depth re-measurement failed ({exc}); BLS depths kept")
        logger.warning("Depth re-measurement failed (%s) — BLS depths kept", exc)
        return 0


def _fit_planets_on(
    lc: lk.LightCurve,
    planets: list[dict],
    *,
    stellar: Optional[StellarParams],
) -> int:
    """Transit fit for every planet on an already-detrended curve (other
    planets' transits masked at one duration); stores ``fit`` on each row,
    never touches ``depth_ppt``. Returns the number of converged fits."""
    try:
        t = np.asarray(lc.time.value, dtype=float)
        f = np.asarray(lc.flux.value, dtype=float)
        try:
            e = np.asarray(lc.flux_err.value, dtype=float)
            if e.shape != t.shape:
                e = None
        except Exception:
            e = None
        ok = np.isfinite(t) & np.isfinite(f)
        t, f = t[ok], f[ok]
        if e is not None:
            e = e[ok]
        cadence_days = float(np.median(np.diff(np.sort(t)))) if t.size > 1 else None
    except Exception as exc:                                      # pragma: no cover
        logger.warning("fallback fit: could not read the light curve (%s)", exc)
        return 0
    n_ok = 0
    for p in planets:
        others = np.zeros(t.shape, dtype=bool)
        for q in planets:
            if q is not p:
                others |= _build_transit_mask(
                    t, float(q["period_days"]), float(q["epoch_btjd"]), float(q["duration_days"]), 1.0,
                )
        sel = ~others if others.any() else np.ones(t.shape, dtype=bool)
        try:
            fit = transit_fit.fit_transit(
                t[sel], f[sel], e[sel] if e is not None else None,
                period=float(p["period_days"]), t0=float(p["epoch_btjd"]),
                duration=float(p["duration_days"]), depth_ppt=float(p["depth_ppt"]),
                exp_time_days=cadence_days, stellar=stellar,
            )
        except Exception as exc:                                  # pragma: no cover
            p["fit"] = {"success": False, "message": str(exc)}
            continue
        p["fit"] = fit.to_dict()
        p["fit"]["on_fallback_flatten"] = True
        if fit.success:
            n_ok += 1
    return n_ok


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def _two_pass_flatten(
    lc_raw: lk.LightCurve,
    lc_clean: lk.LightCurve,
    prep_rec: preprocessing.PreprocessingRecord,
    *,
    sigma_clip: float,
    window_days: Optional[float],
    duration_max: float,
    bin_minutes: float,
    period_min: float,
    period_max: float,
    duration_min: float,
    n_periods: Optional[int],
    snr_min: float,
    mask_width_factor: float,
    artifact_periods: list[float],
    grid_cap: Optional[int] = None,
) -> tuple[lk.LightCurve, preprocessing.PreprocessingRecord, Optional[dict]]:
    """Second flatten pass with the strongest candidate masked (defect P4).

    Runs one broad BLS on the first-pass product; when the top non-artifact
    candidate passes ``snr_min``, builds an in-transit mask at that ephemeris
    over the PRE-flatten light curve and re-runs preprocessing with
    ``transit_mask=``.  Any failure falls back to the first-pass product with
    a logged warning and a note on the record.

    Returns
    -------
    (lc_clean, prep_rec, pass1_candidate) — the light curve and record to use
    for detection, and the masked candidate's ephemeris dict (None when the
    second pass did not run).
    """
    try:
        binned = preprocessing.bin_lightcurve(lc_clean, bin_minutes=bin_minutes)
        _, _, cands = bls_search.run_bls(
            binned,
            period_min=period_min,
            period_max=period_max,
            duration_min=duration_min,
            duration_max=duration_max,
            top_n=3,
            suppress_periods=artifact_periods or None,
            n_periods=n_periods,
            n_max=grid_cap,
        )
        cand = None
        for _, row in cands.iterrows():
            if _is_artifact_period(float(row["period_days"]), artifact_periods):
                continue
            if float(row["snr"]) >= snr_min:
                cand = row
            break  # only the top non-artifact candidate is considered
        if cand is None:
            logger.info(
                "Two-pass flatten: no candidate above SNR %.1f in the first "
                "pass — keeping single-pass product.", snr_min,
            )
            return lc_clean, prep_rec, None

        period = float(cand["period_days"])
        epoch = float(cand["epoch_btjd"])
        duration = float(cand["duration_days"])
        tmask = _build_transit_mask(
            np.asarray(lc_raw.time.value, dtype=float),
            period, epoch, duration, mask_width_factor,
        )
        masked_frac = float(tmask.mean()) if len(tmask) else 0.0
        if not tmask.any() or masked_frac > 0.9:
            logger.warning(
                "Two-pass flatten: mask at P=%.4f d would cover %.0f%% of "
                "cadences — keeping single-pass product.",
                period, 100.0 * masked_frac,
            )
            return lc_clean, prep_rec, None

        logger.info(
            "Two-pass flatten: masking candidate P=%.4f d (SNR %.1f, %.0f%% "
            "of cadences) and re-flattening.",
            period, float(cand["snr"]), 100.0 * masked_frac,
        )
        lc2, rec2 = preprocessing.preprocess(
            lc_raw,
            sigma=sigma_clip,
            do_flatten=True,
            window_days=window_days,
            transit_mask=tmask,
            max_transit_duration_days=duration_max,
        )
        if not rec2.flattened:
            logger.warning(
                "Two-pass flatten: second pass FAILED (%s) — falling back to "
                "the first-pass product.", rec2.flatten_error,
            )
            prep_rec.notes.append(
                "Two-pass flatten: second pass failed "
                f"({rec2.flatten_error}); first-pass product used"
            )
            return lc_clean, prep_rec, None

        pass1_candidate = {
            "period_days": period,
            "epoch_btjd": epoch,
            "duration_days": duration,
            "snr": float(cand["snr"]),
            "masked_fraction": masked_frac,
        }
        rec2.notes.append(
            f"Two-pass flatten: candidate at P={period:.4f} d masked "
            f"({100.0 * masked_frac:.0f}% of cadences) before the trend fit"
        )
        return lc2, rec2, pass1_candidate

    except Exception as exc:
        logger.warning(
            "Two-pass flatten failed (%s) — falling back to the first-pass "
            "product.", exc,
        )
        prep_rec.notes.append(f"Two-pass flatten failed ({exc}); first-pass product used")
        return lc_clean, prep_rec, None


def pick_survivor(resolved_pool: list, rank_by: str = "composite"):
    """The accepted survivor of a detection pass among the candidates that passed
    every quality gate: the highest composite score (prompts 0-8; a row without a
    composite falls back to its SNR) or, under ``rank_by="snr"`` (prompt 10 Part 2b,
    the ``survey_p10_rank`` variant), the highest resolved SNR.  The composite floor
    of gate 4 has already been applied to every member of the pool."""
    if rank_by == "composite":
        key = lambda rn: float(rn[0].get("composite_score", rn[0]["snr"]))      # noqa: E731
    elif rank_by == "snr":
        key = lambda rn: float(rn[0]["snr"])                                       # noqa: E731
    else:
        raise ValueError(f"unknown rank_by {rank_by!r}: expected 'composite' or 'snr'")
    return max(resolved_pool, key=key)


def _detect_planets(
    lc_clean: lk.LightCurve,
    *,
    period_min: float,
    period_max: float,
    duration_min: float,
    duration_max: float,
    max_planets: int,
    bin_minutes: float,
    top_n: int,
    n_periods: Optional[int],
    snr_min: float,
    snr_min_resolved: float,
    min_event_completeness: float,
    min_composite_score: float,
    min_transits: int,
    mask_width_factor: float,
    artifact_periods: list[float],
    known_periods: dict[str, float],
    notes: list[str],
    time_budget_s: Optional[float] = None,
    grid_cap: Optional[int] = None,
    local_grid_cap: Optional[int] = None,
    stellar: Optional[StellarParams] = None,
    rank_by: str = "composite",
) -> tuple[list[dict], pd.DataFrame]:
    """Iterative detection loop ported from ``scripts/_cell_loop_src.py``.

    Each pass: bin the working LC, broad BLS (artifact periods suppressed),
    gate 1 on rank-1 raw SNR, then per-candidate alias resolution with the
    2% artifact skip applied both before and after resolution, gates 2–4
    (resolved SNR / event completeness / composite score), the NEW gate 5
    (``n_transits_observed >= min_transits``, defect B4), acceptance of the
    best survivor by composite score, transit masking with
    ``width_factor=mask_width_factor``, and a post-mask residual check.

    Robustness additions over the notebook loop: the loop stops cleanly when
    the working light curve drops below ``MIN_WORKING_CADENCES`` finite
    cadences or the BLS fails/returns empty, and a mask that would remove
    more than ``MAX_MASK_REMOVAL_FRACTION`` of cadences stops the loop after
    the planet is accepted instead of emptying the light curve.

    Returns
    -------
    (found_planets, first_pass_candidates) — accepted planet dicts and the
    raw BLS candidate table from the first pass (for reporting).
    """
    found_planets: list[dict] = []
    first_pass_candidates = pd.DataFrame()
    working_lc = lc_clean

    # A pass that finds only vetoed signals still MASKS the strongest of them
    # and continues, so a veto can never starve the search (see the empty-pool
    # branch below). Those passes do not produce a planet, so the loop needs
    # headroom beyond max_planets; MAX_VETO_PASSES bounds the extra work.
    detect_t0 = time.perf_counter()
    worst_pass_s = 0.0
    pass_start: Optional[float] = None

    for _idx in range(max_planets + MAX_VETO_PASSES):
        if len(found_planets) >= max_planets:
            break

        # Cost of the pass that just finished, whichever way it exited.
        now = time.perf_counter()
        if pass_start is not None:
            worst_pass_s = max(worst_pass_s, now - pass_start)
        pass_start = now

        # ── Wall-clock guard ──────────────────────────────────────────────────
        # A pass budget is a COUNT and says nothing about runtime, while callers
        # run under a hard per-target timeout. Overrunning it is far worse than
        # stopping early: the benchmark harness records `planets: []` for a
        # target that timed out, so a single overrun converts every recovered
        # planet on that target into a miss. Passes cost near-constant time
        # (masking removes only a few percent of cadences), so the slowest
        # completed pass predicts the next one.
        if time_budget_s is not None and worst_pass_s > 0.0:
            elapsed = now - detect_t0
            if elapsed + PASS_COST_SAFETY * worst_pass_s > time_budget_s:
                msg = (
                    f"Detection stopped before pass {_idx + 1}: another pass "
                    f"(~{PASS_COST_SAFETY * worst_pass_s:.0f} s) would not fit the "
                    f"{time_budget_s:.0f} s detection budget ({elapsed:.0f} s used)"
                )
                logger.warning(msg)
                notes.append(msg)
                break

        planet_num = len(found_planets) + 1
        logger.info("Detection pass %d (planet %d)", _idx + 1, planet_num)

        # ── Robustness: never BLS a (nearly) empty light curve ────────────────
        n_finite = _n_finite_cadences(working_lc)
        if n_finite < MIN_WORKING_CADENCES:
            msg = (
                f"Detection stopped before pass {planet_num}: only {n_finite} "
                f"finite cadences remain (< {MIN_WORKING_CADENCES})"
            )
            logger.warning(msg)
            notes.append(msg)
            break

        working_binned = preprocessing.bin_lightcurve(
            working_lc, bin_minutes=bin_minutes
        )

        # Binned cadence for gate 7: it decides whether the duration grid's
        # lower bound is resolvable at all on this data.
        _bt = np.asarray(working_binned.time.value, dtype=float)
        _bt = _bt[np.isfinite(_bt)]
        binned_cadence_days = (
            float(np.median(np.diff(np.sort(_bt)))) if _bt.size > 1 else 0.0
        )

        # ── Broad BLS (artifact periods suppressed before peak extraction) ────
        try:
            _, _, raw_cands = bls_search.run_bls(
                working_binned,
                period_min=period_min,
                period_max=period_max,
                duration_min=duration_min,
                duration_max=duration_max,
                top_n=top_n,
                suppress_periods=artifact_periods or None,
                n_periods=n_periods,
                n_max=grid_cap,
            )
        except Exception as exc:
            msg = f"Detection stopped at pass {planet_num}: BLS failed ({exc})"
            logger.warning(msg)
            notes.append(msg)
            break

        # Capture the genuine FIRST pass. planet_num is now len(found_planets)+1,
        # which stays 1 across veto passes, so it can no longer serve as the
        # "first pass" test without silently overwriting this table.
        if _idx == 0:
            first_pass_candidates = raw_cands.copy()

        if raw_cands.empty:
            logger.info("No BLS candidates returned — stopping.")
            break

        top = raw_cands.iloc[0]
        logger.info(
            "Broad BLS top: %.4f d  depth %.3f ppt  SNR %.1f  (%d candidates)",
            top["period_days"], top["depth_ppt"], top["snr"], len(raw_cands),
        )

        # Gate 1: fast exit when even rank-1 is clearly below threshold
        if float(top["snr"]) < snr_min:
            logger.info(
                "STOP (gate 1): top SNR %.1f < %.1f", top["snr"], snr_min
            )
            break

        # ── Try every top-N candidate; collect survivors ──────────────────────
        existing_df = pd.DataFrame(found_planets) if found_planets else None
        resolved_pool: list[tuple[pd.Series, int]] = []
        vetoed_pool: list[tuple[pd.Series, int, str]] = []

        logger.info("Resolving %d BLS candidate(s)...", len(raw_cands))
        for _, raw_cand in raw_cands.iterrows():
            p = float(raw_cand["period_days"])

            # Skip known instrument / sampling artifact periods
            if _is_artifact_period(p, artifact_periods):
                logger.info("[%.4f d]  artifact period — skip", p)
                continue

            try:
                resolved, _trial_table = bls_search.resolve_aliases_for_candidate(
                    working_binned,
                    raw_cand,
                    existing_candidates=existing_df,
                    period_min=period_min,
                    period_max=period_max,
                    duration_min=duration_min,
                    duration_max=duration_max,
                    local_n_max=local_grid_cap,
                )
            except Exception as exc:
                logger.warning(
                    "[%.4f d]  alias resolution failed (%s) — skip", p, exc
                )
                continue

            ev_comp = float(resolved.get("event_completeness", float("nan")))
            comp_score = float(resolved.get("composite_score", resolved["snr"]))
            r_p = float(resolved["period_days"])

            # Also skip if alias resolution chose an artifact period
            if _is_artifact_period(r_p, artifact_periods):
                logger.info(
                    "[%.4f d -> %.4f d]  resolved to artifact — skip", p, r_p
                )
                continue

            if float(resolved["snr"]) < snr_min_resolved:
                logger.info(
                    "[%.4f d -> %.4f d]  SNR %.1f < %.1f  (gate 2)",
                    p, r_p, resolved["snr"], snr_min_resolved,
                )
                continue
            if not (ev_comp >= min_event_completeness):   # NaN-safe
                logger.info(
                    "[%.4f d -> %.4f d]  ev_comp %.2f < %.2f  (gate 3)",
                    p, r_p, ev_comp, min_event_completeness,
                )
                continue
            if comp_score < min_composite_score:
                logger.info(
                    "[%.4f d -> %.4f d]  composite %.2f < %.2f  (gate 4)",
                    p, r_p, comp_score, min_composite_score,
                )
                continue

            # Gate 5 (NEW, defect B4): require enough observed transit epochs.
            # Read n_transits_observed from the resolved row; recompute at the
            # resolved ephemeris when the row does not carry an honest count.
            n_obs = int(resolved.get("n_transits_observed", 0) or 0)
            if n_obs <= 0:
                n_obs = bls_search._count_observed_transits(
                    np.asarray(working_binned.time.value, dtype=float),
                    float(resolved["epoch_btjd"]),
                    r_p,
                    float(resolved["duration_days"]),
                )
            if n_obs < min_transits:
                logger.info(
                    "[%.4f d -> %.4f d]  n_transits_observed %d < %d  (gate 5"
                    "%s)",
                    p, r_p, n_obs, min_transits,
                    "; single event" if n_obs <= 1 else "",
                )
                continue

            # ── Vetoes (gates 6 and 7) ────────────────────────────────────────
            # Applied AFTER the quality gates so only genuinely strong signals
            # can be vetoed — a veto must never be spent on noise. A vetoed
            # candidate is a real feature of the light curve (residual ringing
            # or an unresolvable-duration systematic); it is not reported as a
            # planet, but it is still eligible to be MASKED so the search can
            # keep going. See the empty-pool branch below.

            # Gate 6: ratio-1 neighbourhood veto. Masking an accepted planet
            # leaves correlated residual power a few percent away in period,
            # which a later pass re-detects as a new planet. Nothing else
            # carries accepted periods forward: suppress_periods gets only the
            # static artifact list, and the composite's `overlap` term is
            # epoch-based, so ringing at a drifting epoch produces no overlap.
            # HARMONICS ARE NOT SUPPRESSED — see RINGING_PERIOD_TOL.
            near = _ringing_neighbour(r_p, found_planets)
            if near is not None:
                logger.info(
                    "[%.4f d -> %.4f d]  within %.1f%% of accepted planet %d "
                    "(%.4f d) — residual ringing, vetoed  (gate 6)",
                    p, r_p, 100.0 * RINGING_PERIOD_TOL,
                    near["planet_num"], near["period_days"],
                )
                vetoed_pool.append((resolved, n_obs, "ringing"))
                continue

            # Gate 7: a duration pinned on an unresolvable grid floor. When
            # duration_min is below ~2 binned cadences no transit that short
            # can be measured at all, so a best fit landing exactly there is
            # the optimiser against a rail — characteristically a sharp
            # single-bin residual fitted as an absurdly deep box.
            if _duration_is_railed(
                float(resolved["duration_days"]), duration_min, binned_cadence_days
            ):
                # Second condition (prompt 3, part C3): the railed box must
                # also be too deep to be a planet. A shallow railed fit is
                # kept and left to vetting.
                rp_rs_box = _box_rp_rs(float(resolved["depth_ppt"]))
                if rp_rs_box > GATE7_MIN_RP_RS:
                    logger.info(
                        "[%.4f d -> %.4f d]  duration pinned at the unresolvable "
                        "grid floor %.5f d (< %.1f binned cadences of %.5f d) and "
                        "box depth implies Rp/R* %.3f > %.2f — vetoed  (gate 7)",
                        p, r_p, duration_min, MIN_CADENCES_PER_DURATION,
                        binned_cadence_days, rp_rs_box, GATE7_MIN_RP_RS,
                    )
                    vetoed_pool.append((resolved, n_obs, "railed duration"))
                    continue
                logger.info(
                    "[%.4f d -> %.4f d]  duration railed at %.5f d but box depth "
                    "implies Rp/R* %.3f <= %.2f — kept  (gate 7 second condition)",
                    p, r_p, duration_min, rp_rs_box, GATE7_MIN_RP_RS,
                )

            logger.info(
                "[%.4f d -> %.4f d]  SNR %.1f  ev_comp %.2f  composite %.2f  "
                "n_transits %d  PASS",
                p, r_p, resolved["snr"], ev_comp, comp_score, n_obs,
            )
            resolved_pool.append((resolved, n_obs))

        if not resolved_pool:
            if not vetoed_pool:
                logger.info("No candidate survived quality gates — stopping.")
                break
            # Every survivor was vetoed. Mask the strongest of them and carry
            # on: the signal is real (it passed every quality gate) and simply
            # is not a planet, so removing it is what lets a later pass reach
            # the planets hiding underneath. Without this, a target whose
            # top-N list is dominated by systematics loses the whole search —
            # on TRAPPIST-1 that cost 6 of 7 accepted candidates.
            v_res, _v_obs, v_why = max(
                vetoed_pool,
                key=lambda rv: float(rv[0].get("composite_score", rv[0]["snr"])),
            )
            v_p = float(v_res["period_days"])
            n_before = len(working_lc)
            masked_lc = preprocessing.mask_transits(
                working_lc, period=v_p, epoch=float(v_res["epoch_btjd"]),
                duration=float(v_res["duration_days"]),
                width_factor=mask_width_factor,
            )
            frac_removed = 1.0 - len(masked_lc) / max(n_before, 1)
            if frac_removed > MAX_MASK_REMOVAL_FRACTION:
                msg = (
                    f"Detection stopped: masking the vetoed {v_why} signal at "
                    f"P={v_p:.4f} d would remove {100.0 * frac_removed:.0f}% of cadences"
                )
                logger.warning(msg)
                notes.append(msg)
                break
            msg = (
                f"Vetoed {v_why} signal at P={v_p:.4f} d "
                f"(depth {float(v_res['depth_ppt']):.3f} ppt, SNR "
                f"{float(v_res['snr']):.1f}) masked but NOT reported as a planet"
            )
            logger.info(msg)
            notes.append(msg)
            working_lc = masked_lc
            continue

        # ── Pick best survivor by composite score (or resolved SNR, prompt 10) ─
        resolved, n_obs = pick_survivor(resolved_pool, rank_by)
        ev_comp = float(resolved.get("event_completeness", float("nan")))
        comp_score = float(resolved.get("composite_score", resolved["snr"]))
        r_p = float(resolved["period_days"])

        logger.info(
            "Accepted planet %d: [%s]  P = %.6f d  depth %.3f ppt  SNR %.1f  "
            "ev_comp %.2f  composite %.2f  n_transits %d",
            planet_num, resolved.get("harmonic_label", "P"), r_p,
            resolved["depth_ppt"], resolved["snr"], ev_comp, comp_score, n_obs,
        )

        found_planets.append({
            "planet_num":          planet_num,
            "period_days":         r_p,
            "epoch_btjd":          float(resolved["epoch_btjd"]),
            "duration_days":       float(resolved["duration_days"]),
            "depth_ppt":           float(resolved["depth_ppt"]),
            "power":               float(resolved.get("power", 0.0)),
            "snr":                 float(resolved["snr"]),
            "sde":                 float(resolved.get("sde", 0.0)),
            "event_completeness":  ev_comp,
            "n_transits_observed": int(n_obs),
            "single_event":        bool(n_obs <= 1),
            "harmonic_label":      str(resolved.get("harmonic_label", "P")),
            "odd_even_retest":     bool(resolved.get("odd_even_retest", False)),
            "carves_exclusion_zone": True,
        })

        # Gate 6 anchor plausibility (prompt 3, part C2): decide now, from a
        # cheap fit on the working curve, whether this candidate may veto
        # later neighbours as its ringing.
        carve, gate_fit = _anchor_plausibility(working_binned, found_planets[-1], stellar)
        found_planets[-1]["carves_exclusion_zone"] = bool(carve)
        found_planets[-1]["gate_fit"] = gate_fit
        if not carve:
            msg = (
                f"Planet {planet_num} at P={r_p:.4f} d does not carve a gate-6 exclusion "
                f"zone: {gate_fit.get('reason', '')}"
            )
            logger.info(msg)
            notes.append(msg)

        # ── Mask and verify ───────────────────────────────────────────────────
        n_before = len(working_lc)
        masked_lc = preprocessing.mask_transits(
            working_lc,
            period=r_p,
            epoch=float(resolved["epoch_btjd"]),
            duration=float(resolved["duration_days"]),
            width_factor=mask_width_factor,
        )
        frac_removed = 1.0 - len(masked_lc) / max(n_before, 1)
        if frac_removed > MAX_MASK_REMOVAL_FRACTION:
            msg = (
                f"Detection stopped after planet {planet_num}: masking "
                f"P={r_p:.4f} d (width_factor={mask_width_factor:g}) would "
                f"remove {100.0 * frac_removed:.0f}% of cadences"
            )
            logger.warning(msg)
            notes.append(msg)
            break
        working_lc = masked_lc

        # ── Post-mask check + known-period diagnostic (non-fatal) ─────────────
        try:
            if _n_finite_cadences(working_lc) >= MIN_WORKING_CADENCES:
                check_binned = preprocessing.bin_lightcurve(
                    working_lc, bin_minutes=bin_minutes
                )
                _, _, chk = bls_search.run_bls(
                    check_binned,
                    period_min=r_p * 0.98,
                    period_max=r_p * 1.02,
                    duration_min=duration_min,
                    duration_max=duration_max,
                    top_n=3,
                    n_max=local_grid_cap,
                )
                if chk.empty:
                    logger.info(
                        "Post-mask check (%.4f d): signal gone.", r_p
                    )
                else:
                    psnr = float(chk.iloc[0]["snr"])
                    logger.info(
                        "Post-mask check (%.4f d): SNR = %.1f%s",
                        r_p, psnr,
                        "  WARNING: still elevated — check width_factor"
                        if psnr > 5 else "  OK",
                    )
                for name, kp in known_periods.items():
                    _, _, local = bls_search.run_bls(
                        check_binned,
                        period_min=kp * 0.98,
                        period_max=kp * 1.02,
                        duration_min=duration_min,
                        duration_max=duration_max,
                        top_n=3,
                        n_max=local_grid_cap,
                    )
                    if local.empty:
                        logger.info("  %s (%.4f d): no signal", name, kp)
                    else:
                        b = local.iloc[0]
                        logger.info(
                            "  %s (%.4f d): P=%.4f d  depth=%.3f ppt  SNR=%.1f",
                            name, kp, b["period_days"], b["depth_ppt"], b["snr"],
                        )
        except Exception as exc:
            logger.debug("Post-mask check failed (non-fatal): %s", exc)

    logger.info(
        "Detection complete — %d candidate(s) found", len(found_planets)
    )
    return found_planets, first_pass_candidates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_target(
    target: str | int,
    mission: str = "TESS",
    sector: Optional[int | list[int]] = None,
    campaign: Optional[int | list[int]] = None,
    quarter: Optional[int | list[int]] = None,
    author: Optional[str | list[str]] = None,
    exptime: str | int | None = "auto",
    quality_bitmask: str = "default",
    max_results: Optional[int] = None,
    max_units: Optional[int] = 3,
    period_min: float = 1.0,
    period_max: float = 13.0,
    duration_min: float = 0.01,
    duration_max: float = 0.15,
    max_planets: int = 5,
    bin_minutes: float = 10.0,
    top_n: int = 20,
    n_periods: Optional[int] = None,
    snr_min: float = 5.0,
    snr_min_resolved: float = 5.0,
    min_event_completeness: float = 0.5,
    min_composite_score: float = 3.0,
    min_transits: int = 2,
    sigma_clip: float = 4.0,
    mask_width_factor: float = 7.0,
    artifact_periods: Optional[list[float]] = None,
    known_periods: Optional[dict[str, float]] = None,
    window_days: Optional[float] = None,
    do_flatten: bool = True,
    two_pass_flatten: bool = True,
    remeasure_depths: bool = True,
    time_budget_s: Optional[float] = None,
    stellar_radius_rsun: Optional[float] = None,
    stellar_rotation_period_days: Optional[float] = None,
    is_known_toi: bool = False,
    do_crossmatch: bool = False,
    hard_stop: bool = True,
    generate_report: bool = False,
    report_dir: Optional[Path] = None,
    summary_csv: Optional[Path] = None,
    target_label: Optional[str] = None,
    grid_cap: Optional[int] = None,
    local_grid_cap: Optional[int] = None,
    stellar_params=None,
    fetch_stellar_params: bool = True,
) -> SearchTargetResult:
    """Run the full search pipeline for one target and return a structured result.

    ``stellar_params`` (a :class:`tesshunter.stellar.StellarParams` or dict)
    supplies Teff, log g, radius, mass and density for the transit fit and
    the a/R* consistency test; when absent and ``fetch_stellar_params`` is
    True the TIC is queried once per star (cached under ``data/cache/tic``,
    non-fatal) for TESS targets with a numeric id.

    Parameters
    ----------
    target:
        TIC ID (int), "EPIC NNN"/"KIC NNN" string, or a resolvable name.
    mission:
        "TESS", "K2", or "Kepler".
    sector / campaign / quarter:
        Mission-specific observing-unit filter (None = all available).
    author:
        Pipeline author filter ("SPOC", "K2", ...). Never dropped silently —
        any retry without it is recorded in ``provenance["fallback_events"]``.
    exptime:
        Cadence filter; the "auto" sentinel maps author SPOC to 120 s and
        otherwise searches all cadences (selection then happens via the
        dedup priority).
    quality_bitmask:
        Lightkurve quality bitmask for the download ("default", "hard", ...).
    max_results:
        Cap on raw search results downloaded (None = no cap).
    max_units:
        Cap on DISTINCT observing units stitched (None = no cap).
    period_min / period_max / duration_min / duration_max:
        BLS search ranges in days.
    max_planets:
        Maximum detection passes (planets accepted).
    bin_minutes:
        Bin width for the working light curve fed to the BLS.
    top_n:
        BLS peaks examined per pass.
    n_periods:
        BLS frequency-grid override; None uses the corrected auto grid
        (oversample 4, floor 500, cap 20 000).
    snr_min / snr_min_resolved / min_event_completeness / min_composite_score:
        Detection gates 1–4 (see :func:`_detect_planets`).
    min_transits:
        Gate 5 — minimum ``n_transits_observed`` for acceptance (default 2,
        which rejects single-event candidates; defect B4).
    sigma_clip:
        Upper-tail sigma-clip threshold for preprocessing.
    mask_width_factor:
        Transit-mask half-width in units of duration (accepted planets are
        masked with this factor before the next pass; also sizes the
        two-pass flatten mask).
    artifact_periods:
        Known instrument periods (days) to suppress/skip (e.g. [1.0] for K2).
    known_periods:
        Optional {name: period} dict — after each accepted planet is masked,
        the loop logs whether these periods remain in the residual.
    window_days:
        Detrending window in days. None means the fixed default
        (:data:`tesshunter.preprocessing.DEFAULT_WINDOW_DAYS` = 1.0 day).
    do_flatten:
        Whether to detrend at all.
    two_pass_flatten:
        Enable the P4 two-pass flatten (mask the strongest first-pass
        candidate, re-flatten). Falls back to the single-pass product on any
        failure.
    time_budget_s:
        Soft wall-clock budget in seconds for this target. When set, the
        detection loop refuses to start a pass that its own measured pass cost
        says will not fit, so a caller running under a hard timeout is not
        killed mid-run. None (the default) means unlimited, preserving the
        previous behaviour exactly.
    remeasure_depths:
        Re-measure every accepted planet's depth after vetting, against a
        local out-of-transit baseline on a flatten that masks ALL accepted
        ephemerides, using unbinned cadences. Corrects both trend
        self-absorption (the two-pass flatten protects only one candidate) and
        binning dilution. Cannot change which planets are found or how they
        are vetted; falls back to the BLS box depth on any failure.
    stellar_radius_rsun / stellar_rotation_period_days:
        Stellar parameters forwarded to vetting (radius-aware depth veto).
    is_known_toi:
        Forwarded to vetting; also set from the crossmatch when
        ``do_crossmatch=True``.
    hard_stop:
        When True (default) and ``do_crossmatch`` is on, a target whose TIC ID
        appears in any known-object catalog (TOI, CTOI, NASA archive, TESS EB,
        SPOC TCE) is returned BEFORE download with a ``HARD STOP`` note and no
        search.  Known objects within one TESS pixel are recorded as a FLAG
        note; the search still runs.
    do_crossmatch:
        When True, run the known-object cross-match before download (needs
        network). ``catalog_ok`` passed to vetting is True unless a
        crossmatch was attempted and failed.
    generate_report:
        Write a markdown report (planet 1) and upsert every planet into the
        candidate summary CSV with its REAL per-planet verdict. Report
        failures never kill the search result.
    report_dir:
        Output directory override for the markdown report.
    summary_csv:
        Summary CSV path (default ``outputs/candidates/candidate_summary.csv``).
    target_label:
        Human-readable label for reports (default derived from ``target``).
    grid_cap / local_grid_cap:
        Upper bounds on the broad-search and alias-refinement period grids.
        None (the default) keeps ``run_bls``'s 20 000-point cap for both, so
        the benchmark behaviour is unchanged; the survey sets them from its
        own cost measurements.

    Returns
    -------
    :class:`SearchTargetResult` — see its docstring for the ``to_dict()``
    key contract.
    """
    artifact_list = [float(p) for p in (artifact_periods or [])]
    known = {str(k): float(v) for k, v in (known_periods or {}).items()}
    label = target_label or (
        f"TIC {target}" if isinstance(target, (int, np.integer)) else str(target)
    )

    result = SearchTargetResult(
        target=target,
        mission=mission,
        params=_to_native({
            "sector": sector, "campaign": campaign, "quarter": quarter,
            "author": author, "exptime": exptime, "max_results": max_results,
            "max_units": max_units, "period_min": period_min,
            "period_max": period_max, "duration_min": duration_min,
            "duration_max": duration_max, "max_planets": max_planets,
            "bin_minutes": bin_minutes, "top_n": top_n, "n_periods": n_periods,
            "snr_min": snr_min, "snr_min_resolved": snr_min_resolved,
            "min_event_completeness": min_event_completeness,
            "min_composite_score": min_composite_score,
            "min_transits": min_transits, "sigma_clip": sigma_clip,
            "mask_width_factor": mask_width_factor,
            "artifact_periods": artifact_list, "window_days": window_days,
            "stellar_radius_rsun": stellar_radius_rsun,
            "is_known_toi": is_known_toi,
        }),
    )
    logger.info("search_target: %s  mission=%s  author=%s", label, mission, author)

    # ── Stage 0: known-object hard stop ───────────────────────────────────────
    # Runs BEFORE any download.  A catalog fetch failure propagates as
    # CatalogFetchError: the run fails loudly rather than searching a target
    # whose known-object status could not be verified.
    catalog_ok = True
    crossmatch_summary = "Catalog crossmatch not attempted."
    tic_id = _numeric_id(target)
    if do_crossmatch:
        if tic_id is not None and mission.upper() == "TESS":
            from . import catalog_crossmatch
            try:
                xm = catalog_crossmatch.crossmatch(int(tic_id))
            except catalog_crossmatch.CatalogFetchError:
                raise
            except Exception as exc:
                raise catalog_crossmatch.CatalogFetchError(
                    f"Catalog crossmatch failed for {label}: {exc}"
                ) from exc
            crossmatch_summary = xm.get("summary_str", crossmatch_summary)
            is_known_toi = bool(
                is_known_toi
                or xm.get("is_known_toi")
                or xm.get("is_confirmed_planet")
            )
            result.crossmatch = {
                "status": xm.get("status"),
                "summary": crossmatch_summary,
                "catalog_versions": xm.get("catalog_versions"),
                "hard_stop": xm.get("hard_stop"),
            }
            if hard_stop and xm.get("rejected"):
                msg = f"HARD STOP: {crossmatch_summary}"
                logger.warning("%s: %s", label, msg)
                result.notes.append(msg)
                result.provenance = {
                    "products": [], "units_used": [], "units_all": [],
                    "fallback_events": [], "n_products_downloaded": 0,
                }
                return result
            if xm.get("flagged"):
                result.notes.append(f"FLAG: {crossmatch_summary}")
        else:
            crossmatch_summary = (
                "Catalog crossmatch skipped (no numeric TIC id or non-TESS mission)."
            )

    # ── Stage 0.5: stellar parameters (fit, density test, Rp) ─────────────────
    stellar = _resolve_stellar(
        stellar_params,
        tic_id if (mission.upper() == "TESS" and tic_id is not None) else None,
        fetch_stellar_params, stellar_radius_rsun,
    )
    result.stellar = stellar.to_dict() if stellar is not None else None

    # ── Stage 1: download ─────────────────────────────────────────────────────
    t0 = time.perf_counter()
    lcc = search_and_download_lc(
        target,
        mission=mission,
        sector=sector,
        campaign=campaign,
        quarter=quarter,
        author=author,
        exptime=exptime,
        quality_bitmask=quality_bitmask,
        max_results=max_results,
    )
    if lcc is None or len(lcc) == 0:
        result.timings["download"] = time.perf_counter() - t0
        msg = f"No light curves could be downloaded for {label} ({mission})"
        logger.error(msg)
        result.notes.append(msg)
        result.provenance = {
            "products": [], "units_used": [], "units_all": [],
            "fallback_events": [], "n_products_downloaded": 0,
        }
        return result

    units_all = observing_units_available(lcc, mission)
    fallback_events = list(getattr(lcc, "tesshunter_events", []) or [])

    lc_raw = stitch_collection(lcc, dedupe=True, max_units=max_units, mission=mission)
    products = list(lc_raw.meta.get("TESSHUNTER_PROVENANCE", []) or [])
    units_used = list(lc_raw.meta.get("TESSHUNTER_UNITS", []) or [])
    if not units_used:
        units_used = [p["unit"] for p in products if p.get("unit") is not None]
    # n_sectors for vetting = number of DISTINCT units actually used
    n_sectors = len(set(units_used)) if units_used else max(len(products), 1)

    result.provenance = {
        "products": products,
        "units_used": sorted(set(units_used)),
        "units_all": units_all,
        "fallback_events": fallback_events,
        "n_products_downloaded": len(lcc),
    }
    result.n_sectors = n_sectors
    result.n_cadences_raw = len(lc_raw)
    result.timings["download"] = time.perf_counter() - t0

    # ── Stages 2-5 on the stitched light curve ────────────────────────────────
    return _run_search_stages(
        lc_raw, result,
        label=label, mission=mission, tic_id=tic_id, n_sectors=n_sectors,
        units_used=units_used,
        period_min=period_min, period_max=period_max,
        duration_min=duration_min, duration_max=duration_max,
        max_planets=max_planets, bin_minutes=bin_minutes, top_n=top_n,
        n_periods=n_periods, snr_min=snr_min, snr_min_resolved=snr_min_resolved,
        min_event_completeness=min_event_completeness,
        min_composite_score=min_composite_score, min_transits=min_transits,
        sigma_clip=sigma_clip, mask_width_factor=mask_width_factor,
        artifact_list=artifact_list, known=known, window_days=window_days,
        do_flatten=do_flatten, two_pass_flatten=two_pass_flatten,
        remeasure_depths=remeasure_depths, time_budget_s=time_budget_s,
        stellar_radius_rsun=stellar_radius_rsun,
        stellar_rotation_period_days=stellar_rotation_period_days,
        is_known_toi=is_known_toi, catalog_ok=catalog_ok,
        crossmatch_summary=crossmatch_summary, generate_report=generate_report,
        report_dir=report_dir, summary_csv=summary_csv,
        grid_cap=grid_cap, local_grid_cap=local_grid_cap,
        stellar=stellar,
    )


def search_light_curve(
    lc_raw: lk.LightCurve,
    *,
    target: str | int = "",
    mission: str = "TESS",
    n_sectors: Optional[int] = None,
    provenance: Optional[dict] = None,
    target_label: Optional[str] = None,
    period_min: float = 1.0,
    period_max: float = 13.0,
    duration_min: float = 0.01,
    duration_max: float = 0.15,
    max_planets: int = 5,
    bin_minutes: float = 10.0,
    top_n: int = 20,
    n_periods: Optional[int] = None,
    snr_min: float = 5.0,
    snr_min_resolved: float = 5.0,
    min_event_completeness: float = 0.5,
    min_composite_score: float = 3.0,
    min_transits: int = 2,
    sigma_clip: float = 4.0,
    mask_width_factor: float = 7.0,
    artifact_periods: Optional[list[float]] = None,
    known_periods: Optional[dict[str, float]] = None,
    window_days: Optional[float] = None,
    do_flatten: bool = True,
    two_pass_flatten: bool = True,
    remeasure_depths: bool = True,
    time_budget_s: Optional[float] = None,
    stellar_radius_rsun: Optional[float] = None,
    stellar_rotation_period_days: Optional[float] = None,
    is_known_toi: bool = False,
    catalog_ok: bool = True,
    grid_cap: Optional[int] = None,
    local_grid_cap: Optional[int] = None,
    stellar_params=None,
    fetch_stellar_params: bool = False,
    rank_by: str = "composite",
) -> SearchTargetResult:
    """Run stages 2-5 (preprocess, detect, vet, depth re-measure) on a stitched
    light curve the caller already holds.

    ``stellar_params`` / ``fetch_stellar_params`` as in :func:`search_target`;
    the survey passes its own catalog row and never queries the TIC here.

    This is the survey entry point: the light curve comes from the stitched
    cache (or from an injection harness), so no MAST access happens here.
    Search parameters and their defaults are those of :func:`search_target`;
    ``n_sectors`` and ``provenance`` default to what the stitched curve's
    ``meta`` records (``TESSHUNTER_UNITS`` / ``TESSHUNTER_PROVENANCE``).
    ``grid_cap`` / ``local_grid_cap`` bound the broad and the alias-refinement
    period grids (None keeps the 20 000-point default of ``run_bls``).
    """
    artifact_list = [float(p) for p in (artifact_periods or [])]
    known = {str(k): float(v) for k, v in (known_periods or {}).items()}
    label = target_label or (
        f"TIC {target}" if isinstance(target, (int, np.integer)) else str(target)
    )
    tic_id = _numeric_id(target) if target != "" else None

    products = list(lc_raw.meta.get("TESSHUNTER_PROVENANCE", []) or [])
    units_used = list(lc_raw.meta.get("TESSHUNTER_UNITS", []) or [])
    if not units_used:
        units_used = [p["unit"] for p in products if p.get("unit") is not None]
    if n_sectors is None:
        n_sectors = len(set(units_used)) if units_used else max(len(products), 1)

    result = SearchTargetResult(
        target=target,
        mission=mission,
        params=_to_native({
            "period_min": period_min, "period_max": period_max,
            "duration_min": duration_min, "duration_max": duration_max,
            "max_planets": max_planets, "bin_minutes": bin_minutes,
            "top_n": top_n, "n_periods": n_periods, "snr_min": snr_min,
            "snr_min_resolved": snr_min_resolved,
            "min_event_completeness": min_event_completeness,
            "min_composite_score": min_composite_score,
            "min_transits": min_transits, "sigma_clip": sigma_clip,
            "mask_width_factor": mask_width_factor,
            "artifact_periods": artifact_list, "window_days": window_days,
            "stellar_radius_rsun": stellar_radius_rsun,
            "is_known_toi": is_known_toi, "grid_cap": grid_cap,
            "local_grid_cap": local_grid_cap,
            **({"rank_by": rank_by} if rank_by != "composite" else {}),
        }),
    )
    result.provenance = provenance if provenance is not None else {
        "products": products,
        "units_used": sorted(set(units_used)),
        "units_all": sorted(set(units_used)),
        "fallback_events": [],
        "n_products_downloaded": len(products),
    }
    result.n_sectors = n_sectors
    result.n_cadences_raw = len(lc_raw)
    result.timings["download"] = 0.0
    stellar = _resolve_stellar(
        stellar_params,
        tic_id if (mission.upper() == "TESS" and tic_id is not None) else None,
        fetch_stellar_params, stellar_radius_rsun,
    )
    result.stellar = stellar.to_dict() if stellar is not None else None
    logger.info("search_light_curve: %s  %d cadences, %d unit(s)", label, len(lc_raw), n_sectors)

    return _run_search_stages(
        lc_raw, result,
        label=label, mission=mission, tic_id=tic_id, n_sectors=n_sectors,
        units_used=units_used,
        period_min=period_min, period_max=period_max,
        duration_min=duration_min, duration_max=duration_max,
        max_planets=max_planets, bin_minutes=bin_minutes, top_n=top_n,
        n_periods=n_periods, snr_min=snr_min, snr_min_resolved=snr_min_resolved,
        min_event_completeness=min_event_completeness,
        min_composite_score=min_composite_score, min_transits=min_transits,
        sigma_clip=sigma_clip, mask_width_factor=mask_width_factor,
        artifact_list=artifact_list, known=known, window_days=window_days,
        do_flatten=do_flatten, two_pass_flatten=two_pass_flatten,
        remeasure_depths=remeasure_depths, time_budget_s=time_budget_s,
        stellar_radius_rsun=stellar_radius_rsun,
        stellar_rotation_period_days=stellar_rotation_period_days,
        is_known_toi=is_known_toi, catalog_ok=catalog_ok,
        crossmatch_summary="Catalog crossmatch not attempted.",
        generate_report=False, report_dir=None, summary_csv=None,
        grid_cap=grid_cap, local_grid_cap=local_grid_cap,
        stellar=stellar, rank_by=rank_by,
    )


def _run_search_stages(
    lc_raw: lk.LightCurve,
    result: SearchTargetResult,
    *,
    label: str,
    mission: str,
    tic_id: Optional[int],
    n_sectors: int,
    units_used: list,
    period_min: float,
    period_max: float,
    duration_min: float,
    duration_max: float,
    max_planets: int,
    bin_minutes: float,
    top_n: int,
    n_periods: Optional[int],
    snr_min: float,
    snr_min_resolved: float,
    min_event_completeness: float,
    min_composite_score: float,
    min_transits: int,
    sigma_clip: float,
    mask_width_factor: float,
    artifact_list: list[float],
    known: dict[str, float],
    window_days: Optional[float],
    do_flatten: bool,
    two_pass_flatten: bool,
    remeasure_depths: bool,
    time_budget_s: Optional[float],
    stellar_radius_rsun: Optional[float],
    stellar_rotation_period_days: Optional[float],
    is_known_toi: bool,
    catalog_ok: bool,
    crossmatch_summary: str,
    generate_report: bool,
    report_dir: Optional[Path],
    summary_csv: Optional[Path],
    grid_cap: Optional[int] = None,
    local_grid_cap: Optional[int] = None,
    stellar: Optional[StellarParams] = None,
    rank_by: str = "composite",
) -> SearchTargetResult:
    """Stages 2-5 shared by :func:`search_target` and :func:`search_light_curve`.

    The statements are those of the original ``search_target`` body, in the
    same order; the split exists so a stitched light curve from the survey
    cache (or an injection harness) can enter the search without MAST.
    """
    # ── Stage 2: preprocess (with two-pass flatten) ───────────────────────────
    t0 = time.perf_counter()
    lc_clean, prep_rec = preprocessing.preprocess(
        lc_raw,
        sigma=sigma_clip,
        do_flatten=do_flatten,
        window_days=window_days,
        max_transit_duration_days=duration_max,
    )
    pass1_candidate: Optional[dict] = None
    if do_flatten and two_pass_flatten and prep_rec.flattened:
        lc_clean, prep_rec, pass1_candidate = _two_pass_flatten(
            lc_raw, lc_clean, prep_rec,
            sigma_clip=sigma_clip,
            window_days=window_days,
            duration_max=duration_max,
            bin_minutes=bin_minutes,
            period_min=period_min,
            period_max=period_max,
            duration_min=duration_min,
            n_periods=n_periods,
            snr_min=snr_min,
            mask_width_factor=mask_width_factor,
            artifact_periods=artifact_list,
            grid_cap=grid_cap,
        )
    result.prep = asdict(prep_rec)
    result.prep["two_pass_flatten"] = pass1_candidate is not None
    result.prep["two_pass_candidate"] = pass1_candidate
    result.n_cadences_clean = len(lc_clean)
    result.timings["preprocess"] = time.perf_counter() - t0
    result.lc_raw = lc_raw
    result.lc_clean = lc_clean

    # ── Stage 3: detection loop ───────────────────────────────────────────────
    t0 = time.perf_counter()
    # Wall-clock budget for detection: whatever remains of the caller's
    # per-target budget after download and preprocessing, less a reserve for
    # vetting, depth re-measurement and serialisation.
    detect_budget_s: Optional[float] = None
    if time_budget_s is not None:
        spent = result.timings["download"] + result.timings["preprocess"]
        detect_budget_s = max(0.0, time_budget_s * DETECT_BUDGET_FRACTION - spent)
        logger.info(
            "Detection budget: %.0f s (of a %.0f s target budget, %.0f s already spent)",
            detect_budget_s, time_budget_s, spent,
        )
    found_planets, first_pass_candidates = _detect_planets(
        lc_clean,
        period_min=period_min,
        period_max=period_max,
        duration_min=duration_min,
        duration_max=duration_max,
        max_planets=max_planets,
        bin_minutes=bin_minutes,
        top_n=top_n,
        n_periods=n_periods,
        snr_min=snr_min,
        snr_min_resolved=snr_min_resolved,
        min_event_completeness=min_event_completeness,
        min_composite_score=min_composite_score,
        min_transits=min_transits,
        mask_width_factor=mask_width_factor,
        artifact_periods=artifact_list,
        known_periods=known,
        notes=result.notes,
        time_budget_s=detect_budget_s,
        grid_cap=grid_cap,
        local_grid_cap=local_grid_cap,
        stellar=stellar,
        rank_by=rank_by,
    )
    result.planets = found_planets
    result.timings["detect"] = time.perf_counter() - t0

    # ── Stage 3.5: characterisation (transit fit + depth) ─────────────────────
    # Prompt 3 moved this BEFORE vetting: the vetting stack now consumes the
    # fitted a/R*, Rp/R* and depth (period-aware secondary test, a/R*
    # consistency flag, fit-based odd/even). Detection is already fixed, so
    # this cannot change which planets are found.
    t0 = time.perf_counter()
    if remeasure_depths and found_planets and prep_rec.flattened:
        n_re = _remeasure_depths(
            lc_raw, found_planets,
            sigma_clip=sigma_clip,
            window_days=window_days,
            duration_max=duration_max,
            mask_width_factor=mask_width_factor,
            notes=result.notes,
            stellar=stellar,
            do_fit=True,
            lc_fallback=lc_clean,
        )
        result.prep["depth_remeasured"] = n_re
    result.timings["remeasure"] = time.perf_counter() - t0

    # ── Stage 4: per-planet vetting ───────────────────────────────────────────
    t0 = time.perf_counter()

    vetting_objs: list[Optional[vetting.VettingResult]] = []
    for planet in found_planets:
        try:
            vet = vetting.run_vetting(
                lc_clean,
                period_days=planet["period_days"],
                epoch_btjd=planet["epoch_btjd"],
                duration_days=planet["duration_days"],
                depth_ppt=planet["depth_ppt"],
                n_sectors=n_sectors,
                snr=planet["snr"],
                stellar_radius_rsun=stellar_radius_rsun,
                stellar_rotation_period_days=stellar_rotation_period_days,
                is_known_toi=is_known_toi,
                catalog_ok=catalog_ok,
                fit=planet.get("fit"),
                stellar=stellar,
            )
        except Exception as exc:
            logger.warning(
                "Vetting failed for planet %d (%s) — recording error verdict.",
                planet["planet_num"], exc,
            )
            planet["verdict"] = "vetting error"
            result.vetting.append({
                "planet_num": planet["planet_num"],
                "verdict": "vetting error",
                "flags_hard": [], "flags_high": [], "flags_medium": [],
                "notes": [f"run_vetting raised: {exc}"],
                "result": None,
            })
            vetting_objs.append(None)
            continue

        planet["verdict"] = vet.verdict   # convenience copy on the planet row
        result.vetting.append({
            "planet_num": planet["planet_num"],
            "verdict": vet.verdict,
            "flags_hard": list(vet.flags_hard),
            "flags_high": list(vet.flags_high),
            "flags_medium": list(vet.flags_medium),
            "notes": list(vet.notes),
            "result": asdict(vet),
        })
        vetting_objs.append(vet)
    result.timings["vet"] = time.perf_counter() - t0

    # ── Stage 5 (optional): report generation — never kills the result ────────
    if generate_report and found_planets:
        try:
            from . import reporting
            planets_df = pd.DataFrame(found_planets)
            vet1 = vetting_objs[0] if vetting_objs else None
            if vet1 is not None:
                report_path = reporting.generate_report(
                    target_id=label,
                    tic_id=int(tic_id or 0),
                    sectors=sorted(set(units_used)),
                    prep_record=prep_rec,
                    candidates_df=first_pass_candidates,
                    vetting=vet1,
                    crossmatch_summary=crossmatch_summary,
                    plot_paths={},
                    output_dir=report_dir,
                    planets_df=planets_df,
                    mission=mission,
                )
                result.report_path = str(report_path)
            csv_path = summary_csv or (CANDIDATES_DIR / "candidate_summary.csv")
            for planet in found_planets:
                reporting.append_to_candidate_summary(
                    tic_id=int(tic_id or 0),
                    target_id=label,
                    sectors=sorted(set(units_used)),
                    period_days=planet["period_days"],
                    depth_ppt=planet["depth_ppt"],
                    duration_hours=planet["duration_days"] * 24.0,
                    bls_power=planet["power"],
                    snr=planet["snr"],
                    verdict=planet.get("verdict", "unvetted"),
                    crossmatch_summary=crossmatch_summary,
                    summary_csv=csv_path,
                )
        except Exception as exc:
            msg = f"Report generation failed (non-fatal): {exc}"
            logger.warning(msg)
            result.notes.append(msg)

    logger.info(
        "search_target complete: %s — %d planet(s), %d vetted",
        label, len(result.planets), len(result.vetting),
    )
    return result


# ---------------------------------------------------------------------------
# YAML configuration story
# ---------------------------------------------------------------------------

def load_search_config(path: Optional[Path | str] = None) -> list[dict]:
    """Read a search-targets YAML file into per-target ``search_target`` kwargs.

    The expected layout matches ``configs/search_targets.yaml``::

        search:
          period_min_days: 0.5
          period_max_days: 20.0
          duration_min_hours: 0.5
          duration_max_hours: 12.0
          top_n_candidates: 5
        targets:
          - tic_id: 441462736
            notes: "..."

    The ``search`` block sets shared kwargs (hour-valued durations are
    converted to days); any key in either block that matches a
    :func:`search_target` parameter name is passed through as-is, so per-
    target overrides like ``mission``, ``author``, ``max_planets``, or
    ``stellar_radius_rsun`` work without code changes.  A per-target
    ``known_period_days`` becomes a ``known_periods`` diagnostic entry.

    Parameters
    ----------
    path:
        YAML file path. None uses ``configs/search_targets.yaml`` under the
        project's config directory.

    Returns
    -------
    list of dicts, each directly usable as ``search_target(**entry)``.
    """
    import yaml  # lazy import — only needed for the config story

    cfg_path = Path(path) if path is not None else CONFIGS_DIR / "search_targets.yaml"
    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    valid_params = set(inspect.signature(search_target).parameters)

    search_block = raw.get("search") or {}
    shared: dict = {}
    if "period_min_days" in search_block:
        shared["period_min"] = float(search_block["period_min_days"])
    if "period_max_days" in search_block:
        shared["period_max"] = float(search_block["period_max_days"])
    if "duration_min_hours" in search_block:
        shared["duration_min"] = float(search_block["duration_min_hours"]) / 24.0
    if "duration_max_hours" in search_block:
        shared["duration_max"] = float(search_block["duration_max_hours"]) / 24.0
    if "top_n_candidates" in search_block:
        shared["top_n"] = int(search_block["top_n_candidates"])
    for key, val in search_block.items():
        if key in valid_params and key != "target":
            shared[key] = val

    entries: list[dict] = []
    for tgt in raw.get("targets") or []:
        if not isinstance(tgt, dict):
            logger.warning("Skipping malformed target entry: %r", tgt)
            continue
        kw = dict(shared)
        if "tic_id" in tgt and tgt["tic_id"] is not None:
            kw["target"] = int(tgt["tic_id"])
        elif "target" in tgt and tgt["target"] is not None:
            kw["target"] = tgt["target"]
        else:
            logger.warning("Skipping target entry without tic_id/target: %r", tgt)
            continue
        if tgt.get("known_period_days") is not None:
            kw["known_periods"] = {"known": float(tgt["known_period_days"])}
        for key, val in tgt.items():
            if key in valid_params and key != "target":
                kw[key] = val
        entries.append(kw)

    logger.info("Loaded %d search target(s) from %s", len(entries), cfg_path)
    return entries


def search_targets_from_config(
    path: Optional[Path | str] = None,
    **overrides,
) -> list[SearchTargetResult]:
    """Run :func:`search_target` for every entry in a search-targets YAML file.

    Parameters
    ----------
    path:
        YAML file path (None = ``configs/search_targets.yaml``).
    **overrides:
        Keyword arguments applied on top of every entry (e.g.
        ``generate_report=True`` or ``max_planets=2``).

    Returns
    -------
    One :class:`SearchTargetResult` per target, in file order.  A per-target
    failure is recorded as an empty result with an ERROR note instead of
    aborting the batch.
    """
    results: list[SearchTargetResult] = []
    for entry in load_search_config(path):
        kwargs = {**entry, **overrides}
        tgt = kwargs.get("target", "?")
        try:
            results.append(search_target(**kwargs))
        except Exception as exc:
            logger.error("search_target failed for %r: %s", tgt, exc)
            failed = SearchTargetResult(
                target=tgt,
                mission=str(kwargs.get("mission", "TESS")),
                params=_to_native({
                    k: v for k, v in kwargs.items() if k != "target"
                }),
                notes=[f"ERROR: search_target raised {type(exc).__name__}: {exc}"],
            )
            results.append(failed)
    return results
