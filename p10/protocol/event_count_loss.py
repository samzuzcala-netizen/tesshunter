"""Descriptive Part 2b event-count loss from existing P8 injection funnel records.

No fitting, threshold selection, new pipeline run, or writes to historical evidence.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
P8 = ROOT/"data/survey/p8"


def main():
    source = P8/"injection_outcomes_p8.csv"
    outcomes = list(csv.DictReader(source.open(encoding="utf-8")))
    selected = [r for r in outcomes if 10 <= float(r["period"]) <= 30]
    rows, missing, hashes = [], [], {}
    for r in selected:
        if r["recovered"] != "True":
            continue
        files = list((P8/"inj_funnel"/r["job_id"]/"stageA").glob("*.json"))
        if len(files) != 1:
            missing.append({"job_id":r["job_id"], "n_records":len(files)})
            continue
        path = files[0]
        raw = path.read_bytes()
        a = json.loads(raw)
        if a.get("decision") not in ("PASS", "FAIL"):
            missing.append({"job_id":r["job_id"], "decision":a.get("decision")})
            continue
        chosen = a["per_ephemeris"][a["chosen_ephemeris"]]
        criteria = a["criteria"]
        fails = criteria["kept_events_ge_3"] is False
        if fails != (chosen["n_kept"] < 3):
            raise RuntimeError("Recorded criterion and event count disagree: "+r["job_id"])
        rows.append({"job_id":r["job_id"], "period":float(r["period"]), "period_bin":int(r["period_bin"]),
                     "pregate":r["pregate"]=="True", "stageA":a["decision"],
                     "chosen_ephemeris":a["chosen_ephemeris"], "n_observed":chosen["n_observed"],
                     "n_excluded":chosen["n_excluded"], "n_kept":chosen["n_kept"],
                     "fails_three_kept_events":fails,
                     "crosses_below_three_after_exclusions":fails and chosen["n_observed"]>=3,
                     "only_failed_criterion":fails and all(v for k,v in criteria.items() if k!="kept_events_ge_3"),
                     "record":str(path.relative_to(ROOT))})
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    bins = []
    for b in sorted({int(r["period_bin"]) for r in selected}):
        all_bin = [r for r in selected if int(r["period_bin"])==b]
        measured = [r for r in rows if r["period_bin"]==b]
        bins.append({"p8_period_bin":b, "selected_period_min":min(float(r["period"]) for r in all_bin),
                     "selected_period_max":max(float(r["period"]) for r in all_bin),
                     "n_injected":len(all_bin), "n_recovered":sum(r["recovered"]=="True" for r in all_bin),
                     "n_stageA_measured":len(measured), "n_pregate_pass":sum(r["pregate"] for r in measured),
                     **{k:sum(r[k] for r in measured) for k in
                        ("fails_three_kept_events", "crosses_below_three_after_exclusions", "only_failed_criterion")},
                     "pregate_pass_and_crosses_below_three":sum(r["pregate"] and r["crosses_below_three_after_exclusions"] for r in measured)})
    result = {"utc":datetime.now(timezone.utc).isoformat(), "purpose":"descriptive only; no decision or protocol change",
              "selection":"10 <= injected period <= 30 d; original P8 period-bin labels, restricted to this interval",
              "interpretation":"The chosen saved ephemeris is used. Crossing from >=3 observed to <3 kept after exclusions is distinguished from all <3-kept failures. Criteria may fail together; no counterfactual recovery is inferred.",
              "source":str(source.relative_to(ROOT)), "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
              "n_selected_injections":len(selected), "missing_or_unsettled":missing, "bins":bins, "rows":rows,
              "stageA_sha256":hashes}
    out = ROOT/"p10/results"
    (out/"event_count_loss.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    lines = ["# Part 2b: 10-30 d event-count loss [M]", "", result["purpose"]+".", "", result["interpretation"], "",
             "| P8 bin / observed selected period span (d) | Injected | Recovered with A record | <3 kept | >=3 observed -> <3 kept | Only failing A criterion | Crossed and pre-gate passed |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for b in bins:
        lines.append(f"| {b['p8_period_bin']} / {b['selected_period_min']:.3f}-{b['selected_period_max']:.3f} | {b['n_injected']} | {b['n_stageA_measured']} | {b['fails_three_kept_events']} | {b['crosses_below_three_after_exclusions']} | {b['only_failed_criterion']} | {b['pregate_pass_and_crosses_below_three']} |")
    lines += ["", "Original P8 bin labels are retained; the spans are the minimum and maximum selected injected periods, not new bin edges.",
              "Missing/unsettled recovered records: "+str(len(missing))+". Per-record counts and input hashes are in `event_count_loss.json`.",
              "The three-kept-events threshold remains unchanged.", ""]
    (out/"event_count_loss.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"bins":bins, "missing":missing},indent=2))


if __name__ == "__main__":
    main()
