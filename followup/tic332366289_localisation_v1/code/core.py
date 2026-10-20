"""Shared per-event context and the single extraction/localisation recipe used for
real events, null control windows and injections (identical code path)."""
from __future__ import annotations

import json

import common as C
import numpy as np

import data as Dm
import diffimg
import fitting
import prf as P
import scene as Sc
import windows as W

CFG = W.CFG
EA = CFG["ephemerides"]["primary"]
EF = CFG["ephemerides"]["sensitivity"][0]
EVENTS = {"E00": (57, 0), "E32": (79, 32), "E33": (80, 33), "E39": (84, 39)}
PRIMARY = ["E00", "E32", "E33"]
HOST_RADIUS_PX = 3.6
# union over E00/E32/E33/E39 of catalogue sources within 3.6 px (results/scene.json, neighbours.csv)
HOSTS = [C.GAIA_TARGET] + list(C.LISTED_NEIGHBOURS) + ["1415338478770171264", "1415338543194431616",
                                                       "1415338543194435712"]


def tc_of(eph, n):
    return eph["t0_btjd"] + n * eph["period_d"]


class EventContext:
    """Sector data, registered host positions, PRFs and the fitter for one event."""

    def __init__(self, eid, S=None, cat=None, scene_json=None, prf_kind="tess", gauss_sigma=None):
        sec, n = EVENTS[eid]
        self.eid, self.sector, self.n = eid, sec, n
        self.S = S if S is not None else Dm.load_sector(sec)
        self.cat = cat if cat is not None else Sc.load_catalogue()
        sj = scene_json if scene_json is not None else json.load(open(C.RESULTS / "scene.json"))
        reg = sj["events"][eid]["registration"]
        self.dx, self.dy = reg["dx"], reg["dy"]
        self.sig_reg = sj["events"][eid]["registration_sigma_adopted_px"]
        self.zp = sj["events"][eid]["zero_point"]
        self.f_target = sj["events"][eid]["target_flux_fit_e_s"]
        self.tc = tc_of(EA, n)
        ra, dec, x, y, _ = Sc.scene_positions(self.S, self.cat, self.tc)
        self.ra, self.dec = ra, dec
        self.x, self.y = x + self.dx, y + self.dy  # registered pixel positions
        ids = [c["source_id"] for c in self.cat]
        self.ids = ids
        kt = ids.index(C.GAIA_TARGET)
        self.kt = kt
        self.xt, self.yt = self.x[kt], self.y[kt]
        self.prf_tess = P.prf_for_sector(self.S, (self.xt, self.yt))
        self.prf = self.prf_tess if prf_kind == "tess" else P.GaussPRF(gauss_sigma)
        self.fitter = fitting.EventFitter(self.prf, (self.xt, self.yt), self.S.flux.shape[1:], half=CFG["fit"]["fit_box_half_width_px"])
        self.ap = self.S.spoc["aperture_mask"]

    def fixed_host_indices(self):
        """Common host list for all events (target, 4 listed neighbours, and every
        catalogue source found within 3.6 px of the target in any event's scene)."""
        return [self.ids.index(s) for s in HOSTS]

    def host_indices(self, extra_ids=()):
        d = np.hypot(self.x - self.xt, self.y - self.yt)
        hosts = [self.kt]
        for i in np.argsort(d):
            if i == self.kt:
                continue
            if (d[i] <= HOST_RADIUS_PX and np.isfinite(self.cat[i]["tmag"])) or self.ids[i] in C.LISTED_NEIGHBOURS or self.ids[i] in extra_ids:
                hosts.append(int(i))
        return hosts

    def flux_of(self, i):
        if i == self.kt:
            return self.f_target
        t = self.cat[i]["tmag"]
        return 10 ** (-0.4 * (t - self.zp))

    def aperture_fraction(self, xs, ys, prf=None, width_scale=1.0):
        p = self.prf_tess if prf is None else prf
        img = p.render(xs, ys, self.S.flux.shape[1:], width_scale)
        return float(img[self.ap].sum())


# Revision R1 (results/noise_model_revision.json; selected on calibration-half null
# windows before any event fit): linear baseline + per-frame background regressor,
# point-to-point noise. The original V0 (linear, MAD) is kept as a sensitivity.
PRIMARY_RECIPE = {"deg": 1, "noise": "p2p", "bkg_regressor": True}


def analyse(ctx, tc, duration_d, cube=None, deg=None, kappa=1.0, host_idx=(), keep_maps=True, noise=None,
            bkg_regressor=None, inject=None):
    """The single recipe: difference image -> M0 / M_free map / M_host fits."""
    deg = PRIMARY_RECIPE["deg"] if deg is None else deg
    noise = PRIMARY_RECIPE["noise"] if noise is None else noise
    bkg_regressor = PRIMARY_RECIPE["bkg_regressor"] if bkg_regressor is None else bkg_regressor
    di = diffimg.difference_image(ctx.S, tc, duration_d, deg=deg, cube=cube, noise=noise, bkg_regressor=bkg_regressor,
                                  inject=inject)
    if di is None:
        return None
    f = ctx.fitter
    m = f.fit_map(di["D"], di["sigma"], kappa)
    res = {"tc": float(tc), "n_in": di["n_in"], "n_ref": di["n_ref"], "kappa": kappa, "chi2_0": m["chi2_0"],
           "npix": m["npix"], "best_x": m["best_x"], "best_y": m["best_y"], "best_A": m["best_A"],
           "best_sA": m["best_sA"], "best_chi2": m["best_chi2"],
           "free_improvement": m["chi2_0"] - m["best_chi2"],
           # R2 dimming-only (A >= 0) free fit
           "bestp_x": m["bestp_x"], "bestp_y": m["bestp_y"], "bestp_A": m["bestp_A"], "bestp_sA": m["bestp_sA"],
           "bestp_chi2": m["bestp_chi2"], "freep_improvement": m["chi2_0"] - m["bestp_chi2"]}
    hosts = {}
    if len(host_idx):
        xs = np.array([ctx.x[i] for i in host_idx]); ys = np.array([ctx.y[i] for i in host_idx])
        A, sA, c2, c0 = f.fit_at(di["D"], di["sigma"], xs, ys, kappa)
        c2p = np.where(A > 0, c2, c0)
        for j, i in enumerate(host_idx):
            hosts[ctx.ids[i]] = {"x": float(xs[j]), "y": float(ys[j]), "A": float(A[j]), "sA": float(sA[j]),
                                 "snr": float(A[j] / sA[j]), "chi2": float(c2[j]), "chi2p": float(c2p[j]),
                                 "dchi2_vs_free": float(c2[j] - m["best_chi2"]),
                                 "dchi2p_vs_free": float(c2p[j] - m["bestp_chi2"]),
                                 "improvement_vs_null": float(m["chi2_0"] - c2[j])}
    res["hosts"] = hosts
    if keep_maps:
        res["_maps"] = {"chi2": m["chi2"], "chi2p": m["chi2p"], "A": m["A"], "sA": m["sA"]}
        res["_di"] = di
    return res


def trapezoid_shape(t, tc, duration_d, ingress_d=10.0 / 1440.0, cadence_d=200.0 / 86400.0, nsub=10):
    """Fractional depth shape (0..1) integrated over each cadence."""
    off = (np.arange(nsub) + 0.5) / nsub - 0.5
    tt = t[:, None] + off[None, :] * cadence_d
    a = np.abs(tt - tc)
    half = duration_d / 2.0
    s = np.clip((half - a) / ingress_d, 0.0, 1.0)
    return s.mean(axis=1)


def injected_cube(ctx, tc, duration_d, xs, ys, A, prf=None, width_scale=1.0):
    """Subtract A * shape(t) * PRF(host) from the real cube, only near the window."""
    p = ctx.prf_tess if prf is None else prf
    cube = ctx.S.flux.copy()
    near = np.abs(ctx.S.time - tc) <= duration_d
    shp = trapezoid_shape(ctx.S.time[near], tc, duration_d)
    img = p.render(xs, ys, cube.shape[1:], width_scale)
    cube[near] -= (A * shp)[:, None, None] * img[None]
    return cube


def sky_to_event_pixels(ctx, ra, dec, extra_dx=0.0, extra_dy=0.0):
    x, y = ctx.S.wcs.all_world2pix(np.asarray(ra).ravel(), np.asarray(dec).ravel(), 0)
    return (np.asarray(x).reshape(np.shape(ra)) + ctx.dx + extra_dx,
            np.asarray(y).reshape(np.shape(ra)) + ctx.dy + extra_dy)
