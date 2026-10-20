"""TESScut cube handling for FU3 (PROTOCOL 5.4): source positions, backgrounds, predeclared apertures, PRF scene
photometry and per-pixel transit-decrement maps.  Read-only on all inputs."""
from __future__ import annotations

import glob
import warnings

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time
import astropy.units as u
from scipy.optimize import minimize, lsq_linear

from fu3_common import S1, CACHE, read
from prf import PRF

warnings.filterwarnings("ignore")
try:
    from lightkurve.utils import TessQualityFlags
    DEFAULT_BITMASK = int(TessQualityFlags.DEFAULT_BITMASK)
except Exception:   # noqa: BLE001
    DEFAULT_BITMASK = 175


def gaia_objects(tic):
    f = glob.glob(str(S1 / "funnel" / "s1_b1" / f"s1_{tic}_p*" / "pixels" / f"tic{tic}_gaia_positions.json"))
    return read(f[0])["objects"]


def load_cube(path):
    import lightkurve as lk
    tpf = lk.TessTargetPixelFile(str(path), quality_bitmask="none")
    t = np.asarray(tpf.time.value, float)
    cube = np.asarray(tpf.flux.value, float)
    err = np.asarray(tpf.flux_err.value, float)
    q = np.asarray(tpf.quality, np.int64)
    good = np.isfinite(t) & ((q & DEFAULT_BITMASK) == 0) & np.isfinite(cube).all(axis=(1, 2))
    return dict(tpf=tpf, t_all=t, q_all=q, t=t[good], cube=cube[good], err=err[good], q=q[good],
                camera=int(tpf.camera), ccd=int(tpf.ccd), row0=int(tpf.row), col0=int(tpf.column),
                shape=cube.shape[1:], sector=int(tpf.sector))


def positions(c, tic, gmax=19.5):
    objs = gaia_objects(tic)
    tmid = Time(np.median(c["t"]) + 2457000, format="jd")
    tg = None
    out = []
    for o in objs:
        if (o.get("phot_g_mean_mag") or 99) > gmax and o["source_id"] != 0:
            pass
        sc = SkyCoord(o["ra"] * u.deg, o["dec"] * u.deg, pm_ra_cosdec=(o.get("pmra") or 0) * u.mas / u.yr,
                      pm_dec=(o.get("pmdec") or 0) * u.mas / u.yr, obstime=Time(2016.0, format="jyear"))
        sc = sc.apply_space_motion(new_obstime=tmid)
        x, y = c["tpf"].wcs.world_to_pixel(sc)
        ny, nx = c["shape"]
        if -1.5 <= x <= nx + 0.5 and -1.5 <= y <= ny + 0.5:
            out.append(dict(id=str(o["source_id"]), x=float(x), y=float(y), G=o.get("phot_g_mean_mag"),
                            Rp=o.get("phot_rp_mean_mag"), ra=float(sc.ra.deg), dec=float(sc.dec.deg)))
    return out


def target_of(pos, gaia_id):
    for p in pos:
        if p["id"] == str(gaia_id):
            return p
    raise KeyError(gaia_id)


def backgrounds(c, pos, tgt):
    """Two predeclared sky estimates per cadence: annulus median (5-9 px, pixels within 2 px of G < 18 sources
    masked) and a fitted plane on the faintest 40% of pixels beyond 4 px."""
    ny, nx = c["shape"]
    yy, xx = np.indices((ny, nx))
    r = np.hypot(xx - tgt["x"], yy - tgt["y"])
    srcmask = np.zeros((ny, nx), bool)
    for s in pos:
        if (s["G"] or 99) < 18:
            srcmask |= np.hypot(xx - s["x"], yy - s["y"]) < 2.0
    ann = (r >= 5) & (r <= 9) & ~srcmask
    ref = np.median(c["cube"], axis=0)
    outer = (r > 4) & ~srcmask
    faint = outer & (ref <= np.quantile(ref[outer], 0.4)) if outer.sum() > 10 else outer
    res = {}
    if ann.sum() >= 16:
        res["annulus"] = np.median(c["cube"][:, ann], axis=1)[:, None, None] * np.ones((1, ny, nx))
    if faint.sum() >= 16:
        A = np.column_stack([np.ones(faint.sum()), (xx[faint] - nx / 2) / nx, (yy[faint] - ny / 2) / ny])
        coef = np.linalg.lstsq(A, c["cube"][:, faint].T, rcond=None)[0]          # 3 x n_cad
        P = np.stack([np.ones((ny, nx)), (xx - nx / 2) / nx, (yy - ny / 2) / ny])
        res["plane"] = np.einsum("kt,kij->tij", coef, P)
    meta = dict(n_annulus=int(ann.sum()), n_plane=int(faint.sum()))
    return res, meta


def scene_model(c, pos, tgt, prf, sub, dg=6.0, rmax=4.5):
    """Reference-image scene fit: all Gaia sources with G < G_t + dg within rmax+2 px, a common position offset,
    free non-negative fluxes and a plane.  Returns offset, fluxes, fractional residual rms within rmax."""
    ny, nx = c["shape"]
    yy, xx = np.indices((ny, nx))
    ref = np.median(c["cube"] - sub, axis=0)
    gt = tgt["G"] or 14
    stars = [s for s in pos if (s["G"] or 99) < gt + dg and np.hypot(s["x"] - tgt["x"], s["y"] - tgt["y"]) < rmax + 2]
    mask = np.hypot(xx - tgt["x"], yy - tgt["y"]) < rmax
    P3 = [np.ones(mask.sum()), ((xx - nx / 2) / nx)[mask], ((yy - ny / 2) / ny)[mask]]
    w = 1 / np.sqrt(np.maximum(np.abs(ref[mask]), np.percentile(np.abs(ref[mask]), 30)))

    def calc(off, full=False):
        M = np.column_stack([prf.image(s["x"] + off[0], s["y"] + off[1], (ny, nx))[mask] for s in stars] + P3)
        lb = np.r_[np.zeros(len(stars)), [-np.inf] * 3]
        sol = lsq_linear(M * w[:, None], ref[mask] * w, bounds=(lb, np.full(len(lb), np.inf)), tol=1e-7, max_iter=200)
        resid = ref[mask] - M @ sol.x
        return (resid, sol.x) if full else float(np.sum((resid * w) ** 2))

    fit = minimize(calc, [0.0, 0.0], method="Powell", bounds=[(-0.8, 0.8), (-0.8, 0.8)],
                   options={"maxiter": 60, "xtol": 0.003})
    resid, coef = calc(fit.x, True)
    peak = ref[int(round(tgt["y"])), int(round(tgt["x"]))] if 0 <= round(tgt["y"]) < ny and 0 <= round(tgt["x"]) < nx else np.max(ref[mask])
    return dict(offset=[float(v) for v in fit.x], stars=stars, fluxes={s["id"]: float(coef[i]) for i, s in enumerate(stars)},
                frac_rms=float(np.std(resid) / max(peak, 1e-9)), n_stars=len(stars), mask_r=rmax)


def aperture_masks(c, tgt, scene, prf):
    ny, nx = c["shape"]
    yy, xx = np.indices((ny, nx))
    off = scene["offset"]
    r = np.hypot(xx - tgt["x"] - off[0], yy - tgt["y"] - off[1])
    masks = {f"circ{rad:.1f}": r <= rad for rad in (1.0, 1.5, 2.0)}
    tot = np.zeros((ny, nx))
    tim = None
    for s in scene["stars"]:
        im = prf.image(s["x"] + off[0], s["y"] + off[1], (ny, nx)) * max(scene["fluxes"][s["id"]], 0)
        tot += im
        if s["id"] == tgt["id"]:
            tim = im
    frac = np.where(tot > 0, tim / np.maximum(tot, 1e-12), 0)
    masks["neighbour_excl"] = (frac >= 0.5) & (r <= 3.0)
    return masks, frac


def throughput(c, scene, prf, mask):
    """Fraction of each scene source's flux that falls in ``mask`` (mission PRF, fitted offset)."""
    ny, nx = c["shape"]
    off = scene["offset"]
    out = {}
    for s in scene["stars"]:
        im = prf.image(s["x"] + off[0], s["y"] + off[1], (ny, nx))
        out[s["id"]] = dict(frac_in_aperture=float(im[mask].sum()), flux_fit=scene["fluxes"][s["id"]],
                            flux_in_aperture=float(im[mask].sum() * max(scene["fluxes"][s["id"]], 0)), G=s["G"],
                            sep_px=float(np.hypot(s["x"] - scene["stars"][0]["x"], s["y"] - scene["stars"][0]["y"])))
    return out


def prf_photometry(c, sub, scene, prf, tgt, rmax=3.5):
    """Per-cadence linear PRF fit (fixed positions + offset, all scene stars, plane); returns target flux series."""
    ny, nx = c["shape"]
    yy, xx = np.indices((ny, nx))
    off = scene["offset"]
    mask = np.hypot(xx - tgt["x"] - off[0], yy - tgt["y"] - off[1]) < rmax
    stars = [s for s in scene["stars"] if np.hypot(s["x"] - tgt["x"], s["y"] - tgt["y"]) < rmax + 2.5]
    M = np.column_stack([prf.image(s["x"] + off[0], s["y"] + off[1], (ny, nx))[mask] for s in stars]
                        + [np.ones(mask.sum()), ((xx - nx / 2) / nx)[mask], ((yy - ny / 2) / ny)[mask]])
    data = (c["cube"] - sub)[:, mask]
    coef = np.linalg.lstsq(M, data.T, rcond=None)[0]
    it = [i for i, s in enumerate(stars) if s["id"] == tgt["id"]][0]
    return coef[it], dict(n_stars=len(stars), n_pix=int(mask.sum()))


def series_from_flux(c, flux, label):
    """Normalised segment for events.measure (good cadences only; edges from all cadences)."""
    from reductions import _norm
    ok = np.isfinite(flux)
    y = (_norm(c["t"], np.where(ok, flux, np.nan)) - 1.0) * 1000.0
    cad = float(np.round(np.median(np.diff(c["t"])) * 86400))
    return dict(label=label, sector=c["sector"], t=c["t"], y=y, cad_s=cad, quality_ok=ok & np.isfinite(y),
                t_all=c["t_all"], quality_all=c["q_all"], bkg_all=None)


def decrement_map(c, sub, tc, eph, tmpl, half=None):
    """Per-pixel local regression (linear baseline + unit template) around one event; returns per-pixel decrement
    (e-/s; positive = dimming), its error, and the number of points; None if coverage fails."""
    T14 = eph["T14"]
    half = half or min(max(3 * T14, 0.2), 0.4 * eph["P"])
    t = c["t"]
    w = np.abs(t - tc) < half
    if w.sum() < 10:
        return None
    dt = t[w] - tc
    exp_d = np.median(np.diff(t)) if len(t) > 1 else 0.0
    h = tmpl(dt, exp_d)
    nin = (np.abs(dt) < T14 / 2).sum()
    if nin < 3 or (dt < -0.6 * T14).sum() < 4 or (dt > 0.6 * T14).sum() < 4:
        return None
    X = np.column_stack([np.ones_like(dt), dt / half, -h])
    Y = (c["cube"] - sub)[w].reshape(w.sum(), -1)
    coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
    R = Y - X @ coef
    sig = 1.4826 * np.median(np.abs(R - np.median(R, axis=0)), axis=0)
    cov = np.linalg.pinv(X.T @ X)
    err = np.sqrt(cov[-1, -1]) * np.maximum(sig, 1e-9)
    ny, nx = c["shape"]
    return coef[-1].reshape(ny, nx), err.reshape(ny, nx), int(w.sum())
