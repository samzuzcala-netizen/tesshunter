"""Fill only missing native raw arrays for the already-permitted 37 C records.

Inventory first; run unchanged p8.0 in new P10 roots, one eight-worker job at a
time. Existing complete spectra are validated and reused without invoking C.
Partial roots, changed evidence, unknown owners and locks require review.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

import resume_cadence as Q

os.environ.update(LIGHTKURVE_CACHE=str(Q.REPO / "data/cache/lightkurve"),
                  PYTHONIOENCODING="utf-8", TESSHUNTER_OFFLINE="1",
                  PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1",
                  MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
import numpy as np
import psutil

INVENTORY = Q.REPO / "p10/results/stage_c_native_raw_inventory.json"
MEASUREMENTS = Q.REPO / "p10/results/stage_c_native_raw_measurements.json"
STATE = Q.RECEIPTS / "native_raw_queue.json"
LOCK = Q.RECEIPTS / "native_raw_queue.lock"
FIELDS = ("time", "flux", "flux_err", "time_unbinned", "flux_unbinned", "sector_unbinned", "trend_unbinned")
ARRAYS = {"periods", "power", "chi2", "SR", "power_raw"}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_arrays(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def base_paths(root, key):
    return [root / name for name in ("candidates.csv", "survivors.csv")] + [
        root / sub / (key + suffix) for sub, suffix in (
            ("stageC", ".json"), ("prep", ".json"), ("tls", ".json"),
            ("tls", "_lc.npz"), ("tls", "_spectrum.npz"))]


def hashes(paths):
    return {str(p.relative_to(Q.REPO)): sha(p) for p in paths}


def verify_hashes(saved):
    for path, expected in saved.items():
        require(sha(Q.REPO / path) == expected, "Saved input changed: " + path)


def statistics(z):
    power = z["power"]; peak = int(np.argmax(power))
    centered = (power - np.mean(power)) ** 2
    require(np.sum(centered) > 0, "Degenerate installed spectrum")
    concentration = float(np.max(centered) / np.sum(centered))
    robust = None
    if "power_raw" in z:
        raw = z["power_raw"]; median = np.median(raw); mad = np.median(np.abs(raw - median))
        require(mad > 0, "Degenerate raw-power MAD")
        robust = float((raw[peak] - median) / (1.4826 * mad))
    return {"n_trials": len(power), "strongest_period": float(z["periods"][peak]),
            "installed_SDE": float(power[peak]), "installed_concentration": concentration,
            "fallback_triggered": concentration > .5, "raw_robust_at_installed_strongest": robust}


def validate(item, ws):
    key = item["key"]; native = (Q.REPO / item["native_record"]).parents[1]
    tag = ws.parent.name
    require(Q.complete(item["set"], tag, key), "Incomplete native record: " + key)
    old = Q.read(Q.REPO / item["native_record"])
    new = Q.read(ws / "stageC" / (key + ".json"))
    require(new["p10"]["cadence"] == "native", "Wrong cadence: " + key)
    require(new["survey_period"] == old["survey_period"] and new["survey_depth_ppt"] == old["survey_depth_ppt"], "Candidate changed")
    a, b = (load_arrays(root / "tls" / (key + "_spectrum.npz")) for root in (native, ws))
    require(set(b) == ARRAYS and all(v.shape == b["periods"].shape and np.isfinite(v).all() for v in b.values()), "Missing or invalid raw arrays")
    require(all(np.array_equal(a[f], b[f]) for f in ("periods", "power")), "Native installed spectrum does not reproduce exactly: " + key)
    lc_a, lc_b = (load_arrays(root / "tls" / (key + "_lc.npz")) for root in (native, ws))
    require(all(np.array_equal(lc_a[f], lc_b[f], equal_nan=True) for f in FIELDS), "Prepared input changed: " + key)
    prep_a, prep_b = (Q.read(root / "prep" / (key + ".json")) for root in (native, ws))
    require(prep_a["input_config"] == prep_b["input_config"] == new["p10"]["input_config"], "Input configuration changed")
    require(prep_a["bin_minutes"] is None and prep_b["bin_minutes"] is None, "Unexpected binning")
    if tag == "p8.0_native":
        require(new["rules_version"] == new["p10"]["rules"] == "p8.0", "Wrong reproduction rule")
        require(new["decision"] == old["decision"], "Original p8.0 decision differs")
        require("spectrum_fallback" not in new and "significant_peak" not in new, "Unexpected experimental rule")
    return {"utc": Q.utc(), "set": item["set"], "key": key,
            "workspace": str(ws.relative_to(Q.REPO)), "native_decision": old["decision"],
            "record_rules": new["rules_version"], "wall_s": new["p10"]["wall_s"],
            "checks": {name: True for name in ("all_five_finite_arrays", "native_grid_exact", "native_installed_power_exact",
                "all_seven_prepared_arrays_exact", "same_native_input_config", "same_candidate", "complete_positive_wall")},
            "statistics": statistics(b), "artifacts_sha256": hashes(base_paths(ws, key))}


def no_owners():
    require(not Q.tls_owners(), "An existing TLS job still owns the slot")
    for name in ("cadence_queue.lock", "residual_resume.lock"):
        require(not (Q.RECEIPTS / name).exists(), "Inspect existing queue lock: " + name)
    for proc in psutil.process_iter():
        try:
            if not proc.name().lower().startswith(("python", "bash")):
                continue
            args = proc.cmdline()
            require(args, "Cannot inspect command line: " + str(proc.pid))
            markers = ("resume_cadence.py", "resume_residuals.py", "p7_reproduce.py")
            require(not any(Path(a).name in markers for a in args), "Another TLS-capable queue is active: " + str(proc.pid))
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise RuntimeError("Process visibility insufficient for PID " + str(proc.pid)) from exc


def inventory():
    require(not INVENTORY.exists(), "Inventory exists; inspect it instead of replacing")
    Q.assert_source(); no_owners()
    rows = []
    for item in Q.manifest():
        key = item["key"]; native = (Q.REPO / item["native_record"]).parents[1]
        z = load_arrays(native / "tls" / (key + "_spectrum.npz"))
        found = []
        for spectrum in (Q.OUT / item["set"]).glob("*/" + key + "/tls/" + key + "_spectrum.npz"):
            ws = spectrum.parents[1]
            if ws.parent.name == "cadence_600s":
                continue
            found.append(validate(item, ws))
        require(len(found) <= 1, "Multiple native raw workspaces require explicit reconciliation: " + key)
        target = Q.OUT / item["set"] / "p8.0_native" / key
        require(found or not target.exists(), "Unexpected partial target: " + str(target))
        rows.append(dict(item, legacy_arrays=list(z), installed_statistics=statistics(z),
                         original_sha256=hashes(base_paths(native, key)), reused=found[0] if found else None,
                         new_workspace=None if found else str(target.relative_to(Q.REPO))))
    reused = sum(r["reused"] is not None for r in rows)
    require(len(rows) == 37 and reused == 8, "Unexpected initial native raw inventory")
    result = {"utc": Q.utc(), "n": 37, "reused": reused, "missing": 37-reused,
              "scope": "Only the existing 19 P8 and 18 post-lock P9 C records permitted by Part 2c; no new candidate or held-out evaluation.",
              "reason": "The frozen raw-power statistic cannot be computed from legacy installed-power arrays. Reuse eight exact reproductions; save the missing 29 in new P10 roots.",
              "execution": {"rules": "p8.0", "cadence": "native", "threads": 8, "concurrent_TLS_jobs": 1,
                            "originals_read_only": True, "thresholds_changed": False},
              "source_sha256": sha(Path(__file__)), "rows": rows}
    with INVENTORY.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


def run():
    os.chdir(Q.REPO)
    inv = Q.read(INVENTORY)
    require(inv["n"] == 37 and inv["reused"] == 8 and inv["missing"] == 29, "Inventory mismatch")
    Q.assert_source(); no_owners()
    validations = []
    # Verify originals and reused raw arrays before taking ownership of any output.
    for item in inv["rows"]:
        verify_hashes(item["original_sha256"])
        if item["reused"]:
            verify_hashes(item["reused"]["artifacts_sha256"])
            validations.append(item["reused"])
    with LOCK.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "created": psutil.Process().create_time()}))
    state = {"utc": Q.utc(), "pid": os.getpid(), "status": "starting", "threads": 8,
             "n_expected": 37, "n_reused": 8, "inventory_sha256": sha(INVENTORY)}
    def save():
        Q.write(STATE, dict(state, n_validated=len(validations)))
        Q.write(MEASUREMENTS, {"utc": Q.utc(), "n_expected": 37, "n_validated": len(validations),
                "complete": len(validations) == 37, "adoption": "pending separate rule and control validation",
                "inventory_sha256": sha(INVENTORY), "rows": validations})
    try:
        save()
        for item in inv["rows"]:
            if item["reused"]:
                print(Q.utc(), "reuse", item["key"], flush=True)
                continue
            key = item["key"]; ws = Q.REPO / item["new_workspace"]
            Q.assert_source(); no_owners(); verify_hashes(item["original_sha256"])
            if ws.exists():
                result = validate(item, ws)  # A partial workspace fails closed; no cache-hit C call.
                print(Q.utc(), "reuse previously completed", key, flush=True)
            else:
                command = [str(Q.PY), "scripts/p10_stage_c.py", "run", "--set", item["set"],
                           "--keys", key, "--rules", "p8.0", "--cadence", "native", "--threads", "8"]
                state.update(utc=Q.utc(), status="running", active_key=key, command=command)
                save(); print(Q.utc(), "start", key, flush=True)
                log = Q.REPO / "p10/logs" / ("raw_native_" + key + ".log")
                with log.open("x", encoding="utf-8") as stream:
                    stream.write(Q.utc() + " " + " ".join(command) + "\n"); stream.flush()
                    code = subprocess.run(command, cwd=Q.REPO, stdout=stream, stderr=subprocess.STDOUT).returncode
                require(code == 0, "Native raw replay failed: " + key)
                no_owners(); result = validate(item, ws)
                verify_hashes(item["original_sha256"])
                print(Q.utc(), "complete and exact", key, result["wall_s"], "s", flush=True)
            validations.append(result); save()
        require(len(validations) == 37, "Incomplete raw-spectrum census")
        state.update(utc=Q.utc(), status="validated_spectra_complete_review_required", active_key=None)
        save(); print(Q.utc(), "NATIVE_RAW_37_COMPLETE=1; controls and adoption still pending", flush=True)
    except BaseException as exc:
        state.update(utc=Q.utc(), status="needs_review", error=str(exc))
        save(); raise
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "run"))
    arguments = parser.parse_args()
    inventory() if arguments.command == "inventory" else run()
