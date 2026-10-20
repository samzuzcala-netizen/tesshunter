"""K1 Part F evaluation (RULES_K1 section 4; amendments 4-5): G1, G2, G3 on the HELD-OUT sets.

Order enforced: the prediction lock ``partF`` (every HELD-OUT and paired-P12 search result and funnel receipt)
must verify before any HELD-OUT truth is read.  K1 arm = frozen configuration (survey_k1, 8,100 s, S
``bound_alias``; job ``ho_k1_<tic>``); P12 arm = frozen aee65172b ``survey_p10`` + p10.0 funnel on sectors 56-98
(job ``p12_<tic>``; NO_DATA_IN_ARM hosts count as P12 non-recoveries).  Writes ``k1/results/validation_partF.json``
and the per-item ledgers under ``k1/results/ledgers/``.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from k1_common import ROOT, TRUTH, read, write, utc
import evaluate_k1 as EV
import match_k1 as M

FROZEN_MODE = "bound_alias"


def _truth_row(r) -> dict:
    sp = float(np.nanmax(np.abs([r.get("pl_orbpererr1", np.nan), r.get("pl_orbpererr2", np.nan)]))) \
        if np.isfinite(r.get("pl_orbpererr1", np.nan)) else 0.0
    st = float(np.nanmax(np.abs([r.get("pl_tranmiderr1", np.nan), r.get("pl_tranmiderr2", np.nan)]))) \
        if np.isfinite(r.get("pl_tranmiderr1", np.nan)) else 0.0
    return {"tic_id": int(r.tic_id), "period": float(r.pl_orbper), "t0": float(r.t0_btjd),
            "t14": float(r.t14_hours) / 24.0, "sigma_t0": st, "sigma_p": sp}


def kp_ledgers(kp: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in kp.iterrows():
        t = _truth_row(r)
        k = EV.ledger_item(t, f"ho_k1_{int(r.tic_id)}", "ho_k1", "ho_k1", s56=False)
        p = EV.ledger_item(t, f"p12_{int(r.tic_id)}", "p12_paired", "p12_paired", s56=True)
        rows.append({"pl_name": r.pl_name, "tic_id": int(r.tic_id), "period": float(r.pl_orbper),
                     "rp_rearth": r.get("pl_rade"), "tmag": r.get("tic_Tmag"), "k1_class": r.get("k1_class"),
                     "n_usable": r.get("n_usable"), "snr_exp_k1": r.get("snr_exp_k1"), "n_obs_k1": r.get("n_obs_transits_k1"),
                     **{f"k1_{s}": k[s] for s in ("search", "pregate", "A", f"S_{FROZEN_MODE}", "B", "C", "D")},
                     **{f"p12_{s}": p[s] for s in ("search", "pregate", "A", "S_bound", "B", "C")},
                     "k1_paths": len(k["matched_paths"]), "p12_paths": len(p["matched_paths"])})
    return pd.DataFrame(rows)


def adversarial(adv: pd.DataFrame, kp_all: pd.DataFrame) -> dict:
    cands = EV.candidates("ho_k1")
    a, s, b, c, d = (EV.receipts("ho_k1", st) for st in ("A", "S", "B", "C", "D"))
    per, n_sub, n_sub_hold, n_any_sub, n_any_sub_hold = [], 0, 0, 0, 0
    for _, r in adv.iterrows():
        tic = int(r.tic_id)
        rows = cands[cands.job_id == f"ho_k1_{tic}"] if len(cands) else cands
        planets = [_truth_row(x) for _, x in kp_all[kp_all.tic_id == tic].iterrows()]
        times = EV.host_times(tic, False) if planets else None
        best_m, best_any = None, None
        for _, q in rows.iterrows():
            cid = q.candidate_id
            if planets and any(M.match(times, {"period": M.candidate_period(q), "epoch": q.epoch_btjd, "duration": q.duration_days},
                                       pl).get("matched") for pl in planets):
                continue                                     # a known planet of this host, never an adversarial path
            v = ((d.get(cid) or {}).get("verdicts") or {}).get("k1.0", {}).get("verdict")
            if v not in ("SUBMIT", "HOLD"):
                continue
            rank = 0 if v == "SUBMIT" else 1
            best_any = rank if best_any is None else min(best_any, rank)
            if M.period_matches(M.candidate_period(q), float(r.eb_period_days))["matched"]:
                best_m = rank if best_m is None else min(best_m, rank)
        n_sub += best_m == 0
        n_sub_hold += best_m is not None
        n_any_sub += best_any == 0
        n_any_sub_hold += best_any is not None
        per.append({"tic_id": tic, "kind": r.kind, "matched": {0: "SUBMIT", 1: "HOLD", None: None}[best_m],
                    "any": {0: "SUBMIT", 1: "HOLD", None: None}[best_any]})
    n = len(adv)
    return {"n": n, "submit": int(n_sub), "submit_frac": n_sub / n if n else None, "submit_wilson": EV.wilson(int(n_sub), n),
            "submit_or_hold": int(n_sub_hold), "any_candidate_submit": int(n_any_sub),
            "any_candidate_submit_or_hold": int(n_any_sub_hold), "g3_pass": bool(n and n_sub <= 0.05 * n), "per_host": per}


def d_outcomes() -> list:
    out = []
    for cid, rec in sorted(EV.receipts("ho_k1", "D").items()):
        v = (rec.get("verdicts") or {}).get("k1.0") or {}
        out.append({"candidate_id": cid, "verdict": v.get("verdict"), "tier": v.get("candidate_tier"),
                    "deciding_condition": v.get("deciding_condition"), "not_measurable": v.get("not_measurable"),
                    "p12_0": ((rec.get("verdicts") or {}).get("p12.0") or {}).get("verdict")})
    return out


def stage_table(df: pd.DataFrame, by: str, bins) -> list:
    d = df.copy()
    d["bin"] = pd.cut(d[by].astype(float), bins, right=False).astype(str)
    rows = []
    for k, g in d.groupby("bin"):
        row = {"bin": k, "n": int(len(g))}
        for arm, stages in (("k1", ("search", "pregate", "A", f"S_{FROZEN_MODE}", "B", "C")),
                            ("p12", ("search", "pregate", "A", "S_bound", "B", "C"))):
            row[arm] = {s: int(g[f"{arm}_{s}"].astype(bool).sum()) for s in stages}
        rows.append(row)
    return rows


def main() -> dict:
    EV.verify_lock("partF")
    kp_all = pd.read_csv(TRUTH / "known_planets_final.csv")
    kp = kp_all[kp_all.in_final_set & (kp_all.role == "HELDOUT")]
    led = kp_ledgers(kp)
    (ROOT / "results" / "ledgers").mkdir(parents=True, exist_ok=True)
    led.to_csv(ROOT / "results" / "ledgers" / "heldout_kp.csv", index=False)
    coh = led[(led.snr_exp_k1.astype(float) >= 20) & (led.n_obs_k1.astype(float) >= 3)].copy()
    k1c, p12c = coh.k1_C.astype(bool), coh.p12_C.astype(bool)
    g1 = {"n": int(len(coh)), "hosts": int(coh.tic_id.nunique()), "reach_C": int(k1c.sum()),
          "frac": float(k1c.mean()) if len(coh) else None, "wilson": EV.wilson(int(k1c.sum()), len(coh)),
          "host_boot": EV.host_bootstrap_prop(coh.assign(_c=k1c), "_c"), "threshold": 0.60}
    g1["pass"] = bool(g1["frac"] is not None and g1["frac"] >= 0.60)
    coh["_d"] = k1c.astype(float) - p12c.astype(float)
    g2 = {"n": int(len(coh)), "k1_C": int(k1c.sum()), "p12_C": int(p12c.sum()),
          "delta_pp": 100.0 * float(coh._d.mean()) if len(coh) else None,
          "host_boot_pp": EV.host_bootstrap(coh, lambda g: 100.0 * g._d.mean(), n=4000),
          "k1_only": int((k1c & ~p12c).sum()), "p12_only": int((~k1c & p12c).sum()), "threshold_pp": -5.0}
    g2["pass"] = bool(g2["delta_pp"] is not None and g2["delta_pp"] >= -5.0)
    adv_all = pd.read_csv(TRUTH / "adversarial_truth.csv")
    g3 = adversarial(adv_all[adv_all.role == "HELDOUT"], kp_all)
    res = {"utc": utc(), "lock": "partF", "frozen_mode": FROZEN_MODE, "G1": g1, "G2": g2, "G3": g3,
           "all_heldout_planets": {"n": int(len(led)), **{f"k1_{s}": int(led[f"k1_{s}"].astype(bool).sum())
                                                         for s in ("search", "pregate", "A", f"S_{FROZEN_MODE}", "B", "C")},
                                   **{f"p12_{s}": int(led[f"p12_{s}"].astype(bool).sum())
                                      for s in ("search", "pregate", "A", "S_bound", "B", "C")}},
           "d_verdicts_recovered": led[led.k1_C.astype(bool)][["pl_name", "tic_id", "k1_D"]].to_dict(orient="records"),
           "d_outcomes": d_outcomes(),
           "tables": {"snr": stage_table(led, "snr_exp_k1", [0, 7, 10, 15, 20, 30, 40, 1e9]),
                      "period": stage_table(led, "period", [0.5, 1, 3, 10, 20, 50.0001, 1e9]),
                      "radius": stage_table(led, "rp_rearth", [0, 1.5, 2, 2.83, 4, 8, 1e9]),
                      "tmag": stage_table(led, "tmag", [0, 10, 11, 12, 13.6, 99]),
                      "n_usable": stage_table(led, "n_usable", [0, 5, 8, 13, 1000])}}
    write(ROOT / "results" / "validation_partF.json", res, replace=True)
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in ("G1", "G2")}, indent=1, default=str))
    print(json.dumps({k: v for k, v in r["G3"].items() if k != "per_host"}, indent=1, default=str))
