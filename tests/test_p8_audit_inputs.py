"""The P8 audit must examine the same sectors and cadence as the measured search."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from tesshunter import audit_prep, survey, survey_p8
from tests.test_survey_p8 import _product


def test_native_bin_lc_preserves_cadences():
    t = np.arange(80) * 200.0 / 86400
    f, e = np.ones(80), np.full(80, 0.002)
    actual = audit_prep.bin_lc(t, f, e, None)
    for got, expected in zip(actual, (t, f, e)):
        np.testing.assert_array_equal(got, expected)


def test_audit_selection_matches_search_and_legacy_is_unchanged(monkeypatch):
    import audit_p5 as A
    prods = [_product(27, "QLP", 600), _product(56, "SPOC", 120),
             _product(56, "QLP", 200), _product(57, "QLP", 200), _product(58, "QLP", 600)]
    cfg = survey.get_config("survey_p8")
    monkeypatch.setattr(A, "INPUT_CONFIG", cfg)
    selected = A.choose_per_sector(prods)
    expected, _ = survey_p8.harmonise_cadence([prods[1], prods[3], prods[4]], cfg.target_cadence_minutes)
    assert [p["sector"] for p in selected] == [56, 57]
    for got, want in zip(selected, expected):
        for name in survey_p8.PRODUCT_ARRAYS:
            np.testing.assert_array_equal(got[name], want[name])
    A.set_input_config()
    assert [p["sector"] for p in A.choose_per_sector(prods)] == [27, 56, 57, 58]
    assert A.choose_per_sector(prods)[1]["cadence_s"] == 120


def test_prepare_uses_native_input_and_rejects_old_context(tmp_path, monkeypatch):
    import audit_p5 as A
    monkeypatch.setattr(A, "INPUT_CONFIG", None)
    monkeypatch.setattr(A, "OUT", tmp_path)
    for name in ("prep", "tls"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(A, "RULES", A.R.LEGACY_RULES)
    monkeypatch.setattr(A, "RULES_VERSION", "p6.2")
    monkeypatch.setattr(A, "survivor_row", lambda *_: {"depth_ppt": "3"})
    monkeypatch.setattr(A, "stellar_for", lambda *_: {"R_star": 0.3, "M_star": 0.3, "expected_t14_hours_b0": 1.0})
    monkeypatch.setattr(A, "load_products", lambda *_: [_product(55, "QLP", 600, n=4000),
                                                       _product(56, "QLP", 200, n=6000, t0=3100)])
    old = A.prepare_step(999, 2.0)
    assert old["bin_minutes"] == 30
    A.set_input_config(survey.get_config("survey_p8"))
    new = A.prepare_step(999, 2.0)
    assert new["bin_minutes"] is None
    assert [p["sector"] for p in new["products"]] == [56]
    assert new["n_binned"] > 5500
    saved = json.loads((tmp_path / "prep" / "tic999_P2.0000.json").read_text())
    assert A.cache_matches(saved)
    assert not A.cache_matches(dict(saved, input_config=None))
    with np.load(tmp_path / "tls" / "tic999_P2.0000_lc.npz") as z:
        assert np.isclose(np.median(np.diff(z["time"])), 200 / 86400)


def test_audit_injection_matches_completed_search_order(monkeypatch):
    import audit_p5 as A
    import p8_completeness as C
    prods = [_product(56, "SPOC", 120, n=6000)]
    monkeypatch.setattr(A, "INPUT_CONFIG", survey.get_config("survey_p8"))
    loader = lambda *_: prods
    monkeypatch.setattr(A, "load_products", loader)
    monkeypatch.setattr(A, "_load_products_uninjected", loader, raising=False)
    model = dict(period=1.3, t0=3000.5, rp_rs=0.09, b=0.2, a_rs=9.0, u=(0.2, 0.4))
    C.install_injection({"inj_period": model["period"], "inj_t0": model["t0"], "inj_rp_rs": model["rp_rs"],
                         "inj_b": model["b"], "inj_a_rs": model["a_rs"], "inj_u1": 0.2, "inj_u2": 0.4})
    got = A.choose_per_sector(A.load_products(999))
    harmonised, _ = survey_p8.harmonise_cadence(prods, 200 / 60)
    expected, _ = survey_p8.inject_products(harmonised, **model)
    for name in survey_p8.PRODUCT_ARRAYS:
        np.testing.assert_array_equal(got[0][name], expected[0][name])


@pytest.mark.parametrize("change", [{"decision": "ERROR"}, {"rules_version": "p6.2"}, {"input_config": None}])
def test_completeness_refuses_unsettled_or_stale_records(tmp_path, change):
    import audit_p5 as A
    import p8_completeness as C
    path = tmp_path / "record.json"
    valid = {"rules_version": "p7.0", "input_config": A.input_config_for(survey.get_config("survey_p8")), "decision": "PASS"}
    path.write_text(json.dumps(valid), encoding="utf-8")
    assert C.require_settled_record(path, "p7.0", "decision", ("PASS", "FAIL")) == valid
    path.write_text(json.dumps(dict(valid, **change)), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete/stale"):
        C.require_settled_record(path, "p7.0", "decision", ("PASS", "FAIL"))


def test_rule_selection_requires_the_complete_instrument():
    from p8_decisions import validate_measurement_set
    records = [{"key": "one", "status": "OK"}, {"key": "two", "status": "OK"}]
    validate_measurement_set("adv", records, {"one", "two"})
    with pytest.raises(ValueError, match="incomplete"):
        validate_measurement_set("adv", records[:1], {"one", "two"})
    with pytest.raises(ValueError, match="incomplete"):
        validate_measurement_set("adv", [records[0], {"key": "two", "status": "ERROR"}], {"one", "two"})


def test_injection_instrument_requires_both_settled_gates(tmp_path, monkeypatch):
    import audit_p5 as A
    import p8_decisions as D
    monkeypatch.setattr(D, "INJ_ROOT", tmp_path)
    job = {"job_id": "j1", "tic_id": 999, "period_days": 2.0, "depth_ppt": 3.0, "teff_k": 3300}
    root = tmp_path / "j1"
    key = "tic999_P2.0000"
    for name in ("stageA", "secondary", "prep"):
        (root / name).mkdir(parents=True)
    context = {"rules_version": "p7.0", "input_config": A.input_config_for(survey.get_config("survey_p8"))}
    eph = {"period": 2.0, "t0": 3000.0, "duration": 0.06}
    stagea = dict(context, decision="PASS", chosen_ephemeris="survey", per_ephemeris={"survey": {"ephemeris": eph}})
    (root / "stageA" / f"{key}.json").write_text(json.dumps(stagea))
    with pytest.raises(ValueError, match="incomplete/stale gate"):
        D.injection_job(job)
    secondary = root / "secondary" / f"{key}.json"
    secondary.write_text(json.dumps(dict(context, gate="ERROR")))
    with pytest.raises(ValueError, match="incomplete/stale gate"):
        D.injection_job(job)
    secondary.write_text(json.dumps(dict(context, gate="PASS", secondary={"gate": "PASS"})))
    (root / "prep" / f"{key}.json").write_text(json.dumps({"wotan": {"window_days": 0.75}, "R_star": 0.3, "M_star": 0.3}))
    actual = D.injection_job(job)
    assert actual["eph"] == eph and actual["secondary_from"] == {"gate": "PASS"}
    assert actual["stageA_p7"] == "PASS" and actual["job"] == job


def test_native_fit_refuses_a_stale_cache(tmp_path, monkeypatch):
    import audit_p5 as A
    monkeypatch.setattr(A, "OUT", tmp_path)
    monkeypatch.setattr(A, "INPUT_CONFIG", survey.get_config("survey_p8"))
    monkeypatch.setattr(A, "RULES_VERSION", "p7.0")
    (tmp_path / "fit").mkdir()
    path = tmp_path / "fit" / "tic999_P2.0000.json"
    current = {"rules_version": "p7.0", "input_config": A.input_config()}
    path.write_text(json.dumps(current), encoding="utf-8")
    assert A.fit_step(999, 2.0) == current
    path.write_text(json.dumps(dict(current, input_config=None)), encoding="utf-8")
    def preparing(*_):
        raise RuntimeError("recomputing the stale fit")
    monkeypatch.setattr(A, "_ephemeris", preparing)
    with pytest.raises(RuntimeError, match="recomputing the stale fit"):
        A.fit_step(999, 2.0)


def test_stagea_threshold_record_follows_the_selected_rules(monkeypatch):
    from dataclasses import replace
    import audit_p5 as A
    import revet_p6 as V
    monkeypatch.setattr(V, "THRESHOLDS", dict(V.THRESHOLDS))
    monkeypatch.setattr(V, "RULES", V.RULES)
    monkeypatch.setattr(V, "RULE_SET", V.RULE_SET)
    monkeypatch.setattr(A, "RULES", A.RULES)
    monkeypatch.setattr(A, "RULES_VERSION", A.RULES_VERSION)
    V.set_rules(A.R.DEFAULT_RULES)
    previous = V.THRESHOLDS["stageA"]
    V.set_rules(replace(A.R.DEFAULT_RULES, depth_consistency_p_min=1e-4))
    assert V.THRESHOLDS["stageA"]["min_p_const"] == 1e-4
    assert previous["min_p_const"] == 1e-3


def test_native_fit_uses_stellar_limb_darkening_without_a_packet(tmp_path, monkeypatch):
    import audit_p5 as A
    monkeypatch.setattr(A, "PACKETS_DIR", tmp_path)
    monkeypatch.setattr(A, "INPUT_CONFIG", survey.get_config("survey_p8"))
    monkeypatch.setattr(A, "stellar_from_cache", lambda _: {})
    monkeypatch.setattr(A, "survivor_row", lambda *_: {"teff_k": "3146"})
    u1, u2, source = A._ld_from_packet(999, 2.0)
    assert (u1, u2) == survey.limb_darkening_for_teff(3146)
    assert "TIC Teff 3146 K" in source
    A.set_input_config()
    assert A._ld_from_packet(999, 2.0) == (0.45, 0.2, "default quadratic (no packet)")
