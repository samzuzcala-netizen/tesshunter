"""K1 Part C1 (evaluator side): the known-planet set on realised data, then the 220-planet cap.

For every pool planet whose host downloaded: the observed-transit count (RULES 1.3) and expected SNR
(1.4) under both arms from the catalogue transit model on the host's usable products; eligibility is
>= 3 observed transits in the all-sector arm.  Hosts are taken in acquisition (hash) order, whole,
until 220 eligible planets.  Writes ``k1/truth/known_planets_final.csv`` (sealed) and the blind host
list ``k1/manifests/kp_hosts_final.csv`` (stellar columns and role only).
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from k1_common import ROOT, STORE, TRUTH, environment, write, sha, utc

environment(offline=True)
import inject_k1 as I  # noqa: E402
from tesshunter import survey  # noqa: E402
from tesshunter.limb_darkening import quadratic_ld  # noqa: E402

CAP = 220


def model_for(r) -> dict:
    R = float(r.tic_rad)
    M = float(r.tic_mass) if np.isfinite(r.tic_mass) else R
    P = float(r.pl_orbper)
    rp_rs = float(r.pl_ratror) if "pl_ratror" in r and np.isfinite(r.pl_ratror) else float(r.pl_rade) / (R * 109.076)
    a_rs = float(r.pl_ratdor) if "pl_ratdor" in r and np.isfinite(r.pl_ratdor) else survey.a_over_rs(P, M, R)
    b = float(r.pl_imppar) if "pl_imppar" in r and np.isfinite(r.pl_imppar) and r.pl_imppar < 1 + rp_rs else 0.0
    ld = quadratic_ld(r.tic_Teff, r.tic_logg)
    return dict(period=P, t0=float(r.t0_btjd), rp_rs=rp_rs, b=b, a_rs=a_rs, u=(ld.u1, ld.u2))


def main():
    pool = pd.read_csv(TRUTH / "known_planets_truth.csv", dtype={"tic_GAIA": str})
    rows = []
    for tic, g in pool.groupby("tic_id"):
        if not (STORE / f"tic{int(tic)}" / "index.json").exists():
            for _, r in g.iterrows():
                rows.append(dict(r, data_status="no_download"))
            continue
        try:
            prods = I.load_products(int(tic))
            prep = I.prepared(prods) if prods else None
        except Exception as exc:  # noqa: BLE001
            prep = None
        for _, r in g.iterrows():
            rec = dict(r)
            if prep is None or len(prep["time"]) == 0:
                rec["data_status"] = "no_usable_products"
                rows.append(rec)
                continue
            m = model_for(r)
            t14 = float(r.t14_hours) / 24.0
            rec.update(data_status="ok", model_rp_rs=m["rp_rs"], model_a_rs=m["a_rs"], model_b=m["b"],
                       n_obs_transits_k1=I.observed_transits(prep, False, m["period"], m["t0"], t14),
                       n_obs_transits_s56=I.observed_transits(prep, True, m["period"], m["t0"], t14),
                       snr_exp_k1=I.expected_snr(prep, False, **m), snr_exp_s56=I.expected_snr(prep, True, **m),
                       n_products=len(prods))
            rows.append(rec)
    df = pd.DataFrame(rows)
    df["eligible"] = (df.data_status == "ok") & (df.n_obs_transits_k1.fillna(0) >= 3)
    chosen, n = [], 0
    for tic in df.sort_values("acq_rank").drop_duplicates("tic_id").tic_id:
        e = df[(df.tic_id == tic) & df.eligible]
        if e.empty:
            continue
        if n + len(e) > CAP and n > 0:
            break
        chosen.append(tic)
        n += len(e)
    df["in_final_set"] = df.tic_id.isin(chosen) & df.eligible
    df.to_csv(TRUTH / "known_planets_final.csv", index=False)
    final = df[df.in_final_set]
    hosts = final.drop_duplicates("tic_id")[["tic_id", "role", "acq_rank", "k1_class", "tic_Tmag", "tic_Teff", "tic_rad",
                                            "tic_mass", "tic_logg", "tic_ra", "tic_dec", "tic_GAIA"]]
    hosts.to_csv(ROOT / "manifests" / "kp_hosts_final.csv", index=False)
    summary = {"utc": utc(), "pool_planets": int(len(df)), "pool_hosts": int(df.tic_id.nunique()),
               "data_status": df.data_status.value_counts().to_dict(), "eligible_planets": int(df.eligible.sum()),
               "final_planets": int(len(final)), "final_hosts": int(final.tic_id.nunique()),
               "by_role_planets": final.role.value_counts().to_dict(),
               "by_role_hosts": final.drop_duplicates("tic_id").role.value_counts().to_dict(),
               "strong_cohort_snr20_ge3": {r: int(((final.role == r) & (final.snr_exp_k1 >= 20)).sum()) for r in ("DEV", "HELDOUT")},
               "truth_sha256": sha(TRUTH / "known_planets_final.csv"), "hosts_sha256": sha(ROOT / "manifests" / "kp_hosts_final.csv")}
    write(ROOT / "manifests" / "kp_final_selection.json", summary, replace=True)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
