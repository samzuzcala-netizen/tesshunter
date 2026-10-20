"""Attach the completed P8 survivor depths to the pre-search Gaia cache.

This replays audit_p5.neighbours_step's dilution calculation from its saved full
magnitudes. The original per-star, any-survivor rule and source catalogue data
stay unchanged. A recorded plan makes interrupted writes resumable; downstream
records prohibit a new plan, so a stale Stage B result cannot be reused silently.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "data/survey/p8"
sys.path.insert(0, str(REPO / "src"))
from tesshunter.star_vet import gaia_flag_digest

COUNT = "n_neighbours_that_could_produce_depth_total_eclipse_within_63arcsec"
TOTAL = "can_produce_candidate_depths_total_eclipse"
HALF = "can_produce_candidate_depths_50pct_eclipse"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def semantic_sha(record):
    return sha(json.dumps(record, sort_keys=True, separators=(",", ":")).encode())


def atomic(path, raw):
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_bytes(raw)
    tmp.replace(path)


def depths_by_tic(raw):
    depths = {}
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        tic = int(row["tic_id"])
        values = depths.setdefault(tic, set())
        if row.get("depth_ppt") not in (None, "", "nan"):
            values.add(round(float(row["depth_ppt"]), 3))
    return {tic: sorted(values) for tic, values in depths.items()}


def enrich_record(record, depths):
    result = copy.deepcopy(record)
    result["candidate_depths_ppt"] = list(depths)
    gaia = result["gaia"]
    if gaia.get("error"):
        raise RuntimeError(f"Cannot enrich failed Gaia record: {record['tic_id']}")
    target = gaia.get("target") or {}
    for neighbour in gaia["neighbours"]:
        band = neighbour["band_used"]
        if band not in ("rp", "g"):
            raise RuntimeError(f"Unknown saved Gaia dilution band: {band}")
        m_n = neighbour.get("Rp" if band == "rp" else "G")
        m_t = target.get(f"phot_{band}_mean_mag")
        if m_n is None or m_t is None:
            neighbour[TOTAL] = neighbour[HALF] = None
        else:
            # Do not use the rounded flux ratio or displayed maximum depth.
            fr = 10 ** (-0.4 * (m_n - m_t))
            dmax = fr / (1 + fr)
            neighbour[TOTAL] = [bool(1000 * dmax >= d) for d in depths]
            neighbour[HALF] = [bool(500 * dmax >= d) for d in depths]
    gaia[COUNT] = int(sum(1 for n in gaia["neighbours"]
                          if n["sep_arcsec"] <= 63 and n[TOTAL] and any(n[TOTAL])))
    if "summary" in result:
        result["summary"], replacements = re.subn(
            r"(?:\d+|\?) neighbour\(s\) within 3 px bright enough to make the depth",
            f"{gaia[COUNT]} neighbour(s) within 3 px bright enough to make the depth",
            result["summary"])
        if replacements != 1:
            raise RuntimeError(f"Unexpected Gaia summary: {record['tic_id']}")
    return result


def ensure_context(*, check_only=False):
    validation = json.loads((ROOT / "search_validation_p8.json").read_bytes())
    sources = (ROOT / "survivors.csv", REPO / "data/survey/targets_p8.csv")
    source_sha = {str(p.relative_to(REPO)): sha(p.read_bytes()) for p in sources}
    if not validation.get("verified") or any(
            validation.get("evidence_sha256", {}).get(name) != value for name, value in source_sha.items()):
        raise RuntimeError("P8 depths require the completed, validated candidate and target tables")
    depths = depths_by_tic(sources[0].read_bytes())
    tics = [int(r["tic_id"]) for r in csv.DictReader(io.StringIO(sources[1].read_text(encoding="utf-8")))]
    if len(tics) != validation["n_targets"] or len(set(tics)) != len(tics) or set(depths) - set(tics):
        raise RuntimeError("P8 neighbour population differs from the validated search")
    evidence = ROOT / "neighbour_depth_context_p8.json"
    if evidence.exists():
        plan = json.loads(evidence.read_bytes())
        if plan["source_sha256"] != source_sha:
            raise RuntimeError("Candidate-depth context changed; revalidate it and review downstream caches")
    else:
        if check_only:
            raise RuntimeError("Run the P8 neighbour-depth enrichment before Stage B")
        if any(next((ROOT / f"stage{stage}").glob("*.json"), None) for stage in "BCD"):
            raise RuntimeError("Downstream P8 records exist without depth provenance; review them before enrichment")
        plan = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": "planned",
                "source_sha256": source_sha, "n_stars": len(tics), "n_stars_with_survivors": len(depths),
                "method": "audit_p5.neighbours_step: full saved Rp/G magnitudes, depths rounded to 0.001 ppt; any survivor depth per star; separation <= 63 arcsec",
                "files": [], "n_records_changed": 0, "n_star_flag_lists_changed": 0,
                "n_stars_with_depth_capable_neighbour": 0}
        for tic in tics:
            path = ROOT / "neighbours" / f"tic{tic}.json"
            raw = path.read_bytes()
            before = json.loads(raw)
            if before.get("tic_id") != tic:
                raise RuntimeError(f"Neighbour file identifies a different star: {path}")
            after = enrich_record(before, depths.get(tic, []))
            flags_before = gaia_flag_digest(before, 1.0)["flags"]
            flags_after = gaia_flag_digest(after, 1.0)["flags"]
            changed = before != after
            plan["n_records_changed"] += changed
            plan["n_star_flag_lists_changed"] += flags_before != flags_after
            plan["n_stars_with_depth_capable_neighbour"] += after["gaia"][COUNT] > 0
            plan["files"].append({"tic_id": tic, "changed": changed,
                "before_sha256": sha(raw), "after_sha256": sha(json.dumps(after, indent=1).encode()) if changed else sha(raw),
                "before_semantic_sha256": semantic_sha(before), "after_semantic_sha256": semantic_sha(after),
                "depths_ppt": depths.get(tic, []), "flags_before": flags_before, "flags_after": flags_after})
        atomic(evidence, json.dumps(plan, indent=1).encode())
    if check_only and plan["status"] != "complete":
        raise RuntimeError("P8 neighbour-depth enrichment is incomplete; resume it before Stage B")
    if {item["tic_id"] for item in plan["files"]} != set(tics):
        raise RuntimeError("Neighbour-depth evidence does not cover the validated population")
    for item in plan["files"]:
        path = ROOT / "neighbours" / f"tic{item['tic_id']}.json"
        record = json.loads(path.read_bytes())
        current_sha = semantic_sha(record)
        if current_sha == item["after_semantic_sha256"]:
            continue
        if plan["status"] == "complete" or current_sha != item["before_semantic_sha256"]:
            raise RuntimeError(f"Neighbour cache changed since depth enrichment: {path}")
        updated = enrich_record(record, depths.get(item["tic_id"], []))
        if semantic_sha(updated) != item["after_semantic_sha256"]:
            raise RuntimeError(f"Enrichment differs from its recorded plan: {path}")
        atomic(path, json.dumps(updated, indent=1).encode())
    if plan["status"] != "complete":
        plan.update(status="complete", completed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        atomic(evidence, json.dumps(plan, indent=1).encode())
    return {k: v for k, v in plan.items() if k != "files"}


if __name__ == "__main__":
    print(json.dumps(ensure_context(), indent=1))
