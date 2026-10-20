"""Operational resume guards: tests never suspend or resume a real process."""
from pathlib import Path
from types import SimpleNamespace
import sys

import psutil
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p10/protocol"))
import resume_suspended_c_queue as R


SAVED = {"pid": 101, "created_epoch": 1000.0, "ppid": 100, "command": ["python", "job.py"]}


def fake_process(**changes):
    values = dict(SAVED, status=psutil.STATUS_STOPPED)
    values.update(changes)
    return SimpleNamespace(pid=values["pid"], create_time=lambda: values["created_epoch"],
                           ppid=lambda: values["ppid"], cmdline=lambda: values["command"],
                           status=lambda: values["status"])


def test_matching_suspended_identity():
    R.check_identity(fake_process(), SAVED)


@pytest.mark.parametrize("changes", [
    {"pid": 102}, {"created_epoch": 1001.0}, {"ppid": 99},
    {"command": ["python", "another.py"]}, {"status": psutil.STATUS_RUNNING},
])
def test_reused_changed_or_running_process_refused(changes):
    with pytest.raises(RuntimeError, match="do not resume PID"):
        R.check_identity(fake_process(**changes), SAVED)


def test_prior_resume_journal_refused_before_process_access(tmp_path, monkeypatch):
    receipt = tmp_path / "suspended_c_queue_test.json"
    receipt.with_name(receipt.stem + ".resume.events.jsonl").write_text("partial\n")
    monkeypatch.setattr(R, "inspect_pause", lambda _: pytest.fail("Must refuse before process access"))
    with pytest.raises(RuntimeError, match="already attempted"):
        R.resume(receipt)
    assert not receipt.with_name(receipt.stem + ".resume.json").exists()


def test_reboot_refused_before_file_or_process_access(monkeypatch):
    monkeypatch.setattr(R.Q, "load_manifest", lambda: None)
    monkeypatch.setattr(R.Q, "read", lambda _: {"status": "suspended_in_memory", "boot_time_epoch": 1000})
    monkeypatch.setattr(R.psutil, "boot_time", lambda: 2000)
    monkeypatch.setattr(R.Q, "sha", lambda _: pytest.fail("Must refuse before file checks"))
    with pytest.raises(RuntimeError, match="Windows restarted"):
        R.inspect_pause(Path("unused.json"))
