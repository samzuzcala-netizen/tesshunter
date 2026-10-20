"""Validate and compare two settled injection measurements without adopting rules.

Rechecks the exact seeded census, raw-result and ranking-evidence hashes,
registered configurations, injected inputs and saved preparation diagnostics.
Writes a new receipt only; does not execute searches or change their inputs.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tesshunter.survey import get_config

PRESETS = {"a": "survey_p8", "b": "survey_p10_budget", "c": "survey_p10_slots",
           "d": "survey_p10_rank", "e": "survey_p10_both"}
BINS = {"R_7_15": (7, 15), "R_15_30": (15, 30), "other_6_7": (6, 7)}
PAIRED_FIELDS = ("injection", "injection_model", "star", "n_cadences_raw",
                 "baseline_days", "n_units", "prepare_counters")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate(variant, expected, snr, sample):
    path = ROOT / f"p10/results/search_injections_{variant}.json"
    measurement = read(path)
    rows = {r["job_id"]: r for r in measurement["rows"]}
    require(len(rows) == len(measurement["rows"]) == 600 and set(rows) == set(expected),
            "Measurement must have exactly the 600 seeded IDs")
    require(measurement["expected_input_sha256"] == sha(sample), "Seeded input hash changed")
    require(not measurement["ranking_errors"], "Unresolved ranking errors")
    run = ROOT / f"data/survey/runs/p10_2b/{variant}_inj"
    require({p.stem for p in (run / "results").glob("*.json")} == set(expected),
            "Raw result census differs from seeded sample")
    config = get_config(PRESETS[variant], record_traces=True).to_dict()
    raw = {}
    for key, row in rows.items():
        result_path = run / "results" / (key + ".json")
        require(sha(result_path) == row["result_sha256"], f"Result changed: {variant}/{key}")
        record = read(result_path)
        require(record["status"] == "ok" and record.get("result")
                and record["job_id"] == key and record["tic_id"] == expected[key],
                f"Unsettled or mismatched result: {variant}/{key}")
        require(record["config"] == config, f"Unexpected preset: {variant}/{key}")
        require(row["snr_expected"] == snr[key], f"Unpaired SNR: {variant}/{key}")
        require(math.isfinite(record["wall_s"]) and record["wall_s"] > 0
                and record["wall_s"] == row["wall_s"], f"Invalid wall: {variant}/{key}")
        searches = record.get("searches") or []
        require(searches and all("budget_exhausted" in s for s in searches),
                f"Missing partition instrumentation: {variant}/{key}")
        require(row["n_partitions"] == len(searches)
                and row["n_partitions_exhausted"] == sum(bool(s["budget_exhausted"]) for s in searches),
                f"Budget count mismatch: {variant}/{key}")
        require(row["recovered_p8"] == (row["p8_status"] == "recovered")
                and row["matched_p9"] == row["p9_match"]["matched"], "Inconsistent matching fields")
        if not row["recovered_p8"]:
            ranking = row["ranking"]
            require(sha(run / "traces" / (key + ".jsonl")) == ranking["trace_sha256"]
                    and sha(run / "logs" / (key + ".log")) == ranking["log_sha256"],
                    f"Ranking evidence changed: {variant}/{key}")
            require(ranking["witnesses"] == [w for w in ranking["period_near_witnesses"]
                                            if w["injection_epoch_match_p8"]]
                    and ranking["lost_to_ranking"] == bool(ranking["witnesses"]),
                    "Ranking witness attribution mismatch")
        raw[key] = record
    summary = measurement["summary"]
    require(summary["n_injections"] == 600
            and summary["status_counts_p8"] == dict(Counter(r["p8_status"] for r in rows.values()))
            and summary["median_injection_wall_s"] == statistics.median(r["wall_s"] for r in rows.values()),
            "Injection summary count or independent median mismatch")
    parts = sum(r["n_partitions"] for r in rows.values())
    exhausted = sum(r["n_partitions_exhausted"] for r in rows.values())
    require(summary["n_partitions"] == parts
            and summary["budget_exhausted_partition_fraction"] == exhausted / parts, "Budget summary mismatch")
    rankings = [r["ranking"] for r in rows.values() if not r["recovered_p8"]]
    require(summary["ranking_lost_injections_p8_epoch_match"] == sum(bool(r["witnesses"]) for r in rankings)
            and summary["ranking_period_near_injections"] == sum(bool(r["period_near_witnesses"]) for r in rankings)
            and summary["n_ranking_witnesses"] == sum(len(r["witnesses"]) for r in rankings),
            "Ranking summary mismatch")
    for name, (lo, hi) in BINS.items():
        selected = [r for r in rows.values() if lo <= r["snr_expected"] < hi]
        if name in summary["bins"]:
            b = summary["bins"][name]
            require(b["n"] == len(selected)
                    and b["recovered_p8"] == sum(r["recovered_p8"] for r in selected)
                    and b["matched_p9"] == sum(r["matched_p9"] for r in selected)
                    and b["rate_p8"] == b["recovered_p8"] / b["n"]
                    and b["rate_p9"] == b["matched_p9"] / b["n"], "Bin summary mismatch")
    return measurement, rows, raw, config, sha(path), exhausted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", choices=list(PRESETS))
    parser.add_argument("variant", choices=list(PRESETS))
    args = parser.parse_args()
    require(args.baseline != args.variant, "Two different variants are required")
    out = ROOT / f"p10/results/search_injections_{args.baseline}_{args.variant}_comparison.json"
    require(not out.exists(), "Comparison already exists; review before replacing")
    sample = ROOT / "data/survey/p10/injections_2b.csv"
    with sample.open(encoding="utf-8", newline="") as stream:
        sample_rows = list(csv.DictReader(stream))
    expected = {r["job_id"]: int(r["tic_id"]) for r in sample_rows}
    require(len(sample_rows) == len(expected) == 600, "Expected exact seeded 600-record input")
    snr_file = ROOT / "data/survey/p8/injection_outcomes_p8.csv"
    with snr_file.open(encoding="utf-8", newline="") as stream:
        snr = {r["job_id"]: float(r["snr_expected"]) for r in csv.DictReader(stream)}
    a = validate(args.baseline, expected, snr, sample)
    b = validate(args.variant, expected, snr, sample)
    differences = sorted(k for k in set(a[3]) | set(b[3]) if a[3].get(k) != b[3].get(k))
    require(a[3]["ingest_key"] == b[3]["ingest_key"], "Ingest configuration differs")
    paired_rows = []
    for key in sorted(expected):
        require(all(a[2][key][f] == b[2][key][f] for f in PAIRED_FIELDS),
                f"Injected inputs or preparation diagnostics differ: {key}")
        x, y = a[1][key], b[1][key]
        paired_rows.append({"job_id": key, "snr_expected": snr[key],
                            "p8_baseline": x["p8_status"], "p8_variant": y["p8_status"],
                            "p9_baseline": x["matched_p9"], "p9_variant": y["matched_p9"],
                            "result_sha256_baseline": x["result_sha256"],
                            "result_sha256_variant": y["result_sha256"]})
    bins = {}
    for name, (lo, hi) in BINS.items():
        selected = [r for r in paired_rows if lo <= r["snr_expected"] < hi]
        bins[name] = {"n": len(selected),
                      "p8_gained": sum(r["p8_baseline"] != "recovered" and r["p8_variant"] == "recovered" for r in selected),
                      "p8_lost": sum(r["p8_baseline"] == "recovered" and r["p8_variant"] != "recovered" for r in selected),
                      "p9_gained": sum(not r["p9_baseline"] and r["p9_variant"] for r in selected),
                      "p9_lost": sum(r["p9_baseline"] and not r["p9_variant"] for r in selected)}
    checks = {name: True for name in (
        "exact_seeded_census", "seeded_input_hash_unchanged", "all_raw_results_ok_and_hashes_unchanged",
        "all_configs_match_registered_presets", "saved_snr_matches_p8_outcomes", "same_ingest_key",
        "identical_injection_and_preparation_fields", "ranking_evidence_hashes_unchanged",
        "ranking_epoch_attribution_and_counts_match", "matching_fields_consistent",
        "independent_counts_medians_and_budget_fractions_match", "bin_counts_and_rates_match")}
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "baseline": args.baseline, "variant": args.variant,
               "scope": "Completed injection measurements only; no false-alarm inference, combined-wall eligibility or final adoption.",
               "checks": checks, "paired_fields": PAIRED_FIELDS,
               "config_difference_fields": {",".join(differences): 600}, "bins": bins,
               "exhausted_partitions": {args.baseline: a[5], args.variant: b[5]},
               "measurement_sha256": {args.baseline: a[4], args.variant: b[4]},
               "inputs_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (sample, snr_file, Path(__file__))},
               "changed_classifications": [r for r in paired_rows if r["p8_baseline"] != r["p8_variant"]
                                           or r["p9_baseline"] != r["p9_variant"]], "paired_rows": paired_rows}
    with out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: receipt[k] for k in ("baseline", "variant", "checks", "config_difference_fields",
                                             "bins", "exhausted_partitions")}, indent=2))


if __name__ == "__main__":
    main()
