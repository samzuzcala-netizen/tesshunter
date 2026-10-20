"""K1 Part D4 / Part E: calibration ledger, rules E1-E3 (E4 is decided on the C4 pilot), and the tables.

Run only after ``evaluate_k1.lock("partD", ...)``.  Inputs: sealed truth (k1/truth/injections,
known_planets_final.csv, adversarial_truth.csv), search runs inj_k1 / inj_s56 / fa_k1 / fa_s56 / dev_k1, funnel
receipts under the same labels (+ ``<label>_ramp`` for the Stage A variant).  Writes
``k1/results/calibration_partD.json`` and the per-item ledgers under ``k1/results/ledgers/``.
"""
from __future__ import annotations

import glob
import json
import math

import numpy as np
import pandas as pd

from k1_common import ROOT, RUNS, TRUTH, read, write, utc
import evaluate_k1 as EV
import rules_eval_k1 as RE

MODES = EV.S_MODES


def injections_ledger(arm: str) -> pd.DataFrame:
    rows = []
    phase, label = f"inj_{arm}", f"inj_{arm}"
    for p in sorted(glob.glob(str(TRUTH / "injections" / "inj_*.json"))):
        t = read(p)
        truth = {"tic_id": t["tic_id"], "period": t["period"], "t0": t["t0"], "t14": t["t14_days"], "sigma_t0": 0.0, "sigma_p": 0.0}
        led = EV.ledger_item(truth, f"{t['inj_id']}_{arm}", phase, label, s56=(arm == "s56"), ramp_label=f"{label}_ramp")
        rows.append({"inj_id": t["inj_id"], "tic_id": t["tic_id"], "arm": arm, "k1_class": t["k1_class"], "tmag": t["tmag"],
                     "n_usable": t["n_usable"], "rp_rearth": t["rp_rearth"], "period": t["period"],
                     "snr_exp_k1": t["snr_exp_k1"], "snr_exp_s56": t["snr_exp_s56"],
                     "n_obs_k1": t["n_obs_transits_k1"], "n_obs_s56": t["n_obs_transits_s56"],
                     **{k: v for k, v in led.items() if k != "matched_paths"}, "n_matched_paths": len(led["matched_paths"])})
    return pd.DataFrame(rows)


def kp_dev_ledger() -> pd.DataFrame:
    kp = pd.read_csv(TRUTH / "known_planets_final.csv")
    kp = kp[kp.in_final_set & (kp.role == "DEV")]
    rows = []
    for _, r in kp.iterrows():
        sp = float(np.nanmax(np.abs([r.get("pl_orbpererr1", np.nan), r.get("pl_orbpererr2", np.nan)]))) if np.isfinite(r.get("pl_orbpererr1", np.nan)) else 0.0
        st = float(np.nanmax(np.abs([r.get("pl_tranmiderr1", np.nan), r.get("pl_tranmiderr2", np.nan)]))) if np.isfinite(r.get("pl_tranmiderr1", np.nan)) else 0.0
        truth = {"tic_id": int(r.tic_id), "period": float(r.pl_orbper), "t0": float(r.t0_btjd), "t14": float(r.t14_hours) / 24.0,
                 "sigma_t0": st, "sigma_p": sp}
        led = EV.ledger_item(truth, f"dev_k1_{int(r.tic_id)}", "dev_k1", "dev_k1", s56=False, ramp_label="dev_k1_ramp")
        rows.append({"pl_name": r.pl_name, "tic_id": int(r.tic_id), "snr_exp_k1": r.snr_exp_k1, "n_obs_k1": r.n_obs_transits_k1,
                     "period": r.pl_orbper, "rp_rearth": r.pl_rade, "tmag": r.tic_Tmag, "k1_class": r.k1_class,
                     **{k: v for k, v in led.items() if k != "matched_paths"}})
    return pd.DataFrame(rows)


def adv_dev_passthrough() -> dict:
    adv = pd.read_csv(TRUTH / "adversarial_truth.csv")
    adv = adv[adv.role == "DEV"]
    cands = EV.candidates("dev_k1")
    a, s, b, c, d = (EV.receipts("dev_k1", st) for st in ("A", "S", "B", "C", "D"))
    out = {m: 0 for m in MODES}
    per_host = []
    for tic in adv.tic_id:
        rows = cands[cands.job_id == f"dev_k1_{int(tic)}"] if len(cands) else cands
        reached = {m: False for m in MODES}
        for _, r in rows.iterrows():
            cid = r.candidate_id
            if not r.passes_pregate or (a.get(cid) or {}).get("decision") != "PASS":
                continue
            if (b.get(cid) or {}).get("decision") != "PASS" or (c.get(cid) or {}).get("decision") != "PASS":
                continue
            v = ((d.get(cid) or {}).get("verdicts") or {}).get("k1.0", {}).get("verdict")
            if v not in ("SUBMIT", "HOLD"):
                continue
            gbm = (s.get(cid) or {}).get("gate_by_mode") or {}
            for m in MODES:
                if gbm.get(m) in ("PASS", "HOLD"):
                    reached[m] = True
        per_host.append({"tic_id": int(tic), **reached})
        for m in MODES:
            out[m] += int(reached[m])
    n = len(adv)
    return {"n_dev_adversarial": n, "passthrough": {m: out[m] / n if n else 0.0 for m in MODES}, "per_host": per_host}


def fa_per_star(arm: str) -> dict:
    ph = f"fa_{arm}"
    rec = EV.search_receipts(ph)
    n = sum(1 for r in rec.values() if r["status"] == "COMPLETE")
    cands = EV.candidates(ph)
    a, ar, s = EV.receipts(ph, "A"), EV.receipts(f"{ph}_ramp", "A"), EV.receipts(ph, "S")
    pre = int(cands.passes_pregate.sum()) if len(cands) else 0
    a_pass = sum(1 for r in a.values() if r.get("decision") == "PASS")
    ar_pass = sum(1 for r in ar.values() if r.get("decision") == "PASS")
    s_pass = {m: sum(1 for r in s.values() if (r.get("gate_by_mode") or {}).get(m) in ("PASS", "HOLD")) for m in MODES}
    return {"n_hosts": n, "accepted_per_star": (len(cands) / n) if n else None, "pregate_per_star": pre / n if n else None,
            "A_per_star": a_pass / n if n else None, "A_ramp_per_star": ar_pass / n if n else None,
            "S_per_star": {m: v / n for m, v in s_pass.items()} if n else None,
            "search_wall_s": sum(r["wall_seconds"] for r in rec.values()),
            "partition_limited_fraction": float(np.mean([r["budget_exhausted_partitions"] > 0 for r in rec.values()])) if rec else None}


def logistic_snr50(snr, rec):
    """MLE logistic in log10(SNR) (cmax free in [0,1]); returns SNR50 and SNR90 of the fitted curve."""
    from scipy.optimize import minimize
    x = np.log10(np.clip(np.asarray(snr, float), 1e-3, None)); y = np.asarray(rec, float)
    ok = np.isfinite(x)
    x, y = x[ok], y[ok]

    def nll(p):
        x50, w, c = p
        pr = np.clip(c / (1 + np.exp(-(x - x50) / max(w, 1e-3))), 1e-9, 1 - 1e-9)
        return -np.sum(y * np.log(pr) + (1 - y) * np.log(1 - pr))
    r = minimize(nll, x0=[1.1, 0.15, 0.9], bounds=[(0, 3), (0.01, 1.0), (0.05, 1.0)])
    x50, w, c = r.x
    snr50 = 10 ** (x50 + w * math.log(0.5 / (c - 0.5))) if c > 0.5 else None      # recovery = 50%
    snr90 = 10 ** (x50 + w * math.log(0.9 / max(c - 0.9, 1e-9))) if c > 0.9 else None
    # P10 convention for comparability: two-parameter logistic in ln SNR (plateau 1), crossing at 50%
    def nll2(p):
        a, b = p
        pr = np.clip(1 / (1 + np.exp(-(a + b * np.log(10 ** x)))), 1e-9, 1 - 1e-9)
        return -np.sum(y * np.log(pr) + (1 - y) * np.log(1 - pr))
    r2 = minimize(nll2, x0=[-5.0, 2.0])
    a2, b2 = r2.x
    return {"snr50": (float(snr50) if snr50 else None), "snr90": (float(snr90) if snr90 else None),
            "snr_half_plateau": float(10 ** x50), "cmax": float(c), "width_dex": float(w),
            "snr50_p10_convention": (float(math.exp(-a2 / b2)) if b2 > 0 else None), "n": int(len(y))}


def table(df, by, flags, bins=None):
    d = df.copy()
    if bins is not None:
        d["bin"] = pd.cut(d[by], bins, right=False).astype(str)
        key = "bin"
    else:
        key = by
    out = []
    for k, g in d.groupby(key):
        row = {"bin": str(k), "n": int(len(g)), "n_hosts": int(g.tic_id.nunique())}
        for f in flags:
            kk = int(g[f].sum())
            row[f] = kk
            row[f + "_frac"] = round(kk / len(g), 4)
            row[f + "_wilson"] = EV.wilson(kk, len(g))
            row[f + "_host_boot"] = EV.host_bootstrap_prop(g, f, n=2000)
        out.append(row)
    return out


def e1_and_leading(lock_name: str = "partD_S") -> dict:
    """E1 (it reads only search, pre-gate, A and S) and the leading S mode for the injection C sample
    (plan_partD_C_k1 docstring: highest injection retention through S at expected SNR 7-40 on the adopted arm,
    before E2's adversarial constraint; ties to the simpler mode).  Runs under the partD_S lock; writes
    k1/results/e1_partD.json.  E1 is restated unchanged in Part E's final calibration_partD.json."""
    EV.verify_lock(lock_name)
    led = {arm: injections_ledger(arm) for arm in ("k1", "s56")}
    k1, s56 = led["k1"], led["s56"]
    pool = k1[(k1.snr_exp_k1 >= 7) & (k1.snr_exp_k1 <= 20)][["inj_id", "tic_id", "S_bound"]].merge(
        s56[["inj_id", "S_bound"]], on="inj_id", suffixes=("_k1", "_s56"))
    d_pp = 100.0 * (pool.S_bound_k1.mean() - pool.S_bound_s56.mean())
    ci = EV.host_bootstrap(pool, lambda g: 100.0 * (g.S_bound_k1.mean() - g.S_bound_s56.mean()), n=4000)
    fa = {arm: fa_per_star(arm) for arm in ("k1", "s56")}
    walls = {arm: sum(r["wall_seconds"] for r in EV.search_receipts(f"inj_{arm}").values()) for arm in ("k1", "s56")}
    fa_ratio = fa["k1"]["pregate_per_star"] / fa["s56"]["pregate_per_star"] if fa["s56"]["pregate_per_star"] else float("inf")
    e1 = RE.e1_cadence(d_pp, ci[0], fa_ratio, walls["k1"] / walls["s56"])
    e1.update(pool_n=int(len(pool)), pool_hosts=int(pool.tic_id.nunique()), R_k1=float(pool.S_bound_k1.mean()),
              R_s56=float(pool.S_bound_s56.mean()), delta_ci=ci, fa=fa, search_wall_s=walls, lock=lock_name)
    adopted = "k1" if e1["adopt"] == "survey_k1" else "s56"
    A = led[adopted]
    col = f"snr_exp_{adopted}"
    p = A[(A[col] >= 7) & (A[col] <= 40)]
    counts = {m: int(p[f"S_{m}"].sum()) for m in MODES}
    best = max(counts.values())
    leading = next(m for m in RE.E2_ORDER if counts[m] == best)
    out = {"utc": utc(), "E1": e1, "leading_mode": leading, "leading_counts": counts, "leading_pool_n": int(len(p)),
           "adopted_arm": e1["adopt"]}
    for arm, df in led.items():
        df.to_csv(ROOT / "results" / "ledgers" / f"injections_{arm}_partD_S.csv", index=False)
    write(ROOT / "results" / "e1_partD.json", out, replace=True)
    return out


def _e2_on(led_arm, arm, dev, adv):
    col = f"snr_exp_{arm}"
    p2i = led_arm[(led_arm[col] >= 7) & (led_arm[col] <= 40)]
    p2k = dev[dev.n_obs_k1 >= 3]
    counts = {m: int(p2i[f"S_{m}"].sum() + p2k[f"S_{m}"].sum()) for m in MODES}
    n2 = len(p2i) + len(p2k)
    ret = {m: counts[m] / n2 for m in MODES}
    e2 = RE.e2_mode(ret, adv["passthrough"], counts)
    e2.update(arm=arm, pool_injections=int(len(p2i)), pool_dev_planets=int(len(p2k)), retained_counts=counts,
              adv={k: v for k, v in adv.items() if k != "per_host"})
    return e2


def e1e2_amended(lock_name: str = "partD_dev") -> dict:
    """AMENDMENT_K1_20261011_3: E2 on survey_k1 -> mode m; E1 (a)-(c) with S retention under m in both arms;
    survey_k1 + m if E1 holds, else survey_k1_s56 with E2 applied on that arm.  Writes k1/results/e1e2_amended.json."""
    EV.verify_lock("partD_S")
    EV.verify_lock(lock_name)
    led = {arm: injections_ledger(arm) for arm in ("k1", "s56")}
    dev = kp_dev_ledger()
    adv = adv_dev_passthrough()
    e2_k1 = _e2_on(led["k1"], "k1", dev, adv)
    m = e2_k1["choice"]
    k1, s56 = led["k1"], led["s56"]
    pool = k1[(k1.snr_exp_k1 >= 7) & (k1.snr_exp_k1 <= 20)][["inj_id", "tic_id", f"S_{m}"]].merge(
        s56[["inj_id", f"S_{m}"]], on="inj_id", suffixes=("_k1", "_s56"))
    a, b = pool[f"S_{m}_k1"].astype(float), pool[f"S_{m}_s56"].astype(float)
    d_pp = 100.0 * (a.mean() - b.mean())
    ci = EV.host_bootstrap(pool.assign(_d=a - b), lambda g: 100.0 * g._d.mean(), n=4000)
    fa = {arm: fa_per_star(arm) for arm in ("k1", "s56")}
    walls = {arm: sum(r["wall_seconds"] for r in EV.search_receipts(f"inj_{arm}").values()) for arm in ("k1", "s56")}
    e1 = RE.e1_cadence(d_pp, ci[0], fa["k1"]["pregate_per_star"] / fa["s56"]["pregate_per_star"], walls["k1"] / walls["s56"])
    e1.update(mode=m, pool_n=int(len(pool)), pool_hosts=int(pool.tic_id.nunique()), R_k1=float(a.mean()), R_s56=float(b.mean()),
              delta_ci=ci, amendment="AMENDMENT_K1_20261011_3")
    if e1["adopt"] == "survey_k1":
        e2_final, frozen = e2_k1, {"preset": "survey_k1", "s_mode": m}
    else:
        e2_final = _e2_on(led["s56"], "s56", dev, adv)
        frozen = {"preset": "survey_k1_s56", "s_mode": e2_final["choice"]}
    out = {"utc": utc(), "E2_on_survey_k1": e2_k1, "E1_under_m": e1, "E2_final": e2_final, "frozen": frozen,
           "adv_per_host": adv["per_host"]}
    (ROOT / "results" / "ledgers").mkdir(parents=True, exist_ok=True)
    dev.to_csv(ROOT / "results" / "ledgers" / "kp_dev_partD_dev.csv", index=False)
    write(ROOT / "results" / "e1e2_amended.json", out, replace=True)
    return out


def fit_linear_logistic(snr, rec):
    """yieldlib form p = cmax / (1 + exp(-(SNR - x50) / w)) (linear SNR), MLE; for the Part G yield re-estimate."""
    from scipy.optimize import minimize
    x = np.asarray(snr, float); y = np.asarray(rec, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]

    def nll(p):
        x50, w, c = p
        pr = np.clip(c / (1 + np.exp(-(x - x50) / max(w, 1e-3))), 1e-9, 1 - 1e-9)
        return -np.sum(y * np.log(pr) + (1 - y) * np.log(1 - pr))
    r = minimize(nll, x0=[15.0, 4.0, 0.6], bounds=[(1, 200), (0.2, 50), (0.02, 1.0)])
    return {"x50": float(r.x[0]), "w": float(r.x[1]), "cmax": float(r.x[2]), "n": int(len(y))}


def main():
    """CALIBRATION_K1 inputs (D4) under the final lock ``partD``, for the frozen arm and S mode
    (k1/results/e1e2_amended.json).  E1-E4 are restated from decisions_E.json, not recomputed."""
    EV.verify_lock("partD")
    dec = read(ROOT / "results" / "decisions_E.json")
    arm = "k1" if dec["E1"]["preset"] == "survey_k1" else "s56"
    mode = dec["E2"]["mode"]
    snr_col = f"snr_exp_{arm}"
    res = {"utc": utc(), "lock": "partD", "frozen": {"arm": arm, "s_mode": mode}, "decisions": dec}
    (ROOT / "results" / "ledgers").mkdir(parents=True, exist_ok=True)
    led = {a: injections_ledger(a) for a in ("k1", "s56")}
    for a, df in led.items():
        df.to_csv(ROOT / "results" / "ledgers" / f"injections_{a}.csv", index=False)
    A = led[arm]
    # C sample: C | S retention by stratum (sampled items only), then combined S x C|S per SNR bin
    man = read(ROOT / "manifests" / "inj_c_sample.json")
    # AMENDMENT_K1_20261012_6: the sample is the items whose sampled candidate's C job completed
    crec = EV.receipts(f"inj_{arm}", "C")
    done = {inj for inj, cid in zip(man["inj_ids"], man["candidate_ids"]) if (crec.get(cid) or {}).get("status") == "COMPLETE"}
    samp = A[A.inj_id.isin(done)].copy()
    import price_survey_k1 as PS
    samp["nbin"] = samp.tic_id.map(lambda t: PS.nbin(PS.n_usable(int(t))))
    res["c_sample_completed"] = {"n": int(len(samp)), "planned": len(man["inj_ids"]), "amendment": "AMENDMENT_K1_20261012_6"}
    res["c_given_s_by_nusable"] = []
    for nb_, g in samp.groupby("nbin"):
        k = int(g.C.astype(bool).sum())
        res["c_given_s_by_nusable"].append({"n_usable": nb_, "n": int(len(g)), "reach_C": k, "frac": k / len(g), "wilson": EV.wilson(k, len(g))})
    strata = [(7, 10), (10, 15), (15, 20), (20, 40), (40, 1e9)]
    cs = []
    for lo, hi in strata:
        g = samp[(samp[snr_col] >= lo) & (samp[snr_col] < hi)]
        k = int(g.C.astype(bool).sum())
        cs.append({"stratum": f"{lo}-{hi}", "n": int(len(g)), "reach_C": k, "frac": (k / len(g)) if len(g) else None,
                   "wilson": EV.wilson(k, len(g)) if len(g) else None,
                   "host_boot": EV.host_bootstrap_prop(g.assign(_c=g.C.astype(bool)), "_c", n=2000) if len(g) else None})
    res["c_given_s"] = cs
    sflag = f"S_{mode}"
    comb = []
    for (lo, hi), c in zip(strata, cs):
        g = A[(A[snr_col] >= lo) & (A[snr_col] < hi)]
        s_frac = float(g[sflag].astype(bool).mean()) if len(g) else None
        comb.append({"bin": f"{lo}-{hi}", "n": int(len(g)), "S": s_frac,
                     "C_given_S": c["frac"], "through_C": (s_frac * c["frac"]) if (s_frac is not None and c["frac"] is not None) else None})
    res["through_C_by_snr"] = comb
    # per-item expected through-C probability for the curve fit: S flag x C|S of its stratum (S-fail items -> 0)
    cmap = {f"{lo}-{hi}": c["frac"] for (lo, hi), c in zip(strata, cs)}
    if cmap.get("7-10") is None:                       # amendment 6: no completed 7-10 C job -> borrow 10-15 (labelled)
        cmap["7-10"] = cmap.get("10-15")
        res["c_given_s_7_10_borrowed_from"] = "10-15"
        for row in comb:
            if row["bin"] == "7-10" and row["S"] is not None and cmap["7-10"] is not None:
                row["C_given_S"], row["through_C"], row["borrowed"] = cmap["7-10"], row["S"] * cmap["7-10"], "10-15"
    def p_c(row):
        if not row[sflag]:
            return 0.0
        for lo, hi in strata:
            if lo <= row[snr_col] < hi:
                return cmap[f"{lo}-{hi}"] or 0.0
        return 0.0
    A = A.assign(_pc=A.apply(p_c, axis=1))
    res["yield_model_through_C"] = fit_linear_logistic(A[snr_col], A._pc)      # fractional targets (cross-entropy)
    res["yield_model_through_S"] = fit_linear_logistic(A[snr_col], A[sflag].astype(float))
    flags = ["search", "pregate", "A", "S_bound", sflag, "B", "C"]
    res["tables"] = {
        "snr": table(A, snr_col, flags, [0, 7, 10, 15, 20, 30, 40, 1e9]),
        "period": table(A, "period", flags, [0.5, 1, 3, 10, 20, 50.0001]),
        "radius": table(A, "rp_rearth", flags, [1, 1.5, 2, 2.83, 4, 8.0001]),
        "tmag": table(A, "tmag", flags, [10, 11, 12, 13.6]),
        "n_usable": table(A, "n_usable", flags, [5, 8, 13, 1000]),
        "class": table(A, "k1_class", flags)}
    res["snr50"] = {f: logistic_snr50(A[snr_col], A[f]) for f in ("search", "pregate", "A", "S_bound", sflag)}
    res["fa_per_star"] = {a: fa_per_star(a) for a in ("k1", "s56")}
    res["partition_limited"] = {a: float(np.mean([r["budget_exhausted_partitions"] > 0 for r in EV.search_receipts(f"inj_{a}").values()]))
                                for a in ("k1", "s56")}
    res["no_data_in_arm"] = {a: [r["job_id"] for r in EV.search_receipts(f"inj_{a}").values() if r.get("status") != "COMPLETE"]
                             for a in ("k1", "s56")}
    dev = kp_dev_ledger()
    dev.to_csv(ROOT / "results" / "ledgers" / "kp_dev.csv", index=False)
    res["dev_planets"] = {"n": int(len(dev)), **{f: int(dev[f].astype(bool).sum()) for f in ("search", "pregate", "A", sflag, "B", "C")},
                          "D": dev.D.value_counts(dropna=False).to_dict()}
    res["dev_adversarial"] = {k: v for k, v in adv_dev_passthrough().items() if k != "per_host"}
    write(ROOT / "results" / "calibration_partD.json", res, replace=True)
    print(json.dumps({k: res[k] for k in ("frozen", "c_given_s", "through_C_by_snr", "yield_model_through_C", "yield_model_through_S",
                                          "snr50", "partition_limited", "dev_planets")}, indent=1, default=str)[:7000])


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "e1e2":
        print(json.dumps({k: v for k, v in e1e2_amended().items() if k != "adv_per_host"}, indent=1, default=str)[:6000])
    elif len(sys.argv) > 1 and sys.argv[1] == "e1":
        (ROOT / "results" / "ledgers").mkdir(parents=True, exist_ok=True)
        print(json.dumps(e1_and_leading(), indent=1, default=str)[:4000])
    else:
        main()
