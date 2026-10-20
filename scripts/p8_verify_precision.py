"""Verify the numerical guard preserves completed P8 search inputs on affected stars."""
import csv
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
P8 = REPO / "data/survey/p8"
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data/cache/lightkurve"))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")


def compare(job):
    from tesshunter import biweight_precision, survey, survey_p8
    cfg = survey.get_config("survey_p8")
    tic = int(job["tic_id"])
    if job["kind"] == "injection":
        spec = {k: float(v) for k, v in job["spec"].items() if k not in ("job_id",)}
        original_guard = biweight_precision.needs_precision_guard
        try:
            biweight_precision.needs_precision_guard = lambda _: False
            old, _, _ = survey_p8.get_prepared(tic, cfg, injection=spec, star=spec)
        finally:
            biweight_precision.needs_precision_guard = original_guard
        new, _, _ = survey_p8.get_prepared(tic, cfg, injection=spec, star=spec)
    else:
        old, _, _ = survey_p8.get_prepared(tic, cfg)
        products = survey_p8.load_audit_products(tic, sector_min=cfg.sector_min)
        products, notes = survey_p8.harmonise_cadence(products, cfg.target_cadence_minutes)
        new, _ = survey_p8.build_prepared(tic, cfg, products, cadence_notes=notes)
    differences = {}
    for field in ("time", "flux", "flux_err"):
        a, b = getattr(old, field).value, getattr(new, field).value
        identical = np.array_equal(a, b, equal_nan=True)
        differences[field] = {"identical": bool(identical), "n_old": len(a), "n_new": len(b),
                              "max_absolute_difference": float(np.nanmax(np.abs(a - b))) if len(a) == len(b) else None}
    return {"tic_id": tic, "job_id": job.get("spec", {}).get("job_id"), "kind": job["kind"],
            "arrays": differences, "identical": all(r["identical"] for r in differences.values())}


def main():
    measured = json.loads((P8 / "numerical_inputs_p8.json").read_text(encoding="utf-8"))
    affected = {r["tic_id"] for r in measured["hits"]}
    injection_stars = {r["tic_id"] for r in measured["hits_on_injection_sample"]}
    jobs = [{"kind": "noise", "tic_id": tic} for tic in sorted(affected)]
    for spec in csv.DictReader(open(REPO / "data/survey/injections_p8.csv", newline="", encoding="utf-8")):
        if int(spec["tic_id"]) in injection_stars:
            jobs.append({"kind": "injection", "tic_id": int(spec["tic_id"]), "spec": spec})
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(compare, jobs):
            results.append(result)
            print(json.dumps(result), flush=True)
    output = {"n_comparisons": len(results), "n_identical": sum(r["identical"] for r in results), "results": results}
    (P8 / "precision_verification_p8.json").write_text(json.dumps(output, indent=1), encoding="utf-8")
    if any(not r["identical"] for r in results):
        raise SystemExit("completed search inputs changed; inspect precision_verification_p8.json before continuing")


if __name__ == "__main__":
    main()
