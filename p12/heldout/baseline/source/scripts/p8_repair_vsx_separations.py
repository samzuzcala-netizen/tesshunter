"""Repair only P8 VSX display separations, preserving objects, counts and vetting flags.

The saved plan contains before/after hashes and each replacement. Atomic writes and
that plan allow a desktop interruption to resume without losing the original evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
import p8_neighbours as N
from tesshunter.star_vet import gaia_flag_digest

ROOT = REPO / "data/survey/p8"
EVIDENCE = ROOT / "vsx_separation_repair_p8.json"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic(path, raw):
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_bytes(raw)
    tmp.replace(path)


def replacements(target, objects):
    corrected = N.vsx_with_separations(target, objects)
    return [{"index": i, "name": old.get("Name"), "old": old.get("sep_arcsec"), "new": new["sep_arcsec"]}
            for i, (old, new) in enumerate(zip(objects, corrected)) if old.get("sep_arcsec") != new["sep_arcsec"]]


def apply_to_record(record, item):
    for fix in item["replacements"]:
        objects = record["vsx"]["objects"] if item["kind"] == "neighbour" else record[str(fix["tic_id"])]
        obj = objects[fix["index"]]
        if obj.get("Name") != fix["name"] or obj.get("sep_arcsec") != fix["old"]:
            raise RuntimeError(f"Object changed since the repair plan: {item['path']}")
        obj["sep_arcsec"] = fix["new"]


def build_plan():
    targets = {int(r["tic_id"]): r for r in N.load_targets(str(REPO / "data/survey/targets_p8.csv"))}
    plan = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": "planned",
            "reason": "The old bulk reader treated VizieR _r as degrees. Separations are now derived from target and VSX coordinates.",
            "n_neighbour_records_checked": 0, "n_vsx_objects": 0, "n_vsx_hosts": 0,
            "n_flag_differences": 0, "flag_check_depth_ppt": 1.0, "files": []}
    paths = [(ROOT / "neighbours" / f"tic{tic}.json", "neighbour", tic) for tic in targets]
    paths += [(p, "bulk", None) for p in sorted((ROOT / "neighbours_bulk").glob("vsx_*.json"))]
    for path, kind, tic in paths:
        raw = path.read_bytes()
        before = json.loads(raw)
        if kind == "neighbour":
            objects = (before.get("vsx") or {}).get("objects", [])
            fixes = replacements(targets[tic], objects)
            plan["n_neighbour_records_checked"] += 1
            plan["n_vsx_objects"] += len(objects)
            plan["n_vsx_hosts"] += bool(objects)
        else:
            fixes = [dict(fix, tic_id=int(k)) for k, objects in before.items() if int(k) in targets
                     for fix in replacements(targets[int(k)], objects)]
        item = {"path": str(path.relative_to(REPO)), "kind": kind, "replacements": fixes}
        after = copy.deepcopy(before)
        apply_to_record(after, item)
        if kind == "neighbour" and gaia_flag_digest(before, 1.0) != gaia_flag_digest(after, 1.0):
            raise RuntimeError(f"Repair would change the star-vetting digest: {path}")
        if fixes:
            item.update(before_sha256=digest(raw), after_sha256=digest(json.dumps(after, indent=1 if kind == "neighbour" else 0).encode()))
            plan["files"].append(item)
    plan["n_neighbour_files_changed"] = sum(f["kind"] == "neighbour" for f in plan["files"])
    plan["n_neighbour_separations_changed"] = sum(len(f["replacements"]) for f in plan["files"] if f["kind"] == "neighbour")
    plan["n_bulk_files_changed"] = sum(f["kind"] == "bulk" for f in plan["files"])
    return plan


def main():
    if EVIDENCE.exists():
        plan = json.loads(EVIDENCE.read_bytes())
    else:
        plan = build_plan()
        atomic(EVIDENCE, json.dumps(plan, indent=1).encode())
    for item in plan["files"]:
        path = REPO / item["path"]
        raw = path.read_bytes()
        if plan["status"] == "complete":
            # Later candidate-depth enrichment can legitimately alter other
            # fields. Keep this original repair evidence and check its fields.
            record = json.loads(raw)
            for fix in item["replacements"]:
                objects = record["vsx"]["objects"] if item["kind"] == "neighbour" else record[str(fix["tic_id"])]
                obj = objects[fix["index"]]
                if obj.get("Name") != fix["name"] or obj.get("sep_arcsec") != fix["new"]:
                    raise RuntimeError(f"A repaired separation changed: {path}")
            continue
        if digest(raw) == item["after_sha256"]:
            continue
        if digest(raw) != item["before_sha256"]:
            raise RuntimeError(f"File changed since repair planning: {path}")
        record = json.loads(raw)
        apply_to_record(record, item)
        updated = json.dumps(record, indent=1 if item["kind"] == "neighbour" else 0).encode()
        if digest(updated) != item["after_sha256"]:
            raise RuntimeError(f"Repair differs from the plan: {path}")
        atomic(path, updated)
    if plan["status"] != "complete":
        plan.update(status="complete", completed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        atomic(EVIDENCE, json.dumps(plan, indent=1).encode())
    print(json.dumps({k: v for k, v in plan.items() if k != "files"}, indent=1))


if __name__ == "__main__":
    main()
