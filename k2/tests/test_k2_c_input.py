"""RULES_K2 section 2 (C1): the C input of each variant.

* binning preserves the transit-integrated depth;
* the cadence duration floor (coarsest in-transit cadence) follows the binned cadence;
* the K1 variant returns K1's C input unchanged; the oversampling rule; the point -> product mapping.
"""
import numpy as np
import pytest

import c_input_k2 as CI
from funnel_k1 import coarsest_in_transit_cadence_days

DAY = 86400.0


def _sector(t0, days, cad_s, sector):
    t = t0 + np.arange(0.0, days, cad_s / DAY)
    return t, np.full(t.size, sector)


def _transit(t, period, epoch, t14, depth):
    ph = np.abs(((t - epoch + 0.5 * period) % period) - 0.5 * period)
    return 1.0 - depth * (ph < 0.5 * t14)


def _arrays(parts, period=3.1, epoch=1.37, t14=2.5 / 24, depth=2e-3):
    t = np.concatenate([p[0] for p in parts])
    s = np.concatenate([p[1] for p in parts])
    o = np.argsort(t)
    t, s = t[o], s[o]
    f = _transit(t, period, epoch, t14, depth)
    return {"time": t, "flux": f, "flux_err": np.full(t.size, 1e-3), "time_unbinned": t, "sector_unbinned": s}


def _integrated(t, f, period, epoch, window=0.25):
    """Sum of (1 - f) dt over +/- window of each mid-time, with dt the local point spacing."""
    dt = np.gradient(t)
    ph = np.abs(((t - epoch + 0.5 * period) % period) - 0.5 * period)
    m = ph < window
    return float(np.sum((1.0 - f[m]) * dt[m]))


@pytest.mark.parametrize("variant", ["V2", "V3", "V1", "V4"])
def test_binning_preserves_transit_integrated_depth(variant):
    parts = [_sector(1000.0, 26.0, 200.0, 60), _sector(1100.0, 26.0, 600.0, 40)]
    arr = _arrays(parts)
    prods = [{"sector": 60, "cadence_s": 200.0}, {"sector": 40, "cadence_s": 600.0}]
    t, f, e, info = CI.transform(arr, prods, variant)
    native = _integrated(arr["time"], arr["flux"], 3.1, 1.37)
    binned = _integrated(t, f, 3.1, 1.37)
    assert native > 0
    assert binned == pytest.approx(native, rel=0.02)
    assert info["n_c_input"] < info["n_k1_input"]


def test_duration_floor_follows_binned_cadence():
    period, epoch, t14 = 3.1, 1.37, 2.5 / 24
    arr = _arrays([_sector(1000.0, 26.0, 200.0, 60)], period, epoch, t14)
    native = coarsest_in_transit_cadence_days(arr["time"], period, epoch, t14)
    assert native * DAY == pytest.approx(200.0)
    t30, *_ = CI.transform(arr, [{"sector": 60, "cadence_s": 200.0}], "V2")
    assert coarsest_in_transit_cadence_days(t30, period, epoch, t14) * DAY == pytest.approx(1800.0)
    t10, *_ = CI.transform(arr, [{"sector": 60, "cadence_s": 200.0}], "V1")
    assert coarsest_in_transit_cadence_days(t10, period, epoch, t14) * DAY == pytest.approx(600.0)
    # V1 keeps 1800-s products native: with events in an 1800-s sector the floor is 1800 s
    arr2 = _arrays([_sector(1000.0, 26.0, 200.0, 60), _sector(1100.0, 26.0, 1800.0, 10)], period, epoch, t14)
    prods = [{"sector": 60, "cadence_s": 200.0}, {"sector": 10, "cadence_s": 1800.0}]
    tm, *_ = CI.transform(arr2, prods, "V4")
    assert coarsest_in_transit_cadence_days(tm, period, epoch, t14) * DAY == pytest.approx(1800.0)


def test_k1_variant_is_identity_and_oversampling_rule():
    arr = _arrays([_sector(1000.0, 26.0, 200.0, 60)])
    t, f, e, info = CI.transform(arr, [{"sector": 60, "cadence_s": 200.0}], "K1")
    assert np.array_equal(t, arr["time"]) and np.array_equal(f, arr["flux"]) and np.array_equal(e, arr["flux_err"])
    assert info["n_sibling_masked"] == 0
    assert CI.oversampling("V3", 1500.0) == 2 and CI.oversampling("V3", 900.0) == 3
    assert CI.oversampling("V4", 1001.0) == 2 and CI.oversampling("V2", 2500.0) == 3
    assert CI.oversampling("V1", 2500.0) == 3 and CI.oversampling("K1", 2500.0) == 3
    with pytest.raises(ValueError):
        CI.oversampling("V9", 10.0)


def test_point_sectors_and_per_product_binning():
    parts = [_sector(1000.0, 5.0, 200.0, 60), _sector(1010.0, 5.0, 1800.0, 9)]
    arr = _arrays(parts)
    keep = np.ones(arr["time"].size, bool)
    keep[::7] = False                                     # a native-cadence clip removed some points
    sec = CI.point_sectors(arr["time"][keep], arr["time_unbinned"], arr["sector_unbinned"])
    assert np.array_equal(sec, arr["sector_unbinned"][keep])
    with pytest.raises(ValueError):
        CI.point_sectors(arr["time"][:3] + 1e-7, arr["time_unbinned"], arr["sector_unbinned"])
    t, f, e = CI.bin_per_product(arr["time"], arr["flux"], arr["flux_err"], arr["sector_unbinned"],
                                 {60: 200.0, 9: 1800.0}, 10.0)
    n1800 = int((arr["sector_unbinned"] == 9).sum())
    n200_binned = int(np.ceil(5.0 * DAY / 600.0))
    assert abs(t.size - (n1800 + n200_binned)) <= 1
    assert np.all(np.diff(t) > 0)


def test_bin_errors_are_propagated_and_keep_k1_weighting():
    """AMENDMENT_K2_20261014_1: bin error = sqrt(sum e^2) / n, so uniform per-cadence errors give e / sqrt(n) and
    no small set of bins carries the chi-square weight (the in-bin-scatter estimate from 3-9 points did)."""
    rng = np.random.default_rng(5)
    parts = [_sector(1000.0, 26.0, 200.0, 60), _sector(1100.0, 26.0, 600.0, 40)]
    arr = _arrays(parts)
    arr["flux"] = arr["flux"] + rng.normal(0, 1e-3, arr["flux"].size)
    t, f, e = CI.bin_series(arr["time"], arr["flux"], arr["flux_err"], 30.0)
    full = e[1:-1]
    assert np.all(np.isin(np.round(full / 1e-3 * np.sqrt(9), 6), [1.0])
                  | np.isin(np.round(full / 1e-3 * np.sqrt(3), 6), [1.0])
                  | (np.round(full / 1e-3, 6) <= 1.0))
    w = 1.0 / e ** 2
    top = np.sort(w)[::-1][: max(1, len(w) // 100)].sum() / w.sum()
    assert top < 0.05
    t2, f2, e2, info = CI.transform(arr, [{"sector": 60, "cadence_s": 200.0}, {"sector": 40, "cadence_s": 600.0}], "V3")
    assert info["bin_errors"] == "propagated" and np.allclose(e2, e)
