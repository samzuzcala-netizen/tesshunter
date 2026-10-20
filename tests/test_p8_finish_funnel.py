"""The real-funnel coordinator must not silently lose candidates between stages."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from p8_finish_funnel import stage_gaps


def test_stage_check_catches_missing_error_and_stale_records(tmp_path):
    folder = tmp_path / "stageA"
    folder.mkdir()
    jobs = [{"tic_id": i, "period": 2.0} for i in range(1, 5)]
    for tic, decision, version in [(1, "PASS", "p8.0"), (2, "ERROR", "p8.0"), (3, "FAIL", "p7.0")]:
        (folder / f"tic{tic}_P2.0000.json").write_text(json.dumps(
            {"decision": decision, "rules_version": version}))
    gaps = stage_gaps(tmp_path, "A", jobs, lambda r: r.get("rules_version") == "p8.0")
    assert [r["key"] for r in gaps] == ["tic2_P2.0000", "tic3_P2.0000", "tic4_P2.0000"]


def test_secondary_hold_is_terminal_but_error_is_not(tmp_path):
    folder = tmp_path / "secondary"
    folder.mkdir()
    jobs = [{"tic_id": i, "period": 2.0} for i in range(1, 3)]
    for tic, gate in [(1, "HOLD"), (2, "ERROR")]:
        (folder / f"tic{tic}_P2.0000.json").write_text(json.dumps({"gate": gate}))
    assert [r["key"] for r in stage_gaps(tmp_path, "S", jobs, lambda r: True)] == ["tic2_P2.0000"]


def test_empty_stage_needs_no_records(tmp_path):
    assert stage_gaps(tmp_path, "C", [], lambda r: False) == []
