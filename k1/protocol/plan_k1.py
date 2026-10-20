"""K1 phase planner: job lists (``D:/tesshunter_k1/jobs/<phase>_jobs.json``) and per-job runtimes
(``D:/tesshunter_k1/runtimes/<phase>/``) for the controller.  Evaluator-side: reads the host manifests,
never writes truth into a runtime.

  download <phase> <hosts.csv> <use>             one download job per host (online, 900 s)
  search <phase> <set> <preset> <budget_s> [--hosts csv] [--injections csv]
  collect <phase>                                accepted candidates + pre-gate -> candidates.csv
  funnel <phase> <stage> <search_phase> <label> [--s-mode m] [--ramp] [--from-label L] [--only ids]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from k1_common import REPO, ROOT, DATA, STORE, RUNS, RUNTIMES, JOBS, RECEIPTS, read, write, utc

PREGATE = {"stitch_snr_min": 7.1, "stitch_n_transits_min": 3}
SHORT = {"survey_k1": "k1", "survey_k1_s56": "s56"}


def star_block(r) -> dict:
    g = lambda *ks: next((r[k] for k in ks if k in r and pd.notna(r[k])), None)  # noqa: E731
    rad = float(g("rad", "tic_rad", "radius_rsun"))
    mass = g("mass", "tic_mass", "mass_msun")
    mass = float(mass) if mass is not None and np.isfinite(float(mass)) else rad
    logg = g("logg", "tic_logg")
    return {"radius_rsun": rad, "mass_msun": mass, "teff_k": float(g("Teff", "tic_Teff", "teff_k")),
            "tmag": float(g("Tmag", "tic_Tmag", "tmag")), "ra_deg": float(g("ra", "tic_ra", "ra_deg")),
            "dec_deg": float(g("dec", "tic_dec", "dec_deg")),
            "logg": float(logg) if logg is not None and np.isfinite(float(logg)) else None}


def plan_download(phase, hosts_csv, use, attempt=1):
    hosts = pd.read_csv(hosts_csv)
    rec_dir = DATA / "download_receipts" / phase
    jobs = []
    for t in hosts.tic_id.astype("int64"):
        rp = rec_dir / f"tic{t}.json"
        jobs.append({"job_id": f"dl_{t}", "arguments": ["download_k1.py", str(t), str(attempt), use, "--receipt", str(rp)],
                     "result_path": str(rp), "deadline_s": 900, "online": True})
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "jobs": len(jobs)}


def plan_search(phase, set_name, preset, budget, hosts_csv=None, injections_csv=None):
    if preset not in SHORT:
        raise ValueError("unregistered preset")
    run = RUNS / phase
    rt_dir = RUNTIMES / phase
    jobs = []
    if injections_csv:
        inj = pd.read_csv(injections_csv)            # blind columns only: inj_id, tic_id + stellar
        rows = [(r, f"{r['inj_id']}_{SHORT[preset]}", Path(DATA / "injected" / r["inj_id"]),
                 DATA / "stitched" / "inj" / r["inj_id"]) for _, r in inj.iterrows()]
    else:
        hosts = pd.read_csv(hosts_csv)
        rows = [(r, f"{set_name}_{SHORT[preset]}_{int(r['tic_id'])}", STORE, DATA / "stitched" / "clean")
                for _, r in hosts.iterrows()]
    for r, job_id, lc_root, cache in rows:
        rt = {"job_id": job_id, "tic_id": int(r["tic_id"]), "preset": preset, "star": star_block(r),
              "lc_root": str(lc_root), "cache_dir": str(cache), "run_dir": str(run),
              "overrides": {"time_budget_s": float(budget)}, "use": set_name}
        path = rt_dir / f"{job_id}.json"
        write(path, rt, replace=True)
        jobs.append({"job_id": job_id, "arguments": ["search_worker_k1.py", str(path)],
                     "result_path": str(run / "receipts" / f"{job_id}.json"),
                     "deadline_s": float(budget) * 1.6 + 900, "online": False})
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "jobs": len(jobs), "budget_s": budget, "preset": preset}


def plan_inject(phase, hosts_csv, n=4):
    hosts = pd.read_csv(hosts_csv)
    jobs = []
    for t in hosts.tic_id.astype("int64"):
        rp = DATA / "inject_receipts" / phase / f"tic{t}.json"
        jobs.append({"job_id": f"inj_{t}", "arguments": ["inject_host_k1.py", str(t), "--n", str(n), "--receipt", str(rp)],
                     "result_path": str(rp), "deadline_s": 1800, "online": False, "pins": ["inject_k1.py"]})
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "jobs": len(jobs)}


def gather_blind(out=None):
    rows = []
    for p in sorted((DATA / "injections" / "blind").glob("tic*.json")):
        rows.extend(read(p))
    df = pd.DataFrame(rows)
    out = Path(out) if out else DATA / "injections" / "injections_blind.csv"
    df.to_csv(out, index=False)
    return {"n": len(df), "path": str(out)}


def plan_pilot(phase="pilot_search", n_hosts=40,
               specs=(("survey_k1", 8100), ("survey_k1", 5400), ("survey_k1", 2700),
                      ("survey_k1_s56", 8100), ("survey_k1_s56", 2700))):
    """C4 timing pilot: 40 injection hosts (seeded order 20261013), injection 0 of each, every
    (preset, budget) pair; one combined job list, longest budgets first."""
    import hashlib
    blind = pd.read_csv(DATA / "injections" / "injections_blind.csv")
    blind = blind[blind.inj_id.str.endswith("_0")].copy()
    blind["o"] = blind.tic_id.map(lambda t: hashlib.sha256(f"20261013:k1:pilot:{int(t)}".encode()).hexdigest())
    pick = blind.sort_values("o").head(n_hosts).drop(columns="o")
    pick.to_csv(DATA / "hosts" / "timing_pilot_injections.csv", index=False)
    jobs = []
    for preset, budget in specs:
        sub = f"{phase}_{SHORT[preset]}_b{int(budget)}"
        plan_search(sub, "pilot", preset, budget, injections_csv=str(DATA / "hosts" / "timing_pilot_injections.csv"))
        jobs += read(JOBS / f"{sub}_jobs.json")
    for j in jobs:
        j["job_id"] = j["job_id"] + "_b" + str(int(read(j["arguments"][1])["overrides"]["time_budget_s"]))
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "jobs": len(jobs), "hosts": len(pick)}


CAND_COLS = ["period_days", "epoch_btjd", "duration_days", "depth_ppt", "snr", "stitch_snr", "stitch_n_transits",
             "stitch_epoch_consistent", "stitch_period_days", "stitch_depth_ppt", "search", "planet_num"]


def collect(phase):
    run = RUNS / phase
    rows, status = [], {}
    for p in sorted((run / "results").glob("*.json")):
        d = read(p)
        status[d.get("status")] = status.get(d.get("status"), 0) + 1
        if d.get("status") != "ok" or not d.get("result"):
            continue
        st = d.get("star") or {}
        for q in d["result"].get("planets") or []:
            row = {"candidate_id": f"{d['job_id']}_p{int(q['planet_num']):02d}", "job_id": d["job_id"],
                   "tic_id": int(d["tic_id"]), **{k: q.get(k) for k in CAND_COLS},
                   "n_transits": q.get("n_transits_observed"), "n_units": d.get("n_units"),
                   "tmag": st.get("tmag"), "teff_k": st.get("teff_k"), "radius_rsun": st.get("radius_rsun"),
                   "mass_msun": st.get("mass_msun"), "ra_deg": st.get("ra_deg"), "dec_deg": st.get("dec_deg")}
            row["passes_pregate"] = bool((q.get("stitch_snr") or 0) >= PREGATE["stitch_snr_min"]
                                         and int(q.get("stitch_n_transits") or 0) >= PREGATE["stitch_n_transits_min"]
                                         and bool(q.get("stitch_epoch_consistent")))
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(run / "candidates.csv", index=False)
    out = {"phase": phase, "utc": utc(), "statuses": status, "n_accepted": len(df),
           "n_pregate": int(df.passes_pregate.sum()) if len(df) else 0}
    write(run / "collect.json", out, replace=True)
    return out


def _decisions(label, stage):
    out = {}
    for p in (RECEIPTS / label / stage).glob("*.json"):
        r = read(p)
        out[r["candidate_id"]] = r
    return out


def plan_funnel(phase, stage, search_phase, label, s_mode="bound", ramp=False, from_label=None, only=None,
                neighbours_dir=None, tls_threads=4, deadline=None, b_mode=None):
    """``b_mode``: B eligibility under that S mode only (the frozen configuration); None = any mode (calibration)."""
    run = RUNS / search_phase
    cands = pd.read_csv(run / "candidates.csv")
    lc_of = {}
    for p in (RUNTIMES / search_phase).glob("*.json"):
        rt = read(p)
        lc_of[rt["job_id"]] = rt
    src = from_label or label
    if stage == "A":
        elig = cands[cands.passes_pregate]
    elif stage == "S":
        a = _decisions(src, "A")
        elig = cands[cands.candidate_id.map(lambda c: (a.get(c) or {}).get("decision") == "PASS")]
    elif stage == "B":
        a, s = _decisions(src, "A"), _decisions(src, "S")
        def s_ok(c):
            gbm = (s.get(c) or {}).get("gate_by_mode") or {}
            return gbm.get(b_mode) in ("PASS", "HOLD") if b_mode else any(v in ("PASS", "HOLD") for v in gbm.values())
        elig = cands[cands.candidate_id.map(lambda c: (a.get(c) or {}).get("decision") == "PASS" and s_ok(c))]
    elif stage == "C":
        b = _decisions(src, "B")
        elig = cands[cands.candidate_id.map(lambda c: (b.get(c) or {}).get("decision") == "PASS")]
    else:
        raise ValueError("unregistered stage")
    if only is not None:
        elig = elig[elig.candidate_id.isin(set(only))]
    rt_dir = RUNTIMES / phase
    jobs = []
    for _, r in elig.iterrows():
        srt = lc_of[r["job_id"]]
        cid = r["candidate_id"]
        allc = cands[cands.job_id == r["job_id"]]
        row = {k: (None if (isinstance(v, float) and not np.isfinite(v)) else v) for k, v in r.items()
               if k not in ("job_id", "candidate_id", "passes_pregate")}
        rt = {"candidate_id": cid, "tic_id": int(r["tic_id"]), "candidate": row,
              "all_candidates": [{k: v for k, v in x.items() if k not in ("job_id", "candidate_id", "passes_pregate")}
                                 for x in allc.to_dict(orient="records")],
              "star": srt["star"], "lc_root": srt["lc_root"],
              "root": str(DATA / "funnel" / label / (cid + ("_ramp" if ramp else ""))),
              "preset": srt["preset"], "s_mode": s_mode, "ramp_variant": bool(ramp), "label": label,
              "use": srt.get("use"), "tls_threads": int(tls_threads),
              "neighbours_path": (str(Path(neighbours_dir) / f"tic{int(r['tic_id'])}.json") if neighbours_dir else None)}
        if from_label and stage != "A":
            rt["root"] = str(DATA / "funnel" / from_label / cid)
        path = rt_dir / f"{cid}.json"
        write(path, rt, replace=True)
        dl = deadline or {"A": 1800, "S": 600, "B": 600, "C": 14400}[stage]
        jobs.append({"job_id": f"{stage}_{label}_{cid}", "arguments": ["funnel_k1.py", stage, str(path)],
                     "result_path": str(RECEIPTS / label / stage / f"{cid}.json"), "deadline_s": dl, "online": False,
                     "pins": ["funnel_k1.py"]})
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "stage": stage, "jobs": len(jobs)}


def plan_d(phase, search_phase, label, redact=False, n_draws=100000, only=None, deadline=5400):
    """Stage D for every Stage C PASS of ``label`` (runtimes reuse the funnel case roots)."""
    import catalog_adapter_k1 as CA
    cat = CA.load()
    c = _decisions(label, "C")
    cands = pd.read_csv(RUNS / search_phase / "candidates.csv")
    rt_dir = RUNTIMES / phase
    jobs = []
    for cid, rec in sorted(c.items()):
        if rec.get("decision") != "PASS" or (only and cid not in only):
            continue
        frt = read(RUNTIMES / f"{label}_C" / f"{cid}.json") if (RUNTIMES / f"{label}_C" / f"{cid}.json").exists()             else next(read(p) for p in RUNTIMES.glob(f"*/{cid}.json"))
        r = cands[cands.candidate_id == cid].iloc[0]
        tic, period = int(r.tic_id), float(r.period_days)
        st = frt["star"]
        xm = CA.crossmatch_record(cat, tic, st["ra_deg"], st["dec_deg"])
        rt = {"candidate_id": cid, "key": f"tic{tic}_P{period:.4f}", "tic_id": tic, "period": period,
              "depth_ppt": float(r.depth_ppt), "root": frt["root"], "lc_root": frt["lc_root"], "preset": frt["preset"],
              "s_mode": frt.get("s_mode") or "bound", "crossmatch_star": xm, "tce_sidecar": xm.get("tce_sidecar"),
              "star": st, "neighbours_path": str(DATA / "neighbours" / "neighbours" / f"tic{tic}.json"),
              "n_draws": int(n_draws), "label": label, "use": frt.get("use"), "redact_catalogue": bool(redact),
              "job": {"rank": 0, "tic_id": tic, "period": period, "depth_ppt": float(r.depth_ppt)},
              "candidate": frt["candidate"], "all_candidates": frt["all_candidates"], "ramp_variant": False}
        path = rt_dir / f"{cid}.json"
        write(path, rt, replace=True)
        jobs.append({"job_id": f"D_{cid}", "arguments": ["stage_d_worker_k1.py", str(path)],
                     "result_path": str(RECEIPTS / label / "D" / f"{cid}.json"), "deadline_s": deadline, "online": True,
                     "pins": ["stage_d_worker_k1.py", "stage_d_packets_k1.py", "stage_d_pixels_k1.py", "rules_k1.py",
                              "funnel_k1.py"]})
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return {"phase": phase, "jobs": len(jobs)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download"); d.add_argument("phase"); d.add_argument("hosts"); d.add_argument("use")
    d.add_argument("--attempt", type=int, default=1)
    s = sub.add_parser("search"); s.add_argument("phase"); s.add_argument("set"); s.add_argument("preset")
    s.add_argument("budget", type=float); s.add_argument("--hosts"); s.add_argument("--injections")
    c = sub.add_parser("collect"); c.add_argument("phase")
    i = sub.add_parser("inject"); i.add_argument("phase"); i.add_argument("hosts"); i.add_argument("--n", type=int, default=4)
    g = sub.add_parser("gather_blind"); g.add_argument("--out")
    pp = sub.add_parser("pilot"); pp.add_argument("--n", type=int, default=40)
    dd = sub.add_parser("D"); dd.add_argument("phase"); dd.add_argument("search_phase"); dd.add_argument("label")
    dd.add_argument("--redact", action="store_true"); dd.add_argument("--n-draws", type=int, default=100000)
    f = sub.add_parser("funnel"); f.add_argument("phase"); f.add_argument("stage"); f.add_argument("search_phase")
    f.add_argument("label"); f.add_argument("--s-mode", default="bound"); f.add_argument("--ramp", action="store_true")
    f.add_argument("--from-label"); f.add_argument("--neighbours-dir"); f.add_argument("--tls-threads", type=int, default=4)
    a = ap.parse_args()
    if a.cmd == "download":
        r = plan_download(a.phase, a.hosts, a.use, a.attempt)
    elif a.cmd == "search":
        r = plan_search(a.phase, a.set, a.preset, a.budget, a.hosts, a.injections)
    elif a.cmd == "collect":
        r = collect(a.phase)
    elif a.cmd == "inject":
        r = plan_inject(a.phase, a.hosts, a.n)
    elif a.cmd == "gather_blind":
        r = gather_blind(a.out)
    elif a.cmd == "pilot":
        r = plan_pilot(n_hosts=a.n)
    elif a.cmd == "D":
        r = plan_d(a.phase, a.search_phase, a.label, a.redact, a.n_draws)
    else:
        r = plan_funnel(a.phase, a.stage, a.search_phase, a.label, a.s_mode, a.ramp, a.from_label,
                        neighbours_dir=a.neighbours_dir, tls_threads=a.tls_threads)
    print(json.dumps(r, indent=1))
