"""Complete P10's existing FA funnels only after all four search variants settle.

One 16-slice A or S phase at a time, with the inherited p8.0/bound rules.
Inspect never launches workers. Run refuses unknown owners and partial outputs;
completed phases are validated and reused without refreshing their timings.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys

import psutil
import resume_cadence as Q
import queue_fourth_variant as SEARCH

os.environ.update(LIGHTKURVE_CACHE=str(Q.REPO / "data/cache/lightkurve"),
                  PYTHONIOENCODING="utf-8", TESSHUNTER_OFFLINE="1",
                  PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1",
                  MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
sys.path.insert(0, str(Q.REPO / "scripts"))
import p8_funnel as F

BASE = Q.REPO / "data/survey/p10/fa_2b"
STATE = Q.RECEIPTS / "false_alarm_funnel_queue.json"
LOCK = Q.RECEIPTS / "false_alarm_funnel_queue.lock"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_hashes(mapping):
    for name, digest in mapping.items():
        require(sha(Q.REPO / name) == digest, "Saved input changed: " + name)


def configure(variant):
    require(variant in "abcde" and len(variant) == 1, "Unknown variant")
    root = BASE / variant
    measurement = Q.REPO / "p10/results" / ("search_false_alarms_" + variant + ".json")
    require(measurement.is_file(), "Complete search measurement required: " + variant)
    data = Q.read(measurement)
    require(data["variant"] == variant and data["summary"]["n_fa_stars"] == 300
            and data["summary"]["n_injections"] == 600, "Wrong paired measurement")
    require((Q.REPO / data["funnel_root"]).resolve() == root.resolve(), "Wrong funnel root")
    verify_hashes(data["inputs"])
    F.set_root(root)
    F.set_rules("p8.0")
    require(F.V.RULE_SET.secondary_gate == "bound", "Part 2a retained bound")
    require(F.SECONDARY_FAIL_SAMPLE_SEED == 20260904
            and F.SECONDARY_FAIL_SAMPLE_FRACTION == .10, "Secondary sample changed")
    jobs = F.V.jobs()
    keys = [F.V.kkey(j["tic_id"], j["period"]) for j in jobs]
    require(len(keys) == len(set(keys)) == data["summary"]["n_pregate_candidates"],
            "Missing, extra or colliding pre-gate candidates")
    require(all(F.V.have_lc(j["tic_id"]) for j in jobs), "Missing native light-curve index")
    return root, measurement, data, jobs


def read_phase(root, stage, jobs):
    folder, field = ("stageA", "decision") if stage == "A" else ("secondary", "gate")
    expected = {F.V.kkey(j["tic_id"], j["period"]): j for j in jobs}
    paths = list((root / folder).glob("*.json"))
    require({p.stem for p in paths} == set(expected), "Incomplete/extra " + folder + " records")
    records = {}
    for path in paths:
        rec = Q.read(path)
        job = expected[path.stem]
        require(rec.get("key") == path.stem and rec.get("tic_id") == job["tic_id"]
                and rec.get("rank") == job["rank"] and rec.get("rules_version") == "p8.0",
                "Mixed identity/rules: " + str(path))
        require(rec.get(field) in ("PASS", "FAIL"), "Unsettled or unexpected bound decision: " + str(path))
        require(math.isfinite(float(rec.get("seconds", -1))) and rec["seconds"] >= 0,
                "Missing execution timing: " + str(path))
        if stage == "A":
            require(rec.get("survey") == {k: job[k] for k in (
                "period", "epoch_btjd", "duration_days", "depth_ppt", "stitch_snr",
                "stitch_n_transits", "n_units", "tmag")}, "Candidate changed: " + str(path))
            require(rec.get("thresholds") == F.V.THRESHOLDS["stageA"], "Stage A thresholds changed")
            for sub, suffix in (("prep", ".json"), ("tls", "_lc.npz")):
                require((root / sub / (path.stem + suffix)).is_file(), "Missing prepared A artifact")
        else:
            require(rec.get("survey_period") == job["period"]
                    and rec.get("survey_depth_ppt") == job["depth_ppt"], "Secondary candidate changed")
            require(rec.get("thresholds") == F.R.thresholds(F.V.RULE_SET)["secondary"],
                    "Secondary thresholds changed")
            require(rec.get("stageA_sample") is job["stageA_sample"], "Wrong seeded failure sample")
            require(rec.get("stageA_decision") == ("FAIL" if job["stageA_sample"] else "PASS"),
                    "Secondary is attached to the wrong A decision")
        records[path.stem] = rec
    return records, {str(p.relative_to(Q.REPO)): sha(p) for p in paths}


def assert_free():
    require(not SEARCH.owners(), "The 16-worker search allocation is still owned")
    require(not (Q.RECEIPTS / "fourth_variant_queue.lock").exists(), "Fourth search queue is not closed")
    for process in psutil.process_iter():
        try:
            if not process.name().lower().startswith(("python", "bash", "pwsh", "powershell")):
                continue
            args = process.cmdline()
            require(args, "Cannot inspect command line: " + str(process.pid))
            markers = {"queue_fourth_variant.py", "p8_funnel.py", "p8_completeness.py",
                       "p10_secondary_modes.py", "p7_reproduce.py"}
            require(not any(Path(a).name in markers for a in args),
                    "Another A/S-capable job or search waiter is active: " + str(process.pid))
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise RuntimeError("Process visibility insufficient: " + str(process.pid)) from exc


def ensure_phase(variant, stage, state):
    Q.assert_source()
    assert_free()
    root, measurement, data, all_jobs = configure(variant)
    jobs = all_jobs if stage == "A" else F.secondary_jobs()
    if stage == "S":
        read_phase(root, "A", all_jobs)
    folder = root / ("stageA" if stage == "A" else "secondary")
    existing = list(folder.glob("*.json"))
    phase_receipt = Q.RECEIPTS / ("fa_" + variant + "_" + stage + "_validation.json")
    if existing or phase_receipt.exists():
        records, hashes = read_phase(root, stage, jobs)
        if phase_receipt.exists():
            saved = Q.read(phase_receipt)
            require(saved["record_sha256"] == hashes, "Completed phase changed")
            verify_hashes(saved["record_sha256"])
            return saved
    else:
        # The inherited driver opens slice logs with 'w'; never erase an earlier attempt.
        if stage == "A":
            require({p.name for p in root.iterdir()} == {"candidates.csv", "survivors.csv", "collect_p8.json"},
                    "Partial A workspace requires an owner/artifact review: " + variant)
        else:
            require(not folder.exists() and not (root / "secondary.csv").exists()
                    and not list((root / "logs").glob("stageS_slice*.log")),
                    "Partial secondary workspace requires review: " + variant)
        log = Q.REPO / "p10/logs" / ("false_alarm_" + variant + "_" + stage + ".log")
        command = [str(Q.PY), "scripts/p8_funnel.py", "--root", str(root), "--rules", "p8.0",
                   "stageA" if stage == "A" else "secondary", "--slices", "16", "--threads", "1"]
        state.update(utc=Q.utc(), status="running", variant=variant, stage=stage,
                     expected=len(jobs), command=command, log=str(log.relative_to(Q.REPO)))
        Q.write(STATE, state)
        print(Q.utc(), "start", variant, stage, len(jobs), flush=True)
        with log.open("x", encoding="utf-8") as stream:
            code = subprocess.run(command, cwd=Q.REPO, stdout=stream, stderr=subprocess.STDOUT).returncode
        require(code == 0, "Funnel driver failed: " + variant + " " + stage)
        assert_free()
        Q.assert_source()
        configure(variant)
        records, hashes = read_phase(root, stage, jobs)
    result = {"utc": Q.utc(), "variant": variant, "stage": stage, "rules": "p8.0",
              "secondary_mode": "bound", "n_expected": len(jobs), "n_complete": len(records),
              "decisions": dict(Counter(r["decision" if stage == "A" else "gate"] for r in records.values())),
              "measurement_sha256": sha(measurement), "record_sha256": hashes,
              "checks": {k: True for k in ("complete_expected_ids", "identity_and_rules",
                  "unchanged_thresholds", "settled_decisions", "preserved_search_inputs", "no_live_phase_owner")}}
    with phase_receipt.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(Q.utc(), "validated", variant, stage, result["decisions"], flush=True)
    return result


def summarize(variant):
    root, measurement, data, jobs = configure(variant)
    a, a_hashes = read_phase(root, "A", jobs)
    s, s_hashes = read_phase(root, "S", F.secondary_jobs())
    kept = sorted(k for k in a if a[k]["decision"] == "PASS" and s[k]["gate"] == "PASS")
    # bound has no HOLD outcome. The separate failure sample never contributes to FA_S.
    result = {"utc": Q.utc(), "variant": variant, "rules": "p8.0", "secondary_mode": "bound",
              "n_fa_stars": 300, "n_pregate": len(jobs), "FA_pre": data["summary"]["FA_pre"],
              "n_A_pass": sum(r["decision"] == "PASS" for r in a.values()),
              "n_secondary_total": len(s), "n_secondary_failure_sample": sum(r["stageA_sample"] for r in s.values()),
              "FA_S_count": len(kept), "FA_S": len(kept) / 300, "FA_S_keys": kept,
              "scope": "All 300 original FA stars; through pre-gate, A and bound S; no B/C execution or final adoption.",
              "measurement_sha256": sha(measurement), "record_sha256": dict(a_hashes, **s_hashes)}
    path = Q.REPO / "p10/results" / ("search_false_alarm_secondary_" + variant + ".json")
    if path.exists():
        saved = Q.read(path)
        require(all(saved[k] == value for k, value in result.items() if k != "utc"), "Existing FA_S measurement differs")
        return saved
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "run"))
    parser.add_argument("--variants", default="a,b,c,e")
    args = parser.parse_args()
    os.chdir(Q.REPO)
    variants = args.variants.split(",")
    require(len(variants) == len(set(variants)), "Repeated variant")
    Q.assert_source()
    if args.command == "inspect":
        result = []
        for variant in variants:
            root, measurement, data, jobs = configure(variant)
            result.append({"variant": variant, "n_pre": len(jobs), "input_hashes_verified": True,
                           "root": str(root.relative_to(Q.REPO)), "stageA_records": len(list((root / "stageA").glob("*.json"))),
                           "secondary_records": len(list((root / "secondary").glob("*.json")))})
        print(json.dumps({"read_only_inspection": True, "variants": result}, indent=2))
        return
    assert_free()
    fourth = Q.read(Q.RECEIPTS / "fourth_variant_queue.json")
    require(fourth["status"] == "search_measurements_complete_review_required", "Fourth search queue incomplete")
    require(variants == ["a", "b", "c", fourth["selected"]], "Requires all registered variants, in order")
    for variant in variants:
        for kind in ("inj", "fa"):
            SEARCH.complete(variant, kind)
        configure(variant)
    with LOCK.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "created": psutil.Process().create_time()}))
    state = {"utc": Q.utc(), "pid": os.getpid(), "status": "validated_inputs", "variants": variants,
             "slices": 16, "threads_per_slice": 1, "rules": "p8.0", "secondary_mode": "bound"}
    Q.write(STATE, state)
    try:
        for variant in variants:
            for stage in ("A", "S"):
                ensure_phase(variant, stage, state)
            measurement = summarize(variant)
            print(Q.utc(), "FA_S", variant, measurement["FA_S_count"], "/ 300", flush=True)
        state.update(utc=Q.utc(), status="FA_S_complete_review_required", variant=None, stage=None)
        Q.write(STATE, state)
        print("FOUR_VARIANT_FA_S_COMPLETE=1; final comparison/adoption still required", flush=True)
    except BaseException as exc:
        state.update(utc=Q.utc(), status="needs_review", error=str(exc))
        Q.write(STATE, state)
        raise
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
