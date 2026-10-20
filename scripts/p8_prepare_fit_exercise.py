"""Copy one completed recovered-injection audit into an explicitly labelled Part 4 exercise.

The source injection records are retained. Continue with p8_funnel --root data/survey/p8/demo_inj
--rules p7.0 --inject data/survey/p8/demo_inj/inject.json stageB / stageC / stageD / verdict.
"""
import argparse
import csv
import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
P8 = REPO / "data" / "survey" / "p8"
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    import p8_completeness as C
    source = P8 / "inj_funnel" / args.job
    out = P8 / "demo_inj"
    if out.exists():
        existing = json.loads((out / "exercise.json").read_text(encoding="utf-8"))
        if existing["job_id"] != args.job:
            raise ValueError("demo_inj already contains a different exercise")
        print(json.dumps(existing, indent=1))
        return
    row = next(csv.DictReader(open(source / "survivors.csv", newline="", encoding="utf-8")))
    key = C.kkey(int(row["tic_id"]), float(row["period_days"]))
    for stage, field in (("stageA", "decision"), ("secondary", "gate")):
        C.require_settled_record(source / stage / f"{key}.json", "p7.0", field, ("PASS",))
    for stage in ("stageA", "secondary", "prep", "tls", "neighbours"):
        (out / stage).mkdir(parents=True, exist_ok=True)
    for name in ("survivors.csv", "candidates.csv"):
        shutil.copy2(source / name, out / name)
    for stage in ("stageA", "secondary", "prep"):
        shutil.copy2(source / stage / f"{key}.json", out / stage / f"{key}.json")
    prep_path = out / "prep" / f"{key}.json"
    prep = json.loads(prep_path.read_text(encoding="utf-8"))
    prep["lc_npz"] = str((out / "tls" / f"{key}_lc.npz").relative_to(REPO))
    prep["copied_from"] = str((source / "prep" / f"{key}.json").relative_to(REPO))
    prep_path.write_text(json.dumps(prep, indent=1), encoding="utf-8")
    for suffix in ("_lc.npz", "_forced.json"):
        shutil.copy2(source / "tls" / f"{key}{suffix}", out / "tls" / f"{key}{suffix}")
    neighbour = f"tic{row['tic_id']}.json"
    shutil.copy2(P8 / "neighbours" / neighbour, out / "neighbours" / neighbour)
    model = {k: row[k] for k in row if k.startswith("inj_")}
    (out / "inject.json").write_text(json.dumps(model, indent=1), encoding="utf-8")
    plan = {"job_id": args.job, "source_root": str(source.relative_to(REPO)), "tic_id": int(row["tic_id"]),
            "period": float(row["period_days"]), "key": key, "rules_version": "p7.0",
            "purpose": "EXERCISE on a recovered injected signal; not a candidate; never submit",
            "injection_truth": model}
    (out / "exercise.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print(json.dumps(plan, indent=1))


if __name__ == "__main__":
    main()
