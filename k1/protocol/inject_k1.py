"""K1 injections (Part D1) and the shared truth-side measurements (RULES_K1 1.3, 1.4).

Evaluator side only.  For each injection: draw the planet (seeded), multiply the batman model into
``flux`` AND ``sap_flux`` of every usable product at its own exposure (``survey_p8.inject_products``),
write the injected products to ``D:/tesshunter_k1/injected/<inj_id>/tic<id>/`` (same layout as the
store; the index carries no parameters), and write the truth row to ``k1/truth/injections/`` (sealed;
search and funnel workers never read it).  The same module measures, for any transit model on a host
and arm, the expected SNR (1.4) and the observed-transit count (1.3), used for known planets too.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import numpy as np

from k1_common import DATA, STORE, TRUTH, environment, read, write, utc

environment()
from tesshunter import survey, survey_p8  # noqa: E402
from tesshunter.limb_darkening import quadratic_ld  # noqa: E402

INJ_ROOT = DATA / "injected"
R_SUN_IN_R_EARTH = 109.076
WINDOW = 1.1


def load_products(tic: int, root: Path = STORE, s56: bool = False) -> list[dict]:
    idx = read(Path(root) / f"tic{int(tic)}" / "index.json")
    out = []
    for p in idx["products"]:
        if s56 and int(p["sector"]) < 56:
            continue
        with np.load(Path(root) / f"tic{int(tic)}" / p["file"], allow_pickle=False) as z:
            d = {k: np.asarray(z[k]) for k in z.files}
        d.update(p)
        out.append(d)
    return out


def prepared(products: list[dict]) -> dict:
    """The K1 prepared (uninjected) series: per-cadence times, sectors and per-sector noise."""
    prods, _ = survey_p8.harmonise_cadence(products, 200.0 / 60.0, policy="native_mixed")
    prep = survey_p8.prepare_search_input(prods, WINDOW, deep_clip=False, empirical_err=True)
    cad = {int(p["sector"]): float(p["cadence_s"]) for p in prods}
    return {"time": prep["time"], "sector": prep["sector"].astype(int),
            "sigma": {int(k): v for k, v in prep["counters"]["empirical_flux_err_by_sector"].items()},
            "cadence_s": cad}


def model_depth(times, sector, cad_by_sector, *, period, t0, rp_rs, b, a_rs, u):
    """delta_i = 1 - model at each cadence, integrated over that cadence's product exposure."""
    d = np.zeros(len(times))
    for s in np.unique(sector):
        m = sector == s
        mod = survey.transit_model(times[m], period=period, t0=t0, rp_rs=rp_rs, b=b, a_rs=a_rs, u=u,
                                   exp_time_days=cad_by_sector[int(s)] / 86400.0, supersample=7)
        d[m] = 1.0 - mod
    return d


def expected_snr(prep: dict, s56: bool, **model) -> float:
    m = prep["sector"] >= 56 if s56 else np.ones(len(prep["time"]), bool)
    t, sec = prep["time"][m], prep["sector"][m]
    if t.size == 0:
        return 0.0
    d = model_depth(t, sec, prep["cadence_s"], **model)
    sig = np.array([prep["sigma"][int(s)] for s in sec])
    return float(math.sqrt(np.sum(d ** 2 / sig ** 2)))


def observed_transits(prep: dict, s56: bool, period: float, t0: float, t14: float) -> int:
    """Epochs with >= 50% of the expected in-transit cadences (T14 / product cadence) present."""
    m = prep["sector"] >= 56 if s56 else np.ones(len(prep["time"]), bool)
    t, sec = prep["time"][m], prep["sector"][m]
    if t.size == 0 or t14 <= 0:
        return 0
    k = np.round((t - t0) / period).astype(np.int64)
    inside = np.abs(t - (t0 + k * period)) <= t14 / 2.0
    n = 0
    for e in np.unique(k[inside]):
        sel = inside & (k == e)
        cad = np.median([prep["cadence_s"][int(s)] for s in sec[sel]]) / 86400.0
        if sel.sum() >= 0.5 * max(1.0, t14 / cad):
            n += 1
    return n


def draw(host: dict, rng, prep: dict, max_tries: int = 200) -> dict:
    """RULES/D1: Rp log-uniform 1-8 R_E (1-6 on eM), P log-uniform 0.5-50 d, b U(0, 0.9), epoch
    uniform over one period from the first cadence; Claret LD at Teff/log g; a/R* from TIC M, R.
    Redraw until >= 3 observed transits in the all-sector arm."""
    rmax = 6.0 if host["k1_class"] == "eM" else 8.0
    R = float(host["rad"]); M = float(host["mass"]) if np.isfinite(host.get("mass", np.nan)) else R
    ld = quadratic_ld(host.get("Teff"), host.get("logg"))
    tmin = float(prep["time"].min())
    for n in range(1, max_tries + 1):
        rp = float(np.exp(rng.uniform(np.log(1.0), np.log(rmax))))
        P = float(np.exp(rng.uniform(np.log(0.5), np.log(50.0))))
        b = float(rng.uniform(0.0, 0.9))
        t0 = tmin + float(rng.uniform(0.0, P))
        rp_rs = rp / (R * R_SUN_IN_R_EARTH)
        a_rs = survey.a_over_rs(P, M, R)
        if a_rs <= 1.5:
            continue
        t14 = survey.transit_duration_days(P, a_rs, b, rp_rs)
        nobs = observed_transits(prep, False, P, t0, t14)
        if nobs >= 3:
            return {"rp_rearth": rp, "period": P, "b": b, "t0": t0, "rp_rs": rp_rs, "a_rs": a_rs,
                    "u1": ld.u1, "u2": ld.u2, "ld_source": ld.source, "t14_days": t14, "n_draws": n,
                    "mass_used": M, "radius_used": R}
    raise RuntimeError("no draw with >= 3 observed transits")


def prepare_injection(inj_id: str, host: dict, params: dict) -> dict:
    """Write the injected products and return the sealed truth row (written by the caller)."""
    tic = int(host["tic_id"])
    products = load_products(tic)
    injected, info = survey_p8.inject_products(products, period=params["period"], t0=params["t0"],
                                               rp_rs=params["rp_rs"], b=params["b"], a_rs=params["a_rs"],
                                               u=(params["u1"], params["u2"]))
    dest = INJ_ROOT / inj_id / f"tic{tic}"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    idx = read(STORE / f"tic{tic}" / "index.json")
    for p in injected:
        arrays = {k: p[k] for k in survey_p8.PRODUCT_ARRAYS}
        with open(dest / p["file"], "wb") as fh:
            np.savez_compressed(fh, **arrays)
    blind = {k: v for k, v in idx.items() if k in ("tic_id", "products", "sectors_usable_realised")}
    blind["source"] = "k1 injection store copy (parameters sealed elsewhere)"
    write(dest / "index.json", blind)
    return {"inj_id": inj_id, "tic_id": tic, **params, "depth_max_ppm": info["depth_max_ppm"],
            "n_cadences_in_transit": info["n_cadences_in_transit"], "n_transits_with_data": info["n_transits_with_data"]}
