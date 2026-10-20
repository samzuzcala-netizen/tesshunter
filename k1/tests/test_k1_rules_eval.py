"""Rules E1-E4 (change 14 is rule E4) and the worker preset assertions (change 6)."""
import json

import pytest

import rules_eval_k1 as E


def test_e4_smallest_budget_with_at_most_5pct():
    assert E.e4_budget({2700: 0.12, 5400: 0.05, 8100: 0.0})["budget_s"] == 5400.0
    assert E.e4_budget({2700: 0.02, 5400: 0.0, 8100: 0.0})["budget_s"] == 2700.0
    r = E.e4_budget({2700: 0.3, 5400: 0.2, 8100: 0.08})
    assert r["budget_s"] == 8100.0 and not r["qualified"]


def test_e1_all_three_conditions():
    assert E.e1_cadence(5.0, 1.0, 1.2, 2.0)["adopt"] == "survey_k1"
    assert E.e1_cadence(5.0, -0.1, 1.2, 2.0)["adopt"] == "survey_k1_s56"
    assert E.e1_cadence(2.9, 1.0, 1.2, 2.0)["adopt"] == "survey_k1_s56"
    assert E.e1_cadence(5.0, 1.0, 1.6, 2.0)["adopt"] == "survey_k1_s56"
    assert E.e1_cadence(5.0, 1.0, 1.2, 3.1)["adopt"] == "survey_k1_s56"


def test_e2_constraint_and_ties():
    ret = {"bound": .40, "empirical_bound": .45, "recurrent_bound": .50, "recurrent_bound_corr": .50, "bound_alias": .55}
    pt = {"bound": .10, "empirical_bound": .12, "recurrent_bound": .14, "recurrent_bound_corr": .13, "bound_alias": .20}
    r = E.e2_mode(ret, pt)
    assert r["choice"] == "recurrent_bound" and "bound_alias" not in r["allowed"]     # 0.20 > 0.10 + 0.05
    pt["bound_alias"] = .15
    assert E.e2_mode(ret, pt)["choice"] == "bound_alias"
    tie = dict(ret, bound_alias=.50)
    assert E.e2_mode(tie, pt)["choice"] == "recurrent_bound"                        # simpler mode wins a tie


def test_e3():
    assert E.e3_ramp(0.62, 0.60, 0.12, 0.10)["adopt"]
    assert not E.e3_ramp(0.62, 0.60, 0.13, 0.10)["adopt"]
    assert not E.e3_ramp(0.615, 0.60, 0.10, 0.10)["adopt"]


def test_workers_refuse_unregistered_presets(tmp_path):
    import search_worker_k1 as S
    rt = tmp_path / "rt.json"
    rt.write_text(json.dumps({"job_id": "x", "tic_id": 1, "preset": "survey_p10", "star": {}, "lc_root": str(tmp_path),
                              "cache_dir": str(tmp_path), "run_dir": str(tmp_path), "overrides": {}}))
    with pytest.raises(RuntimeError, match="Unregistered preset"):
        S.main(str(rt))
    import funnel_k1 as F
    rt2 = tmp_path / "rt2.json"
    rt2.write_text(json.dumps({"candidate_id": "c", "tic_id": 1, "candidate": {}, "all_candidates": [], "star": {},
                               "lc_root": str(tmp_path), "root": str(tmp_path), "preset": "survey_p10", "s_mode": "bound",
                               "ramp_variant": False, "label": "t"}))
    with pytest.raises(RuntimeError, match="Unregistered preset"):
        F.main("A", str(rt2))
    assert S.PRESETS == ("survey_k1", "survey_k1_s56")
