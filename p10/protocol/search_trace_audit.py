"""Recover actual detection passes and all-gate outcomes from inherited P10 traces.

The inherited recorder increments `pass` for local alias BLS calls too. Its
pass field is retained as evidence, but cannot identify competing candidates.
Actual broad calls are identified by the preset's top_n and 40000-point cap.
The pipeline's PASS log is emitted after gates 2-7 and the artifact check.
No search result, trace, log, threshold, or scientific source is changed.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_bytes())


def reconstructed(trace, log, top_n):
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()]
    counts, groups, recorded = Counter(), defaultdict(list), Counter()
    for event in events:
        part = event["partition"]
        if event["event"] == "broad_bls":
            settings = event["settings"]
            if settings.get("top_n") == top_n and settings.get("n_max") == 40000:
                counts[part] += 1
                groups[(part,counts[part])]
        elif event["event"] == "alias":
            if not counts[part]:
                raise RuntimeError("Alias precedes broad pass: "+str(trace))
            groups[(part,counts[part])].append(event)
            recorded[(part,event["pass"])] += 1
    text = log.read_text(encoding="utf-8")
    text = text.rsplit("=== attempt ",1)[-1]
    part, detection_pass = None, None
    passed, winners, log_groups = defaultdict(Counter), {}, set()
    for line in text.splitlines():
        match = re.search(r"search_light_curve: TIC \d+ (\w+)\s",line)
        if match:
            part = match[1]
        match = re.search(r"Detection pass (\d+) \(planet",line)
        if match:
            detection_pass = int(match[1])
            log_groups.add((part,detection_pass))
        match = re.search(r"\[([\d.]+) d -> ([\d.]+) d\].*\bPASS\s*$",line)
        if match:
            passed[(part,detection_pass)][(match[1],match[2])] += 1
        match = re.search(r"Accepted planet \d+:.*?P = ([\d.]+) d",line)
        if match:
            winners[(part,detection_pass)] = float(match[1])
    # A budget exit can log a new pass without a completed broad call. That is
    # not an observed candidate pool. Every recorded broad call must have a log.
    if set(groups)-log_groups:
        raise RuntimeError("Trace pass absent from log: "+str(set(groups)-log_groups))
    for key, trials in groups.items():
        pool = passed[key].copy()
        identities = Counter((f"{e['raw']['period_days']:.4f}",f"{e['resolved']['period_days']:.4f}") for e in trials)
        if any(0 < pool[identity] < count for identity,count in identities.items()):
            raise RuntimeError("Rounded log identities cannot distinguish every gate outcome: "+str(key))
        for event in trials:
            identity = (f"{event['raw']['period_days']:.4f}",f"{event['resolved']['period_days']:.4f}")
            event["all_gates_pass_log"] = pool[identity]>0
            if pool[identity]>0:
                pool[identity]-=1
        if any(pool.values()):
            raise RuntimeError("PASS log has no trace counterpart: "+str(key)+" "+str(pool))
    return groups,winners,{"recorded_group_size_counts":dict(Counter(recorded.values())),
                           "actual_group_size_counts":dict(Counter(map(len,groups.values()))),
                           "n_recorded_groups":len(recorded), "n_actual_groups":len(groups)}


def audit_job(run_root, record, top_n=8, rank_by="composite"):
    job_id = record["job_id"]
    trace = run_root/"traces"/(job_id+".jsonl")
    log = run_root/"logs"/(job_id+".log")
    groups,winners,diagnostic = reconstructed(trace,log,top_n)
    p_inj = float(record["injection"]["period"])
    injection_t0 = float(record["injection_model"]["t0"])
    injection_duration = float(record["injection_model"].get("t14_days") or 0)
    score = lambda row: float(row["snr"] if rank_by=="snr" else row.get("composite_score",row["snr"]))
    witnesses = []
    for group,events in groups.items():
        passing = [event["resolved"] for event in events if event["all_gates_pass_log"]]
        if not passing:
            continue
        selected = winners.get(group)
        if selected is None:
            raise RuntimeError("Passing pool has no accepted winner: "+job_id+" "+str(group))
        winner = max(passing,key=score)
        if abs(float(winner["period_days"])-selected) > 0.00000051:
            raise RuntimeError("Reconstructed maximum differs from logged selection: "+job_id+" "+str(group))
        mine = [row for row in passing if abs(float(row["period_days"])/p_inj-1)<0.01]
        if mine and abs(selected/p_inj-1)>=0.01:
            for row in mine:
                base = min(p_inj,float(row["period_days"]))
                epoch_delta = (float(row["epoch_btjd"])-injection_t0+0.5*base)%base-0.5*base
                epoch_tolerance = max(injection_duration,float(row["duration_days"]),0.02)
                witnesses.append({"partition":group[0],"detection_pass":group[1],
                                  "injection_trial_period":float(row["period_days"]),"injection_score":score(row),
                                  "injection_trial_epoch":float(row["epoch_btjd"]),"injection_trial_duration":float(row["duration_days"]),
                                  "injection_epoch_match_p8":abs(epoch_delta)<=epoch_tolerance,
                                  "epoch_delta_days_p8":epoch_delta,"epoch_tolerance_days_p8":epoch_tolerance,
                                  "injection_snr":float(row["snr"]),"competing_period":float(winner["period_days"]),
                                  "competing_score":score(winner),"competing_snr":float(winner["snr"]),
                                  "n_all_gates_passing":len(passing)})
    return {"job_id":job_id, "injected_period":p_inj, "diagnostic":diagnostic, "witnesses":witnesses,
            "trace_sha256":hashlib.sha256(trace.read_bytes()).hexdigest(),
            "log_sha256":hashlib.sha256(log.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant",choices=list("abcde"),default="a")
    parser.add_argument("--job",default="inj00003_tic5655186")
    parser.add_argument("--all-settled",action="store_true",help="Validate the parser on a snapshot of all settled results; not a variant decision")
    args = parser.parse_args()
    run = ROOT/"data/survey/runs/p10_2b"/(args.variant+"_inj")
    if args.all_settled:
        rows,errors = [],[]
        paths = sorted((run/"results").glob("*.json"))
        for path in paths:
            rec = read(path)
            if rec.get("status")!="ok":
                continue
            try:
                rows.append(audit_job(run,rec,16 if args.variant in "cde" else 8,"snr" if args.variant in "de" else "composite"))
            except Exception as exc:
                errors.append({"job_id":rec["job_id"],"error":str(exc)})
        result = {"utc":datetime.now(timezone.utc).isoformat(),"purpose":"parser validation on settled snapshot; no recovery or variant decision",
                  "variant":args.variant,"n_valid":len(rows),"errors":errors,"rows":rows}
        (ROOT/"p10/results"/("search_trace_parser_validation_"+args.variant+".json")).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"n_valid":len(rows),"n_errors":len(errors),"first_errors":errors[:5]},indent=2))
        return
    record = read(run/"results"/(args.job+".json"))
    if record.get("status")!="ok":
        raise RuntimeError("Only completed successful records are audited")
    result = {"utc":datetime.now(timezone.utc).isoformat(),"purpose":"instrumentation contract audit; no variant decision",
              "variant":args.variant, "inherited_defect":"Local alias BLS calls increment the stored detection-pass counter, separating actual competitors; the inherited metrics also omit gates 6/7. Reconstruct groups from broad settings and verify all-gate PASS and actual winner against the complete per-job log.",
              "record":audit_job(run,record,16 if args.variant in "cde" else 8,"snr" if args.variant in "de" else "composite")}
    path = ROOT/"p10/results/search_trace_contract_audit.json"
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
