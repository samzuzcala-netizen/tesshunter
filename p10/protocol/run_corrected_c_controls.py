"""Guarded native C execution on the frozen 30 injections and 41 EB candidates.

prepare freezes execution inputs without TLS; inspect is read-only; run reuses
verified completed cases and launches one eight-worker case at a time. Partial
roots and unknown owners stop the queue for review, never trigger an overwrite.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
os.environ.update(LIGHTKURVE_CACHE=str(ROOT / "data/cache/lightkurve"),
                  PYTHONIOENCODING="utf-8", TESSHUNTER_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1",
                  OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import numpy as np
import psutil
import p10_stage_c as T
from tesshunter import stage_c as C

RESULTS = ROOT / "p10/results"
MANIFEST = RESULTS / "stage_c_corrected_control_manifest.json"
STATE = RESULTS / "takeover_20260908/corrected_c_control_queue.json"
LOCK = STATE.with_suffix(".lock")
RECEIPTS = RESULTS / "corrected_c_controls"
THREADS = 8
FROZEN_SHA = "01bd29efc1b4b57eb6fcc99f340f515c0c2cae2e0162a2e9f96beef92b678f19"


def utc():
    return datetime.now(timezone.utc).isoformat()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def write_state(obj):
    temporary = STATE.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(dict(obj, utc=utc()), indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATE)


def verify_hashes(mapping):
    for name, digest in mapping.items():
        require(sha(ROOT / name) == digest, "Frozen input/source changed: " + name)


def owners():
    own_family = {os.getpid()} | {p.pid for p in psutil.Process().parents()}
    markers = {Path(__file__).name, "p10_stage_c.py", "native_raw_spectra.py", "resume_cadence.py",
               "resume_residuals.py", "run_false_alarm_funnels.py", "queue_fourth_variant.py",
               "p8_funnel.py", "p8_completeness.py", "p7_reproduce.py", "run_survey.py",
               "p10_search_capacity.py", "p10_secondary_modes.py"}
    found = []
    for process in psutil.process_iter():
        try:
            if not process.name().lower().startswith(("python", "py.exe", "bash", "powershell", "pwsh")):
                continue
            args = process.cmdline()
            require(args, "Process command line unavailable: " + str(process.pid))
            if any(Path(arg).name in markers for arg in args) and process.pid not in own_family:
                found.append({"pid": process.pid, "ppid": process.ppid(), "created": process.create_time(), "command": args})
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise RuntimeError("Process visibility insufficient for PID " + str(process.pid)) from exc
    return found


def closed_prior_queues():
    require(not owners(), "A scientific job/controller still owns the resource allocation")
    for name in ("native_raw_queue", "false_alarm_funnel_queue", "cadence_queue", "residual_resume", "fourth_variant_queue"):
        require(not (STATE.parent / (name + ".lock")).exists(), "Prior queue lock needs review: " + name)


def load_manifest():
    data = read(MANIFEST)
    require(data["n_injections"] == 30 and data["n_adversarial_candidates"] == 41
            and len(data["items"]) == len({r["id"] for r in data["items"]}) == 71, "Wrong frozen control census")
    require(data["threads"] == THREADS and data["cadence"] == "native"
            and data["implementation"] == C.IMPLEMENTATION and data["rule_options"] == T.rules_for("p10c").options,
            "Execution conditions changed")
    verify_hashes(data["source_sha256"])
    verify_hashes(data["input_sha256"])
    frozen = (ROOT / "HANDOFF_P10.md").read_bytes().split(b"## 0. Pre-registered decision rules", 1)[1].split(b"## 1. Part 0: housekeeping", 1)[0]
    require(hashlib.sha256(frozen).hexdigest() == FROZEN_SHA, "Frozen preregistration changed")
    return data


def prepare():
    require(not MANIFEST.exists() and not LOCK.exists(), "Existing manifest/lock must be reused or reviewed")
    closed_prior_queues()
    sample_path = RESULTS / "stage_c_injection_sample.json"
    validated_path = RESULTS / "stage_c_injection_sample_validation.json"
    adv_path = RESULTS / "stage_c_adversarial_input_inventory.json"
    sample, validated, adv = (read(p) for p in (sample_path, validated_path, adv_path))
    require(sha(sample_path) == validated["sample_sha256"] == "dd2a7e1e58c3fcc9f673211286913cf5f376cb3cc64361ca721cf6e4ae31fc91",
            "Frozen sample hash differs")
    require(sample["n"] == 30 and sample["cadence"] == "native" and sample["n_per_bin"] == 10
            and all(validated["checks"].values()), "Native sample validation incomplete")
    require([r["job_id"] for r in sample["jobs"]] == [r["job_id"] for r in validated["rows"]], "Sample identities/order changed")
    input_hashes = {}
    # Historical source hashes stay in their original receipts. Check all data
    # inputs here; the corrected executable source is separately frozen below.
    for receipt in (validated, adv):
        saved = {p: h for p, h in receipt["inputs_sha256"].items()
                 if p.replace("\\", "/").startswith(("data/", "p9/inputs/", "p10/results/"))}
        verify_hashes(saved); input_hashes.update(saved)
    items = []
    for row in validated["rows"]:
        job = row["funnel_job"]
        rec = {"key": row["key"], "tic_id": int(job["tic_id"]), "period": row["search_period"],
               "depth_ppt": row["search_depth_ppt"], "source_root": str(ROOT / row["source_root"]),
               "lc_root": str(T.LC_ROOT), "stellar": "cache", "job_id": row["job_id"],
               "snr_expected": row["snr_expected"], "bin": row["bin"]}
        items.append({"id": row["job_id"], "set": "inj", "tag": "injc_corrected_native", "record": rec,
                      "injection": job, "injection_model": row["injection_model"]})
    for rec in T.adv_tables():
        items.append({"id": rec["candidate_id"], "set": "adv", "tag": "adv_corrected_native", "record": rec,
                      "injection": None})
    for item in items:
        rec = item["record"]
        ws = T.OUT / item["set"] / item["tag"] / rec.get("workspace_id", rec["key"])
        require(not ws.exists(), "Existing unowned/partial control workspace needs review: " + str(ws))
        item["workspace"] = str(ws.relative_to(ROOT))
        for name in ("candidates.csv", "survivors.csv"):
            path = Path(rec["source_root"]) / name
            input_hashes[str(path.relative_to(ROOT))] = sha(path)
        index = Path(rec["lc_root"]) / f"tic{rec['tic_id']}" / "index.json"
        input_hashes[str(index.relative_to(ROOT))] = sha(index)
    require(len(items) == 71 and len({r["workspace"] for r in items}) == 71, "Candidate workspaces collide")
    for path in (sample_path, validated_path, adv_path):
        input_hashes[str(path.relative_to(ROOT))] = sha(path)
    source_paths = subprocess.check_output(["git", "ls-files", "src", "scripts", "configs", "pyproject.toml", "requirements.txt", "PROMPT_P10.md"], cwd=ROOT, text=True).splitlines()
    source_paths.append(str(Path(__file__).relative_to(ROOT)))
    result = {"utc": utc(), "n_injections": 30, "n_adversarial_hosts": 18, "n_adversarial_candidates": 41,
              "cadence": "native", "threads": THREADS, "concurrent_TLS_jobs": 1,
              "implementation": C.IMPLEMENTATION, "rule_options": T.rules_for("p10c").options,
              "scope": "Paired C(a)/(b), with/without candidate robust fallback. All 41 audited survey candidates are retained; no catalogue ephemerides enter TLS.",
              "source_sha256": {p: sha(ROOT / p) for p in source_paths}, "input_sha256": input_hashes,
              "items": items}
    write_new(MANIFEST, result)
    load_manifest()
    print("Frozen 71 cases: 30 original seeded injections, 41 original survey candidates; no TLS launched", flush=True)


def validate_case(item):
    rec = item["record"]; key = rec["key"]; ws = ROOT / item["workspace"]
    path = ws / "stageC" / (key + ".json")
    require(path.is_file(), "No settled C record: " + item["id"])
    result = read(path); meta = result.get("p10") or {}
    require(result.get("decision") in ("PASS", "FAIL") and result.get("decision_strongest") in ("PASS", "FAIL")
            and result.get("decision_strongest_installed") in ("PASS", "FAIL")
            and result.get("decision_significant_installed") in ("PASS", "FAIL"), "Incomplete paired C decisions")
    require(result.get("stagec_implementation") == C.IMPLEMENTATION
            and result.get("stagec_rule_options") == T.rules_for("p10c").options
            and result["rules_version"] == T.rules_for("p10c").version, "Wrong C implementation/rules")
    require(meta.get("workspace") == item["workspace"] and meta.get("cadence") == "native"
            and meta.get("rules") == "p10c" and np.isfinite(meta["wall_s"]) and meta["wall_s"] > 0,
            "Wrong workspace/cadence or missing original timing")
    require(result["tic_id"] == rec["tic_id"] and result["survey_period"] == rec["period"]
            and result["survey_depth_ppt"] == rec["depth_ppt"], "Candidate changed")
    tls = read(ws / "tls" / (key + ".json")); prep = read(ws / "prep" / (key + ".json"))
    require(prep["bin_minutes"] is None and prep["input_config"] == meta["input_config"]
            == result["input_config"] == tls["input_config"], "Unpaired native input configuration")
    with np.load(ws / "tls" / (key + "_lc.npz"), allow_pickle=False) as z:
        cadence_s = float(np.median(np.diff(np.sort(z["time"])))) * 86400
        if item["set"] == "inj":
            old_lc = Path(rec["source_root"]) / "tls" / (key + "_lc.npz")
            with np.load(old_lc, allow_pickle=False) as old:
                require(all(np.array_equal(z[f], old[f], equal_nan=True) for f in
                            ("time", "flux", "flux_err", "time_unbinned", "flux_unbinned", "sector_unbinned", "trend_unbinned")),
                        "Injected prepared arrays differ from the original S-passing input")
    for field in ("blind", "forced"):
        b = tls[field]; floor = C.floor_duration(b["duration_raw_days"], cadence_s)
        require(b["duration_days"] == floor["floored_days"] and b["duration_floor"] == floor, "Duration floor not applied")
    spectrum_paths = sorted((ws / "tls").glob("*_spectrum.npz"))
    require(any(p.name == key + "_spectrum.npz" for p in spectrum_paths), "Missing blind raw spectrum")
    for spectrum in spectrum_paths:
        with np.load(spectrum, allow_pickle=False) as z:
            require(set(z.files) == {"periods", "power", "chi2", "SR", "power_raw"}
                    and all(z[f].shape == z["periods"].shape and np.isfinite(z[f]).all() for f in z.files),
                    "Incomplete/nonfinite raw spectrum: " + str(spectrum))
    files = sorted(p for p in ws.rglob("*") if p.is_file())
    return {"id": item["id"], "set": item["set"], "workspace": item["workspace"], "key": key,
            "a_installed": result["decision_strongest_installed"], "a_with_fallback": result["decision_strongest"],
            "b_installed": result["decision_significant_installed"], "b_with_fallback": result["decision"],
            "fallback": result["spectrum_fallback"], "wall_s": meta["wall_s"], "n_spectra": len(spectrum_paths),
            "bin": rec.get("bin"), "snr_expected": rec.get("snr_expected"),
            "checks": {k: True for k in ("settled_paired_decisions", "frozen_rule_options", "exact_candidate",
                      "native_input_config", "raw_arrays_saved", "duration_floor_at_consumers", "original_injected_arrays_if_applicable")},
            "artifact_sha256": {str(p.relative_to(ROOT)): sha(p) for p in files}}


def run_case(identifier):
    manifest = load_manifest()
    require(LOCK.exists(), "A case requires the guarded queue's live lock")
    lock = read(LOCK)
    require(lock["pid"] in {p.pid for p in psutil.Process().parents()}, "Queue owner is not this case's parent")
    item = next(r for r in manifest["items"] if r["id"] == identifier)
    require(not (ROOT / item["workspace"]).exists(), "Partial/existing case needs review")
    result = T.run_c(item["set"], item["record"], "p10c", "native", THREADS, False,
                     injection=item["injection"], tag=item["tag"])
    require(result.get("decision") in ("PASS", "FAIL"), "C did not settle: " + str(result.get("reason")))
    print("CASE_DONE", identifier, result["decision_strongest"], result["decision"], result["p10"]["wall_s"], flush=True)


def run_queue():
    manifest = load_manifest(); closed_prior_queues()
    require(not LOCK.exists(), "Existing queue lock needs ownership review")
    write_new(LOCK, {"pid": os.getpid(), "created": psutil.Process().create_time(), "utc": utc(), "manifest_sha256": sha(MANIFEST)})
    state = {"pid": os.getpid(), "status": "validating", "n_expected": 71, "n_complete": 0,
             "active_id": None, "threads": THREADS, "manifest_sha256": sha(MANIFEST)}
    try:
        for item in manifest["items"]:
            closed_prior_queues(); load_manifest()
            receipt_path = RECEIPTS / (item["id"] + ".json")
            if receipt_path.exists():
                saved = read(receipt_path); current = validate_case(item)
                require(all(saved[k] == v for k, v in current.items()), "Completed control changed")
            else:
                require(not (ROOT / item["workspace"]).exists(), "Partial control root needs review: " + item["id"])
                log = ROOT / "p10/logs" / ("corrected_c_" + item["id"] + ".log")
                require(not log.exists(), "Prior case log needs review: " + item["id"])
                command = [sys.executable, "-B", str(Path(__file__)), "case", "--id", item["id"]]
                state.update(status="running", active_id=item["id"], workspace=item["workspace"], command=command,
                             log=str(log.relative_to(ROOT)))
                write_state(state)
                print(utc(), "START", item["id"], flush=True)
                with log.open("x", encoding="utf-8") as stream:
                    code = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT).returncode
                require(code == 0, "Control case failed; preserve its workspace/log for review: " + item["id"])
                closed_prior_queues(); load_manifest()
                current = validate_case(item)
                write_new(receipt_path, dict(current, utc=utc(), log_sha256=sha(log)))
            state["n_complete"] += 1
            state.update(status="validated", active_id=None); write_state(state)
            print(utc(), "VALIDATED", item["id"], state["n_complete"], flush=True)
        state.update(status="controls_complete_review_required", active_id=None); write_state(state)
        print("CORRECTED_C_CONTROLS_COMPLETE=1", flush=True)
    except Exception as exc:
        state.update(status="stopped_review_required", error=f"{type(exc).__name__}: {exc}"); write_state(state)
        raise
    finally:
        # Never remove a different owner's lock; no process termination is used.
        if LOCK.exists() and read(LOCK).get("pid") == os.getpid():
            LOCK.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "inspect", "run", "case"))
    parser.add_argument("--id")
    args = parser.parse_args(); os.chdir(ROOT)
    if args.command == "prepare":
        prepare()
    elif args.command == "inspect":
        manifest = load_manifest()
        print(json.dumps({"utc": utc(), "manifest_sha256": sha(MANIFEST), "n": len(manifest["items"]),
                          "lock": read(LOCK) if LOCK.exists() else None, "state": read(STATE) if STATE.exists() else None,
                          "owners": owners(), "completed_receipts": len(list(RECEIPTS.glob("*.json")))}, indent=2))
    elif args.command == "case":
        require(args.id, "Case id required"); run_case(args.id)
    else:
        run_queue()


if __name__ == "__main__":
    main()
