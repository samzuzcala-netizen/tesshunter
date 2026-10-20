"""PROTOCOL 6/11: posterior summaries of transit geometry conditional on the named target being the
(undiluted) host, with exposure integration and local baselines profiled per event (s11 Model).

Parameters: k, b' = b/(1+k) in [0, 1), ln rho_eff (circular-equivalent density); for TIC 270573718 also one
timing offset per observing season (the 'season' mode).  Two prior choices:
  free     : ln rho_eff uniform in [ln 0.05, ln 100] (eccentricity absorbed; reports g and the implied e_min)
  catalog  : rho_eff ~ N(rho_cat, sigma_rho_cat) truncated > 0 (circular-orbit assumption)
Radius: Rp = k * R_star with R_star ~ N(R_TIC, 10 %) (TIC error), reported in Earth radii.  Per-point errors are
the event white scatter x beta (as s11).  These are CONDITIONAL posteriors: they do not include dilution by an
unresolved star, and they do not validate the planet.
Outputs: results/s17_mcmc_<tic>.json
"""
import sys

import emcee

from fu3_common import *
from events import adopted
from s11_shape import windows, Model, season_map, a_rs

SEED = 20261018
RSUN_REARTH = 109.076


def run(tic, red="pdc_raw", nwalk=24, nstep=1500, burn=500):
    eph = adopted(tic)
    ev = windows(tic, red, eph)
    use_season = tic == 270573718
    smap = season_map([e["cycle"] for e in ev])
    M = Model(ev, eph, seasons=smap if use_season else None)
    ns = len(set(smap.values())) if use_season else 0
    rho_c, rho_e = eph["stellar"]["rho_cgs"], eph["stellar"]["rho_err"]
    out = dict(tic=tic, reduction=red, generated_utc=utc(), season_offsets_free=use_season, n_events=len(ev),
               stellar=eph["stellar"], runs={})
    for prior in ("free", "catalog"):
        def lnp(x):
            k, bp, lnr = x[:3]
            offs = {s: x[3 + s] for s in range(ns)}
            if not (0.005 < k < 0.3 and 0 <= bp < 1 and np.log(0.05) < lnr < np.log(100)):
                return -np.inf
            if any(abs(v) > 0.15 for v in offs.values()):
                return -np.inf
            lp = 0.0
            if prior == "catalog":
                lp += -0.5 * ((np.exp(lnr) - rho_c) / rho_e) ** 2
            r = M.resid(k, bp * (1 + k), np.exp(lnr), 1.0, offs)
            return lp - 0.5 * float(r @ r)
        rng = np.random.default_rng(SEED + tic % 1000 + (0 if prior == "free" else 1))
        p0 = []
        for _ in range(nwalk):
            p0.append([eph["k"] * (1 + 0.05 * rng.normal()), min(0.95, abs(0.3 + 0.1 * rng.normal())),
                       np.log(rho_c) + 0.1 * rng.normal()] + [0.0004 * rng.normal() for _ in range(ns)])
        p0 = np.array(p0)
        if use_season:
            s11 = read(RES / f"s11_shape_{tic}_{red}.json")["season"]["A_planet_free"]["offsets_min"]
            for s in range(ns):
                p0[:, 3 + s] += float(s11.get(str(s), 0.0)) / 1440
        sampler = emcee.EnsembleSampler(nwalk, p0.shape[1], lnp)
        sampler.random_state = np.random.RandomState(SEED % 2 ** 31)
        sampler.run_mcmc(p0, nstep, progress=False)
        ch = sampler.get_chain(discard=burn, flat=True)
        lnpost = sampler.get_log_prob(discard=burn, flat=True)
        k, bp, lnr = ch[:, 0], ch[:, 1], ch[:, 2]
        b = bp * (1 + k)
        rho = np.exp(lnr)
        g = (rho_c / rho) ** (1 / 3)
        emin = np.abs(g * g - 1) / (g * g + 1)
        Rs = eph["stellar"]["radius"] * (1 + 0.10 * np.random.default_rng(SEED).normal(size=len(k)))
        rp = k * Rs * RSUN_REARTH
        T14 = []
        q = lambda a: dict(zip(("p02.5", "p16", "p50", "p84", "p97.5"), np.percentile(a, [2.5, 16, 50, 84, 97.5]).tolist()))  # noqa: E731
        res = dict(acceptance=float(np.mean(sampler.acceptance_fraction)), n_samples=int(len(k)),
                   k=q(k), b=q(b), rho_eff=q(rho), g=q(g), e_min=q(emin), rp_rearth=q(rp),
                   frac_b_gt_0p8=float(np.mean(b > 0.8)), frac_grazing=float(np.mean(b > 1 - k)),
                   best_lnpost=float(lnpost.max()))
        if use_season:
            res["season_offsets_min"] = {str(s): q(ch[:, 3 + s] * 1440) for s in range(ns)}
        try:
            res["autocorr_steps"] = [float(v) for v in sampler.get_autocorr_time(quiet=True)]
        except Exception:   # noqa: BLE001
            res["autocorr_steps"] = None
        out["runs"][prior] = res
        log("s17", f"{tic} {red} {prior}: k {res['k']['p50']:.4f} [{res['k']['p16']:.4f},{res['k']['p84']:.4f}] "
                   f"b {res['b']['p50']:.2f} [{res['b']['p16']:.2f},{res['b']['p84']:.2f}] rho {res['rho_eff']['p50']:.2f} "
                   f"Rp {res['rp_rearth']['p50']:.2f} [{res['rp_rearth']['p16']:.2f},{res['rp_rearth']['p84']:.2f}] "
                   f"e_min p50 {res['e_min']['p50']:.2f}; P(b>0.8) {res['frac_b_gt_0p8']:.2f}; acc {res['acceptance']:.2f}")
    save(RES / f"s17_mcmc_{tic}.json", out)


if __name__ == "__main__":
    for t in [int(a) for a in sys.argv[1:]] or list(TICS):
        run(t)
