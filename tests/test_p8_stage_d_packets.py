"""The P8 packet adapter must use the audit fit and native inputs, without a re-search."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import p8_stage_d_packets as D


@pytest.fixture
def native_case(tmp_path, monkeypatch):
    import audit_p5 as A
    root = tmp_path / "p8"
    key = "tic99_P2.0000"
    job = {"key": key, "tic_id": 99, "period": 2.0}
    for folder in ("stageA", "secondary", "stageB", "stageC", "stageD", "fit", "tls", "neighbours"):
        (root / folder).mkdir(parents=True)
    adopted = {"period": 2.0000123, "t0_btjd": 3001.25, "rp_rs": .1, "a_rs": 12., "b": .3,
               "t14_hours": 1.2, "depth_max_ppt": 11.}
    for folder in ("stageA", "secondary", "stageB", "stageC", "stageD", "fit", "tls"):
        rec = {"rules_version": "p8.0", "adopted": adopted, "data": {"beta_red_noise": 2.1},
               "decision": "PASS", "gate": "PASS", "provisional_verdict": "SUBMIT",
               "blind": {"period": 2.00001, "T0_btjd": 3001.25, "duration_days": 0.05, "depth": 0.989},
               "inputs": {"products": [{"sector": 60, "cadence_s": 200.}]}}
        (root / folder / f"{key}.json").write_text(json.dumps(rec))
    (root / "crossmatch_p8.json").write_text("{}")
    (root / "neighbours/tic99.json").write_text(json.dumps({"ra": 30., "dec": -40., "tmag": 13.,
                                                          "gaia": {"target": {"ruwe": 1.1}, "neighbours": []}}))
    times = 3000. + np.arange(80) * 200 / 86400
    np.savez(root / "tls" / f"{key}_lc.npz", time_unbinned=times,
             flux_unbinned=np.ones(80), sector_unbinned=np.full(80, 60))
    monkeypatch.setattr(D, "REPO", tmp_path)
    monkeypatch.setattr(A, "cache_matches", lambda r: r.get("rules_version") == "p8.0")
    monkeypatch.setattr(A, "OUT", root)
    monkeypatch.setattr(A, "_ephemeris", lambda *_: {"duration": 0.05, "ref_depth_ppt": 11})
    fit_path = root / "fit" / f"{key}.json"
    fit = D.read(fit_path)
    fit["fit_input"] = A._p8_fit_input(job["tic_id"], job["period"])
    fit_path.write_text(json.dumps(fit))
    monkeypatch.setattr(D, "setup", lambda root: SimpleNamespace(V=SimpleNamespace(gaia_flags=lambda n, d: {})))
    return root, job, adopted, times


def test_expensive_calls_receive_exact_audit_fit_and_native_series(native_case, monkeypatch):
    import survivor_packets as S
    from tesshunter import fpp
    root, job, fit, times = native_case
    seen = {}
    def centroid(*args, **kwargs):
        seen["centroid"] = (args, kwargs)
        return {"available": True}
    def fake_fpp(*args, **kwargs):
        seen["fpp"] = (args, kwargs)
        return SimpleNamespace(to_dict=lambda: {"available": True, "fpp": .01, "nfpp": .001})
    monkeypatch.setattr(S, "centroid_all_sectors", centroid)
    monkeypatch.setattr(fpp, "run_fpp", fake_fpp)
    packets = []
    monkeypatch.setattr(D, "build_packet", lambda *args: packets.append(args))
    rec = D.measure_one(root, job)
    assert rec["status"] == "complete"
    args, kw = seen["fpp"]
    np.testing.assert_array_equal(args[2], times)
    assert kw["period"] == fit["period"] != job["period"]
    assert kw["t0"] == fit["t0_btjd"]
    assert kw["exp_time_days"] == 200 / 86400
    assert kw["fold_mode"] == "binned"
    assert kw["input_fingerprint"] == rec["input_fingerprint"]
    assert seen["centroid"][1] == {"tesscut_only": True}
    assert rec["gaia_neighbours"]["target"]["ruwe"] == 1.1
    assert len(packets) == 1
    # A completed measurement still regenerates a missing/outdated packet on resume.
    seen.clear()
    D.measure_one(root, job)
    assert seen == {} and len(packets) == 2
    # Even an unchanged fit must not reuse FPP from a different prepared series.
    np.savez(root / "tls" / f"{job['key']}_lc.npz", time_unbinned=times,
             flux_unbinned=np.full(80, 1.0001), sector_unbinned=np.full(80, 60))
    D.measure_one(root, job)
    assert seen["fpp"][1]["input_fingerprint"] != rec["input_fingerprint"]
    assert seen["fpp"][1]["force"] is False
    D.measure_one(root, job, force=True)
    assert seen["fpp"][1]["force"] is True


@pytest.mark.parametrize("change", ["stale", "coarse", "old_sector"])
def test_invalid_inputs_stop_before_expensive_work(native_case, change):
    root, job, _, _ = native_case
    path = root / "tls" / f"{job['key']}.json"
    data = D.read(path)
    if change == "stale":
        data["rules_version"] = "p7.0"
    elif change == "coarse":
        data["inputs"]["products"][0]["cadence_s"] = 1800
    else:
        data["inputs"]["products"][0]["sector"] = 55
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        D.measurement_inputs(root, job)


def test_uniform_probability_diagnostic_does_not_mislabel_named_equal_scenarios():
    assert D.uniform_fpp({"top_scenarios": [{"scenario": "", "prob": .25}] * 3})
    assert not D.uniform_fpp({"top_scenarios": [{"scenario": "TP", "prob": .25}] * 3})


def test_previously_queued_candidate_cannot_bypass_a_changed_gate(native_case):
    root, job, _, _ = native_case
    path = root / "stageC" / f"{job['key']}.json"
    data = D.read(path)
    data["decision"] = "FAIL"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="stageC did not pass"):
        D.measurement_inputs(root, job)


@pytest.mark.parametrize("change", ["survey_seeded_fit", "changed_accepted_period"])
def test_packet_refuses_a_fit_of_an_outdated_signal(native_case, change):
    root, job, _, _ = native_case
    folder = "fit" if change == "survey_seeded_fit" else "stageC"
    path = root / folder / f"{job['key']}.json"
    data = D.read(path)
    if change == "survey_seeded_fit":
        data.pop("fit_input")
    else:
        data["blind"]["period"] += 0.003
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="current accepted Stage C ephemeris"):
        D.measurement_inputs(root, job)


def test_attached_pixel_review_refuses_changed_measurements(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setattr(D, "REPO", tmp_path)
    root, out = tmp_path / "p8", tmp_path / "packet"
    (root / "pixel_followup").mkdir(parents=True)
    out.mkdir()
    measurement = root / "measurement.json"
    measurement.write_text('{"depth": 2.7}')
    review = {"key": "test", "status": "complete", "assessment": "Unresolved source",
              "what_would_change": "Resolve the transit location", "figures": [],
              "source_sha256": {"p8/measurement.json": hashlib.sha256(measurement.read_bytes()).hexdigest()}}
    (root / "pixel_followup/test.json").write_text(json.dumps(review))
    assert "Unresolved source" in D.pixel_followup_lines(root, "test", out)
    measurement.write_text('{"depth": 0.0}')
    with pytest.raises(ValueError, match="stale pixel follow-up"):
        D.pixel_followup_lines(root, "test", out)
