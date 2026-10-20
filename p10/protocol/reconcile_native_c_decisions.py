"""Evaluate corrected C rules using only the 37 validated native spectra.

Reuses measured stronger-peak ephemerides and residual spectra, checking their
duration floor, coverage and masks. Never executes TLS or writes old records.
Pending measurements remain explicit; this is not final C adoption.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
os.environ.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", TESSHUNTER_OFFLINE="1",
                  OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
import numpy as np
import audit_p5 as A
import revet_p6 as V
from tesshunter import stage_c as C


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def main():
    output = ROOT / "p10/results/stage_c_native_corrected_20260910.json"
    require(not output.exists(), "Existing corrected measurement must be preserved")
    measurement = ROOT / "p10/results/stage_c_native_raw_measurements.json"
    data = read(measurement)
    require(data["complete"] and data["n_validated"] == data["n_expected"] == 37, "Raw census incomplete")
    hashes = {str(measurement.relative_to(ROOT)): sha(measurement)}
    rows = []
    for item in data["rows"]:
        for name, digest in item["artifacts_sha256"].items():
            require(sha(ROOT / name) == digest, "Changed validated native artifact: " + name)
        hashes.update(item["artifacts_sha256"])
        key = item["key"]; ws = ROOT / item["workspace"]
        saved = read(ws / "stageC" / (key + ".json"))
        tls = read(ws / "tls" / (key + ".json")); blind = tls["blind"]
        period = saved["survey_period"]
        with np.load(ws / "tls" / (key + "_spectrum.npz"), allow_pickle=False) as z:
            p, w = z["periods"], z["power"]
        with np.load(ws / "tls" / (key + "_lc.npz"), allow_pickle=False) as z:
            times = z["time"]
        cadence_s = float(np.median(np.diff(np.sort(times)))) * 86400
        local = C.local_peak(p, w, period)
        strongest = {"period": blind["period"], "SDE": blind["SDE"], "index": int(np.argmax(w))}
        fb = V.spectrum_fallback(SimpleNamespace(OUT=ws), saved["tic_id"], period)
        peaks = A._peak_table(p, w, n=len(p), min_power=local["sde"]) if local["sde"] is not None else []
        consistency = V.alias_depths_consistent(blind)
        adc = {f"{blind['period']:.6f}": consistency["consistent"]}
        transits, residuals, evidence = {}, {}, []
        for run in (saved.get("significant_peak") or {}).get("runs", []):
            peak = run["period"]; peak_key = f"{peak:.6f}"
            floor = C.floor_duration(run["duration_days"], cadence_s)
            duration = floor["floored_days"]
            require(duration == run["duration_used_days"], "Inherited mask duration differs from the floor")
            count = C.covered_transits(times, peak, run["t0"], duration, cadence_days=cadence_s/86400) if run["t0"] is not None else 0
            require(count == run["covered_transits"], "Inherited covered-transit count differs: " + key)
            transits[peak_key] = count
            row = {"period": peak, "duration_floor": floor, "covered_transits": count,
                   "inherited_ephemeris_source": run["ephemeris_source"]}
            if run.get("residual_suffix"):
                require(count >= 3, "Unexpected residual with fewer than three covered transits")
                base = ws / "tls" / (key + run["residual_suffix"])
                # Keys contain decimal periods; append extensions to keep them intact.
                path = Path(str(base) + ".json")
                spectrum = Path(str(base) + "_spectrum.npz")
                record = read(path)
                mask = A.transit_mask(times, peak, run["t0"], duration, n_durations=1.0)
                require(int(mask.sum()) == run["n_cadences_masked"] == record["blind"]["residual_mask"]["n_cadences_masked"],
                        "Saved residual mask differs: " + key)
                with np.load(spectrum, allow_pickle=False) as z:
                    require(set(z.files) == {"periods", "power", "chi2", "SR", "power_raw"}
                            and all(np.isfinite(z[f]).all() and z[f].shape == p.shape for f in z.files)
                            and np.array_equal(z["periods"], p), "Residual grid/raw spectrum differs")
                    residuals[peak_key] = C.local_peak(z["periods"], z["power"], period)
                require(residuals[peak_key] == run["residual_local"], "Saved residual local maximum differs")
                row.update(residual_local=residuals[peak_key], n_cadences_masked=int(mask.sum()))
                hashes.update({str(x.relative_to(ROOT)): sha(x) for x in (path, spectrum)})
            evidence.append(row)
        b0 = C.significant_peak(period, strongest, peaks, local, transits, residuals, adc)
        b1 = C.significant_peak(period, strongest, peaks, local, transits, residuals, adc, fb)
        match = blind["match"]
        period_ok = match["same_period_1pct"] or (match["alias_1pct"] and match["closest_alias"] in ("2:1", "1:2")
                                                          and consistency["consistent"])
        a0 = "PASS" if period_ok and blind["SDE"] >= 9 else "FAIL"
        a1 = "PASS" if period_ok and (blind["SDE"] >= 9 or fb["passes_on_robust"]) else "FAIL"
        require(a0 == item["native_decision"], "Unchanged strongest rule does not reproduce original: " + key)
        rows.append({"set": item["set"], "key": key, "workspace": item["workspace"],
                     "original_decision": item["native_decision"], "a_installed": a0, "a_with_fallback": a1,
                     "b_installed": b0, "b_with_fallback": b1, "fallback": fb,
                     "blind_duration_floor": C.floor_duration(blind["duration_days"], cadence_s),
                     "forced_duration_floor": C.floor_duration(tls["forced"]["duration_days"], cadence_s),
                     "all_stronger_distinct_peaks": peaks, "reused_measurements": evidence,
                     "inherited_wall_s_preserved": item["wall_s"], "new_TLS_runs": 0})
        print(key, a0, a1, b0["decision"], b1["decision"], flush=True)
    for path in (Path(__file__), ROOT / "src/tesshunter/stage_c.py", ROOT / "scripts/audit_p5.py", ROOT / "scripts/revet_p6.py"):
        hashes[str(path.relative_to(ROOT))] = sha(path)
    result = {"utc": datetime.now(timezone.utc).isoformat(), "n": 37, "implementation": C.IMPLEMENTATION,
              "scope": "Corrected native development decisions only. Injection/adversarial controls and fallback withdrawal/adoption still pending.",
              "all_original_strongest_decisions_reproduced": True,
              "fallback_trigger_count": sum(r["fallback"]["triggered"] for r in rows),
              "counts": {f: dict(Counter(r[f] if isinstance(r[f], str) else r[f]["decision"] for r in rows))
                         for f in ("a_installed", "a_with_fallback", "b_installed", "b_with_fallback")},
              "pending": [r["key"] for r in rows if r["b_with_fallback"]["decision"] not in ("PASS", "FAIL")],
              "new_TLS_runs": 0, "input_sha256": hashes, "rows": rows}
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("input_sha256", "rows")}, indent=2))


if __name__ == "__main__":
    main()
