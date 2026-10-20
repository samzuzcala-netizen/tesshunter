"""Fast unit tests for the FU3 core methods (synthetic data only; no network, no large inputs).

Run:  <venv python> -m pytest code/tests -q
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from events import Template, admit, measure, pool  # noqa: E402

EPH = dict(P=24.0, T0=100.0, T14=3.6 / 24, k=0.04, a_rs=50.0, b=0.3, inc=89.66, u=[0.3, 0.3], depth_ppt=1.6,
           stellar=dict(rho_cgs=5.0, radius=0.5))


def seg(t, y, cad_s=600.0):
    return dict(label="synthetic", sector=1, t=t, y=y, cad_s=cad_s, quality_ok=np.ones(len(t), bool), t_all=t,
                quality_all=None, bkg_all=None)


def series(depth=1.5, noise=0.8, shift_d=0.0, cad_s=600.0, seed=1, tc=124.0):
    rng = np.random.default_rng(seed)
    t = np.arange(tc - 1.0, tc + 1.0, cad_s / 86400)
    h = Template(EPH)(t - tc - shift_d, cad_s / 86400)
    y = -depth * h + rng.normal(0, noise, len(t))
    return seg(t, y, cad_s), tc


def test_template_unit_depth():
    tm = Template(EPH)
    assert abs(tm(np.array([0.0]), 600 / 86400)[0] - 1.0) < 1e-9
    assert tm(np.array([0.5]), 600 / 86400)[0] == pytest.approx(0.0, abs=1e-12)


def test_admission_is_sign_independent():
    s, tc = series(depth=1.5)
    s_neg = dict(s, y=-s["y"])
    assert admit(s, tc, EPH)[0] and admit(s_neg, tc, EPH)[0]


def test_admission_rejects_poor_coverage():
    s, tc = series()
    keep = np.abs(s["t"] - tc) > EPH["T14"] / 2 * 0.7      # leave only 30% in-transit coverage (< 50% rule)
    s2 = dict(s, quality_ok=keep)
    assert not admit(s2, tc, EPH)[0]


def test_depth_recovery_unbiased():
    est = [measure(*series(depth=1.5, noise=0.8, seed=k), EPH, Template(EPH), use_profile=False)["depth_ppt"] for k in range(40)]
    assert abs(np.mean(est) - 1.5) < 0.1


def test_negative_depth_is_reported_not_dropped():
    s, tc = series(depth=-1.0, noise=0.2)
    r = measure(s, tc, EPH, Template(EPH), use_profile=False)
    assert r["admitted"] and r["depth_ppt"] < 0


def test_timing_recovers_shift():
    s, tc = series(depth=3.0, noise=0.3, shift_d=20 / 1440, cad_s=200.0)
    r = measure(s, tc, EPH, Template(EPH))
    assert abs(r["oc_d"] * 1440 - 20) < 4


def test_pool_inflates_for_scatter():
    recs = [dict(admitted=True, depth_ppt=d, depth_err_ppt=0.1) for d in (1.0, 2.0, 1.0, 2.0)]
    p = pool(recs)
    assert p["err_ppt"] > p["err_white_ppt"]


def test_stassun_tmag_relation():
    from s13_fluxbudget import tmag
    T, how = tmag(13.2439, 14.2727, 12.2430)          # TIC 193718989 Gaia photometry
    assert how == "stassun2019" and abs(T - 12.31) < 0.02


def test_season_grouping_and_coherence():
    from s16_ttv_null import coherence
    rows = [dict(cycle=c, oc_d=v / 1440) for c, v in ((0, 5), (2, -3), (3, 4), (4, 1), (17, -60), (18, -55), (20, -62), (21, -58))]
    best, per = coherence(rows)
    assert best["n"] == 4 and best["stat"] > 50 and best["frac_same_sign"] == 1.0


def test_rv_mass_conversion_order_of_magnitude():
    from s15_rv_limits import k_to_mass
    m = k_to_mass(2.0, 24.1, 0.56)       # 2 km/s at 24 d around 0.56 Msun ~ 20 MJ
    assert 15 < m < 25


def test_binomial_limits():
    from s08_summarize import cp, ul95
    assert ul95(0, 27) == pytest.approx(1 - 0.05 ** (1 / 27), rel=1e-6)
    lo, hi = cp(4, 8)
    assert 0 < lo < 0.5 < hi < 1
    assert cp(0, 8)[0] == 0.0 and cp(8, 8)[1] == 1.0


def test_clip_isolated_keeps_transit_drops_outlier():
    from s19_freeshape_timing import clip_isolated
    s, tc = series(depth=1.5, noise=0.8, seed=3)
    y = s["y"].copy()
    i = len(y) // 3
    y[i] += 25.0
    keep = clip_isolated(s["t"], y, s["cad_s"] / 86400)
    assert not keep[i]
    intr = np.abs(s["t"] - tc) < EPH["T14"] / 2
    assert keep[intr].mean() > 0.95


def test_bounded_freeshape_recovers_shift():
    from s19_freeshape_timing import fit_event
    s, tc = series(depth=3.0, noise=0.5, shift_d=30 / 1440, seed=5)
    b = fit_event(s["t"], s["y"], 0.5, tc, 0.4, EPH["T14"], s["cad_s"] / 86400, dmax=3 * 3.0, tlo=0.6, thi=1.6, dmin=0.0)
    assert abs(b.x[0] * 1440 - 30) < 10
    assert 0 < b.x[1] <= 9.0