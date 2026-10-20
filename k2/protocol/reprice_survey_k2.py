"""Re-price the 10,000-star survey with K2's unit costs (``price_survey_k1.py`` logic; RULES_K2 Part 1 step 4 and
Part 5).  K1's ``k1/results/survey_price.json`` is the base: same n_usable distribution of the frozen list
(catalogue column only), workers, 1.5 margin and real-signal allowance.  Replaced: the Stage C unit costs by
n_usable bin, measured on K2's C receipts of the given labels (host n = sectors in its store), and, when given, the
natural per-star rates of the adopted A1 configuration.  Writes ``k2/results/survey_price_k2_<tag>.json``.
"""
from __future__ import annotations

import glob
import json
import sys

import pandas as pd

from k2_common import K1, K2, K1_STORE, K2_STORE, K2_RECEIPTS, read, write, utc

N_BINS = [0, 8, 13, 20, 30, 1000]


def nbin(n: int) -> str:
    for lo, hi in zip(N_BINS[:-1], N_BINS[1:]):
        if lo <= n < hi:
            return f"{lo}-{hi}"
    return "other"


def store_n(tic: int) -> int:
    for store in (K1_STORE, K2_STORE):
        p = store / f"tic{int(tic)}" / "index.json"
        if p.exists():
            idx = read(p)
            return len({int(x["sector"]) for x in (idx.get("products") or idx.get("kept") or [])})
    raise FileNotFoundError(tic)


def c_units(labels) -> dict:
    rows = []
    for lb in labels:
        for p in glob.glob(str(K2_RECEIPTS / lb / "C" / "*.json")):
            r = read(p)
            if r.get("status") == "COMPLETE" and r.get("wall_seconds"):
                rows.append({"tic_id": int(r["tic_id"]), "wall": float(r["wall_seconds"])})
    df = pd.DataFrame(rows)
    df["nbin"] = df.tic_id.map(lambda t: nbin(store_n(t)))
    g = df.groupby("nbin").wall.agg(["mean", "median", "count"])
    out = {k: {"mean_s": float(v["mean"]), "median_s": float(v["median"]), "n": int(v["count"])} for k, v in g.iterrows()}
    out["_all"] = {"mean_s": float(df.wall.mean()), "n": int(len(df))}
    return out


def main(tag: str, labels, rates: dict | None = None) -> dict:
    base = read(K1 / "results" / "survey_price.json")
    units = dict(base["unit_costs"], C=c_units(labels))
    nat = dict(base["natural_rates"], **(rates or {}))
    real = base["real_signal_allowance_per_star"]
    c_load = nat["S_per_star"] + real
    per_star = {"search": 1.0, "A": nat["pregate_per_star"], "S": nat["A_per_star"] + real, "B": c_load, "C": c_load,
                "D": c_load}
    dist, W, M = base["n_usable_distribution"], base["workers"], base["margin"]
    qh = {}
    for st in ("search", "A", "S", "B", "C", "D"):
        tot = sum(cnt * per_star[st] * units[st].get(b, units[st]["_all"])["mean_s"] for b, cnt in dist.items())
        qh[st] = M * tot / W[st] / 3600.0
    res = {"utc": utc(), "tag": tag, "c_labels": list(labels), "base": "k1/results/survey_price.json",
           "n_usable_distribution": dist, "unit_costs": units, "natural_rates": nat, "per_star": per_star,
           "queue_hours": qh, "total_queue_hours": float(sum(qh.values())), "k1_total_queue_hours": base["total_queue_hours"],
           "k1_queue_hours": base["queue_hours"], "days_on_this_machine": float(sum(qh.values())) / 24.0,
           "workers": W, "margin": M}
    write(K2 / "results" / f"survey_price_k2_{tag}.json", res, replace=True)
    return res


if __name__ == "__main__":
    r = main(sys.argv[1], sys.argv[2].split(","))
    print(json.dumps({k: r[k] for k in ("queue_hours", "total_queue_hours", "k1_total_queue_hours", "days_on_this_machine")},
                     indent=1))
