"""Prompt-10 Part 2c: the Stage C statistics and the strongest-peak rule, pure.

* :func:`floor_duration`: a reported TLS duration floored at one cadence before it enters a
  matching or coverage rule (gotcha 12); the raw value is kept beside it.
* :func:`covered_transits`: distinct transit epochs of an ephemeris covered by the data.
* :func:`concentration` / :func:`robust_sde`: the largest single ordinate's share of a
  spectrum's centred variance, and the MAD-normalised SDE (HANDOFF_P10.md 0.4 i).
* :func:`sde_fallback`: the pre-registered fallback rule (consult SDE_robust only when the
  concentration exceeds ``C_CONCENTRATION_TRIGGER``; the threshold stays 9).
* :func:`significant_peak`: the ``significant_peak`` strongest-peak rule (0.4 ii), given the
  spectrum, the peak table and, when a stronger unrelated peak with at least three covered
  transits exists, the residual-run local SDE.

Every number is a ``C_*`` constant of :mod:`tesshunter.audit_rules`.  Nothing here runs TLS;
``scripts/revet_p6.py`` and ``scripts/audit_p5.py`` supply the runs.
"""
from __future__ import annotations

import math

import numpy as np

from .audit_rules import (
    C_ALIAS_P_CONST,
    C_CONCENTRATION_TRIGGER,
    C_RESIDUAL_MIN_TRANSITS,
    C_SDE,
    C_TOL,
    TIER_ALIAS_RATIOS,
)

BLOCKING_ALIASES = ("3:1", "1:3", "3:2", "2:3")
DEPTH_TESTED_ALIASES = ("2:1", "1:2")
IMPLEMENTATION = "p10-stage-c-20260910"


def floor_duration(duration_days: float | None, cadence_s: float) -> dict:
    """The duration a matching or coverage rule may use: never below one cadence."""
    if duration_days is None or not math.isfinite(float(duration_days)):
        return {"raw_days": duration_days, "floored_days": None, "floored": False, "cadence_days": cadence_s / 86400.0}
    cad = float(cadence_s) / 86400.0
    raw = float(duration_days)
    return {"raw_days": raw, "floored_days": max(raw, cad), "floored": bool(raw < cad), "cadence_days": cad}


def duration_summary(summary: dict, cadence_s: float) -> dict:
    """Return a TLS summary with the usable duration and its unchanged raw value."""
    raw = summary.get("duration_raw_days", summary.get("duration_days"))
    floor = floor_duration(raw, cadence_s)
    return dict(summary, duration_raw_days=raw, duration_days=floor["floored_days"], duration_floor=floor)


def covered_transits(t: np.ndarray, period: float, t0: float, duration_days: float,
                     min_coverage: float = 0.5, cadence_days: float | None = None) -> int:
    """Distinct transit epochs whose in-transit window holds at least ``min_coverage`` of the
    cadences it would hold at the median cadence."""
    t = np.sort(np.asarray(t, dtype=float))
    if t.size < 2 or not (period > 0 and duration_days > 0):
        return 0
    cad = float(np.median(np.diff(t))) if cadence_days is None else float(cadence_days)
    expected = max(1.0, duration_days / max(cad, 1e-9))
    n0, n1 = math.ceil((t[0] - t0) / period), math.floor((t[-1] - t0) / period)
    n = 0
    for k in range(n0, n1 + 1):
        tc = t0 + k * period
        inside = np.searchsorted(t, tc + duration_days / 2) - np.searchsorted(t, tc - duration_days / 2)
        if inside / expected >= min_coverage:
            n += 1
    return int(n)


def concentration(power: np.ndarray) -> dict:
    """The largest single ordinate's share of the spectrum's centred variance (the P9
    definition), over every finite ordinate."""
    y = np.asarray(power, dtype=float)
    good = np.isfinite(y)
    if good.sum() < 3:
        return {"fraction": None, "index": None, "n": int(good.sum())}
    yg = y[good]
    ss = (yg - yg.mean()) ** 2
    total = float(ss.sum())
    j = int(np.argmax(ss))
    return {"fraction": float(ss[j] / total) if total > 0 else None, "index": int(np.flatnonzero(good)[j]),
            "value": float(yg[j]), "n": int(good.sum())}


def robust_sde(power: np.ndarray) -> np.ndarray:
    """``(power - median) / (1.4826 x MAD)``, no ordinate removed; NaN where the input is not finite."""
    y = np.asarray(power, dtype=float)
    good = np.isfinite(y)
    out = np.full(y.shape, np.nan)
    if good.sum() < 3:
        return out
    med = float(np.median(y[good]))
    mad = float(np.median(np.abs(y[good] - med)))
    if mad <= 0:
        return out
    out[good] = (y[good] - med) / (1.4826 * mad)
    return out


def sde_fallback(power: np.ndarray, peak_index: int | None, *, power_raw: np.ndarray | None = None) -> dict:
    """The 0.4 (i) rule at the installed spectrum's strongest peak: the robust statistic is
    consulted only when the concentration exceeds ``C_CONCENTRATION_TRIGGER``; then the peak
    passes the SDE test if ``SDE_robust >= C_SDE`` there."""
    conc = concentration(power)
    if power_raw is not None and np.shape(power_raw) != np.shape(power):
        raise ValueError("Installed and raw spectra must have the same trial grid")
    # The installed concentration triggers the fallback. Missing raw arrays are
    # not permission to substitute installed SDE for the registered statistic.
    rob = robust_sde(power_raw) if power_raw is not None else np.full(np.shape(power), np.nan)
    at_peak = float(rob[peak_index]) if (peak_index is not None and 0 <= peak_index < rob.size and np.isfinite(rob[peak_index])) else None
    triggered = bool(conc["fraction"] is not None and conc["fraction"] > C_CONCENTRATION_TRIGGER)
    return {"concentration": conc["fraction"], "concentration_index": conc["index"], "concentration_value": conc.get("value"),
            "sde_robust_at_peak": at_peak, "sde_robust_max": float(np.nanmax(rob)) if np.isfinite(rob).any() else None,
            "triggered": triggered, "passes_on_robust": bool(triggered and at_peak is not None and at_peak >= C_SDE),
            "trigger": C_CONCENTRATION_TRIGGER, "threshold": C_SDE, "raw_available": power_raw is not None,
            "peak_index": peak_index}


def alias_name(period: float, other: float, tol: float = C_TOL) -> str | None:
    """The integer ratio ``period / other`` within ``tol`` (the ``_match`` list), or None."""
    if not (period > 0 and other > 0):
        return None
    r = period / other
    best = min(TIER_ALIAS_RATIOS.items(), key=lambda kv: abs(r / kv[1] - 1.0))
    return best[0] if abs(r / best[1] - 1.0) < tol else None


def local_peak(periods: np.ndarray, power: np.ndarray, survey_period: float, tol: float = C_TOL) -> dict:
    """The spectrum inside +/- ``tol`` of the survey period: its maximum and whether that
    maximum is a local maximum (interior to the window) rather than the window's edge."""
    p = np.asarray(periods, dtype=float)
    w = np.asarray(power, dtype=float)
    m = (np.abs(p / survey_period - 1.0) < tol) & np.isfinite(w)
    if not m.any():
        return {"sde": None, "period": None, "is_local_maximum": False, "n_grid": 0}
    idx = np.flatnonzero(m)
    j = idx[int(np.nanargmax(w[idx]))]
    interior = idx[0] < j < idx[-1]
    # a maximum at the window edge still counts when the spectrum turns over just outside it
    if not interior:
        left = w[j - 1] if j - 1 >= 0 else -np.inf
        right = w[j + 1] if j + 1 < w.size else -np.inf
        interior = bool(np.isfinite(w[j]) and w[j] >= left and w[j] >= right)
    return {"sde": float(w[j]), "period": float(p[j]), "is_local_maximum": bool(interior), "n_grid": int(idx.size),
            "index": int(j)}


def significant_peak(survey_period: float, strongest: dict, peaks: list[dict], local: dict,
                     stronger_transits: dict | None = None, residual_local_sde: dict | None = None,
                     alias_depths_consistent: bool | dict | None = None,
                     robust_fallback: dict | None = None) -> dict:
    """The ``significant_peak`` rule (0.4 ii).

    ``strongest``: the installed strongest peak (``period``, ``SDE``); ``peaks``: the peak
    table (``period``, ``SDE``); ``local``: :func:`local_peak` at the survey period;
    ``stronger_transits``: covered transit count per stronger unrelated peak period (as a
    string key), where known; ``residual_local_sde``: the survey-period local SDE after
    masking each stronger signal with >= 3 transits, keyed the same way; ``alias_depths_consistent``:
    a per-peak mapping of measured 2:1 / 1:2 depth-consistency results. A boolean
    applies only to the strongest peak. An unmeasured alias requires a measurement.
    ``robust_fallback`` may satisfy the SDE requirement only at that same installed
    strongest peak, with the survey-period and local-maximum requirements retained.

    Returns PASS, FAIL, NEEDS_ALIAS_DEPTH or NEEDS_RESIDUAL with the blocking analysis.
    """
    out = {"rule": "significant_peak", "survey_period": survey_period, "local": local, "stronger": [], "decision": None}
    local_sde = local.get("sde")
    same_strongest = abs(float(strongest["period"]) / survey_period - 1.0) < C_TOL
    fb = robust_fallback or {}
    robust_here = bool(fb.get("passes_on_robust") and fb.get("triggered") and fb.get("raw_available")
                       and same_strongest and local.get("index") is not None
                       and local["index"] == strongest.get("index") == fb.get("peak_index")
                       and fb.get("sde_robust_at_peak") is not None and fb["sde_robust_at_peak"] >= C_SDE)
    out["robust_fallback_used"] = bool(robust_here and local_sde is not None and local_sde < C_SDE)
    if (local_sde is None or not math.isfinite(local_sde) or not local.get("is_local_maximum")
            or (local_sde < C_SDE and not robust_here)):
        out.update(decision="FAIL", reason=f"no local peak within 1% of the survey period at SDE >= {C_SDE} "
                                           f"(local maximum {local_sde}, is_local_maximum {local.get('is_local_maximum')})")
        return out
    # the strongest peak: the p8.0 case, kept verbatim
    if same_strongest and (float(strongest["SDE"]) >= C_SDE or robust_here):
        out.update(decision="PASS", reason=f"strongest peak {strongest['period']:.5f} d is within 1% at SDE {strongest['SDE']:.1f}")
        if out["robust_fallback_used"]:
            out["reason"] += f"; installed concentration triggers raw robust SDE {fb['sde_robust_at_peak']:.6f} at the same peak"
        return out
    stronger_unrelated = []
    for pk in peaks:
        p2, s2 = float(pk["period"]), float(pk["SDE"])
        if s2 <= local_sde or abs(p2 / survey_period - 1.0) < C_TOL:
            continue
        name = alias_name(survey_period, p2)
        entry = {"period": p2, "SDE": s2, "alias_of_survey_period": name}
        if name in BLOCKING_ALIASES:
            out["stronger"].append(dict(entry, blocks="alias"))
            out.update(decision="FAIL", reason=f"the survey period is a {name} alias of the stronger peak {p2:.5f} d (SDE {s2:.1f})")
            return out
        if name in DEPTH_TESTED_ALIASES:
            if isinstance(alias_depths_consistent, dict):
                consistent = alias_depths_consistent.get(f"{p2:.6f}")
            else:
                consistent = alias_depths_consistent if abs(p2 / float(strongest["period"]) - 1) < 1e-6 else None
            entry["depth_consistency"] = consistent
            if consistent is False:
                out["stronger"].append(dict(entry, blocks="alias_depths_inconsistent"))
                out.update(decision="FAIL", reason=f"the survey period is a {name} alias of the stronger peak {p2:.5f} d and the per-transit depths are inconsistent")
                return out
            out["stronger"].append(dict(entry, blocks=None if consistent is True else "alias_depths_unmeasured"))
            continue
        stronger_unrelated.append(entry)
    for entry in stronger_unrelated:
        key = f"{entry['period']:.6f}"
        n_tr = (stronger_transits or {}).get(key)
        entry["covered_transits"] = n_tr
        if n_tr is None:
            entry["blocks"] = "unknown_transits"
            out["stronger"].append(entry)
            continue
        if n_tr < C_RESIDUAL_MIN_TRANSITS:
            entry["blocks"] = None
            out["stronger"].append(entry)
            continue
        res = (residual_local_sde or {}).get(key)
        entry["residual_local_sde"] = res
        if res is None:
            entry["blocks"] = "residual_pending"
        elif res.get("sde") is not None and res["sde"] >= C_SDE and res.get("is_local_maximum", True):
            entry["blocks"] = None
        else:
            entry["blocks"] = "residual_below_threshold"
        out["stronger"].append(entry)
    blocking = [e for e in out["stronger"] if e.get("blocks") in ("residual_below_threshold",)]
    pending = [e for e in out["stronger"] if e.get("blocks") in ("residual_pending", "unknown_transits")]
    if blocking:
        e = blocking[0]
        out.update(decision="FAIL", reason=f"after masking the stronger {e['period']:.5f} d signal ({e['covered_transits']} transits) the "
                                           f"survey-period local SDE is {(e.get('residual_local_sde') or {}).get('sde')} < {C_SDE}")
    elif any(e.get("blocks") == "alias_depths_unmeasured" for e in out["stronger"]):
        out.update(decision="NEEDS_ALIAS_DEPTH", reason="A stronger 2:1 or 1:2 alias needs measured per-transit depth consistency")
    elif pending:
        out.update(decision="NEEDS_RESIDUAL", reason=f"{len(pending)} stronger unrelated peak(s) need a transit count or a residual run")
    else:
        out.update(decision="PASS", reason=f"local peak at SDE {local_sde:.1f} within 1%; no stronger peak blocks "
                                           f"({len(out['stronger'])} stronger peak(s) examined)")
    return out


__all__ = ["floor_duration", "duration_summary", "covered_transits", "concentration", "robust_sde", "sde_fallback", "alias_name",
           "local_peak", "significant_peak", "BLOCKING_ALIASES", "DEPTH_TESTED_ALIASES"]
