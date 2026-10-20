"""The legacy EB controls retain their original observed sectors and cadence."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest

PROTOCOL = Path(__file__).resolve().parents[1] / "p10/protocol"
sys.path.insert(0, str(PROTOCOL))
_spec = importlib.util.spec_from_file_location("original_adversarial_c", PROTOCOL / "run_original_adversarial_c.py")
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)


def inputs():
    search = dict(data_source="SPOC 120 s", data_author="SPOC", units_used=[22, 49], n_sectors=2)
    products = [dict(sector=s, author="SPOC", cadence_s=120.0, file=f"s{s:03d}_SPOC.npz") for s in (22, 49, 95)]
    products += [dict(sector=22, author="QLP", cadence_s=1800.0, file="s022_QLP.npz")]
    return search, dict(products=products)


def test_original_pre56_sectors_are_used_without_later_or_duplicate_products():
    search, index = inputs()
    before = deepcopy((search, index))
    selected = A.select_original_products(search, index)
    assert [p["sector"] for p in selected] == [22, 49]
    assert all(p["author"] == "SPOC" and p["cadence_s"] == 120 for p in selected)
    assert (search, index) == before


@pytest.mark.parametrize("change", ["missing", "duplicate", "wrong_cadence", "wrong_author", "duplicate_unit", "wrong_count", "wrong_source"])
def test_unavailable_or_changed_original_inputs_refuse_substitution(change):
    search, index = inputs()
    if change == "missing": index["products"].pop(0)
    elif change == "duplicate": index["products"].append(deepcopy(index["products"][0]))
    elif change == "wrong_cadence": index["products"][0]["cadence_s"] = 200.0
    elif change == "wrong_author": index["products"][0]["author"] = "TESS-SPOC"
    elif change == "duplicate_unit": search["units_used"] = [22, 22]
    elif change == "wrong_count": search["n_sectors"] = 3
    else: search["data_source"] = "QLP"
    with pytest.raises(RuntimeError): A.select_original_products(search, index)


def test_profile_changes_only_sector_and_native_cadence_without_mutating_p8():
    from dataclasses import asdict
    from tesshunter.survey import get_config
    original = asdict(get_config("survey_p8"))
    corrected = asdict(A.profile_config())
    assert corrected["sector_min"] is None and corrected["target_cadence_minutes"] == 2.0
    assert corrected["bin_minutes"] is None
    assert {k for k in original if original[k] != corrected[k]} == {"sector_min", "target_cadence_minutes"}
    assert asdict(get_config("survey_p8")) == original


def test_queue_refuses_a_live_scientific_owner_before_writing(monkeypatch):
    monkeypatch.setattr(A, "load_manifest", lambda: {"items": []})
    def occupied(): raise RuntimeError("scientific owner exists")
    def forbidden_write(*args, **kwargs): pytest.fail("Busy queue must not write or launch")
    monkeypatch.setattr(A.Q, "closed_prior_queues", occupied)
    monkeypatch.setattr(A.Q, "write_new", forbidden_write)
    with pytest.raises(RuntimeError, match="scientific owner"): A.run_queue()


def test_launch_requires_explicit_frozen_source_binding(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_original_adversarial_c.py", "run"])
    monkeypatch.setattr(A, "run_queue", lambda: pytest.fail("Unbound launch must not run"))
    with pytest.raises(RuntimeError, match="Explicit binding"): A.main()
