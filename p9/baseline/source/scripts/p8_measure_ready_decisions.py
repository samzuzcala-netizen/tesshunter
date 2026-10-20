"""Measure a bounded batch of settled injection records while the rest of the funnel runs.

This only fills the existing decision instrument's per-injection checkpoints. It never
builds tables, chooses a rule, or starts a search. Run one batch at a time and let it finish
before the complete-set decision runner starts. No TLS call runs inside the process pool.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "scripts")]
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data/cache/lightkurve"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for name in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(name, "1")


def measure(job):
    from p8_worker_qos import configure_current_worker
    configure_current_worker()
    import p8_decisions as D
    result = D.one(job)
    return {k: result[k] for k in ("key", "status", "seconds", "error") if k in result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=64)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.limit < 1 or args.workers < 1:
        parser.error("limit and workers must be positive")
    import audit_p5 as A
    import p8_completeness as C
    import p8_decisions as D
    from tesshunter.survey import get_config
    config = A.input_config_for(get_config("survey_p8"))
    selected = []
    for job in C.recovered_jobs(C._load_results(C.INJ_RUN)):
        path = D.DEC / "inj" / f"{job['job_id']}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "OK" and record.get("input_config") == config:
                continue
        try:
            selected.append(D.injection_job(job))
        except (ValueError, OSError):
            continue  # only a settled Stage A and secondary pair can be measured
        if len(selected) >= args.limit:
            break
    started = time.perf_counter()
    summary = {"generated_utc": C.utc(), "scope": "partial instrument only; no rule selection",
               "planned": [j["key"] for j in selected], "workers": args.workers, "completed": []}
    path = C.P8 / "logs" / f"decisions_ready_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    A.jdump(path, summary)
    print(f"Measuring {len(selected)} settled injections with {args.workers} workers; all-set validation stays required", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(measure, job) for job in selected]
        for future in as_completed(pending):
            result = future.result()
            summary["completed"].append(result)
            summary["seconds"] = time.perf_counter() - started
            A.jdump(path, summary)
            print(f"{len(summary['completed'])}/{len(selected)} {json.dumps(result)}", flush=True)
    if any(r["status"] != "OK" for r in summary["completed"]):
        raise SystemExit("incomplete batch; failed entries will be retried by the complete-set runner")
    print(f"DONE {len(selected)} injections in {(time.perf_counter() - started) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
