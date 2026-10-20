"""The registered decision rules E1-E4 (RULES_K1 section 3) as pure functions of their measured inputs."""
from __future__ import annotations

E2_ORDER = ("bound", "empirical_bound", "recurrent_bound", "recurrent_bound_corr", "bound_alias")
BUDGETS = (2700.0, 5400.0, 8100.0)


def e1_cadence(delta_pp: float, delta_ci_low_pp: float, fa_pre_ratio: float, wall_ratio: float) -> dict:
    """Adopt survey_k1 over survey_k1_s56 iff all three hold."""
    a = delta_pp >= 3.0 and delta_ci_low_pp > 0.0
    b = fa_pre_ratio <= 1.5
    c = wall_ratio <= 3.0
    return {"adopt": "survey_k1" if (a and b and c) else "survey_k1_s56", "recovery_gain_ok": a,
            "fa_ok": b, "wall_ok": c, "delta_pp": delta_pp, "delta_ci_low_pp": delta_ci_low_pp,
            "fa_pre_ratio": fa_pre_ratio, "wall_ratio": wall_ratio}


def e2_mode(retention: dict, passthrough: dict, retained_counts: dict | None = None) -> dict:
    """Highest retention through S subject to DEV adversarial pass-through <= bound's + 5 pp; exact ties
    (equal retained counts, else equal retention) go to the simpler mode in E2_ORDER."""
    limit = passthrough["bound"] + 0.05
    allowed = [m for m in E2_ORDER if passthrough[m] <= limit + 1e-12]
    key = (lambda m: retained_counts[m]) if retained_counts else (lambda m: round(retention[m], 12))
    best = max(key(m) for m in allowed)
    choice = next(m for m in E2_ORDER if m in allowed and key(m) == best)
    return {"choice": choice, "allowed": allowed, "passthrough_limit": limit, "retention": retention,
            "passthrough": passthrough}


def e3_ramp(ret_on: float, ret_off: float, fa_on: float, fa_off: float) -> dict:
    gain = 100.0 * (ret_on - ret_off)
    ratio = (fa_on / fa_off) if fa_off > 0 else (float("inf") if fa_on > 0 else 1.0)
    adopt = gain >= 2.0 and ratio <= 1.2
    return {"adopt": adopt, "gain_pp": gain, "fa_ratio": ratio}


def e4_budget(partition_limited_fraction: dict) -> dict:
    """Smallest tested budget with <= 5% partition-limited hosts; else 8,100 s (and report)."""
    for b in BUDGETS:
        f = partition_limited_fraction.get(b, partition_limited_fraction.get(int(b)))
        if f is not None and f <= 0.05:
            return {"budget_s": b, "qualified": True, "fractions": partition_limited_fraction}
    return {"budget_s": 8100.0, "qualified": False, "fractions": partition_limited_fraction}
