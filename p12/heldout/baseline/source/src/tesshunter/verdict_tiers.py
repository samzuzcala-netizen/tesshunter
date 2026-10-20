"""The p10.0 verdict tiers: KILL conditions K1-K9, HOLD conditions H1-H4 and the
flag list F1-F9 that travels with every SUBMIT.

Pre-registered in ``HANDOFF_P10.md`` section 0.1 before any measurement; every
number is named once in :mod:`tesshunter.audit_rules` (the ``TIER_*``
constants).  Nothing here re-measures anything: the functions read the saved
stage records, the physical fit, the expensive (FPP / centroid) record, the
fixed-aperture and difference-image records and their arrays, and the human
K9 review, and say which conditions hold.  A condition whose inputs are
missing is *not measurable* (``fired`` is ``None``), never "not fired".

The evaluation order is K1 .. K9, then H1 .. H4, then SUBMIT; the first
condition that holds decides, but every condition is evaluated and recorded.

SUBMIT is a local verdict on a candidate.  Nothing here submits anything
anywhere; the human decides.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import numpy as np

from . import audit_rules as R

K_ORDER = ("K0", "K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8", "K9")
H_ORDER = ("H1", "H2", "H3", "H4")
F_ORDER = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9")

CONDITION_NAMES = {
    "K0": "hard stop: the star is catalogued at this TIC (REJECT)",
    "K1": "Stage A fails the six criteria",
    "K2": "the secondary gate fails",
    "K3": "Stage B phase-independent sector non-detection excludes the period",
    "K4": "Stage C fails",
    "K5": "the period is an integer alias of a deeper accepted signal or a catalogued period",
    "K6": "odd/even depth difference above 3 sigma",
    "K7": "pixel evidence places the dimming elsewhere or measures its absence",
    "K8": "the physical fit implies a stellar companion",
    "K9": "artefact-carried under D review (numeric criterion plus the reviewer's decision)",
    "H1": "TRICERATOPS NFPP at or above 0.5",
    "H2": "the all-transit fit is unconverged or on the grazing rail",
    "H3": "a D measurement did not execute and can be re-run",
    "H4": "the target is a VSX EA/EB/EW/ELL with no alias match",
}


def _f(v):
    """A finite float or None."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _cond(fired, detail: str, **values) -> dict:
    """One condition: ``fired`` is True / False / None (not measurable)."""
    return {"fired": fired, "measurable": fired is not None, "detail": detail, **values}


def alias_ratio(period: float, other: float, include_unity: bool = False,
                tol: float = R.TIER_ALIAS_TOL) -> str | None:
    """The name of the integer ratio ``period / other`` within ``tol``, or None."""
    if not period or not other or period <= 0 or other <= 0:
        return None
    ratios = dict(R.TIER_ALIAS_RATIOS)
    if include_unity:
        ratios = {"1:1": 1.0, **ratios}
    r = period / other
    best = min(ratios.items(), key=lambda kv: abs(r / kv[1] - 1.0))
    return best[0] if abs(r / best[1] - 1.0) < tol else None


# ─────────────────────────────────────────────────────────────────────────────
# The reference depth (section 0.1.1)
# ─────────────────────────────────────────────────────────────────────────────
def reference_depth(fit: dict | None, stagea: dict | None) -> dict:
    """D_ref and sigma_ref: the adopted fit's duration-averaged depth when the fit
    is converged and not grazing (H2 does not hold), else the Stage A kept-event
    weighted mean depth under the chosen ephemeris."""
    h2 = h2_fit(fit)
    a = ((fit or {}).get("adopted") or {}) if fit and not fit.get("error") else {}
    d, e = _f(a.get("depth_avg_ppt")), _f(a.get("depth_err_ppt"))
    if h2["fired"] is False and d is not None and e is not None and d > 0:
        return {"depth_ppt": d, "err_ppt": e, "source": "fit.adopted.depth_avg_ppt"}
    chosen = _chosen(stagea)
    dk = (chosen or {}).get("det_kept") or {}
    d, e = _f(dk.get("weighted_mean_depth_ppt")), _f(dk.get("err_ppt"))
    if d is not None and e is not None:
        return {"depth_ppt": d, "err_ppt": e, "source": "stageA.det_kept.weighted_mean_depth_ppt"}
    return {"depth_ppt": None, "err_ppt": None, "source": "unavailable"}


def _chosen(stagea: dict | None) -> dict | None:
    if not stagea:
        return None
    per = stagea.get("per_ephemeris") or {}
    return per.get(stagea.get("chosen_ephemeris")) if per else None


# ─────────────────────────────────────────────────────────────────────────────
# KILL conditions
# ─────────────────────────────────────────────────────────────────────────────
def k0_hard_stop(crossmatch_star: dict | None) -> dict:
    status = (crossmatch_star or {}).get("status")
    if status is None or status == "KNOWN_STATUS_REDACTED":
        return _cond(None, f"hard-stop status unavailable ({status})", status=status)
    return _cond(status == "REJECT", f"hard stop {status}", status=status)


def k1_stage_a(stagea: dict | None) -> dict:
    dec = (stagea or {}).get("decision")
    if dec not in ("PASS", "FAIL"):
        return _cond(None, f"Stage A decision {dec}", decision=dec)
    crit = (_chosen(stagea) or {}).get("criteria") or stagea.get("criteria") or {}
    failed = [k for k, v in crit.items() if isinstance(v, dict) and v.get("passed") is False] if isinstance(crit, dict) else []
    return _cond(dec == "FAIL", f"Stage A {dec}" + (f": failed {failed}" if failed else ""),
                 decision=dec, failed_criteria=failed)


def k2_secondary(secondary: dict | None) -> dict:
    gate = (secondary or {}).get("gate")
    if gate not in ("PASS", "FAIL", "HOLD"):
        return _cond(None, f"secondary gate {gate}", gate=gate)
    mode = ((secondary or {}).get("thresholds") or {}).get("gate_mode") or (secondary or {}).get("gate_mode") or "bound"
    return _cond(gate == "FAIL", f"secondary gate {gate} (mode {mode})", gate=gate, mode=mode)


def k3_stage_b(stageb: dict | None) -> dict:
    pi = (stageb or {}).get("phase_independent")
    if not isinstance(pi, dict) or "excluded" not in pi:
        return _cond(None, "Stage B phase-independent test unavailable")
    return _cond(bool(pi["excluded"]), f"phase-independent exclusion {bool(pi['excluded'])} "
                 f"({pi.get('n_sectors_tested')} sector(s) tested)", excluded=bool(pi["excluded"]),
                 n_sectors_tested=pi.get("n_sectors_tested"))


def k4_stage_c(stagec: dict | None) -> dict:
    dec = (stagec or {}).get("decision")
    if dec not in ("PASS", "FAIL"):
        return _cond(None, f"Stage C decision {dec}", decision=dec)
    rule = ((stagec or {}).get("thresholds") or {}).get("peak_rule", "strongest")
    return _cond(dec == "FAIL", f"Stage C {dec} ({rule}): {(stagec or {}).get('reason', '')[:160]}",
                 decision=dec, peak_rule=rule)


def k5_alias(period: float, depth_ppt: float, candidate_rows: list[dict] | None,
             catalogue_periods: list[dict] | None) -> dict:
    """K5a: an integer alias of a deeper accepted signal on the star (depth > 30 ppt or
    > 5x the candidate depth); K5b: a 1:1 or integer alias of a catalogued VSX, TESS-EB,
    TOI or CTOI period within 1 arcmin."""
    hits = []
    for r in candidate_rows or []:
        p2, d2 = _f(r.get("period_days")), _f(r.get("depth_ppt"))
        if p2 is None or d2 is None or abs(p2 / period - 1.0) < R.TIER_ALIAS_TOL:
            continue
        if d2 >= R.B_DEEP_PPT or d2 >= R.B_DEEP_RATIO * depth_ppt:
            name = alias_ratio(period, p2)
            if name:
                hits.append({"kind": "deeper_accepted_signal", "ratio": name, "period_days": p2, "depth_ppt": d2})
    n_cat = 0
    for c in catalogue_periods or []:
        p2 = _f(c.get("period"))
        if p2 is None:
            continue
        n_cat += 1
        name = alias_ratio(period, p2, include_unity=True)
        if name:
            hits.append({"kind": "catalogue", "ratio": name, "period_days": p2, "source": c.get("source"),
                         "label": c.get("label"), "sep_arcsec": c.get("sep_arcsec")})
    measurable = candidate_rows is not None or catalogue_periods is not None
    return _cond(bool(hits) if measurable else None,
                 (f"{len(hits)} alias match(es)" if hits else "no alias match") +
                 f" among {len(candidate_rows or [])} accepted signals and {n_cat} catalogued periods",
                 matches=hits, n_catalogue_periods=n_cat)


def k6_odd_even(fit: dict | None) -> dict:
    oe = ((fit or {}).get("odd_even") or {}) if fit and not fit.get("error") else {}
    s = _f(oe.get("sigma"))
    n_odd = (oe.get("odd") or {}).get("n_transits")
    n_even = (oe.get("even") or {}).get("n_transits")
    if s is None or n_odd is None or n_even is None:
        return _cond(None, "odd/even fit unavailable", sigma=s)
    enough = n_odd >= R.TIER_ODD_EVEN_MIN_TRANSITS and n_even >= R.TIER_ODD_EVEN_MIN_TRANSITS
    fired = bool(enough and s > R.TIER_ODD_EVEN_SIGMA)
    return _cond(fired, f"odd/even {s:.2f} sigma ({n_odd} odd, {n_even} even transits)"
                 + ("" if enough else "; too few transits to decide"),
                 sigma=s, n_odd=n_odd, n_even=n_even)


def _target_position(positions: list[dict], target_gaia_id: int | None) -> dict | None:
    for p in positions:
        if p.get("label") == "T":
            return p
    if target_gaia_id is not None:
        for p in positions:
            if int(p.get("source_id") or -1) == int(target_gaia_id):
                return p
    return None


def _k7a_pixel(row, col, value, scatter_image, tgt, positions) -> dict:
    """The K7a test at one pixel: distance to the target and to the nearest other Gaia
    source, and the difference value over the event scatter at that pixel."""
    d_t = math.hypot(col - tgt["x"], row - tgt["y"])
    others = [(math.hypot(col - p["x"], row - p["y"]), p) for p in positions if p is not tgt
              and int(p.get("source_id") or -1) != int(tgt.get("source_id") or -2)]
    d_n, near = min(others, key=lambda t: t[0]) if others else (None, None)
    scat = None
    if scatter_image is not None:
        try:
            scat = _f(scatter_image[int(row), int(col)])
        except (IndexError, TypeError):
            scat = None
    sig = value / scat if scat else None
    fired = bool(d_t > R.TIER_K7_TARGET_PX and d_n is not None and d_n <= R.TIER_K7_NEIGHBOUR_PX
                 and sig is not None and sig > R.TIER_PIXEL_SIGMA)
    return {"fired": fired if scat else None, "row": int(row), "column": int(col), "difference_e_per_s": value,
            "dist_target_px": round(d_t, 3), "dist_nearest_neighbour_px": None if d_n is None else round(d_n, 3),
            "nearest_neighbour_source_id": None if near is None else near.get("source_id"),
            "nearest_neighbour_G": None if near is None else near.get("G"),
            "event_scatter_e_per_s": scat, "significance": None if sig is None else round(sig, 2),
            "detail": ("event scatter unavailable at the maximum pixel" if not scat else
                       f"max pixel {d_t:.2f} px from target, {d_n if d_n is None else round(d_n, 2)} px from nearest "
                       f"neighbour, {sig:.1f} sigma")}


def k7a_sector(sector_rec: dict, scatter_image: np.ndarray | None, target_gaia_id: int | None,
               difference_image: np.ndarray | None = None) -> dict:
    """K7a in one sector: the primary difference maximum sits on a resolved neighbour.

    The decision (``fired``) uses the maximum within ``TIER_K7_SEARCH_PX`` of the target
    (amendment 0.11.5: the whole-cutout maximum is the largest of 441 noisy pixels).  The
    whole-cutout maximum stored on the record (the literal pre-registered form) is evaluated
    too and reported under ``literal``.  Without the difference image the local maximum is
    known only when the stored maximum already lies inside the search radius.
    """
    mp = (sector_rec.get("maximum_pixels") or {}).get("primary") or {}
    row, col, value = mp.get("row"), mp.get("column"), _f(mp.get("difference_e_per_s"))
    positions = sector_rec.get("gaia_positions") or []
    tgt = _target_position(positions, target_gaia_id)
    out = {"sector": sector_rec.get("sector"), "fired": None, "row": row, "column": col, "difference_e_per_s": value}
    if row is None or col is None or value is None or tgt is None:
        out["detail"] = "difference maximum or target position unavailable"
        return out
    literal = _k7a_pixel(row, col, value, scatter_image, tgt, positions)
    out["literal"] = literal
    local = None
    if difference_image is not None:
        img = np.asarray(difference_image, dtype=float)
        yy, xx = np.indices(img.shape)
        inside = (np.hypot(xx - tgt["x"], yy - tgt["y"]) <= R.TIER_K7_SEARCH_PX) & np.isfinite(img)
        if inside.any():
            masked = np.where(inside, img, -np.inf)
            r, c = np.unravel_index(int(np.argmax(masked)), img.shape)
            local = _k7a_pixel(r, c, float(img[r, c]), scatter_image, tgt, positions)
    elif literal["dist_target_px"] <= R.TIER_K7_SEARCH_PX:
        local = literal
    if local is None:
        out.update({"fired": None, "detail": "local maximum unavailable (no difference image; stored maximum outside "
                                              f"{R.TIER_K7_SEARCH_PX:.0f} px); literal form: " + literal["detail"]})
        return out
    out.update({k: v for k, v in local.items()})
    out["detail"] = f"local ({R.TIER_K7_SEARCH_PX:.0f} px) " + local["detail"] + "; literal: " + literal["detail"]
    return out


def _aperture_sector_usable(sec: dict) -> tuple[bool, str]:
    if sec.get("status") not in (None, "available", "complete", "ok"):
        return False, f"sector {sec.get('status')}: {sec.get('error', '')}"[:120]
    if (sec.get("n_background_pixels") or 0) < R.TIER_MIN_SKY_PIXELS:
        return False, f"{sec.get('n_background_pixels')} sky pixels < {R.TIER_MIN_SKY_PIXELS}"
    net = (sec.get("measurements") or {}).get("net") or {}
    d, e = _f(net.get("depth_ppt")), _f(net.get("err_ppt"))
    if d is None or e is None or e <= 0:
        return False, "no usable net box measurement (zero or missing error)"
    return True, ""


def k7b_sector(sec: dict, d_ref: float | None) -> dict:
    """K7b in one sector: the net fixed-aperture depth excludes the diluted reference depth."""
    out = {"sector": sec.get("sector"), "fired": None}
    usable, why = _aperture_sector_usable(sec)
    if not usable:
        out["detail"] = "unmeasurable: " + why
        return out
    net = sec["measurements"]["net"]
    d, e = float(net["depth_ppt"]), float(net["err_ppt"])
    out.update({"net_depth_ppt": round(d, 4), "net_err_ppt": round(e, 4)})
    if d_ref is None:
        out["detail"] = "reference depth unavailable"
        return out
    diluted = R.TIER_DILUTION_ALLOWANCE * d_ref
    if diluted < R.TIER_PIXEL_SIGMA * e:
        out["detail"] = f"unmeasurable: 0.5 x D_ref {diluted:.3f} < 3 sigma_s {R.TIER_PIXEL_SIGMA * e:.3f} ppt"
        return out
    out["fired"] = bool(d < diluted - R.TIER_PIXEL_SIGMA * e)
    out["detail"] = f"net {d:.3f} +/- {e:.3f} ppt against 0.5 x D_ref {diluted:.3f} ppt: " + \
                    ("absence at 3 sigma" if out["fired"] else "consistent with the diluted depth")
    return out


def k7_pixels(difference: dict | None, difference_arrays: dict | None, aperture: dict | None,
              d_ref: float | None, target_gaia_id: int | None) -> dict:
    a_sectors, b_sectors = [], []
    for s in (difference or {}).get("sectors") or []:
        scat = img = None
        if difference_arrays is not None:
            scat = difference_arrays.get(f"s{s.get('sector')}_primary_event_scatter")
            img = difference_arrays.get(f"s{s.get('sector')}_primary_difference")
        a_sectors.append(k7a_sector(s, scat, target_gaia_id, img))
    for s in (aperture or {}).get("sectors") or []:
        b_sectors.append(k7b_sector(s, d_ref))
    n_a = sum(1 for s in a_sectors if s["fired"])
    n_a_literal = sum(1 for s in a_sectors if (s.get("literal") or {}).get("fired"))
    n_b = sum(1 for s in b_sectors if s["fired"])
    measurable = any(s["fired"] is not None for s in a_sectors + b_sectors)
    fired = (n_a >= R.TIER_MIN_SECTORS or n_b >= R.TIER_MIN_SECTORS) if measurable else None
    return _cond(fired, f"K7a in {n_a} sector(s) (literal whole-cutout form: {n_a_literal}), K7b in {n_b} sector(s) "
                 f"({sum(1 for s in a_sectors if s['fired'] is not None)} K7a-measurable, "
                 f"{sum(1 for s in b_sectors if s['fired'] is not None)} K7b-measurable)",
                 n_elsewhere=n_a, n_elsewhere_literal=n_a_literal, n_absent=n_b, elsewhere=a_sectors, absent=b_sectors)


def k8_companion(fit: dict | None) -> dict:
    if not fit or fit.get("error"):
        return _cond(None, "physical fit unavailable")
    a = fit.get("adopted") or {}
    rp = _f(a.get("rp_rearth"))
    big = rp is not None and rp > R.TIER_MAX_RADIUS_RJUP * R.R_JUP_IN_R_EARTH
    dchi2 = _f(fit.get("delta_chi2_prior_minus_free"))
    converged = not fit.get("uncertainty_issues")
    b, rprs = _f(a.get("b")), _f(a.get("rp_rs"))
    non_grazing = b is not None and rprs is not None and (b + rprs) < 1.0
    rho_fit = _f(((fit.get("free_fit") or {}).get("rho_fit_cgs")))
    rho_cat = _f((fit.get("stellar") or {}).get("rho_cgs"))
    ratio = rho_fit / rho_cat if rho_fit and rho_cat else None
    lo, hi = R.TIER_DENSITY_RATIO_RANGE
    density = (dchi2 is not None and dchi2 >= R.TIER_DENSITY_REJECT_DCHI2 and converged and non_grazing
               and ratio is not None and not (lo <= ratio <= hi))
    fired = bool(big or density)
    return _cond(fired, f"Rp {rp} Re (limit {R.TIER_MAX_RADIUS_RJUP * R.R_JUP_IN_R_EARTH:.2f}); density prior "
                 f"delta chi2 {dchi2}, converged {converged}, non-grazing {non_grazing}, "
                 f"rho_fit/rho_cat {None if ratio is None else round(ratio, 3)}",
                 rp_rearth=rp, radius_kill=bool(big), density_kill=bool(density),
                 delta_chi2_prior_minus_free=dchi2, density_ratio=ratio, converged=converged, non_grazing=non_grazing)


def k9_sector(time: np.ndarray, raw: np.ndarray, sky: np.ndarray, period: float, t0: float,
              duration_days: float) -> dict:
    """K9a in one sector: Pearson r between the raw aperture and sky series over the
    cadences within ``TIER_K9_WINDOW_DURATIONS`` durations of every event centre."""
    t = np.asarray(time, dtype=float)
    phase = ((t - t0 + period / 2) % period) - period / 2
    w = np.abs(phase) <= R.TIER_K9_WINDOW_DURATIONS * duration_days
    r_, s_ = np.asarray(raw, dtype=float)[w], np.asarray(sky, dtype=float)[w]
    good = np.isfinite(r_) & np.isfinite(s_)
    n = int(good.sum())
    if n < R.TIER_K9_MIN_POINTS or np.std(r_[good]) == 0 or np.std(s_[good]) == 0:
        return {"n_points": n, "r": None, "fired": None, "detail": "too few event-window points"}
    r = float(np.corrcoef(r_[good], s_[good])[0, 1])
    return {"n_points": n, "r": round(r, 4), "fired": bool(abs(r) > R.TIER_K9_CORRELATION),
            "detail": f"|r| = {abs(r):.3f} over {n} event-window cadences"}


def k9b_sector(sec: dict, d_ref: float | None, e_ref: float | None) -> dict:
    """K9b in one sector: the net fixed-aperture depth disagrees with the reference depth."""
    out = {"sector": sec.get("sector"), "fired": None}
    usable, why = _aperture_sector_usable(sec)
    if not usable:
        out["detail"] = "unmeasurable: " + why
        return out
    net = sec["measurements"]["net"]
    d, e = float(net["depth_ppt"]), float(net["err_ppt"])
    out.update({"net_depth_ppt": round(d, 4), "net_err_ppt": round(e, 4)})
    if d_ref is None or e_ref is None:
        out["detail"] = "reference depth unavailable"
        return out
    tot = math.sqrt(e ** 2 + e_ref ** 2)
    too_deep = d > d_ref + R.TIER_PIXEL_SIGMA * tot
    too_shallow = d < R.TIER_DILUTION_ALLOWANCE * d_ref - R.TIER_PIXEL_SIGMA * tot
    brightening = d < -R.TIER_PIXEL_SIGMA * e
    out.update({"fired": bool(too_deep or too_shallow or brightening), "too_deep": bool(too_deep),
                "too_shallow": bool(too_shallow), "brightening": bool(brightening),
                "detail": f"net {d:.3f} +/- {e:.3f} ppt against D_ref {d_ref:.3f} +/- {e_ref:.3f} ppt"})
    return out


def k9_artefact(aperture: dict | None, aperture_arrays: dict | None, ephemeris: dict | None,
                d_ref: float | None, e_ref: float | None, review: dict | None) -> dict:
    """K9: both clauses in at least two sectors each, AND the reviewer's recorded decision."""
    a_sectors, b_sectors = [], []
    for s in (aperture or {}).get("sectors") or []:
        sec = s.get("sector")
        usable, _ = _aperture_sector_usable(s)
        rec = {"sector": sec, "fired": None, "detail": "arrays unavailable"}
        if usable and aperture_arrays is not None and ephemeris and all(
                f"s{sec}_{n}" in aperture_arrays for n in ("time", "raw", "sky")):
            rec = {"sector": sec, **k9_sector(aperture_arrays[f"s{sec}_time"], aperture_arrays[f"s{sec}_raw"],
                                              aperture_arrays[f"s{sec}_sky"], ephemeris["period"],
                                              ephemeris["t0"], ephemeris["duration"])}
        a_sectors.append(rec)
        b_sectors.append(k9b_sector(s, d_ref, e_ref))
    n_a = sum(1 for s in a_sectors if s["fired"])
    n_b = sum(1 for s in b_sectors if s["fired"])
    n_meas = sum(1 for s in a_sectors if s["fired"] is not None)
    criterion = n_a >= R.TIER_MIN_SECTORS and n_b >= R.TIER_MIN_SECTORS
    decision = None if review is None else bool(review.get("k9_artefact"))
    if n_meas < R.TIER_MIN_SECTORS:
        fired = None
    else:
        fired = bool(criterion and decision)
    return _cond(fired, f"criterion {'holds' if criterion else 'does not hold'}: K9a in {n_a}, K9b in {n_b} "
                 f"sector(s) of {n_meas} measurable; reviewer decision "
                 f"{'not recorded' if decision is None else ('artefact' if decision else 'not an artefact')}"
                 + ("; reviewer KILL without the criterion is NOT applied" if decision and not criterion else ""),
                 criterion_holds=bool(criterion), n_correlated=n_a, n_disagreeing=n_b, n_measurable=n_meas,
                 reviewer_decision=decision, reviewer_note=(review or {}).get("reason"),
                 correlation=a_sectors, disagreement=b_sectors)


# ─────────────────────────────────────────────────────────────────────────────
# HOLD conditions
# ─────────────────────────────────────────────────────────────────────────────
def h1_nfpp(expensive: dict | None) -> dict:
    fp = (expensive or {}).get("fpp") or {}
    if not fp.get("available"):
        return _cond(None, f"FPP unavailable: {fp.get('error') or 'not run'}"[:160])
    if (expensive or {}).get("fpp_uniform"):
        return _cond(None, "fpp_uniform: the likelihood calculation failed; unavailable, not a HOLD",
                     nfpp=_f(fp.get("nfpp")), fpp=_f(fp.get("fpp")), fpp_uniform=True)
    nfpp = _f(fp.get("nfpp"))
    if nfpp is None:
        return _cond(None, "NFPP missing")
    return _cond(nfpp >= R.TIER_NFPP_HOLD, f"NFPP {nfpp:.4g}, FPP {_f(fp.get('fpp'))}", nfpp=nfpp, fpp=_f(fp.get("fpp")),
                 fpp_uniform=False)


def h2_fit(fit: dict | None) -> dict:
    if not fit or fit.get("error"):
        return _cond(None, "physical fit unavailable")
    issues = list(fit.get("uncertainty_issues") or [])
    a = fit.get("adopted") or {}
    grazing = bool(a.get("grazing"))
    b_err, t14, t14_err = _f(a.get("b_err")), _f(a.get("t14_hours")), _f(a.get("t14_err_hours"))
    rail = grazing and ((b_err is None or b_err > R.TIER_GRAZING_B_ERR)
                        or (t14 is not None and t14_err is not None and t14_err >= t14))
    fired = bool(issues or rail)
    return _cond(fired, ("; ".join(issues) if issues else "converged") +
                 (f"; grazing rail with b_err {b_err}, T14 {t14} +/- {t14_err} h" if rail else
                  (f"; grazing but usable (b_err {b_err})" if grazing else "")),
                 uncertainty_issues=issues, grazing=grazing, grazing_rail=bool(rail), b_err=b_err)


def h3_operational(fit: dict | None, expensive: dict | None, difference: dict | None,
                   aperture: dict | None) -> dict:
    missing = []
    if not fit:
        missing.append("fit not run")
    elif fit.get("error"):
        missing.append(f"fit error: {fit['error'][:80]}")
    if not expensive:
        missing.append("FPP/centroid measurement not run")
    else:
        for name in ("fpp", "centroid"):
            part = expensive.get(name) or {}
            if not part.get("available"):
                missing.append(f"{name} unavailable: {part.get('error') or 'not run'}"[:100])
    if difference is None:
        missing.append("difference images not run")
    if aperture is None:
        missing.append("fixed-aperture photometry not run")
    return _cond(bool(missing), "; ".join(missing) if missing else "every D measurement executed", missing=missing)


def _vsx_class(type_str) -> str | None:
    if not type_str:
        return None
    m = re.match(r"[A-Za-z]+", str(type_str).strip())
    return m.group(0).upper() if m else None


def h4_vsx(vsx_objects: list[dict] | None, period: float) -> dict:
    if vsx_objects is None:
        return _cond(None, "VSX unavailable")
    on_target = [o for o in vsx_objects if _f(o.get("sep_arcsec")) is not None
                 and float(o["sep_arcsec"]) <= R.TIER_VSX_TARGET_RADIUS_ARCSEC]
    if on_target and all(o.get("Type") is None for o in on_target):
        return _cond(None, "VSX class redacted or missing on the target entry")
    ebs = [o for o in on_target if _vsx_class(o.get("Type")) in R.TIER_VSX_EB_CLASSES]
    hits = []
    for o in ebs:
        alias = alias_ratio(period, _f(o.get("Period")) or 0.0, include_unity=True)
        hits.append({"name": o.get("Name"), "type": o.get("Type"), "period": _f(o.get("Period")),
                     "sep_arcsec": o.get("sep_arcsec"), "alias": alias})
    fired = bool(hits) and all(h["alias"] is None for h in hits)
    return _cond(fired, f"{len(on_target)} VSX entr(ies) within {R.TIER_VSX_TARGET_RADIUS_ARCSEC:.0f} arcsec, "
                 f"{len(ebs)} eclipsing class(es)" + (f": {hits}" if hits else ""), entries=hits)


# ─────────────────────────────────────────────────────────────────────────────
# The flag list F1-F9
# ─────────────────────────────────────────────────────────────────────────────
def flag_list(inputs: dict, conditions: dict, d_ref: dict) -> dict:
    nb = inputs.get("neighbours") or {}
    g = nb.get("gaia") or {}
    tg = g.get("target") or {}
    depth = _f(inputs.get("depth_ppt"))
    f1 = []
    for x in g.get("neighbours") or []:
        sep = _f(x.get("sep_arcsec"))
        dmax = _f(x.get("max_observed_depth_ppt_total_eclipse"))
        if sep is None or sep > R.TIER_NEIGHBOUR_RADIUS_ARCSEC or dmax is None or depth is None or dmax < depth:
            continue
        f1.append({"source_id": x.get("source_id"), "sep_arcsec": sep, "sep_px": x.get("sep_px"), "G": x.get("G"),
                   "delta_mag": x.get("delta_mag"), "max_depth_ppt_total_eclipse": dmax,
                   "required_eclipse_fraction": round(depth / dmax, 4)})
    f1.sort(key=lambda r: r["sep_arcsec"])
    f2 = {k: tg.get(k) for k in ("ruwe", "ipd_frac_multi_peak", "astrometric_excess_noise_sig",
                                 "non_single_star", "phot_variable_flag", "best_class_name", "duplicated_source")}
    f3 = {"vsx": [{k: o.get(k) for k in ("Name", "Type", "Period", "sep_arcsec")} for o in (nb.get("vsx") or {}).get("objects") or []],
          "simbad": [{k: o.get(k) for k in ("main_id", "otype", "sp_type", "sep_arcsec")} for o in (nb.get("simbad") or {}).get("objects") or []]}
    ex = inputs.get("expensive") or {}
    fp = ex.get("fpp") or {}
    f4 = {"fpp": _f(fp.get("fpp")), "nfpp": _f(fp.get("nfpp")), "available": bool(fp.get("available")),
          "fpp_uniform": bool(ex.get("fpp_uniform")), "sectors": fp.get("sectors"),
          "caveats": "binned fold; circular aperture from Tmag; first three selected sectors; probabilities are "
                     "conditional on TRICERATOPS's astrophysical scenarios and do not price instrumental artefacts"
                     + ("; fpp_uniform: the likelihood calculation failed and the numbers are unavailable" if ex.get("fpp_uniform") else "")}
    k7, k9 = conditions.get("K7") or {}, conditions.get("K9") or {}
    per_sector = {}
    for s in (k7.get("absent") or []):
        per_sector.setdefault(s["sector"], {})["net_depth_ppt"] = s.get("net_depth_ppt")
        per_sector[s["sector"]]["net_err_ppt"] = s.get("net_err_ppt")
        per_sector[s["sector"]]["k7_absent"] = s.get("fired")
        per_sector[s["sector"]]["note"] = s.get("detail")
    for s in (k7.get("elsewhere") or []):
        per_sector.setdefault(s["sector"], {})["k7_elsewhere"] = s.get("fired")
        per_sector[s["sector"]]["difference_max_dist_target_px"] = s.get("dist_target_px")
    for s in (ex.get("centroid") or {}).get("per_sector") or []:
        per_sector.setdefault(s.get("sector"), {})["centroid_sigma"] = _f(s.get("sigma"))
        per_sector[s.get("sector")]["centroid_shift_px"] = _f(s.get("total_shift_px"))
    # sectors with a usable net fixed-aperture measurement (K7b may still be unmeasurable there
    # when the diluted reference depth is below 3 sigma of that sector's error)
    n_meas = sum(1 for s in (k7.get("absent") or []) if s.get("net_depth_ppt") is not None)
    if k7.get("fired"):
        loc = "elsewhere" if (k7.get("n_elsewhere") or 0) >= R.TIER_MIN_SECTORS else "absent_on_target"
    elif n_meas == 0:
        loc = "not_measurable"
    else:
        loc = "unlocalised" if f1 else "on_target_consistent"
    f5 = {"localisation": loc, "n_sectors_measurable": n_meas, "per_sector": [dict(sector=k, **v) for k, v in sorted(per_sector.items(), key=lambda kv: (kv[0] is None, kv[0]))]}
    f6 = [{k: r.get(k) for k in ("period_days", "depth_ppt", "snr", "verdict", "stitch_snr", "passes_pregate")}
          for r in inputs.get("candidates") or [] if abs((_f(r.get("period_days")) or 0) / float(inputs["period"]) - 1) >= R.TIER_ALIAS_TOL]
    xs = inputs.get("crossmatch_star") or {}
    f7 = {"status": xs.get("status"), "tic_matches": xs.get("tic_matches") or [], "neighbour_matches": xs.get("neighbour_matches") or [],
          "tce_association": inputs.get("tce_association")}
    chosen = _chosen(inputs.get("stageA")) or {}
    events = chosen.get("events") or []
    classes = {c: 0 for c in ("dip_absent_in_sap", "pdc_gap", "scattered_light_ramp", "scattered_light_flag",
                              "momentum_dump", "sector_orbit_edge", "quality_flagged", "sap_baseline_ramp")}
    for e in events:
        for c in e.get("artefact_classes") or []:
            if c in classes:
                classes[c] += 1
    strongest = chosen.get("strongest_event") or {}
    f8 = {"n_observed": chosen.get("n_observed"), "n_excluded": chosen.get("n_excluded"), "n_kept": chosen.get("n_kept"),
          "removed_by_class": classes, "strongest_event_removed": bool(strongest.get("excluded")) if strongest else None}
    f9 = validation_status(f1, f5, f4, conditions, d_ref)
    return {"F1": f1, "F2": f2, "F3": f3, "F4": f4, "F5": f5, "F6": f6, "F7": f7, "F8": f8, "F9": f9}


def validation_status(f1: list, f5: dict, f4: dict, conditions: dict, d_ref: dict) -> str:
    """F9: the specific external evidence that would settle the source.  Text, attached
    to a SUBMIT instead of replacing it."""
    parts = []
    loc = f5.get("localisation")
    if f1:
        near = f1[0]
        parts.append(f"{len(f1)} Gaia neighbour(s) within {R.TIER_NEIGHBOUR_RADIUS_ARCSEC:.0f} arcsec could produce the "
                     f"depth by total eclipse (nearest {near['sep_arcsec']:.1f} arcsec, G {near['G']}, needing an eclipse of "
                     f"{100 * near['required_eclipse_fraction']:.0f}% of its light). Seeing-limited ground photometry at the "
                     f"predicted epochs, resolving each of them, would settle the source.")
    else:
        parts.append("No Gaia neighbour within 63 arcsec can produce the depth by total eclipse; an unresolved companion "
                     "within the target's PSF remains untested until high-resolution imaging or RV excludes it.")
    if loc == "not_measurable":
        parts.append("TESS pixel evidence is not measurable for this candidate (no usable fixed-aperture sector); the "
                     "localisation rests entirely on external photometry.")
    elif loc == "unlocalised":
        parts.append(f"TESS fixed-aperture photometry is consistent with the target in {f5.get('n_sectors_measurable')} "
                     f"sector(s) but cannot separate the target from the listed neighbours.")
    elif loc == "on_target_consistent":
        parts.append(f"TESS fixed-aperture photometry is consistent with the target in {f5.get('n_sectors_measurable')} sector(s).")
    if f4.get("fpp_uniform") or not f4.get("available"):
        parts.append("The FPP calculation is unavailable; a rerun with a resolved scene is needed before any statistical validation.")
    elif f4.get("nfpp") is not None:
        parts.append(f"TRICERATOPS FPP {f4['fpp']:.3g}, NFPP {f4['nfpp']:.3g} on the binned fold; a low value does not "
                     f"price instrumental artefacts.")
    h2 = conditions.get("H2") or {}
    if h2.get("grazing"):
        parts.append("The fit is grazing; a constrained geometry needs higher-precision photometry.")
    parts.append("Statistical validation additionally needs a resolved source, repeated localised dimming and a low FPP "
                 "with the scene fixed; this candidate is submitted as a candidate, not as a validated planet.")
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# The evaluation
# ─────────────────────────────────────────────────────────────────────────────
def evaluate(inputs: dict) -> dict:
    """Evaluate every tier condition from the saved records in ``inputs`` and decide.

    ``inputs`` keys (any may be missing or None): ``key``, ``period``, ``depth_ppt``,
    ``stageA``, ``secondary``, ``stageB``, ``stageC``, ``fit``, ``expensive``,
    ``neighbours``, ``crossmatch_star``, ``candidates`` (the host's accepted rows),
    ``catalogue_periods`` (VSX / TESS-EB / TOI / CTOI within 1 arcmin), ``aperture``
    and ``aperture_arrays`` (the fixed-aperture record and its npz), ``difference``
    and ``difference_arrays``, ``review`` (the K9 reviewer record), ``ephemeris``
    (period / t0 / duration used for K9; defaults to the adopted fit), ``tce_association``.
    """
    period, depth = float(inputs["period"]), float(inputs.get("depth_ppt") or 0.0)
    fit = inputs.get("fit")
    if fit is not None and fit.get("error") is None and not fit.get("adopted"):
        fit = None
    stagea = inputs.get("stageA")
    dref = reference_depth(fit, stagea)
    eph = inputs.get("ephemeris")
    if eph is None and fit and not fit.get("error"):
        a = fit.get("adopted") or {}
        if all(_f(a.get(k)) is not None for k in ("period", "t0_btjd", "t14_hours")):
            eph = {"period": float(a["period"]), "t0": float(a["t0_btjd"]), "duration": float(a["t14_hours"]) / 24.0,
                   "source": "fit.adopted"}
    nb = inputs.get("neighbours") or {}
    target_gaia = ((nb.get("gaia") or {}).get("target") or {}).get("source_id")
    if target_gaia is None:
        target_gaia = nb.get("tic_gaia_id")
    vsx_objects = None
    if nb.get("vsx") is not None and isinstance(nb.get("vsx"), dict) and "objects" in nb["vsx"]:
        vsx_objects = nb["vsx"].get("objects") or []
    conditions = {
        "K0": k0_hard_stop(inputs.get("crossmatch_star")),
        "K1": k1_stage_a(stagea),
        "K2": k2_secondary(inputs.get("secondary")),
        "K3": k3_stage_b(inputs.get("stageB")),
        "K4": k4_stage_c(inputs.get("stageC")),
        "K5": k5_alias(period, depth, inputs.get("candidates"), inputs.get("catalogue_periods")),
        "K6": k6_odd_even(fit),
        "K7": k7_pixels(inputs.get("difference"), inputs.get("difference_arrays"), inputs.get("aperture"),
                        dref["depth_ppt"], target_gaia),
        "K8": k8_companion(fit),
        "K9": k9_artefact(inputs.get("aperture"), inputs.get("aperture_arrays"), eph, dref["depth_ppt"],
                          dref["err_ppt"], inputs.get("review")),
        "H1": h1_nfpp(inputs.get("expensive")),
        "H2": h2_fit(fit),
        "H3": h3_operational(fit, inputs.get("expensive"), inputs.get("difference"), inputs.get("aperture")),
        "H4": h4_vsx(vsx_objects, period),
    }
    verdict, deciding = "SUBMIT", None
    for name in K_ORDER:
        if conditions[name]["fired"]:
            verdict, deciding = "KILL", name
            break
    if verdict == "SUBMIT":
        for name in H_ORDER:
            if conditions[name]["fired"]:
                verdict, deciding = "HOLD", name
                break
    flags = flag_list(inputs, conditions, dref)
    not_measurable = [n for n in K_ORDER + H_ORDER if conditions[n]["fired"] is None]
    return {"rules_version": "p10.0", "key": inputs.get("key"), "verdict": verdict, "deciding_condition": deciding,
            "deciding_detail": None if deciding is None else conditions[deciding]["detail"],
            "reference_depth": dref, "ephemeris": eph, "conditions": conditions, "not_measurable": not_measurable,
            "flags": flags, "thresholds": R.tier_thresholds(),
            "note": "SUBMIT is a local CTOI-grade verdict, not a validation; F9 states what would settle the source. "
                    "Nothing is submitted by the pipeline."}


# ─────────────────────────────────────────────────────────────────────────────
# Loading the saved records of one candidate from a funnel root
# ─────────────────────────────────────────────────────────────────────────────
def _read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _detail_period(detail: str | None) -> float | None:
    m = re.search(r"P=([0-9.]+)d", str(detail or ""))
    return float(m.group(1)) if m else None


def catalogue_periods_from(neighbours: dict | None, crossmatch_star: dict | None) -> list[dict] | None:
    """Catalogued periods near the target: VSX entries within 1 arcmin (from the cached
    neighbour record) and TESS-EB / TOI / CTOI / TCE matches carried by the hard-stop record
    (their ``detail`` strings carry ``P=...d`` where the catalogue gives one)."""
    out = []
    vsx = (neighbours or {}).get("vsx")
    if vsx is None and crossmatch_star is None:
        return None
    for o in (vsx or {}).get("objects") or []:
        sep = _f(o.get("sep_arcsec"))
        if sep is not None and sep <= R.TIER_CATALOGUE_RADIUS_ARCSEC and _f(o.get("Period")):
            out.append({"source": "vsx", "label": o.get("Name"), "period": float(o["Period"]), "sep_arcsec": sep,
                        "class": o.get("Type")})
    for m in ((crossmatch_star or {}).get("tic_matches") or []) + ((crossmatch_star or {}).get("neighbour_matches") or []):
        p = _detail_period(m.get("detail"))
        if p and m.get("source") in ("tess_eb", "toi", "ctoi"):
            out.append({"source": m.get("source"), "label": m.get("label"), "period": p,
                        "sep_arcsec": m.get("sep_arcsec", 0.0), "class": None})
    return out


def load_inputs(root: Path, key: str, tic: int, period: float, depth_ppt: float | None = None,
                candidates_csv: Path | None = None) -> dict:
    """Every saved record of one candidate under a funnel root laid out as the P8 and P9
    trees are (``stageA/``, ``secondary/``, ``stageB/``, ``stageC/``, ``stageD/``, ``fit/``,
    ``expensive/``, ``neighbours/``, ``eb_screen/``, ``pixel_followup/``, ``tiers_review/``)."""
    root = Path(root)

    def opt(rel):
        p = root / rel
        return _read(p) if p.exists() else None

    def npz(rel):
        p = root / rel
        if not p.exists():
            return None
        with np.load(p) as z:
            return {k: z[k] for k in z.files}

    stagea = opt(f"stageA/{key}.json")
    if depth_ppt is None:
        depth_ppt = _f((stagea or {}).get("survey_depth_ppt")) or _f(((opt(f"stageB/{key}.json") or {}).get("survey_depth_ppt")))
    xm_all = None
    for cand in (f"crossmatch_{root.name}.json", "crossmatch_p8.json", f"crossmatch_tic{tic}.json"):
        if (root / cand).exists():
            xm_all = _read(root / cand)
            break
    xm_star = ((xm_all or {}).get("per_star") or {}).get(str(tic))
    if xm_star is None:
        xm_star = ((opt(f"stageD/{key}.json") or {}).get("crossmatch") or {}).get("star")
    rows = None
    csv_path = candidates_csv or (root / "candidates.csv")
    if csv_path.exists():
        rows = [r for r in csv.DictReader(csv_path.open(newline="", encoding="utf-8")) if int(r["tic_id"]) == int(tic)]
    nb = opt(f"neighbours/tic{tic}.json")
    review = None
    tr = opt(f"tiers_review/{key}.json")
    pf = opt(f"pixel_followup/{key}.json")
    if tr is not None:
        review = {"k9_artefact": bool(tr.get("k9_artefact")), "reason": tr.get("reason"), "source": f"tiers_review/{key}.json"}
    elif pf is not None:
        review = {"k9_artefact": pf.get("recommended_verdict") == "KILL", "reason": (pf.get("assessment") or "")[:300],
                  "source": f"pixel_followup/{key}.json (P8 pixel review; KILL read as the artefact decision)"}
    fit = opt(f"fit/{key}.json")
    return {"key": key, "tic_id": tic, "period": period, "depth_ppt": depth_ppt, "stageA": stagea,
            "secondary": opt(f"secondary/{key}.json"), "stageB": opt(f"stageB/{key}.json"),
            "stageC": opt(f"stageC/{key}.json"), "stageD": opt(f"stageD/{key}.json"), "fit": fit,
            "expensive": opt(f"expensive/{key}.json"), "neighbours": nb, "crossmatch_star": xm_star,
            "candidates": rows, "catalogue_periods": catalogue_periods_from(nb, xm_star),
            "aperture": opt(f"eb_screen/{key}_target_aperture.json"),
            "aperture_arrays": npz(f"eb_screen/{key}_target_aperture.npz"),
            "difference": opt(f"eb_screen/{key}_fit_difference.json"),
            "difference_arrays": npz(f"eb_screen/{key}_fit_difference.npz"),
            "review": review, "tce_association": None}


def summarise(ev: dict) -> str:
    c = ev["conditions"]
    fired = [n for n in K_ORDER + H_ORDER if c[n]["fired"]]
    return (f"{ev['verdict']} ({ev['deciding_condition'] or 'no condition'}): fired {fired or 'none'}; "
            f"not measurable {ev['not_measurable'] or 'none'}")


__all__ = ["evaluate", "load_inputs", "reference_depth", "alias_ratio", "flag_list", "validation_status",
           "catalogue_periods_from", "summarise", "K_ORDER", "H_ORDER", "F_ORDER", "CONDITION_NAMES",
           "k0_hard_stop", "k1_stage_a", "k2_secondary", "k3_stage_b", "k4_stage_c", "k5_alias", "k6_odd_even",
           "k7_pixels", "k7a_sector", "k7b_sector", "k8_companion", "k9_artefact", "k9_sector", "k9b_sector",
           "h1_nfpp", "h2_fit", "h3_operational", "h4_vsx"]
