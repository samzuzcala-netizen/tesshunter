"""Stellar scene: Gaia DR3 positions propagated to the observation epoch, TESS
magnitudes, WCS transform to cutout pixels, and the out-of-event registration fit.

Gaia source_id values are handled as strings end to end (never floats).
"""
from __future__ import annotations

import csv

import common as C
import numpy as np
from astropy.time import Time
from scipy.optimize import minimize

TARGET = C.GAIA_TARGET


def _f(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else np.nan
    except (TypeError, ValueError):
        return np.nan


def stassun_tmag(g, bp, rp):
    """Stassun et al. 2019 (TIC v8) Gaia->TESS; G - 0.430 when no colour."""
    if np.isfinite(bp) and np.isfinite(rp):
        c = bp - rp
        if -0.2 < c < 6.0:   # validity range used for dwarfs in the TIC
            return g - 0.00522555 * c ** 3 + 0.0891337 * c ** 2 - 0.633923 * c + 0.0324473, "stassun2019_colour"
    return g - 0.430, "stassun2019_no_colour"


def load_catalogue():
    gaia = []
    with open(C.INPUTS / "gaia_dr3_cone600.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            gaia.append(r)
    tic = {}
    with open(C.INPUTS / "tic_cone400.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            gid = (r.get("GAIA") or "").strip()
            if gid and gid not in ("--", "nan"):
                tic[gid] = r
    out = []
    for r in gaia:
        sid = r["source_id"].strip()
        assert sid.isdigit(), sid
        g, bp, rp = _f(r["phot_g_mean_mag"]), _f(r["phot_bp_mean_mag"]), _f(r["phot_rp_mean_mag"])
        t_gaia, src = stassun_tmag(g, bp, rp) if np.isfinite(g) else (np.nan, "none")
        t = tic.get(sid)
        if t is not None and np.isfinite(_f(t.get("Tmag"))):
            tmag, tsrc = _f(t["Tmag"]), "TIC v8.2"
            etm = max(_f(t.get("e_Tmag")) if np.isfinite(_f(t.get("e_Tmag"))) else 0.0, 0.2)
            ticid = t.get("ID")
        else:
            tmag, tsrc, etm, ticid = t_gaia, src, 0.3, None
        out.append({"source_id": sid, "ra": _f(r["ra"]), "dec": _f(r["dec"]), "pmra": _f(r["pmra"]),
                    "pmdec": _f(r["pmdec"]), "ref_epoch": _f(r["ref_epoch"]), "parallax": _f(r["parallax"]),
                    "G": g, "BP": bp, "RP": rp, "tmag": tmag, "tmag_src": tsrc, "e_tmag": etm,
                    "tmag_gaia_relation": t_gaia, "tic_id": ticid, "ruwe": _f(r["ruwe"]),
                    "ipd_frac_multi_peak": _f(r["ipd_frac_multi_peak"]),
                    "non_single_star": r.get("non_single_star"), "duplicated_source": r.get("duplicated_source"),
                    "astrometric_params_solved": r.get("astrometric_params_solved")})
    return out


def propagate(cat, btjd):
    """Positions at epoch btjd (proper motion only; parallax term < 1e-3 px here)."""
    yr = Time(btjd + 2457000.0, format="jd", scale="tdb").jyear
    ra, dec = [], []
    for s in cat:
        dt = yr - (s["ref_epoch"] if np.isfinite(s["ref_epoch"]) else 2016.0)
        pmra = s["pmra"] if np.isfinite(s["pmra"]) else 0.0
        pmdec = s["pmdec"] if np.isfinite(s["pmdec"]) else 0.0
        d = s["dec"] + pmdec * dt / 3.6e6
        r = s["ra"] + pmra * dt / 3.6e6 / np.cos(np.radians(s["dec"]))
        ra.append(r); dec.append(d)
    return np.array(ra), np.array(dec), yr


def to_pixels(S, ra, dec):
    x, y = S.wcs.all_world2pix(np.asarray(ra), np.asarray(dec), 0)
    return np.asarray(x, float), np.asarray(y, float)


def sep_arcsec(ra1, dec1, ra2, dec2):
    d1, d2 = np.radians(dec1), np.radians(dec2)
    a = np.sin((d2 - d1) / 2) ** 2 + np.cos(d1) * np.cos(d2) * np.sin(np.radians(ra2 - ra1) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(a))) * 3600.0


def scene_positions(S, cat, btjd):
    ra, dec, yr = propagate(cat, btjd)
    x, y = to_pixels(S, ra, dec)
    return ra, dec, x, y, yr


def fit_registration(S, img, img_err, cat, x, y, prf, zp0=20.44, bright_t=16.0, margin=3.0,
                     tmax=20.5, frac_model_err=0.03, width_scale=1.0):
    """Fit out-of-event image = sum f_k PRF(x_k+dx, y_k+dy) + plane.

    Bright stars (T <= bright_t) have free fluxes; fainter ones are fixed at the
    catalogue flux scaled by a common free factor. Returns dict with offsets,
    fluxes and diagnostics. Weights: 1/(err^2 + (frac*img)^2).
    """
    ny, nx = img.shape
    tm = np.array([c["tmag"] for c in cat])
    inside = (x > -margin) & (x < nx - 1 + margin) & (y > -margin) & (y < ny - 1 + margin) & np.isfinite(tm) & (tm < tmax)
    idx = np.nonzero(inside)[0]
    bright = idx[tm[idx] <= bright_t]
    faint = idx[tm[idx] > bright_t]
    ii, jj = np.mgrid[0:ny, 0:nx]
    pr, pc = ii.ravel().astype(float), jj.ravel().astype(float)
    d = img.ravel()
    w = 1.0 / (img_err.ravel() ** 2 + (frac_model_err * np.clip(d, 0, None)) ** 2)
    sw = np.sqrt(w)
    fcat = 10 ** (-0.4 * (tm - zp0))

    def design(dx, dy):
        cols = []
        if bright.size:
            cols.append(prf.render_many(x[bright] + dx, y[bright] + dy, pr, pc, width_scale).T)
        if faint.size:
            fr = prf.render_many(x[faint] + dx, y[faint] + dy, pr, pc, width_scale).T @ fcat[faint]
            cols.append(fr[:, None])
        cols.append(np.ones((pr.size, 1)))
        cols.append((pc - nx / 2)[:, None]); cols.append((pr - ny / 2)[:, None])
        return np.hstack(cols)

    def solve(p):
        A = design(p[0], p[1])
        coef, *_ = np.linalg.lstsq(A * sw[:, None], d * sw, rcond=None)
        r = d - A @ coef
        return float(np.sum(w * r * r)), coef, A, r

    best = None
    for gx in np.arange(-0.6, 0.61, 0.2):
        for gy in np.arange(-0.6, 0.61, 0.2):
            c2 = solve((gx, gy))[0]
            if best is None or c2 < best[0]:
                best = (c2, gx, gy)
    x0 = np.array([best[1], best[2]])
    simplex = np.array([x0, x0 + [0.05, 0.0], x0 + [0.0, 0.05]])
    res = minimize(lambda p: solve(p)[0], x0=x0, method="Nelder-Mead",
                   options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": 600, "initial_simplex": simplex})
    c2, coef, A, r = solve(res.x)
    dof = max(1, d.size - A.shape[1] - 2)
    red = c2 / dof
    # statistical offset errors from the numerical Hessian, scaled by reduced chi2
    h = 0.02
    H = np.zeros((2, 2))
    f0 = c2
    for a in range(2):
        for b in range(2):
            ea = np.eye(2)[a] * h; eb = np.eye(2)[b] * h
            H[a, b] = (solve(res.x + ea + eb)[0] - solve(res.x + ea - eb)[0]
                       - solve(res.x - ea + eb)[0] + solve(res.x - ea - eb)[0]) / (4 * h * h)
    try:
        cov = 2.0 * np.linalg.inv(H) * max(red, 1.0)
        err = np.sqrt(np.clip(np.diag(cov), 0, None))
    except np.linalg.LinAlgError:
        err = np.array([np.nan, np.nan])
    nb = bright.size
    fl = {cat[k]["source_id"]: float(coef[n]) for n, k in enumerate(bright)}
    faint_scale = float(coef[nb]) if faint.size else None
    return {"dx": float(res.x[0]), "dy": float(res.x[1]), "dx_err_stat": float(err[0]), "dy_err_stat": float(err[1]),
            "chi2": c2, "dof": dof, "red_chi2": red, "n_bright": int(nb), "n_faint": int(faint.size),
            "bright_ids": [cat[k]["source_id"] for k in bright], "flux_bright": fl, "faint_scale": faint_scale,
            "plane": [float(v) for v in coef[-3:]], "residual": r.reshape(img.shape), "model": (A @ coef).reshape(img.shape),
            "width_scale": width_scale}


def zero_point(reg, cat_by_id, tmax=15.5, exclude=()):
    vals = []
    for sid, f in reg["flux_bright"].items():
        t = cat_by_id[sid]["tmag"]
        if sid in exclude or not np.isfinite(t) or t > tmax or f <= 0:
            continue
        vals.append(t + 2.5 * np.log10(f))
    vals = np.array(vals)
    if vals.size == 0:
        return np.nan, np.nan, 0
    med = float(np.median(vals))
    mad = float(1.4826 * np.median(np.abs(vals - med))) if vals.size > 2 else np.nan
    return med, mad, int(vals.size)
