"""Draw and validate the registered native-30 C sample without running C.

Uses the inherited seed, pool order and draw exactly; refuses undersampling,
redrawing, missing original A/S passes or duplicate candidate workspace keys.
"""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
os.environ.update(LIGHTKURVE_CACHE=str(ROOT / "data/cache/lightkurve"), PYTHONIOENCODING="utf-8",
                  TESSHUNTER_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1",
                  MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np
import p10_stage_c as T
import p8_completeness as C
from analyze_completeness import _load_results
import resume_cadence as Q


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = T.RES / "stage_c_injection_sample.json"
    validation = T.RES / "stage_c_injection_sample_validation.json"
    require(not output.exists() and not validation.exists(), "Sample already exists; do not redraw")
    Q.assert_source()
    cadence_path = T.RES / "stage_c_cadence_validation.json"
    cadence = Q.read(cadence_path)
    require(cadence["n"] == 37 and cadence["agree"] < 35 and all(cadence["checks"].values()), "Cadence validation incomplete")
    require(cadence["selected_injection_cadence"] == "native" and cadence["injection_count"] == 30, "Wrong registered sample")
    # HANDOFF_P8: the original calibration is stamped p7.0. The chosen p8.0
    # rules change only exact Stage B duration/window metadata; A/S is identical.
    rule_differences = {k: {"p7.0": v, "p8.0": T.R.P8_RULES.options[k]}
                        for k, v in T.R.DEFAULT_RULES.options.items() if v != T.R.P8_RULES.options[k]}
    require(rule_differences == {"exact_t14_record": {"p7.0": False, "p8.0": True}}, "Historical A/S equivalence changed")
    source = T.P8 / "injection_outcomes_p8.csv"
    rows = list(csv.DictReader(source.open(encoding="utf-8", newline="")))
    eligible = [r for r in rows if r["status"] == "recovered" and r["through_funnel"] == "True"]
    rng = np.random.default_rng(20260908)
    selected, pools = [], {}
    for name, (lo, hi) in T.INJ_BINS.items():
        pool = sorted((r for r in eligible if lo <= float(r["snr_expected"]) < hi), key=lambda r: r["job_id"])
        require(len(pool) >= 10, "Too few eligible injections: " + name)
        pools[name] = [r["job_id"] for r in pool]
        indices = sorted(rng.choice(len(pool), size=10, replace=False))
        selected.extend(dict(pool[i], bin=name) for i in indices)
    require(selected == T.injection_sample(10), "Draw differs from inherited seeded construction")
    require(len(selected) == len({r["job_id"] for r in selected}) == 30, "Sample is not exactly 30 unique jobs")
    data = _load_results(C.INJ_RUN)
    recovered = {j["job_id"]: j for j in C.recovered_jobs(data)}
    raw = {r["job_id"]: r for r in data}
    jobs, validated, candidate_keys = [], [], []
    input_hashes = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), source, C.SPEC, C.SAMPLE, cadence_path,
                                                            ROOT / "HANDOFF_P8.md", ROOT / "src/tesshunter/audit_rules.py")}
    for row in selected:
        job = recovered[row["job_id"]]; root = C.INJ_ROOT / job["job_id"]
        key = T.kkey(job["tic_id"], job["period_days"])
        require(job["tic_id"] == int(row["tic_id"]), "Injection identity mismatch")
        require(job["pregate_pass"] == (row["pregate"] == "True"), "Saved pre-gate field differs")
        a_path, s_path = (root / name / (key + ".json") for name in ("stageA", "secondary"))
        a, s = Q.read(a_path), Q.read(s_path)
        require(a["rules_version"] == s["rules_version"] and a["rules_version"] in ("p7.0", "p8.0"), "Different historical A/S rule")
        require(a["decision"] == s["gate"] == "PASS", "Selected injection did not pass A and S")
        require(raw[job["job_id"]]["status"] == "ok", "Selected search did not complete")
        for path in (a_path, s_path, root / "candidates.csv", root / "survivors.csv",
                     C.INJ_RUN / "results" / (job["job_id"] + ".json")):
            input_hashes[str(path.relative_to(ROOT))] = sha(path)
        candidate_keys.append(key)
        jobs.append({k: row[k] for k in ("job_id", "tic_id", "snr_expected", "bin")})
        validated.append({"job_id": job["job_id"], "key": key, "bin": row["bin"],
                          "snr_expected": float(row["snr_expected"]), "source_root": str(root.relative_to(ROOT)),
                          "search_period": job["period_days"], "search_depth_ppt": job["depth_ppt"],
                          "injection_model": raw[job["job_id"]]["injection_model"],
                          "stageA": a["decision"], "secondary": s["gate"], "historical_rules": a["rules_version"],
                          "pregate": job["pregate_pass"], "funnel_job": job})
    require(len(set(candidate_keys)) == 30, "Inherited C workspace keys collide; resolve storage before execution")
    require(not (T.OUT / "inj" / "injc_native").exists(), "Injection-C workspace already exists; inspect before sampling")
    sample = {"generated_utc": Q.utc(), "seed": 20260908, "n_per_bin": 10, "cadence": "native",
              "n": 30, "jobs": jobs, "executed": False,
              "selection": "Original P8 recovered injections with A/S PASS; inherited sorted pools and numpy default_rng sequence.",
              "cadence_validation_sha256": sha(cadence_path)}
    receipt = {"utc": Q.utc(), "seed": 20260908, "n": 30, "cadence": "native",
               "counts": dict(Counter(r["bin"] for r in selected)), "eligible_counts": {k: len(v) for k, v in pools.items()},
               "historical_rule_counts": dict(Counter(r["historical_rules"] for r in validated)),
               "p7_p8_option_differences": rule_differences,
               "provenance": "HANDOFF_P8 documents the original calibration as p7.0 with A/S identical to p8.0. Original version stamps are preserved. The initial validator incorrectly required a p8.0 stamp; that failed log and helper are retained. No sample was written on that failure and the seeded IDs are unchanged.",
               "eligible_job_ids": pools, "checks": {name: True for name in (
                   "cadence_decision_complete", "exact_inherited_seeded_draw", "exact_ten_per_bin",
                   "all_searches_successful_and_recovered", "all_original_A_S_pass_and_rule_equivalence",
                   "candidate_workspace_keys_unique", "no_existing_C_execution")},
               "inputs_sha256": input_hashes, "rows": validated,
               "scope": "Sampling only; no C result or retention measurement exists yet. Do not redraw based on later outcomes."}
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(sample, indent=2) + "\n")
    receipt["sample_sha256"] = sha(output)
    with validation.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("rows", "inputs_sha256", "eligible_job_ids")}, indent=2))


if __name__ == "__main__":
    main()
