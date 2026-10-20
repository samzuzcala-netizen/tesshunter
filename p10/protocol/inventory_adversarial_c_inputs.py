"""Inventory the existing 18 adversarial EBs' actual search candidates for 2c.

No search or C execution; no catalogue ephemeris is substituted for a candidate.
Retains every candidate so truth-matched selection cannot hide alias cases.
"""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import math

import resume_cadence as Q

RATIOS = {"1:1": 1., "2:1": 2., "1:2": .5, "3:1": 3., "1:3": 1/3, "3:2": 1.5, "2:3": 2/3}
FIELDS = ("planet_num", "period_days", "epoch_btjd", "duration_days", "depth_ppt", "snr")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = Q.REPO / "p10/results/stage_c_adversarial_input_inventory.json"
    require(not output.exists(), "Inventory exists; inspect it instead of replacing")
    Q.assert_source()
    target_path = Q.REPO / "data/adversarial/targets_v1.csv"
    targets = [r for r in csv.DictReader(target_path.open(encoding="utf-8", newline="")) if r["cls"] == "eb"]
    require(len(targets) == len({r["tic_id"] for r in targets}) == 18, "Wrong original EB set")
    rows, files = [], [target_path, Path(__file__), Q.REPO / "scripts/adversarial_vetting.py",
                       Q.REPO / "scripts/p8_decisions.py", Q.REPO / "scripts/p10_stage_c.py"]
    for target in targets:
        tic = int(target["tic_id"])
        source = Q.REPO / "data/adversarial/runs/v1" / f"eb_tic{tic}.json"
        data = Q.read(source)
        require(data["status"] == "ok" and data["cls"] == "eb" and data["tic_id"] == tic, "Unsettled original EB search")
        require(float(target["period_known"]) == data["period_known"], "Catalogue period provenance differs")
        require(len(data["planets"]) == data["n_planets"] > 0, "Missing original candidates")
        matched = data.get("matched") or {}
        require(matched and any(all(p[f] == matched[f] for f in FIELDS) for p in data["planets"]), "Matched summary is not an original candidate")
        lc_index = Q.REPO / "data/survey/audit_lc" / f"tic{tic}" / "index.json"
        require(lc_index.exists(), "Missing saved adversarial light-curve index")
        files.extend((source, lc_index))
        for candidate in data["planets"]:
            require(all(candidate[f] is not None and math.isfinite(float(candidate[f])) for f in FIELDS), "Nonfinite candidate inputs")
            require(all(float(candidate[f]) > 0 for f in ("period_days", "duration_days", "depth_ppt", "snr")), "Invalid candidate inputs")
            period = candidate["period_days"]
            fractions = {label: abs(period / (data["period_known"] * ratio) - 1) for label, ratio in RATIOS.items()}
            closest = min(fractions, key=fractions.get)
            alias = closest if fractions[closest] < .01 else "unrelated"
            key = f"tic{tic}_P{period:.4f}"
            rows.append({"candidate_id": f"eb_tic{tic}_candidate{candidate['planet_num']}", "tic_id": tic,
                         "name": target["name"], "key": key, "survey": {f: candidate[f] for f in FIELDS},
                         "catalogue_period_for_audit_only": data["period_known"],
                         "catalogue_epoch_for_audit_only_btjd": float(target["epoch_known_bjd"]) - 2457000,
                         "survey_to_catalogue_alias": alias, "closest_alias_fraction": fractions[closest],
                         "selected_by_original_truth_match": candidate["planet_num"] == matched["planet_num"],
                         "source": str(source.relative_to(Q.REPO)), "source_sha256": sha(source),
                         "original_search_data": {k: data.get(k) for k in ("data_source", "data_author", "n_sectors", "units_used")},
                         "native_lc_index": str(lc_index.relative_to(Q.REPO))})
    require(len({r["candidate_id"] for r in rows}) == len(rows), "Duplicate candidate identity")
    grouped = {}
    for row in rows:
        grouped.setdefault(row["key"], []).append(row["candidate_id"])
    collisions = {k: v for k, v in grouped.items() if len(v) > 1}
    aliases = [r for r in rows if r["survey_to_catalogue_alias"] in ("1:2", "2:1")]
    result = {"utc": Q.utc(), "n_hosts": 18, "n_survey_candidates": len(rows),
              "candidate_ratio_counts": dict(Counter(r["survey_to_catalogue_alias"] for r in rows)),
              "original_truth_matched_count": sum(r["selected_by_original_truth_match"] for r in rows),
              "half_double_cases": [{k: r[k] for k in ("candidate_id", "key", "survey_to_catalogue_alias", "selected_by_original_truth_match")} for r in aliases],
              "rounded_key_collisions": collisions,
              "findings": [
                  "The inherited P10 adversarial builder substitutes catalogue period/epoch/depth. Part 2c requires the stored survey-candidate inputs.",
                  "The original adversarial truth-matched summary alone omits an actual half-period candidate and an actual double-period candidate; retain the complete candidate list for the prescribed alias checks.",
                  "Distinct detected events can share the same rounded TIC/period key; separate workspaces by original candidate identity before execution.",
                  "The original adversarial search itself was catalogue-windowed and usually used up to three SPOC 120-s sectors with a 600-s search bin. These are existing development controls, not an independent blind or in-domain holdout."],
              "checks": {name: True for name in ("exact_original_18_EBs", "all_original_searches_successful",
                  "all_candidates_retained_with_original_fields", "finite_positive_inputs", "matched_summaries_reconcile",
                  "all_18_native_LC_indexes_present", "candidate_ids_unique")},
              "inputs_sha256": {str(p.relative_to(Q.REPO)): sha(p) for p in files}, "rows": rows,
              "scope": "Input/provenance inventory only. No C decision, alias rejection measurement or adoption has been made. No original records, source, thresholds or held-out inputs were changed."}
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "inputs_sha256")}, indent=2))


if __name__ == "__main__":
    main()
