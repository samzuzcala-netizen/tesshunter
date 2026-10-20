"""No live-owner duplication, no partial-root overwrite, and immutable reuse."""
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def queue(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "p10/protocol"))
    q = importlib.import_module("run_corrected_c_controls")
    monkeypatch.setattr(q, "ROOT", tmp_path)
    monkeypatch.setattr(q, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(q, "LOCK", tmp_path / "state.lock")
    monkeypatch.setattr(q, "RECEIPTS", tmp_path / "receipts")
    monkeypatch.setattr(q, "MANIFEST", tmp_path / "manifest.json")
    q.MANIFEST.write_text("{}")
    item = {"id": "example", "workspace": "case"}
    monkeypatch.setattr(q, "load_manifest", lambda: {"items": [item]})
    monkeypatch.setattr(q, "owners", lambda: [])
    monkeypatch.setattr(q.subprocess, "run", lambda *a, **k: pytest.fail("unexpected TLS launch"))
    return q


def test_live_owner_prevents_even_a_new_lock(queue, monkeypatch):
    monkeypatch.setattr(queue, "owners", lambda: [{"pid": 123}])
    with pytest.raises(RuntimeError, match="owns"):
        queue.run_queue()
    assert not queue.LOCK.exists() and not queue.STATE.exists()


def test_partial_workspace_is_preserved_and_queue_stops(queue):
    workspace = queue.ROOT / "case"; workspace.mkdir()
    artifact = workspace / "partial.json"; artifact.write_bytes(b"old scientific output")
    with pytest.raises(RuntimeError, match="Partial control"):
        queue.run_queue()
    assert artifact.read_bytes() == b"old scientific output"
    assert queue.read(queue.STATE)["status"] == "stopped_review_required"
    assert not queue.LOCK.exists()


def test_verified_completion_is_reused_without_rewriting_time_or_receipt(queue, monkeypatch):
    queue.RECEIPTS.mkdir()
    path = queue.RECEIPTS / "example.json"
    saved = {"id": "example", "wall_s": 1234.5}
    path.write_text(json.dumps(saved)); before = path.read_bytes()
    monkeypatch.setattr(queue, "validate_case", lambda item: dict(saved))
    queue.run_queue()
    assert path.read_bytes() == before
    assert queue.read(queue.STATE)["n_complete"] == 1


def test_changed_completion_is_not_silently_accepted(queue, monkeypatch):
    queue.RECEIPTS.mkdir()
    path = queue.RECEIPTS / "example.json"
    path.write_text(json.dumps({"id": "example", "wall_s": 1234.5})); before = path.read_bytes()
    monkeypatch.setattr(queue, "validate_case", lambda item: {"id": "example", "wall_s": 0.1})
    with pytest.raises(RuntimeError, match="Completed control changed"):
        queue.run_queue()
    assert path.read_bytes() == before and not queue.LOCK.exists()


def test_case_requires_an_actual_parent_queue_owner(queue):
    queue.LOCK.write_text(json.dumps({"pid": -1}))
    with pytest.raises(RuntimeError, match="not this case's parent"):
        queue.run_case("example")
