"""K2 evaluator (truth side): rules C1, A1, M1 on the K1 reference sets, prediction locks, G1-G3.

Runs WITHOUT ``K1_DATA`` set, so ``evaluate_k1`` (EV) reads K1's runs and receipts; K2 receipts are read from
``D:/tesshunter_k2`` explicitly.  Truth is read only after the relevant K1 lock verifies (partD for R-C / R-A,
partF for the seen set) or K2's own lock (the fresh set).  Workers never import this module.
"""
from __future__ import annotations

import glob
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from k2_common import (K1, K2, K2_DATA, K1_RECEIPTS, K2_RECEIPTS, K1_TRUTH, K2_TRUTH, read, write, sha, utc)
import evaluate_k1 as EV
import match_k1 as M
import plan_k2 as PK

FROZEN_S_MODE = "bound_alias"


# ── generic helpers ───────────────────────────────────────────────────────────
@lru_cache(maxsize=None)
def k2_receipts(label: str, stage: str) -> dict:
    return PK.receipts(K2_RECEIPTS, label, stage)


def endpoint(c_rec: dict | None, truth_period: float) -> bool:
    """RULES_K1 1.5 at Stage C: decision PASS and the blind period re-matches the truth period."""
    if not c_rec or c_rec.get("status") != "COMPLETE" or c_rec.get("decision") != "PASS":
        return False
    bp = ((c_rec.get("measurement") or {}).get("blind") or {}).get("period")
    return bool(bp and M.period_matches(float(bp), float(truth_period))["matched"])


def paired_host_bootstrap(df: pd.DataFrame, a: str, b: str, n: int = 10000, seed: int = 20261011) -> tuple:
    """Percentile 95% interval of mean(b) - mean(a) (items equally weighted) under host resampling."""
    g = pd.DataFrame({"tic_id": df.tic_id.values, "d": df[b].astype(float).values - df[a].astype(float).values,
                      "n": 1.0}).groupby("tic_id").sum()
    k, m = g.d.to_numpy(), g.n.to_numpy()
    rng = np.random.default_rng(seed)
    H = len(g)
    out = np.empty(n)
    for i in range(0, n, 500):
        bsz = min(500, n - i)
        idx = rng.integers(0, H, (bsz, H))
        cnt = np.zeros((bsz, H))
        np.add.at(cnt, (np.repeat(np.arange(bsz), H), idx.ravel()), 1.0)
        out[i:i + bsz] = (cnt @ k) / np.maximum(cnt @ m, 1e-12)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def kp_truth_row(r) -> dict:
    sp = float(np.nanmax(np.abs([r.get("pl_orbpererr1", np.nan), r.get("pl_orbpererr2", np.nan)]))) \
        if np.isfinite(r.get("pl_orbpererr1", np.nan)) else 0.0
    st = float(np.nanmax(np.abs([r.get("pl_tranmiderr1", np.nan), r.get("pl_tranmiderr2", np.nan)]))) \
        if np.isfinite(r.get("pl_tranmiderr1", np.nan)) else 0.0
    return {"tic_id": int(r.tic_id), "period": float(r.pl_orbper), "t0": float(r.t0_btjd),
            "t14": float(r.t14_hours) / 24.0, "sigma_t0": st, "sigma_p": sp}


def matched_ids(cands: pd.DataFrame, job_id: str, truth: dict, times) -> list[str]:
    rows = cands[cands.job_id == job_id]
    out = []
    for _, r in rows.iterrows():
        mm = M.match(times, {"period": M.candidate_period(r), "epoch": r.epoch_btjd, "duration": r.duration_days}, truth)
        if mm.get("matched"):
            out.append(r.candidate_id)
    return out


# ── R-C items (RULES_K2 2.2) ──────────────────────────────────────────────────
def rc_items() -> pd.DataFrame:
    """One row per (item, R-C path): 58 injection-sample items and the DEV planets with an R-C path."""
    EV.verify_lock("partD")
    rc = PK.rc_table().set_index("candidate_id")
    rows = []
    inj_paths = rc[rc.k1_label == "inj_k1"]
    for cid in inj_paths.index:
        inj_id = cid.rsplit("_k1_", 1)[0]
        t = read(K1_TRUTH / "injections" / f"{inj_id}.json")
        rows.append({"item": inj_id, "kind": "inj", "tic_id": int(t["tic_id"]), "candidate_id": cid,
                     "truth_period": float(t["period"]), "snr_exp_k1": float(t["snr_exp_k1"] or 0.0)})
    kp = pd.read_csv(K1_TRUTH / "known_planets_final.csv")
    kp = kp[kp.in_final_set & (kp.role == "DEV")]
    cands = EV.candidates("dev_k1")
    for _, r in kp.iterrows():
        t = kp_truth_row(r)
        ids = [c for c in matched_ids(cands, f"dev_k1_{t['tic_id']}", t, EV.host_times(t["tic_id"], False)) if c in rc.index]
        for c in ids:
            rows.append({"item": r.pl_name, "kind": "dev_kp", "tic_id": t["tic_id"], "candidate_id": c,
                         "truth_period": t["period"], "snr_exp_k1": float(r.snr_exp_k1)})
    df = pd.DataFrame(rows)
    df["n_usable"] = df.candidate_id.map(rc.n_usable)
    return df


def c1_evaluate(variant_label: str, k1_label_c: dict | None = None) -> dict:
    """Rule C1 (a)-(c) for one variant label (e.g. ``rc_v3``) against K1's R-C receipts."""
    rc = PK.rc_table()
    k1c = {**EV.receipts("dev_k1", "C"), **EV.receipts("inj_k1", "C")}
    var = k2_receipts(variant_label, "C")
    paths = rc_items()
    paths["k1"] = [endpoint(k1c.get(c), p) for c, p in zip(paths.candidate_id, paths.truth_period)]
    paths["var"] = [endpoint(var.get(c), p) for c, p in zip(paths.candidate_id, paths.truth_period)]
    items = paths.groupby(["item", "kind", "tic_id"], as_index=False).agg(k1=("k1", "max"), var=("var", "max"),
                                                                          snr_exp_k1=("snr_exp_k1", "first"))
    missing = [c for c in rc.candidate_id if c not in var or var[c].get("status") != "COMPLETE"]
    n = len(items)
    r_k1, r_var = float(items.k1.mean()), float(items["var"].mean())
    lo, hi = paired_host_bootstrap(items, "k1", "var")
    a = {"n_items": n, "n_inj": int((items.kind == "inj").sum()), "n_dev_planets": int((items.kind == "dev_kp").sum()),
         "k1_endpoint": int(items.k1.sum()), "variant_endpoint": int(items["var"].sum()),
         "R_k1": r_k1, "R_variant": r_var, "delta_pp": 100 * (r_var - r_k1), "boot95_pp": (100 * lo, 100 * hi),
         "lost": items[items.k1 & ~items["var"]][["item", "kind", "tic_id"]].to_dict(orient="records"),
         "gained": items[~items.k1 & items["var"]][["item", "kind", "tic_id"]].to_dict(orient="records")}
    a["pass"] = bool(a["delta_pp"] >= -2.0 and 100 * lo >= -5.0)
    adv = pd.read_csv(K1_TRUTH / "adversarial_truth.csv")
    dev_adv = set(adv[adv.role == "DEV"].tic_id.astype(int))
    adv_jobs = rc[rc.tic_id.isin(dev_adv)]
    flips = [c for c in adv_jobs.candidate_id if (k1c.get(c) or {}).get("decision") == "FAIL"
             and (var.get(c) or {}).get("decision") == "PASS"]
    b = {"n_adv_jobs": int(len(adv_jobs)), "k1_fail": int(sum((k1c.get(c) or {}).get("decision") == "FAIL" for c in adv_jobs.candidate_id)),
         "now_pass": flips, "pass": not flips}
    rows = []
    for r in rc.itertuples():
        v = var.get(r.candidate_id) or {}
        k = k1c.get(r.candidate_id) or {}
        vb = ((v.get("measurement") or {}).get("blind") or {})
        kb = ((k.get("measurement") or {}).get("blind") or {})
        rows.append({"candidate_id": r.candidate_id, "n_usable": r.n_usable, "n_class": r.n_class, "tic_id": r.tic_id,
                     "k1_wall": k.get("wall_seconds"), "var_wall": v.get("wall_seconds"),
                     "k1_decision": k.get("decision"), "var_decision": v.get("decision"),
                     "k1_period": kb.get("period"), "var_period": vb.get("period"), "k1_sde": kb.get("SDE"),
                     "var_sde": vb.get("SDE"), "oversampling": ((v.get("k2") or {}).get("c_input") or {}).get("oversampling"),
                     "n_k1_input": ((v.get("k2") or {}).get("c_input") or {}).get("n_k1_input"),
                     "n_c_input": ((v.get("k2") or {}).get("c_input") or {}).get("n_c_input")})
    jobs = pd.DataFrame(rows)
    done = jobs[jobs.var_wall.notna()]
    ge20 = done[done.n_usable >= 20]
    c = {"n_jobs_ge20": int(len(ge20)), "k1_median_wall_s": float(ge20.k1_wall.median()) if len(ge20) else None,
         "variant_median_wall_s": float(ge20.var_wall.median()) if len(ge20) else None}
    c["speedup"] = (c["k1_median_wall_s"] / c["variant_median_wall_s"]) if len(ge20) else None
    c["median_per_job_ratio"] = float((ge20.k1_wall / ge20.var_wall).median()) if len(ge20) else None
    c["pass"] = bool(c["speedup"] is not None and c["speedup"] >= 3.0)
    agree = []
    for cls, g in done.groupby("n_class"):
        same_dec = (g.k1_decision == g.var_decision)
        same_p = [bool(kp_ and vp and abs(vp / kp_ - 1) < 0.01) for kp_, vp in zip(g.k1_period, g.var_period)]
        agree.append({"n_class": cls, "n": int(len(g)), "decision_agree": int(same_dec.sum()),
                      "blind_period_agree": int(sum(same_p)), "k1_median_wall_s": float(g.k1_wall.median()),
                      "variant_median_wall_s": float(g.var_wall.median()),
                      "wall_ratio_median": float((g.k1_wall / g.var_wall).median())})
    flipped = done[done.k1_decision != done.var_decision][["candidate_id", "n_usable", "k1_decision", "var_decision",
                                                           "k1_period", "var_period", "k1_sde", "var_sde"]]
    return {"utc": utc(), "variant_label": variant_label, "complete": int(len(done)), "missing": missing,
            "a": a, "b": b, "c": c, "qualifies": bool(a["pass"] and b["pass"] and c["pass"] and not missing),
            "agreement_by_class": agree, "flipped": flipped.to_dict(orient="records"),
            "jobs": jobs.to_dict(orient="records")}


def timing_summary(variant_label: str) -> dict:
    """The 10-job timing check: per-class variant/K1 wall ratios (pricing input, RULES_K2 7)."""
    rc = PK.rc_table()
    var = k2_receipts(variant_label, "C")
    rows = []
    for r in rc.itertuples():
        v = var.get(r.candidate_id)
        if v and v.get("status") == "COMPLETE":
            rows.append({"candidate_id": r.candidate_id, "n_usable": r.n_usable, "n_class": r.n_class,
                         "k1_wall": r.k1_wall_s, "var_wall": v["wall_seconds"], "ratio": v["wall_seconds"] / r.k1_wall_s,
                         "k1_decision": r.k1_decision, "var_decision": v.get("decision"),
                         "oversampling": v["k2"]["c_input"]["oversampling"], "n_k1_input": v["k2"]["c_input"]["n_k1_input"],
                         "n_c_input": v["k2"]["c_input"]["n_c_input"]})
    df = pd.DataFrame(rows)
    by = df.groupby("n_class").agg(n=("ratio", "size"), ratio_median=("ratio", "median"),
                                   k1_wall_median=("k1_wall", "median"), var_wall_median=("var_wall", "median"))
    return {"utc": utc(), "variant_label": variant_label, "jobs": df.to_dict(orient="records"),
            "by_class": by.reset_index().to_dict(orient="records"),
            "overall_ratio_median": float(df.ratio.median()) if len(df) else None,
            "wall_weighted_ratio": float(df.var_wall.sum() / df.k1_wall.sum()) if len(df) else None}


# ── A1 (RULES_K2 3.3) ─────────────────────────────────────────────────────────
def a_decisions(scope: str | None) -> dict:
    """Stage A decision of every R-A pre-gate candidate under a scope: K1's receipt, overridden by the ra_a1
    re-run (decision re-derived for the scope) where one exists.  None = K1."""
    df = pd.read_csv(K2_DATA / "ra_table.csv")
    k2a = k2_receipts("ra_a1", "A")
    out = {}
    for r in df.itertuples():
        dec = r.k1_decision if r.k1_status == "COMPLETE" else None
        rec = k2a.get(r.candidate_id)
        if scope and rec and rec.get("status") == "COMPLETE":
            dec = PK.a1_decision(rec["measurement"], scope)
        out[r.candidate_id] = dec
    return out


def determinism_check() -> dict:
    """RULES_K2 3.2: every ra_a1 re-run's K1-scope decision equals its K1 receipt, and the 20 K1 A-PASS candidates
    PASS with their K1 per-ephemeris p_const reproduced."""
    sel = read(K2 / "manifests" / "ra_a1_selection.json")
    k2a = k2_receipts("ra_a1", "A")
    k1a = {**EV.receipts("inj_k1", "A"), **EV.receipts("fa_k1", "A"), **EV.receipts("dev_k1", "A")}
    bad, n = [], 0
    for row in sel["rows"]:
        cid = row["candidate_id"]
        rec = k2a.get(cid)
        if not rec or rec.get("status") != "COMPLETE":
            continue
        n += 1
        k1m = k1a[cid]["measurement"]
        if PK.a1_decision(rec["measurement"], None) != k1a[cid]["decision"]:
            bad.append({"candidate_id": cid, "why": "K1-scope decision differs"})
        pc_k2 = {s: pe["det_kept"].get("p_const") for s, pe in rec["measurement"]["per_ephemeris"].items()}
        pc_k1 = {s: pe["det_kept"].get("p_const") for s, pe in k1m["per_ephemeris"].items()}
        if pc_k2 != pc_k1:
            bad.append({"candidate_id": cid, "why": "per-ephemeris p_const differs", "k1": pc_k1, "k2": pc_k2})
        if row["purpose"] == "determinism" and rec.get("decision") != "PASS":
            bad.append({"candidate_id": cid, "why": "K1 PASS not PASS under A1"})
    return {"n_checked": n, "n_rows": len(sel["rows"]), "mismatches": bad, "pass": not bad}


def a1_evaluate() -> dict:
    EV.verify_lock("partD")
    det = determinism_check()
    inj = [read(p) for p in sorted(glob.glob(str(K1_TRUTH / "injections" / "inj_*.json")))]
    inj = [t for t in inj if float(t.get("snr_exp_k1") or 0.0) >= 20.0]
    cands = EV.candidates("inj_k1")
    pre = cands[cands.passes_pregate]
    matched = {}
    for t in inj:
        truth = {"tic_id": t["tic_id"], "period": t["period"], "t0": t["t0"], "t14": t["t14_days"], "sigma_t0": 0.0, "sigma_p": 0.0}
        matched[t["inj_id"]] = matched_ids(pre, f"{t['inj_id']}_k1", truth, EV.host_times(int(t["tic_id"]), False))
    ra = pd.read_csv(K2_DATA / "ra_table.csv")
    adv = pd.read_csv(K1_TRUTH / "adversarial_truth.csv")
    dev_adv = set(adv[adv.role == "DEV"].tic_id.astype(int))
    fa = ra[ra.k1_label == "fa_k1"]
    advc = ra[(ra.k1_label == "dev_k1") & ra.tic_id.isin(dev_adv)]
    out = {"utc": utc(), "determinism": det, "pool_injections": len(inj), "scopes": {}}
    base = None
    for scope in (None, "author", "author_exposure"):
        dec = a_decisions(scope)
        ret = sum(any(dec.get(c) == "PASS" for c in ids) for ids in matched.values())
        fa_pass = int(sum(dec.get(c) == "PASS" for c in fa.candidate_id))
        adv_pass = int(sum(dec.get(c) == "PASS" for c in advc.candidate_id))
        adv_hosts = int(advc.assign(p=[dec.get(c) == "PASS" for c in advc.candidate_id]).groupby("tic_id").p.max().sum())
        row = {"inj_retained_A": int(ret), "inj_retention_A": ret / len(inj), "fa_A_pass": fa_pass, "fa_per_star": fa_pass / 250.0,
               "adv_candidates": int(len(advc)), "adv_A_pass": adv_pass, "adv_A_rate": adv_pass / max(len(advc), 1),
               "adv_hosts_with_A_pass": adv_hosts, "adv_hosts": len(dev_adv)}
        if scope is None:
            base = row
        else:
            row["delta_retention_pp"] = 100 * (row["inj_retention_A"] - base["inj_retention_A"])
            row["fa_ratio"] = row["fa_per_star"] / base["fa_per_star"] if base["fa_per_star"] else None
            row["delta_adv_rate_pp"] = 100 * (row["adv_A_rate"] - base["adv_A_rate"])
            row["i"] = bool(row["delta_retention_pp"] >= 3.0)
            row["ii"] = bool(row["fa_ratio"] is not None and row["fa_ratio"] <= 1.2)
            row["iii"] = bool(row["delta_adv_rate_pp"] <= 5.0)
            row["qualifies"] = bool(row["i"] and row["ii"] and row["iii"])
        out["scopes"][scope or "K1"] = row
    adopted = None
    if det["pass"]:
        for scope in ("author", "author_exposure"):
            if out["scopes"][scope]["qualifies"]:
                adopted = scope
                break
    out["adopted"] = adopted
    return out


# ── M1 (RULES_K2 4.2) ─────────────────────────────────────────────────────────
def c_receipts(label: str) -> dict:
    if label == "K1":
        return {**EV.receipts("dev_k1", "C"), **EV.receipts("inj_k1", "C")}
    return dict(k2_receipts(label, "C"))


def m1_evaluate(c1_label: str, m1_label: str) -> dict:
    base = c_receipts(c1_label)
    m1 = k2_receipts(m1_label, "C")
    with_m1 = dict(base, **m1)
    paths = rc_items()
    paths["c1"] = [endpoint(base.get(c), p) for c, p in zip(paths.candidate_id, paths.truth_period)]
    paths["m1"] = [endpoint(with_m1.get(c), p) for c, p in zip(paths.candidate_id, paths.truth_period)]
    items = paths.groupby(["item", "kind", "tic_id"], as_index=False).agg(c1=("c1", "max"), m1=("m1", "max"))
    kp = pd.read_csv(K1_TRUTH / "known_planets_final.csv")
    kp = kp[kp.in_final_set & (kp.role == "DEV")]
    multi = set(kp.groupby("tic_id").size().loc[lambda s: s >= 2].index.astype(int))
    dev = items[items.kind == "dev_kp"]
    dm = dev[dev.tic_id.isin(multi)]
    adv = pd.read_csv(K1_TRUTH / "adversarial_truth.csv")
    dev_adv = set(adv[adv.role == "DEV"].tic_id.astype(int))
    d = k2_receipts(m1_label, "D")
    gained = []
    for cid, rec in d.items():
        v = ((rec.get("verdicts") or {}).get("k1.0") or {}).get("verdict")
        if int(rec["tic_id"]) in dev_adv and v in ("SUBMIT", "HOLD"):
            gained.append({"candidate_id": cid, "verdict": v})
    res = {"utc": utc(), "c1_label": c1_label, "m1_label": m1_label, "n_m1_jobs": len(m1),
           "m1_flips": [{"candidate_id": c, "c1": (base.get(c) or {}).get("decision"), "m1": r.get("decision"),
                         "c1_period": (((base.get(c) or {}).get("measurement") or {}).get("blind") or {}).get("period"),
                         "m1_period": ((r.get("measurement") or {}).get("blind") or {}).get("period")}
                        for c, r in m1.items()],
           "dev_planets": {"n": int(len(dev)), "c1": int(dev.c1.sum()), "m1": int(dev.m1.sum())},
           "dev_multi_planet_hosts": {"hosts": len(multi), "n": int(len(dm)), "c1": int(dm.c1.sum()), "m1": int(dm.m1.sum())},
           "injections": {"n": int((items.kind == "inj").sum()), "c1": int(items[items.kind == "inj"].c1.sum()),
                          "m1": int(items[items.kind == "inj"].m1.sum())},
           "dev_adversarial_gained_submit_hold": gained, "d_receipts": len(d)}
    res["rule_recovery"] = bool(res["dev_planets"]["m1"] >= res["dev_planets"]["c1"]
                                and res["dev_multi_planet_hosts"]["m1"] > res["dev_multi_planet_hosts"]["c1"])
    res["rule_adversarial"] = not gained
    res["adopt"] = bool(res["rule_recovery"] and res["rule_adversarial"])
    return res


# ── prediction locks (K2) ────────────────────────────────────────────────────
LOCK_SETS = {
    "seen": {"runs": [("K1", "ho_k1"), ("K1", "p12_paired")],
             "receipts": [("K1", "ho_k1"), ("K1", "p12_paired"), ("K2", "seen_a1"), ("K2", "seen_c")]},
    "fresh": {"runs": [("K2", "fr_k1"), ("K2", "fr_p12")], "receipts": [("K2", "fr_k1"), ("K2", "fr_p12")]},
}


def _base(which: str, kind: str) -> Path:
    from k2_common import K1_RUNS, K2_RUNS
    return {("K1", "runs"): K1_RUNS, ("K2", "runs"): K2_RUNS, ("K1", "rec"): K1_RECEIPTS, ("K2", "rec"): K2_RECEIPTS}[(which, kind)]


def lock_files(name: str) -> list[str]:
    spec = LOCK_SETS[name]
    files = []
    for which, ph in spec["runs"]:
        b = _base(which, "runs") / ph
        files += sorted(glob.glob(str(b / "results" / "*.json"))) + sorted(glob.glob(str(b / "receipts" / "*.json")))
        files += [str(b / "candidates.csv")] if (b / "candidates.csv").exists() else []
    for which, lb in spec["receipts"]:
        files += sorted(glob.glob(str(_base(which, "rec") / lb / "*" / "*.json")))
    return files


def lock(name: str) -> dict:
    files = lock_files(name)
    hashes = {f: sha(f) for f in files}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    rec = {"name": name, "utc": utc(), "n_files": len(files), "bundle_sha256": digest, "hashes": hashes}
    write(K2 / "manifests" / f"prediction_lock_{name}.json", rec)
    return {k: v for k, v in rec.items() if k != "hashes"}


def verify_lock(name: str) -> dict:
    rec = read(K2 / "manifests" / f"prediction_lock_{name}.json")
    changed = [f for f, h in rec["hashes"].items() if not Path(f).exists() or sha(f) != h]
    if changed:
        raise RuntimeError(f"K2 prediction lock {name}: {len(changed)} files changed since the lock")
    return rec


# ── G1-G3 (RULES_K2 6) ────────────────────────────────────────────────────────
def merged(pairs: list[tuple[Path, str]], stage: str) -> dict:
    out = {}
    for base, lb in pairs:                                   # later pairs override earlier ones
        out.update(PK.receipts(base, lb, stage))
    return out


def path_ledger(truth: dict, job_id: str, cands: pd.DataFrame, R: dict, times, s_mode: str) -> dict:
    out = {"search": False, "pregate": False, "A": False, "S": False, "B": False, "C": False, "D": None, "paths": []}
    best = None
    for _, r in cands[cands.job_id == job_id].iterrows():
        mm = M.match(times, {"period": M.candidate_period(r), "epoch": r.epoch_btjd, "duration": r.duration_days}, truth)
        if not mm.get("matched"):
            continue
        cid = r.candidate_id
        out["paths"].append(cid)
        out["search"] = True
        if not bool(r.passes_pregate):
            continue
        out["pregate"] = True
        if (R["A"].get(cid) or {}).get("decision") != "PASS":
            continue
        out["A"] = True
        if ((R["S"].get(cid) or {}).get("gate_by_mode") or {}).get(s_mode) in ("PASS", "HOLD"):
            out["S"] = True
        if (R["B"].get(cid) or {}).get("decision") != "PASS":
            continue
        out["B"] = True
        if endpoint(R["C"].get(cid), truth["period"]):
            out["C"] = True
            v = (((R["D"].get(cid) or {}).get("verdicts") or {}).get("k1.0") or {}).get("verdict")
            if v:
                rank = {"SUBMIT": 0, "HOLD": 1, "KILL": 2}.get(v, 3)
                if best is None or rank < best[0]:
                    best = (rank, v)
    out["D"] = best[1] if best else None
    return out


def host_times_store(tic: int, store: Path) -> np.ndarray:
    import inject_k1 as I
    return I.prepared(I.load_products(int(tic), root=store))["time"]


def gates(set_name: str) -> dict:
    from k2_common import K1_RUNS, K2_RUNS, K1_STORE, K2_STORE
    verify_lock(set_name)
    if set_name == "seen":
        EV.verify_lock("partF")
        kp_all = pd.read_csv(K1_TRUTH / "known_planets_final.csv")
        kp = kp_all[kp_all.in_final_set & (kp_all.role == "HELDOUT")]
        adv_all = pd.read_csv(K1_TRUTH / "adversarial_truth.csv")
        adv = adv_all[adv_all.role == "HELDOUT"]
        k_run, p_run, store = K1_RUNS / "ho_k1", K1_RUNS / "p12_paired", K1_STORE
        k_job, p_job = "ho_k1_{}", "p12_{}"
        Rk = {"A": merged([(K1_RECEIPTS, "ho_k1"), (K2_RECEIPTS, "seen_a1")], "A"),
              "S": merged([(K1_RECEIPTS, "ho_k1"), (K2_RECEIPTS, "seen_a1")], "S"),
              "B": merged([(K1_RECEIPTS, "ho_k1"), (K2_RECEIPTS, "seen_a1")], "B"),
              "C": merged([(K2_RECEIPTS, "seen_c")], "C"), "D": merged([(K2_RECEIPTS, "seen_c")], "D")}
        Rp = {st: merged([(K1_RECEIPTS, "p12_paired")], st) for st in ("A", "S", "B", "C", "D")}
    else:
        kp_all = pd.read_csv(K2_TRUTH / "fresh_kp_final.csv")
        kp = kp_all[kp_all.in_final_set]
        adv = pd.read_csv(K2_TRUTH / "fresh_adversarial_truth.csv")
        k_run, p_run, store = K2_RUNS / "fr_k1", K2_RUNS / "fr_p12", K2_STORE
        k_job, p_job = "fr_k1_{}", "p12_{}"
        Rk = {st: merged([(K2_RECEIPTS, "fr_k1")], st) for st in ("A", "S", "B", "C", "D")}
        Rp = {st: merged([(K2_RECEIPTS, "fr_p12")], st) for st in ("A", "S", "B", "C", "D")}
    kc, pc = pd.read_csv(k_run / "candidates.csv"), pd.read_csv(p_run / "candidates.csv")
    rows = []
    for _, r in kp.iterrows():
        t = kp_truth_row(r)
        times = host_times_store(t["tic_id"], store)
        lk = path_ledger(t, k_job.format(t["tic_id"]), kc, Rk, times, FROZEN_S_MODE)
        lp = path_ledger(t, p_job.format(t["tic_id"]), pc, Rp, times_s56(t["tic_id"], store), "bound")
        rows.append({"pl_name": r.pl_name, "tic_id": t["tic_id"], "period": t["period"], "rp_rearth": r.get("pl_rade"),
                     "tmag": r.get("tic_Tmag"), "snr_exp_k1": r.get("snr_exp_k1"), "n_obs_k1": r.get("n_obs_transits_k1"),
                     **{f"k2_{s}": lk[s] for s in ("search", "pregate", "A", "S", "B", "C", "D")},
                     **{f"p12_{s}": lp[s] for s in ("search", "pregate", "A", "S", "B", "C")}})
    led = pd.DataFrame(rows)
    coh = led[(led.snr_exp_k1.astype(float) >= 20) & (led.n_obs_k1.astype(float) >= 3)].copy()
    kc_, pc_ = coh.k2_C.astype(bool), coh.p12_C.astype(bool)
    g1 = {"n": int(len(coh)), "hosts": int(coh.tic_id.nunique()), "reach_C": int(kc_.sum()),
          "frac": float(kc_.mean()) if len(coh) else None, "wilson": EV.wilson(int(kc_.sum()), len(coh)),
          "host_boot": EV.host_bootstrap_prop(coh.assign(_c=kc_), "_c") if len(coh) else None, "threshold": 0.60}
    g1["pass"] = bool(g1["frac"] is not None and g1["frac"] >= 0.60)
    coh["_k"], coh["_p"] = kc_.astype(float), pc_.astype(float)
    g2 = {"n": int(len(coh)), "k2_C": int(kc_.sum()), "p12_C": int(pc_.sum()),
          "delta_pp": 100.0 * float((coh._k - coh._p).mean()) if len(coh) else None,
          "host_boot_pp": tuple(100 * x for x in paired_host_bootstrap(coh, "_p", "_k")) if len(coh) else None,
          "k2_only": int((kc_ & ~pc_).sum()), "p12_only": int((~kc_ & pc_).sum()), "threshold_pp": -5.0}
    g2["pass"] = bool(g2["delta_pp"] is not None and g2["delta_pp"] >= -5.0)
    g3 = adversarial_gate(adv, kp_all, kc, Rk, k_job, store)
    losses = []
    for _, r in coh[~kc_].iterrows():
        last = next((s for s in ("B", "S", "A", "pregate", "search") if r[f"k2_{s}"]), None)
        losses.append({"pl_name": r.pl_name, "tic_id": int(r.tic_id), "snr_exp_k1": r.snr_exp_k1,
                       "last_stage_reached": last, "lost_at": {None: "search", "search": "pregate", "pregate": "A",
                                                               "A": "S", "S": "B", "B": "C"}[last]})
    return {"utc": utc(), "set": set_name, "label": "seen set, design-informed" if set_name == "seen" else "fresh",
            "G1": g1, "G2": g2, "G3": g3, "losses": losses, "ledger": led.to_dict(orient="records"),
            "all_planets": {"n": int(len(led)), **{f"k2_{s}": int(led[f"k2_{s}"].astype(bool).sum()) for s in ("search", "pregate", "A", "S", "B", "C")},
                            **{f"p12_{s}": int(led[f"p12_{s}"].astype(bool).sum()) for s in ("search", "pregate", "A", "S", "B", "C")}},
            "d_verdicts_recovered": led[led.k2_C.astype(bool)][["pl_name", "tic_id", "k2_D"]].to_dict(orient="records")}


def times_s56(tic: int, store: Path) -> np.ndarray:
    import inject_k1 as I
    prep = I.prepared(I.load_products(int(tic), root=store))
    return prep["time"][prep["sector"] >= 56]


def adversarial_gate(adv: pd.DataFrame, kp_all: pd.DataFrame, cands: pd.DataFrame, R: dict, k_job: str, store: Path) -> dict:
    per, n_sub, n_sub_hold, n_any_sub, n_any_hold = [], 0, 0, 0, 0
    for _, r in adv.iterrows():
        tic = int(r.tic_id)
        rows = cands[cands.job_id == k_job.format(tic)]
        planets = [kp_truth_row(x) for _, x in kp_all[kp_all.tic_id == tic].iterrows()]
        times = host_times_store(tic, store) if planets else None
        best_m, best_any = None, None
        for _, q in rows.iterrows():
            cid = q.candidate_id
            if planets and any(M.match(times, {"period": M.candidate_period(q), "epoch": q.epoch_btjd,
                                               "duration": q.duration_days}, pl).get("matched") for pl in planets):
                continue
            v = (((R["D"].get(cid) or {}).get("verdicts") or {}).get("k1.0") or {}).get("verdict")
            if v not in ("SUBMIT", "HOLD"):
                continue
            rank = 0 if v == "SUBMIT" else 1
            best_any = rank if best_any is None else min(best_any, rank)
            if M.period_matches(M.candidate_period(q), float(r.eb_period_days))["matched"]:
                best_m = rank if best_m is None else min(best_m, rank)
        n_sub += best_m == 0
        n_sub_hold += best_m is not None
        n_any_sub += best_any == 0
        n_any_hold += best_any is not None
        per.append({"tic_id": tic, "kind": r.kind, "matched": {0: "SUBMIT", 1: "HOLD", None: None}[best_m],
                    "any": {0: "SUBMIT", 1: "HOLD", None: None}[best_any]})
    n = len(adv)
    return {"n": n, "submit": int(n_sub), "submit_frac": n_sub / n if n else None, "submit_wilson": EV.wilson(int(n_sub), n),
            "submit_or_hold": int(n_sub_hold), "any_candidate_submit": int(n_any_sub),
            "any_candidate_submit_or_hold": int(n_any_hold), "pass": bool(n and n_sub <= 0.05 * n), "per_host": per}


def decisions() -> dict:
    """``k2/results/decisions_k2.json`` from the three rule evaluations (input of freeze_k2.py)."""
    c1 = read(K2 / "results" / "c1_rc_v3a.json")
    a1 = read(K2 / "results" / "a1.json")
    m1 = read(K2 / "results" / "m1_m1_v3.json")
    dec = {"utc": utc(),
           "C1": {"adopted": "V3" if c1["qualifies"] else None, "label": "rc_v3a", "bin_errors": "propagated",
                  "amendment": "AMENDMENT_K2_20261014_1", "a": c1["a"]["delta_pp"], "a_boot95_pp": c1["a"]["boot95_pp"],
                  "b_flips": c1["b"]["now_pass"], "c_speedup": c1["c"]["speedup"]},
           "A1": {"adopted": a1["adopted"], **{s: {k: v for k, v in a1["scopes"][s].items() if k in
                                                   ("delta_retention_pp", "fa_ratio", "delta_adv_rate_pp", "qualifies")}
                                               for s in ("author", "author_exposure")}},
           "M1": {"adopted": bool(m1["adopt"]), "dev_planets": m1["dev_planets"], "dev_multi": m1["dev_multi_planet_hosts"],
                  "adversarial_gained": m1["dev_adversarial_gained_submit_hold"]}}
    write(K2 / "results" / "decisions_k2.json", dec, replace=True)
    return dec


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1]
    if cmd == "timing":
        out = timing_summary(sys.argv[2])
        write(K2 / "results" / f"timing_{sys.argv[2]}.json", out, replace=True)
    elif cmd == "c1":
        out = c1_evaluate(sys.argv[2])
        write(K2 / "results" / f"c1_{sys.argv[2]}.json", out, replace=True)
        out = {k: v for k, v in out.items() if k not in ("jobs",)}
    elif cmd == "a1":
        out = a1_evaluate()
        write(K2 / "results" / "a1.json", out, replace=True)
    elif cmd == "m1":
        out = m1_evaluate(sys.argv[2], sys.argv[3])
        write(K2 / "results" / f"m1_{sys.argv[3]}.json", out, replace=True)
    elif cmd == "decisions":
        out = decisions()
    elif cmd == "lock":
        out = lock(sys.argv[2])
    elif cmd == "gates":
        out = gates(sys.argv[2])
        write(K2 / "results" / f"gates_{sys.argv[2]}.json", out, replace=True)
        out = {k: v for k, v in out.items() if k not in ("ledger",)}
    print(json.dumps(out, indent=1, default=str)[:6000])
