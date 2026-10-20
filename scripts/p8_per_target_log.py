"""Prompt 8 Part 2: the per-star log of the search run.

One row per target from ``data/survey/runs/survey_p8/results``: status and attempts, timing by
stage, cadences, sectors and products used (by author and cadence), every cadence note or
fallback, the detection-budget stop, the rotation proxy, the preprocessing counters and the
candidate count.  Writes ``data/survey/p8/per_target_log.csv`` and ``run_summary_p8.json``.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "data" / "survey" / "runs" / "survey_p8"
OUT = REPO / "data" / "survey" / "p8"
TARGETS = REPO / "data" / "survey" / "targets_p8.csv"


def main() -> None:
    targets = [int(r["tic_id"]) for r in csv.DictReader(open(TARGETS, newline="", encoding="utf-8"))]
    rows, missing = [], []
    for tic in targets:
        p = RUN / "results" / f"tic{tic}.json"
        if not p.exists():
            missing.append(tic)
            rows.append({"tic_id": tic, "status": "missing"})
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        res = d.get("result") or {}
        prov = res.get("provenance") or {}
        prods = prov.get("products") or []
        by_author = {}
        for q in prods:
            by_author[q.get("author")] = by_author.get(q.get("author"), 0) + 1
        cad = sorted({round(float(q.get("cadence_s") or 0)) for q in prods})
        rot = d.get("rotation_proxy") or {}
        cnt = d.get("prepare_counters") or {}
        cache = d.get("cache") or {}
        tm = res.get("timings") or {}
        rows.append({
            "tic_id": tic, "status": d.get("status"), "attempts": d.get("attempts"),
            "wall_s": round(float(d.get("wall_s") or 0), 1),
            "prepare_s": round(float(cache.get("stitch_s") or 0), 1), "cache_hit": cache.get("cache_hit"),
            "search_s": round(float((d.get("timings") or {}).get("search") or 0), 1),
            "detect_s": round(float(tm.get("detect") or 0), 1), "vet_s": round(float(tm.get("vet") or 0), 1),
            "confirm_s": round(float((d.get("timings") or {}).get("confirm") or 0), 1),
            "n_cadences": d.get("n_cadences_raw"), "baseline_days": round(float(d.get("baseline_days") or 0), 1),
            "n_units": d.get("n_units"), "sectors_used": ",".join(str(u) for u in (prov.get("units_used") or [])),
            "n_products": len(prods), "products_by_author": ";".join(f"{k}:{v}" for k, v in sorted(by_author.items())),
            "cadences_s": ",".join(str(c) for c in cad),
            "cadence_notes": " | ".join(prov.get("cadence_notes") or []),
            "fallback_events": " | ".join(str(e) for e in (prov.get("fallback_events") or [])),
            "n_searches": res.get("n_searches"), "budget_stop": any("would not fit" in n for n in (res.get("notes") or [])),
            "n_candidates": len(res.get("planets") or []),
            "rotation_peak_period_days": rot.get("peak_period_days"), "rotation_semi_amplitude_ppt": rot.get("semi_amplitude_ppt"),
            "rotation_scatter_ppt": rot.get("scatter_ppt"), "prep_mad_ppt": cnt.get("mad_ppt"),
            "n_masked_quality": cnt.get("n_masked_quality"), "n_clipped_up": cnt.get("n_clipped_up"),
            "n_isolated_clipped": cnt.get("n_isolated_clipped"), "n_deep_clipped": cnt.get("n_deep_clipped"),
            "error": (d.get("error") or "").splitlines()[0][:200] if d.get("error") else "",
        })
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(OUT / "per_target_log.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if r.get("status") == "ok"]
    walls = np.array([r["wall_s"] for r in ok], dtype=float) if ok else np.zeros(0)
    summ = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_targets": len(targets),
            "status_counts": {s: sum(1 for r in rows if r.get("status") == s) for s in sorted({r.get("status") for r in rows}, key=str)},
            "n_missing": len(missing), "missing_tics": missing,
            "errors": [{"tic_id": r["tic_id"], "error": r.get("error")} for r in rows if r.get("status") not in ("ok", "missing")],
            "wall_s_median_p90_max": [float(np.median(walls)), float(np.percentile(walls, 90)), float(walls.max())] if walls.size else None,
            "job_wall_hours": float(walls.sum() / 3600.0) if walls.size else None,
            "timing_note": "Sum of per-job wall time; CPU time was not measured by this log.",
            "n_budget_stops": sum(1 for r in ok if r.get("budget_stop")),
            "n_candidates_total": sum(int(r.get("n_candidates") or 0) for r in ok),
            "n_units_median": float(np.median([r["n_units"] for r in ok if r.get("n_units")])) if ok else None,
            "n_cadences_median": float(np.median([r["n_cadences"] for r in ok if r.get("n_cadences")])) if ok else None,
            "n_with_cadence_notes": sum(1 for r in ok if r.get("cadence_notes")),
            "n_with_fallback_events": sum(1 for r in ok if r.get("fallback_events")),
            "products_by_author_total": {}}
    for r in ok:
        for kv in (r.get("products_by_author") or "").split(";"):
            if ":" in kv:
                k, v = kv.split(":")
                summ["products_by_author_total"][k] = summ["products_by_author_total"].get(k, 0) + int(v)
    (OUT / "run_summary_p8.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
