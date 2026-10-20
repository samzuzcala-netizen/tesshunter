"""Prevent mixed configurations, modified provenance and unsafe worker restarts."""
import importlib.util
from pathlib import Path
from copy import deepcopy
import json

import pytest

path = Path(__file__).resolve().parents[1] / "p10/protocol/run_part2d_injection_search.py"
spec = importlib.util.spec_from_file_location("p10_injection_continuation", path)
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def example():
    job = dict(job_id="inj00000_tic1", tic_id=1, injection={"period":2.0}, star={"mass_msun":0.5})
    config = dict(name="survey_p10", rank_by="snr", record_traces=True)
    rec = dict(**deepcopy(job), status="ok", orchestrator_status="ok",
               config=dict(config, name="survey_p10_both"), injection_model={"period":2.0}, result={})
    return rec, job, config


def test_reused_selected_configuration_keeps_its_historical_name():
    rec, job, config = example()
    before = deepcopy(rec)
    C.check_record(rec, job, config, original=True)
    assert rec == before
    with pytest.raises(AssertionError):
        C.check_record(rec, job, config, original=False)


@pytest.mark.parametrize("bad", ["baseline_config", "wrong_injection", "wrong_host", "unfinished_orchestrator"])
def test_result_from_wrong_experiment_or_unsettled_worker_is_rejected(bad):
    rec, job, config = example()
    if bad == "baseline_config":
        rec["config"]["rank_by"] = "composite"
    elif bad == "wrong_injection":
        rec["injection"]["period"] = 3.0
    elif bad == "wrong_host":
        rec["tic_id"] = 2
    else:
        rec.pop("orchestrator_status")
    with pytest.raises(AssertionError):
        C.check_record(rec, job, config, original=True)


def test_changed_frozen_input_prevents_resume(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    source.write_text("original")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(dict(source_sha256={"source.py":C.sha(source)}, input_sha256={}, reused_files=[])))
    monkeypatch.setattr(C, "REPO", tmp_path)
    monkeypatch.setattr(C, "MANIFEST", manifest)
    monkeypatch.setattr(C, "frozen_section_sha", lambda:C.FROZEN_SHA)
    C.verify_manifest()
    source.write_text("changed")
    with pytest.raises(AssertionError, match="Frozen source/input changed"):
        C.verify_manifest()


def test_live_pid_file_is_refused_without_killing_or_removing_it(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    pidfile = jobs / "inj00000_tic1.pid"
    pidfile.write_text("12345")
    monkeypatch.setattr(C, "RUN", tmp_path)
    monkeypatch.setattr(C, "process_snapshot", lambda:dict(processes=[], inaccessible_pids=[]))
    monkeypatch.setattr(C.psutil, "pid_exists", lambda pid:pid == 12345)
    with pytest.raises(RuntimeError, match="Live PID file needs identity review"):
        C.require_no_workers()
    assert pidfile.read_text() == "12345"


def test_incomplete_process_visibility_prevents_launch(monkeypatch):
    monkeypatch.setattr(C, "process_snapshot", lambda:dict(processes=[], inaccessible_pids=[42]))
    with pytest.raises(RuntimeError, match="incomplete visibility"):
        C.require_no_workers()
