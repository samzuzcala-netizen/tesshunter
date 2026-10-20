"""Prompt 10 Part 1c: re-score seen records under the pre-registered p10.0 tiers.

Applies ``tesshunter.verdict_tiers.evaluate`` FROM THE SAVED RECORDS ONLY to the 19 P8
Stage B passers (``data/survey/p8``) and the 16 P9 final candidates
(``p9/results/blind/<tic>``).  Nothing is re-measured, no stage is rerun, no record under
``data/survey/p8`` or ``p9`` is written.  A P8 record without D evidence (a Stage C FAIL
under p8.0) gets "not permitted", never a verdict: under the p10.0 tiers K2 and K4 are
read from the saved p8.0 decisions until Part 2 decides the repaired gates.

This is a re-scoring of seen records under a rule written before it ran
(HANDOFF_P10.md section 0.1.2).  Output: ``p10/results/tier_rederivation.csv`` and
``.json``, and a Markdown table on stdout for the handoff.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from tesshunter import verdict_tiers as T   # noqa: E402

P8_ROOT = REPO / "data/survey/p8"
P9_BLIND = REPO / "p9/results/blind"
OUT = REPO / "p10/results"

# AUDIT_P9.md "Final reviews and positive loss census": the post-lock final-fit truth
# association of each P9 final candidate (identification only; no score is changed).
P9_ASSOCIATION = {
    "tic231702397_P5.0783": "TOI-122 b", "tic335590096_P1.5228": "TOI-4860 b", "tic102734241_P10.9047": "TOI-6002 b",
    "tic243641947_P2.5929": "TOI-3235 b", "tic271971130_P19.2884": "TOI-715 b", "tic389900760_P5.8005": "TOI-2120 b",
    "tic259168516_P4.8025": "TOI-1680 b", "tic181804752_P4.9893": "LP 791-18 c", "tic178709444_P3.4721": "TOI-762 A b",
    "tic161032923_P3.9644": "TOI-1080 b", "tic284441182_P2.5272": "TOI-1470 b", "tic377293776_P2.0439": "TOI-1450 A b",
    "tic33595516_P0.7655": "no labelled signal association (TOI-849 b timing, see AUDIT_P9)",
    "tic177079323_P5.7518": "TOI-2353.01 (uncertain)", "tic230006888_P12.2789": "TOI-4111.01 (uncertain)",
    "tic41422753_P2.4708": "TOI-5855.01 (TFOP nearby EB blend, negative)",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def fired_list(ev):
    return [n for n in T.K_ORDER + T.H_ORDER if ev["conditions"][n]["fired"]]


def row_from(ev, extra):
    k9, h1 = ev["conditions"]["K9"], ev["conditions"]["H1"]
    f5 = ev["flags"]["F5"]
    return {**extra, "p10_verdict": ev["verdict"], "deciding_condition": ev["deciding_condition"] or "",
            "deciding_detail": (ev["deciding_detail"] or "")[:200], "fired": " ".join(fired_list(ev)),
            "not_measurable": " ".join(ev["not_measurable"]),
            "nfpp": "" if h1.get("nfpp") is None else round(h1["nfpp"], 4),
            "k9_criterion_holds": k9.get("criterion_holds"), "k9_reviewer": k9.get("reviewer_decision"),
            "k9_correlated_sectors": k9.get("n_correlated"), "k9_disagreeing_sectors": k9.get("n_disagreeing"),
            "k7_elsewhere_sectors": ev["conditions"]["K7"].get("n_elsewhere"),
            "k7_elsewhere_sectors_literal_form": ev["conditions"]["K7"].get("n_elsewhere_literal"),
            "k7_absent_sectors": ev["conditions"]["K7"].get("n_absent"),
            "n_F1_neighbours": len(ev["flags"]["F1"]), "F5_localisation": f5["localisation"],
            "F5_sectors_measurable": f5["n_sectors_measurable"],
            "reference_depth_ppt": ev["reference_depth"]["depth_ppt"], "reference_depth_source": ev["reference_depth"]["source"]}


def p8_rows():
    rows, evaluations = [], {}
    for path in sorted((P8_ROOT / "stageB").glob("*.json")):
        b = read(path)
        key, tic, period = b["key"], int(b["tic_id"]), float(b["survey_period"])
        c = read(P8_ROOT / "stageC" / f"{key}.json")
        d_path = P8_ROOT / "stageD" / f"{key}.json"
        extra = {"set": "P8", "key": key, "tic_id": tic, "period_days": period, "association": "",
                 "p8_stageC": c.get("decision"), "p8_verdict": "", "p8_useful_hold": ""}
        if not d_path.exists():
            rows.append({**extra, "p8_verdict": f"C {c.get('decision')}: never reached D", "p10_verdict": "not permitted",
                         "deciding_condition": "K4 (p8.0 C decision; the Part 2c rule is pending)",
                         "deciding_detail": (c.get("reason") or "")[:200], "fired": "", "not_measurable": "",
                         "nfpp": "", "k9_criterion_holds": "", "k9_reviewer": "", "k9_correlated_sectors": "",
                         "k9_disagreeing_sectors": "", "k7_elsewhere_sectors": "", "k7_elsewhere_sectors_literal_form": "",
                         "k7_absent_sectors": "",
                         "n_F1_neighbours": "", "F5_localisation": "", "F5_sectors_measurable": "",
                         "reference_depth_ppt": "", "reference_depth_source": ""})
            continue
        d = read(d_path)
        extra["p8_verdict"] = d.get("verdict") or d.get("provisional_verdict")
        inputs = T.load_inputs(P8_ROOT, key, tic, period, float(b["survey_depth_ppt"]),
                               candidates_csv=P8_ROOT / "candidates.csv")
        ev = T.evaluate(inputs)
        evaluations[key] = ev
        rows.append(row_from(ev, extra))
    return rows, evaluations


def p9_rows():
    rows, evaluations = [], {}
    for path in sorted(P9_BLIND.glob("tic*/final/*.json")):
        final = read(path)
        key, tic = final["key"], int(final["tic_id"])
        root = path.parents[1]
        b = read(root / "stageB" / f"{key}.json")
        period, depth = float(b["survey_period"]), float(b["survey_depth_ppt"])
        inputs = T.load_inputs(root, key, tic, period, depth, candidates_csv=root / "candidates.csv")
        ev = T.evaluate(inputs)
        evaluations[key] = ev
        rows.append(row_from(ev, {"set": "P9", "key": key, "tic_id": tic, "period_days": period,
                                  "association": P9_ASSOCIATION.get(key, ""), "p8_stageC": "PASS",
                                  "p8_verdict": final.get("scientific_verdict"),
                                  "p8_useful_hold": final.get("legitimate_useful_hold")}))
    return rows, evaluations


def markdown(rows):
    lines = ["| set | key | association | p8.0 verdict | p10.0 verdict | deciding condition | fired | not measurable |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['set']} | {r['key']} | {r['association']} | {r['p8_verdict']}"
                     f"{' (useful)' if r.get('p8_useful_hold') is True else ''} | {r['p10_verdict']} | "
                     f"{r['deciding_condition']} | {r['fired'] or '-'} | {r['not_measurable'] or '-'} |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    rows8, ev8 = p8_rows()
    rows9, ev9 = p9_rows()
    rows = rows8 + rows9
    cols = list(rows[0].keys())
    with (args.out / "tier_rederivation.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    summary = {}
    for name, rs in (("P8", rows8), ("P9", rows9)):
        summary[name] = {"n": len(rs), "p10_verdicts": {}, "deciding": {}}
        for r in rs:
            summary[name]["p10_verdicts"][r["p10_verdict"]] = summary[name]["p10_verdicts"].get(r["p10_verdict"], 0) + 1
            dk = r["deciding_condition"].split(" ")[0] if r["deciding_condition"] else "none"
            summary[name]["deciding"][dk] = summary[name]["deciding"].get(dk, 0) + 1
    payload = {"scope": "Re-scoring of seen records under the pre-registered p10.0 tiers (HANDOFF_P10.md 0.1); "
                        "nothing re-measured; K2 and K4 read from the saved p8.0 decisions.",
               "summary": summary, "rows": rows, "evaluations": {**ev8, **ev9}}
    (args.out / "tier_rederivation.json").write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print()
    print(markdown(rows))
    print()
    print("written:", args.out / "tier_rederivation.csv", args.out / "tier_rederivation.json")


if __name__ == "__main__":
    main()
