"""The reported central funnel includes its pre-gate and the required control sample."""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_false_alarm_count_requires_secondary_failure_sample(tmp_path, monkeypatch):
    import audit_p5 as A
    import p8_completeness as C
    from p8_funnel import select_secondary_jobs
    from tesshunter.survey import get_config

    monkeypatch.setattr(C, "FA_ROOT", tmp_path)
    rows = [{"rank": i + 1, "tic_id": i + 100, "period_days": 2.0} for i in range(11)]
    write_csv(tmp_path / "survivors.csv", rows)
    (tmp_path / "collect_p8.json").write_text(json.dumps({"n_stars_ok": 11, "n_pass_pregate": 11,
                                                        "n_accepted_candidates": 11}))
    context = {"rules_version": "p7.0", "input_config": A.input_config_for(get_config("survey_p8"))}
    for directory in ("stageA", "secondary"):
        (tmp_path / directory).mkdir()
    jobs = [{"tic_id": r["tic_id"], "period": r["period_days"]} for r in rows]
    decisions = {C.kkey(j["tic_id"], j["period"]): ("PASS" if i == 0 else "FAIL") for i, j in enumerate(jobs)}
    for key, decision in decisions.items():
        (tmp_path / "stageA" / f"{key}.json").write_text(json.dumps(dict(context, key=key, decision=decision)))
    # A leftover record outside this population must not inflate the measured rate.
    (tmp_path / "stageA" / "extra.json").write_text(json.dumps({"key": "extra", "decision": "PASS"}))
    pass_key = C.kkey(100, 2.0)
    (tmp_path / "secondary" / f"{pass_key}.json").write_text(json.dumps(dict(context, key=pass_key, gate="PASS")))
    with pytest.raises(ValueError, match="incomplete/stale gate"):
        C.fa_funnel_counts(11, "p7.0")
    sample = [j for j in select_secondary_jobs(jobs, decisions) if j["stageA_sample"]]
    assert len(sample) == 1
    key = C.kkey(sample[0]["tic_id"], sample[0]["period"])
    (tmp_path / "secondary" / f"{key}.json").write_text(json.dumps(dict(context, key=key, gate="FAIL")))
    result = C.fa_funnel_counts(11, "p7.0")
    assert result["stageA_done"] == 11
    assert result["stageA_pass_and_secondary"] == 1
    assert result["stageA_failure_sample_gate"] == {"PASS": 0, "FAIL": 1, "HOLD": 0}


@pytest.mark.parametrize("amplitude", [3.0, 3e30])
def test_analysis_preserves_pre_gate_losses_in_all_maps(tmp_path, monkeypatch, amplitude):
    import p8_completeness as C

    monkeypatch.setattr(C, "P8", tmp_path)
    spec = tmp_path / "spec.csv"
    sample = tmp_path / "sample.csv"
    monkeypatch.setattr(C, "SPEC", spec)
    monkeypatch.setattr(C, "SAMPLE", sample)
    write_csv(sample, [{"tic_id": 100}])
    rows = [{"job_id": f"j{i}", "period": 2.0, "period_bin": 1, "rp_earth": 2.1,
             "rp_rs": 0.05, "b": 0.2, "tmag": 13.2} for i in range(3)]
    write_csv(spec, rows)
    records = [{"job_id": r["job_id"], "tic_id": 100, "status": "ok", "wall_s": 1.0} for r in rows]
    jobs = [{"job_id": r["job_id"], "pregate_pass": i != 1} for i, r in enumerate(rows)]
    outcomes = {r["job_id"]: {"stageA": "FAIL" if i == 2 else "PASS", "secondary_gate": "PASS",
                              "stageA_criteria": {"kept_snr": i != 2}} for i, r in enumerate(rows)}
    monkeypatch.setattr(C, "_load_results", lambda _: records)
    monkeypatch.setattr(C, "recovered_jobs", lambda _: jobs)
    monkeypatch.setattr(C, "load_funnel_outcomes", lambda *a, **k: outcomes)
    monkeypatch.setattr(C, "fa_funnel_counts", lambda *a, **k: {"available": False})
    monkeypatch.setattr(C, "classify", lambda _: {"status": "recovered", "ratio": 1,
                                                 "matched_snr": 12, "matched_stitch_snr": 12})
    snr = {r["job_id"]: {"snr_expected": 12, "rotation_proxy": {"semi_amplitude_ppt": amplitude}} for r in rows}
    (tmp_path / "expected_snr_p8.json").write_text(json.dumps(snr))
    result = C.analyze("p7.0")
    assert result["levels"]["search_and_stageA_and_secondary"]["n_through"] == 2
    assert result["levels"]["full_funnel_with_pregate"]["n_through"] == 1
    for name in ("by_period_bin", "by_rp_earth", "by_tmag", "by_rotation_amplitude"):
        nonempty = [r for r in result[name].values() if r["n"]]
        assert len(nonempty) == 1
        assert nonempty[0]["through_funnel"] == 2
        assert nonempty[0]["through_funnel_pregated"] == 1
    assert sum(r["k"] for r in result["map_period_x_snr"]["1"]["funnel_pregated"]) == 1
    assert sum(r["n"] for r in result["by_rotation_amplitude"].values()) == 3
    assert result["rotation_proxy_quality"]["n_extreme_injections"] == (3 if amplitude > 1e9 else 0)
