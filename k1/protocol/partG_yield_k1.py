"""K1 Part G3: expected yield of the frozen target list with the Part D completeness curve.

E_new (``rank_k1.e_new``; periods 0.5-50 d) is recomputed for the top 7,000 K (TOI-calibrated occurrence) and the
3,000-star eM slice (TOI-calibrated and published DC15 occurrence) under:
  * USER: the review's Oct 3-4 curve (x50 12.5, w 2.5, cmax 0.65), as the list was ranked;
  * K1: the Part D through-C curve (``calibration_partD.json`` ``yield_model_through_C``);
  * K1_low / K1_high: the same fit with C|S at each stratum's Wilson lower / upper bound (amendment 6 range);
  * K1 x noise refit (C3 scale) as a sensitivity.
The review's eM decision rule (>= 5 real new candidates: eM leads the next batch; <= 2: stay with K; 3-4: extend
the slice) is restated with these numbers.  Writes ``k1/results/yield_partG.json``.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from k1_common import ROOT, read, write, utc
import rank_k1 as RK
import yieldlib_k1 as Y
import analyze_partD_k1 as AN


def curves() -> dict:
    cal = read(ROOT / "results" / "calibration_partD.json")
    base = {"min_tr": 3, "floor": 7.1}
    out = {"USER": dict(Y.USER), "K1": {**{k: cal["yield_model_through_C"][k] for k in ("x50", "w", "cmax")}, **base}}
    led = pd.read_csv(ROOT / "results" / "ledgers" / "injections_k1.csv")
    sflag, col = f"S_{cal['frozen']['s_mode']}", f"snr_exp_{cal['frozen']['arm']}"
    strata = [(7, 10), (10, 15), (15, 20), (20, 40), (40, 1e9)]
    cs = {c["stratum"]: c for c in cal["c_given_s"]}
    for name, idx in (("K1_low", 0), ("K1_high", 1)):
        vals = {}
        for lo, hi in strata:
            c = cs[f"{lo}-{hi}"] if f"{lo}-{hi}" in cs else cs[f"{lo}-1000000000.0"]
            w = c.get("wilson") or cs["10-15"]["wilson"]           # 7-10 borrows 10-15 (amendment 6)
            vals[(lo, hi)] = w[idx]
        def pc(r):
            if not r[sflag]:
                return 0.0
            for (lo, hi), v in vals.items():
                if lo <= r[col] < hi:
                    return v
            return 0.0
        fit = AN.fit_linear_logistic(led[col], led.apply(pc, axis=1))
        out[name] = {**{k: fit[k] for k in ("x50", "w", "cmax")}, **base}
    return out


def main(targets_csv: str | None = None) -> dict:
    tg = pd.read_csv(targets_csv or (ROOT / "survey" / "targets_k1.csv"))
    types = tg.k1_type.to_numpy() if "k1_type" in tg else RK.star_type(tg.Teff)
    is_em = np.asarray(types == RK.TYPE_EM)
    K, M = tg[~is_em].copy(), tg[is_em].copy()
    tK, tM = types[~is_em], types[is_em]
    cv = curves()
    noise = read(ROOT / "results" / "noise_refit.json")["fit"]["scale"]
    res = {"utc": utc(), "targets": str(targets_csv or "k1/survey/targets_k1.csv"), "n_K": int(len(K)), "n_eM": int(len(M)),
           "curves": cv, "noise_refit_scale": noise, "review_values": {"K_top10k": 9.0, "eM_top3k_toi": 2.4, "eM_top3k_published": 8.1},
           "yield": {}}
    for name, m in cv.items():
        res["yield"][name] = {
            "K_toi": float(RK.e_new(K, tK, model=m, k_variant="toi").sum()),
            "eM_toi": float(RK.e_new(M, tM, model=m, k_variant="toi").sum()),
            "eM_published": float(RK.e_new(M, tM, model=m, k_variant="published").sum())}
    m = cv["K1"]
    res["yield"]["K1_noise_refit"] = {
        "K_toi": float(RK.e_new(K, tK, model=m, k_variant="toi", noise_scale=noise).sum()),
        "eM_toi": float(RK.e_new(M, tM, model=m, k_variant="toi", noise_scale=noise).sum()),
        "eM_published": float(RK.e_new(M, tM, model=m, k_variant="published", noise_scale=noise).sum())}
    def rule(x):
        return "eM leads the next batch" if x >= 5 else ("stay with K" if x <= 2 else "extend the eM slice")
    res["eM_rule"] = {v: {"expected": res["yield"]["K1"][v], "low": res["yield"]["K1_low"][v], "high": res["yield"]["K1_high"][v],
                          "rule_on_expected": rule(res["yield"]["K1"][v])} for v in ("eM_toi", "eM_published")}
    write(ROOT / "results" / "yield_partG.json", res, replace=True)
    return res


if __name__ == "__main__":
    r = main(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps({k: r[k] for k in ("n_K", "n_eM", "curves", "yield", "eM_rule")}, indent=1, default=str))
