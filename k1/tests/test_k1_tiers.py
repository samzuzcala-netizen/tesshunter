"""K1 change 13: a density-only K8 at P > 10 d becomes HOLD (k8_density_long_period)."""
import copy

import rules_k1


def _ev(k8, others=None):
    cond = {"K1": {"fired": False}, "K8": k8, "K9": {"fired": False}, "H1": {"fired": False}}
    cond.update(others or {})
    return {"verdict": "KILL" if k8["fired"] else "SUBMIT", "deciding_condition": "K8" if k8["fired"] else None,
            "conditions": cond, "k_order": ["K1", "K8", "K9"], "h_order": ["H1"], "flags": {}}


DENSITY = {"fired": True, "density_kill": True, "radius_kill": False, "detail": "rho ratio 0.3"}


def test_density_kill_long_period_becomes_hold():
    ev = rules_k1.apply_k8_rule(copy.deepcopy(_ev(DENSITY)), 23.4)
    assert ev["verdict"] == "HOLD" and ev["deciding_condition"] == "K8_HOLD"
    assert ev["flags"]["k8_density_long_period"] is True and ev["p12_verdict"]["verdict"] == "KILL"


def test_short_period_density_kill_unchanged():
    ev = rules_k1.apply_k8_rule(copy.deepcopy(_ev(DENSITY)), 6.0)
    assert ev["verdict"] == "KILL" and ev["deciding_condition"] == "K8"


def test_radius_kill_never_demoted():
    k8 = {"fired": True, "density_kill": True, "radius_kill": True, "detail": "Rp 20 Re"}
    ev = rules_k1.apply_k8_rule(copy.deepcopy(_ev(k8)), 30.0)
    assert ev["verdict"] == "KILL" and ev["deciding_condition"] == "K8"


def test_a_later_kill_still_kills_after_demotion():
    ev = rules_k1.apply_k8_rule(copy.deepcopy(_ev(DENSITY, {"K9": {"fired": True, "detail": "sky"}})), 23.4)
    assert ev["verdict"] == "KILL" and ev["deciding_condition"] == "K9"


def test_hold_reason_before_k8_hold_keeps_order():
    ev = rules_k1.apply_k8_rule(copy.deepcopy(_ev(DENSITY, {"H1": {"fired": True, "detail": "nfpp"}})), 23.4)
    assert ev["verdict"] == "HOLD" and ev["deciding_condition"] == "H1"


def test_no_k8_no_change():
    ev = rules_k1.apply_k8_rule(copy.deepcopy(_ev({"fired": False})), 23.4)
    assert ev["verdict"] == "SUBMIT" and ev["flags"]["k8_density_long_period"] is False
