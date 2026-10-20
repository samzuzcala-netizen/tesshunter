"""K1 Part D, after Stage S: the DEV end-to-end stages (D3) and the capped injection Stage C sample (D1).

  dev <B|C|D>        D3 on the dev_k1 search: B on any-mode S passers (neighbour records), C on B passers,
                     D on C passers with the catalogue redacted (DEV objects are catalogued by construction)
  inj_c_sample       D1: 150 S-passers of the E1-adopted arm under the leading S mode or ``bound``, stratified
                     by expected SNR, seed 20261014 (written to k1/manifests/inj_c_sample.json), then B on
                     them; ``inj_c`` plans C on the sample's B passers.

Sample definition [A, fixed here before any Part D funnel output existed]:
* arm: the one rule E1 adopts (E1 reads only search, pre-gate and S, so it is applied mechanically first);
* leading S mode: highest injection retention through S at expected SNR 7-40 before the adversarial
  constraint of E2 (ties to the simpler mode, E2 order); the sample is drawn from items whose best matched
  candidate passes S under that mode or under ``bound``;
* strata: expected SNR (that arm's ``snr_exp``) in [0,7), [7,10), [10,15), [15,20), [20,40), [40,inf);
  30 per stratum from the five strata >= 7 (none from < 7), shortfalls reallocated to the nearest stratum
  with spare items (ties to the lower one); within a stratum, items in sha256("20261014:k1:injC:" + inj_id)
  order; one candidate per item (the matched candidate with the highest stitch SNR).
Evaluator side: reads the sealed injection truth, so it refuses to run without a verified prediction lock.
"""
from __future__ import annotations

import argparse
import hashlib
import json

import numpy as np
import pandas as pd

from k1_common import ROOT, DATA, JOBS, read, write, utc
import plan_k1 as PK

NB_DIR = str(DATA / "neighbours" / "neighbours")
STRATA = [(7, 10), (10, 15), (15, 20), (20, 40), (40, float("inf"))]
PER_STRATUM = 30


def dev(stage: str) -> dict:
    if stage == "D":
        return PK.plan_d("dev_k1_D", "dev_k1", "dev_k1", redact=True)
    return PK.plan_funnel(f"dev_k1_{stage}", stage, "dev_k1", "dev_k1",
                          neighbours_dir=NB_DIR if stage == "B" else None)


def _order(inj_id: str) -> str:
    return hashlib.sha256(f"20261014:k1:injC:{inj_id}".encode()).hexdigest()


def inj_c_sample(arm: str, leading: str, lock_name: str = "partD_S") -> dict:
    import evaluate_k1 as EV
    import match_k1 as M
    EV.verify_lock(lock_name)                       # raises if the lock is missing or any file changed
    phase = f"inj_{'k1' if arm == 'survey_k1' else 's56'}"
    s56 = arm != "survey_k1"
    cands = EV.candidates(phase)
    a, s = EV.receipts(phase, "A"), EV.receipts(phase, "S")
    rows = []
    for p in sorted((ROOT / "truth" / "injections").glob("*.json")):
        t = read(p)
        job = f"{t['inj_id']}_{'s56' if s56 else 'k1'}"
        times = EV.host_times(int(t["tic_id"]), s56)
        best = None
        for _, r in cands[cands.job_id == job].iterrows():
            if not bool(r.passes_pregate) or (a.get(r.candidate_id) or {}).get("decision") != "PASS":
                continue
            gbm = (s.get(r.candidate_id) or {}).get("gate_by_mode") or {}
            if not any(gbm.get(m) in ("PASS", "HOLD") for m in {leading, "bound"}):
                continue
            truth = {"tic_id": t["tic_id"], "period": t["period"], "t0": t["t0"], "t14": t["t14_days"],
                     "sigma_t0": 0.0, "sigma_p": 0.0}          # as analyze_partD_k1.injections_ledger
            mm = M.match(times, {"period": M.candidate_period(r), "epoch": r.epoch_btjd, "duration": r.duration_days}, truth)
            if mm.get("matched") and (best is None or float(r.stitch_snr) > best[1]):
                best = (r.candidate_id, float(r.stitch_snr))
        if best:
            rows.append({"inj_id": t["inj_id"], "candidate_id": best[0],
                         "snr_exp": float(t["snr_exp_s56" if s56 else "snr_exp_k1"] or 0.0)})
    df = pd.DataFrame(rows)
    df["o"] = df.inj_id.map(_order)
    avail = {s: df[(df.snr_exp >= s[0]) & (df.snr_exp < s[1])].sort_values("o") for s in STRATA}
    take = {s: min(PER_STRATUM, len(avail[s])) for s in STRATA}
    short = PER_STRATUM * len(STRATA) - sum(take.values())
    while short > 0:
        spare = [i for i, s in enumerate(STRATA) if len(avail[s]) > take[s]]
        if not spare:
            break
        for i, s in enumerate(STRATA):
            if take[s] < PER_STRATUM:
                j = min(spare, key=lambda k: (abs(k - i), k))
                take[STRATA[j]] += 1
                short -= 1
                spare = [k for k, x in enumerate(STRATA) if len(avail[x]) > take[x]]
                if short == 0 or not spare:
                    break
    picked = pd.concat([avail[s].head(take[s]) for s in STRATA])
    man = {"utc": utc(), "arm": arm, "phase": phase, "leading_mode": leading, "lock": lock_name,
           "strata": {f"{a}-{b}": {"available": int(len(avail[(a, b)])), "taken": int(take[(a, b)])} for a, b in STRATA},
           "n": int(len(picked)), "candidate_ids": picked.candidate_id.tolist(), "inj_ids": picked.inj_id.tolist()}
    write(ROOT / "manifests" / "inj_c_sample.json", man, replace=True)
    r = PK.plan_funnel(f"{phase}_Bsample", "B", phase, phase, only=man["candidate_ids"], neighbours_dir=NB_DIR)
    return {"sample": {k: v for k, v in man.items() if k not in ("candidate_ids", "inj_ids")}, "B": r}


def inj_c() -> dict:
    man = read(ROOT / "manifests" / "inj_c_sample.json")
    # 16 h per job from the start: blind TLS on 30-40-sector hosts takes 6-9 h (DEV C, 2026-10-11)
    return PK.plan_funnel(f"{man['phase']}_Csample", "C", man["phase"], man["phase"], only=man["candidate_ids"],
                          deadline=57600)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dev"); d.add_argument("stage", choices=["B", "C", "D"])
    s = sub.add_parser("inj_c_sample"); s.add_argument("arm"); s.add_argument("leading")
    sub.add_parser("inj_c")
    a = ap.parse_args()
    out = dev(a.stage) if a.cmd == "dev" else inj_c_sample(a.arm, a.leading) if a.cmd == "inj_c_sample" else inj_c()
    print(json.dumps(out, indent=1, default=str))
