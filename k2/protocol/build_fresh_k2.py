"""K2 fresh confirmatory set (RULES_K2 section 5), evaluator side.  Truth goes to ``k2/truth/`` (sealed); blind
host lists to ``k2/manifests/``.

  kp        K1's ``build_sets_k1.build_kp`` on a fresh NASA pull + the 2026-10-14 TOI snapshot, every eligible host
            kept (no 200-host pool), then K1's pool hosts, every K1 set, the survey list and the reserve removed;
            hash order "20261009:k1:kp" kept.
  adv       K1's ``build_sets_k1.build_adv`` on K1's 2026-10-08 catalogue snapshot with every eligible host kept,
            then K1's 88 adversarial hosts, every K1 set, the fresh known-planet hosts, the survey list and the
            reserve removed; the first 50 EB and 20 BLEND in hash order "20261012:k1:adv".
  stellar   worker-visible stellar tables ``D:/tesshunter_k2/hosts/stellar_fresh.csv`` and the neighbour-target form.
  finalize  on the downloaded K2 store: observed transits and expected SNR (``finalize_kp_k1`` logic), K1's
            220-planet cap (hosts whole, hash order).
The K1 builders are called with their module paths pointed at K2 folders, so no K1 file is written.
"""
from __future__ import annotations

import argparse
import json
import shutil

import numpy as np
import pandas as pd

from k2_common import K1, K2, K1_DATA, K2_DATA, K2_STORE, K2_TRUTH, read, write, sha, utc

WORK = K2 / "work" / "fresh_build"
N_EB, N_BLEND = 50, 20


def _exclusions() -> set:
    ex = set()
    for p in (K1 / "manifests" / "kp_hosts.csv", K1 / "manifests" / "injection_hosts.csv",
              K1 / "manifests" / "false_alarm_hosts.csv", K1 / "manifests" / "adv_hosts.csv",
              K1 / "survey" / "targets_k1.csv", K1 / "survey" / "reserve_k1.csv"):
        ex |= set(pd.read_csv(p, usecols=["tic_id"]).tic_id.astype("int64"))
    return ex


def _builder(snap: str, sub: str):
    import build_sets_k1 as BS
    root = WORK / sub
    (root / "manifests").mkdir(parents=True, exist_ok=True)
    (root / "survey").mkdir(parents=True, exist_ok=True)
    BS.SNAP = K1_DATA / "catalogs" / snap
    BS.ROOT = root
    BS.TRUTH = K2_TRUTH / f"build_{sub}"
    return BS, root


def build_kp() -> dict:
    BS, root = _builder("snap_20261014", "kp")
    summ = BS.build_kp(cap=220, pool_max=10 ** 6)
    allp = pd.read_csv(BS.TRUTH / "known_planets_truth.csv", dtype={"tic_GAIA": str})
    ex = _exclusions()
    keep = allp[~allp.tic_id.isin(ex)].copy()
    keep["role"] = "FRESH"
    order = keep.drop_duplicates("tic_id").sort_values("host_order").tic_id.tolist()
    keep["acq_rank"] = keep.tic_id.map({t: i + 1 for i, t in enumerate(order)})
    keep = keep.sort_values(["acq_rank", "pl_orbper"])
    K2_TRUTH.mkdir(parents=True, exist_ok=True)
    keep.to_csv(K2_TRUTH / "fresh_kp_truth.csv", index=False)
    hosts = keep.drop_duplicates("tic_id")[["tic_id", "role", "acq_rank", "k1_class", "tic_Tmag", "tic_Teff", "tic_rad",
                                            "tic_mass", "tic_logg", "tic_ra", "tic_dec", "tic_GAIA", "n_usable",
                                            "sectors_usable"]]
    hosts.to_csv(K2 / "manifests" / "fresh_kp_hosts.csv", index=False)
    out = {"utc": utc(), "k1_builder_summary": summ, "eligible_hosts_all": int(allp.tic_id.nunique()),
           "eligible_planets_all": int(len(allp)), "excluded_hosts": int(allp[allp.tic_id.isin(ex)].tic_id.nunique()),
           "fresh_hosts": int(len(hosts)), "fresh_planets": int(len(keep)),
           "n_usable_hosts": hosts.n_usable.describe().round(1).to_dict(),
           "truth_sha256": sha(K2_TRUTH / "fresh_kp_truth.csv"), "hosts_sha256": sha(K2 / "manifests" / "fresh_kp_hosts.csv")}
    shutil.rmtree(BS.TRUTH)                                  # the unfiltered builder output (K1 pool included)
    write(K2 / "manifests" / "fresh_kp_selection.json", out, replace=True)
    return out


def build_adv() -> dict:
    BS, root = _builder("snap_20261008", "adv")
    shutil.copyfile(K1 / "survey" / "targets_k1.csv", root / "survey" / "targets_k1.csv")
    for n in ("injection_hosts.csv", "false_alarm_hosts.csv"):
        shutil.copyfile(K1 / "manifests" / n, root / "manifests" / n)
    summ = BS.build_adv(n_eb=10 ** 6, n_blend=10 ** 6)
    allp = pd.read_csv(BS.TRUTH / "adversarial_truth.csv")
    ex = _exclusions() | set(pd.read_csv(K2 / "manifests" / "fresh_kp_hosts.csv").tic_id.astype("int64"))
    keep = allp[~allp.tic_id.isin(ex) & allp.kind.isin(["EB", "BLEND"])].sort_values("split_order")
    chosen = pd.concat([keep[keep.kind == "EB"].head(N_EB), keep[keep.kind == "BLEND"].head(N_BLEND)])
    chosen = chosen.sort_values("split_order").assign(role="FRESH")
    chosen.to_csv(K2_TRUTH / "fresh_adversarial_truth.csv", index=False)
    chosen[["tic_id", "role", "kind", "k1_class", "Tmag"]].to_csv(K2 / "manifests" / "fresh_adv_hosts.csv", index=False)
    out = {"utc": utc(), "k1_builder_summary": summ, "eligible": allp.kind.value_counts().to_dict(),
           "after_exclusion": keep.kind.value_counts().to_dict(), "chosen": chosen.kind.value_counts().to_dict(),
           "truth_sha256": sha(K2_TRUTH / "fresh_adversarial_truth.csv")}
    shutil.rmtree(BS.TRUTH)
    write(K2 / "manifests" / "fresh_adv_selection.json", out, replace=True)
    return out


def stellar() -> dict:
    """Worker-visible stellar table for every fresh host (no truth columns) and the neighbour-target form."""
    import build_sets_k1 as BS
    import hosts_stellar_k1 as HS
    out = K2_DATA / "hosts"
    out.mkdir(parents=True, exist_ok=True)
    kp = pd.read_csv(K2_TRUTH / "fresh_kp_truth.csv", dtype={"tic_GAIA": str}).drop_duplicates("tic_id")
    kps = pd.DataFrame({"tic_id": kp.tic_id, "ra": kp.tic_ra, "dec": kp.tic_dec, "Tmag": kp.tic_Tmag, "Teff": kp.tic_Teff,
                        "logg": kp.tic_logg, "rad": kp.tic_rad, "mass": kp.tic_mass, "k1_class": kp.k1_class,
                        "GAIA": kp.tic_GAIA, "role": "kp_FRESH"})
    adv = pd.read_csv(K2 / "manifests" / "fresh_adv_hosts.csv")
    tp = BS.tic_params(adv.tic_id)
    a = adv[["tic_id", "k1_class"]].merge(tp, on="tic_id", how="left").assign(role="adv_FRESH")
    allh = pd.concat([kps, a[HS.COLS]], ignore_index=True).drop_duplicates("tic_id")
    allh.to_csv(out / "stellar_fresh.csv", index=False)
    HS.nb_form(allh).to_csv(out / "neighbours_fresh.csv", index=False)
    return {"n": int(len(allh)), "kp": int(len(kps)), "adv": int(len(a)), "missing_coords": int(allh.ra.isna().sum())}


def finalize(cap: int = 220) -> dict:
    """finalize_kp_k1 on the K2 store (observed transits, expected SNR, the 220-planet cap)."""
    import finalize_kp_k1 as FK
    import inject_k1 as I
    pool = pd.read_csv(K2_TRUTH / "fresh_kp_truth.csv", dtype={"tic_GAIA": str})
    rows = []
    for tic, g in pool.groupby("tic_id"):
        prep = None
        if (K2_STORE / f"tic{int(tic)}" / "index.json").exists():
            try:
                prods = I.load_products(int(tic), root=K2_STORE)
                prep = I.prepared(prods) if prods else None
            except Exception:  # noqa: BLE001
                prep = None
        for _, r in g.iterrows():
            rec = dict(r)
            if prep is None or len(prep["time"]) == 0:
                rec["data_status"] = "no_usable_products"
                rows.append(rec)
                continue
            m = FK.model_for(r)
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
        if n + len(e) > cap and n > 0:
            break
        chosen.append(tic)
        n += len(e)
    df["in_final_set"] = df.tic_id.isin(chosen) & df.eligible
    df.to_csv(K2_TRUTH / "fresh_kp_final.csv", index=False)
    final = df[df.in_final_set]
    final.drop_duplicates("tic_id")[["tic_id", "role", "acq_rank", "k1_class", "tic_Tmag", "tic_Teff", "tic_rad",
                                     "tic_mass", "tic_logg", "tic_ra", "tic_dec", "tic_GAIA"]].to_csv(
        K2 / "manifests" / "fresh_kp_hosts_final.csv", index=False)
    out = {"utc": utc(), "pool_planets": int(len(df)), "pool_hosts": int(df.tic_id.nunique()),
           "data_status": df.data_status.value_counts().to_dict(), "eligible_planets": int(df.eligible.sum()),
           "final_planets": int(len(final)), "final_hosts": int(final.tic_id.nunique()),
           "strong_cohort_snr20_ge3": int((final.snr_exp_k1 >= 20).sum()),
           "truth_sha256": sha(K2_TRUTH / "fresh_kp_final.csv")}
    write(K2 / "manifests" / "fresh_kp_final_selection.json", out, replace=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["kp", "adv", "stellar", "finalize"])
    a = ap.parse_args()
    fn = {"kp": build_kp, "adv": build_adv, "stellar": stellar, "finalize": finalize}[a.what]
    print(json.dumps(fn(), indent=1, default=str))
