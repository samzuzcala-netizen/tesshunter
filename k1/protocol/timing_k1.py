"""K1 Part C4: timing pilot summary, rule E4 and the price of Parts D-F and of the 10,000-star survey.

Reads the pilot search receipts (``D:/tesshunter_k1/runs/pilot_search_<arm>_b<budget>/receipts``), the
pilot funnel receipts (labels ``pilot_A`` / ``pilot_S`` / ``pilot_B`` / ``pilot_C``) and the dry-run
Stage D receipt.  Prices use the prompt's worker counts (24 search, 16 A/S/B, 3-6 C, 6 D) and a 1.5x
margin; queue-hours = summed job wall / workers.  Writes ``k1/results/timing_pilot.json``.
"""
from __future__ import annotations

import glob
import json
import statistics as st

import numpy as np

from k1_common import ROOT, RUNS, RECEIPTS, read, write, utc
import rules_eval_k1 as E

MARGIN = 1.5


def search_stats(arm, budget):
    rs = [read(p) for p in glob.glob(str(RUNS / f"pilot_search_{arm}_b{int(budget)}" / "receipts" / "*.json"))]
    if not rs:
        return None
    w = [r["wall_seconds"] for r in rs]
    lim = [r["budget_exhausted_partitions"] > 0 for r in rs]
    return {"n": len(rs), "complete": sum(r["status"] == "COMPLETE" for r in rs), "wall_mean_s": float(np.mean(w)),
            "wall_median_s": float(np.median(w)), "wall_p90_s": float(np.percentile(w, 90)), "wall_max_s": float(max(w)),
            "partition_limited_fraction": float(np.mean(lim)), "n_partition_limited": int(sum(lim)),
            "pregate_per_star": float(np.mean([r["n_pre_gate"] for r in rs])),
            "accepted_per_star": float(np.mean([r["n_accepted"] for r in rs]))}


def funnel_stats(label, stage):
    rs = [read(p) for p in glob.glob(str(RECEIPTS / label / stage / "*.json"))]
    if not rs:
        return None
    w = [r.get("wall_seconds", 0.0) for r in rs]
    return {"n": len(rs), "wall_mean_s": float(np.mean(w)), "wall_median_s": float(np.median(w)),
            "wall_max_s": float(max(w)), "unknown": sum(r["status"] != "COMPLETE" for r in rs),
            "pass": sum((r.get("decision") or "") in ("PASS",) for r in rs)}


def price(n_jobs, mean_s, workers):
    return MARGIN * n_jobs * mean_s / workers / 3600.0


WORKERS = {"search": 24, "A": 16, "S": 16, "B": 16, "C": 6, "D": 6}
COUNTS = {"inj": 1000, "fa": 250, "dev_hosts": 64 + 35, "heldout_hosts": 107 + 53, "heldout_kp_hosts": 107,
          "c_sample": 150, "survey": 10000}


def _funnel_unit(out, st_, default):
    f = out["funnel"].get(st_)
    return (f["wall_mean_s"] if f else default), (f is not None)


def priced(out, budget):
    """Queue-hours (1.5x margin) for Parts D-F and the 10,000-star survey from the measured unit costs.

    Search cost per star: the pilot mean at the E4 budget (s56 arm: the same budget if tested, else the next
    larger).  Funnel volume: measured pre-gate passers per star and the pilot A, S and B pass fractions; every
    B-passer of DEV, HELD-OUT and paired-P12 hosts goes to C, and every C-passer to D (pass fraction of C taken
    as 1, an upper bound).  The P12 paired search is priced at the s56 search cost (same sectors 56-98)."""
    s = out["search"]
    k1 = s.get(f"k1_b{int(budget)}")
    s56 = s.get(f"s56_b{int(budget)}") or s.get("s56_b8100")
    if not (k1 and s56):
        return None
    a_s, _ = _funnel_unit(out, "A", 0.0)
    s_s, _ = _funnel_unit(out, "S", 0.0)
    b_s, _ = _funnel_unit(out, "B", 0.0)
    c_s, _ = _funnel_unit(out, "C", 0.0)
    d_s = out.get("stage_d_unit_s", 0.0)
    fr = out.get("pass_fractions", {})
    pa, ps, pb = fr.get("A", 1.0), fr.get("S_any", 1.0), fr.get("B", 1.0)
    pg_k1, pg_56 = k1["pregate_per_star"], s56["pregate_per_star"]
    f56 = out.get("funnel_s56", {})
    a56 = (f56.get("A") or {}).get("wall_mean_s", a_s)
    s56s = (f56.get("S") or {}).get("wall_mean_s", s_s)
    pa56 = out.get("pass_fractions_s56", {}).get("A", pa)
    rows = []

    def add(part, item, n, unit, stage):
        rows.append({"part": part, "item": item, "n_jobs": float(n), "unit_s": float(unit), "workers": WORKERS[stage],
                     "queue_h": price(n, unit, WORKERS[stage])})

    n_k1_d = COUNTS["inj"] + COUNTS["fa"] + COUNTS["dev_hosts"]
    n_56_d = COUNTS["inj"] + COUNTS["fa"]
    add("D", "search survey_k1 (inj+FA+DEV)", n_k1_d, k1["wall_mean_s"], "search")
    add("D", "search survey_k1_s56 (inj+FA)", n_56_d, s56["wall_mean_s"], "search")
    add("D", "A legacy + A ramp (survey_k1)", 2 * n_k1_d * pg_k1, a_s, "A")
    add("D", "A legacy + A ramp (survey_k1_s56)", 2 * n_56_d * pg_56, a56, "A")
    add("D", "S all modes (survey_k1)", n_k1_d * pg_k1 * pa, s_s, "S")
    add("D", "S all modes (survey_k1_s56)", n_56_d * pg_56 * pa56, s56s, "S")
    dev_b = COUNTS["dev_hosts"] * pg_k1 * pa * ps
    add("D", "DEV B", dev_b, b_s, "B")
    add("D", "C capped injection sample", COUNTS["c_sample"], c_s, "C")
    add("D", "DEV C", dev_b * pb, c_s, "C")
    add("D", "DEV D", dev_b * pb, d_s, "D")
    h = COUNTS["heldout_hosts"]
    add("F", "HELD-OUT search survey_k1", h, k1["wall_mean_s"], "search")
    add("F", "HELD-OUT A + S", h * pg_k1 * (1 + pa), (a_s + s_s) / 2, "A")
    add("F", "HELD-OUT B", h * pg_k1 * pa * ps, b_s, "B")
    add("F", "HELD-OUT C", h * pg_k1 * pa * ps * pb, c_s, "C")
    add("F", "HELD-OUT D", h * pg_k1 * pa * ps * pb, d_s, "D")
    hk = COUNTS["heldout_kp_hosts"]
    add("F", "P12 paired search (survey_p10)", hk, s56["wall_mean_s"], "search")
    add("F", "P12 paired A + S + B", hk * pg_56 * (1 + pa56 + pa56 * ps), (a56 + s56s + b_s) / 3, "A")
    add("F", "P12 paired C", hk * pg_56 * pa * ps * pb, c_s, "C")
    n = COUNTS["survey"]
    add("survey", "search survey_k1", n, k1["wall_mean_s"], "search")
    add("survey", "A", n * pg_k1, a_s, "A")
    add("survey", "S", n * pg_k1 * pa, s_s, "S")
    add("survey", "B", n * pg_k1 * pa * ps, b_s, "B")
    add("survey", "C", n * pg_k1 * pa * ps * pb, c_s, "C")
    add("survey", "D", n * pg_k1 * pa * ps * pb, d_s, "D")
    tot = {}
    for r in rows:
        tot[r["part"]] = tot.get(r["part"], 0.0) + r["queue_h"]
    return {"budget_s": budget, "rows": rows, "queue_hours": tot,
            "parts_D_to_F_queue_hours": tot.get("D", 0.0) + tot.get("F", 0.0),
            "stop_c_fires": tot.get("D", 0.0) + tot.get("F", 0.0) > 60.0}


def pass_fractions(label="pilot"):
    import plan_k1 as PK
    a, s, b = PK._decisions(label, "A"), PK._decisions(label, "S"), PK._decisions(label, "B")
    fa = [r.get("decision") == "PASS" for r in a.values() if r.get("status") == "COMPLETE"]
    fs = [any(v in ("PASS", "HOLD") for v in (r.get("gate_by_mode") or {}).values()) for r in s.values()
          if r.get("status") == "COMPLETE"]
    fb = [r.get("decision") == "PASS" for r in b.values() if r.get("status") == "COMPLETE"]
    f = lambda x: (float(np.mean(x)) if x else None)
    return {"A": f(fa), "S_any": f(fs), "B": f(fb), "n": {"A": len(fa), "S": len(fs), "B": len(fb)}}


def main(label="pilot", c_label="pilot"):
    out = {"utc": utc(), "search": {}, "funnel": {}, "labels": [label, c_label]}
    for arm in ("k1", "s56"):
        for b in (2700, 5400, 8100):
            s = search_stats(arm, b)
            if s:
                out["search"][f"{arm}_b{b}"] = s
    frac = {b: out["search"][f"k1_b{b}"]["partition_limited_fraction"] for b in (2700, 5400, 8100) if f"k1_b{b}" in out["search"]}
    out["E4"] = E.e4_budget(frac)
    out["funnel_s56"] = {}
    for st_ in ("A", "S", "B", "C"):
        f = funnel_stats(c_label if st_ == "C" else label, st_)
        if f:
            out["funnel"][st_] = f
        f = funnel_stats(f"{label}_s56", st_)
        if f:
            out["funnel_s56"][st_] = f
    out["pass_fractions"] = {k: v for k, v in pass_fractions(label).items() if v is not None}
    out["pass_fractions_s56"] = {k: v for k, v in pass_fractions(f"{label}_s56").items() if v is not None}
    d = [read(p)["wall_seconds"] for p in glob.glob(str(RECEIPTS / "*" / "D" / "*.json"))]
    out["stage_d_unit_s"] = float(np.mean(d)) if d else 0.0
    out["stage_d_n"] = len(d)
    out["price"] = priced(out, out["E4"]["budget_s"])
    write(ROOT / "results" / ("timing_pilot.json" if label == "pilot" else f"timing_{label}.json"), out, replace=True)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:3])
