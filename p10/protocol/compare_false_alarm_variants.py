"""Independently validate completed paired FA measurements and their P10 funnels.

Reads the exact 600 injections and 300 FA stars per variant. Reconstructs the
pre-gate from raw planet fields, checks hashes and saved preparation inputs, and
recomputes successful-job wall statistics. Does not run A/S or adopt a preset.
"""
from pathlib import Path
from datetime import datetime, timezone
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
PAIRED_FIELDS = ("injection", "injection_model", "star", "n_cadences_raw",
                 "baseline_days", "n_units", "prepare_counters")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate(variant):
    measurement_path = ROOT / f"p10/results/search_false_alarms_{variant}.json"
    m = json.loads(measurement_path.read_bytes())
    for name, digest in m["inputs"].items():
        require(sha(ROOT / name) == digest, "Measurement input changed: " + name)
    config = get_config(PRESETS[variant], record_traces=True).to_dict()
    require(m["config"] == config, "Measurement configuration differs from registered preset")
    injection_path = ROOT / f"p10/results/search_injections_{variant}.json"
    injection_measurement = json.loads(injection_path.read_bytes())
    previous_injection_hashes = {r["job_id"]: r["result_sha256"] for r in injection_measurement["rows"]}
    raw, pregate_ids, accepted_ids, fa_rows, all_rows = {}, set(), set(), [], []
    for kind, sample, row_field, count in (
        ("inj", ROOT / "data/survey/p10/injections_2b.csv", "injection_wall_rows", 600),
        ("fa", ROOT / "data/survey/completeness_sample_p8.csv", "false_alarm_rows", 300),
    ):
        samples = read_csv(sample)
        expected = {r["job_id"] if kind == "inj" else "tic" + r["tic_id"]: int(r["tic_id"]) for r in samples}
        rows = m[row_field]
        result_dir = ROOT / f"data/survey/runs/p10_2b/{variant}_{kind}/results"
        require(len(samples) == len(expected) == len(rows) == count
                and {r["job_id"] for r in rows} == set(expected)
                and {p.stem for p in result_dir.glob("*.json")} == set(expected), "Incomplete paired census")
        for row in rows:
            key = row["job_id"]
            path = result_dir / (key + ".json")
            r = json.loads(path.read_bytes())
            require(sha(path) == row["result_sha256"], "Raw result changed: " + str(path))
            require(r["status"] == "ok" and r.get("result") and r["job_id"] == key
                    and r["tic_id"] == expected[key] == row["tic_id"], "Unsettled or mismatched result")
            require(r["config"] == config, "Unexpected per-job configuration")
            require(math.isfinite(r["wall_s"]) and r["wall_s"] > 0 and r["wall_s"] == row["wall_s"], "Invalid wall")
            searches = r.get("searches") or []
            require(searches and all("budget_exhausted" in s for s in searches), "Missing budget instrumentation")
            require(row["n_partitions"] == len(searches)
                    and row["n_partitions_exhausted"] == sum(bool(s["budget_exhausted"]) for s in searches), "Budget count mismatch")
            if kind == "inj":
                require(previous_injection_hashes[key] == row["result_sha256"], "Prior injection measurement changed")
            else:
                planets = r["result"].get("planets") or []
                passed = [p for p in planets if float(p.get("stitch_snr") or 0) >= 7.1
                          and int(p.get("stitch_n_transits") or 0) >= 3 and bool(p.get("stitch_epoch_consistent"))]
                numbers = sorted(int(p["planet_num"]) for p in passed)
                require(row["n_accepted"] == len(planets) and row["n_pregate"] == len(passed)
                        and sorted(row["pregate_planet_numbers"]) == numbers, "Independent pre-gate differs")
                pregate_ids.update((r["tic_id"], n) for n in numbers)
                accepted_ids.update((r["tic_id"], int(p["planet_num"])) for p in planets)
                fa_rows.append(row)
            all_rows.append(row)
            raw[kind, key] = r
    funnel = ROOT / m["funnel_root"]
    require(funnel.resolve().is_relative_to((ROOT / "data/survey/p10").resolve()), "Funnel must be under P10")
    candidates, survivors = read_csv(funnel / "candidates.csv"), read_csv(funnel / "survivors.csv")
    identity = lambda r: (int(r["tic_id"]), int(r["planet_num"]))
    require(len(candidates) == len(accepted_ids) and set(map(identity, candidates)) == accepted_ids, "Candidate census differs")
    require(len(survivors) == len(pregate_ids) and set(map(identity, survivors)) == pregate_ids
            and {identity(r) for r in candidates if r["passes_pregate"] == "True"} == pregate_ids, "Survivor identities differ")
    require(len({f"tic{r['tic_id']}_P{float(r['period_days']):.4f}" for r in survivors}) == len(survivors),
            "Pre-gate candidates would collide in funnel job keys")
    s = m["summary"]
    walls = [r["wall_s"] for r in all_rows]
    ordered = sorted(walls); index = (len(ordered) - 1) * .9; lo = math.floor(index)
    p90 = ordered[lo] + (ordered[math.ceil(index)] - ordered[lo]) * (index - lo)
    parts = sum(r["n_partitions"] for r in all_rows)
    exhausted = sum(r["n_partitions_exhausted"] for r in all_rows)
    derived = {"n_injections": 600, "n_fa_stars": 300, "n_accepted_candidates": len(accepted_ids),
               "n_pregate_candidates": len(pregate_ids), "n_pregate_stars": len({t for t, n in pregate_ids}),
               "FA_pre": len(pregate_ids) / 300, "median_wall_s_all": statistics.median(walls),
               "median_wall_s_fa": statistics.median(r["wall_s"] for r in fa_rows), "p90_wall_s_all": p90,
               "sum_successful_job_hours": sum(walls) / 3600, "n_partitions": parts,
               "n_exhausted_partitions": exhausted, "budget_exhausted_partition_fraction": exhausted / parts,
               "jobs_with_any_exhaustion_fraction": sum(r["n_partitions_exhausted"] > 0 for r in all_rows) / 900}
    require(all(math.isclose(s[k], v, rel_tol=1e-12, abs_tol=1e-9) for k, v in derived.items()), "Independent summary differs")
    require(s["FA_S"] is None and s["FA_S_count"] is None and s["FA_S_status"].startswith("pending"), "FA_S is not explicitly pending")
    return m, raw, derived, {str(p.relative_to(ROOT)): sha(p) for p in (measurement_path, injection_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", choices=list(PRESETS))
    parser.add_argument("variant", choices=list(PRESETS))
    args = parser.parse_args()
    require(args.baseline != args.variant, "Two different variants required")
    out = ROOT / f"p10/results/search_false_alarms_{args.baseline}_{args.variant}_comparison.json"
    require(not out.exists(), "Comparison exists; review before replacing")
    a, b = validate(args.baseline), validate(args.variant)
    require(a[0]["config"]["ingest_key"] == b[0]["config"]["ingest_key"], "Different ingestion configurations")
    require(set(a[1]) == set(b[1]), "Unpaired raw result IDs")
    require(all(a[1][key].get(f) == b[1][key].get(f) for key in a[1] for f in PAIRED_FIELDS),
            "Injected inputs or preparation diagnostics differ between variants")
    diffs = sorted(k for k in set(a[0]["config"]) | set(b[0]["config"]) if a[0]["config"].get(k) != b[0]["config"].get(k))
    paired = []
    rows_b = {r["job_id"]: r for r in b[0]["false_alarm_rows"]}
    for x in a[0]["false_alarm_rows"]:
        y = rows_b[x["job_id"]]
        paired.append({"job_id": x["job_id"], "tic_id": x["tic_id"], "baseline": x, "variant": y})
    checks = {name: True for name in (
        "exact_600_plus_300_census_per_variant", "all_results_ok", "all_saved_result_hashes_match",
        "prior_injection_hashes_match", "all_saved_measurement_input_hashes_match", "registered_configs_match",
        "same_ingest_key", "identical_injected_inputs_and_preparation_fields",
        "independent_raw_pregate_counts_match", "candidate_and_survivor_identities_match",
        "unique_funnel_job_per_pregate_candidate", "independent_wall_statistics_match",
        "independent_budget_counts_and_fractions_match", "FA_S_explicitly_pending")}
    result = {"utc": datetime.now(timezone.utc).isoformat(), "baseline": args.baseline, "variant": args.variant,
              "scope": "All 900 completed searches per variant; FA_S remains unmeasured. No final variant adoption.",
              "checks": checks, "paired_fields": PAIRED_FIELDS, "config_difference_fields": {",".join(diffs): 900},
              "summaries": {args.baseline: a[2], args.variant: b[2]},
              "ratios_to_baseline": {"FA_pre": b[2]["FA_pre"] / a[2]["FA_pre"],
                                     "median_wall_s_all": b[2]["median_wall_s_all"] / a[2]["median_wall_s_all"]},
              "measurement_sha256": a[3] | b[3], "validator_sha256": sha(Path(__file__)), "paired_fa_rows": paired}
    with out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "paired_fa_rows"}, indent=2))


if __name__ == "__main__":
    main()
