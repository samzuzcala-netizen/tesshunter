"""Prompt 3 part D: the packet builder and the CTOI field file, offline."""

import json

import numpy as np
import lightkurve as lk
from astropy.time import Time
from astropy import units as u

from tesshunter import packet, stellar, survey, transit_fit as tf
from tesshunter.packet import CTOI_FORM_FIELDS


def _result_with_fit():
    P, t0, rp, a, b = 3.3, 1001.2, 0.08, 10.0, 0.3
    rng = np.random.default_rng(2)
    t = 1000.0 + np.arange(0.0, 54.0, 2.0 / 1440.0)
    t = t[~((t - 1000.0 >= 26.0) & (t - 1000.0 < 28.5))]
    f = survey.transit_model(t, period=P, t0=t0, rp_rs=rp, b=b, a_rs=a, u=(0.35, 0.25),
                             exp_time_days=2.0 / 1440.0) + rng.normal(0, 8e-4, t.size)
    e = np.full(t.size, 8e-4)
    star = stellar.StellarParams(tic_id=999, ra=10.0, dec=-20.0, tmag=9.5, teff=5500.0, logg=4.5,
                                 radius=1.0, radius_err=0.05, mass=1.0, mass_err=0.08, source="user")
    t14 = tf.transit_duration_t14(P, a, b, rp)
    fit = tf.fit_transit(t, f, e, period=P, t0=t0, duration=t14, depth_ppt=6.5,
                         exp_time_days=2.0 / 1440.0, stellar=star)
    assert fit.success
    lc = lk.LightCurve(time=Time(t, format="btjd", scale="tdb"), flux=f * u.dimensionless_unscaled,
                       flux_err=e * u.dimensionless_unscaled)
    cand = {"planet_num": 1, "period_days": fit.period, "epoch_btjd": fit.t0, "duration_days": fit.duration_days,
            "depth_ppt": fit.depth_ppt, "depth_ppt_bls": 6.0, "snr": 45.0, "n_transits_observed": 15,
            "harmonic_label": "P", "verdict": "promising planet candidate", "fit": fit.to_dict()}
    vet = {"planet_num": 1, "verdict": "promising planet candidate", "flags_hard": [], "flags_high": [],
           "flags_medium": [], "notes": [], "result": {"secondary_depth_ppt": 0.01, "secondary_planet_bound_ppt": 0.2,
                                                        "odd_even_delta_sigma": 0.5, "v_shape_flag": "none"}}
    res = {"target": 999, "mission": "TESS", "planets": [cand], "vetting": [vet],
           "provenance": {"units_used": [1, 2], "products": [{"author": "SPOC", "unit": 1}]},
           "n_cadences_raw": t.size, "n_cadences_clean": t.size, "stellar": star.to_dict(),
           "crossmatch": {"summary": "CLEAN (test)", "catalog_versions": "toi=test"}}
    return res, lc, star


def test_build_packet_writes_every_file_and_a_valid_ctoi_form(tmp_path):
    res, lc, star = _result_with_fit()
    fpp = {"available": True, "fpp": 0.012, "nfpp": 0.001, "aperture_source": "spoc", "note": "stub"}
    summary = packet.build_packet(result=res, planet_num=1, lc_clean=lc, stellar=star, fpp=fpp,
                                  fetch_neighbours=False, out_dir=tmp_path / "pkt", label="TEST 999",
                                  tag="20260902_test_tesshunter_001")
    files = summary["files"]
    for key in ("packet_md", "summary_png", "ctoi_fields_json", "fit_json", "fpp_json", "vetting_json"):
        assert files[key] and (tmp_path / "pkt" / files[key].split("pkt")[-1].lstrip("\\/")).exists(), key
    fields = json.loads((tmp_path / "pkt" / "ctoi_fields.json").read_text(encoding="utf-8"))
    form = fields["form_fields"]
    assert list(form.keys()) == CTOI_FORM_FIELDS
    assert form["target"] == "TIC 999" and form["disposition"] == "PC"
    for k in ("period_days", "epoch_bjd", "depth_ppm", "duration_hours"):
        assert form[k] is not None and form[k] > 0, k
    assert form["epoch_bjd"] > 2457000.0
    assert form["tag"] == "20260902_test_tesshunter_001"
    assert "candidate" in form["notes"].lower()
    for bad in ("discovered", "planet found", "confirmed"):
        assert bad not in form["notes"].lower()
    md = (tmp_path / "pkt" / "packet.md").read_text(encoding="utf-8")
    assert "Completeness at this SNR" in md and "FPP" in md and "summary.png" in md
    assert summary["completeness"]["available"] and 0.0 <= summary["completeness"]["logistic_recovery"] <= 1.0
    assert not summary["fpp_blocks_packet"]


def test_completeness_curve_is_monotonic_and_anchored():
    lo = packet.completeness_at_snr(7.0)
    mid = packet.completeness_at_snr(26.5)
    hi = packet.completeness_at_snr(100.0)
    assert lo["available"] and hi["available"]
    assert lo["logistic_recovery"] < mid["logistic_recovery"] < hi["logistic_recovery"]
    assert abs(mid["logistic_recovery"] - 0.5) < 0.02
    assert not packet.completeness_at_snr(None)["available"]


def test_fpp_above_half_blocks_the_packet(tmp_path):
    res, lc, star = _result_with_fit()
    summary = packet.build_packet(result=res, planet_num=1, lc_clean=lc, stellar=star,
                                  fpp={"available": True, "fpp": 0.8, "nfpp": 0.3},
                                  fetch_neighbours=False, out_dir=tmp_path / "pkt2")
    assert summary["fpp_blocks_packet"]
    md = (tmp_path / "pkt2" / "packet.md").read_text(encoding="utf-8")
    assert "does not proceed" in md
