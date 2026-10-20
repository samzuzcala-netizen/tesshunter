"""Apply frozen Part 2b selection only to all four complete paired measurements.

Revalidate saved searches, ranking witnesses and A/S records without running
searches or rewriting evidence. This chooses search fields; Part 2d creates
survey_p10 and freezes p10.0 after the independent Stage C validation.
"""
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
import csv
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
PRESETS = {"a": "survey_p8", "b": "survey_p10_budget", "c": "survey_p10_slots",
           "d": "survey_p10_rank", "e": "survey_p10_both"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def choose_variant(rows):
    """Exact count-based recovery/FA boundaries, and the measured median wall."""
    require(set("abc") <= set(rows) and len(rows) == 4, "Four complete variants required")
    denominator = rows["a"]["n_R_7_15"]
    rates = {}
    for variant, row in rows.items():
        require(variant in PRESETS and row["n_injections"] == 600
                and row["n_fa_stars"] == 300 and row["FA_S_complete"] is True,
                "Complete 600-injection/300-FA search and A/S census required")
        for field in ("n_R_7_15", "recovered_R_7_15", "n_pregate", "FA_S_count"):
            require(type(row[field]) is int and row[field] >= 0, "Invalid count: " + field)
        require(row["n_R_7_15"] == denominator and 0 < denominator <= 600
                and row["recovered_R_7_15"] <= denominator
                and row["FA_S_count"] <= row["n_pregate"], "Unpaired or inconsistent counts")
        require(math.isfinite(row["median_wall_s"]) and row["median_wall_s"] > 0,
                "Finite positive combined median wall required")
        rates[variant] = Fraction(row["recovered_R_7_15"], denominator)
    fourth = "e" if rates["b"] > rates["c"] else "d"
    require(set(rows) == set("abc" + fourth), "Fourth variant contradicts frozen b/c branch")
    base = rows["a"]
    eligibility = {}
    for variant, row in rows.items():
        fa_ok = 2 * row["n_pregate"] <= 3 * base["n_pregate"]
        wall_ok = row["median_wall_s"] <= 3 * base["median_wall_s"]
        eligibility[variant] = {"FA_pre_within_1_5x": fa_ok, "wall_within_3x": wall_ok,
                                "eligible": fa_ok and wall_ok,
                                "gain_percentage_points": float(100 * (rates[variant] - rates["a"]))}
    eligible = [v for v in rows if eligibility[v]["eligible"]]
    best = min(eligible, key=lambda v: (-rates[v], rows[v]["median_wall_s"], v))
    meets_gain = rates[best] - rates["a"] >= Fraction(5, 100)
    chosen = best if meets_gain else "a"
    return {"variant": chosen, "preset": PRESETS[chosen], "fourth_variant": fourth,
            "best_eligible_variant": best, "improvement_at_least_5_percentage_points": meets_gain,
            "eligibility": eligibility,
            "reason": "Highest eligible P8 recovery with at least five percentage points gain"
                      if meets_gain else "No eligible variant reaches five percentage points gain",
            "FA_S_role": "Required completed reported measurement; not an eligibility threshold",
            "freeze_status": "Search choice complete; p10.0/survey_p10 freeze waits for Part 2c and 2d"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def main():
    sys.path.insert(0, str(ROOT / "p10/protocol"))
    import compare_injection_variants as I
    import compare_false_alarm_variants as C
    import run_false_alarm_funnels as F

    output = ROOT / "p10/results/search_capacity_final.json"
    markdown = output.with_suffix(".md")
    require(not output.exists() and not markdown.exists(), "Final comparison exists; review it without overwriting")
    F.Q.assert_source()
    F.assert_free()
    require(not F.Q.tls_owners() and not F.LOCK.exists()
            and not (F.Q.RECEIPTS / "native_raw_queue.lock").exists(), "Scientific queues must be closed")
    queue = read(F.STATE)
    require(queue["status"] == "FA_S_complete_review_required", "FA queue not complete")
    variants = queue["variants"]
    require(len(variants) == len(set(variants)) == 4, "Wrong queue variant census")
    sample = ROOT / "data/survey/p10/injections_2b.csv"
    with sample.open(encoding="utf-8", newline="") as stream:
        samples = list(csv.DictReader(stream))
    expected = {r["job_id"]: int(r["tic_id"]) for r in samples}
    require(len(samples) == len(expected) == 600, "Seeded sample changed")
    snr_path = ROOT / "data/survey/p8/injection_outcomes_p8.csv"
    with snr_path.open(encoding="utf-8", newline="") as stream:
        snr = {r["job_id"]: float(r["snr_expected"]) for r in csv.DictReader(stream)}
    rows, metrics, provenance = {}, {}, {}
    baseline = None
    require(variants[0] == "a", "Baseline must be first")
    for variant in variants:
        injection = I.validate(variant, expected, snr, sample)
        search = C.validate(variant)
        if baseline is None:
            baseline = search
        require(search[0]["config"]["ingest_key"] == baseline[0]["config"]["ingest_key"]
                and set(search[1]) == set(baseline[1]), "Inputs must be paired")
        require(all(search[1][k].get(f) == baseline[1][k].get(f)
                    for k in search[1] for f in C.PAIRED_FIELDS), "Prepared inputs differ")
        secondary_path = ROOT / f"p10/results/search_false_alarm_secondary_{variant}.json"
        require(secondary_path.is_file(), "Missing complete FA_S measurement: " + variant)
        secondary = F.summarize(variant)  # Existing-file branch verifies every saved field/hash.
        root, _, _, jobs = F.configure(variant)
        for stage, stage_jobs in (("A", jobs), ("S", F.F.secondary_jobs())):
            records, hashes = F.read_phase(root, stage, stage_jobs)
            receipt_path = F.Q.RECEIPTS / f"fa_{variant}_{stage}_validation.json"
            receipt = read(receipt_path)
            require(receipt["record_sha256"] == hashes and all(receipt["checks"].values())
                    and receipt["n_expected"] == receipt["n_complete"] == len(records),
                    "Completed phase receipt differs: " + variant + stage)
            provenance[str(receipt_path.relative_to(ROOT))] = sha(receipt_path)
        b = injection[0]["summary"]["bins"]["R_7_15"]
        rows[variant] = {"n_injections": search[2]["n_injections"], "n_fa_stars": secondary["n_fa_stars"],
                         "n_R_7_15": b["n"], "recovered_R_7_15": b["recovered_p8"],
                         "n_pregate": secondary["n_pregate"], "FA_S_count": secondary["FA_S_count"],
                         "FA_S_complete": True, "median_wall_s": search[2]["median_wall_s_all"]}
        metrics[variant] = {"preset": PRESETS[variant], "injections": injection[0]["summary"],
                            "search": search[2], "secondary": {k: v for k, v in secondary.items()
                                                               if k != "record_sha256"},
                            "ranking_witnesses": f"p10/results/search_injections_{variant}.json"}
        provenance.update(search[3])
        provenance[str(secondary_path.relative_to(ROOT))] = sha(secondary_path)
        print(f"Validated {variant}: 600 injections, 300 FA stars, all A/S records", flush=True)
    decision = choose_variant(rows)
    for path in (sample, snr_path, F.STATE, Path(__file__), Path(I.__file__), Path(C.__file__), Path(F.__file__)):
        provenance[str(path.relative_to(ROOT))] = sha(path)
    checks = {k: True for k in ("exact_four_variant_search_and_funnel_census",
              "all_saved_measurement_and_record_hashes_match", "registered_configurations",
              "same_900_inputs_and_preparation_diagnostics", "reconstructed_pregate_and_combined_wall",
              "verified_epoch_matched_ranking_witnesses", "complete_A_and_bound_S",
              "seeded_A_failure_sample_excluded_from_FA_S", "frozen_fourth_variant_branch",
              "frozen_count_and_wall_choice", "no_active_scientific_output_owners")}
    result = {"utc": datetime.now(timezone.utc).isoformat(), "scope": "Final Part 2b only",
              "checks": checks, "decision": decision, "selection_inputs": rows,
              "variants": metrics, "input_sha256": provenance,
              "event_count_loss_report": "p10/results/event_count_loss.json",
              "caveats": ["P8 matching is the fixed primary metric; P9 event matching is secondary.",
                          "FA_S counts A+S candidates, not distinct stars; no B/C is run here.",
                          "Median wall uses all 900 successful saved job walls, not queue duration.",
                          "A ranking witness does not prove an alternate search would recover that injection.",
                          "The historical search-only measurements remain unchanged with FA_S pending there."]}
    lines = ["# Part 2b: final paired search comparison", "", f"Measured {result['utc']}.", "",
             f"The frozen rule selects **{decision['variant']} ({decision['preset']})**. "
             "The p10.0/survey_p10 freeze follows completion of Part 2c in Part 2d.", "",
             "All variants contain the same 600 seeded injections and full 300-star FA set. "
             "All searches and A/S records are complete and validated.", "",
             "| Variant | R7–15 P8 | R7–15 P9 | R15–30 P8 | R15–30 P9 | FA_pre | FA_S | Median wall (s) | Exhausted partitions |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for v in variants:
        m = metrics[v]; s = m["search"]; a = m["secondary"]; bins = m["injections"]["bins"]
        values = [f"{bins[name][field]}/{bins[name]['n']}" for name in ("R_7_15", "R_15_30")
                  for field in ("recovered_p8", "matched_p9")]
        lines.append(f"| {v} | {' | '.join(values)} | {s['n_pregate_candidates']}/300 = {s['FA_pre']:.6f} "
                     f"| {a['FA_S_count']}/300 | {s['median_wall_s_all']:.6f} "
                     f"| {s['n_exhausted_partitions']}/{s['n_partitions']} |")
    chosen = rows[decision["variant"]]; base = rows["a"]
    lines += ["", f"Chosen gain: {decision['eligibility'][decision['variant']]['gain_percentage_points']:.8f} percentage points. "
              f"FA_pre ratio to a: {chosen['n_pregate']/base['n_pregate']:.8f} (limit 1.5); "
              f"median-wall ratio: {chosen['median_wall_s']/base['median_wall_s']:.8f} (limit 3). "
              "R7–15(b) exceeds R7–15(c), so e was the prescribed fourth variant; d was not run.", "",
              "FA_S for a/b/e has equal counts, but e's surviving candidate identities differ. "
              "The seeded 10% A-failure sample is excluded from every FA_S count.", "",
              "| Variant | Non-recovered injections | Epoch-matched ranking losses | Witnesses | Period-near losses |",
              "|---|---:|---:|---:|---:|"]
    for v in variants:
        s = metrics[v]["injections"]
        lines.append(f"| {v} | {600-s['status_counts_p8']['recovered']} | "
                     f"{s['ranking_lost_injections_p8_epoch_match']} | {s['n_ranking_witnesses']} "
                     f"| {s['ranking_period_near_injections']} |")
    lines += ["", "Every competing score, all gate-confirmed witnesses and input hashes are retained in "
              "`search_injections_<variant>.json`; the corresponding paired comparison files report individual gains/losses. "
              "The final JSON includes all measurements and provenance hashes.", "",
              "The existing `event_count_loss.{json,md}` reports the 10–30 d event-count mechanism without a decision: "
              "282 recovered injections, 13 fail the kept-event count, 11 cross below three after exclusions, "
              "7 of those passed the pre-gate, and only 1 has the event count as its sole A failure. "
              "These mechanisms overlap. The three-event threshold is unchanged.", ""]
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    with markdown.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
