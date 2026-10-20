"""Frozen decision boundaries and refusal to select on partial measurements."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "p10_search_choice", Path(__file__).resolve().parents[1] / "p10/protocol/finalize_search_comparison.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
choose = _module.choose_variant


def measurements():
    base = {"n_injections": 600, "n_fa_stars": 300, "n_R_7_15": 200,
            "recovered_R_7_15": 80, "n_pregate": 200, "FA_S_count": 2,
            "FA_S_complete": True, "median_wall_s": 100.0}
    rows = {v: deepcopy(base) for v in "abce"}
    rows["b"]["recovered_R_7_15"] = 81
    rows["e"].update(recovered_R_7_15=90, n_pregate=300, median_wall_s=300.0)
    return rows


def test_all_three_inclusive_boundaries_and_p8_metric():
    result = choose(measurements())
    assert result["variant"] == "e"
    assert result["eligibility"]["e"]["gain_percentage_points"] == 5.0


@pytest.mark.parametrize("field,value", [
    ("recovered_R_7_15", 89), ("n_pregate", 301),
    ("median_wall_s", math.nextafter(300.0, math.inf)),
])
def test_just_outside_each_adoption_boundary_retains_a(field, value):
    rows = measurements(); rows["e"][field] = value
    assert choose(rows)["variant"] == "a"


def test_equal_recovery_chooses_lower_median_wall():
    rows = measurements(); rows["b"]["recovered_R_7_15"] = 90
    assert choose(rows)["variant"] == "b"


def test_fa_s_is_required_but_has_no_added_eligibility_threshold():
    rows = measurements(); rows["e"]["FA_S_count"] = 300
    assert choose(rows)["variant"] == "e"


@pytest.mark.parametrize("field,value", [
    ("n_injections", 599), ("n_fa_stars", 299), ("FA_S_complete", False),
    ("FA_S_count", None), ("median_wall_s", float("nan")), ("n_R_7_15", 199),
])
def test_incomplete_or_unpaired_measurements_cannot_select(field, value):
    rows = measurements(); rows["e"][field] = value
    with pytest.raises(RuntimeError):
        choose(rows)


def test_b_c_tie_requires_d_and_rejects_e():
    rows = measurements(); rows["b"]["recovered_R_7_15"] = 80
    with pytest.raises(RuntimeError, match="Fourth variant"):
        choose(rows)
    rows["d"] = rows.pop("e")
    assert choose(rows)["variant"] == "d"


def test_missing_fourth_variant_is_not_a_decision():
    rows = measurements(); del rows["e"]
    with pytest.raises(RuntimeError, match="Four complete"):
        choose(rows)
