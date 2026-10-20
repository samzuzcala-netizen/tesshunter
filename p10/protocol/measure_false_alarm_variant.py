"""Measure a complete paired P10 variant and prepare its P10-only FA funnel.

Requires all 600 injection and 300 FA results. Reuses the inherited pre-gate
collector, without running A or S, changing scientific code, or adopting a rule.
Existing measurements and funnel inputs are never overwritten.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import math
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("LIGHTKURVE_CACHE", str(ROOT / "data/cache/lightkurve"))
os.environ.setdefault("TESSHUNTER_OFFLINE", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
import p10_search_capacity as C
from tesshunter.survey import get_config


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def complete_records(variant, kind, config):
    sample = C.SUBSET if kind == "inj" else C.FA_SAMPLE
    with sample.open(encoding="utf-8", newline="") as stream:
        samples = list(csv.DictReader(stream))
    expected = {r["job_id"] if kind == "inj" else "tic" + r["tic_id"]: int(r["tic_id"])
                for r in samples}
    count = 600 if kind == "inj" else 300
    paths = sorted((C.RUNS / f"{variant}_{kind}" / "results").glob("*.json"))
    if len(expected) != count or len(samples) != count or {p.stem for p in paths} != set(expected):
        raise RuntimeError(f"Requires exactly {count} expected {kind} records")
    records = []
    for path in paths:
        data = path.read_bytes()
        record = json.loads(data)
        if (record.get("status") != "ok" or record.get("job_id") != path.stem
                or record.get("tic_id") != expected[path.stem] or not record.get("result")):
            raise RuntimeError("Unsettled or mismatched record: " + str(path))
        if record.get("config") != config:
            raise RuntimeError("Unexpected paired search configuration: " + str(path))
        if not math.isfinite(float(record["wall_s"])) or float(record["wall_s"]) <= 0:
            raise RuntimeError("Missing successful-job wall: " + str(path))
        searches = record.get("searches") or []
        if not searches or any("budget_exhausted" not in search for search in searches):
            raise RuntimeError("Missing partition budget instrumentation: " + str(path))
        records.append((record, hashlib.sha256(data).hexdigest()))
    return records


def wall_row(record, digest):
    return {"job_id": record["job_id"], "tic_id": record["tic_id"],
            "wall_s": record["wall_s"], "result_sha256": digest,
            "n_partitions": len(record["searches"]),
            "n_partitions_exhausted": sum(bool(s["budget_exhausted"]) for s in record["searches"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=list("abcde"))
    args = parser.parse_args()
    variant = args.variant
    out = C.RES / f"search_false_alarms_{variant}.json"
    funnel = ROOT / "data/survey/p10/fa_2b" / variant
    if out.exists() or funnel.exists():
        raise RuntimeError("Measurement or funnel already exists; review before replacing")
    config = get_config(C.VARIANTS[variant], record_traces=True).to_dict()
    inj = complete_records(variant, "inj", config)
    fa = complete_records(variant, "fa", config)
    # set_root precedes every operation that writes; the inherited P8 tree is read-only.
    import p8_funnel as F
    F.set_root(funnel)
    F.set_rules("p8.0")
    collection = F.collect(C.RUNS / f"{variant}_fa", C.FA_SAMPLE)
    if collection["n_stars_ok"] != 300 or collection["statuses"] != {"ok": 300}:
        raise RuntimeError("Collector disagrees with the complete FA census")
    with F.CANDIDATES.open(encoding="utf-8", newline="") as stream:
        candidates = list(csv.DictReader(stream))
    pre_by_tic = {}
    for candidate in candidates:
        if candidate["passes_pregate"] == "True":
            pre_by_tic.setdefault(int(candidate["tic_id"]), []).append(int(candidate["planet_num"]))
    fa_rows = []
    for record, digest in fa:
        row = wall_row(record, digest)
        row.update(n_accepted=len(record["result"].get("planets") or []),
                   pregate_planet_numbers=pre_by_tic.get(record["tic_id"], []))
        row["n_pregate"] = len(row["pregate_planet_numbers"])
        fa_rows.append(row)
    if sum(r["n_pregate"] for r in fa_rows) != collection["n_pass_pregate"]:
        raise RuntimeError("Candidate identity audit disagrees with collector count")
    inj_rows = [wall_row(record, digest) for record, digest in inj]
    all_rows = inj_rows + fa_rows
    walls = [float(r["wall_s"]) for r in all_rows]
    n_parts = sum(r["n_partitions"] for r in all_rows)
    n_exhausted = sum(r["n_partitions_exhausted"] for r in all_rows)
    summary = {"n_injections": 600, "n_fa_stars": 300,
               "n_accepted_candidates": collection["n_accepted_candidates"],
               "n_pregate_candidates": collection["n_pass_pregate"],
               "n_pregate_stars": collection["n_stars_pass_pregate"],
               "FA_pre": collection["n_pass_pregate"] / 300,
               "FA_S": None, "FA_S_count": None,
               "FA_S_status": "pending Stage A and bound secondary on the prepared P10 funnel",
               "median_wall_s_all": float(np.median(walls)),
               "median_wall_s_fa": float(np.median([r["wall_s"] for r in fa_rows])),
               "p90_wall_s_all": float(np.percentile(walls, 90)),
               "sum_successful_job_hours": sum(walls) / 3600,
               "n_partitions": n_parts, "n_exhausted_partitions": n_exhausted,
               "budget_exhausted_partition_fraction": n_exhausted / n_parts,
               "jobs_with_any_exhaustion_fraction": sum(r["n_partitions_exhausted"] > 0 for r in all_rows) / len(all_rows)}
    result = {"utc": datetime.now(timezone.utc).isoformat(), "variant": variant,
              "preset": C.VARIANTS[variant], "config": config, "summary": summary,
              "scope": "All 600 injections and 300 FA stars. No Stage A/S execution or variant adoption.",
              "wall_definition": "Median over the 900 saved successful per-job wall_s values, including the 402 inherited completed a injections where applicable; interrupted attempts and queue elapsed time are not substituted.",
              "pregate": F.PREGATE,
              "funnel_root": str(funnel.relative_to(ROOT)),
              "inputs": {str(p.relative_to(ROOT)): sha(p) for p in
                         (C.SUBSET, C.FA_SAMPLE, ROOT / "scripts/p8_funnel.py",
                          F.CANDIDATES, F.SURVIVORS, funnel / "collect_p8.json")},
              "injection_wall_rows": inj_rows, "false_alarm_rows": fa_rows}
    with out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
