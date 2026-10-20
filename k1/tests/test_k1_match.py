"""RULES_K1 2.2 matching rule."""
import numpy as np

import match_k1 as M

T = np.concatenate([1500 + np.arange(0, 25, 0.02), 2400 + np.arange(0, 25, 0.007), 3500 + np.arange(0, 25, 0.0023)])
TRUTH = {"period": 3.7, "t0": 1501.3, "t14": 0.12}


def test_exact_and_alias_matches():
    assert M.match(T, {"period": 3.700002, "epoch": 1501.31, "duration": 0.1}, TRUTH)["matched"]
    r2 = M.match(T, {"period": 7.4, "epoch": 1501.31, "duration": 0.1}, TRUTH)
    assert r2["matched"] and r2["ratio"] == 2.0 and 0.4 < r2["coverage"] < 0.6
    rh = M.match(T, {"period": 1.85, "epoch": 1501.31, "duration": 0.1}, TRUTH)
    assert rh["matched"] and rh["ratio"] == 0.5
    # a 1e-4 fractional period error drifts ~0.2 d over the 6-year baseline: no longer the same events
    assert not M.match(T, {"period": 3.7004, "epoch": 1501.31, "duration": 0.1}, TRUTH)["matched"]


def test_period_coincidence_alone_is_not_enough():
    # right period, wrong phase: no coinciding events
    assert not M.match(T, {"period": 3.7, "epoch": 1501.3 + 1.6, "duration": 0.1}, TRUTH)["matched"]
    # unrelated period
    assert not M.match(T, {"period": 5.1, "epoch": 1501.3, "duration": 0.1}, TRUTH)["matched"]


def test_timing_uncertainty_widens_tolerance():
    # the catalogue period is off by 1.5 sigma_p: the drift grows with epoch, inside 3 sigma_t(epoch)
    drift = {"period": 3.7, "t0": 1501.3, "t14": 0.12, "sigma_t0": 0.0, "sigma_p": 2e-4}
    cand = {"period": 3.7 + 1.5 * 2e-4, "epoch": 1501.3, "duration": 0.1}
    assert not M.match(T, cand, dict(drift, sigma_p=0.0))["matched"]
    assert M.match(T, cand, drift)["matched"]


def test_stage_c_rematch():
    assert M.period_matches(7.402, 3.7)["ratio"] == 2.0 and not M.period_matches(5.0, 3.7)["matched"]


def test_candidate_period_prefers_stitch_and_falls_back():
    """Amendment 7: a chunk period drifts over a multi-year baseline; the stitch re-measured period is used."""
    import math
    import numpy as np
    import match_k1 as M
    assert M.candidate_period({"period_days": 1.0690543, "stitch_period_days": 1.0690009}) == 1.0690009
    assert M.candidate_period({"period_days": 1.0, "stitch_period_days": float("nan")}) == 1.0
    assert M.candidate_period({"period_days": 1.0, "stitch_period_days": 2.0}) == 1.0          # inconsistent -> reported
    assert M.candidate_period({"period_days": 3.0}) == 3.0
    # the drift itself: a 5e-5 relative error over ~2,400 cycles moves the predicted mid-time by ~0.13 d at P = 1.07 d
    times = np.arange(1400.0, 4000.0, 0.01)
    truth = {"period": 1.0690009, "t0": 1400.3, "t14": 0.05, "sigma_t0": 0.0, "sigma_p": 0.0}
    bad = M.match(times, {"period": 1.0690009 * (1 + 5e-5), "epoch": 1400.3, "duration": 0.05}, truth)
    good = M.match(times, {"period": 1.0690009 * (1 + 1e-6), "epoch": 1400.3, "duration": 0.05}, truth)
    assert good["matched"] and not bad["matched"]
