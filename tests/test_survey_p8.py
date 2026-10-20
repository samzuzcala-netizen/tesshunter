"""Prompt 8: the native-cadence search input, the presets, and the rule-set options."""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from tesshunter import audit_rules as R
from tesshunter import event_vet, preprocessing, secondary, star_vet, survey, survey_p8

#: The prompt-4 stitched-cache key of ``survey_v1``; every P4 cache file is named by it.
SURVEY_V1_INGEST_KEY = "50c453a40c"


# ── presets and keys ─────────────────────────────────────────────────────────
def test_survey_v1_ingest_key_unchanged_by_p8_fields():
    assert survey.get_config("survey_v1").ingest_key() == SURVEY_V1_INGEST_KEY


def test_p8_presets_exist_and_name_their_ingestion():
    p8 = survey.get_config("survey_p8")
    assert p8.source == "audit_lc" and p8.preprocess == "audit_prep" and p8.sector_min == 56
    assert p8.bin_minutes is None and abs(p8.target_cadence_minutes - 200.0 / 60.0) < 1e-12
    assert p8.period_min == 0.5 and p8.period_max == 30.0
    assert p8.ingest_key() != SURVEY_V1_INGEST_KEY
    assert survey.get_config("survey_p8_600s").ingest_key() not in (p8.ingest_key(), SURVEY_V1_INGEST_KEY)
    assert p8.to_dict()["ingest_key"] == p8.ingest_key()


def test_p8_duration_floor_never_arms_gate_7():
    # gate 7 arms when duration_min < 2 binned cadences (prompt 2); 0.02 d is 8.6 cadences at 200 s
    p8 = survey.get_config("survey_p8")
    assert p8.duration_min >= 2 * 200.0 / 86400.0 * 4


# ── no-op binning ─────────────────────────────────────────────────────────────
def _lc(n=500, cadence_days=200.0 / 86400.0, seed=0):
    import lightkurve as lk
    from astropy import units as u
    from astropy.time import Time
    rng = np.random.default_rng(seed)
    t = 3000.0 + np.arange(n) * cadence_days
    f = 1.0 + 1e-3 * rng.standard_normal(n)
    return lk.LightCurve(time=Time(t, format="btjd", scale="tdb"), flux=f * u.dimensionless_unscaled,
                         flux_err=np.full(n, 1e-3) * u.dimensionless_unscaled)


def test_bin_lightcurve_none_returns_input_unchanged():
    lc = _lc()
    out = preprocessing.bin_lightcurve(lc, bin_minutes=None)
    assert out is lc
    out2 = preprocessing.bin_lightcurve(lc, bin_minutes=0)
    assert len(out2) == len(lc)


def test_bin_lightcurve_positive_still_bins():
    lc = _lc()
    out = preprocessing.bin_lightcurve(lc, bin_minutes=30.0)
    assert len(out) < len(lc)


# ── products, cadence rule, injection ────────────────────────────────────────
def _product(sector, author, cadence_s, n=2000, seed=0, t0=3000.0):
    rng = np.random.default_rng(seed + sector)
    t = t0 + np.arange(n) * cadence_s / 86400.0
    return {"sector": sector, "author": author, "cadence_s": float(cadence_s), "n": n, "file": f"s{sector}.npz",
            "time": t, "flux": 1000.0 + rng.standard_normal(n), "flux_err": np.ones(n),
            "sap_flux": 1200.0 + rng.standard_normal(n), "sap_flux_err": np.ones(n),
            "sap_bkg": 50.0 + rng.standard_normal(n), "quality": np.zeros(n, dtype=np.int64)}


def test_harmonise_cadence_bins_finer_and_drops_coarser():
    prods = [_product(56, "SPOC", 120.0), _product(57, "QLP", 200.0), _product(40, "QLP", 600.0)]
    kept, notes = survey_p8.harmonise_cadence(prods, 200.0 / 60.0)
    assert [int(p["sector"]) for p in kept] == [56, 57]
    assert abs(kept[0]["cadence_s"] - 200.0) < 1e-9 and kept[0]["binned_from_s"] == 120.0
    assert kept[0]["n"] < prods[0]["n"]
    assert any("dropped" in n for n in notes) and any("binned" in n for n in notes)


def test_bin_product_keeps_every_array_and_ors_quality():
    p = _product(56, "SPOC", 120.0, n=600)
    p["quality"][7] = 32
    q = survey_p8.bin_product(p, 200.0 / 60.0)
    for k in survey_p8.PRODUCT_ARRAYS:
        assert len(q[k]) == len(q["time"])
    assert (q["quality"] & 32).any()
    assert np.all(np.isfinite(q["flux_err"])) and np.all(q["flux_err"] > 0)


def test_inject_products_touches_both_flux_columns_identically():
    prods = [_product(56, "QLP", 200.0, n=4000)]
    out, info = survey_p8.inject_products(prods, period=1.3, t0=3000.5, rp_rs=0.1, b=0.1, a_rs=8.0, u=(0.2, 0.4))
    m1 = out[0]["flux"] / prods[0]["flux"]
    m2 = out[0]["sap_flux"] / prods[0]["sap_flux"]
    assert np.allclose(m1, m2)
    assert m1.min() < 0.995 and info["n_transits_with_data"] >= 5
    assert info["injected_into"] == ["flux", "sap_flux"]
    assert abs(prods[0]["flux"].mean() - 1000.0) < 1.0          # the input was not modified in place


def test_harmonise_then_inject_matches_inject_then_harmonise_in_depth():
    p = _product(56, "SPOC", 120.0, n=6000)
    a, _ = survey_p8.inject_products(survey_p8.harmonise_cadence([p], 200.0 / 60.0)[0],
                                     period=2.0, t0=3001.0, rp_rs=0.1, b=0.0, a_rs=10.0, u=(0.2, 0.4))
    b, _ = survey_p8.inject_products([p], period=2.0, t0=3001.0, rp_rs=0.1, b=0.0, a_rs=10.0, u=(0.2, 0.4))
    b = survey_p8.harmonise_cadence(b, 200.0 / 60.0)[0]
    da = 1 - a[0]["flux"].min() / np.median(a[0]["flux"])
    db = 1 - b[0]["flux"].min() / np.median(b[0]["flux"])
    assert abs(da - db) < 0.15 * da


# ── the prepared series ──────────────────────────────────────────────────────
def test_prepare_search_input_deep_clips_and_counts():
    prods = [_product(56, "QLP", 200.0, n=5000), _product(57, "QLP", 200.0, n=5000, t0=3040.0)]
    prods[0]["flux"][2000:2010] -= 500.0       # a 50% dip, 10 cadences: deeper than 10 MAD
    prep = survey_p8.prepare_search_input(prods, 0.75)
    assert prep["counters"]["n_deep_clipped"] >= 8
    assert prep["counters"]["n_products_dropped"] == 0
    assert len(prep["time"]) == len(prep["flux"]) == len(prep["sector"])
    assert set(np.unique(prep["sector"])) == {56, 57}
    assert abs(np.median(prep["flux"]) - 1.0) < 1e-3


def test_rotation_proxy_finds_an_injected_sinusoid():
    prods = [_product(56, "QLP", 200.0, n=8000)]
    t = prods[0]["time"]
    prods[0]["flux"] *= 1.0 + 0.01 * np.sin(2 * np.pi * t / 2.5)
    rot = survey_p8.rotation_proxy(prods)
    assert rot["available"]
    assert abs(rot["peak_period_days"] - 2.5) < 0.1
    assert 7.0 < rot["semi_amplitude_ppt"] < 13.0


def test_load_audit_products_applies_sector_cut_and_author_preference(tmp_path):
    tdir = tmp_path / "tic1"
    tdir.mkdir()
    prods = [_product(40, "QLP", 600.0), _product(56, "QLP", 200.0), _product(56, "TESS-SPOC", 200.0),
             _product(57, "SPOC", 120.0)]
    index = {"tic_id": 1, "products": []}
    for i, p in enumerate(prods):
        name = f"p{i}.npz"
        np.savez(tdir / name, **{k: p[k] for k in survey_p8.PRODUCT_ARRAYS})
        index["products"].append({"file": name, "sector": p["sector"], "author": p["author"], "cadence_s": p["cadence_s"]})
    (tdir / "index.json").write_text(json.dumps(index))
    got = survey_p8.load_audit_products(1, root=tmp_path, sector_min=56)
    assert [(p["sector"], p["author"]) for p in got] == [(56, "TESS-SPOC"), (57, "SPOC")]
    with pytest.raises(survey_p8.NoStoreDataError):
        survey_p8.load_audit_products(2, root=tmp_path)
    with pytest.raises(survey_p8.NoStoreDataError):
        survey_p8.load_audit_products(1, root=tmp_path, sector_min=60)


def test_build_prepared_records_provenance(tmp_path):
    prods = [_product(56, "QLP", 200.0, n=3000), _product(59, "QLP", 200.0, n=3000, t0=3100.0)]
    cfg = survey.get_config("survey_p8")
    lc, prov = survey_p8.build_prepared(7, cfg, prods, None, ["note"])
    assert prov["units_used"] == [56, 59] and prov["source"] == "audit_lc"
    assert prov["ingest_key"] == cfg.ingest_key()
    assert lc.meta["TESSHUNTER_UNITS"] == [56, 59]
    assert prov["rotation_proxy"]["available"]
    assert len(lc) == prov["n_cadences"] > 5000


# ── rule-set options ─────────────────────────────────────────────────────────
def test_ruleset_versions_with_p8_fields():
    assert R.LEGACY_RULES.version == "p6.2"
    assert R.DEFAULT_RULES.version == "p7.0"
    assert R.DEFAULT_RULES.with_options(secondary_gate="quiet_bound").version in ("p8.0", "p8.0-partial")
    assert R.LEGACY_RULES.with_options(beta_max=3.0).version == "p8.0-partial"
    assert R.DEFAULT_RULES.with_options(secondary_scan=False).version == "p7.0-partial"
    assert "p8.0" in R.KNOWN_RULES_VERSIONS


def test_thresholds_report_p8_fields():
    th = R.thresholds(R.DEFAULT_RULES.with_options(beta_max=2.0, depth_consistency_errors="white",
                                                  depth_consistency_p_min=1e-4, secondary_gate="quiet_zero",
                                                  secondary_quiet_max_dips=3))
    assert th["events"]["beta_inflation"]["beta_max"] == 2.0
    assert th["stageA"]["p_const_used"] == "white" and th["stageA"]["min_p_const"] == 1e-4
    assert th["secondary"]["gate_mode"] == "quiet_zero" and th["secondary"]["quiet_max_dips"] == 3


@pytest.mark.parametrize("mode,n_dips,depth,err,bound,var,expect", [
    ("bound", 20, 1.0, 0.1, 1e-3, True, "FAIL"),          # p7.0: any scan, over the bound
    ("bound", 2, 0.2, 0.1, 1e-3, False, "PASS"),          # 2 sigma over the bound: not fired
    ("quiet_bound", 20, 1.0, 0.1, 1e-3, True, "PASS"),    # noisy scan: the quiet variant does not fire
    ("quiet_bound", 2, 1.0, 0.1, 1e-3, False, "FAIL"),    # quiet scan, over the bound: fired
    ("quiet_bound", 3, 1.0, 0.1, 1e-3, False, "PASS"),    # just not quiet (N=2)
    ("quiet_zero", 2, 0.35, 0.1, 1e-3, False, "FAIL"),    # 3.5 sigma over zero on a quiet scan
    ("quiet_zero", 2, 0.29, 0.1, 1e-3, False, "PASS"),    # 2.9 sigma: just not fired
    ("quiet_bound_hold", 20, 0.1, 0.1, 1e-3, True, "HOLD"),   # variability demotes to HOLD
    ("quiet_bound_hold", 2, 1.0, 0.1, 1e-3, False, "FAIL"),
    ("quiet_bound_hold", 2, 0.1, 0.1, 1e-3, False, "PASS"),
])
def test_apply_gate_modes(mode, n_dips, depth, err, bound, var, expect):
    assert secondary.apply_gate(depth, err, bound, n_dips, var, mode, 2)["gate"] == expect


def test_apply_gate_quiet_max_dips_moves_the_threshold():
    assert secondary.apply_gate(1.0, 0.1, 1e-3, 4, False, "quiet_zero", 5)["gate"] == "FAIL"
    assert secondary.apply_gate(1.0, 0.1, 1e-3, 4, False, "quiet_zero", 3)["gate"] == "PASS"


def test_apply_gate_unknown_mode_raises():
    with pytest.raises(ValueError):
        secondary.apply_gate(1.0, 0.1, 1e-3, 2, False, "nope", 2)


def _events(depths, errs, sectors):
    return [{"n": i, "observed": True, "excluded": False, "det_depth_ppt": d, "det_depth_err_ppt": e,
             "sap_depth_ppt": d, "sap_depth_err_ppt": e, "sector": s} for i, (d, e, s) in enumerate(zip(depths, errs, sectors))]


def test_kept_event_stats_gate_errors_white_vs_inflated():
    ev = _events([1.0, 3.0, 1.0, 3.0], [0.2, 0.2, 0.2, 0.2], [1, 1, 2, 2])
    beta = {1: 5.0, 2: 5.0}
    inf = event_vet.kept_event_stats(ev, "det", beta, gate_errors="inflated")
    wh = event_vet.kept_event_stats(ev, "det", beta, gate_errors="white")
    assert inf["p_const"] == inf["p_const_inflated"] and wh["p_const"] == wh["p_const_white"]
    assert wh["p_const"] < 1e-3 < inf["p_const"]
    assert wh["p_const_gate_errors"] == "white" and "p_const_gate_errors" not in inf


def test_sector_beta_cap_is_honoured():
    rng = np.random.default_rng(3)
    n = 4000
    t = np.arange(n) * 200.0 / 86400.0
    red = np.cumsum(rng.standard_normal(n)) * 5e-4          # strongly correlated noise
    f = 1.0 + red - red.mean()
    sec = np.ones(n, dtype=int)
    in_tr = np.zeros(n, dtype=bool)
    b5 = event_vet.sector_beta(t, f, sec, in_tr, 0.1, {1: 200.0}, beta_max=5.0)
    b2 = event_vet.sector_beta(t, f, sec, in_tr, 0.1, {1: 200.0}, beta_max=2.0)
    assert b5[1] > 2.0 and b2[1] == 2.0


def test_stagea_criteria_p_min():
    dk = {"n": 5, "snr": 10.0, "top_event_share_of_snr2": 0.3, "snr_without_top_event": 8.0,
          "weighted_mean_depth_ppt": 1.0, "p_const": 5e-4, "err_ppt": 0.1}
    assert not event_vet.stagea_criteria(dk, 1.0)["criteria"]["depths_consistent_p_ge_1e-3"]
    assert event_vet.stagea_criteria(dk, 1.0, p_min=1e-4)["criteria"]["depths_consistent_p_ge_1e-3"]


@pytest.mark.parametrize("threshold", [1e-3, 1e-4, 1e-5])
def test_depth_consistency_passes_at_threshold_and_fails_just_below(threshold):
    stats = {"n": 5, "snr": 10.0, "top_event_share_of_snr2": 0.3, "snr_without_top_event": 8.0,
             "weighted_mean_depth_ppt": 1.0, "p_const": threshold, "err_ppt": 0.1}
    assert event_vet.stagea_criteria(stats, 1.0, p_min=threshold)["all_passed"]
    stats["p_const"] = np.nextafter(threshold, 0.0)
    result = event_vet.stagea_criteria(stats, 1.0, p_min=threshold)
    assert not result["all_passed"] and result["n_criteria_passed"] == 5


def test_bound_secondary_gate_is_strictly_above_three_sigma():
    # These values are exactly representable, so the inclusive/exclusive boundary
    # is checked without a decimal subtraction rounding onto the wrong side.
    assert secondary.apply_gate(0.875, 0.125, 0.5, 20, True, "bound", 2)["gate"] == "PASS"
    assert secondary.apply_gate(np.nextafter(0.875, np.inf), 0.125, 0.5, 20, True, "bound", 2)["gate"] == "FAIL"


@pytest.mark.parametrize("cap", [2.0, 3.0, 5.0])
def test_beta_caps_clip_correlated_noise_and_preserve_white_noise(cap):
    rng = np.random.default_rng(3)
    t = np.arange(4000) * 200 / 86400
    sector = np.ones(len(t), dtype=int)
    masked = np.zeros(len(t), dtype=bool)
    red = 1 + np.cumsum(rng.standard_normal(len(t))) * 5e-4
    white = 1 + rng.standard_normal(len(t)) * 5e-4

    def beta(flux, maximum):
        return event_vet.sector_beta(t, flux, sector, masked, 0.2, {1: 200.0}, beta_max=maximum)[1]

    assert beta(red, 1e6) > 5 and beta(red, cap) == cap
    assert beta(white, 1e6) < 2 and beta(white, cap) == beta(white, 1e6)


def test_phase_independent_exact_record_replays_from_its_fields():
    rng = np.random.default_rng(0)
    t = 3000.0 + np.arange(8000) * 200.0 / 86400.0
    sectors = [{"sector": 56, "author": "QLP", "cadence_s": 200.0, "time": t, "flux": 1.0 + 1e-3 * rng.standard_normal(t.size)}]
    t14 = 1.2345678
    rounded = star_vet.phase_independent_test(sectors, 3.0, 2.0, t14)
    exact = star_vet.phase_independent_test(sectors, 3.0, 2.0, t14, exact=True)
    assert rounded["t14_hours"] == round(t14, 3) and exact["t14_hours"] == t14
    assert exact["window_days"] == t14 / 24.0
    assert rounded["sectors"][0]["excludes_period"] == exact["sectors"][0]["excludes_period"]


# ── the primary-shoulder split of the secondary scan (prompt 8) ─────────────
def test_split_primary_shoulders_keeps_only_genuine_secondaries():
    prim = {"phase": 0.0008, "depth_ppt": 7.9, "sigma": 146.0}
    dips = [prim, {"phase": 0.01, "depth_ppt": 7.0, "sigma": 131.0}, {"phase": 0.99, "depth_ppt": 7.0, "sigma": 130.0},
            {"phase": 0.605, "depth_ppt": 2.5, "sigma": 52.0}, {"phase": 0.03, "depth_ppt": 4.1, "sigma": 76.0}]
    secs, shoulders = secondary.split_primary_shoulders(dips, prim, width_days=0.04, period=1.0)
    assert [d["phase"] for d in secs] == [0.605]
    assert sorted(d["phase"] for d in shoulders) == [0.01, 0.03, 0.99]
    # a wide box on a short period widens the exclusion
    assert abs(secondary.primary_exclusion_phase(0.1, 0.5) - 0.3) < 1e-12
    assert secondary.primary_exclusion_phase(0.02, 10.0) == 0.03
    secs2, sh2 = secondary.split_primary_shoulders(dips, None, 0.04, 1.0)
    assert len(secs2) == 5 and sh2 == []


def test_secondary_scan_on_an_injected_planet_passes_every_gate_mode():
    from tesshunter.survey import transit_model
    rng = np.random.default_rng(11)
    n = 60000
    t = 3000.0 + np.arange(n) * 200.0 / 86400.0
    m = transit_model(t, period=1.05, t0=3000.3, rp_rs=0.09, b=0.1, a_rs=10.0, u=(0.2, 0.4), exp_time_days=200 / 86400)
    f = m * (1.0 + 3e-3 * rng.standard_normal(n))
    sec = secondary.secondary_scan(t, f, 1.05, 3000.3, 0.05, 0.3, 0.3, 3300.0, t, f)
    assert sec["primary"] is not None and sec["primary"]["sigma"] > 50
    assert sec["gate"] == "PASS", sec.get("verdict")
    assert all(g == "PASS" for g in sec["gate_by_mode"].values()), sec["gate_by_mode"]
    assert not sec["variability_flag"]


def test_secondary_scan_still_fails_a_real_secondary():
    from tesshunter.survey import transit_model
    rng = np.random.default_rng(12)
    n = 60000
    t = 3000.0 + np.arange(n) * 200.0 / 86400.0
    m = transit_model(t, period=2.0, t0=3000.3, rp_rs=0.1, b=0.1, a_rs=10.0, u=(0.2, 0.4), exp_time_days=200 / 86400)
    m2 = transit_model(t, period=2.0, t0=3000.3 + 1.21, rp_rs=0.1, b=0.1, a_rs=10.0, u=(0.2, 0.4), exp_time_days=200 / 86400)
    f = m * (1.0 - 0.5 * (1.0 - m2)) * (1.0 + 3e-3 * rng.standard_normal(n))
    sec = secondary.secondary_scan(t, f, 2.0, 3000.3, 0.06, 0.3, 0.3, 3300.0, t, f)
    assert sec["gate"] == "FAIL"
    assert abs(sec["secondaries"][0]["phase"] - 0.605) < 0.02
