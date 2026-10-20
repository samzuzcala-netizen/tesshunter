"""Record the completed P8 search's coverage, input checks and source hashes."""
from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data/survey/p8"
RUN = REPO / "data/survey/runs/survey_p8"


def rows(path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    log_path = OUT / "logs/search_p8_20260905.log"
    log = log_path.read_text(encoding="utf-8")
    if "=== DONE search ===" not in log:
        raise RuntimeError("The search and retry pass have not finished")
    targets_path = REPO / "data/survey/targets_p8.csv"
    target_rows = rows(targets_path)
    targets = {int(r["tic_id"]) for r in target_rows}
    if len(targets) != len(target_rows):
        raise RuntimeError("Duplicate target identifiers")
    records, source_hashes = [], {}
    for path in sorted((RUN / "results").glob("*.json")):
        raw = path.read_bytes()
        rec = json.loads(raw)
        if path.stem != f"tic{rec['tic_id']}":
            raise RuntimeError(f"Result name and target differ: {path.name}")
        records.append(rec)
        source_hashes[path.name] = hashlib.sha256(raw).hexdigest()
    actual = {int(d["tic_id"]) for d in records}
    if actual != targets or len(records) != len(targets):
        raise RuntimeError(f"Result coverage differs: missing={targets-actual}, extra={actual-targets}")
    if any(d.get("status") != "ok" for d in records):
        raise RuntimeError("This successful-search checkpoint requires every target to be ok")
    expected = ("survey_p8", "3d160359ad", 56, 200.0 / 60.0, None, 0.5, 30.0)
    fields = ("name", "ingest_key", "sector_min", "target_cadence_minutes", "bin_minutes", "period_min", "period_max")
    if any(tuple(d["config"].get(k) for k in fields) != expected for d in records):
        raise RuntimeError("A result has a different P8 search configuration")
    products = [p for d in records for p in d["result"]["provenance"]["products"]]
    if not products or any(float(p["cadence_s"]) != 200.0 or int(p["unit"]) < 56 for p in products):
        raise RuntimeError("Search products include a different cadence or an earlier sector")
    # Sector 1751 is a real January 2026 special pointing, not a malformed label.
    # It was downloaded with the other public native-cadence data, but the
    # population's three-sector qualification used the standard-sector table.
    special_rows = []
    target_by_id = {int(r["tic_id"]): r for r in target_rows}
    for d in records:
        for p in d["result"]["provenance"]["products"]:
            if int(p["unit"]) <= 105:
                continue
            if int(p["unit"]) != 1751:
                raise RuntimeError(f"Unreviewed special sector: {p['unit']}")
            target = target_by_id[int(d["tic_id"])]
            qualifying = {int(s) for s in target["sectors_200s"].split(",")}
            if 1751 in qualifying or len(qualifying) < 3:
                raise RuntimeError("A special sector was used for the population minimum")
            index_path = REPO / "data/survey/audit_lc" / f"tic{d['tic_id']}" / "index.json"
            index = json.loads(index_path.read_bytes())
            raw = next(q for q in index["products"] if q.get("file") == p["file"])
            if raw["sector"] != 1751 or raw["exptime_s"] != 200.0 or raw["cadence_s"] != 200.0:
                raise RuntimeError("Special-sector raw metadata differs")
            special_rows.append({"tic_id": d["tic_id"], "file": p["file"], "sector": raw["sector"],
                                 "native_cadence_s": raw["cadence_s"], "n_input_cadences": raw["n"],
                                 "t_start_btjd": raw["t_start"], "t_end_btjd": raw["t_end"],
                                 "qualifying_standard_sectors": sorted(qualifying),
                                 "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest()})
    candidates = [(int(d["tic_id"]), q) for d in records for q in d["result"].get("planets", [])]
    if any(not 0.5 <= q["period_days"] <= 30.0 for _, q in candidates):
        raise RuntimeError("A candidate falls outside the P8 search band")
    keys = Counter(f"tic{tic}_P{q['period_days']:.4f}" for tic, q in candidates)
    if any(n != 1 for n in keys.values()):
        raise RuntimeError("Accepted candidates have duplicate rounded audit identifiers")
    pregate = {(tic, q["period_days"]) for tic, q in candidates
               if (q.get("stitch_snr") or 0) >= 7.1 and (q.get("stitch_n_transits") or 0) >= 3
               and q.get("stitch_epoch_consistent")}
    collected = rows(OUT / "candidates.csv")
    survivors = rows(OUT / "survivors.csv")
    if (len(collected) != len(candidates)
            or {(int(r["tic_id"]), float(r["period_days"])) for r in collected}
            != {(t, q["period_days"]) for t, q in candidates}):
        raise RuntimeError("The collected candidate table differs from the search records")
    if len(survivors) != len(pregate) or {(int(r["tic_id"]), float(r["period_days"])) for r in survivors} != pregate:
        raise RuntimeError("The Stage A input differs from the pre-gate calculation")
    markers = {}
    for name, value in re.findall(r"^=== (.*?) === (.*?)$", log, re.MULTILINE):
        markers[name] = datetime.strptime(" ".join(value.split()), "%a %m/%d/%Y %H:%M:%S.%f")
    calibration_tics = {int(r["tic_id"]) for r in rows(OUT / "injection_outcomes_p8.csv")}
    evidence = {"generated_utc": datetime.now(timezone.utc).isoformat(), "verified": True,
                "n_targets": len(targets), "n_results": len(records), "n_missing": 0, "n_extra": 0,
                "status_counts": dict(Counter(d["status"] for d in records)),
                "attempt_counts": dict(Counter(d["attempts"] for d in records)),
                "n_cache_hits": sum(bool(d["cache"]["cache_hit"]) for d in records),
                "n_products": len(products), "cadences_s": sorted({p["cadence_s"] for p in products}),
                "sector_min": min(p["unit"] for p in products), "sector_max": max(p["unit"] for p in products),
                "standard_sector_range": [min(p["unit"] for p in products if p["unit"] != 1751),
                                          max(p["unit"] for p in products if p["unit"] != 1751)],
                "special_sector_1751": {"n_products": len(special_rows), "products": special_rows,
                    "not_used_for_population_minimum": True,
                    "calibration_sample_overlap_tics": sorted(calibration_tics & {r["tic_id"] for r in special_rows}),
                    "explanation": "A special 200-second FFI pointing on 2026-01-15 to 2026-01-22, during sector 99. Native products are retained by the existing sector/cadence selection.",
                    "sources": ["https://heasarc.gsfc.nasa.gov/docs/tess/sector1751_summary.html",
                                "https://archive.stsci.edu/hlsp/tess-spoc"]},
                "n_accepted": len(candidates), "n_pregate": len(pregate),
                "duplicate_audit_keys": 0, "out_of_band_periods": 0,
                "configuration_fields": dict(zip(fields, expected)),
                "log_timestamps_local": {k: v.isoformat() for k, v in markers.items()},
                "timestamp_note": "Host local time, America/New_York (EDT for this run).",
                "prefetch_launcher_elapsed_seconds": (markers["search survey_p8"]-markers["prefetch survey_p8"]).total_seconds(),
                "search_launcher_elapsed_seconds": (markers["retry pass"]-markers["search survey_p8"]).total_seconds(),
                "retry_launcher_elapsed_seconds": (markers["DONE search"]-markers["retry pass"]).total_seconds(),
                "free_disk_gib_at_validation": shutil.disk_usage(REPO).free / 2**30,
                "evidence_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in (targets_path, log_path, OUT / "candidates.csv", OUT / "survivors.csv",
                                              OUT / "per_target_log.csv", OUT / "collect_p8.json", OUT / "run_summary_p8.json")},
                "result_sha256": source_hashes}
    path = OUT / "search_validation_p8.json"
    path.write_text(json.dumps(evidence, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k not in ("result_sha256", "evidence_sha256")}, indent=1))


if __name__ == "__main__":
    main()
