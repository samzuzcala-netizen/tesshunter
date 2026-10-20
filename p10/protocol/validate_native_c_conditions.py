"""Check the native portion of the frozen C adoption conditions, without TLS.

The stronger statement of no alias-case flips among any of the 37 records does
not require opening additional control outcomes to classify individual hosts.
Injection/adversarial conditions remain pending and no rule is adopted here.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def main():
    output = ROOT / "p10/results/stage_c_native_conditions_20260910.json"
    require(not output.exists(), "Native condition receipt exists; preserve it")
    source = ROOT / "p10/results/stage_c_native_corrected_20260910.json"
    data = read(source)
    require(data["n"] == 37 and len(data["rows"]) == 37 and not data["pending"]
            and data["all_original_strongest_decisions_reproduced"], "Native reconciliation incomplete")
    for name, digest in data["input_sha256"].items():
        require(sha(ROOT / name) == digest, "Native reconciliation evidence changed: " + name)
    rows = []
    for r in data["rows"]:
        tls_path = ROOT / r["workspace"] / "tls" / (r["key"] + ".json")
        blind = read(tls_path)["blind"]
        matches = blind["match"]
        alias_case = bool(matches["alias_1pct"] and not matches["same_period_1pct"])
        b_flip = r["a_installed"] == "FAIL" and r["b_installed"]["decision"] == "PASS"
        fallback_a_flip = r["a_installed"] == "FAIL" and r["a_with_fallback"] == "PASS"
        fallback_b_flip = r["b_installed"]["decision"] == "FAIL" and r["b_with_fallback"]["decision"] == "PASS"
        rows.append({"set": r["set"], "key": r["key"], "strongest_period": blind["period"],
                     "strongest_match": matches, "strongest_is_survey_alias": alias_case,
                     "a_installed": r["a_installed"], "b_installed": r["b_installed"]["decision"],
                     "b_flip": b_flip, "b_alias_flip": b_flip and alias_case,
                     "fallback_triggered": r["fallback"]["triggered"],
                     "fallback_a_flip": fallback_a_flip, "fallback_b_flip": fallback_b_flip})
    by_key = {r["key"]: r for r in rows}
    require(len(by_key) == 37, "Duplicate native key")
    flips = [r["key"] for r in rows if r["b_flip"]]
    alias_flips = [r["key"] for r in rows if r["b_alias_flip"]]
    triggers = [r["key"] for r in rows if r["fallback_triggered"]]
    fallback_flips = [r["key"] for r in rows if r["fallback_a_flip"] or r["fallback_b_flip"]]
    toi = by_key["tic284441182_P18.0890"]
    known_negative = by_key["tic41422753_P2.4708"]
    require(toi["b_flip"], "TOI-1470 c native condition failed")
    require(not alias_flips, "A native alias case newly passes")
    require(triggers == fallback_flips == ["tic237222864_P10.2888"], "Unexpected native fallback change")
    require(known_negative["a_installed"] == known_negative["b_installed"] == "PASS"
            and not known_negative["fallback_triggered"], "Known recorded P9 negative changed")
    result = {"utc": datetime.now(timezone.utc).isoformat(), "n": 37,
              "scope": "Native portion of Part 2c conditions only; no new TLS or later-stage outcomes inspected.",
              "TOI_1470_c_flips": True, "significant_peak_installed_flips": flips,
              "n_alias_case_flips_among_all_37": 0,
              "fallback_trigger_keys": triggers, "fallback_flip_keys": fallback_flips,
              "fallback_native_interpretation": "Only HIP 97166 b, the positive development case named in the prompt, newly passes. No other native record triggers or changes under fallback.",
              "recorded_P9_negative": {"key": known_negative["key"], "C_before": "PASS", "C_after": "PASS",
                    "label_source": "HANDOFF_P10.md section 2.2: TOI-5855.01 is a negative nearby-EB blend; the previously recorded C pass is not a new C-rule flip."},
              "adoption": "pending all 30 injection and 41 adversarial-candidate controls",
              "checks": {k: True for k in ("exact_native_census", "all_reconciliation_hashes_unchanged",
                            "TOI_1470_c_condition", "no_native_alias_case_flip", "only_named_positive_fallback_change")},
              "input_sha256": {str(source.relative_to(ROOT)): sha(source),
                               str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))}, "rows": rows}
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "input_sha256")}, indent=2))


if __name__ == "__main__":
    main()
