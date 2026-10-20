"""Prompt 8: the survey_v1 path must still reproduce prompt 4.

One smoke test on TIC 100196477: rerun the prompt-4 survey job from the stitched cache
(no MAST) with the unchanged ``survey_v1`` preset and compare every accepted candidate's
period, epoch, SNR, depth and whole-stitch SNR with the stored prompt-4 record
``data/survey/runs/survey_v1/results/tic100196477.json``.  Writes
``data/survey/p8/smoke_v1_tic100196477.json``.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

TIC = 100196477
STORED = REPO / "data" / "survey" / "runs" / "survey_v1" / "results" / f"tic{TIC}.json"
OUT = REPO / "data" / "survey" / "p8" / f"smoke_v1_tic{TIC}.json"
RTOL = 1e-9


def main() -> int:
    import warnings
    warnings.simplefilter("ignore")
    from tesshunter import survey

    old = json.loads(STORED.read_text(encoding="utf-8"))
    job = {"job_id": f"smoke_tic{TIC}", "tic_id": TIC, "config": "survey_v1", "star": old.get("star") or {}}
    t0 = time.perf_counter()
    new = survey.run_job(job, allow_download=False)
    wall = time.perf_counter() - t0
    diffs = []
    rows = []
    op, np_ = old["result"]["planets"], (new.get("result") or {}).get("planets") or []
    if len(op) != len(np_):
        diffs.append(f"candidate count {len(np_)} vs stored {len(op)}")
    for a, b in zip(op, np_):
        row = {}
        for k in ("period_days", "epoch_btjd", "snr", "depth_ppt", "stitch_snr", "duration_days", "stitch_n_transits"):
            va, vb = a.get(k), b.get(k)
            row[k] = {"stored": va, "new": vb}
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                if abs(float(va) - float(vb)) > RTOL * max(1.0, abs(float(va))):
                    diffs.append(f"{k}: {vb} vs stored {va} (P={a.get('period_days')})")
            elif va != vb:
                diffs.append(f"{k}: {vb} vs stored {va}")
        rows.append(row)
    rec = {"tic_id": TIC, "config": "survey_v1", "ingest_key_new": new["config"]["ingest_key"],
           "ingest_key_stored": old["config"]["ingest_key"], "cache_hit": (new.get("cache") or {}).get("cache_hit"),
           "n_cadences_new": new.get("n_cadences_raw"), "n_cadences_stored": old.get("n_cadences_raw"),
           "status_new": new.get("status"), "n_candidates_stored": len(op), "n_candidates_new": len(np_),
           "n_differences": len(diffs), "differences": diffs[:20], "per_candidate": rows,
           "tolerance": f"relative {RTOL}", "wall_s": round(wall, 1),
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if new["config"]["ingest_key"] != old["config"]["ingest_key"]:
        rec["n_differences"] += 1
        rec["differences"].append("ingest key changed")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: rec[k] for k in ("ingest_key_new", "ingest_key_stored", "cache_hit", "n_cadences_new",
                                          "n_cadences_stored", "n_candidates_stored", "n_candidates_new",
                                          "n_differences", "differences", "wall_s")}, indent=1))
    return 0 if rec["n_differences"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
