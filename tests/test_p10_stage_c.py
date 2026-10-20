"""Prompt 10 Part 2c: the duration floor, the SDE_robust fallback and the significant-peak
rule, each fired and just-not-fired at its threshold (HANDOFF_P10.md 0.4)."""
import numpy as np
import pytest

from tesshunter import audit_rules as R
from tesshunter import stage_c as C


def test_duration_floor_at_one_cadence():
    cad = 200.0 / 86400
    f = C.floor_duration(np.nextafter(cad, 0), 200.0)
    assert f["floored"] and f["floored_days"] == cad and f["raw_days"] < cad
    g = C.floor_duration(cad, 200.0)
    assert not g["floored"] and g["floored_days"] == cad
    assert C.floor_duration(89.71 / 86400, 200.0)["floored_days"] == pytest.approx(cad)
    assert C.floor_duration(None, 200.0)["floored_days"] is None


def test_covered_transits_counts_only_covered_epochs():
    cad = 200.0 / 86400
    t = np.concatenate([3000 + np.arange(5000) * cad, 3040 + np.arange(5000) * cad])   # two 11.6-day runs with a gap
    n_all = C.covered_transits(t, 3.0, 3000.5, 0.1)
    assert n_all == 8                                            # 4 in each 11.6-day run, none in the gap
    # an epoch inside the gap is not covered
    assert C.covered_transits(t, 100.0, 3025.0, 0.1) == 0
    # coverage just below and just above the 50% rule
    t2 = 3000 + np.arange(20) * cad                              # 20 cadences: a 0.1-d box needs 43
    assert C.covered_transits(t2, 5.0, 3000 + 10 * cad, 0.1) == 0
    assert C.covered_transits(t2, 5.0, 3000 + 10 * cad, 20 * cad / 0.5 - 1e-9) == 1


def _spectrum(n=20000, seed=5):
    rng = np.random.default_rng(seed)
    p = np.linspace(0.5, 110, n)
    w = rng.normal(0, 1, n)
    return p, w


def test_concentration_and_robust_sde_and_fallback_trigger():
    p, w = _spectrum()
    w[100] = 12.0                              # a real peak
    base = C.sde_fallback(w, 100, power_raw=w)
    assert base["concentration"] < R.C_CONCENTRATION_TRIGGER and not base["triggered"] and not base["passes_on_robust"]
    assert base["sde_robust_at_peak"] == pytest.approx(12.0, abs=0.6)
    # one extreme negative ordinate carries the variance: the fallback triggers and the peak
    # passes on the robust statistic (the HIP 97166 b pattern)
    w2 = w.copy(); w2[5000] = -400.0
    fb = C.sde_fallback(w2, 100, power_raw=w2)
    assert fb["concentration"] > R.C_CONCENTRATION_TRIGGER and fb["triggered"] and fb["passes_on_robust"]
    assert fb["concentration_index"] == 5000
    # the trigger boundary: concentration exactly at 0.5 does not trigger
    w3 = np.zeros(4); w3[0] = 1.0; w3[1] = -1.0      # two ordinates share the variance equally
    fb3 = C.sde_fallback(w3, 0, power_raw=w3)
    assert fb3["concentration"] == pytest.approx(0.5) and not fb3["triggered"]
    # below 9 on the robust statistic: triggered but not passing
    w4 = w.copy(); w4[5000] = -400.0; w4[100] = 8.0
    assert C.sde_fallback(w4, 100, power_raw=w4)["triggered"] and not C.sde_fallback(w4, 100, power_raw=w4)["passes_on_robust"]


def test_local_peak_interior_versus_edge():
    p = np.linspace(9.0, 11.0, 2001)
    w = np.zeros_like(p)
    w[np.argmin(np.abs(p - 10.0))] = 12.0
    loc = C.local_peak(p, w, 10.0)
    assert loc["sde"] == 12.0 and loc["is_local_maximum"] and abs(loc["period"] - 10.0) < 1e-6
    ramp = np.linspace(0, 20, 2001)                                # rises through the window: edge maximum
    loc2 = C.local_peak(p, ramp, 10.0)
    assert not loc2["is_local_maximum"]
    assert C.local_peak(p, w, 50.0)["sde"] is None


def _case(local_sde=16.85, strongest=(2.5271, 32.07), peaks=None, **kw):
    peaks = peaks if peaks is not None else [{"period": strongest[0], "SDE": strongest[1]}, {"period": 1.2635, "SDE": 17.0}, {"period": 18.0875, "SDE": local_sde}]
    return C.significant_peak(18.08896, {"period": strongest[0], "SDE": strongest[1]}, peaks,
                              {"sde": local_sde, "period": 18.0875, "is_local_maximum": True, "n_grid": 40}, **kw)


def test_significant_peak_needs_residual_then_passes_or_fails():
    # TOI-1470 c's configuration: the survey period is not an alias of the 2.527-d strongest peak
    r = _case()
    assert r["decision"] == "NEEDS_RESIDUAL"
    keys = {f"{2.5271:.6f}": 25, f"{1.2635:.6f}": 50}
    r2 = _case(stronger_transits=keys, residual_local_sde={k: {"sde": 12.0, "is_local_maximum": True} for k in keys})
    assert r2["decision"] == "PASS"
    r3 = _case(stronger_transits=keys, residual_local_sde={f"{2.5271:.6f}": {"sde": np.nextafter(R.C_SDE, 0), "is_local_maximum": True},
                                                          f"{1.2635:.6f}": {"sde": 12.0, "is_local_maximum": True}})
    assert r3["decision"] == "FAIL" and "after masking" in r3["reason"]
    r4 = _case(stronger_transits=keys, residual_local_sde={f"{2.5271:.6f}": {"sde": R.C_SDE, "is_local_maximum": True},
                                                          f"{1.2635:.6f}": {"sde": R.C_SDE, "is_local_maximum": True}})
    assert r4["decision"] == "PASS"
    # a stronger peak with fewer than three transits does not block (P8's one- or two-event winners)
    r5 = _case(stronger_transits={f"{2.5271:.6f}": 2, f"{1.2635:.6f}": 2})
    assert r5["decision"] == "PASS"


def test_significant_peak_local_threshold_and_alias_blocks():
    assert _case(local_sde=np.nextafter(R.C_SDE, 0))["decision"] == "FAIL"
    weak = C.significant_peak(18.08896, {"period": 2.5271, "SDE": 32.07}, [], {"sde": 12.0, "period": 18.09, "is_local_maximum": False})
    assert weak["decision"] == "FAIL"
    # the survey period is a 1:3 alias of a stronger peak: FAIL without a residual run
    third = C.significant_peak(6.0, {"period": 18.0, "SDE": 30.0}, [{"period": 18.0, "SDE": 30.0}],
                               {"sde": 12.0, "period": 6.0, "is_local_maximum": True})
    assert third["decision"] == "FAIL" and third["stronger"][0]["blocks"] == "alias"
    # a 2:1 alias keeps the depth-consistency test: inconsistent fails, consistent passes
    half = C.significant_peak(9.0, {"period": 18.0, "SDE": 30.0}, [{"period": 18.0, "SDE": 30.0}],
                              {"sde": 12.0, "period": 9.0, "is_local_maximum": True}, alias_depths_consistent=False)
    assert half["decision"] == "FAIL"
    half_ok = C.significant_peak(9.0, {"period": 18.0, "SDE": 30.0}, [{"period": 18.0, "SDE": 30.0}],
                                 {"sde": 12.0, "period": 9.0, "is_local_maximum": True}, alias_depths_consistent=True)
    assert half_ok["decision"] == "PASS"
    # the p8.0 case is kept verbatim: the strongest peak at the survey period passes
    same = C.significant_peak(10.0, {"period": 10.001, "SDE": 15.0}, [{"period": 10.001, "SDE": 15.0}],
                              {"sde": 15.0, "period": 10.001, "is_local_maximum": True})
    assert same["decision"] == "PASS"


def test_rule_set_fields_for_stage_c():
    rules = R.P10_RULES.with_options(stagec_peak_rule="significant_peak", stagec_sde_robust_fallback=True, duration_floor_cadence=True)
    assert rules.version == "p10.0-partial"
    assert R.P8_RULES.stagec_peak_rule == "strongest" and not R.P8_RULES.stagec_sde_robust_fallback
    assert R.C_CONCENTRATION_TRIGGER == 0.5 and R.C_RESIDUAL_MIN_TRANSITS == 3
