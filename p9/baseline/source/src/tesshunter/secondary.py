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
    SEC_GATE_SIGMA_OVER_BOUND,
    SEC_MAX_DIPS_BEFORE_VARIABILITY,
    SEC_MIN_PHASE_SEPARATION,
    SEC_MIN_SIGMA,
    SEC_PHASE_STEP,
    SEC_PRIMARY_PHASE_TOLERANCE,
    SEC_REFINE_HALF,
    SEC_REFINE_STEP,
)
from .vetting import planetary_secondary_bound_ppt

__all__ = ["box_depth", "phase_scan", "planet_secondary_bound", "secondary_scan", "apply_gate", "GATE_MODES",
           "split_primary_shoulders", "primary_exclusion_phase"]


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


def apply_gate(gate_depth: float, gate_err: float, bound: float, n_dips: int, variability: bool,
               mode: str = "bound", quiet_max_dips: int = 2) -> dict:
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
    """
    if mode not in GATE_MODES:
        raise ValueError(f"unknown secondary gate mode {mode!r}")
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
                   gate_mode: str = "bound", quiet_max_dips: int = 2) -> dict:
    """Scan every phase, judge what is found, and apply the gate.

    ``t``/``f`` are the prepared detrended series; ``t_sap``/``f_sap``, when
    given, are the same baseline in normalised raw SAP flux, in which the
    deepest off-phase dip is re-measured - the gate is on the SAP depth, so a
    dip the flux correction manufactured cannot fail a candidate.
    ``gate_mode`` / ``quiet_max_dips`` select the prompt-8 decision-1 variant
    (:func:`apply_gate`); the defaults are p7.0.  Under any other setting every
    variant's decision is also recorded under ``gate_by_mode`` so one scan
    measures them all.
    """
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
    g = apply_gate(gate_depth, gate_err, b, len(dips), out["variability_flag"], gate_mode, quiet_max_dips)
    if p8_mode:
        out["gate_quiet_scan"] = g["quiet"]
    if g["gate"] == "FAIL":
        out["gate"] = "FAIL"
        out["verdict"] = (f"SECONDARY ECLIPSE: a dip at phase {d['phase']:.4f} of "
                          f"{gate_depth:.3f} +/- {gate_err:.3f} ppt in the {gate_flux} flux is "
                          f"{out['secondary_sigma_over_planet_bound']:.1f} sigma above the deepest "
                          f"secondary a planet could make ({b:.2e} ppt)"
                          + (f" on a quiet scan ({len(dips)} dips)" if p8_mode else "")
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
