"""K1 amendment 2: the exposure-aware Stage A per-event depth (event_vet.EVENT_DEPTH_TEMPLATE)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from tesshunter import event_vet

U_TRUE = (0.50, 0.18)          # deliberately not the template's (0.45, 0.20), and b != 0
B_TRUE = 0.4


def _ld_transit(t, period, t0, dur, depth, exposure_s, n_sub=31):
    """Exposure-integrated limb-darkened small-planet transit (chord through impact parameter B_TRUE)."""
    off = ((np.arange(n_sub) + 0.5) / n_sub - 0.5) * exposure_s / 86400.0
    tt = t[:, None] + off[None, :]
    x = ((tt - t0 + 0.5 * period) % period) - 0.5 * period
    s = np.clip(2.0 * np.abs(x) / dur, 0.0, 1.0)
    r = np.sqrt(B_TRUE ** 2 + (1.0 - B_TRUE ** 2) * s * s)
    mu = np.sqrt(np.clip(1.0 - r * r, 0.0, 1.0))
    u1, u2 = U_TRUE
    prof = np.where(np.abs(x) < dur / 2.0, (1.0 - u1 * (1.0 - mu) - u2 * (1.0 - mu) ** 2) / (1.0 - u1 / 3 - u2 / 6), 0.0)
    return 1.0 - depth * prof.mean(axis=1)


def _product(sector, cadence_s, depth_fn, sigma_1h_ppm=150.0, days=24.0, seed=0):
    rng = np.random.default_rng(seed + sector)
    t0 = 1400.0 + 27.4 * sector
    n = int(days * 86400.0 / cadence_s)
    t = t0 + np.arange(n) * cadence_s / 86400.0
    f = depth_fn(t, cadence_s) + sigma_1h_ppm * 1e-6 * math.sqrt(3600.0 / cadence_s) * rng.standard_normal(n)
    return {"sector": sector, "author": "QLP", "cadence_s": float(cadence_s), "n": n, "file": f"s{sector}.npz",
            "time": t, "flux": f.copy(), "flux_err": np.full(n, np.nan), "sap_flux": f.copy(), "flux_column": "kspsap_flux",
            "sap_flux_err": np.full(n, np.nan), "sap_bkg": np.full(n, 10.0), "quality": np.zeros(n, dtype=np.int64)}


P, DUR, DEPTH = 2.3719, 0.07, 8e-3


def _events(depth_of_epoch=None):
    """Every observed event of a three-cadence (1800 / 600 / 200 s) target."""
    t0 = 1400.0 + 27.4 * 5 + 0.61

    def fn(t, cad):
        if depth_of_epoch is None:
            return _ld_transit(t, P, t0, DUR, DEPTH, cad)
        n = np.round((t - t0) / P)
        return np.where(n % 2 == 0, _ld_transit(t, P, t0, DUR, depth_of_epoch[0], cad),
                        _ld_transit(t, P, t0, DUR, depth_of_epoch[1], cad))
    evs = []
    for sector, cad in ((5, 1800.0), (40, 600.0), (60, 200.0)):
        p = _product(sector, cad, fn, seed=11)
        n0, n1 = math.ceil((p["time"][0] + 0.6 - t0) / P), math.floor((p["time"][-1] - 0.6 - t0) / P)
        for n in range(n0, n1 + 1):
            tc = t0 + n * P
            ev = event_vet.measure_event(p, tc, DUR, DEPTH, p["time"], p["flux"], n)
            if ev.get("observed") and ev.get("det_depth_ppt") is not None:
                evs.append(ev)
    return evs


def _class_means(evs):
    out = {}
    for c in (1800.0, 600.0, 200.0):
        d = np.array([e["det_depth_ppt"] for e in evs if e["cadence_s"] == c])
        s = np.array([e["det_depth_err_ppt"] for e in evs if e["cadence_s"] == c])
        w = 1 / s ** 2
        out[c] = float((d * w).sum() / w.sum())
    return out


def test_template_has_unit_chord_mean_at_zero_exposure():
    x = np.linspace(-DUR / 2, DUR / 2, 20001)[1:-1]
    assert event_vet.exposure_ld_template(x, DUR, 1e-9).mean() == pytest.approx(1.0, abs=2e-3)
    # a long exposure spreads the profile beyond +/- T/2 and conserves its integral
    xx = np.linspace(-DUR, DUR, 40001)
    a0 = np.trapezoid(event_vet.exposure_ld_template(xx, DUR, 1e-9), xx)
    a1 = np.trapezoid(event_vet.exposure_ld_template(xx, DUR, 1800 / 86400), xx)
    assert a1 == pytest.approx(a0, rel=5e-3)


def test_default_estimator_is_the_box_mean(monkeypatch):
    monkeypatch.setattr(event_vet, "EVENT_DEPTH_TEMPLATE", None)
    evs = _events()
    e = evs[0]
    assert "det_depth_estimator" not in e
    # the 1800-s box means are smeared shallow relative to 200 s and scatter with the sampling phase, so a
    # constant-depth transit fails the consistency criterion (the defect the amendment removes)
    m = _class_means(evs)
    assert m[1800.0] < 0.99 * m[200.0]
    stats = event_vet.kept_event_stats(evs, "det")
    assert stats["p_const"] < 1e-3 and stats["chi2_const"] / stats["dof"] > 5


def test_exposure_ld_depths_agree_across_cadences(monkeypatch):
    monkeypatch.setattr(event_vet, "EVENT_DEPTH_TEMPLATE", "exposure_ld")
    evs = _events()
    assert all(e["det_depth_estimator"] == "exposure_ld" for e in evs)
    m = _class_means(evs)
    assert m[1800.0] == pytest.approx(m[200.0], rel=0.03)
    assert m[600.0] == pytest.approx(m[200.0], rel=0.03)
    stats = event_vet.kept_event_stats(evs, "det")
    assert stats["n"] >= 25
    assert stats["p_const"] >= 1e-3
    # the amplitude keeps the meaning of a depth: within 10% of the injected chord-mean depth
    assert stats["weighted_mean_depth_ppt"] == pytest.approx(1000 * DEPTH * 1.0, rel=0.10)


def test_exposure_ld_still_flags_inconsistent_depths(monkeypatch):
    monkeypatch.setattr(event_vet, "EVENT_DEPTH_TEMPLATE", "exposure_ld")
    evs = _events(depth_of_epoch=(8e-3, 5e-3))
    stats = event_vet.kept_event_stats(evs, "det")
    assert stats["p_const"] < 1e-3
    assert stats["odd_even"]["sigma"] > 5
