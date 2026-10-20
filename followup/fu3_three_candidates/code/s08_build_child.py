"""Child of s08_replay.build (runs with K1_DATA = K2_DATA = the replay root): writes replay store copies.

inv: per product, flux' = 2*m - flux and sap_flux' = 2*m_sap - sap_flux, m = median of finite values; time,
     errors, background and quality unchanged.
inj: the frozen survey_p8.inject_products with the candidate's P, k, b, a/R*, LD; epoch drawn (seeded) uniformly
     over one period from the first cadence, redrawn until >= 3 observed transits (inject_k1.observed_transits).
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter")
for p in (REPO / "src", REPO / "scripts", REPO / "k1" / "protocol", REPO / "k2" / "protocol"):
    sys.path.insert(0, str(p))
assert "tess_fu3_cache" in os.environ["K1_DATA"]
import k1_common  # noqa: E402
k1_common.environment(offline=True)
from tesshunter import survey_p8  # noqa: E402
import inject_k1 as I  # noqa: E402

S1_STORE = Path(r"D:\tesshunter_s1\audit_lc")
REPLAY = Path(r"D:\tess_fu3_cache\replay")
FU3 = Path(r"C:\Users\seanj\Documents\TESS_followup_262_193_270")


def seed_of(*parts):
    return int(hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()[:16], 16)


def write_copy(dest, tic, products):
    dest.mkdir(parents=True, exist_ok=True)
    for p in products:
        arrays = {k: p[k] for k in survey_p8.PRODUCT_ARRAYS if k in p}
        with open(dest / p["file"], "wb") as fh:
            np.savez_compressed(fh, **arrays)
    idx = json.loads((S1_STORE / f"tic{tic}" / "index.json").read_text(encoding="utf-8"))
    blind = {k: v for k, v in idx.items() if k in ("tic_id", "products", "sectors_usable_realised")}
    blind["source"] = "FU3 replay store copy"
    (dest / "index.json").write_text(json.dumps(blind, indent=1), encoding="utf-8")


def main():
    plan = json.loads((REPLAY / "jobs" / "plan.json").read_text(encoding="utf-8"))
    for row in plan:
        tic, job_id, var = int(row["tic"]), row["job_id"], row["variant"]
        base = REPLAY / ("store_inv" if var == "inv" else "store_inj") / job_id
        dest = base / f"tic{tic}"
        if (dest / "index.json").exists():
            continue
        prods = I.load_products(tic, root=S1_STORE)
        if var == "inv":
            for p in prods:
                for col in ("flux", "sap_flux"):
                    a = np.asarray(p[col], float)
                    m = np.nanmedian(a[np.isfinite(a)]) if np.isfinite(a).any() else np.nan
                    p[col] = (2 * m - a).astype(np.asarray(p[col]).dtype)
            write_copy(dest, tic, prods)
            print("inv", job_id, len(prods), flush=True)
        else:
            cand = int(row["candidate"])
            fit = json.loads((Path(r"D:\tesshunter_s1\packets\s1_b1") / {270573718: "tic270573718_P41.3839",
                              262843927: "tic262843927_P24.1089", 193718989: "tic193718989_P24.5335"}[cand]
                              / "fit.json").read_text(encoding="utf-8"))
            a = fit["adopted"]
            u = (fit["limb_darkening"]["u1"], fit["limb_darkening"]["u2"])
            prep = I.prepared(prods)
            rng = np.random.default_rng(seed_of(20261018, "inj", job_id))
            t14 = a["t14_hours"] / 24
            for n in range(1, 51):
                t0 = float(prep["time"].min()) + float(rng.uniform(0, a["period"]))
                nobs = I.observed_transits(prep, False, a["period"], t0, t14)
                if nobs >= 3:
                    break
            inj, info = survey_p8.inject_products(prods, period=a["period"], t0=t0, rp_rs=a["rp_rs"], b=a["b"],
                                                  a_rs=a["a_rs"], u=u)
            write_copy(dest, tic, inj)
            truth = dict(job_id=job_id, tic_id=tic, candidate=cand, period=a["period"], t0=t0, rp_rs=a["rp_rs"],
                         b=a["b"], a_rs=a["a_rs"], u=list(u), t14_days=t14, n_observed_transits=int(nobs),
                         n_epoch_draws=n, depth_max_ppm=info.get("depth_max_ppm"),
                         expected_snr=I.expected_snr(prep, False, period=a["period"], t0=t0, rp_rs=a["rp_rs"],
                                                     b=a["b"], a_rs=a["a_rs"], u=u))
            (base / "injection_truth.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
            print("inj", job_id, "nobs", nobs, "snr_exp", round(truth["expected_snr"], 2), flush=True)


if __name__ == "__main__":
    main()
