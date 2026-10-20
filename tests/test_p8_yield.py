"""Occurrence-cell accounting for P8's pre-registered yield decision."""
import math
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from p8_expected_yield import box_fraction, remaining_fraction


def test_literature_box_includes_the_part_of_a_cell_below_ten_days():
    cell = {"p_lo": 5.5, "p_hi": 18.2, "r_lo": 2.0, "r_hi": 2.5}
    assert box_fraction(cell) == pytest.approx(math.log(10 / 5.5) / math.log(18.2 / 5.5))
    assert box_fraction(dict(cell, p_lo=18.2, p_hi=30)) == 0
    assert box_fraction(dict(cell, p_lo=0.5, p_hi=1.7)) == 1


def test_prior_and_recovery_are_applied_jointly_before_cell_sum():
    # One readily recoverable cell is already catalogued; a second is unseen but unrecoverable.
    # Their expected NEW yield is zero. Averaging the prior first spuriously gives 0.5.
    prior = {"A": {"mid": 1.0}, "B": {"mid": 0.0}, "C": {"mid": 0.0}}
    total = (1.0 * remaining_fraction({"A": 1, "B": 0, "C": 0}, prior, "mid")
             + 0.0 * remaining_fraction({"A": 0, "B": 1, "C": 0}, prior, "mid"))
    assert total == 0
    assert remaining_fraction({"A": 1, "B": 3, "C": 0}, prior, "mid") == 0.75


def test_yield_entrypoint_writes_consistent_model_and_provenance(tmp_path, monkeypatch):
    """Exercise the first-use integration with synthetic calibration, never real survey outputs."""
    import p8_expected_yield as E

    targets = tmp_path / "targets.csv"
    rows = [{"tic_id": tic, "radius_rsun": 0.3, "mass_msun": 0.3, "teff_k": 3300,
             "contamination_ratio": 0.05} for tic in (1, 2)]
    rows[1]["contamination_ratio"] = ""  # use the same measured-median fill as the real missing entries
    with targets.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    noise = {"sigma": 0.005, "n_cad": 40000, "cadence_days": 200 / 86400,
             "span_days": 500, "data_days": 40000 * 200 / 86400, "n_sectors": 4, "rot": None}
    monkeypatch.setattr(E, "measure_population_noise", lambda *a, **k: {1: noise, 2: noise})
    calibration = tmp_path / "synthetic_calibration.json"
    calibration.write_text(json.dumps({
        "generated_utc": "test fixture", "rules_version": "synthetic", "n_injections": 12, "n_stars": 2,
        "levels": {"search_only": {"logistic": {"a": -2, "b": 1}},
                   "full_funnel_with_pregate": {"logistic": {"a": -4, "b": 1}}},
        "false_alarms": {"stageA_pass_and_secondary_per_star": 1 / 12},
    }))
    output = tmp_path / "yield.json"
    E.main(["--targets", str(targets), "--completeness", str(calibration), "--out", str(output)])
    result = json.loads(output.read_text())
    json.dumps(result, allow_nan=False)
    assert result["n_stars_with_prepared_curve"] == result["n_targets"] == 2
    assert result["contamination_fill"] == pytest.approx(0.05)
    assert result["per_star"][0]["new"] == result["per_star"][1]["new"]
    assert result["calibration"]["rules_version"] == "synthetic"
    assert result["calibration"]["stages"] == ["search", "pre-gate", "Stage A", "secondary"]
    funnel = result["expected_new_signals"]["through_funnel"]
    assert 0 < funnel["high"] < funnel["mid"] < funnel["low"]
    for prior in ("high", "mid", "low"):
        assert funnel[prior] < result["expected_new_signals"]["search_only"][prior]
        assert funnel[prior] == pytest.approx(sum(star["new"][prior] for star in result["per_star"]))
    assert result["expected_funnel_passing_false_alarms"] == pytest.approx(1 / 6)
    assert result["decision"]["stop"] is True
    assert result["decision"]["mid_prior_expectation"] == funnel["mid"]
