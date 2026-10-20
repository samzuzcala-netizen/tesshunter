"""RULES_K2 section 3 (A1): within-family depth consistency in Stage A.

* a constant-depth planet with a 5% TESS-SPOC / QLP depth offset passes (and fails K1's test);
* an alternating-depth EB still fails;
* a blend-like 40% family offset at high SNR fails;
* the default path (option None) is unchanged: no ``a1`` block, K1 criteria, and stored K1 Stage A receipts
  re-evaluate to their recorded criteria.
"""
import glob
import json

import numpy as np
import pytest

from tesshunter import event_vet as EV


@pytest.fixture(autouse=True)
def _restore():
    old = EV.DEPTH_CONSISTENCY_FAMILIES
    yield
    EV.DEPTH_CONSISTENCY_FAMILIES = old


def _events(depths, errs, authors, cads=None):
    cads = cads or [200.0] * len(depths)
    return [{"n": i, "sector": 60 + i, "author": a, "cadence_s": c, "det_depth_ppt": float(d), "det_depth_err_ppt": float(s)}
            for i, (d, s, a, c) in enumerate(zip(depths, errs, authors, cads))]


def _criterion(evs, scope, survey_depth=10.0):
    EV.DEPTH_CONSISTENCY_FAMILIES = scope
    st = EV.kept_event_stats(evs, "det")
    return EV.stagea_criteria(st, survey_depth), st


def test_constant_depth_planet_with_5pct_product_offset_passes():
    rng = np.random.default_rng(1)
    n, q = 20, 15                                         # TESS-SPOC carries more weight: the dominant family
    d = np.r_[10.0 + rng.normal(0, 0.1, n), 9.5 + rng.normal(0, 0.1, q)]
    evs = _events(d, [0.1] * (n + q), ["TESS-SPOC"] * n + ["QLP"] * q)
    k1, st0 = _criterion(evs, None)
    assert "a1" not in st0
    assert not k1["criteria"]["depths_consistent_p_ge_1e-3"]
    for scope in ("author", "author_exposure"):
        c, st = _criterion(evs, scope)
        assert c["criteria"]["depths_consistent_p_ge_1e-3"]
        assert c["depth_consistency_a1"]["rescued"] and not c["depth_consistency_a1"]["k1_consistent"]
        assert st["a1"]["author"]["families"]["QLP"]["ratio_to_dominant"] == pytest.approx(0.95, abs=0.01)


def test_alternating_depth_eb_still_fails():
    n = 24
    d = np.array([10.0 if i % 2 else 7.0 for i in range(n)])
    evs = _events(d, [0.2] * n, ["TESS-SPOC", "QLP"] * (n // 2), [200.0, 600.0] * (n // 2))
    for scope in (None, "author", "author_exposure"):
        c, _ = _criterion(evs, scope)
        assert not c["criteria"]["depths_consistent_p_ge_1e-3"]


def test_blend_like_family_offset_fails():
    rng = np.random.default_rng(2)
    n = 15
    d = np.r_[10.0 + rng.normal(0, 0.1, n), 6.0 + rng.normal(0, 0.1, n)]
    evs = _events(d, [0.1] * (2 * n), ["TESS-SPOC"] * n + ["QLP"] * n)
    c, st = _criterion(evs, "author")
    assert st["a1"]["author"]["p_within"] > 1e-3 and not st["a1"]["author"]["means_agree"]
    assert not c["criteria"]["depths_consistent_p_ge_1e-3"]


def test_k1_pass_is_never_changed_and_default_output_identical():
    rng = np.random.default_rng(3)
    d = 5.0 + rng.normal(0, 0.5, 12)
    evs = _events(d, [0.5] * 12, ["TESS-SPOC"] * 6 + ["QLP"] * 6)
    c0, st0 = _criterion(evs, None)
    c1, st1 = _criterion(evs, "author")
    assert c0["criteria"] == c1["criteria"]
    assert {k: v for k, v in st1.items() if k != "a1"} == st0
    assert {k: v for k, v in c1.items() if k != "depth_consistency_a1"} == c0


def test_stored_k1_stage_a_receipts_reproduce_under_default():
    """K1 Stage A receipts: the recorded per-ephemeris det_kept block re-evaluates to the recorded criteria."""
    files = sorted(glob.glob(r"D:/tesshunter_k1/funnel_receipts/dev_k1/A/*.json"))[:60]
    if not files:
        pytest.skip("K1 receipts not available")
    EV.DEPTH_CONSISTENCY_FAMILIES = None
    n = 0
    for f in files:
        m = json.load(open(f, encoding="utf-8")).get("measurement") or {}
        for src, per in (m.get("per_ephemeris") or {}).items():
            got = EV.stagea_criteria(per["det_kept"], m["survey"]["depth_ppt"], p_min=1e-3)
            assert got["criteria"] == per["criteria"], (f, src)
            n += 1
    assert n > 50
