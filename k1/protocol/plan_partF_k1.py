"""K1 Part F planner: the HELD-OUT validation runs and the paired P12 comparison (RULES_K1 G1-G3).

  searches <preset> <budget>   HELD-OUT known-planet + HELD-OUT adversarial hosts under the frozen preset
                               ("ho_k1" or "ho_s56"), plus the paired P12 search ("p12_paired", frozen
                               ``survey_p10`` from the isolated aee65172b copy) on the HELD-OUT known-planet hosts
  p12_funnel <stage>           A / S / B / C of the paired P12 arm (p12_paired_worker_k1.py, label "p12_paired")

The K1 arm's funnel and Stage D use plan_k1 ``funnel`` / ``D`` with the frozen S mode and the ramp choice.
Runtimes carry no truth: hosts only (tic_id + stellar block).
"""
from __future__ import annotations

import argparse
import json

import pandas as pd

from k1_common import ROOT, DATA, STORE, RUNS, RUNTIMES, JOBS, RECEIPTS, read, write
import plan_k1 as PK

NB_DIR = DATA / "neighbours" / "neighbours"


def heldout_csvs() -> tuple[str, str]:
    kp = pd.read_csv(ROOT / "manifests" / "kp_hosts_final.csv", dtype={"tic_GAIA": str})
    kph = kp[kp.role == "HELDOUT"]
    st_kp = pd.read_csv(DATA / "hosts" / "stellar_kp.csv", dtype={"GAIA": str})
    st_adv = pd.read_csv(DATA / "hosts" / "stellar_adv.csv", dtype={"GAIA": str})
    kp_ho = st_kp[st_kp.tic_id.isin(kph.tic_id)]
    allh = pd.concat([kp_ho, st_adv[st_adv.role == "adv_HELDOUT"]], ignore_index=True)
    # AMENDMENT_K1_20261011_4: a host in both HELD-OUT sets (TIC 232612416) is searched once and serves both ledgers
    dup = sorted(int(t) for t in allh.tic_id[allh.tic_id.duplicated()])
    allh = allh.drop_duplicates("tic_id", keep="first")
    write(ROOT / "manifests" / "heldout_hosts_overlap.json", {"both_sets": dup}, replace=True)
    a, k = DATA / "hosts" / "heldout_hosts.csv", DATA / "hosts" / "heldout_kp_hosts.csv"
    allh.to_csv(a, index=False)
    kp_ho.to_csv(k, index=False)
    return str(a), str(k)


def searches(preset: str, budget: float) -> dict:
    allh, kph = heldout_csvs()
    ph = f"ho_{PK.SHORT[preset]}"
    PK.plan_search(ph, "ho", preset, budget, hosts_csv=allh)
    jobs = list(read(JOBS / f"{ph}_jobs.json"))
    run, rt_dir = RUNS / "p12_paired", RUNTIMES / "p12_paired"
    for _, r in pd.read_csv(kph).iterrows():
        job_id = f"p12_{int(r['tic_id'])}"
        rt = {"job_id": job_id, "tic_id": int(r["tic_id"]), "preset": "survey_p10 (frozen aee65172b)",
              "star": PK.star_block(r), "lc_root": str(STORE), "cache_dir": str(DATA / "stitched" / "p12_frozen"),
              "run_dir": str(run), "use": "p12_paired"}
        path = rt_dir / f"{job_id}.json"
        write(path, rt, replace=True)
        jobs.append({"job_id": job_id, "arguments": ["p12_paired_worker_k1.py", "search", str(path)],
                     "result_path": str(run / "receipts" / f"{job_id}.json"), "deadline_s": 2700 * 1.6 + 900,
                     "online": False, "pins": ["p12_paired_worker_k1.py"]})
    jobs.sort(key=lambda j: 0 if j["job_id"].startswith("ho_") else 1)
    write(JOBS / "partF_search_jobs.json", jobs, replace=True)
    return {"jobs": len(jobs), "ho": len(read(JOBS / f"{ph}_jobs.json")), "p12": len(jobs) - len(read(JOBS / f"{ph}_jobs.json"))}


def p12_funnel(stage: str, tls_threads: int = 4) -> dict:
    """The paired arm's funnel: plan_k1's eligibility (pre-gate -> A PASS -> S PASS/HOLD -> B PASS) on the
    p12_paired candidates, with the frozen-copy worker in place of funnel_k1.py."""
    phase = f"p12_paired_{stage}"
    r = PK.plan_funnel(phase, stage, "p12_paired", "p12_paired", neighbours_dir=str(NB_DIR), tls_threads=tls_threads)
    jobs = read(JOBS / f"{phase}_jobs.json")
    for j in jobs:
        j["arguments"] = ["p12_paired_worker_k1.py", stage, j["arguments"][2]]
        j["pins"] = ["p12_paired_worker_k1.py"]
    write(JOBS / f"{phase}_jobs.json", jobs, replace=True)
    return r


def funnel(stage: str, s_mode: str = "bound_alias") -> dict:
    """One combined job list ``partF_<stage>``: the HELD-OUT arm under the frozen configuration (S mode
    ``s_mode``; B on that mode's PASS/HOLD only; C with a 16 h deadline; D catalogue-redacted, as for DEV) and,
    for A/S/B/C, the paired P12 arm (frozen-copy worker)."""
    jobs = []
    if stage == "D":
        r = PK.plan_d("ho_k1_D", "ho_k1", "ho_k1", redact=True)
        jobs += read(JOBS / "ho_k1_D_jobs.json")
    else:
        r = PK.plan_funnel(f"ho_k1_{stage}", stage, "ho_k1", "ho_k1", s_mode=s_mode,
                           neighbours_dir=str(NB_DIR) if stage == "B" else None,
                           deadline=57600 if stage == "C" else None, b_mode=s_mode if stage == "B" else None)
        jobs += read(JOBS / f"ho_k1_{stage}_jobs.json")
        r2 = p12_funnel(stage)
        p12 = read(JOBS / f"p12_paired_{stage}_jobs.json")
        if stage == "C":
            for j in p12:
                j["deadline_s"] = 57600
        jobs += p12
        r = {"ho": r, "p12": r2}
    write(JOBS / f"partF_{stage}_jobs.json", jobs, replace=True)
    return {"stage": stage, "jobs": len(jobs), "detail": r}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("searches"); s.add_argument("preset"); s.add_argument("budget", type=float)
    f = sub.add_parser("p12_funnel"); f.add_argument("stage", choices=["A", "S", "B", "C"])
    g = sub.add_parser("funnel"); g.add_argument("stage", choices=["A", "S", "B", "C", "D"])
    a = ap.parse_args()
    out = (searches(a.preset, a.budget) if a.cmd == "searches" else p12_funnel(a.stage) if a.cmd == "p12_funnel"
           else funnel(a.stage))
    print(json.dumps(out, indent=1))
