"""K1 Part G: price the 10,000-star survey from Part D/F measurements, per usable-sector count.

Unit costs are measured job walls binned by the host's usable-sector count n (sectors in the host's K1 store):
search (survey_k1, 8,100 s, Part D injection + FA + DEV jobs; calibrated conditions), Stage A (legacy), S, B, C
(blind TLS; DEV, injection sample and HELD-OUT jobs) and D.  Natural per-star rates come from the 250
uninjected FA hosts (survey_k1): pre-gate, A PASS and S PASS under the frozen mode.  C/D load per star = the FA
S-pass rate (natural false alarms) + an allowance for real signals (expected new + known planets per star;
argument).  The survey's n distribution is the targets list's ``n_usable`` column (catalogue metadata only;
no survey light curve is read).  Queue-hours = sum(job wall) / workers x 1.5.
Writes ``k1/results/survey_price.json``.
"""
from __future__ import annotations

import glob
import json
import sys

import numpy as np
import pandas as pd

from k1_common import ROOT, DATA, RUNS, RECEIPTS, CONTROLLERS, read, write, utc

MARGIN = 1.5
WORKERS = {"search": 24, "A": 28, "S": 16, "B": 16, "C": 8, "D": 6}
N_BINS = [0, 8, 13, 20, 30, 1000]


def n_usable(tic: int) -> int:
    idx = read(DATA / "audit_lc" / f"tic{int(tic)}" / "index.json")
    prods = idx.get("products") or idx.get("kept") or []
    return len({int(p["sector"]) for p in prods})


def nbin(n: int) -> str:
    for lo, hi in zip(N_BINS[:-1], N_BINS[1:]):
        if lo <= n < hi:
            return f"{lo}-{hi}"
    return "other"


def search_walls() -> pd.DataFrame:
    rows = []
    for ph in ("inj_k1", "fa_k1", "dev_k1"):
        for p in glob.glob(str(RUNS / ph / "receipts" / "*.json")):
            r = read(p)
            if r.get("status") == "COMPLETE":
                rows.append({"tic_id": int(r["tic_id"]), "wall": float(r["wall_seconds"]), "phase": ph})
    return pd.DataFrame(rows)


def stage_walls(stage: str, labels) -> pd.DataFrame:
    rows = []
    for lb in labels:
        for p in glob.glob(str(RECEIPTS / lb / stage / "*.json")):
            r = read(p)
            if r.get("status") == "COMPLETE" and r.get("wall_seconds"):
                rows.append({"tic_id": int(r["tic_id"]), "wall": float(r["wall_seconds"]), "label": lb})
    return pd.DataFrame(rows)


def natural_rates(mode: str) -> dict:
    fa = read(ROOT / "results" / "e1_partD.json")["E1"]["fa"]["k1"]
    return {"pregate_per_star": fa["pregate_per_star"], "A_per_star": fa["A_per_star"],
            "S_per_star": fa["S_per_star"][mode], "n_hosts": fa["n_hosts"]}


def main(real_per_star: float = 0.03) -> dict:
    dec = read(ROOT / "results" / "decisions_E.json")
    mode = dec["E2"]["mode"]
    tg = pd.read_csv(ROOT / "survey" / "targets_k1.csv", usecols=lambda c: c in ("tic_id", "n_usable"))
    dist = tg.n_usable.map(nbin).value_counts().to_dict()
    cache = {}

    def nb(t):
        if t not in cache:
            cache[t] = nbin(n_usable(t))
        return cache[t]

    units = {}
    sw = search_walls()
    for name, df in (("search", sw), ("A", stage_walls("A", ["inj_k1", "fa_k1", "dev_k1", "ho_k1"])),
                     ("S", stage_walls("S", ["inj_k1", "fa_k1", "dev_k1", "ho_k1"])),
                     ("B", stage_walls("B", ["inj_k1", "dev_k1", "ho_k1"])),
                     ("C", stage_walls("C", ["dev_k1", "inj_k1", "ho_k1"])),
                     ("D", stage_walls("D", ["dev_k1", "ho_k1"]))):
        if df.empty:
            units[name] = {}
            continue
        df["nbin"] = df.tic_id.map(nb)
        g = df.groupby("nbin").wall.agg(["mean", "median", "count"])
        units[name] = {k: {"mean_s": float(v["mean"]), "median_s": float(v["median"]), "n": int(v["count"])} for k, v in g.iterrows()}
        units[name]["_all"] = {"mean_s": float(df.wall.mean()), "n": int(len(df))}
    nat = natural_rates(mode)
    c_load = nat["S_per_star"] + real_per_star
    per_star = {"search": 1.0, "A": nat["pregate_per_star"], "S": nat["A_per_star"] + real_per_star,
                "B": c_load, "C": c_load, "D": c_load}
    qh, detail = {}, {}
    for st in ("search", "A", "S", "B", "C", "D"):
        tot = 0.0
        for b, cnt in dist.items():
            u = units[st].get(b, units[st].get("_all", {"mean_s": 0.0}))
            tot += cnt * per_star[st] * u["mean_s"]
        qh[st] = MARGIN * tot / WORKERS[st] / 3600.0
        detail[st] = {"jobs": float(sum(dist.values()) * per_star[st]), "per_star": per_star[st]}
    res = {"utc": utc(), "mode": mode, "n_usable_distribution": dist, "unit_costs": units, "natural_rates": nat,
           "real_signal_allowance_per_star": real_per_star, "queue_hours": qh, "total_queue_hours": float(sum(qh.values())),
           "workers": WORKERS, "margin": MARGIN, "jobs": detail}
    write(ROOT / "results" / "survey_price.json", res, replace=True)
    return res


if __name__ == "__main__":
    r = main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.03)
    print(json.dumps({k: r[k] for k in ("n_usable_distribution", "natural_rates", "queue_hours", "total_queue_hours", "jobs")},
                     indent=1, default=str))
