"""K1 Part C3 / rule A4: refit the ranking's noise model from measured per-product noise.

For every injection and false-alarm host (uninjected store): the K1 prepared series (window 1.1 d,
quality and low-precision masks, isolated dips removed) gives each product's empirical per-cadence
noise sigma_cad (1.4826 x MAD); its one-hour equivalent is sigma_cad x sqrt(cadence / 3600 s).  Per
host, the hourly noise is the median over products.  The ranking model is
``yieldlib_k1.sigma_1h(Tmag)`` (repo noise model x the review's measured Tmag ratio).  Refit:
sigma_1h(Tmag) = sqrt((s x model(Tmag))^2 + floor^2), s and floor by least squares in log space.
A4: the population is re-ranked with noise_scale = refit / model; if more than 10% of the top-7,000 K
or top-3,000 eM change, the re-ranked lists are adopted before the freeze (both kept).
Writes ``k1/results/noise_refit.json`` and ``D:/tesshunter_k1/pop/noise_per_host.csv``.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from k1_common import ROOT, DATA, STORE, environment, write, utc

environment(offline=True)
import inject_k1 as I  # noqa: E402
import yieldlib_k1 as Y  # noqa: E402


def measure_hosts(hosts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, h in hosts.iterrows():
        tic = int(h.tic_id)
        if not (STORE / f"tic{tic}" / "index.json").exists():
            continue
        try:
            prods = I.load_products(tic)
            if not prods:
                continue
            prep = I.prepared(prods)
        except Exception as exc:  # noqa: BLE001
            rows.append({"tic_id": tic, "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        per = []
        for s, sig in prep["sigma"].items():
            cad = prep["cadence_s"][int(s)]
            per.append({"sector": int(s), "cadence_s": cad, "sigma_cad": sig, "sigma_1h": sig * math.sqrt(cad / 3600.0)})
        per = pd.DataFrame(per)
        r = {"tic_id": tic, "Tmag": float(h.Tmag), "k1_class": h.k1_class, "n_products": len(per),
             "sigma_1h_median": float(per.sigma_1h.median())}
        for c, name in ((1800.0, "1800"), (600.0, "600"), (200.0, "200")):
            sub = per[np.isclose(per.cadence_s, c, rtol=0.2)]
            r[f"sigma_1h_{name}"] = float(sub.sigma_1h.median()) if len(sub) else np.nan
            r[f"n_{name}"] = int(len(sub))
        rows.append(r)
    return pd.DataFrame(rows)


def fit(df: pd.DataFrame) -> dict:
    from scipy.optimize import least_squares
    d = df.dropna(subset=["sigma_1h_median"])
    t = d.Tmag.to_numpy(float)
    y = d.sigma_1h_median.to_numpy(float)
    m = Y.sigma_1h(t)

    def resid(p):
        s, f = p
        return np.log(np.sqrt((s * m) ** 2 + (f * 1e-6) ** 2)) - np.log(y)
    r = least_squares(resid, x0=[1.0, 50.0], bounds=([0.1, 0.0], [10.0, 2000.0]))
    s, f = r.x
    return {"scale": float(s), "floor_ppm_per_hour": float(f), "n_hosts": int(len(d)),
            "rms_log_residual": float(np.sqrt(np.mean(r.fun ** 2)))}


def refit_sigma(tmag, p):
    m = Y.sigma_1h(np.asarray(tmag, float))
    return np.sqrt((p["scale"] * m) ** 2 + (p["floor_ppm_per_hour"] * 1e-6) ** 2)


def rerank(p) -> dict:
    import rank_k1 as RK
    r = pd.read_pickle(DATA / "pop" / "ranked_all.pkl")
    scale = refit_sigma(r.Tmag, p) / Y.sigma_1h(r.Tmag.to_numpy(float))
    r["E_new_refit"] = RK.e_new(r, r["k1_type"], n_user_col="n_usable", p_max=50.0, noise_scale=scale)
    out = {}
    for cls, n in (("K", 7000), ("eM", 3000)):
        sub = r[r.k1_class == cls]
        old = set(sub.sort_values(["E_new", "tic_id"], ascending=[False, True]).head(n).tic_id)
        new = set(sub.sort_values(["E_new_refit", "tic_id"], ascending=[False, True]).head(n).tic_id)
        out[cls] = {"n": n, "changed": len(old - new), "fraction_changed": len(old - new) / n,
                    "top_E_new_model": float(sub.E_new.nlargest(n).sum()),
                    "top_E_new_refit": float(sub.E_new_refit.nlargest(n).sum())}
    out["a4_fires"] = any(v["fraction_changed"] > 0.10 for v in out.values() if isinstance(v, dict))
    r[["tic_id", "k1_class", "E_new", "E_new_refit"]].to_pickle(DATA / "pop" / "ranked_refit.pkl")
    return out


def main():
    hosts = pd.concat([pd.read_csv(ROOT / "manifests" / f"{n}_hosts.csv").assign(set=n)
                       for n in ("injection", "false_alarm")], ignore_index=True)
    df = measure_hosts(hosts)
    df.to_csv(DATA / "pop" / "noise_per_host.csv", index=False)
    ok = df.dropna(subset=["sigma_1h_median"]) if "sigma_1h_median" in df else df.iloc[0:0]
    p = fit(ok)
    ok = ok.assign(model=Y.sigma_1h(ok.Tmag.to_numpy(float)), refit=refit_sigma(ok.Tmag, p))
    bins = pd.cut(ok.Tmag, [10, 11, 12, 13, 13.6])
    table = []
    for b, g in ok.groupby(bins, observed=True):
        row = {"tmag_bin": str(b), "n": int(len(g)), "measured_ppm_h": float(g.sigma_1h_median.median() * 1e6),
               "model_ppm_h": float(g.model.median() * 1e6), "refit_ppm_h": float(g.refit.median() * 1e6),
               "measured_over_model": float((g.sigma_1h_median / g.model).median())}
        for c in ("1800", "600", "200"):
            row[f"measured_{c}s_ppm_h"] = float(g[f"sigma_1h_{c}"].median() * 1e6)
        table.append(row)
    out = {"utc": utc(), "fit": p, "by_tmag": table, "n_hosts_measured": int(len(ok)),
           "n_errors": int(df["error"].notna().sum()) if "error" in df else 0, "rerank": rerank(p)}
    write(ROOT / "results" / "noise_refit.json", out, replace=True)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
