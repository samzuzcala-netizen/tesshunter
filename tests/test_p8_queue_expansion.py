"""A failed worker launch must never allow a retry to race still-running producers."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.mark.parametrize("wait_for_capacity", [False, True])
def test_launch_failure_waits_for_original_and_started_helper(tmp_path, monkeypatch, wait_for_capacity):
    import p8_expand_injection_queue as E

    class Process:
        pid = 123

        def __init__(self, pending):
            self.pending = pending
            self.finished = False

        def poll(self):
            if self.pending:
                self.pending -= 1
                return None
            self.finished = True
            return 0

        def wait(self):
            assert self.finished
            return 0

    original, helper, capacity = Process(3), Process(5), Process(3)
    launched = []

    def spawn(*args, **kwargs):
        assert not wait_for_capacity or capacity.finished
        if launched:
            raise OSError("test launch failure")
        launched.append(helper)
        return helper

    queue = tmp_path / "queue.sqlite"
    queue.touch()
    monkeypatch.setattr(E, "LOGS", tmp_path)
    monkeypatch.setattr(E, "os", SimpleNamespace(name="nt", getpid=lambda: 1))
    monkeypatch.setattr(E, "ExistingProcess", lambda pid: capacity if pid == 2 else original)
    monkeypatch.setattr(E, "subprocess", SimpleNamespace(Popen=spawn, CREATE_NO_WINDOW=0, STDOUT=-2))
    monkeypatch.setattr(E.time, "sleep", lambda _: None)
    arguments = ["expand", "--parent-pid", "1", "--queue", str(queue), "--workers", "2"]
    if wait_for_capacity:
        arguments.extend(["--wait-pid", "2"])
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(OSError, match="test launch failure"):
        E.main()
    assert original.finished and helper.finished
