"""Common-sky-position joint fit over events (each event in its own WCS/PRF,
event-specific amplitude and plane). mode='dimming' (R2, A >= 0) or 'signed'."""
from __future__ import annotations

import numpy as np
from scipy.stats import chi2 as chi2d

import core
import fitting

D2 = fitting.DCHI2_2DOF
KEYS = {"dimming": ("chi2p", "chi2p", "bestp_chi2"), "signed": ("chi2", "chi2", "best_chi2")}


def sky_setup(ctxs, ra0, dec0, half=85.0, step=1.0):
    xi, eta, ra, dec = fitting.sky_grid(ra0, dec0, half, step)
    maps = {}
    for e, ctx in ctxs.items():
        maps[e] = core.sky_to_event_pixels(ctx, ra, dec)
    return {"xi": xi, "eta": eta, "ra": ra, "dec": dec, "pix": maps, "step": step}


def joint(ctxs, ress, use, sky, mode="dimming", reg_draws=0, rng=None, host_ids=None, keep_maps=False):
    mk, hk, bk = KEYS[mode]
    xi, eta = sky["xi"], sky["eta"]
    tot = np.zeros_like(xi)
    for e in use:
        x, y = sky["pix"][e]
        tot = tot + ctxs[e].fitter.interp_chi2(ress[e]["_maps"][mk], x, y)
    k = np.nanargmin(tot)
    iy, ix = np.unravel_index(k, tot.shape)
    best = {"xi": float(xi[iy, ix]), "eta": float(eta[iy, ix]), "ra": float(sky["ra"][iy, ix]),
            "dec": float(sky["dec"][iy, ix]), "chi2": float(tot[iy, ix])}
    sum0 = float(sum(ress[e]["chi2_0"] for e in use))
    sum_emin = float(sum(ress[e][bk] for e in use))
    out = {"mode": mode, "events": list(use), "best": best, "chi2_0_sum": sum0, "free_improvement": sum0 - best["chi2"],
           "Q_consistency": best["chi2"] - sum_emin, "Q_dof": 2 * (len(use) - 1)}
    out["Q_p"] = float(chi2d.sf(out["Q_consistency"], out["Q_dof"])) if len(use) > 1 else None
    sids = host_ids if host_ids is not None else list(ress[use[0]]["hosts"].keys())
    sids = [s for s in sids if all(s in ress[e]["hosts"] for e in use)]
    hosts = {}
    for sid in sids:
        c = sum(ress[e]["hosts"][sid][hk] for e in use)
        A = np.array([ress[e]["hosts"][sid]["A"] for e in use]); sA = np.array([ress[e]["hosts"][sid]["sA"] for e in use])
        wA = 1 / sA ** 2
        Am = float(np.sum(A * wA) / np.sum(wA)); sAm = float(1 / np.sqrt(np.sum(wA)))
        hosts[sid] = {"chi2": float(c), "dchi2_vs_free": float(c - best["chi2"]), "A_weighted": Am, "sA_weighted": sAm,
                      "snr_weighted": Am / sAm, "A_per_event": A.tolist(), "sA_per_event": sA.tolist(),
                      "common_amplitude_extra_chi2": float(np.sum((A - Am) ** 2 * wA)),
                      "improvement_vs_null": float(sum0 - c)}
    if hosts:
        cmin = min(h["chi2"] for h in hosts.values())
        for sid, h in hosts.items():
            h["dchi2_vs_best_catalogue"] = h["chi2"] - cmin
            h["inside"] = {lvl: bool(h["dchi2_vs_free"] <= thr) for lvl, thr in D2.items()}
        out["best_catalogue_host"] = min(hosts, key=lambda s: hosts[s]["chi2"])
    out["hosts"] = hosts
    dmap = tot - best["chi2"]
    st = sky["step"]
    out["region_area_arcsec2"] = {lvl: float(np.nansum(dmap <= thr) * st * st) for lvl, thr in D2.items()}
    out["best_on_grid_edge"] = bool(iy in (0, tot.shape[0] - 1) or ix in (0, tot.shape[1] - 1))
    if reg_draws:
        rng = rng or np.random.default_rng(0)
        bx, by, hostd = [], [], {s: [] for s in hosts}
        Lsum = np.zeros_like(xi)
        for _ in range(reg_draws):
            tt = np.zeros_like(xi)
            hc = {s: 0.0 for s in hosts}
            for e in use:
                ctx = ctxs[e]
                ox, oy = rng.normal(0, ctx.sig_reg[0]), rng.normal(0, ctx.sig_reg[1])
                x, y = sky["pix"][e]
                tt = tt + ctx.fitter.interp_chi2(ress[e]["_maps"][mk], x + ox, y + oy)
                for s in hosts:
                    k2 = ctx.ids.index(s)
                    hc[s] += float(ctx.fitter.interp_chi2(ress[e]["_maps"][mk], np.array([ctx.x[k2] + ox]),
                                                          np.array([ctx.y[k2] + oy]))[0])
            kk = np.nanargmin(tt)
            jy, jx = np.unravel_index(kk, tt.shape)
            bx.append(float(xi[jy, jx])); by.append(float(eta[jy, jx]))
            m = float(np.nanmin(tt))
            Lsum += np.exp(-0.5 * (tt - best["chi2"]))
            for s in hosts:
                hostd[s].append(hc[s] - m)
        Lm = Lsum / reg_draws
        with np.errstate(divide="ignore"):
            marg = -2 * np.log(np.where(Lm > 0, Lm, np.nan))
        marg = marg - np.nanmin(marg)
        out["registration_mc"] = {"n_draws": reg_draws, "best_xi_std": float(np.std(bx)), "best_eta_std": float(np.std(by)),
                                  "best_xi_mean": float(np.mean(bx)), "best_eta_mean": float(np.mean(by)),
                                  "marginal_region_area_arcsec2": {lvl: float(np.nansum(marg <= thr) * st * st) for lvl, thr in D2.items()},
                                  "host_dchi2_vs_free_median": {s: float(np.median(v)) for s, v in hostd.items()},
                                  "host_dchi2_vs_free_p05": {s: float(np.percentile(v, 5)) for s, v in hostd.items()}}
        if keep_maps:
            out["_marg"] = marg
    if keep_maps:
        out["_tot"] = tot
    return out


def strip(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}
