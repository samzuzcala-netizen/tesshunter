"""Measure a complete P10 injection variant while other queues remain protected.

Uses the inherited P8 and P9 match functions, with corrected trace reconstruction.
Does not inspect partial FA data, adopt a variant, or modify inherited source.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse
import csv
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("LIGHTKURVE_CACHE",str(ROOT/"data/cache/lightkurve"))
os.environ.setdefault("TESSHUNTER_OFFLINE","1")
os.environ.setdefault("PYTHONIOENCODING","utf-8")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE","1")
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"src"))
import numpy as np
import p10_search_capacity as C
from analyze_completeness import classify
from search_trace_audit import audit_job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant",choices=list("abcde"))
    args = parser.parse_args()
    run = C.RUNS/(args.variant+"_inj")
    out = ROOT/"p10/results"/("search_injections_"+args.variant+".json")
    if out.exists():
        raise RuntimeError("Measurement already exists; review before replacing: "+str(out))
    expected_file = ROOT/"data/survey/p10/injections_2b.csv"
    expected = [r["job_id"] for r in csv.DictReader(expected_file.open(encoding="utf-8"))]
    paths = sorted((run/"results").glob("*.json"))
    if len(expected)!=600 or {p.stem for p in paths}!=set(expected):
        raise RuntimeError("Requires the exact complete 600-record injection census")
    outcomes = {r["job_id"]:r for r in C.outcomes()}
    rows, errors = [], []
    for index,path in enumerate(paths,1):
        record = json.loads(path.read_bytes())
        if record.get("status")!="ok" or record.get("job_id")!=path.stem or not record.get("result"):
            raise RuntimeError("Unsettled injection: "+str(path))
        p8 = classify(record)
        p9 = C.p9_match(record)
        row = {"job_id":record["job_id"],"tic_id":record["tic_id"],
               "snr_expected":float(outcomes[record["job_id"]]["snr_expected"]),
               "p8_status":p8["status"],"p8_match":p8,"p9_match":p9,
               "recovered_p8":p8["status"]=="recovered","matched_p9":p9["matched"],
               "wall_s":record["wall_s"],"n_partitions":len(record.get("searches") or []),
               "n_partitions_exhausted":sum(bool(s.get("budget_exhausted")) for s in record.get("searches") or []),
               "result_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
        if not row["recovered_p8"]:
            try:
                audit = audit_job(run,record,16 if args.variant in "cde" else 8,"snr" if args.variant in "de" else "composite")
                row["ranking"] = {"diagnostic":audit["diagnostic"],"trace_sha256":audit["trace_sha256"],"log_sha256":audit["log_sha256"],
                                  "period_near_witnesses":audit["witnesses"],
                                  "witnesses":[w for w in audit["witnesses"] if w["injection_epoch_match_p8"]]}
                row["ranking"]["lost_to_ranking"] = bool(row["ranking"]["witnesses"])
            except Exception as exc:
                errors.append({"job_id":record["job_id"],"error":str(exc)})
        rows.append(row)
        if index%100==0:
            print(datetime.now(timezone.utc).isoformat(),args.variant,index,"of",len(paths),flush=True)
    bins = {}
    for name,(lo,hi) in C.BINS.items():
        selected = [r for r in rows if lo<=r["snr_expected"]<hi]
        bins[name] = {"n":len(selected),"recovered_p8":sum(r["recovered_p8"] for r in selected),
                      "matched_p9":sum(r["matched_p9"] for r in selected)}
        bins[name]["rate_p8"] = bins[name]["recovered_p8"]/len(selected) if selected else None
        bins[name]["rate_p9"] = bins[name]["matched_p9"]/len(selected) if selected else None
    lost = [r for r in rows if r.get("ranking",{}).get("lost_to_ranking")]
    period_only = [r for r in rows if r.get("ranking",{}).get("period_near_witnesses")]
    n_parts = sum(r["n_partitions"] for r in rows)
    summary = {"n_injections":len(rows),"status_counts_p8":dict(Counter(r["p8_status"] for r in rows)),
               "bins":bins,"ranking_lost_injections_p8_epoch_match":len(lost),"ranking_period_near_injections":len(period_only),
               "n_ranking_witnesses":sum(len(r["ranking"]["witnesses"]) for r in lost),
               "median_injection_wall_s":float(np.median([r["wall_s"] for r in rows])),
               "budget_exhausted_partition_fraction":sum(r["n_partitions_exhausted"] for r in rows)/n_parts,
               "n_partitions":n_parts,"n_ranking_errors":len(errors)}
    result = {"utc":datetime.now(timezone.utc).isoformat(),"variant":args.variant,"preset":C.VARIANTS[args.variant],
              "scope":"Complete injection set only. FA_pre, FA_S, combined injection+FA wall and final adoption remain unmeasured here.",
              "matching":"Inherited P8 classify and P9 match_signal on the P8 stars' harmonised 200-s cadence times. These are BLS candidate durations, not TLS durations; all raw matching inputs remain unchanged.",
              "ranking_definition":"Non-recovered injection with a trace candidate matching its P8 period and epoch windows, confirmed PASS after all internal gates, and a different logged winning period. Period-near witnesses failing the P8 epoch window are reported separately, never called verified lost injections. A loss witness is not proof that an alternate overall search would recover the injection.",
              "expected_input_sha256":hashlib.sha256(expected_file.read_bytes()).hexdigest(),
              "summary":summary,"ranking_errors":errors,"rows":rows}
    out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2),flush=True)
    if errors:
        raise SystemExit("Ranking audit has unresolved records")


if __name__ == "__main__":
    main()
