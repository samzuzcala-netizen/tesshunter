"""Validate settled P8 native P10 case artifacts without running TLS or adopting C.

Uses the inherited spectrum/coverage functions and saved logs. Requires no live
owner for the selected workspace; preserves every artifact and original timing.
This does not resolve the documented implementation defects or replace the final
negative/alias, cadence and injection-C validation.
"""
from pathlib import Path
import argparse
import hashlib
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
for name, value in {"LIGHTKURVE_CACHE": str(ROOT / "data/cache/lightkurve"),
                    "TESSHUNTER_OFFLINE": "1", "PYTHONIOENCODING": "utf-8",
                    "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}.items():
    os.environ.setdefault(name, value)
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
import resume_cadence as Q
import audit_p5 as A
from tesshunter import stage_c as SC
from tesshunter import audit_rules as R
from tesshunter.audit_prep import transit_mask


def arrays(path):
    with np.load(path) as z:
        return {name: z[name] for name in z.files}


def finite_spectrum(z):
    return (set(z) == {"periods", "power", "chi2", "SR", "power_raw"}
            and all(a.shape == z["periods"].shape and a.ndim == 1
                    and bool(np.isfinite(a).all()) for a in z.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", choices=[key for source, key in Q.ORIGINAL_KEYS if source == "p8"])
    key = parser.parse_args().key
    out = Q.RECEIPTS / ("native_validation_" + key + ".json")
    if out.exists():
        raise RuntimeError("Validation receipt already exists; review before replacing")
    if any(key in owner["command"] for owner in Q.tls_owners()):
        raise RuntimeError("Live owner still names selected workspace")
    Q.assert_source()
    if not Q.complete("p8", "p10c_native", key):
        raise RuntimeError("Native case is incomplete")
    ws = Q.OUT / "p8/p10c_native" / key
    record = Q.read(ws / "stageC" / (key + ".json"))
    tls = Q.read(ws / "tls" / (key + ".json"))
    base = arrays(ws / "tls" / (key + "_spectrum.npz"))
    time = arrays(ws / "tls" / (key + "_lc.npz"))["time"]
    cadence = float(np.median(np.diff(np.sort(time))))
    log = ROOT / "p10/logs" / ("residual_native_" + key + ".log")
    calls = [(int(n), int(grid)) for n, grid in re.findall(
        r"Searching (\d+) data points, (\d+) periods", log.read_text(encoding="utf-8"))]
    local = SC.local_peak(base["periods"], base["power"], record["survey_period"])
    peaks = A._peak_table(base["periods"], base["power"])
    checks = {"base_arrays_finite_complete": finite_spectrum(base),
              "base_full_grid_matches_log": (len(time), len(base["periods"])) in calls,
              "base_top_ten_peaks_reproduce": peaks == tls["blind"]["peaks"],
              "native_local_reproduces": local == record["significant_peak"]["local"]}
    counts, locals_after_mask, rows = {}, {}, []
    for i, run in enumerate(record["significant_peak"].get("runs", [])):
        duration = SC.floor_duration(run["duration_days"], cadence * 86400)["floored_days"]
        ntransits = SC.covered_transits(time, run["period"], run["t0"], duration, cadence_days=cadence)
        period_key = f"{run['period']:.6f}"
        counts[period_key] = ntransits
        checks[f"run_{i}_coverage_and_duration_reproduce"] = (
            ntransits == run["covered_transits"] and duration == run["duration_used_days"])
        suffix = run.get("residual_suffix")
        checks[f"run_{i}_required_residual_present"] = bool(suffix) == (ntransits >= R.C_RESIDUAL_MIN_TRANSITS)
        row = {"period": run["period"], "covered_transits": ntransits,
               "duration_raw_days": run["duration_days"], "duration_used_days": duration,
               "residual_suffix": suffix}
        if suffix:
            residual = arrays(ws / "tls" / (key + suffix + "_spectrum.npz"))
            rtls = Q.read(ws / "tls" / (key + suffix + ".json"))
            mask = transit_mask(time, run["period"], run["t0"], duration,
                                n_durations=R.C_RESIDUAL_MASK_DURATIONS)
            rlocal = SC.local_peak(residual["periods"], residual["power"], record["survey_period"])
            locals_after_mask[period_key] = rlocal
            checks[f"run_{i}_full_finite_grid"] = (finite_spectrum(residual)
                and bool(np.array_equal(base["periods"], residual["periods"])))
            checks[f"run_{i}_mask_count_reproduces"] = (
                int(mask.sum()) == run["n_cadences_masked"] == rtls["blind"]["residual_mask"]["n_cadences_masked"])
            # inputs describes prepare before masking; actual masked counts are in the TLS log.
            checks[f"run_{i}_prepared_and_masked_input_counts_reproduce"] = (
                rtls["inputs"]["n_binned"] == len(time)
                and (int((~mask).sum()), len(residual["periods"])) in calls)
            checks[f"run_{i}_local_reproduces"] = rlocal == run["residual_local"]
            row.update(n_cadences_masked=int(mask.sum()), n_cadences_after_mask=int((~mask).sum()),
                       local=rlocal, residual_strongest=run["residual_strongest"])
        rows.append(row)
    concentration = SC.concentration(base["power"])
    raw_concentration = SC.concentration(base["power_raw"])
    redecision = SC.significant_peak(record["survey_period"], record["blind"], peaks, local,
                                     stronger_transits=counts, residual_local_sde=locals_after_mask)
    checks["no_fallback_trigger_in_this_case"] = concentration["fraction"] <= R.C_CONCENTRATION_TRIGGER
    checks["no_missing_alias_depth_test_needed_in_this_case"] = all(
        p["alias_of_survey_period"] is None for p in redecision["stronger"])
    checks["experimental_decision_reproduces"] = redecision["decision"] == record["decision"]
    result = {"utc": Q.utc(), "key": key, "checks": checks,
              "scope": "Settled inherited native execution and saved-array validation only; no C adoption or resolution of the documented implementation defects.",
              "native_local": local, "installed_concentration": concentration,
              "raw_concentration": raw_concentration,
              "raw_robust_at_installed_strongest": float(SC.robust_sde(base["power_raw"])[np.argmax(base["power"])]),
              "n_full_grid": len(base["periods"]), "n_prepared_cadences": len(time),
              "runs": rows, "experimental_decision": redecision,
              "decision_strongest": record["decision_strongest"], "wall_s": record["p10"]["wall_s"],
              "artifacts": {str(p.relative_to(ROOT)): {"bytes": p.stat().st_size,
                  "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in [*sorted(p for p in ws.rglob("*") if p.is_file()), log]}}
    with out.open("x", encoding="utf-8") as stream:
        stream.write(Q.json.dumps(result, indent=2) + "\n")
    print(Q.json.dumps({k: v for k, v in result.items() if k not in ("artifacts", "experimental_decision")}, indent=2))
    if not all(checks.values()):
        raise SystemExit("Saved case validation requires review; original artifacts are unchanged")


if __name__ == "__main__":
    main()
