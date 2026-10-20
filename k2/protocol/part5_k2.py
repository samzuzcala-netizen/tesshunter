"""K2 Part 5: refreshed survey list, yield and price (evaluator side; K1's Part G logic, K2 outputs).

  refresh <label>   ``partG_refresh_k1`` logic against the K2 delivery-day snapshot D:/tesshunter_k2/catalogs/
                    snap_<label>: REJECTed stars dropped and refilled from the reserve in rank order (skipping REJECTs,
                    listed stars and every star in the K1 or K2 exposure ledgers); list sorted by slice then rank.
                    Reads k1/survey; writes k2/survey/targets_k2.csv, reserve_k2.csv, tce_sidecar_k2.csv and
                    k2/manifests/target_refresh_<label>.json.  K1's frozen files are not modified.
  yield             ``partG_yield_k1`` with the K2 through-C curve: K1's S flags (A1 not adopted) x C|S per expected-SNR
                    stratum on the injection C sample under the adopted C (V3; no sample item has an M1 sibling).
  price             ``reprice_survey_k2`` with the V3 Stage C unit costs (R-C, clean conditions; HELD-OUT and fresh as a
                    sensitivity).
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from k2_common import K1, K2, K1_DATA, K2_DATA, K1_TRUTH, read, write, sha, utc

N_K, N_EM = 7000, 3000


def ledger_tics() -> set:
    out = set()
    for p in (K1 / "manifests" / "exposure_ledger.csv", K2 / "manifests" / "exposure_ledger_k2.csv"):
        led = pd.read_csv(p, dtype=str)
        out |= set(pd.to_numeric(led.tic_id, errors="coerce").dropna().astype("int64"))
    return out


def refresh(label: str) -> dict:
    import catalog_adapter_k1 as CA
    sv1, sv2 = K1 / "survey", K2 / "survey"
    sv2.mkdir(parents=True, exist_ok=True)
    tg = pd.read_csv(sv1 / "targets_k1.csv", low_memory=False)
    rs = pd.read_csv(sv1 / "reserve_k1.csv", low_memory=False)
    ledger = ledger_tics()
    exposed = sorted(int(t) for t in set(tg.tic_id.astype("int64")) & ledger)
    if exposed:
        raise SystemExit(f"K-E: survey-list stars in an exposure ledger: {exposed[:10]}")
    cat = CA.K1Catalog(K2_DATA / "catalogs" / f"snap_{label}")
    chk = cat.check_many(tg)
    drop = tg[chk.xmatch_status == "REJECT"].assign(reason=chk.xmatch_reject_sources[chk.xmatch_status == "REJECT"])
    keep = tg[chk.xmatch_status != "REJECT"].copy()
    is_em = lambda df: df.k1_type.eq("M_early") if "k1_type" in df else df.k1_class.eq("eM")  # noqa: E731
    need = {"eM": N_EM - int(is_em(keep).sum()), "K": N_K - int((~is_em(keep)).sum())}
    rs = rs.sort_values("rank")
    rchk = cat.check_many(rs)
    cand = rs[(rchk.xmatch_status != "REJECT") & ~rs.tic_id.astype("int64").isin(ledger) & ~rs.tic_id.isin(keep.tic_id)]
    add = pd.concat([cand[is_em(cand)].head(max(0, need["eM"])), cand[~is_em(cand)].head(max(0, need["K"]))])
    new = pd.concat([keep, add], ignore_index=True)
    new = new.assign(_o=new.slice.ne("K").astype(int)).sort_values(["_o", "rank"]).drop(columns="_o").reset_index(drop=True)
    new.to_csv(sv2 / "targets_k2.csv", index=False)
    rs[~rs.tic_id.isin(add.tic_id)].to_csv(sv2 / "reserve_k2.csv", index=False)
    side = cat.tce_sidecar(new.tic_id.astype("int64"))
    side.to_csv(sv2 / "tce_sidecar_k2.csv", index=False)
    fchk = cat.check_many(new)
    same = bool(len(new) == len(tg) and (new.tic_id.values == tg.tic_id.values).all())
    man = {"utc": utc(), "snapshot": label, "n_before": int(len(tg)),
           "dropped": drop[["tic_id", "rank", "reason"]].to_dict(orient="records"),
           "dropped_by_reason": drop.reason.value_counts().to_dict(), "added": add[["tic_id", "rank"]].to_dict(orient="records"),
           "n_after": int(len(new)), "n_eM": int(is_em(new).sum()), "n_K": int((~is_em(new)).sum()),
           "identical_to_k1_frozen_list": same, "status_after": fchk.xmatch_status.value_counts().to_dict(),
           "spoc_tce_flagged": int(fchk.spoc_tce.sum()), "exposure_ledger_overlap": exposed,
           "targets_sha256": sha(sv2 / "targets_k2.csv"), "k1_targets_sha256": sha(sv1 / "targets_k1.csv"),
           "tce_sidecar_sha256": sha(sv2 / "tce_sidecar_k2.csv")}
    write(K2 / "manifests" / f"target_refresh_{label}.json", man, replace=True)
    return man


def curve() -> dict:
    """K2 through-C curve: per injection p = S(bound_alias) flag x C|S of its expected-SNR stratum, C|S on the C sample
    under V3 (RULES_K1 1.5 endpoint), 7-10 borrowing 10-15 as in K1 (amendment 6)."""
    import evaluate_k1 as EV
    import analyze_partD_k1 as AN
    import evaluate_k2 as E
    EV.verify_lock("partD")
    A = pd.read_csv(K1 / "results" / "ledgers" / "injections_k1.csv")
    v3 = E.k2_receipts("rc_v3a", "C")
    items = E.rc_items()
    inj = items[items.kind == "inj"].copy()
    inj["C"] = [E.endpoint(v3.get(c), p) for c, p in zip(inj.candidate_id, inj.truth_period)]
    strata = [(7, 10), (10, 15), (15, 20), (20, 40), (40, 1e9)]
    cs = []
    for lo, hi in strata:
        g = inj[(inj.snr_exp_k1 >= lo) & (inj.snr_exp_k1 < hi)]
        k = int(g.C.sum())
        cs.append({"stratum": f"{lo}-{hi}", "n": int(len(g)), "reach_C": k, "frac": (k / len(g)) if len(g) else None,
                   "wilson": EV.wilson(k, len(g)) if len(g) else None})
    cmap = {c["stratum"]: c["frac"] for c in cs}
    if cmap.get("7-10") is None:
        cmap["7-10"] = cmap["10-15"]
    sflag, col = "S_bound_alias", "snr_exp_k1"

    def p_c(row, which=None):
        if not row[sflag]:
            return 0.0
        for (lo, hi), c in zip(strata, cs):
            if lo <= row[col] < hi:
                if which is None:
                    return cmap[f"{lo}-{hi}"] or 0.0
                w = c["wilson"] or cs[1]["wilson"]
                return w[which]
        return 0.0
    out = {"c_given_s": cs, "c_given_s_7_10_borrowed_from": "10-15"}
    for name, which in (("K2", None), ("K2_low", 0), ("K2_high", 1)):
        fit = AN.fit_linear_logistic(A[col], A.apply(lambda r: p_c(r, which), axis=1))
        out[name] = {**{k: fit[k] for k in ("x50", "w", "cmax")}, "min_tr": 3, "floor": 7.1}
    k1 = read(K1 / "results" / "calibration_partD.json")["yield_model_through_C"]
    out["K1"] = {**{k: k1[k] for k in ("x50", "w", "cmax")}, "min_tr": 3, "floor": 7.1}
    return out


def yield_k2() -> dict:
    import rank_k1 as RK
    import yieldlib_k1 as Y
    tg = pd.read_csv(K2 / "survey" / "targets_k2.csv")
    types = tg.k1_type.to_numpy() if "k1_type" in tg else RK.star_type(tg.Teff)
    is_em = np.asarray(types == RK.TYPE_EM)
    K, M = tg[~is_em].copy(), tg[is_em].copy()
    tK, tM = types[~is_em], types[is_em]
    cv = curve()
    res = {"utc": utc(), "targets": "k2/survey/targets_k2.csv", "n_K": int(len(K)), "n_eM": int(len(M)),
           "c_given_s": cv.pop("c_given_s"), "curves": {k: v for k, v in cv.items() if isinstance(v, dict)}, "yield": {}}
    res["curves"]["USER"] = dict(Y.USER)
    for name, m in res["curves"].items():
        res["yield"][name] = {"K_toi": float(RK.e_new(K, tK, model=m, k_variant="toi").sum()),
                              "eM_toi": float(RK.e_new(M, tM, model=m, k_variant="toi").sum()),
                              "eM_published": float(RK.e_new(M, tM, model=m, k_variant="published").sum())}
    write(K2 / "results" / "yield_k2.json", res, replace=True)
    return res


def price() -> dict:
    import reprice_survey_k2 as RP
    base = RP.main("final", ["rc_v3a"])
    sens = RP.main("final_all_receipts", ["rc_v3a", "seen_c", "fr_k1"])
    return {"rc_v3a": {k: base[k] for k in ("queue_hours", "total_queue_hours", "days_on_this_machine")},
            "all_v3_receipts": {k: sens[k] for k in ("queue_hours", "total_queue_hours", "days_on_this_machine")}}


if __name__ == "__main__":
    cmd = sys.argv[1]
    out = refresh(sys.argv[2]) if cmd == "refresh" else yield_k2() if cmd == "yield" else price()
    print(json.dumps({k: v for k, v in out.items() if k not in ("dropped", "added")}, indent=1, default=str)[:5000])
