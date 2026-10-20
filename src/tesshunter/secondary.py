"""Full-phase secondary-eclipse scan (prompt-7 option 1).

The prompt-6 funnel never looked for a secondary eclipse and the P4 packets
tested only phase 0.5.  The rank-16 re-analysis then found, on TIC 233007823, a
**52-sigma secondary at phase 0.605** that both were blind to: the candidate is
an eccentric eclipsing binary, and an eccentric orbit puts the secondary
anywhere but 0.5.  This module closes that gap.  It folds a prepared light curve
on the candidate ephemeris, scans EVERY phase for dips above 5 sigma, measures
any dip in the raw SAP flux as well, and compares it with the deepest secondary
an irradiated planet could produce at the star's a/R* - the period-aware bound
already in :func:`tesshunter.vetting.planetary_secondary_bound_ppt`.

A dip away from phase 0 is **not** by itself a secondary eclipse.  On a variable
star a box scan finds ppt-level dips at many phases, and the strongest of them
means nothing; prompt 6 measured 14 to 41 such dips on five of its seven Stage A
survivors.  So the gate is deliberately narrow:

* a second dip whose **SAP** depth exceeds the planetary bound by more than
  ``SEC_GATE_SIGMA_OVER_BOUND`` sigma is a star-level **FAIL** - it is a stellar
  companion, and no planet can make it;
* more than ``SEC_MAX_DIPS_BEFORE_VARIABILITY`` dips at scattered phases is a
  **variability flag**, never a secondary claim.

Ported from ``scripts/secondary_scan.py`` and ``scripts/rank16_analysis.py``
(same ``box_depth``, one definition).  Pure: arrays in, dicts out.
"""
from __future__ import annotations

import math

import numpy as np

from .audit_rules import (
    SEC_ALBEDO,
    SEC_EMPIRICAL_SIGMA,
    SEC_EVENT_MIN_COVERAGE,
    SEC_GATE_SIGMA_OVER_BOUND,
    SEC_MAX_DIPS_BEFORE_VARIABILITY,
    SEC_MIN_PHASE_SEPARATION,
    SEC_MIN_SIGMA,
    SEC_PHASE_STEP,
    SEC_PRESENT_SIGMA,
    SEC_PRIMARY_PHASE_TOLERANCE,
    SEC_RECUR_EVENT_FRACTION,
    SEC_RECUR_EVENT_SIGMA,
    SEC_RECUR_GROUP_SIGMA,
    SEC_RECUR_MIN_EVENTS,
    SEC_REFINE_HALF,
    SEC_REFINE_STEP,
    SEC_TRACK_MIN_POINTS,
)
from .k1_rules import SEC_ALIAS_CONSISTENCY_SIGMA, SEC_ALIAS_PHASE_TOL, SEC_ALIAS_WIDTH_FACTORS
from .vetting import planetary_secondary_bound_ppt

__all__ = ["box_depth", "phase_scan", "planet_secondary_bound", "secondary_scan", "apply_gate", "GATE_MODES",
           "GATE_MODES_P10", "split_primary_shoulders", "primary_exclusion_phase", "sap_phase_track",
           "empirical_scatter", "event_depths", "recurrence"]


def box_depth(t: np.ndarray, f: np.ndarray, tc_phase: float, period: float, t0: float,
              width_days: float) -> dict | None:
    """Depth of a box of ``width_days`` centred at phase ``tc_phase``, from the folded series.

    The baseline is the median of the points between one and four box widths
    away, and the error is the point scatter over the square root of the number
    of in-box points.  ``None`` when there is too little data to measure.
    """
    ph = ((t - t0) / period) % 1.0
    d = np.abs(((ph - tc_phase + 0.5) % 1.0) - 0.5) * period      # days from the box centre
    inb = d < width_days / 2
    out = (d > width_days) & (d < 4 * width_days)
    if inb.sum() < 5 or out.sum() < 50:
        return None
    base = float(np.nanmedian(f[out]))
    resid = f[out] - base
    sig = float(1.4826 * np.nanmedian(np.abs(resid - np.nanmedian(resid))))
    depth = base - float(np.nanmean(f[inb]))
    err = sig / math.sqrt(int(inb.sum()))
    return {"phase": float(tc_phase), "depth_ppt": 1000 * depth, "err_ppt": 1000 * err,
            "sigma": depth / err if err > 0 else 0.0, "n_in": int(inb.sum()), "n_out": int(out.sum()),
            "point_scatter_ppt": 1000 * sig}


def phase_scan(t: np.ndarray, f: np.ndarray, period: float, t0: float,
               width_days: float) -> tuple[list[dict], np.ndarray]:
    """Every distinct dip above ``SEC_MIN_SIGMA``, deepest first, and the scan's sigma track.

    Dips closer than ``SEC_MIN_PHASE_SEPARATION`` in phase are the same dip; each
    is refined on a fine grid around its coarse position.
    """
    scan = [r for ph in np.arange(0.0, 1.0, SEC_PHASE_STEP)
            if (r := box_depth(t, f, ph, period, t0, width_days))]
    if not scan:
        return [], np.array([])
    sig = np.array([s["sigma"] for s in scan])
    dips, taken = [], []
    for i in np.argsort(-sig):
        if sig[i] < SEC_MIN_SIGMA:
            break
        ph = scan[i]["phase"]
        if any(min(abs(ph - q), 1 - abs(ph - q)) < SEC_MIN_PHASE_SEPARATION for q in taken):
            continue
        taken.append(ph)
        best = scan[i]
        for p2 in np.arange(ph - SEC_REFINE_HALF, ph + SEC_REFINE_HALF, SEC_REFINE_STEP):
            r = box_depth(t, f, p2 % 1.0, period, t0, width_days)
            if r and r["sigma"] > best["sigma"]:
                best = r
        dips.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in best.items()})
    dips.sort(key=lambda d: -d["sigma"])
    return dips, sig


def planet_secondary_bound(period: float, rstar: float, mstar: float, teff: float,
                           primary_depth_ppt: float) -> dict:
    """The deepest secondary an irradiated planet could show at this period.

    Thermal emission from the hottest possible dayside plus reflected light at
    geometric albedo ``SEC_ALBEDO``, evaluated at the circular-orbit a/R* implied
    by the period and the star, with Rp/R* taken from the primary depth.  This is
    :func:`tesshunter.vetting.planetary_secondary_bound_ppt` - the period-aware
    bound of prompt 3 - given the audit's own a/R* rather than a transit fit's.
    """
    G = 6.674e-8
    a_rs = ((G * mstar * 1.989e33 * (period * 86400.0) ** 2) / (4 * math.pi ** 2)) ** (1 / 3) / (rstar * 6.957e10)
    rp_rs = math.sqrt(max(primary_depth_ppt, 0.0) / 1000.0)
    bound, thermal, reflected, t_day = planetary_secondary_bound_ppt(
        rp_rs, a_rs, teff, albedo=SEC_ALBEDO)
    return {"a_over_rstar": round(a_rs, 2), "rp_over_rstar": round(rp_rs, 5),
            "T_day_K": round(t_day, 0), "T_eq_K": round(teff * math.sqrt(1.0 / (2.0 * a_rs)), 0),
            "thermal_ppt": thermal, "reflected_ppt": reflected, "albedo": SEC_ALBEDO,
            "max_planetary_secondary_ppt": bound}


GATE_MODES = ("bound", "quiet_bound", "quiet_zero", "quiet_bound_hold")
#: [P10] The three prompt-10 Part 2a modes (HANDOFF_P10.md 0.2).  They are kept
#: apart from ``GATE_MODES`` so that every p8.0 record's ``gate_by_mode`` block
#: is byte-identical; a scan evaluates them only when asked (``p10_modes``).
GATE_MODES_P10 = ("empirical_bound", "recurrent_bound", "recurrent_bound_corr")
#: [K1] change 11: ``bound_alias``.  Kept apart like GATE_MODES_P10 so every earlier record is
#: unchanged; evaluated only when asked (``k1_modes``) or selected as the gate mode.
GATE_MODES_K1 = ("bound_alias",)


def apply_gate(gate_depth: float, gate_err: float, bound: float, n_dips: int, variability: bool,
               mode: str = "bound", quiet_max_dips: int = 2, *, empirical_scatter_ppt: float | None = None,
               recurs: bool | None = None, present_both: bool | None = None,
               alias_rescued: bool | None = None) -> dict:
    """The gate decision alone (prompt-8 decision 1), pure, so every variant can
    be evaluated on one scan.

    * ``bound`` (p7.0): FAIL when the SAP depth is more than
      ``SEC_GATE_SIGMA_OVER_BOUND`` sigma above the planetary bound, whatever
      the scan looks like.
    * ``quiet_bound``: the same, but only on a quiet scan (``n_dips`` at most
      ``quiet_max_dips``, the primary included).
    * ``quiet_zero``: FAIL when the SAP depth is more than 3 sigma above ZERO
      and the scan is quiet.
    * ``quiet_bound_hold``: ``quiet_bound``; a variability-flagged scan gives
      HOLD instead of PASS.

    The prompt-10 modes (``GATE_MODES_P10``) take the keyword inputs and leave
    the four legacy modes untouched:

    * ``empirical_bound``: FAIL when the SAP depth exceeds the bound by more
      than ``SEC_EMPIRICAL_SIGMA`` times ``empirical_scatter_ppt`` (the scan's
      own off-phase scatter); without a scatter the white error is used and
      ``empirical_fallback_white`` says so.
    * ``recurrent_bound``: ``empirical_bound`` and ``recurs`` (the dip is seen
      in at least half of the covered events, or in both sector groups).
    * ``recurrent_bound_corr``: ``recurrent_bound`` and ``present_both`` (the
      dip is at least ``SEC_PRESENT_SIGMA`` sigma in the SAP and the corrected
      flux).
    """
    if mode in GATE_MODES:
        quiet = n_dips <= quiet_max_dips
        over_bound = (gate_depth - bound) / max(gate_err, 1e-12)
        over_zero = gate_depth / max(gate_err, 1e-12)
        if mode == "bound":
            fail = over_bound > SEC_GATE_SIGMA_OVER_BOUND
        elif mode in ("quiet_bound", "quiet_bound_hold"):
            fail = quiet and over_bound > SEC_GATE_SIGMA_OVER_BOUND
        else:  # quiet_zero
            fail = quiet and over_zero > SEC_GATE_SIGMA_OVER_BOUND
        gate = "FAIL" if fail else ("HOLD" if (mode == "quiet_bound_hold" and variability) else "PASS")
        return {"gate": gate, "mode": mode, "quiet": bool(quiet), "quiet_max_dips": int(quiet_max_dips),
                "sigma_over_bound": round(float(over_bound), 1), "sigma_over_zero": round(float(over_zero), 1)}
    if mode in GATE_MODES_K1:
        return apply_gate_bound_alias(gate_depth, gate_err, bound, empirical_scatter_ppt=empirical_scatter_ppt,
                                      recurs=recurs, alias_rescued=alias_rescued)
    if mode not in GATE_MODES_P10:
        raise ValueError(f"unknown secondary gate mode {mode!r}")
    over_bound = (gate_depth - bound) / max(gate_err, 1e-12)
    over_zero = gate_depth / max(gate_err, 1e-12)
    scat = float(empirical_scatter_ppt) if (empirical_scatter_ppt is not None and empirical_scatter_ppt > 0) else None
    over_bound_emp = (gate_depth - bound) / scat if scat else over_bound
    emp_fail = over_bound_emp > SEC_EMPIRICAL_SIGMA
    if mode == "empirical_bound":
        fail = emp_fail
    elif mode == "recurrent_bound":
        fail = emp_fail and bool(recurs)
    else:
        fail = emp_fail and bool(recurs) and bool(present_both)
    return {"gate": "FAIL" if fail else "PASS", "mode": mode,
            "sigma_over_bound": round(float(over_bound), 1), "sigma_over_zero": round(float(over_zero), 1),
            "sigma_over_bound_empirical": round(float(over_bound_emp), 1), "empirical_scatter_ppt": scat,
            "empirical_fallback_white": scat is None, "recurs": recurs, "present_both": present_both}


def apply_gate_bound_alias(gate_depth: float, gate_err: float, bound: float, *,
                           empirical_scatter_ppt: float | None = None, recurs: bool | None = None,
                           alias_rescued: bool | None = None) -> dict:
    """[K1] ``bound_alias``: (1) a dip near phase 0.5 whose depth and duration agree with the primary
    and whose P/2 fold is consistent with one planet keeps the fundamental-period hypothesis (PASS,
    ``alias_rescued``); (2) any other off-phase feature fails only as ``recurrent_bound`` does: over
    the bound by more than SEC_EMPIRICAL_SIGMA times the scan's own off-phase scatter AND recurring."""
    over_bound = (gate_depth - bound) / max(gate_err, 1e-12)
    over_zero = gate_depth / max(gate_err, 1e-12)
    scat = float(empirical_scatter_ppt) if (empirical_scatter_ppt is not None and empirical_scatter_ppt > 0) else None
    over_bound_emp = (gate_depth - bound) / scat if scat else over_bound
    fail = (not alias_rescued) and over_bound_emp > SEC_EMPIRICAL_SIGMA and bool(recurs)
    return {"gate": "FAIL" if fail else "PASS", "mode": "bound_alias",
            "sigma_over_bound": round(float(over_bound), 1), "sigma_over_zero": round(float(over_zero), 1),
            "sigma_over_bound_empirical": round(float(over_bound_emp), 1), "empirical_scatter_ppt": scat,
            "empirical_fallback_white": scat is None, "recurs": recurs, "alias_rescued": bool(alias_rescued)}


def _best_width_index(t: np.ndarray, f: np.ndarray, phase: float, period: float, t0: float,
                      width_days: float) -> tuple[int | None, list]:
    sig = []
    for k in SEC_ALIAS_WIDTH_FACTORS:
        r = box_depth(t, f, phase % 1.0, period, t0, width_days * k)
        sig.append(None if r is None else round(float(r["sigma"]), 2))
    valid = [s for s in sig if s is not None]
    if not valid:
        return None, sig
    return int(np.nanargmax([(-np.inf if s is None else s) for s in sig])), sig


def alias_family_test(t: np.ndarray, f: np.ndarray, prim: dict, dip: dict, period: float, t0: float,
                      width_days: float, rstar: float, mstar: float, teff: float,
                      t_sap: np.ndarray | None = None, f_sap: np.ndarray | None = None,
                      t_sap_sector: np.ndarray | None = None) -> dict:
    """[K1] Is the off-phase dip the same planet's interleaved primary transit (the search carried
    the candidate at about twice the true period, as for TOI-620 b and Ross 176 b)?

    Applicable when the dip lies within max(SEC_ALIAS_PHASE_TOL, 1.5 box widths) of the primary's
    phase + 0.5.  Consistency: detrended depths within SEC_ALIAS_CONSISTENCY_SIGMA combined sigma
    (each depth's sigma = in-box white error and baseline-median error in quadrature) and best box widths (over SEC_ALIAS_WIDTH_FACTORS) within one step.  Then the series is folded
    at P/2: it is consistent with one planet when a primary exists at phase 0 of the P/2 fold and
    its deepest other dip (if any) does not fail ``recurrent_bound`` at P/2 (the same empirical-
    scatter and recurrence pieces, on the SAP flux when given)."""
    out = {"applicable": False, "rescued": False}
    tol = max(SEC_ALIAS_PHASE_TOL, 1.5 * float(width_days) / float(period))
    sep = _circ(dip["phase"], (prim["phase"] + 0.5) % 1.0)
    out["phase_offset_from_half"] = round(float(sep), 4)
    out["phase_tolerance"] = round(float(tol), 4)
    if sep > tol:
        return out
    out["applicable"] = True
    dd = float(dip["depth_ppt"]) - float(prim["depth_ppt"])
    # each depth's error: the in-box white error plus the error of its baseline median
    # (1.2533 x point scatter / sqrt(n_out)); box_depth's err_ppt carries only the first term
    de = math.sqrt(sum(float(x["err_ppt"]) ** 2 + (1.2533 * float(x["point_scatter_ppt"])
                                                    / math.sqrt(max(int(x["n_out"]), 1))) ** 2
                       for x in (dip, prim)))
    out["depth_difference_sigma"] = round(abs(dd) / max(de, 1e-12), 2)
    out["depth_consistent"] = bool(abs(dd) <= SEC_ALIAS_CONSISTENCY_SIGMA * de)
    ip, sp = _best_width_index(t, f, prim["phase"], period, t0, width_days)
    is_, ss = _best_width_index(t, f, dip["phase"], period, t0, width_days)
    out["width_sigma_primary"], out["width_sigma_dip"] = sp, ss
    out["duration_consistent"] = bool(ip is not None and is_ is not None and abs(ip - is_) <= 1)
    if not (out["depth_consistent"] and out["duration_consistent"]):
        return out
    half = float(period) / 2.0
    dips2, _ = phase_scan(t, f, half, t0, width_days)
    prim2 = next((d for d in dips2 if min(d["phase"], 1 - d["phase"]) < SEC_PRIMARY_PHASE_TOLERANCE), None)
    out["half_period"] = half
    out["half_period_primary"] = prim2
    if prim2 is None:
        out["one_planet_at_half_period"] = False
        out["why"] = "no primary at phase 0 of the P/2 fold"
        return out
    secs2, _ = split_primary_shoulders(dips2, prim2, width_days, half)
    if not secs2:
        out["one_planet_at_half_period"] = True
        out["rescued"] = True
        out["why"] = "the P/2 fold has no other dip above 5 sigma"
        return out
    d2 = secs2[0]
    bound2 = planet_secondary_bound(half, rstar, mstar, teff, prim2["depth_ppt"])["max_planetary_secondary_ppt"]
    use_sap = t_sap is not None and f_sap is not None and len(t_sap) > 60
    sap2 = box_depth(t_sap, f_sap, d2["phase"], half, t0, width_days) if use_sap else None
    ts, fs, ss_ = (t_sap, f_sap, t_sap_sector) if sap2 is not None else (t, f, None)
    g_depth, g_err = (sap2["depth_ppt"], sap2["err_ppt"]) if sap2 is not None else (d2["depth_ppt"], d2["err_ppt"])
    track = sap_phase_track(ts, fs, half, t0, width_days)
    emp = empirical_scatter(track, prim2["phase"], primary_exclusion_phase(width_days, half), d2["phase"],
                            float(width_days) / half)
    evs = event_depths(ts, fs, d2["phase"], half, t0, width_days, sector=ss_)
    rec = recurrence(evs, ts, fs, ss_, d2["phase"], half, t0, width_days)
    g = apply_gate(g_depth, g_err, bound2, len(dips2), False, "recurrent_bound",
                   empirical_scatter_ppt=emp["scatter_ppt"], recurs=rec["recurs"])
    out["half_period_secondary"] = d2
    out["half_period_gate"] = g
    out["one_planet_at_half_period"] = g["gate"] == "PASS"
    out["rescued"] = bool(out["one_planet_at_half_period"])
    out["why"] = ("the P/2 fold's deepest other dip passes recurrent_bound" if out["rescued"]
                  else "the P/2 fold's deepest other dip fails recurrent_bound")
    return out


def _circ(a: float, b: float) -> float:
    d = abs(float(a) - float(b)) % 1.0
    return min(d, 1.0 - d)


def sap_phase_track(t: np.ndarray, f: np.ndarray, period: float, t0: float, width_days: float) -> list[dict]:
    """[P10] The box-depth track on the coarse phase grid (every ``box_depth`` that could be measured)."""
    return [r for ph in np.arange(0.0, 1.0, SEC_PHASE_STEP) if (r := box_depth(t, f, ph, period, t0, width_days))]


def empirical_scatter(track: list[dict], prim_phase: float | None, excl_phase: float, dip_phase: float,
                      width_phase: float) -> dict:
    """[P10] The robust standard deviation (1.4826 x MAD) of the box-depth track at every
    phase outside the primary exclusion and more than one box width from the dip."""
    deps = [r["depth_ppt"] for r in track
            if (prim_phase is None or _circ(r["phase"], prim_phase) >= excl_phase) and _circ(r["phase"], dip_phase) > width_phase]
    if len(deps) < SEC_TRACK_MIN_POINTS:
        return {"scatter_ppt": None, "median_ppt": None, "n": len(deps)}
    a = np.asarray(deps, dtype=float)
    med = float(np.median(a))
    return {"scatter_ppt": float(1.4826 * np.median(np.abs(a - med))), "median_ppt": med, "n": int(len(deps))}


def event_depths(t: np.ndarray, f: np.ndarray, phase: float, period: float, t0: float, width_days: float,
                 sector: np.ndarray | None = None) -> list[dict]:
    """[P10] The box depth at ``phase`` in every cycle, measured in the time domain against
    the local out-of-box median (one to four box widths either side); an event is covered
    at ``SEC_EVENT_MIN_COVERAGE`` of the expected in-box cadences."""
    t = np.asarray(t, dtype=float)
    f = np.asarray(f, dtype=float)
    if t.size < 10:
        return []
    order = np.argsort(t)
    cad = float(np.median(np.diff(t[order]))) if t.size > 1 else width_days
    expected = max(1.0, width_days / max(cad, 1e-9))
    tc0 = t0 + phase * period
    n0, n1 = math.ceil((t.min() - tc0) / period), math.floor((t.max() - tc0) / period)
    out = []
    for n in range(n0, n1 + 1):
        tc = tc0 + n * period
        d = np.abs(t - tc)
        inb = d < width_days / 2
        outm = (d > width_days) & (d < 4 * width_days)
        cov = float(inb.sum()) / expected
        rec = {"n": int(n), "tc": float(tc), "n_in": int(inb.sum()), "n_out": int(outm.sum()),
               "coverage": round(min(cov, 1.0), 3), "covered": bool(cov >= SEC_EVENT_MIN_COVERAGE and outm.sum() >= 20)}
        if sector is not None and inb.any():
            vals, counts = np.unique(np.asarray(sector)[inb], return_counts=True)
            rec["sector"] = int(vals[int(np.argmax(counts))])
        if rec["covered"]:
            base = float(np.nanmedian(f[outm]))
            resid = f[outm] - base
            sig = float(1.4826 * np.nanmedian(np.abs(resid - np.nanmedian(resid))))
            depth = base - float(np.nanmean(f[inb]))
            err = sig / math.sqrt(int(inb.sum()))
            rec.update({"depth_ppt": round(1000 * depth, 4), "err_ppt": round(1000 * err, 4),
                        "sigma": round(depth / err, 2) if err > 0 else 0.0})
        out.append(rec)
    return out


def recurrence(events: list[dict], t: np.ndarray, f: np.ndarray, sector: np.ndarray | None, phase: float,
               period: float, t0: float, width_days: float) -> dict:
    """[P10] Does the dip recur?  Per event: at least ``SEC_RECUR_EVENT_SIGMA`` in at least
    ``SEC_RECUR_EVENT_FRACTION`` of the covered events (never fewer than
    ``SEC_RECUR_MIN_EVENTS``); or stacked at ``SEC_RECUR_GROUP_SIGMA`` in each of two sector
    groups (the covered sectors split into an earlier and a later half by sector number)."""
    covered = [e for e in events if e["covered"]]
    n_sig = sum(1 for e in covered if (e.get("sigma") or 0.0) >= SEC_RECUR_EVENT_SIGMA)
    need = max(SEC_RECUR_MIN_EVENTS, math.ceil(SEC_RECUR_EVENT_FRACTION * len(covered)))
    per_event = len(covered) >= SEC_RECUR_MIN_EVENTS and n_sig >= need
    groups, secs = None, []
    if sector is not None:
        sector = np.asarray(sector)
        secs = sorted({e["sector"] for e in covered if "sector" in e})
        if len(secs) >= 2:
            half = len(secs) // 2
            groups = []
            for name, grp in (("early", secs[:half]), ("late", secs[half:])):
                m = np.isin(sector, grp)
                r = box_depth(np.asarray(t)[m], np.asarray(f)[m], phase, period, t0, width_days) if m.sum() > 60 else None
                groups.append({"group": name, "sectors": [int(s) for s in grp],
                               "depth_ppt": None if r is None else round(r["depth_ppt"], 4),
                               "err_ppt": None if r is None else round(r["err_ppt"], 4),
                               "sigma": None if r is None else round(r["sigma"], 2)})
    group_recurs = bool(groups) and all(g["sigma"] is not None and g["sigma"] >= SEC_RECUR_GROUP_SIGMA for g in groups)
    return {"n_events": len(events), "n_covered_events": len(covered), "n_events_ge_sigma": int(n_sig),
            "events_needed": int(need), "per_event_recurs": bool(per_event), "n_sectors_covered": len(secs),
            "sector_groups": groups, "group_recurs": bool(group_recurs), "recurs": bool(per_event or group_recurs)}


def primary_exclusion_phase(width_days: float, period: float) -> float:
    """How far from the primary a dip must sit to be a different feature: the
    primary tolerance, or 1.5 box widths when the box is wide in phase."""
    return max(SEC_PRIMARY_PHASE_TOLERANCE, 1.5 * float(width_days) / float(period))


def split_primary_shoulders(dips: list[dict], prim: dict | None, width_days: float,
                            period: float) -> tuple[list[dict], list[dict]]:
    """Secondaries, and the dips that are the PRIMARY's own shoulders.

    Prompt 8 (measured on injected planets with hundreds of transits): a coarse
    dip just outside ``SEC_MIN_PHASE_SEPARATION`` from the primary is refined
    INTO the transit's ingress or egress (phase 0.01 on a 1-day period is 14
    minutes from mid-transit) and, since only the deepest dip inside
    ``SEC_PRIMARY_PHASE_TOLERANCE`` was taken as the primary, the shoulder was
    then read as a 100-sigma "secondary" and failed the gate on every injected
    planet.  Every dip within :func:`primary_exclusion_phase` of the primary
    belongs to the primary; it is recorded, never gated on, never counted
    toward the variability flag.
    """
    if prim is None:
        return [d for d in dips], []
    excl = primary_exclusion_phase(width_days, period)
    secs, shoulders = [], []
    for d in dips:
        if d is prim:
            continue
        sep = abs(d["phase"] - prim["phase"])
        sep = min(sep, 1.0 - sep)
        (shoulders if sep < excl else secs).append(d)
    return secs, shoulders


def secondary_scan(t: np.ndarray, f: np.ndarray, period: float, t0: float, width_days: float,
                   rstar: float, mstar: float, teff: float,
                   t_sap: np.ndarray | None = None, f_sap: np.ndarray | None = None,
                   gate_mode: str = "bound", quiet_max_dips: int = 2,
                   t_sap_sector: np.ndarray | None = None, p10_modes: bool = False,
                   k1_modes: bool = False) -> dict:
    """Scan every phase, judge what is found, and apply the gate.

    ``t``/``f`` are the prepared detrended series; ``t_sap``/``f_sap``, when
    given, are the same baseline in normalised raw SAP flux, in which the
    deepest off-phase dip is re-measured - the gate is on the SAP depth, so a
    dip the flux correction manufactured cannot fail a candidate.
    ``gate_mode`` / ``quiet_max_dips`` select the prompt-8 decision-1 variant
    (:func:`apply_gate`); the defaults are p7.0.  Under any other setting every
    variant's decision is also recorded under ``gate_by_mode`` so one scan
    measures them all.

    [P10] ``p10_modes`` (or a ``gate_mode`` in ``GATE_MODES_P10``) adds the
    prompt-10 measurements under ``p10`` and every prompt-10 mode's decision
    under ``gate_by_mode_p10``; ``t_sap_sector`` labels the SAP cadences by
    sector for the recurrence sector-group test.  Off by default, so every
    earlier record is unchanged.
    """
    want_k1 = bool(k1_modes) or gate_mode in GATE_MODES_K1
    want_p10 = bool(p10_modes) or gate_mode in GATE_MODES_P10 or want_k1
    dips, sig = phase_scan(t, f, period, t0, width_days)
    out = {"period_days": period, "epoch_btjd": t0, "box_width_days": width_days,
           "n_points": int(len(t)), "n_dips_above_5sigma": len(dips),
           "thresholds": {"min_sigma": SEC_MIN_SIGMA,
                          "min_phase_separation": SEC_MIN_PHASE_SEPARATION,
                          "gate_sigma_over_bound": SEC_GATE_SIGMA_OVER_BOUND,
                          "max_dips_before_variability": SEC_MAX_DIPS_BEFORE_VARIABILITY,
                          "albedo": SEC_ALBEDO}}
    if gate_mode != "bound" or quiet_max_dips != 2:
        out["thresholds"].update({"gate_mode": gate_mode, "quiet_max_dips": quiet_max_dips})
    if sig.size:
        out["scan_sigma_percentiles"] = {"p50": round(float(np.percentile(sig, 50)), 2),
                                         "p90": round(float(np.percentile(sig, 90)), 2),
                                         "p99": round(float(np.percentile(sig, 99)), 2),
                                         "max": round(float(np.max(sig)), 2)}
    prim = next((d for d in dips if min(d["phase"], 1 - d["phase"]) < SEC_PRIMARY_PHASE_TOLERANCE), None)
    secs, shoulders = split_primary_shoulders(dips, prim, width_days, period)
    out["primary"] = prim
    out["secondaries"] = secs
    out["primary_shoulder_dips"] = shoulders
    out["n_dips_above_5sigma"] = len(dips) - len(shoulders)
    bound = planet_secondary_bound(period, rstar, mstar, teff,
                                   prim["depth_ppt"] if prim else 0.0)
    out["planet_secondary_bound"] = bound
    out["variability_flag"] = bool(len(dips) - len(shoulders) > SEC_MAX_DIPS_BEFORE_VARIABILITY)
    out["gate"] = "PASS"
    all_pass = {m: "PASS" for m in GATE_MODES}
    all_pass.update({f"quiet_zero_N{n}": "PASS" for n in (2, 3, 5)})
    all_pass.update({f"quiet_bound_N{n}": "PASS" for n in (2, 3, 5)})
    out["gate_by_mode"] = all_pass
    if want_p10:
        out["gate_by_mode_p10"] = {m: "PASS" for m in GATE_MODES_P10}
        out["p10"] = {"applicable": False}
    if want_k1:
        out["gate_by_mode_k1"] = {m: "PASS" for m in GATE_MODES_K1}
        out["k1"] = {"applicable": False}
    if not prim:
        out["verdict"] = "no dip at phase 0; nothing to interpret"
        return out
    if not secs:
        out["verdict"] = "CLEAN: no dip above 5 sigma at any other phase"
        return out
    d = secs[0]
    out["secondary_over_primary_depth"] = round(d["depth_ppt"] / prim["depth_ppt"], 3) if prim["depth_ppt"] else None
    # the gate is measured in SAP: a dip the flux correction made must not fail a candidate
    sap = None
    if t_sap is not None and f_sap is not None and len(t_sap) > 60:
        sap = box_depth(t_sap, f_sap, d["phase"], period, t0, width_days)
    out["deepest_secondary_in_sap"] = None if sap is None else {
        k: (round(v, 4) if isinstance(v, float) else v) for k, v in sap.items()}
    gate_depth, gate_err, gate_flux = ((sap["depth_ppt"], sap["err_ppt"], "sap")
                                       if sap is not None else (d["depth_ppt"], d["err_ppt"], "detrended"))
    b = bound["max_planetary_secondary_ppt"]
    out["secondary_over_planet_bound"] = round(gate_depth / max(b, 1e-12), 1)
    out["secondary_sigma_over_planet_bound"] = round((gate_depth - b) / max(gate_err, 1e-12), 1)
    out["gate_measured_in"] = gate_flux
    p8_mode = gate_mode != "bound" or quiet_max_dips != 2
    # every variant's decision, so one scan measures them all (the prompt-8 decision-1 instrument)
    out["secondary_sigma_over_zero"] = round(gate_depth / max(gate_err, 1e-12), 1)
    out["gate_by_mode"] = {m: apply_gate(gate_depth, gate_err, b, len(dips), out["variability_flag"],
                                         m, quiet_max_dips)["gate"] for m in GATE_MODES}
    out["gate_by_mode"].update({f"quiet_zero_N{n}": apply_gate(gate_depth, gate_err, b, len(dips),
                                                              out["variability_flag"], "quiet_zero", n)["gate"]
                                for n in (2, 3, 5)})
    out["gate_by_mode"].update({f"quiet_bound_N{n}": apply_gate(gate_depth, gate_err, b, len(dips),
                                                               out["variability_flag"], "quiet_bound", n)["gate"]
                                for n in (2, 3, 5)})
    p10_kw = {}
    if want_p10:
        # [P10] the measurements the three prompt-10 modes need, on the gate series (SAP when
        # available, as the gate itself) with the sector labels for the group test
        ts, fs, ss = (t_sap, f_sap, t_sap_sector) if sap is not None else (t, f, None)
        track = sap_phase_track(ts, fs, period, t0, width_days)
        emp = empirical_scatter(track, prim["phase"], primary_exclusion_phase(width_days, period), d["phase"],
                                float(width_days) / float(period))
        evs = event_depths(ts, fs, d["phase"], period, t0, width_days, sector=ss)
        rec = recurrence(evs, ts, fs, ss, d["phase"], period, t0, width_days)
        sap_sigma = gate_depth / max(gate_err, 1e-12)
        present_both = (bool(sap_sigma >= SEC_PRESENT_SIGMA and d["sigma"] >= SEC_PRESENT_SIGMA)
                        if sap is not None else None)
        out["p10"] = {"applicable": True, "gate_series": gate_flux, "n_track": len(track), "empirical": emp,
                      "events": [{k: e.get(k) for k in ("n", "sector", "covered", "coverage", "depth_ppt", "err_ppt", "sigma")}
                                 for e in evs],
                      "recurrence": rec, "sap_sigma": round(float(sap_sigma), 2), "corrected_sigma": d["sigma"],
                      "present_both": present_both,
                      "thresholds": {"empirical_sigma": SEC_EMPIRICAL_SIGMA, "track_min_points": SEC_TRACK_MIN_POINTS,
                                     "event_sigma": SEC_RECUR_EVENT_SIGMA, "event_fraction": SEC_RECUR_EVENT_FRACTION,
                                     "min_events": SEC_RECUR_MIN_EVENTS, "group_sigma": SEC_RECUR_GROUP_SIGMA,
                                     "event_min_coverage": SEC_EVENT_MIN_COVERAGE, "present_sigma": SEC_PRESENT_SIGMA}}
        p10_kw = {"empirical_scatter_ppt": emp["scatter_ppt"], "recurs": rec["recurs"], "present_both": present_both}
        out["gate_by_mode_p10"] = {m: apply_gate(gate_depth, gate_err, b, len(dips), out["variability_flag"], m,
                                                 quiet_max_dips, **p10_kw)["gate"] for m in GATE_MODES_P10}
    k1_kw = {}
    if want_k1:
        alias = alias_family_test(t, f, prim, d, period, t0, width_days, rstar, mstar, teff,
                                  t_sap, f_sap, t_sap_sector)
        k1_kw = {"empirical_scatter_ppt": p10_kw.get("empirical_scatter_ppt"), "recurs": p10_kw.get("recurs"),
                 "alias_rescued": alias.get("rescued")}
        g_k1 = apply_gate(gate_depth, gate_err, b, len(dips), out["variability_flag"], "bound_alias",
                          quiet_max_dips, **k1_kw)
        out["k1"] = {"applicable": True, "alias_family": alias, "gate": g_k1,
                     "thresholds": {"alias_phase_tol": SEC_ALIAS_PHASE_TOL,
                                    "alias_consistency_sigma": SEC_ALIAS_CONSISTENCY_SIGMA,
                                    "alias_width_factors": list(SEC_ALIAS_WIDTH_FACTORS),
                                    "empirical_sigma": SEC_EMPIRICAL_SIGMA}}
        out["gate_by_mode_k1"] = {"bound_alias": g_k1["gate"]}
    if gate_mode in GATE_MODES_K1:
        g = out["k1"]["gate"]
    else:
        g = apply_gate(gate_depth, gate_err, b, len(dips), out["variability_flag"], gate_mode, quiet_max_dips,
                       **(p10_kw if gate_mode in GATE_MODES_P10 else {}))
    if gate_mode in GATE_MODES_P10:
        out["gate_p10"] = g
    if p8_mode and "quiet" in g:
        out["gate_quiet_scan"] = g["quiet"]
    if g["gate"] == "FAIL":
        out["gate"] = "FAIL"
        out["verdict"] = (f"SECONDARY ECLIPSE: a dip at phase {d['phase']:.4f} of "
                          f"{gate_depth:.3f} +/- {gate_err:.3f} ppt in the {gate_flux} flux is "
                          f"{out['secondary_sigma_over_planet_bound']:.1f} sigma above the deepest "
                          f"secondary a planet could make ({b:.2e} ppt)"
                          + (f" ({g['sigma_over_bound_empirical']:.1f} sigma of the scan's own scatter; recurs "
                             f"{g['recurs']}; present in both fluxes {g.get('present_both')}; mode {gate_mode})"
                             if gate_mode in GATE_MODES_P10 + GATE_MODES_K1
                             else (f" on a quiet scan ({len(dips)} dips)" if p8_mode else ""))
                          + " -> stellar companion")
    elif g["gate"] == "HOLD":
        out["gate"] = "HOLD"
        out["verdict"] = (f"VARIABILITY (HOLD): {len(dips)} dips above 5 sigma at scattered phases; "
                          "the scan cannot separate a secondary from stellar variability, so the candidate "
                          "is held, not passed")
    elif out["variability_flag"]:
        out["verdict"] = (f"VARIABILITY: {len(dips)} dips above 5 sigma at scattered phases, so the "
                          "scan is measuring stellar variability or red noise, not an eclipse; "
                          "no secondary claim is made")
    else:
        out["verdict"] = (f"a dip at phase {d['phase']:.4f} at {d['sigma']:.1f} sigma, within the "
                          "planetary bound in the gate flux; not decisive")
    return out
