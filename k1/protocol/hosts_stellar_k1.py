"""Worker-visible stellar tables for every K1 set (no truth columns): D:/tesshunter_k1/hosts/stellar_<set>.csv
with tic_id, ra, dec, Tmag, Teff, logg, rad, mass, k1_class, GAIA (string), role, and the neighbour-target
form neighbours_<set>.csv (tic_id, ra_deg, dec_deg, tmag, teff_k, radius_rsun, mass_msun, tic_gaia_id)."""
from __future__ import annotations

import json

import pandas as pd

from k1_common import ROOT, DATA, TRUTH, environment, utc, write

environment(offline=False)
COLS = ["tic_id", "ra", "dec", "Tmag", "Teff", "logg", "rad", "mass", "k1_class", "GAIA", "role"]


def nb_form(df):
    return pd.DataFrame({"tic_id": df.tic_id, "ra_deg": df.ra, "dec_deg": df.dec, "tmag": df.Tmag, "teff_k": df.Teff,
                         "radius_rsun": df.rad, "mass_msun": df["mass"].fillna(df.rad), "tic_gaia_id": df.GAIA})


def main():
    out = DATA / "hosts"
    out.mkdir(parents=True, exist_ok=True)
    sets = {}
    for name in ("injection", "false_alarm"):
        h = pd.read_csv(ROOT / "manifests" / f"{name}_hosts.csv", dtype={"GAIA": str})
        sets[name] = h.assign(role=name)[COLS]
    kp = pd.read_csv(TRUTH / "known_planets_truth.csv", dtype={"tic_GAIA": str}).drop_duplicates("tic_id")
    sets["kp"] = pd.DataFrame({"tic_id": kp.tic_id, "ra": kp.tic_ra, "dec": kp.tic_dec, "Tmag": kp.tic_Tmag,
                               "Teff": kp.tic_Teff, "logg": kp.tic_logg, "rad": kp.tic_rad, "mass": kp.tic_mass,
                               "k1_class": kp.k1_class, "GAIA": kp.tic_GAIA, "role": "kp_" + kp.role})
    adv = pd.read_csv(ROOT / "manifests" / "adv_hosts.csv")
    import build_sets_k1 as B
    tp = B.tic_params(adv.tic_id)
    a = adv[["tic_id", "role", "k1_class"]].merge(tp, on="tic_id", how="left")
    sets["adv"] = a.assign(role="adv_" + a.role)[COLS]
    summary = {}
    for name, df in sets.items():
        df.to_csv(out / f"stellar_{name}.csv", index=False)
        nb_form(df).to_csv(out / f"neighbours_{name}.csv", index=False)
        summary[name] = {"n": int(len(df)), "missing_coords": int(df.ra.isna().sum()), "missing_gaia": int(df.GAIA.isna().sum())}
    write(ROOT / "manifests" / "hosts_stellar.json", dict(summary, utc=utc()), replace=True)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
