"""K2 phase planner (evaluator side): job lists ``D:/tesshunter_k2/jobs/<phase>_jobs.json`` and runtimes
``D:/tesshunter_k2/runtimes/<phase>/`` for ``controller_k2.py``.  Runtimes never carry truth.

  rc <variant> <timing|rest|all>   R-C Stage C under a C1 variant (RULES_K2 2), label ``rc_<variant>``
  ra                                Stage A re-runs for A1 on R-A (RULES_K2 3.2), label ``ra_a1``
  ra_next <S|B>                     S / B on the new A passers of ``ra_a1``
  m1 <variant>                      M1 re-runs of R-C jobs with siblings (RULES_K2 4.2), label ``m1_<variant>``
  d <label> <phase>                 Stage D on the new C passes of a K2 label (catalogue redacted)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from k2_common import (K1, K2, K1_DATA, K2_DATA, K1_RUNS, K1_RECEIPTS, K2_RECEIPTS, K1_RUNTIMES, K2_RUNTIMES,
                       K2_FUNNEL, K1_NEIGHBOURS, JOBS, read, write, utc)
import c_input_k2 as CI

RC_SOURCES = (("dev_k1", "dev_k1_C"), ("inj_k1", "inj_k1_Csample"))
N_CLASSES = ((0, 8), (8, 13), (13, 20), (20, 30), (30, 10**6))
C_DEADLINE = 57600
C_PINS = ["funnel_k2.py", "c_input_k2.py", "funnel_k1.py"]
FROZEN_S_MODE = "bound_alias"


def _order(prefix: str, cid: str) -> str:
    return hashlib.sha256(f"{prefix}{cid}".encode()).hexdigest()


def n_class(n: int) -> str:
    for a, b in N_CLASSES:
        if a <= n < b:
            return f"{a}-{b}" if b < 10**6 else f">={a}"
    raise ValueError(n)


def receipts(base: Path, label: str, stage: str) -> dict:
    out = {}
    for p in (base / label / stage).glob("*.json"):
        r = read(p)
        out[r["candidate_id"]] = r
    return out


def case_n_usable(case_root: str) -> int:
    preps = [p for p in Path(case_root, "prep").glob("*.json") if "_res" not in p.name]
    return len(read(preps[0])["products"])


def rc_table() -> pd.DataFrame:
    """The 119 R-C jobs: K1 receipt, runtime, case root, n_usable (RULES_K2 1.1-1.2)."""
    rows = []
    for label, rt_phase in RC_SOURCES:
        for cid, rec in sorted(receipts(K1_RECEIPTS, label, "C").items()):
            if rec.get("status") != "COMPLETE":
                continue
            rt_path = K1_RUNTIMES / rt_phase / f"{cid}.json"
            rows.append({"candidate_id": cid, "k1_label": label, "tic_id": int(rec["tic_id"]), "k1_runtime": str(rt_path),
                         "case_root": rec["case_root"], "n_usable": case_n_usable(rec["case_root"]),
                         "k1_decision": rec.get("decision"), "k1_wall_s": rec["wall_seconds"]})
    df = pd.DataFrame(rows)
    df["n_class"] = df.n_usable.map(n_class)
    if len(df) != 119:
        raise RuntimeError(f"R-C has {len(df)} jobs, registered 119")
    return df


def timing_ids(df: pd.DataFrame) -> list[str]:
    out = []
    for a, b in N_CLASSES:
        sub = df[(df.n_usable >= a) & (df.n_usable < b)].copy()
        sub["o"] = sub.candidate_id.map(lambda c: _order("20261015:k2:timing:", c))
        out += sub.sort_values("o").candidate_id.head(2).tolist()
    return out


def c_job(phase: str, label: str, base_rt: dict, cid: str, variant: str, copy_from: str | None,
          siblings: list | None = None, root: str | None = None) -> dict:
    rt = {k: v for k, v in base_rt.items() if not k.startswith("k2_")}
    rt.update(root=root or str(K2_FUNNEL / label / cid), label=label, k2_c_variant=variant, k2_siblings=siblings or [],
              k2_a1_scope=base_rt.get("k2_a1_scope"), k2_copy_from=copy_from, tls_threads=4)
    path = K2_RUNTIMES / phase / f"{cid}.json"
    write(path, rt, replace=True)
    return {"job_id": f"C_{label}_{cid}", "arguments": ["funnel_k2.py", "C", str(path)],
            "result_path": str(K2_RECEIPTS / label / "C" / f"{cid}.json"), "deadline_s": C_DEADLINE, "online": False,
            "pins": C_PINS}


def plan_rc(variant: str, which: str, tag: str = "a") -> dict:
    if variant not in CI.VARIANTS or variant == "K1":
        raise ValueError("unregistered variant")
    df = rc_table()
    tids = timing_ids(df)
    if which == "timing":
        sel = df[df.candidate_id.isin(tids)]
    elif which == "rest":
        sel = df[~df.candidate_id.isin(tids)]
    else:
        sel = df
    label = f"rc_{variant.lower()}{tag}"          # tag "a": AMENDMENT_K2_20261014_1 bin errors
    phase = f"{label}_{which}"
    jobs = [c_job(phase, label, read(r.k1_runtime), r.candidate_id, variant, r.case_root)
            for r in sel.sort_values("n_usable", ascending=False).itertuples()]   # longest first
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    write(K2 / "manifests" / "rc_table.json", {"utc": utc(), "timing_ids": tids,
                                               "rows": df.to_dict(orient="records")}, replace=True)
    return {"phase": phase, "jobs": len(jobs), "by_class": sel.n_class.value_counts().to_dict()}


# ── A1 (RULES_K2 3.2) ─────────────────────────────────────────────────────────
RA_SOURCES = (("inj_k1", "inj_k1_A"), ("fa_k1", "fa_k1_A"), ("dev_k1", "dev_k1_A"))
A_PINS = ["funnel_k2.py", "c_input_k2.py", "funnel_k1.py"]


def depth_failed_somewhere(m: dict) -> bool:
    return any(not ((pe.get("criteria") or {}).get("depths_consistent_p_ge_1e-3", True))
               for pe in (m.get("per_ephemeris") or {}).values())


def ra_injection_jobs() -> set:
    """Search jobs of the Part D survey_k1 injections with expected SNR >= 20 (evaluator side, partD lock)."""
    import evaluate_k1 as EV
    EV.verify_lock("partD")
    out = set()
    for p in sorted((K1 / "truth" / "injections").glob("inj_*.json")):
        t = read(p)
        if float(t.get("snr_exp_k1") or 0.0) >= 20.0:
            out.add(f"{t['inj_id']}_k1")
    return out


def ra_table() -> pd.DataFrame:
    inj_jobs = ra_injection_jobs()
    rows = []
    for label, rt_phase in RA_SOURCES:
        cands = pd.read_csv(K1_RUNS / label / "candidates.csv")
        cands = cands[cands.passes_pregate]
        if label == "inj_k1":
            cands = cands[cands.job_id.isin(inj_jobs)]
        a = receipts(K1_RECEIPTS, label, "A")
        for r in cands.itertuples():
            rec = a.get(r.candidate_id) or {}
            m = rec.get("measurement") or {}
            rows.append({"candidate_id": r.candidate_id, "job_id": r.job_id, "k1_label": label, "tic_id": int(r.tic_id),
                         "k1_runtime": str(K1_RUNTIMES / rt_phase / f"{r.candidate_id}.json"),
                         "k1_status": rec.get("status"), "k1_decision": rec.get("decision"),
                         "depth_failed": bool(m) and depth_failed_somewhere(m)})
    return pd.DataFrame(rows)


def a_job(phase, label, base_rt, cid, scope="author", root=None, stage="A", deadline=1800):
    rt = {k: v for k, v in base_rt.items() if not k.startswith("k2_")}
    rt.update(root=root or str(K2_FUNNEL / label / cid), label=label, k2_a1_scope=scope, k2_c_variant="K1",
              k2_siblings=[], k2_copy_from=None, s_mode=FROZEN_S_MODE)
    path = K2_RUNTIMES / phase / f"{cid}.json"
    write(path, rt, replace=True)
    return {"job_id": f"{stage}_{label}_{cid}", "arguments": ["funnel_k2.py", stage, str(path)],
            "result_path": str(K2_RECEIPTS / label / stage / f"{cid}.json"), "deadline_s": deadline, "online": False,
            "pins": A_PINS}


def plan_ra() -> dict:
    df = ra_table()
    rerun = df[(df.k1_status == "COMPLETE") & (df.k1_decision == "FAIL") & df.depth_failed]
    passes = df[(df.k1_status == "COMPLETE") & (df.k1_decision == "PASS")].copy()
    passes["o"] = passes.candidate_id.map(lambda c: _order("20261015:k2:det:", c))
    det = passes.sort_values("o").head(20)
    sel = pd.concat([rerun.assign(purpose="rescue"), det.drop(columns="o").assign(purpose="determinism")])
    jobs = [a_job("ra_a1_A", "ra_a1", read(r.k1_runtime), r.candidate_id) for r in sel.itertuples()]
    write(JOBS / "ra_a1_A_jobs.json", jobs, replace=True)
    man = {"utc": utc(), "n_pregate": int(len(df)), "by_label": df.k1_label.value_counts().to_dict(),
           "k1_fail": int((df.k1_decision == "FAIL").sum()), "k1_pass": int((df.k1_decision == "PASS").sum()),
           "k1_not_complete": int((df.k1_status != "COMPLETE").sum()), "rescue_jobs": int(len(rerun)),
           "rescue_by_label": rerun.k1_label.value_counts().to_dict(), "determinism_ids": det.candidate_id.tolist(),
           "rows": sel[["candidate_id", "k1_label", "tic_id", "purpose"]].to_dict(orient="records")}
    write(K2 / "manifests" / "ra_a1_selection.json", man, replace=True)
    df.to_csv(K2_DATA / "ra_table.csv", index=False)
    return {k: v for k, v in man.items() if k != "rows" and k != "determinism_ids"}


def a1_decision(m: dict, scope: str | None) -> str | None:
    """Stage A decision of a recorded measurement under scope None (K1), "author" or "author_exposure": every
    examined ephemeris' criteria with the depth criterion re-derived, the K1 chosen-ephemeris rule re-applied."""
    per = m.get("per_ephemeris") or {}
    if not per:
        return None
    best = None
    for src, pe in per.items():
        crit = dict(pe["criteria"])
        dk = pe.get("det_kept") or {}
        pc = dk.get("p_const")
        ok = bool(pc is not None and pc >= 1e-3)
        if scope:
            blk = (dk.get("a1") or {}).get(scope) or {}
            pw = blk.get("p_within")
            ok = ok or bool(pw is not None and pw >= 1e-3 and blk.get("means_agree"))
        crit["depths_consistent_p_ge_1e-3"] = ok
        key = (sum(bool(v) for v in crit.values()), pe.get("kept_snr") if pe.get("kept_snr") is not None else -1e9)
        if best is None or key > best[0]:
            best = (key, all(bool(v) for v in crit.values()))
    return "PASS" if best[1] else "FAIL"


def plan_ra_next(stage: str, scopes=("author", "author_exposure")) -> dict:
    """S on every ra_a1 candidate that passes A under any registered scope; B on their bound_alias S passers
    with a neighbour record (injection and DEV searches; FA hosts stop at S as in K1)."""
    a = receipts(K2_RECEIPTS, "ra_a1", "A")
    sel = read(K2 / "manifests" / "ra_a1_selection.json")
    purpose = {r["candidate_id"]: r for r in sel["rows"]}
    jobs = []
    for cid, rec in sorted(a.items()):
        if rec.get("status") != "COMPLETE" or purpose[cid]["purpose"] != "rescue":
            continue
        if not any(a1_decision(rec["measurement"], sc) == "PASS" for sc in scopes):
            continue
        base = read(K2_RUNTIMES / "ra_a1_A" / f"{cid}.json")
        if stage == "S":
            jobs.append(a_job("ra_a1_S", "ra_a1", base, cid, stage="S", root=base["root"], deadline=600))
        else:
            s = (receipts(K2_RECEIPTS, "ra_a1", "S").get(cid) or {}).get("gate_by_mode") or {}
            nb = K1_NEIGHBOURS / f"tic{int(rec['tic_id'])}.json"
            if s.get(FROZEN_S_MODE) not in ("PASS", "HOLD") or purpose[cid]["k1_label"] == "fa_k1" or not nb.exists():
                continue
            base = dict(base, neighbours_path=str(nb))
            jobs.append(a_job("ra_a1_B", "ra_a1", base, cid, stage="B", root=base["root"], deadline=600))
    write(JOBS / f"ra_a1_{stage}_jobs.json", jobs, replace=True)
    return {"phase": f"ra_a1_{stage}", "jobs": len(jobs)}


# ── M1 (RULES_K2 4) ──────────────────────────────────────────────────────────
def siblings_for(cid: str, cands: pd.DataFrame, s_rec: dict, a_rec: dict) -> list[dict]:
    """The M1 siblings of candidate ``cid`` (RULES_K2 4.1).  ``s_rec`` / ``a_rec``: candidate_id -> S / A receipt
    under the configuration in force."""
    import match_k1 as M
    row = cands[cands.candidate_id == cid].iloc[0]
    px, snr_x = M.candidate_period(row), float(row.stitch_snr)
    out = []
    for _, y in cands[(cands.job_id == row.job_id) & (cands.candidate_id != cid)].iterrows():
        if not (float(y.stitch_snr) > snr_x):
            continue
        gate = ((s_rec.get(y.candidate_id) or {}).get("gate_by_mode") or {}).get(FROZEN_S_MODE)
        if gate not in ("PASS", "HOLD"):
            continue
        py = M.candidate_period(y)
        if M.period_matches(py, px)["matched"]:
            continue
        fo = ((a_rec.get(y.candidate_id) or {}).get("measurement") or {}).get("forced_tls") or {}
        usable = all(fo.get(k) is not None for k in ("period", "T0_btjd", "duration_days"))
        period, t0 = (float(fo["period"]), float(fo["T0_btjd"])) if usable else (py, float(y.epoch_btjd))
        t14 = max(float(fo["duration_days"]) if usable else 0.0, float(y.duration_days))
        out.append({"candidate_id": y.candidate_id, "period": period, "t0": t0, "t14": t14,
                    "stitch_snr": float(y.stitch_snr), "ephemeris": "stageA_forced_tls" if usable else "stitch"})
    return out


def plan_m1(variant: str, extra_s_label: str | None = None) -> dict:
    rc = rc_table()
    label = f"m1_{variant.lower()}"
    jobs, man = [], []
    for k1_label in ("dev_k1", "inj_k1"):
        cands = pd.read_csv(K1_RUNS / k1_label / "candidates.csv")
        s_rec = receipts(K1_RECEIPTS, k1_label, "S")
        a_rec = receipts(K1_RECEIPTS, k1_label, "A")
        if extra_s_label:
            s_rec.update({c: r for c, r in receipts(K2_RECEIPTS, extra_s_label, "S").items() if c in set(cands.candidate_id)})
            a_rec.update({c: r for c, r in receipts(K2_RECEIPTS, extra_s_label, "A").items() if c in set(cands.candidate_id)})
        for r in rc[rc.k1_label == k1_label].itertuples():
            sib = siblings_for(r.candidate_id, cands, s_rec, a_rec)
            if not sib:
                continue
            jobs.append(c_job(f"{label}_C", label, read(r.k1_runtime), r.candidate_id, variant, r.case_root, siblings=sib))
            man.append({"candidate_id": r.candidate_id, "n_usable": r.n_usable, "siblings": sib})
    write(JOBS / f"{label}_C_jobs.json", jobs, replace=True)
    write(K2 / "manifests" / f"{label}_siblings.json", {"utc": utc(), "variant": variant, "extra_s_label": extra_s_label,
                                                       "jobs": man}, replace=True)
    return {"phase": f"{label}_C", "jobs": len(jobs)}


# ── Stage D on K2 C passes ────────────────────────────────────────────────────
D_PINS = ["stage_d_worker_k1.py", "stage_d_packets_k1.py", "stage_d_pixels_k1.py", "rules_k1.py", "funnel_k1.py"]


def plan_d(label: str, phase: str, only: set | None = None, redact: bool = True, catalogue: str = "20261008",
           n_draws: int = 100000, deadline: int = 5400) -> dict:
    import catalog_adapter_k1 as CA
    cat = CA.load(catalogue)
    jobs = []
    for cid, rec in sorted(receipts(K2_RECEIPTS, label, "C").items()):
        if rec.get("decision") != "PASS" or rec.get("status") != "COMPLETE" or (only is not None and cid not in only):
            continue
        crt = next(read(p) for p in K2_RUNTIMES.glob(f"*/{cid}.json") if read(p).get("label") == label)
        cand = crt["candidate"]
        tic, period = int(crt["tic_id"]), float(cand["period_days"])
        st = crt["star"]
        xm = CA.crossmatch_record(cat, tic, st["ra_deg"], st["dec_deg"])
        nb = crt.get("neighbours_path") or str(K1_NEIGHBOURS / f"tic{tic}.json")
        rt = {"candidate_id": cid, "key": f"tic{tic}_P{period:.4f}", "tic_id": tic, "period": period,
              "depth_ppt": float(cand["depth_ppt"]), "root": crt["root"], "lc_root": crt["lc_root"],
              # the C runtime's own S mode: the rules stamp (p10.0 vs p10.0-partial under bound_alias) must match the
              # case root's records (K1 plan_d did the same)
              "preset": crt["preset"], "s_mode": crt.get("s_mode") or FROZEN_S_MODE, "crossmatch_star": xm,
              "tce_sidecar": xm.get("tce_sidecar"),
              "star": st, "neighbours_path": nb, "n_draws": int(n_draws), "label": label, "use": crt.get("use"),
              "redact_catalogue": bool(redact), "job": {"rank": 0, "tic_id": tic, "period": period,
                                                        "depth_ppt": float(cand["depth_ppt"])},
              "candidate": cand, "all_candidates": crt["all_candidates"], "ramp_variant": False}
        path = K2_RUNTIMES / phase / f"{cid}.json"
        write(path, rt, replace=True)
        jobs.append({"job_id": f"D_{label}_{cid}", "arguments": ["stage_d_worker_k1.py", str(path)],
                     "result_path": str(K2_RECEIPTS / label / "D" / f"{cid}.json"), "deadline_s": deadline,
                     "online": True, "pins": D_PINS})
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "jobs": len(jobs)}


# ── generic K2 funnel planner (seen and fresh sets, Part 4) ───────────────────
def funnel_runtime(cands: pd.DataFrame, search_rt: dict, cid: str, label: str, root: str, *, scope=None,
                   variant="K1", siblings=None, copy_from=None, neighbours_path=None, use=None) -> dict:
    r = cands[cands.candidate_id == cid].iloc[0]
    allc = cands[cands.job_id == r.job_id]
    clean = lambda x: {k: (None if (isinstance(v, float) and not np.isfinite(v)) else v) for k, v in x.items()  # noqa: E731
                       if k not in ("job_id", "candidate_id", "passes_pregate")}
    return {"candidate_id": cid, "tic_id": int(r.tic_id), "candidate": clean(r.to_dict()),
            "all_candidates": [clean(x) for x in allc.to_dict(orient="records")], "star": search_rt["star"],
            "lc_root": search_rt["lc_root"], "root": root, "preset": search_rt["preset"], "s_mode": FROZEN_S_MODE,
            "ramp_variant": False, "label": label, "use": use or search_rt.get("use"), "tls_threads": 4,
            "neighbours_path": neighbours_path, "k2_c_variant": variant, "k2_siblings": siblings or [],
            "k2_a1_scope": scope, "k2_copy_from": copy_from}


def write_funnel_jobs(phase: str, stage: str, label: str, rts: list[dict], deadline: float) -> dict:
    jobs = []
    for rt in rts:
        path = K2_RUNTIMES / phase / f"{rt['candidate_id']}.json"
        write(path, rt, replace=True)
        jobs.append({"job_id": f"{stage}_{label}_{rt['candidate_id']}", "arguments": ["funnel_k2.py", stage, str(path)],
                     "result_path": str(K2_RECEIPTS / label / stage / f"{rt['candidate_id']}.json"),
                     "deadline_s": deadline, "online": False, "pins": C_PINS})
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "jobs": len(jobs)}


# ── Part 4, seen set (RULES_K2 6) ─────────────────────────────────────────────
def frozen() -> dict:
    return read(K2 / "protocol" / "config.json")


def plan_seen(stage: str) -> dict:
    """The changed stages on K1's HELD-OUT (ho_k1) outputs under the frozen K2 configuration."""
    cfg = frozen()
    scope, variant, m1 = cfg["a1_scope"], cfg["c_variant"], cfg["m1"]
    cands = pd.read_csv(K1_RUNS / "ho_k1" / "candidates.csv")
    srt = {read(p)["job_id"]: read(p) for p in (K1_RUNTIMES / "ho_k1").glob("*.json")}
    k1 = {st: receipts(K1_RECEIPTS, "ho_k1", st) for st in ("A", "S", "B")}
    k2 = {st: receipts(K2_RECEIPTS, "seen_a1", st) for st in ("A", "S", "B")}
    rts = []
    if stage == "A":
        if scope is None:
            return write_funnel_jobs("seen_a1_A", "A", "seen_a1", [], 1800)
        for r in cands[cands.passes_pregate].itertuples():
            rec = k1["A"].get(r.candidate_id) or {}
            if rec.get("status") == "COMPLETE" and rec.get("decision") == "FAIL" and depth_failed_somewhere(rec["measurement"]):
                rts.append(funnel_runtime(cands, srt[r.job_id], r.candidate_id, "seen_a1",
                                          str(K2_FUNNEL / "seen_a1" / r.candidate_id), scope=scope))
        return write_funnel_jobs("seen_a1_A", "A", "seen_a1", rts, 1800)
    if stage in ("S", "B"):
        for cid, rec in sorted(k2["A"].items()):
            if rec.get("status") != "COMPLETE" or rec.get("decision") != "PASS":
                continue
            r = cands[cands.candidate_id == cid].iloc[0]
            nb = None
            if stage == "B":
                gate = (k2["S"].get(cid) or {}).get("gate_by_mode", {}).get(FROZEN_S_MODE)
                nb = K1_NEIGHBOURS / f"tic{int(r.tic_id)}.json"
                if gate not in ("PASS", "HOLD") or not nb.exists():
                    continue
            rts.append(funnel_runtime(cands, srt[r.job_id], cid, "seen_a1", str(K2_FUNNEL / "seen_a1" / cid), scope=scope,
                                      neighbours_path=str(nb) if nb else None))
        return write_funnel_jobs(f"seen_a1_{stage}", stage, "seen_a1", rts, 600)
    if stage == "C":
        s_all = dict(k1["S"], **k2["S"])
        a_all = dict(k1["A"], **k2["A"])
        for cid in sorted(set(k1["B"]) | set(k2["B"])):
            rec = k2["B"].get(cid) or k1["B"].get(cid)
            if rec.get("status") != "COMPLETE" or rec.get("decision") != "PASS":
                continue
            r = cands[cands.candidate_id == cid].iloc[0]
            sib = siblings_for(cid, cands, s_all, a_all) if m1 else []
            rescued = cid in k2["B"]
            rts.append(funnel_runtime(cands, srt[r.job_id], cid, "seen_c", str(K2_FUNNEL / "seen_c" / cid), scope=scope,
                                      variant=variant, siblings=sib,
                                      copy_from=(k2["A"][cid]["case_root"] if rescued else k1["B"][cid]["case_root"])))
        return write_funnel_jobs("seen_c_C", "C", "seen_c", rts, C_DEADLINE)
    raise ValueError(stage)


def plan_fresh_funnel(stage: str, arm: str, cfg: dict | None = None) -> dict:
    """Fresh set funnel.  arm ``k1``: the frozen K2 configuration (label fr_k1); arm ``p12``: the frozen P12 copy
    (p12_paired_worker_k1.py, label fr_p12, S gate ``bound``)."""
    run = K2_DATA / "runs" / ("fr_k1" if arm == "k1" else "fr_p12")
    label = "fr_k1" if arm == "k1" else "fr_p12"
    cands = pd.read_csv(run / "candidates.csv")
    srt = {read(p)["job_id"]: read(p) for p in (K2_RUNTIMES / f"fr_{arm}").glob("*.json")}
    rec = {st: receipts(K2_RECEIPTS, label, st) for st in ("A", "S", "B")}
    ok = lambda st, c: (rec[st].get(c) or {}).get("status") == "COMPLETE" and (rec[st].get(c) or {}).get("decision") == "PASS"  # noqa: E731
    # Stage A of the K1 arm needs only the A1 decision (``cfg`` given before the freeze); later stages read the freeze
    cfg = cfg or (frozen() if arm == "k1" else {"a1_scope": None, "c_variant": "K1", "m1": False})
    gate_mode = FROZEN_S_MODE if arm == "k1" else "bound"
    rts = []
    for r in cands.itertuples():
        cid = r.candidate_id
        if stage == "A" and not r.passes_pregate:
            continue
        if stage == "S" and not ok("A", cid):
            continue
        if stage == "B" and not (ok("A", cid) and ((rec["S"].get(cid) or {}).get("gate_by_mode") or {}).get(gate_mode) in ("PASS", "HOLD")):
            continue
        if stage == "C" and not ok("B", cid):
            continue
        nb = str(K2_DATA / "neighbours" / "neighbours" / f"tic{int(r.tic_id)}.json")
        sib = siblings_for(cid, cands, rec["S"], rec["A"]) if (stage == "C" and cfg["m1"]) else []
        rt = funnel_runtime(cands, srt[r.job_id], cid, label, str(K2_FUNNEL / label / cid), scope=cfg["a1_scope"],
                            variant=cfg["c_variant"], siblings=sib, neighbours_path=nb if stage in ("B",) else nb)
        if arm == "p12":
            rt = {k: v for k, v in rt.items() if not k.startswith("k2_")}
            rt["s_mode"] = "bound"
        rts.append(rt)
    phase = f"{label}_{stage}"
    deadline = {"A": 1800, "S": 600, "B": 600, "C": C_DEADLINE}[stage]
    out = write_funnel_jobs(phase, stage, label, rts, deadline)
    if arm == "p12":
        jobs = read(JOBS / f"{phase}_jobs.json")
        for j in jobs:
            j["arguments"] = ["p12_paired_worker_k1.py", stage, j["arguments"][2]]
            j["pins"] = ["p12_paired_worker_k1.py"]
        write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return out


# ── fresh set: download, neighbours, search (RULES_K2 5) ──────────────────────
def plan_fresh_download(phase: str = "fr_dl", attempt: int = 1) -> dict:
    hosts = pd.concat([pd.read_csv(K2 / "manifests" / "fresh_kp_hosts.csv", usecols=["tic_id"]).assign(use="fresh_kp"),
                       pd.read_csv(K2 / "manifests" / "fresh_adv_hosts.csv", usecols=["tic_id"]).assign(use="fresh_adv")])
    hosts = hosts.drop_duplicates("tic_id")
    jobs = []
    for r in hosts.itertuples():
        rp = K2_DATA / "download_receipts" / phase / f"tic{int(r.tic_id)}.json"
        jobs.append({"job_id": f"dl_{int(r.tic_id)}", "arguments": ["download_k2.py", str(int(r.tic_id)), str(attempt), r.use,
                                                                   "--receipt", str(rp)],
                     "result_path": str(rp), "deadline_s": 900, "online": True, "pins": ["download_k1.py"]})
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "jobs": len(jobs)}


def plan_fresh_neighbours() -> dict:
    """K1's neighbour records (neighbours_k1.py, K2 root): bulk SIMBAD + VSX (phase fr_nb_bulk), then the per-star
    Gaia cone (phase fr_nb)."""
    targets = str(K2_DATA / "hosts" / "neighbours_fresh.csv")
    rec = K2_DATA / "neighbour_receipts" / "fresh"
    bulk = [{"job_id": f"nb_fresh_{k}", "arguments": ["neighbours_k1.py", k, "--targets", targets, "--label", "fresh",
                                                      "--receipt", str(rec / f"{k}.json")],
             "result_path": str(rec / f"{k}.json"), "deadline_s": 1800, "online": True, "pins": ["neighbours_k1.py"]}
            for k in ("simbad", "vsx")]
    stars = [{"job_id": f"nb_{int(t)}", "arguments": ["neighbours_k1.py", str(int(t)), "--targets", targets, "--label",
                                                      "fresh", "--receipt", str(rec / f"tic{int(t)}.json")],
              "result_path": str(rec / f"tic{int(t)}.json"), "deadline_s": 900, "online": True, "pins": ["neighbours_k1.py"]}
             for t in pd.read_csv(targets).tic_id]
    write(JOBS / "fr_nb_bulk_jobs.json", bulk, replace=True)
    write(JOBS / "fr_nb_jobs.json", stars, replace=True)
    return {"bulk": len(bulk), "stars": len(stars)}


def plan_fresh_search(budget: float = 8100.0) -> dict:
    """K1 arm (frozen survey_k1, 8,100 s) on every downloaded fresh host + the paired P12 arm on the known-planet
    hosts; one combined job list ``fr_search``.  Runtimes: tic_id + stellar block only."""
    from plan_k1 import star_block
    st = pd.read_csv(K2_DATA / "hosts" / "stellar_fresh.csv", dtype={"GAIA": str})
    have = {int(p.parent.name[3:]) for p in (K2_DATA / "audit_lc").glob("tic*/index.json")}
    kp_final = set(pd.read_csv(K2 / "manifests" / "fresh_kp_hosts_final.csv").tic_id.astype("int64"))
    adv = set(pd.read_csv(K2 / "manifests" / "fresh_adv_hosts.csv").tic_id.astype("int64"))
    jobs = []
    for _, r in st.iterrows():
        tic = int(r.tic_id)
        if tic not in have or tic not in (kp_final | adv):
            continue
        for arm in ("k1", "p12"):
            if arm == "p12" and tic not in kp_final:
                continue
            run = K2_DATA / "runs" / ("fr_k1" if arm == "k1" else "fr_p12")
            job_id = f"fr_k1_{tic}" if arm == "k1" else f"p12_{tic}"
            rt = {"job_id": job_id, "tic_id": tic, "star": star_block(r), "lc_root": str(K2_DATA / "audit_lc"),
                  "run_dir": str(run), "use": "fresh"}
            if arm == "k1":
                rt.update(preset="survey_k1", cache_dir=str(K2_DATA / "stitched" / "clean"),
                          overrides={"time_budget_s": float(budget)})
                args, dl, pins = ["search_worker_k1.py"], float(budget) * 1.6 + 900, []
            else:
                rt.update(preset="survey_p10 (frozen aee65172b)", cache_dir=str(K2_DATA / "stitched" / "p12_frozen"))
                args, dl, pins = ["p12_paired_worker_k1.py", "search"], 2700 * 1.6 + 900, ["p12_paired_worker_k1.py"]
            path = K2_RUNTIMES / f"fr_{arm}" / f"{job_id}.json"
            write(path, rt, replace=True)
            jobs.append({"job_id": job_id, "arguments": args + [str(path)], "result_path": str(run / "receipts" / f"{job_id}.json"),
                         "deadline_s": dl, "online": False, "pins": pins})
    jobs.sort(key=lambda j: 0 if j["job_id"].startswith("fr_k1") else 1)
    write(JOBS / "fr_search_jobs.json", jobs, replace=True)
    return {"phase": "fr_search", "jobs": len(jobs), "k1": sum(j["job_id"].startswith("fr_k1") for j in jobs)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rc"); r.add_argument("variant"); r.add_argument("which", choices=["timing", "rest", "all"]); r.add_argument("--tag", default="a")
    sub.add_parser("ra")
    n = sub.add_parser("ra_next"); n.add_argument("stage", choices=["S", "B"])
    m = sub.add_parser("m1"); m.add_argument("variant"); m.add_argument("--extra-s-label")
    d = sub.add_parser("d"); d.add_argument("label"); d.add_argument("phase")
    a = ap.parse_args()
    if a.cmd == "rc":
        out = plan_rc(a.variant, a.which, a.tag)
    elif a.cmd == "ra":
        out = plan_ra()
    elif a.cmd == "ra_next":
        out = plan_ra_next(a.stage)
    elif a.cmd == "m1":
        out = plan_m1(a.variant, a.extra_s_label)
    else:
        out = plan_d(a.label, a.phase)
    print(json.dumps(out, indent=1, default=str))
