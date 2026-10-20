"""Survey layer (tesshunter.survey): config hashing, the stitched cache
round trip, batman injection, and a full offline job from a pre-populated
cache. No network. Time frame: plain BTJD.
"""

import json

import numpy as np
import lightkurve as lk
import pytest
from astropy import units as u
from astropy.time import Time

from tesshunter import survey


def test_ingest_key_is_stable_and_only_tracks_ingestion_fields():
    a = survey.get_config("survey_v1")
    b = survey.get_config("survey_v1", period_max=60.0, top_n=3)     # search fields only
    c = survey.get_config("survey_v1", qlp_flux="sap")                # ingestion field
    assert a.ingest_key() == b.ingest_key()
    assert a.ingest_key() != c.ingest_key()
    assert len(a.ingest_key()) == 10
    assert a.to_dict()["ingest_key"] == a.ingest_key()
    # int and float spellings of a numeric ingestion field hash identically
    assert survey.get_config("survey_v1", edge_trim_minutes=120).ingest_key() ==         survey.get_config("survey_v1", edge_trim_minutes=120.0).ingest_key()


def test_get_config_rejects_unknown_fields():
    with pytest.raises(ValueError):
        survey.get_config("survey_v1", not_a_field=1)


def _synthetic_stitched(period=3.3, t0=1000.7, depth=0.004, n_sectors=2, seed=3):
    rng = np.random.default_rng(seed)
    pieces = []
    for s in range(n_sectors):
        t = 1000.0 + s * 60.0 + np.arange(0, 27.0, 30 / 1440.0)
        pieces.append(t)
    t = np.concatenate(pieces)
    flux = 1.0 + rng.normal(0, 5e-4, t.size)
    if depth:
        phase = ((t - t0 + 0.5 * period) % period) - 0.5 * period
        flux[np.abs(phase) < 0.05] -= depth
    lc = lk.LightCurve(time=Time(t, format="btjd", scale="tdb"),
                       flux=flux * u.dimensionless_unscaled,
                       flux_err=np.full(t.size, 5e-4) * u.dimensionless_unscaled)
    lc.meta["TESSHUNTER_PROVENANCE"] = [{"unit": 1, "author": "QLP", "n_cadences": 1296, "cadence_s": 1800.0},
                                        {"unit": 3, "author": "QLP", "n_cadences": 1296, "cadence_s": 1800.0}]
    lc.meta["TESSHUNTER_UNITS"] = [1, 3]
    lc.meta["TESSHUNTER_INGEST"] = []
    return lc


def test_stitched_cache_round_trip(tmp_path):
    cfg = survey.get_config("survey_v1")
    lc = _synthetic_stitched()
    prov = {"products": lc.meta["TESSHUNTER_PROVENANCE"], "units_used": [1, 3], "units_all": [1, 2, 3],
            "fallback_events": [], "n_products_downloaded": 3, "ingest": [], "baseline_days": 87.0}
    path = survey.stitched_path(4242, cfg, tmp_path)
    survey.save_stitched(path, lc, prov)
    assert path.exists() and path.with_suffix(".json").exists()
    back, prov2 = survey.load_stitched(path)
    assert np.array_equal(back.time.value, lc.time.value)
    assert np.array_equal(back.flux.value, lc.flux.value)
    assert np.array_equal(back.flux_err.value, lc.flux_err.value)
    assert prov2["units_used"] == [1, 3]
    assert back.meta["TESSHUNTER_UNITS"] == [1, 3]
    assert len(back.meta["TESSHUNTER_PROVENANCE"]) == 2
    # get_stitched serves the cache without a download hook
    lc3, prov3, info = survey.get_stitched(4242, cfg, cache_dir=tmp_path, allow_download=False)
    assert info["cache_hit"] is True and len(lc3) == len(lc)
    with pytest.raises(survey.NoDataError):
        survey.get_stitched(999, cfg, cache_dir=tmp_path, allow_download=False)


def test_inject_transit_depth_duration_and_counts():
    lc = _synthetic_stitched(depth=0.0)
    period, t0, rp, b = 5.0, 1002.0, 0.05, 0.0
    a_rs = survey.a_over_rs(period, 1.0, 1.0)
    out, info = survey.inject_transit(lc, period=period, t0=t0, rp_rs=rp, b=b, a_rs=a_rs,
                                      u=(0.4, 0.2), exp_time_minutes=30.0)
    assert len(out) == len(lc)
    # central depth of a limb-darkened transit exceeds rp^2 (2500 ppm) but not by more than ~1.4x
    assert 2500 < info["depth_max_ppm"] < 3600
    assert info["depth_mean_in_transit_ppm"] < info["depth_max_ppm"]
    # T14 for a solar-density star at 5 d: a/R* ~ 12.4 -> ~0.135 d
    assert abs(info["t14_days"] - 0.135) < 0.02
    # transits inside the two 27-day windows starting 1000 and 1060 with t0=1002:
    # 6 + 5 full ones, plus the partial one whose ingress touches the end of window 2
    assert 11 <= info["n_transits_with_data"] <= 12
    assert info["n_cadences_in_transit"] > 0
    t = np.asarray(out.time.value)
    f = np.asarray(out.flux.value)
    assert f[np.abs(t - t0) < 0.02].mean() < 0.998


def test_limb_darkening_interpolates_and_clips():
    u1, u2 = survey.limb_darkening_for_teff(5750.0)
    assert 0.3 < u1 < 0.45 and 0.15 < u2 < 0.3
    assert survey.limb_darkening_for_teff(None) == survey.limb_darkening_for_teff(5500.0)
    assert survey.limb_darkening_for_teff(2000.0) == survey.limb_darkening_for_teff(3000.0)


def test_run_job_offline_from_cache_recovers_injection(tmp_path):
    """A full survey job on a cached synthetic star, injection included."""
    cfg = survey.get_config("survey_v1")
    lc = _synthetic_stitched(depth=0.0)
    prov = {"products": lc.meta["TESSHUNTER_PROVENANCE"], "units_used": [1, 3], "units_all": [1, 3],
            "fallback_events": [], "n_products_downloaded": 2, "ingest": [], "baseline_days": 87.0}
    survey.save_stitched(survey.stitched_path(777, cfg, tmp_path), lc, prov)
    job = {
        "job_id": "inj_test", "tic_id": 777, "config": "survey_v1",
        "overrides": {"period_min": 1.0, "period_max": 12.0, "max_planets": 1, "top_n": 3,
                      "grid_cap": 3000, "local_grid_cap": 1000, "time_budget_s": 300.0},
        "star": {"radius_rsun": 0.9, "mass_msun": 0.9, "teff_k": 5400.0},
        "injection": {"period": 4.2, "rp_rs": 0.07, "b": 0.2, "t0_frac": 0.3},
    }
    rec = survey.run_job(job, cache_dir=tmp_path, allow_download=False)
    assert rec["status"] == "ok", rec.get("error")
    assert rec["cache"]["cache_hit"] is True
    assert rec["injection_model"]["depth_max_ppm"] > 4000
    planets = rec["result"]["planets"]
    assert planets, "injected 4.2 d transit not recovered"
    assert abs(planets[0]["period_days"] / 4.2 - 1.0) < 0.01
    assert rec["result"]["n_sectors"] == 2
    json.dumps(rec)      # JSON-able


def test_run_job_reports_no_data_when_cache_missing_and_download_disabled(tmp_path):
    rec = survey.run_job({"job_id": "x", "tic_id": 5}, cache_dir=tmp_path, allow_download=False)
    assert rec["status"] == "no_data"
    assert rec["result"] is None


def test_split_chunks_and_plan_searches():
    """Three year-like chunks plus a stitch search for long periods; a single
    chunk gets one search over the whole curve."""
    t = np.concatenate([
        1000.0 + np.arange(0, 60.0, 1 / 48),
        1400.0 + np.arange(0, 80.0, 1 / 48),
        1900.0 + np.arange(0, 27.0, 1 / 48),
        2300.0 + np.arange(0, 5.0, 1 / 48),          # too short: dropped
    ])
    lc = lk.LightCurve(time=Time(t, format="btjd", scale="tdb"),
                       flux=np.ones(t.size) * u.dimensionless_unscaled,
                       flux_err=np.full(t.size, 1e-3) * u.dimensionless_unscaled)
    cfg = survey.get_config("survey_v1")
    masks = survey.split_chunks(t, cfg.chunk_gap_days)
    assert len(masks) == 4 and sum(m.sum() for m in masks) == t.size
    plan = survey.plan_searches(lc, cfg)
    labels = [p["label"] for p in plan]
    assert labels == ["chunk0", "chunk1", "chunk2", "stitch"]
    assert plan[0]["period_max"] == pytest.approx(30.0, rel=0.05)          # half the 60-d span
    assert plan[1]["period_max"] == pytest.approx(40.0, rel=0.05)
    assert plan[2]["period_max"] == pytest.approx(13.5, rel=0.05)
    assert plan[3]["period_min"] == cfg.long_period_min and plan[3]["period_max"] == cfg.period_max
    assert plan[3]["mask"].all()
    assert all(p["budget_s"] >= 60.0 for p in plan)
    assert sum(p["budget_s"] for p in plan) >= cfg.time_budget_s
    single = survey.plan_searches(lc[masks[1]], cfg)
    assert [p["label"] for p in single] == ["chunk0"] and single[0]["mask"].all()
    flat = survey.plan_searches(lc, survey.get_config("survey_v1", search_mode="stitched"))
    assert [p["label"] for p in flat] == ["stitch"] and flat[0]["period_min"] == cfg.period_min


def test_merge_candidates_dedupes_by_period_and_caps():
    searches = [
        {"label": "chunk0", "planets": [{"planet_num": 1, "period_days": 3.000, "snr": 20.0},
                                        {"planet_num": 2, "period_days": 7.5, "snr": 8.0}]},
        {"label": "chunk1", "planets": [{"planet_num": 1, "period_days": 3.004, "snr": 25.0}]},
        {"label": "stitch", "planets": [{"planet_num": 1, "period_days": 40.0, "snr": 12.0},
                                        {"planet_num": 2, "period_days": 7.52, "snr": 9.0}]},
    ]
    merged = survey.merge_candidates(searches, max_total=3)
    assert [round(m["period_days"], 3) for m in merged] == [3.004, 40.0, 7.52]
    assert [m["search"] for m in merged] == ["chunk1", "stitch", "stitch"]
    assert [m["planet_num"] for m in merged] == [1, 2, 3]
    assert merged[0]["planet_num_search"] == 1
    assert len(survey.merge_candidates(searches, max_total=2)) == 2


def test_run_job_records_stitch_confirmation(tmp_path):
    """Chunk candidates get stitch_* fields from the whole-curve re-measurement."""
    cfg = survey.get_config("survey_v1")
    lc = _synthetic_stitched(depth=0.0, n_sectors=3)          # sectors 60 d apart: 3 chunks
    prov = {"products": lc.meta["TESSHUNTER_PROVENANCE"], "units_used": [1, 3, 5], "units_all": [1, 3, 5],
            "fallback_events": [], "n_products_downloaded": 3, "ingest": [], "baseline_days": 147.0}
    survey.save_stitched(survey.stitched_path(778, cfg, tmp_path), lc, prov)
    job = {
        "job_id": "inj_conf", "tic_id": 778, "config": "survey_v1",
        "overrides": {"period_min": 1.0, "period_max": 12.0, "max_planets": 1, "top_n": 3,
                      "grid_cap": 4000, "local_grid_cap": 800, "time_budget_s": 300.0,
                      "chunk_gap_days": 20.0},
        "star": {"radius_rsun": 0.9, "mass_msun": 0.9, "teff_k": 5400.0},
        "injection": {"period": 3.7, "rp_rs": 0.08, "b": 0.1, "t0_frac": 0.4},
    }
    rec = survey.run_job(job, cache_dir=tmp_path, allow_download=False)
    assert rec["status"] == "ok", rec.get("error")
    labels = [s["label"] for s in rec["searches"]]
    assert labels[-1] == "stitch" and len(labels) >= 3
    planets = rec["result"]["planets"]
    hits = [p for p in planets if abs(p["period_days"] / 3.7 - 1.0) < 0.01]
    assert hits, planets
    top = hits[0]
    assert "stitch_snr" in top and top["stitch_snr"] > 5.0
    assert top["stitch_epoch_consistent"] is True
    assert abs(top["stitch_period_days"] / 3.7 - 1.0) < 0.01
    assert top["stitch_n_chunks"] == 3
    assert rec["stitch_confirmation"]["n_confirmed"] >= 1
