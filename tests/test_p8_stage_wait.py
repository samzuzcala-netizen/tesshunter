"""A resumed stage must not race a helper that still owns claimed candidates."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import p8_stage_wait as W


REPO = Path("C:/Science/P8 Project")
ROOT = REPO / "data/survey/p8"
QUEUE = "data/survey/p8/logs/C_ready_batch4.sqlite"


def process(arguments, pid=21, parent=20):
    return {"ProcessId": pid, "ParentProcessId": parent,
            "CommandLine": '"C:\\Python\\python.exe" -u ' + arguments}


@pytest.mark.parametrize("arguments,pid,parent,expected", [
    ('scripts/p8_funnel.py slice --stage C --queue ' + QUEUE, 20, 1, True),
    ('scripts/p8_funnel.py slice --stage C --queue ' + QUEUE, 21, 20, True),
    ('scripts/p8_funnel.py slice --stage C --queue ' + QUEUE, 30, 1, False),
    ('scripts/p8_funnel.py slice --stage C --queue data/survey/p8/logs/other.sqlite', 20, 1, False),
    ('scripts/p8_funnel.py slice --stage A --queue ' + QUEUE, 20, 1, False),
    ('"C:/Science/P8 Project/scripts/p8_funnel.py" --root "C:/Science/P8 Project/data/survey/p8" slice --stage C', 30, 1, True),
    ('scripts/p8_funnel.py --root "C:/Science/P8 Project/data/survey/p8/demo" slice --stage C --queue ' + QUEUE, 20, 1, False),
    ('"C:/other/scripts/p8_funnel.py" slice --stage C --queue ' + QUEUE, 20, 1, False),
    ('scripts/p8_funnel.py stageC --slices 16', 20, 1, False),
    ('scripts/p8_funnel.py slice --stage', 20, 1, False),
    ('"scripts/p8_funnel.py slice --stage C', 20, 1, False),
])
def test_identifies_the_run_and_stage_not_just_a_reused_pid(arguments, pid, parent, expected):
    result = W.matching_workers([process(arguments, pid, parent)], "C", REPO, ROOT, {20: QUEUE})
    assert bool(result) is expected


def test_waits_for_launcher_and_child_without_touching_measurements(tmp_path):
    root = tmp_path / "data/survey/p8"
    root.mkdir(parents=True)
    (root / "C_ready_batch4.json").write_text(json.dumps({"queue": QUEUE, "launcher_pid": 20}))
    measurement = root / "science.json"
    measurement.write_text('{"decision": "PASS"}')
    before = measurement.read_bytes()
    workers = [process("scripts/p8_funnel.py slice --stage C --queue " + QUEUE, p, parent)
               for p, parent in [(20, 1), (21, 20)]]
    snapshots = iter([workers, workers[1:], []])
    sleeps = []
    W.wait_for_existing_workers("C", tmp_path, root,
                                process_source=lambda: next(snapshots), sleep=sleeps.append)
    assert sleeps == [15, 15]
    assert measurement.read_bytes() == before


def test_enumeration_failure_does_not_allow_a_fresh_queue(tmp_path, monkeypatch):
    import p8_funnel as F

    def failure(*args):
        raise RuntimeError("enumeration failed")

    monkeypatch.setattr(W, "wait_for_existing_workers", failure)
    monkeypatch.setattr(F, "OUT", tmp_path)
    monkeypatch.setattr(F, "eligible", lambda stage: pytest.fail("read eligibility before waiting"))
    with pytest.raises(RuntimeError, match="enumeration failed"):
        F.run_stage("A", 1, 1, 3, False, "p8.0", shared_queue=True)
    assert not list(tmp_path.iterdir())


def test_stage_waits_before_snapshotting_eligibility_and_launching(tmp_path, monkeypatch):
    import p8_funnel as F
    import p8_work_queue as Q

    events = []
    monkeypatch.setattr(W, "wait_for_existing_workers", lambda *args: events.append("wait"))
    monkeypatch.setattr(F, "OUT", tmp_path)
    monkeypatch.setattr(F, "eligible", lambda stage: events.append("eligible") or [])
    monkeypatch.setattr(Q, "create_queue", lambda *args: events.append("queue"))
    monkeypatch.setattr(F.V, "write_stage_csv", lambda *args: events.append("csv"))
    F.run_stage("C", 0, 1, 3, False, "p8.0", shared_queue=True)
    assert events == ["wait", "eligible", "queue", "csv"]


@pytest.mark.parametrize("stage,relative_root", [("B", "data/survey/p8"), ("A", "data/survey/p8/fa_funnel")])
def test_other_stages_and_exercise_roots_do_not_wait(tmp_path, stage, relative_root):
    W.wait_for_existing_workers(stage, tmp_path, tmp_path / relative_root,
                                process_source=lambda: pytest.fail("unrelated run enumerated"))
