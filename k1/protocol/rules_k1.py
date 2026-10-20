"""K1 tiers ``k1.0`` = P12's ``p12.0`` (``p12/protocol/rules_p12.py``, imported read-only, with P12's
frozen K10 admission) plus change 13:

  a K8 outcome that fires ONLY on the density test (not on the radius test) at P > 10 d no longer
  kills; the candidate is re-evaluated without it and, if nothing else kills, is HOLD with the flag
  ``k8_density_long_period`` (the density test assumes a circular orbit, so an eccentric planet's
  duration reads as a wrong stellar density).

Everything else is p12.0 unchanged.  ``evaluate`` returns the p12.0 record with ``rules_version``
``k1.0``, the original p12.0 verdict under ``p12_verdict`` and the K8 demotion record.
"""
from __future__ import annotations

import sys

from k1_common import REPO

K8_HOLD_MIN_PERIOD_DAYS = 10.0
RULES_VERSION = "k1.0"


def _p12():
    p = str(REPO / "p12" / "protocol")
    if p not in sys.path:
        sys.path.insert(0, p)
    import rules_p12
    return rules_p12


def k8_demotion(conditions: dict, period: float) -> dict:
    k8 = conditions.get("K8") or {}
    demote = bool(k8.get("fired") and k8.get("density_kill") and not k8.get("radius_kill")
                  and float(period) > K8_HOLD_MIN_PERIOD_DAYS)
    return {"demoted": demote, "period_days": float(period), "min_period_days": K8_HOLD_MIN_PERIOD_DAYS,
            "k8_density_kill": bool(k8.get("density_kill")), "k8_radius_kill": bool(k8.get("radius_kill"))}


def apply_k8_rule(ev: dict, period: float) -> dict:
    """Re-decide a p12.0 record under the K1 K8 rule (pure; used by ``evaluate`` and the tests)."""
    conditions = ev["conditions"]
    dem = k8_demotion(conditions, period)
    ev["p12_verdict"] = {"verdict": ev["verdict"], "deciding_condition": ev["deciding_condition"]}
    ev["k1_k8"] = dem
    ev["rules_version"] = RULES_VERSION
    ev.setdefault("flags", {})["k8_density_long_period"] = dem["demoted"]
    if not dem["demoted"]:
        return ev
    k8 = dict(conditions["K8"])
    conditions["K8"] = dict(k8, fired=False, k1_demoted=True,
                            detail="[K1 change 13: density-only K8 at P > 10 d -> HOLD] " + str(k8.get("detail")))
    conditions["K8_HOLD"] = dict(fired=True, measurable=True, detail="k8_density_long_period: " + str(k8.get("detail")))
    k_order = list(ev.get("k_order") or [])
    h_order = list(ev.get("h_order") or []) + ["K8_HOLD"]
    verdict, deciding = "SUBMIT", None
    for name in k_order:
        if conditions[name]["fired"]:
            verdict, deciding = "KILL", name
            break
    if verdict == "SUBMIT":
        for name in h_order:
            if conditions[name]["fired"]:
                verdict, deciding = "HOLD", name
                break
    ev.update(verdict=verdict, deciding_condition=deciding, h_order=h_order,
              deciding_detail=None if deciding is None else conditions[deciding]["detail"],
              candidate_tier=None if verdict != "SUBMIT" else ev.get("candidate_tier"))
    return ev


def evaluate(inputs: dict, *, redact_catalogue: bool = False) -> dict:
    ev = _p12().evaluate(inputs, "p12.0", redact_catalogue=redact_catalogue)
    return apply_k8_rule(ev, float(inputs["period"]))
