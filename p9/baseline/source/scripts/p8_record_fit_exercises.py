"""Record the completed frozen-P8 injection exercise, retaining earlier controls."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data/survey/p8"
ROOT = OUT / "demo_inj"
KEY = "tic154567574_P6.3063"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    summary_path = OUT / "fit_exercises_p8.json"
    summary = read(summary_path)
    records = {stage: read(ROOT / stage / f"{KEY}.json")
               for stage in ("stageA", "secondary", "stageB", "stageC", "stageD", "fit")}
    for stage, rec in records.items():
        if rec.get("rules_version") != "p8.0":
            raise ValueError(f"{stage} has stale rules")
    for stage in ("stageA", "stageB", "stageC"):
        if records[stage]["decision"] != "PASS":
            raise ValueError(f"{stage} did not pass")
    if records["secondary"]["gate"] != "PASS":
        raise ValueError("Secondary exercise did not pass")
    final = records["stageD"]
    if final["verdict"] != "SUBMIT" or "EXERCISE" not in final["reason"]:
        raise ValueError("The explicitly labelled verdict exercise is unfinished")
    ctoi = REPO / final["ctoi_fields_path"]
    fields = read(ctoi)
    if fields["provenance"]["rules_version"] != "p8.0" or "EXERCISE" not in fields["form_fields"]["notes"]:
        raise ValueError("CTOI exercise provenance is missing")
    paths = [ROOT / stage / f"{KEY}.json" for stage in records] + [ctoi]
    summary["injection_p8"] = {
        "purpose": "EXERCISE: injected signal, not a candidate; never submit",
        "source_calibration_rules": "p7.0", "rules_version": "p8.0",
        "completed_utc": final["verdict_stamped_utc"],
        "exercise": read(ROOT / "exercise.json"),
        "fit": records["fit"],
        "stages": {stage: {k: rec.get(k) for k in (
            "decision", "gate", "reason", "seconds", "max_verdict", "provisional_verdict",
            "provisional_reason", "verdict", "ctoi_fields_path") if k in rec}
                   for stage, rec in records.items() if stage != "fit"},
        "blind_tls": read(ROOT / "tls" / f"{KEY}.json")["blind"],
        "sha256": {str(path.relative_to(REPO)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in paths},
    }
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"completed_utc": final["verdict_stamped_utc"],
                      "rules_version": "p8.0", "fit": records["fit"]["adopted"],
                      "provisional_verdict": final["provisional_verdict"],
                      "provisional_reason": final["provisional_reason"]}, indent=2))


if __name__ == "__main__":
    main()
