"""K1 Part D planner: the paired injection, false-alarm and DEV runs (RULES_K1 section 3 pools).

  searches <budget>   D1 inj_k1 / inj_s56 (1,000 injections), D2 fa_k1 / fa_s56 (250 FA hosts),
                      D3 dev_k1 (DEV known-planet hosts + DEV adversarial hosts, survey_k1 only)
                      -> one combined job list "partD_search" (largest jobs first)
  funnel_AS           after collect: A (legacy) and A_ramp on every pre-gate passer of every search phase,
                      then S (all modes) on legacy-A passers
  dev_BCD             D3: B on any-mode S passers, then C, then D (catalogue redacted)
  inj_C_sample        D1: the capped Stage C sample (150 S-passers stratified by expected SNR, seed 20261014)
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from k1_common import ROOT, DATA, JOBS, RUNTIMES, read, write, utc
import plan_k1 as PK

SEARCH_PHASES = {"inj_k1": ("survey_k1", "inj"), "inj_s56": ("survey_k1_s56", "inj"),
                 "fa_k1": ("survey_k1", "fa"), "fa_s56": ("survey_k1_s56", "fa"), "dev_k1": ("survey_k1", "dev")}


def dev_hosts_csv() -> str:
    kp = pd.read_csv(ROOT / "manifests" / "kp_hosts_final.csv", dtype={"tic_GAIA": str})
    kpd = kp[kp.role == "DEV"]
    st_kp = pd.read_csv(DATA / "hosts" / "stellar_kp.csv", dtype={"GAIA": str})
    st_adv = pd.read_csv(DATA / "hosts" / "stellar_adv.csv", dtype={"GAIA": str})
    dev = pd.concat([st_kp[st_kp.tic_id.isin(kpd.tic_id)], st_adv[st_adv.role == "adv_DEV"]], ignore_index=True)
    out = DATA / "hosts" / "dev_hosts.csv"
    dev.to_csv(out, index=False)
    return str(out)


def searches(budget: float) -> dict:
    jobs = []
    blind = str(DATA / "injections" / "injections_blind.csv")
    PK.plan_search("inj_k1", "inj", "survey_k1", budget, injections_csv=blind)
    PK.plan_search("inj_s56", "inj", "survey_k1_s56", budget, injections_csv=blind)
    fa = str(DATA / "hosts" / "stellar_false_alarm.csv")
    PK.plan_search("fa_k1", "fa", "survey_k1", budget, hosts_csv=fa)
    PK.plan_search("fa_s56", "fa", "survey_k1_s56", budget, hosts_csv=fa)
    PK.plan_search("dev_k1", "dev", "survey_k1", budget, hosts_csv=dev_hosts_csv())
    for ph in SEARCH_PHASES:
        rows = read(JOBS / f"{ph}_jobs.json")
        jobs += rows
    # largest first: all-sector jobs before s56, so the long jobs start early
    jobs.sort(key=lambda j: (0 if "_k1" in j["job_id"] or j["job_id"].startswith(("dev_k1", "fa_k1")) else 1))
    write(JOBS / "partD_search_jobs.json", jobs, replace=True)
    return {"jobs": len(jobs), "by_phase": {ph: len(read(JOBS / f"{ph}_jobs.json")) for ph in SEARCH_PHASES}}


def funnel_as(stage: str) -> dict:
    """A (legacy and ramp) or S for every search phase -> one combined job list."""
    jobs = []
    for ph in SEARCH_PHASES:
        if stage == "A":
            PK.plan_funnel(f"{ph}_A", "A", ph, ph)
            PK.plan_funnel(f"{ph}_Aramp", "A", ph, f"{ph}_ramp", ramp=True)
            jobs += read(JOBS / f"{ph}_A_jobs.json") + read(JOBS / f"{ph}_Aramp_jobs.json")
        else:
            PK.plan_funnel(f"{ph}_S", "S", ph, ph)
            jobs += read(JOBS / f"{ph}_S_jobs.json")
    write(JOBS / f"partD_{stage}_jobs.json", jobs, replace=True)
    return {"stage": stage, "jobs": len(jobs)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["searches", "A", "S"])
    ap.add_argument("--budget", type=float, default=2700.0)
    a = ap.parse_args()
    r = searches(a.budget) if a.what == "searches" else funnel_as(a.what)
    print(json.dumps(r, indent=1))
