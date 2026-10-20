"""K1 Part D1 per-host injection job (evaluator side; truth sealed under k1/truth/injections).

For one injection host: four seeded draws (``inject_k1.draw``; seed = sha256("20261009:k1:inj:<tic>")),
the injected store copies, and for each injection the truth row with the expected SNR (RULES 1.4) and
the observed-transit count (1.3) under both arms.  The blind row (inj_id, tic_id and stellar columns
only) goes to ``D:/tesshunter_k1/injections/blind/tic<id>.json`` for the search planner.
CLI: ``inject_host_k1.py <tic> --n 4 --receipt <path>``.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from k1_common import ROOT, DATA, TRUTH, environment, read, write, utc

environment(offline=True)
import inject_k1 as I  # noqa: E402


def host_row(tic):
    for name in ("injection_hosts.csv",):
        df = pd.read_csv(ROOT / "manifests" / name)
        m = df[df.tic_id == int(tic)]
        if len(m):
            return m.iloc[0].to_dict()
    raise KeyError(tic)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("tic", type=int)
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--receipt", required=True)
    a = ap.parse_args(argv)
    host = host_row(a.tic)
    seed = int(hashlib.sha256(f"20261009:k1:inj:{a.tic}".encode()).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    prods = I.load_products(a.tic)
    prep = I.prepared(prods)
    blind, truths = [], []
    for k in range(a.n):
        inj_id = f"inj_{a.tic}_{k}"
        params = I.draw(host, rng, prep)
        truth = I.prepare_injection(inj_id, host, params)
        model = dict(period=params["period"], t0=params["t0"], rp_rs=params["rp_rs"], b=params["b"],
                     a_rs=params["a_rs"], u=(params["u1"], params["u2"]))
        for arm, s56 in (("k1", False), ("s56", True)):
            truth[f"snr_exp_{arm}"] = I.expected_snr(prep, s56, **model)
            truth[f"n_obs_transits_{arm}"] = I.observed_transits(prep, s56, params["period"], params["t0"], params["t14_days"])
        truth.update(k1_class=host["k1_class"], tmag=float(host["Tmag"]), n_usable=int(host["n_usable"]),
                     seed_hex=f"{seed:016x}", index=k, sigma_by_sector={str(s): v for s, v in prep["sigma"].items()})
        write(TRUTH / "injections" / f"{inj_id}.json", truth, replace=True)
        truths.append(truth)
        blind.append({"inj_id": inj_id, "tic_id": int(a.tic), **{c: host.get(c) for c in
                      ("ra", "dec", "Tmag", "Teff", "logg", "rad", "mass", "k1_class")}})
    write(DATA / "injections" / "blind" / f"tic{a.tic}.json", blind, replace=True)
    write(Path(a.receipt), {"tic_id": a.tic, "status": "COMPLETE", "n": len(truths), "utc": utc(),
                            "n_draws": [t["n_draws"] for t in truths]}, replace=True)
    print("inject", a.tic, len(truths), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
