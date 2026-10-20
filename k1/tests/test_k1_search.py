"""K1 Part B tests, search side: changes 3, 4, 5, 10 and the exposure-aware statistics."""
from __future__ import annotations

import math

import numpy as np
import pytest

from tesshunter import audit_prep, bls_search, pipeline, survey, survey_p8


def _product(sector, cadence_s, days=25.0, sigma_1h_ppm=200.0, seed=0, t0=None, author="QLP"):
    """A quiet normalised product with white noise of ``sigma_1h_ppm`` per hour."""
    rng = np.random.default_rng(seed + sector)
    t0 = 1400.0 + 27.4 * sector if t0 is None else t0
    n = int(days * 86400.0 / cadence_s)
    t = t0 + np.arange(n) * cadence_s / 86400.0
    sig = sigma_1h_ppm * 1e-6 * math.sqrt(3600.0 / cadence_s)
    f = 1.0 + sig * rng.standard_normal(n)
    return {"sector": sector, "author": author, "cadence_s": float(cadence_s), "n": n, "file": f"s{sector}.npz",
            "time": t, "flux": f.copy(), "flux_err": np.full(n, np.nan), "sap_flux": f.copy(),
            "sap_flux_err": np.full(n, np.nan), "sap_bkg": np.full(n, 10.0), "quality": np.zeros(n, dtype=np.int64)}


def _box(t, period, t0, dur, depth):
    ph = np.abs(((t - t0 + 0.5 * period) % period) - 0.5 * period)
    return np.where(ph < dur / 2, 1.0 - depth, 1.0)


def _inject_box(products, period, t0, dur, depth):
    out = []
    for p in products:
        q = dict(p)
        m = _box(p["time"], period, t0, dur, depth)
        q["flux"] = p["flux"] * m
        q["sap_flux"] = p["sap_flux"] * m
        out.append(q)
    return out


# ── presets ───────────────────────────────────────────────────────────────────
def test_k1_presets_registered_values():
    k = survey.get_config("survey_k1")
    s = survey.get_config("survey_k1_s56")
    assert (k.period_min, k.period_max, k.duration_min, k.duration_max, k.n_durations) == (0.5, 50.0, 0.02, 0.35, 14)
    assert k.audit_window_days == 1.1 and k.audit_window_days >= 3 * k.duration_max
    assert k.deep_clip is False and k.empirical_flux_err is True and k.cadence_policy == "native_mixed"
    assert k.sector_min is None and k.sector_max == 98 and s.sector_min == 56 and s.sector_max == 98
    assert k.long_period_min == 10.0 and k.search_mode == "chunked" and k.min_transits == survey.get_config("survey_p10").min_transits
    assert k.exposure_aware and k.event_completeness_noise == "mean_err"
    assert k.ingest_key() != s.ingest_key() != survey.get_config("survey_p10").ingest_key()
    assert "cadence_policy" in k.to_dict() and "cadence_policy" not in survey.get_config("survey_p10").to_dict()


# ── change 4: the duration grid ───────────────────────────────────────────────
def test_duration_grid_k1_has_14_log_steps():
    g = bls_search._build_duration_grid(0.02, 0.35, n=14)
    assert len(g) == 14 and abs(g[0] - 0.02) < 1e-12 and abs(g[-1] - 0.35) < 1e-12
    r = g[1:] / g[:-1]
    assert np.allclose(r, r[0]) and 1.2 < r[0] < 1.3


def test_default_n_durations_is_10_and_switchable():
    assert bls_search.DEFAULT_N_DURATIONS == 10


def _lc_from(t, f, e):
    import lightkurve as lk
    from astropy import units as u
    from astropy.time import Time
    return lk.LightCurve(time=Time(t, format="btjd", scale="tdb"), flux=f * u.dimensionless_unscaled,
                         flux_err=e * u.dimensionless_unscaled)


def test_injected_5p5h_transit_recovered_at_true_duration_within_one_step():
    rng = np.random.default_rng(4)
    cad = 600.0 / 86400.0
    t = 2000.0 + np.arange(0, 54.0, cad)
    dur = 5.5 / 24.0
    f = _box(t, 9.37, 2003.1, dur, 2e-3) + 3e-4 * rng.standard_normal(t.size)
    saved = bls_search.DEFAULT_N_DURATIONS
    try:
        bls_search.DEFAULT_N_DURATIONS = 14
        _, _, c = bls_search.run_bls(_lc_from(t, f, np.full(t.size, 3e-4)), period_min=5.0, period_max=15.0,
                                     duration_min=0.02, duration_max=0.35, top_n=1)
    finally:
        bls_search.DEFAULT_N_DURATIONS = saved
    grid = bls_search._build_duration_grid(0.02, 0.35, n=14)
    step = grid[1] / grid[0]
    row = c.iloc[0]
    assert abs(row["period_days"] / 9.37 - 1) < 0.01
    assert dur / step <= row["duration_days"] <= dur * step


# ── change 3: no global deep clip; isolated dips still removed ────────────────
def test_deep_transit_keeps_in_transit_cadences_without_deep_clip():
    # Tmag 10.5 K dwarf: ~200 ppm/h -> ~0.85 ppt per 200-s cadence; a 20-ppt, 3-h transit
    prods = [_product(s, 200.0, seed=1) for s in (60, 61, 62)]
    period, t0, dur = 6.3, prods[0]["time"][0] + 1.7, 3.0 / 24.0
    inj = _inject_box(prods, period, t0, dur, 0.020)
    prep = survey_p8.prepare_search_input(inj, 1.1, deep_clip=False, empirical_err=True)
    tt = np.concatenate([p["time"] for p in inj])
    in_tr = _box(tt, period, t0, dur, 1.0) < 0.5
    kept = _box(prep["time"], period, t0, dur, 1.0) < 0.5
    assert kept.sum() >= 0.95 * in_tr.sum()
    legacy = survey_p8.prepare_search_input(inj, 0.75)
    kept_legacy = _box(legacy["time"], period, t0, dur, 1.0) < 0.5
    assert kept_legacy.sum() < 0.5 * in_tr.sum()          # the prompt-8 clip cuts the cores out
    assert prep["counters"]["deep_clip_applied"] is False and prep["counters"]["n_deep_clipped"] == 0


def test_isolated_single_cadence_dip_still_removed_without_deep_clip():
    p = _product(60, 200.0, seed=2)
    i = len(p["time"]) // 2
    p["flux"][i] -= 0.02                                  # one cadence 20 ppt low, neighbours normal
    prep = survey_p8.prepare_search_input([p], 1.1, deep_clip=False)
    assert not np.any(np.abs(prep["time"] - p["time"][i]) < 1e-7)
    assert prep["counters"]["n_isolated_clipped"] >= 1


# ── change 5: detrend window and depth retention ─────────────────────────────
def test_window_1p1d_retains_5h_transit_depth():
    prods = [_product(s, 200.0, seed=3, sigma_1h_ppm=100.0) for s in (70, 71)]
    period, t0, dur, depth = 4.9, prods[0]["time"][0] + 1.3, 5.0 / 24.0, 2e-3
    inj = _inject_box(prods, period, t0, dur, depth)
    det = audit_prep.clean_and_detrend(inj, 1.1)
    in_tr = _box(det["time"], period, t0, 0.8 * dur, 1.0) < 0.5
    measured = 1.0 - float(np.mean(det["flux"][in_tr]))
    assert measured >= 0.85 * depth


# ── change 10: mixed cadence ──────────────────────────────────────────────────
def test_native_mixed_keeps_coarse_products_and_bins_2min():
    prods = [_product(5, 1800.0), _product(40, 600.0), _product(60, 200.0), _product(61, 120.0, author="SPOC")]
    kept, notes = survey_p8.harmonise_cadence(prods, 200.0 / 60.0, policy="native_mixed")
    assert [int(p["sector"]) for p in kept] == [5, 40, 60, 61]
    cad = {int(p["sector"]): p["cadence_s"] for p in kept}
    assert cad == {5: 1800.0, 40: 600.0, 60: 200.0, 61: 200.0}
    legacy, _ = survey_p8.harmonise_cadence(prods, 200.0 / 60.0)
    assert [int(p["sector"]) for p in legacy] == [60, 61]


def test_empirical_errors_give_each_product_its_own_weight():
    # same noise per hour: per-cadence noise scales as sqrt(1/cadence), so 1800-s errors are 3x smaller
    prods = [_product(5, 1800.0, seed=5), _product(60, 200.0, seed=5)]
    prep = survey_p8.prepare_search_input(prods, 1.1, deep_clip=False, empirical_err=True)
    e5 = prep["flux_err"][prep["sector"] == 5]
    e60 = prep["flux_err"][prep["sector"] == 60]
    assert np.all(e5 == e5[0]) and np.all(e60 == e60[0])
    assert 2.6 < e60[0] / e5[0] < 3.4
    sig5 = 1.4826 * np.median(np.abs(prep["flux"][prep["sector"] == 5] - np.median(prep["flux"][prep["sector"] == 5])))
    assert abs(e5[0] / sig5 - 1) < 1e-9
    # inverse-variance weight per hour of data is the same for both products
    w5 = np.sum(1 / e5 ** 2) / (len(e5) * 1800.0)
    w60 = np.sum(1 / e60 ** 2) / (len(e60) * 200.0)
    assert 0.75 < w5 / w60 < 1.33
    assert set(prep["counters"]["empirical_flux_err_by_sector"]) == {"5", "60"}


def test_injection_integrates_each_product_over_its_own_exposure():
    from tesshunter.survey import transit_model
    prods = [_product(5, 1800.0, days=3.0), _product(60, 200.0, days=3.0)]
    tc = prods[0]["time"][40]
    inj, info = survey_p8.inject_products(prods, period=50.0, t0=tc, rp_rs=0.1, b=0.3, a_rs=60.0, u=(0.45, 0.2))
    m1800 = transit_model(prods[0]["time"], period=50.0, t0=tc, rp_rs=0.1, b=0.3, a_rs=60.0, u=(0.45, 0.2),
                          exp_time_days=1800.0 / 86400.0)
    assert np.allclose(inj[0]["flux"], prods[0]["flux"] * m1800)
    assert np.allclose(inj[0]["sap_flux"], prods[0]["sap_flux"] * m1800)
    tc2 = prods[1]["time"][300]
    inj2, _ = survey_p8.inject_products([prods[1]], period=50.0, t0=tc2, rp_rs=0.1, b=0.3, a_rs=60.0, u=(0.45, 0.2))
    m200 = transit_model(prods[1]["time"], period=50.0, t0=tc2, rp_rs=0.1, b=0.3, a_rs=60.0, u=(0.45, 0.2),
                         exp_time_days=200.0 / 86400.0)
    assert np.allclose(inj2[0]["flux"], prods[1]["flux"] * m200)


# ── exposure-aware statistics ─────────────────────────────────────────────────
def test_event_completeness_mean_err_judges_each_event_at_its_own_noise():
    # an 1800-s product and a 200-s product, same noise per hour; one 1.2-ppt, 2-h dip in each sector
    p5, p60 = _product(5, 1800.0, seed=7), _product(60, 200.0, seed=7)
    period, dur, depth = 10.0, 2.0 / 24.0, 1.2e-3
    t0 = p5["time"][0] + 3.0
    prods = _inject_box([p5, p60], period, t0, dur, depth)
    prep = survey_p8.prepare_search_input(prods, 1.1, deep_clip=False, empirical_err=True)
    lc = _lc_from(prep["time"], prep["flux"], prep["flux_err"])
    saved = bls_search.EVENT_COMPLETENESS_NOISE
    try:
        bls_search.EVENT_COMPLETENESS_NOISE = "mean_err"
        cov, dip, ec = bls_search.event_completeness(lc, period, t0, dur)
    finally:
        bls_search.EVENT_COMPLETENESS_NOISE = saved
    assert cov >= 4 and ec >= 0.7


def test_dip_threshold_mean_err_uses_inverse_variance_sum():
    saved = bls_search.EVENT_COMPLETENESS_NOISE
    try:
        bls_search.EVENT_COMPLETENESS_NOISE = "mean_err"
        assert abs(bls_search._dip_threshold(1.0, 4, inv_var_sum=4.0 / 0.01 ** 2) - 0.005) < 1e-12
        assert abs(bls_search._dip_threshold(0.01, 4, None) - 0.005) < 1e-12   # falls back to "mean"
        bls_search.EVENT_COMPLETENESS_NOISE = "cadence"
        assert bls_search._dip_threshold(0.01, 4, inv_var_sum=1.0) == 0.01     # legacy unchanged
    finally:
        bls_search.EVENT_COMPLETENESS_NOISE = saved


def test_gate7_uses_the_events_own_cadence():
    t1800 = 1500.0 + np.arange(0, 25.0, 1800.0 / 86400.0)
    t200 = 3500.0 + np.arange(0, 25.0, 200.0 / 86400.0)
    t = np.concatenate([t1800, t200])
    # an ephemeris whose events fall in both: the median of in-transit nearest-neighbour gaps
    cad_1800 = pipeline._in_transit_cadence_days(t1800, 5.0, 1502.0, 0.1)
    cad_200 = pipeline._in_transit_cadence_days(t200, 5.0, 3502.0, 0.1)
    assert abs(cad_1800 * 86400 - 1800) < 1 and abs(cad_200 * 86400 - 200) < 1
    # duration_min 0.02 d is under 2 cadences at 1800 s but not at 200 s
    assert pipeline._duration_is_railed(0.02, 0.02, cad_1800)
    assert not pipeline._duration_is_railed(0.02, 0.02, cad_200)
    # the legacy binned-median cadence of the mixed series is dominated by the 200-s data
    med = float(np.median(np.diff(np.sort(t))))
    assert abs(med * 86400 - 200) < 1


def test_exposure_aware_gate7_context_patches_and_restores():
    from tesshunter import bls_search as B
    orig_rail, orig_res = pipeline._duration_is_railed, B.resolve_aliases_for_candidate
    with pipeline.ExposureAwareGate7() as g:
        assert pipeline._duration_is_railed is not orig_rail and B.resolve_aliases_for_candidate is not orig_res
    assert pipeline._duration_is_railed is orig_rail and B.resolve_aliases_for_candidate is orig_res


def test_detect_planets_source_unchanged_from_base():
    # the P11.5 structural guard pins pipeline._detect_planets to its versioned copy; run that guard
    import importlib.util, pathlib
    path = pathlib.Path(__file__).resolve().parents[2] / 'p11' / 'p11_5' / 'tests' / 'test_search.py'
    spec = importlib.util.spec_from_file_location('p11_5_test_search', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.test_versioned_detector_is_identical_except_observer()


def test_stage_a_event_counts_are_cadence_aware():
    from tesshunter import event_vet
    p = _product(5, 1800.0, seed=9, days=10.0)
    tc = p["time"][0] + 4.0
    dur = 4.0 / 24.0
    q = _inject_box([p], 50.0, tc, dur, 3e-3)[0]
    q["flux_column"] = "kspsap_flux"
    ev = event_vet.measure_event(q, tc, dur, 3e-3, q["time"], q["flux"], 0)
    assert ev["observed"] and ev["coverage_in_transit"] >= 0.99
    assert ev["n_in"] == pytest.approx(dur / (1800.0 / 86400.0), abs=1)


def test_tls_duration_floor_uses_coarsest_in_transit_cadence():
    import funnel_k1
    t = np.concatenate([1500 + np.arange(0, 25, 1800 / 86400), 2400 + np.arange(0, 25, 600 / 86400),
                        3500 + np.arange(0, 25, 200 / 86400)])
    cad = funnel_k1.coarsest_in_transit_cadence_days(t, 5.83, 1501.0, 0.003)
    assert abs(cad * 86400 - 1800) < 1
    only200 = 3500 + np.arange(0, 25, 200 / 86400)
    assert abs(funnel_k1.coarsest_in_transit_cadence_days(only200, 5.83, 3501.0, 0.003) * 86400 - 200) < 1
