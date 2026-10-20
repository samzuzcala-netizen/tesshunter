"""Exercise the FA controller's no-launch boundaries with synthetic fixtures only."""
from pathlib import Path
from unittest.mock import patch
import copy
import json
import os
import tempfile

import run_false_alarm_funnels as C


def main():
    checks = {}
    with patch.object(C.SEARCH, "owners", return_value=[{"pid": 123, "command": "active search"}]):
        try:
            C.assert_free()
        except RuntimeError as exc:
            checks["active_search_owner_refused"] = "allocation is still owned" in str(exc)
    job = {"rank": 1, "tic_id": 1, "planet_num": 1, "period": 2.0, "epoch_btjd": 1.0,
           "duration_days": .1, "depth_ppt": 1.0, "stitch_snr": 10.0,
           "stitch_n_transits": 4, "n_units": 2, "tmag": 11.0}
    key = "tic1_P2.0000"
    temp_parent = Path(os.environ["P10_GUARD_WORK"]).resolve()
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fa_guards_", dir=temp_parent) as directory:
        root = Path(directory).resolve()
        assert root.is_relative_to(temp_parent)
        C.F.set_root(root)
        C.F.set_rules("p8.0")
        a = {"key": key, "tic_id": 1, "rank": 1, "rules_version": "p8.0",
             "decision": "PASS", "seconds": .1, "survey": {k: job[k] for k in (
                 "period", "epoch_btjd", "duration_days", "depth_ppt", "stitch_snr",
                 "stitch_n_transits", "n_units", "tmag")}, "thresholds": C.F.V.THRESHOLDS["stageA"]}
        for name in ("stageA", "prep", "tls", "secondary"):
            (root / name).mkdir()
        (root / "prep" / (key + ".json")).write_text("{}")
        (root / "tls" / (key + "_lc.npz")).write_bytes(b"fixture-existence-only")

        def expect_rejection(name, stage, jobs):
            try:
                C.read_phase(root, stage, jobs)
            except RuntimeError:
                checks[name] = True
            else:
                checks[name] = False

        # Keep receipt path conversion local to the synthetic tree.
        with patch.object(C.Q, "REPO", root):
            expect_rejection("missing_A_census_refused", "A", [job])
            ap = root / "stageA" / (key + ".json")
            ap.write_text(json.dumps(a))
            rows, _ = C.read_phase(root, "A", [job])
            checks["complete_A_fixture_accepted"] = rows[key]["decision"] == "PASS"
            for name, field, value in (("wrong_rule_refused", "rules_version", "p7.0"),
                                       ("error_decision_refused", "decision", "ERROR"),
                                       ("wrong_candidate_refused", "tic_id", 2)):
                altered = copy.deepcopy(a)
                altered[field] = value
                ap.write_text(json.dumps(altered))
                expect_rejection(name, "A", [job])
            ap.write_text(json.dumps(a))
            (root / "stageA" / "extra.json").write_text(json.dumps(a))
            expect_rejection("extra_A_record_refused", "A", [job])
            (root / "stageA" / "extra.json").unlink()
            sjob = dict(job, stageA_sample=True)
            s = {"key": key, "tic_id": 1, "rank": 1, "rules_version": "p8.0", "gate": "PASS",
                 "seconds": .1, "survey_period": 2.0, "survey_depth_ppt": 1.0,
                 "thresholds": C.F.R.thresholds(C.F.V.RULE_SET)["secondary"],
                 "stageA_sample": True, "stageA_decision": "FAIL"}
            sp = root / "secondary" / (key + ".json")
            sp.write_text(json.dumps(s))
            rows, _ = C.read_phase(root, "S", [sjob])
            checks["seeded_failure_fixture_accepted"] = rows[key]["stageA_sample"]
            s["stageA_sample"] = False
            sp.write_text(json.dumps(s))
            expect_rejection("wrong_failure_sample_refused", "S", [sjob])
        # A partial directory must stop before the inherited overwrite-capable runner.
        (root / "stageA" / (key + ".json")).unlink()
        with patch.object(C, "assert_free"), patch.object(C.Q, "assert_source"), \
                patch.object(C, "configure", return_value=(root, root / "measurement.json", {}, [job])), \
                patch.object(C.subprocess, "run") as launch:
            try:
                C.ensure_phase("a", "A", {})
            except RuntimeError as exc:
                checks["partial_workspace_no_launch"] = "Partial A workspace" in str(exc) and not launch.called
    expected = 10
    assert len(checks) == expected and all(checks.values()), checks
    out = C.Q.RECEIPTS / "false_alarm_funnel_guard_validation.json"
    result = {"utc": C.Q.utc(), "checks": checks, "all_pass": True,
              "scientific_workers_launched": 0, "fixture_scope": "Synthetic candidate identity only; no science computation",
              "controller_sha256": C.sha(Path(C.__file__))}
    with out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
