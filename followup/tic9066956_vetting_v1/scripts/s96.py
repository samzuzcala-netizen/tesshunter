"""Sector 96 forward test for TIC 9066956 from a TESScut SPOC-FFI cutout (Claude vetting 2026-10-06).

Steps: download 25x25 cutout; local-annulus background per cadence; circular apertures
r = 1.0/1.5/2.0/3.0 px at the PM-propagated Gaia position; regress against pointing
(flux-weighted centroid) and background; biweight 0.5 d; exposure-integrated box depth at
the six-sector ephemeris; random-phase null; odd/even; phase-0.5.
"""
import json, os, sys, glob, socket
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from wotan import flatten

socket.setdefaulttimeout(120)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "s96")
os.makedirs(OUT, exist_ok=True)
RA0, DE0 = 356.6090260814, -11.79712715164        # Gaia DR3 epoch 2016.0
PMRA, PMDE = 55.1, -114.233                        # mas/yr
EPOCH = 2025.69
P, T0 = 0.7134476511671136, 3182.8243522568264     # six-sector refined
DUR = 0.723 / 24


def get_cutout():
    have = glob.glob(os.path.join(OUT, "*s0096*.fits"))
    if have:
        return have[0]
    from astroquery.mast import Tesscut
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    c = SkyCoord(RA0 * u.deg, DE0 * u.deg)
    m = Tesscut.download_cutouts(coordinates=c, size=25, sector=96, path=OUT)
    return str(m["Local Path"][0])


def overlap(t, exp, phase0=0.0):
    ph = ((t - T0) / P - phase0 + 0.5) % 1.0 - 0.5
    dt = ph * P
    lo = np.maximum(dt - exp / 2, -DUR / 2)
    hi = np.minimum(dt + exp / 2, DUR / 2)
    return np.clip(hi - lo, 0, None) / exp


def depth(t, r, sig, exp, phase0=0.0, parity=None):
    w = overlap(t, exp, phase0)
    if parity is not None:
        cyc = np.round((t - T0) / P - phase0).astype(int)
        w = np.where(cyc % 2 == parity, w, 0.0)
    if (w > 0).sum() < 3:
        return np.nan, np.nan
    return (-np.sum(w * r) / np.sum(w * w) * 1e3, sig / np.sqrt(np.sum(w * w)) * 1e3)


def main():
    path = get_cutout()
    with fits.open(path) as h:
        d = h[1].data
        w = WCS(h[2].header)
        t = np.array(d["TIME"], float)
        cube = np.array(d["FLUX"], float)
        q = np.array(d["QUALITY"], int)
        exp = float(h[1].header.get("TIMEDEL", np.nanmedian(np.diff(t))))
    dy = (EPOCH - 2016.0)
    ra = RA0 + PMRA * dy / 3.6e6 / np.cos(np.radians(DE0))
    de = DE0 + PMDE * dy / 3.6e6
    col, row = w.world_to_pixel_values(ra, de)
    ny, nx = cube.shape[1:]
    yy, xx = np.mgrid[:ny, :nx]
    rr = np.hypot(xx - col, yy - row)
    ok = np.isfinite(t) & (q == 0) & np.all(np.isfinite(cube.reshape(len(t), -1)), axis=1)
    t, cube = t[ok], cube[ok]
    ann = (rr > 6) & (rr < 11)
    med_img = np.nanmedian(cube, axis=0)
    ann &= med_img < np.nanpercentile(med_img[ann], 80)
    bkg = np.nanmedian(cube[:, ann], axis=1)
    sub = cube - bkg[:, None, None]
    # pointing proxy: flux-weighted centroid inside r<3
    m3 = rr < 3
    fw = np.clip(sub[:, m3], 0, None)
    cx = np.sum(fw * xx[m3], 1) / np.sum(fw, 1)
    cy = np.sum(fw * yy[m3], 1) / np.sum(fw, 1)
    # drop scattered-light-heavy cadences
    bz = (bkg - np.median(bkg)) / (1.4826 * np.median(np.abs(bkg - np.median(bkg))))
    good = bz < 5
    res = dict(cutout=os.path.basename(path), n_cad=int(ok.sum()), n_good=int(good.sum()),
               exp_s=round(exp * 86400, 1), target_pix=[float(col), float(row)],
               t_range=[float(t.min()), float(t.max())], apertures={})
    n_tr = len(np.unique(np.round((t[good] - T0) / P)))
    res["n_cycles_covered"] = int(n_tr)
    rng = np.random.default_rng(7)
    for rad in (1.0, 1.5, 2.0, 3.0):
        ap = rr <= rad
        f = np.sum(sub[:, ap], axis=1)
        tt, ff = t[good], f[good]
        X = np.vstack([np.ones_like(tt), cx[good] - cx[good].mean(), cy[good] - cy[good].mean(),
                       bkg[good] - bkg[good].mean()]).T
        trend = flatten(tt, ff / np.median(ff), method="biweight", window_length=0.5, return_trend=True)[1]
        r = ff / np.median(ff) / trend - 1
        fin = np.isfinite(r)
        tt, r, X = tt[fin], r[fin], X[fin]
        coef, *_ = np.linalg.lstsq(X, r, rcond=None)
        r = r - X @ coef
        s = 1.4826 * np.median(np.abs(r - np.median(r)))
        k = (r < 4 * s) & (r > -6 * s)
        tt, r = tt[k], r[k]
        s = 1.4826 * np.median(np.abs(r - np.median(r)))
        dd, ee = depth(tt, r, s, exp)
        nulls = []
        while len(nulls) < 400:
            ph = rng.uniform(0.08, 0.92)
            if abs(ph - 0.5) < 0.06:
                continue
            nulls.append(depth(tt, r, s, exp, ph)[0])
        nulls = np.array(nulls)
        nstd = 1.4826 * np.median(np.abs(nulls - np.median(nulls)))
        do, eo = depth(tt, r, s, exp, parity=1)
        de_, ee_ = depth(tt, r, s, exp, parity=0)
        sd, se = depth(tt, r, s, exp, 0.5)
        # local timing: scan epoch offsets +-30 min
        offs = np.linspace(-30, 30, 61) / 1440
        scan = [depth(tt, r, s, exp, o / P)[0] for o in offs]
        res["apertures"][str(rad)] = dict(
            npix=int(ap.sum()), sig_ppt=round(s * 1e3, 2), depth=round(dd, 3), err=round(ee, 3),
            null_med=round(float(np.median(nulls)), 3), null_std=round(float(nstd), 3),
            snr_null=round(float((dd - np.median(nulls)) / nstd), 2), frac_null_ge=float(np.mean(nulls >= dd)),
            odd=[round(do, 2), round(eo, 2)], even=[round(de_, 2), round(ee_, 2)], sec=[round(sd, 2), round(se, 2)],
            best_offset_min=float(offs[int(np.nanargmax(scan))] * 1440))
        if rad == 1.5:
            np.savez(os.path.join(OUT, "s96_r1p5_lc.npz"), t=tt, r=r, sig=s, exp=exp)
    json.dump(res, open(os.path.join(OUT, "s96_result.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
