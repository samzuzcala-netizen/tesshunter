"""K2 budget (RULES_K2 7, stop rule K-B): price Parts 1-4 after the 10-job V3 timing check.

Stage C cost model: a variant's job wall = K1 wall x (C-input points / K1 points) x (oversampling / 3) x k, with
k fitted on the timing check (median of measured / modelled).  Points per R-C job are counted exactly from the
K1 prepared series (``c_input_k2.transform``).  Other stages use K1's measured walls of the same jobs (Stage A
re-runs) or K1 Part F's measured job-hours scaled by host count (fresh set).  Queue-hours = job-hours / workers
x 1.5 (RULES_K2 1.4).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from k2_common import K1, K2, K1_DATA, K2_DATA, K1_RECEIPTS, K2_RECEIPTS, read, write, utc
import c_input_k2 as CI
import plan_k2 as PK

MARGIN = 1.5
WORKERS = {"search": 24, "A": 16, "S": 10, "B": 10, "C": 6, "D": 6}


def qh(job_seconds: float, stage: str) -> float:
    return job_seconds / WORKERS[stage] / 3600.0 * MARGIN


def points_table() -> pd.DataFrame:
    rc = PK.rc_table()
    rows = []
    for r in rc.itertuples():
        key = next(p.stem for p in (PK.Path(r.case_root) / "prep").glob("*.json") if "_res" not in p.name)
        meta = read(PK.Path(r.case_root) / "prep" / f"{key}.json")
        with np.load(PK.Path(r.case_root) / "tls" / f"{key}_lc.npz") as z:
            arr = {k: z[k] for k in ("time", "flux", "flux_err", "time_unbinned", "sector_unbinned")}
        row = {"candidate_id": r.candidate_id, "n_class": r.n_class, "n_usable": r.n_usable, "k1_wall": r.k1_wall_s}
        for v in ("K1", "V1", "V2", "V3", "V4"):
            t, f, e, info = CI.transform(arr, meta["products"], v)
            row[f"n_{v}"] = info["n_c_input"]
            row[f"os_{v}"] = CI.oversampling(v, info["baseline_days"])
        rows.append(row)
    return pd.DataFrame(rows)


def model(pts: pd.DataFrame, v: str) -> pd.Series:
    return pts.k1_wall * (pts[f"n_{v}"] / pts.n_K1) * (pts[f"os_{v}"] / 3.0)


def price() -> dict:
    pts = points_table()
    tim = read(K2 / "results" / "timing_rc_v3a.json")      # AMENDMENT_K2_20261014_1
    meas = pd.DataFrame(tim["jobs"]).set_index("candidate_id")
    p = pts.set_index("candidate_id")
    k = float(np.median(meas.var_wall / model(p.loc[meas.index], "V3")))
    est = {v: model(p, v) * k for v in ("V3", "V2", "V4", "V1")}
    rest = [c for c in p.index if c not in meas.index]
    part1 = {"V3_rest": qh(float(est["V3"].loc[rest].sum()), "C")}
    for v in ("V2", "V4", "V1"):
        part1[f"{v}_if_needed"] = qh(float(est[v].sum()), "C")
    # Part 2: Stage A re-runs (K1 walls of the same candidates), S/B small
    sel = read(K2 / "manifests" / "ra_a1_selection.json")
    walls = {}
    for lb in ("inj_k1", "fa_k1", "dev_k1"):
        for cid, rec in PK.receipts(K1_RECEIPTS, lb, "A").items():
            walls[cid] = rec.get("wall_seconds") or 0.0
    a_s = sum(walls.get(r["candidate_id"], 143.0) for r in sel["rows"])
    part2 = {"A": qh(a_s, "A"), "S_B": 0.3}
    # Part 3: M1 on the R-C jobs with siblings (upper bound: every DEV/inj R-C job with >= 1 S-passing sibling)
    m1_ids = [j["candidate_id"] for j in read(K2 / "manifests" / "m1_v3_siblings.json")["jobs"]] \
        if (K2 / "manifests" / "m1_v3_siblings.json").exists() else list(p.index)
    part3 = {"C": qh(float(est["V3"].loc[[c for c in m1_ids if c in p.index]].sum()), "C"), "D": qh(20 * 780.0, "D")}
    # Part 4 seen: K1 HELD-OUT C walls x the fitted V3 factor (median per n_class of est/K1 on R-C)
    fac = (est["V3"] / p.k1_wall).groupby(p.n_class).median().to_dict()
    ho = PK.receipts(K1_RECEIPTS, "ho_k1", "C")
    seen_c = 0.0
    for cid, rec in ho.items():
        try:
            n = PK.case_n_usable(rec["case_root"])
        except Exception:  # noqa: BLE001
            n = 30
        seen_c += (rec.get("wall_seconds") or 0.0) * fac.get(PK.n_class(n), max(fac.values()))
    ho_a = PK.receipts(K1_RECEIPTS, "ho_k1", "A")
    seen_a = sum((r.get("wall_seconds") or 0) for r in ho_a.values() if r.get("decision") == "FAIL") * 0.6
    part4_seen = {"A": qh(seen_a, "A"), "C": qh(seen_c, "C"), "D": qh(60 * 900.0, "D")}
    # Part 4 fresh: K1 Part F job-hours scaled by host count (K1 HELD-OUT 159 searched hosts, 107 P12 hosts)
    kp = pd.read_csv(K2 / "manifests" / "fresh_kp_hosts.csv")
    adv = pd.read_csv(K2 / "manifests" / "fresh_adv_hosts.csv") if (K2 / "manifests" / "fresh_adv_hosts.csv").exists() else pd.DataFrame({"tic_id": range(70)})
    s_k1, s_p12 = (len(kp) + len(adv)) / 159.0, len(kp) / 107.0
    ctl = {ph: read(K1_DATA / "controllers" / ph / "closure.json")["job_wall_hours"] * 3600 for ph in
           ("partF_search", "partF_A", "partF_S", "partF_B", "partF_D")}
    hoC = sum(r.get("wall_seconds") or 0 for r in ho.values())
    p12C = sum(r.get("wall_seconds") or 0 for r in PK.receipts(K1_RECEIPTS, "p12_paired", "C").values())
    part4_fresh = {"download_neighbours": 1.0, "search": qh(ctl["partF_search"] * (s_k1 + s_p12) / 2, "search"),
                   "A": qh(ctl["partF_A"] * (s_k1 + s_p12) / 2, "A"), "S_B": qh((ctl["partF_S"] + ctl["partF_B"]) * s_k1, "S"),
                   "C_k2": qh(seen_c * s_k1, "C"), "C_p12": qh(p12C * s_p12, "C"), "D": qh(ctl["partF_D"] * s_k1, "D")}
    tot_exp = (part1["V3_rest"] + sum(part2.values()) + sum(part3.values()) + sum(part4_seen.values())
               + sum(part4_fresh.values()))
    tot_worst = tot_exp + part1["V2_if_needed"] + part1["V4_if_needed"] + part1["V1_if_needed"]
    out = {"utc": utc(), "k_fit": k, "timing_jobs": int(len(meas)), "part1": part1, "part2": part2, "part3": part3,
           "part4_seen": part4_seen, "part4_fresh": part4_fresh, "expected_total_qh": tot_exp,
           "worst_case_total_qh": tot_worst, "budget_qh": 120.0, "within_budget_expected": tot_exp <= 120.0,
           "v3_factor_by_class": fac, "fresh_scale": {"k2_arm": s_k1, "p12_arm": s_p12},
           "points": pts.to_dict(orient="records")}
    write(K2 / "results" / "price_k2.json", out, replace=True)
    return {k_: v for k_, v in out.items() if k_ != "points"}


if __name__ == "__main__":
    print(json.dumps(price(), indent=1, default=str))
