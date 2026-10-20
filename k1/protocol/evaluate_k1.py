"""K1 evaluator (truth side): prediction lock, matching, the per-item stage ledger, intervals.

Order is enforced: ``lock(name, phases, labels)`` hashes every saved prediction (search results and
funnel receipts) into ``k1/manifests/prediction_lock_<name>.json`` BEFORE any truth file is opened;
``ledger_*`` refuse to run without a lock whose hashes still verify.  Workers never import this module.

Stage flags per item (any matched path counts; RULES 1.5): search, pregate, A (legacy), A_ramp,
S_<mode> for every mode, B, C (decision PASS and the blind period re-matching the truth), D verdict.
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from k1_common import ROOT, DATA, STORE, RUNS, RECEIPTS, TRUTH, environment, read, write, sha, utc

environment(offline=True)
import match_k1 as M  # noqa: E402

S_MODES = ("bound", "empirical_bound", "recurrent_bound", "recurrent_bound_corr", "bound_alias")


# ── prediction lock ───────────────────────────────────────────────────────────
def _prediction_files(phases, labels):
    files = []
    for ph in phases:
        files += sorted(glob.glob(str(RUNS / ph / "results" / "*.json")))
        files += sorted(glob.glob(str(RUNS / ph / "receipts" / "*.json")))
    for lb in labels:
        files += sorted(glob.glob(str(RECEIPTS / lb / "*" / "*.json")))
    return files


def lock(name, phases, labels) -> dict:
    files = _prediction_files(phases, labels)
    hashes = {f: sha(f) for f in files}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    rec = {"name": name, "utc": utc(), "phases": list(phases), "labels": list(labels), "n_files": len(files),
           "bundle_sha256": digest, "hashes": hashes}
    write(ROOT / "manifests" / f"prediction_lock_{name}.json", rec)
    return {k: v for k, v in rec.items() if k != "hashes"}


def verify_lock(name) -> dict:
    rec = read(ROOT / "manifests" / f"prediction_lock_{name}.json")
    changed = [f for f, h in rec["hashes"].items() if not Path(f).exists() or sha(f) != h]
    if changed:
        raise RuntimeError(f"prediction lock {name}: {len(changed)} files changed since the lock")
    return rec


# ── inputs ────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=4096)
def host_times(tic: int, s56: bool) -> np.ndarray:
    import inject_k1 as I
    prep = I.prepared(I.load_products(int(tic)))
    t = prep["time"]
    return t[prep["sector"] >= 56] if s56 else t


def candidates(phase) -> pd.DataFrame:
    p = RUNS / phase / "candidates.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


@lru_cache(maxsize=256)
def receipts(label, stage) -> dict:
    out = {}
    for p in glob.glob(str(RECEIPTS / label / stage / "*.json")):
        r = read(p)
        out[r["candidate_id"]] = r
    return out


def search_receipts(phase) -> dict:
    return {read(p)["job_id"]: read(p) for p in glob.glob(str(RUNS / phase / "receipts" / "*.json"))}


# ── the ledger for one truth item ─────────────────────────────────────────────
def ledger_item(truth: dict, job_id: str, phase: str, label: str, s56: bool, ramp_label: str | None = None) -> dict:
    cands = candidates(phase)
    rows = cands[cands.job_id == job_id] if len(cands) else cands
    times = host_times(int(truth["tic_id"]), s56)
    out = {"search": False, "pregate": False, "A": False, "A_ramp": False, "B": False, "C": False, "D": None,
           "matched_paths": [], **{f"S_{m}": False for m in S_MODES}}
    a, s, b, c, d = (receipts(label, st) for st in ("A", "S", "B", "C", "D"))
    ar = receipts(ramp_label, "A") if ramp_label else {}
    best_d = None
    for _, r in rows.iterrows():
        mm = M.match(times, {"period": M.candidate_period(r), "epoch": r.epoch_btjd, "duration": r.duration_days}, truth)
        if not mm.get("matched"):
            continue
        cid = r.candidate_id
        out["matched_paths"].append({"candidate_id": cid, "ratio": mm["ratio"], "coverage": mm["coverage"]})
        out["search"] = True
        if not bool(r.passes_pregate):
            continue
        out["pregate"] = True
        if (ar.get(cid) or {}).get("decision") == "PASS":
            out["A_ramp"] = True
        if (a.get(cid) or {}).get("decision") != "PASS":
            continue
        out["A"] = True
        gbm = (s.get(cid) or {}).get("gate_by_mode") or {}
        for m in S_MODES:
            if gbm.get(m) in ("PASS", "HOLD"):
                out[f"S_{m}"] = True
        if (b.get(cid) or {}).get("decision") != "PASS":
            continue
        out["B"] = True
        cr = c.get(cid) or {}
        if cr.get("decision") == "PASS":
            bp = ((cr.get("measurement") or {}).get("blind") or {}).get("period")
            if bp and M.period_matches(float(bp), float(truth["period"]))["matched"]:
                out["C"] = True
                v = ((d.get(cid) or {}).get("verdicts") or {}).get("k1.0", {}).get("verdict")
                if v:
                    rank = {"SUBMIT": 0, "HOLD": 1, "KILL": 2}.get(v, 3)
                    if best_d is None or rank < best_d[0]:
                        best_d = (rank, v)
    out["D"] = best_d[1] if best_d else None
    return out


# ── intervals ─────────────────────────────────────────────────────────────────
def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(c - h, 4), round(c + h, 4))


def host_bootstrap(df: pd.DataFrame, stat, n=10000, seed=20261011):
    """Percentile 95% interval of ``stat(frame)`` under host resampling (column ``tic_id``)."""
    rng = np.random.default_rng(seed)
    groups = {t: g for t, g in df.groupby("tic_id")}
    keys = list(groups)
    vals = []
    for _ in range(n):
        pick = rng.integers(0, len(keys), len(keys))
        vals.append(stat(pd.concat([groups[keys[i]] for i in pick], ignore_index=True)))
    vals = np.asarray([v for v in vals if v is not None and np.isfinite(v)])
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if len(vals) else (None, None)


def host_bootstrap_prop(df: pd.DataFrame, flag: str, n=10000, seed=20261011, weight: str | None = None):
    """Fast percentile 95% interval of a (weighted) proportion under host resampling: per-host sums of the
    flag and of the item weights, hosts drawn with replacement, ratio of resampled sums."""
    if len(df) == 0:
        return (None, None)
    w = df[weight].astype(float) if weight else pd.Series(1.0, index=df.index)
    g = pd.DataFrame({"tic_id": df.tic_id.values, "k": df[flag].astype(float).values * w.values, "n": w.values}).groupby("tic_id").sum()
    k, m = g.k.to_numpy(), g.n.to_numpy()
    rng = np.random.default_rng(seed)
    H = len(g)
    out = np.empty(n)
    for i in range(0, n, 500):
        b = min(500, n - i)
        idx = rng.integers(0, H, (b, H))
        cnt = np.zeros((b, H))
        np.add.at(cnt, (np.repeat(np.arange(b), H), idx.ravel()), 1.0)
        out[i:i + b] = (cnt @ k) / np.maximum(cnt @ m, 1e-12)
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)))

