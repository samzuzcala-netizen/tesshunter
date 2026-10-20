"""Prompt 8 Part 1e: the 600-second decision, on the same injections.

The seeded 100-star subset (``data/survey/injections_p8_600s_subset.csv``, 700 injections) was run
under ``survey_p8`` (sectors >= 56 at native 200 s) and under ``survey_p8_600s`` (sectors >= 27,
everything binned to 600 s).  Paired outcomes per injection: a = recovered only at 200 s, b =
recovered only at 600 s.

Pre-registered rule (HANDOFF_P8.md section 0, before the run): the 600-second sectors enter the
search only if b - a > 2 sqrt(a + b).  Writes ``data/survey/p8/decision_600s.json``.
"""
from __future__ import annotations

import csv
import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from analyze_completeness import _load_results, classify   # noqa: E402

RUN200 = REPO / "data" / "survey" / "runs" / "inj_p8"
RUN600 = REPO / "data" / "survey" / "runs" / "inj_p8_600s"
SUBSET = REPO / "data" / "survey" / "injections_p8_600s_subset.csv"
OUT = REPO / "data" / "survey" / "p8" / "decision_600s.json"


def main() -> None:
    ids = [r["job_id"] for r in csv.DictReader(open(SUBSET, newline="", encoding="utf-8"))]
    r200 = {r["job_id"]: r for r in _load_results(RUN200)}
    r600 = {r["job_id"]: r for r in _load_results(RUN600)}
    a = b = both = neither = 0
    n_pairs, missing = 0, 0
    walls200, walls600 = [], []
    by_bin: dict[str, dict] = {}
    spec = {r["job_id"]: r for r in csv.DictReader(open(SUBSET, newline="", encoding="utf-8"))}
    for j in ids:
        x, y = r200.get(j), r600.get(j)
        if not x or not y or x.get("status") != "ok" or y.get("status") != "ok":
            missing += 1
            continue
        n_pairs += 1
        walls200.append(float(x.get("wall_s") or 0)); walls600.append(float(y.get("wall_s") or 0))
        cx, cy = classify(x)["status"] == "recovered", classify(y)["status"] == "recovered"
        pb = spec[j]["period_bin"]
        d = by_bin.setdefault(pb, {"n": 0, "rec200": 0, "rec600": 0})
        d["n"] += 1; d["rec200"] += int(cx); d["rec600"] += int(cy)
        if cx and cy:
            both += 1
        elif cx:
            a += 1
        elif cy:
            b += 1
        else:
            neither += 1
    thr = 2.0 * math.sqrt(a + b) if (a + b) else 0.0
    admit = (b - a) > thr
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "rule": "admit the 600-s sectors only if b - a > 2 sqrt(a + b), a = recovered only at 200 s, b = only at 600 s",
           "n_injections_in_subset": len(ids), "n_pairs_compared": n_pairs, "n_missing_or_failed": missing,
           "both_recovered": both, "only_200s": a, "only_600s": b, "neither": neither,
           "recovered_200s": both + a, "recovered_600s": both + b,
           "b_minus_a": b - a, "two_sqrt_a_plus_b": thr, "admit_600s_sectors": bool(admit),
           "by_period_bin": by_bin,
           "wall_s_median_200s": (sorted(walls200)[len(walls200) // 2] if walls200 else None),
           "wall_s_median_600s": (sorted(walls600)[len(walls600) // 2] if walls600 else None),
           "decision": ("the 600-second sectors ENTER the search (survey_p8_600s)" if admit else
                        "the search runs on the 200-second sectors alone (survey_p8)")}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
