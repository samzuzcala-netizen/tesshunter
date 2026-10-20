"""RULES_K1 section 2.2: the identity (matching) rule, evaluator side only.

A candidate (P_c, T0_c, d_c) matches a truth signal (P_t, T0_t, T14_t, sigma_t(epoch)) when for some
r in {1, 2, 1/2, 3, 1/3}: |P_c / (r P_t) - 1| < 0.01, and on the actual timestamps of the arm's usable
products the truth events E_T (epochs with a cadence within T14_t/2 of the truth mid-time) and the
candidate events E_C (epochs with a cadence within d_c/2 of the candidate mid-time) coincide (mid-times
closer than 0.5 max(T14_t, d_c) + 3 sigma_t) with coverage >= 0.8 min(1, 1/r), precision >= 0.8 min(1, r)
and at least 3 coinciding events.
"""
from __future__ import annotations

import numpy as np

RATIOS = (1.0, 2.0, 0.5, 3.0, 1.0 / 3.0)
PERIOD_TOL = 0.01


def observed_epochs(times: np.ndarray, period: float, t0: float, half_window: float) -> np.ndarray:
    t = np.asarray(times, float)
    k = np.round((t - t0) / period).astype(np.int64)
    inside = np.abs(t - (t0 + k * period)) <= half_window
    return np.unique(k[inside])


def match(times, cand: dict, truth: dict) -> dict:
    """``cand``: period, epoch, duration (days).  ``truth``: period, t0, t14, sigma_t0, sigma_p (days)."""
    pc, tc, dc = float(cand["period"]), float(cand["epoch"]), float(cand["duration"])
    pt, tt, t14 = float(truth["period"]), float(truth["t0"]), float(truth["t14"])
    st0, sp = float(truth.get("sigma_t0") or 0.0), float(truth.get("sigma_p") or 0.0)
    best = {"matched": False, "ratio": None}
    for r in RATIOS:
        frac = abs(pc / (r * pt) - 1.0)
        if frac >= PERIOD_TOL:
            continue
        et = observed_epochs(times, pt, tt, t14 / 2.0)
        ec = observed_epochs(times, pc, tc, dc / 2.0)
        if et.size == 0 or ec.size == 0:
            continue
        mt = tt + et * pt
        mc = tc + ec * pc
        sig = np.sqrt(st0 ** 2 + (et * sp) ** 2)
        tol_t = 0.5 * max(t14, dc) + 3.0 * sig
        # nearest candidate event to each truth event, and vice versa
        j = np.searchsorted(mc, mt)
        d_t = np.min(np.abs(np.stack([mc[np.clip(j - 1, 0, mc.size - 1)], mc[np.clip(j, 0, mc.size - 1)]]) - mt), axis=0)
        hit_t = d_t <= tol_t
        i = np.searchsorted(mt, mc)
        lo, hi = np.clip(i - 1, 0, mt.size - 1), np.clip(i, 0, mt.size - 1)
        d_c = np.minimum(np.abs(mt[lo] - mc), np.abs(mt[hi] - mc))
        tol_c = 0.5 * max(t14, dc) + 3.0 * np.maximum(np.sqrt(st0 ** 2 + (np.round((mc - tt) / pt) * sp) ** 2), 0)
        hit_c = d_c <= tol_c
        coverage = float(hit_t.mean())
        precision = float(hit_c.mean())
        n_coincide = int(hit_t.sum())
        ok = (coverage >= 0.8 * min(1.0, 1.0 / r) and precision >= 0.8 * min(1.0, r) and n_coincide >= 3)
        rec = {"matched": bool(ok), "ratio": r, "period_frac": frac, "coverage": coverage, "precision": precision,
               "n_coincide": n_coincide, "n_truth_events": int(et.size), "n_cand_events": int(ec.size)}
        if ok:
            return rec
        if best.get("coverage") is None or coverage > best.get("coverage", -1):
            best = rec
    return best


def period_matches(p_found: float, p_true: float) -> dict:
    """The Stage C rematch: the blind period within 1% of the truth at a registered ratio."""
    for r in RATIOS:
        if abs(p_found / (r * p_true) - 1.0) < PERIOD_TOL:
            return {"matched": True, "ratio": r}
    return {"matched": False, "ratio": None}


def candidate_period(row) -> float:
    """AMENDMENT_K1_20261012_7: P_c of rule 2.2 is the candidate's stitch re-measured period (``stitch_period_days``,
    measured on all of the arm's data) when it is finite and within 1% of the reported ``period_days``; otherwise
    ``period_days``.  A period measured on one chunk drifts off the transits over a multi-year baseline."""
    p = float(row["period_days"])
    try:
        ps = float(row["stitch_period_days"])
    except (KeyError, TypeError, ValueError):
        return p
    return ps if (ps == ps and ps > 0 and abs(ps / p - 1.0) < 0.01) else p

