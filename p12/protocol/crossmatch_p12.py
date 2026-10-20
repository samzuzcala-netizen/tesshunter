"""Snapshot-only copy of audit_p5.crossmatch_step with the P12 bare-TCE adapter.

The pure crossmatch operation is copied, not audit_p5's import-time writers.
Coordinates and ephemerides are explicitly supplied; this module never imports
audit_p5 or resolves coordinates through historical per-candidate records.
"""
import argparse
from collections import Counter
import json
import math

import pandas as pd

from p12_common import REPO, ROOT, DATA, utc, sha, read, write, append_jsonl
from catalog_adapter_p12 import cx, hard_stop_p10


def _finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def _f7(records, candidate_period=None):
    associations = []
    period = _finite(candidate_period)
    for row in records:
        association = {}
        for source, output in (("sectors", "run"), ("tce_plnt_num", "planet_number"),
                               ("tce_period", "period"), ("tce_model_snr", "model_snr")):
            value = row.get(source)
            if source == "sectors":
                if value is not None and str(value).strip():
                    association[output] = str(value)
            else:
                value = _finite(value)
                if value is not None:
                    association[output] = int(value) if source == "tce_plnt_num" else value
        reference = association.get("period")
        if period and period > 0 and reference and reference > 0:
            ratio = period / reference
            alias = min((1., 2., 3., .5, 1 / 3), key=lambda x: abs(ratio / x - 1))
            if abs(ratio / alias - 1) <= .01:
                association["alias_ratio"] = alias
                association["fractional_period_difference"] = abs(ratio / alias - 1)
        if association:
            associations.append(association)
    return {"ephemeris": "available" if records else "none", "associations": associations,
            "meaning": "SPOC TCE association"}


def crossmatch_step(candidate, *, catalog=None, ephemerides=None, redact_catalogue=False) -> dict:
    candidate = {"tic_id": int(candidate)} if isinstance(candidate, (int, str)) else dict(candidate)
    tic = int(candidate["tic_id"])
    if redact_catalogue:
        return dict(tic_id=tic, status="KNOWN_STATUS_REDACTED", checked_utc=utc(),
                    summary="Known-object status redacted for the preregistered negative route")
    cx.CATALOG_CACHE_DIR = DATA / "catalogs"
    cat = catalog if catalog is not None else cx.KnownObjectCatalog.load(
        refresh=False, offline=True, allow_stale=True)
    ra = next((value for name in ("ra_deg", "ra") if (value := _finite(candidate.get(name))) is not None), None)
    dec = next((value for name in ("dec_deg", "dec") if (value := _finite(candidate.get(name))) is not None), None)
    hs = hard_stop_p10(tic, ra, dec, catalog=cat, ephemerides=ephemerides,
        neighbour_tics=candidate.get("neighbour_tics"),
        resolve_neighbours=bool(candidate.get("resolve_neighbours", False)))
    rec = hs.to_dict()
    rec.update(catalog_stamp=cat.stamp(), checked_utc=utc())
    if rec["status"] == "FLAG" and rec.get("tic_matches") and {
            match["source"] for match in rec["tic_matches"]} == {"spoc_tce"}:
        rec["f7"] = _f7(getattr(hs, "ephemerides", []), candidate.get("period", candidate.get("period_days")))
    return rec


def _population():
    p8 = pd.read_csv(REPO / "data/survey/targets_p8.csv").assign(source_set="p8_2000")
    evaluated = pd.read_csv(REPO / "p10/part3/manifests/targets_evaluated.csv").assign(source_set="p10_436")
    population = pd.concat([p8, evaluated], ignore_index=True)
    if population.tic_id.duplicated().any():
        raise RuntimeError("Core source populations overlap")
    return population


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    cx.CATALOG_CACHE_DIR = DATA / "catalogs"
    cat = cx.KnownObjectCatalog.load(refresh=False, offline=True, allow_stale=True)
    sidecar = DATA / "catalogs/spoc_tce/spoc_tce.ephemerides.csv"
    seal = read(ROOT / "manifests/sidecar_p12.json")
    if sha(sidecar) != seal["sha256"]:
        raise RuntimeError("STOP-1: P12 sidecar differs from its seal")
    rows = json.loads(pd.read_csv(sidecar, dtype={"tceid": str}).to_json(orient="records", double_precision=15))
    lookup = {}
    for row in rows:
        lookup.setdefault(int(row["ticid"]), []).append(row)
    per_star = {}
    for row in _population().to_dict(orient="records"):
        tic = int(row["tic_id"])
        rec = crossmatch_step(row, catalog=cat, ephemerides=lookup.get(tic, []))
        rec["source_set"] = row["source_set"]
        rec["hard_stop_p12"] = "REJECT_NOVELTY" if rec["status"] == "REJECT" else rec["status"]
        per_star[str(tic)] = rec
        if lookup.get(tic):
            append_jsonl(ROOT / "manifests/exposure_ledger.jsonl", dict(utc=utc(), star=tic,
                stage="0d catalogue hard stop", path=sidecar.relative_to(REPO).as_posix(),
                reader="crossmatch_p12.py", prompt_of_origin="P12", content="catalogue ephemeris association only"))
    counts = dict(Counter(r["hard_stop_p12"] for r in per_star.values()))
    original = read(REPO / "p10/part3/results/hard_stop_p10.json")
    receipt = dict(utc=utc(), rules_version="p12.0", catalog_stamp=cat.stamp(), refreshed=False,
        per_star=per_star, counts=counts, source_counts={source: dict(Counter(
            r["hard_stop_p12"] for r in per_star.values() if r["source_set"] == source))
            for source in ("p8_2000", "p10_436")},
        inherited_counts={"original_flag_count": original["original_flag_count"],
                          "p8_unchanged_count": original["p8_unchanged_count"]},
        sidecar_sha256=sha(sidecar), source_sha256=sha(__file__))
    write(ROOT / "manifests/hard_stop_p12.json", receipt)
    print(json.dumps({"counts": counts, "source_counts": receipt["source_counts"]}), flush=True)


if __name__ == "__main__":
    main()
