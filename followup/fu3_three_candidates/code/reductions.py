"""Loaders for every reduction of the same TESS photons (D-orig and D-alt tiers), returned as series of
segments for events.py.  Read-only on the survey store, funnel and continuation products."""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np

from fu3_common import S1, CONT, PACKET, CACHE, read

try:
    from lightkurve.utils import TessQualityFlags
    DEFAULT_BITMASK = int(TessQualityFlags.DEFAULT_BITMASK)
except Exception:   # noqa: BLE001
    DEFAULT_BITMASK = 1 | 2 | 4 | 8 | 32 | 128 | 1024 | 2048 | 8192 | 32768


def funnel_case(tic):
    key = PACKET[tic].name
    for c in sorted((S1 / "funnel" / "s1_b1").glob(f"s1_{tic}_p*")):
        if (c / "tls" / f"{key}_lc.npz").exists():
            return c, key
    raise FileNotFoundError(tic)


def _norm(t, f, gap=0.5):
    """Divide by the median of each continuous segment (orbit)."""
    out = np.full_like(f, np.nan, dtype=float)
    order = np.argsort(t)
    ts = t[order]
    br = np.where(np.diff(ts) > gap)[0]
    edges = np.r_[0, br + 1, len(ts)]
    for a, b in zip(edges[:-1], edges[1:]):
        idx = order[a:b]
        m = np.isfinite(f[idx])
        if m.sum() > 5:
            out[idx] = f[idx] / np.nanmedian(f[idx][m])
    return out


def store_products(tic):
    idx = read(S1 / "audit_lc" / f"tic{tic}" / "index.json")
    return idx["products"]


def series_store(tic, column="flux"):
    """pdc_raw (column='flux': TESS-SPOC pdcsap_flux / QLP det_flux) or sap_raw (column='sap_flux')."""
    segs = []
    for p in store_products(tic):
        z = np.load(S1 / "audit_lc" / f"tic{tic}" / p["file"])
        t = z["time"].astype(float)
        q = z["quality"].astype(np.int64)
        f = z[column].astype(float)
        if p["author"] == "QLP":
            ok = q == 0
        else:
            ok = (q & DEFAULT_BITMASK) == 0
        ok &= np.isfinite(f) & np.isfinite(t)
        fn = np.where(ok, f, np.nan)
        y = (_norm(t, fn) - 1.0) * 1000.0
        segs.append(dict(label=f"{p['author']}:{column}", sector=int(p["sector"]), t=t, y=y,
                         cad_s=float(p["cadence_s"]), quality_ok=ok & np.isfinite(y), t_all=t, quality_all=q,
                         bkg_all=z["sap_bkg"].astype(float) if "sap_bkg" in z.files else None,
                         author=p["author"], camera=p.get("camera"), ccd=p.get("ccd")))
    return segs


def series_survey_detrended(tic):
    c, key = funnel_case(tic)
    z = np.load(c / "tls" / f"{key}_lc.npz")
    t, f, s = z["time_unbinned"].astype(float), z["flux_unbinned"].astype(float), z["sector_unbinned"].astype(int)
    prods = {int(p["sector"]): p for p in store_products(tic)}
    segs = []
    for sec in np.unique(s):
        m = s == sec
        ts, ys = t[m], (f[m] - 1.0) * 1000.0
        cad = float(prods[int(sec)]["cadence_s"]) if int(sec) in prods else float(np.median(np.diff(ts)) * 86400)
        segs.append(dict(label="survey_detrended", sector=int(sec), t=ts, y=ys, cad_s=cad,
                         quality_ok=np.isfinite(ys), t_all=ts, quality_all=None, bkg_all=None,
                         author=prods.get(int(sec), {}).get("author")))
    return segs


def _aperture_npz(path, label, cad_by_sector):
    z = np.load(path)
    segs = []
    for k in z.files:
        if k.endswith("_time"):
            sec = int(k.split("_")[0][1:])
            t = z[k].astype(float)
            y = (z[f"s{sec}_net"].astype(float) - 1.0) * 1000.0
            cad = cad_by_sector.get(sec, float(np.median(np.diff(t)) * 86400))
            segs.append(dict(label=label, sector=sec, t=t, y=y, cad_s=cad, quality_ok=np.isfinite(y) & np.isfinite(t),
                             t_all=t, quality_all=None,
                             bkg_all=z[f"s{sec}_sky"].astype(float) if f"s{sec}_sky" in z.files else None))
    return segs


def cadence_map(tic):
    m = {int(p["sector"]): float(p["cadence_s"]) for p in store_products(tic)}
    return m


def series_survey_aperture(tic):
    c, key = funnel_case(tic)
    p = c / "eb_screen" / f"{key}_target_aperture.npz"
    return _aperture_npz(p, "survey_tesscut_aperture", cadence_map(tic)) if p.exists() else []


def series_cont_fresh(tic):
    p = CONT / "analysis" / f"{tic}_fresh_apertures.npz"
    return _aperture_npz(p, "continuation_fresh_aperture", cadence_map(tic)) if p.exists() else []


def series_tglc(tic, column):
    """TGLC (Han & Brandt) calibrated aperture or PSF flux; quality TESS_flags == 0 and TGLC_flags == 0."""
    from astropy.io import fits
    gaia = {270573718: "4792202879700135040", 262843927: "4673750877131752832", 193718989: "1346023547769345792"}[tic]
    segs = []
    for f in sorted((CACHE / "tglc").glob(f"hlsp_tglc_tess_ffi_gaiaid-{gaia}-s*_tess_v1_llc.fits")):
        with fits.open(f) as h:
            d = h[1].data
            t = np.asarray(d["time"], float)
            y0 = np.asarray(d[column], float)
            q = np.asarray(d["TESS_flags"], np.int64)
            ok = (q == 0) & (np.asarray(d["TGLC_flags"]) == 0) & np.isfinite(y0) & np.isfinite(t)
            cad = float(h[1].header.get("XPTIME", np.median(np.diff(t)) * 86400))
            sec = int(h[0].header["SECTOR"])
            bkg = np.asarray(d["background"], float)
        y = (_norm(t, np.where(ok, y0, np.nan)) - 1.0) * 1000.0
        segs.append(dict(label=f"tglc:{column}", sector=sec, t=t, y=y, cad_s=cad, quality_ok=ok & np.isfinite(y),
                         t_all=t, quality_all=q, bkg_all=bkg))
    return segs


def series_fu3pix(tic, key):
    """FU3 TESScut extractions (s07b), scene-pass sectors only (failed scenes such as off-silicon S31/S88 of
    TIC 262843927 are excluded, never treated as non-detections)."""
    from fu3_common import RES
    px = read(RES / f"s07b_pixels_{tic}.json")
    ok = {s["sector"] for s in px["sectors"] if s.get("status") == "OK" and s.get("scene_pass")}
    segs = []
    for f in sorted((CACHE / "fu3pix").glob(f"{tic}_s*.npz")):
        sec = int(f.stem.split("_s")[1])
        if sec not in ok:
            continue
        z = np.load(f)
        if key not in z.files:
            continue
        t = z["t"].astype(float)
        flux = z[key].astype(float)
        good = np.isfinite(flux) & np.isfinite(t)
        y = (_norm(t, np.where(good, flux, np.nan)) - 1.0) * 1000.0
        cad = float(np.round(np.median(np.diff(t)) * 86400))
        segs.append(dict(label=f"fu3pix:{key}", sector=sec, t=t, y=y, cad_s=cad, quality_ok=good & np.isfinite(y),
                         t_all=t, quality_all=None, bkg_all=None))
    return segs


REDUCTIONS = {
    "fu3pix_annulus_circ1p5": lambda tic: series_fu3pix(tic, "annulus__circ1p5"),
    "fu3pix_plane_circ1p5": lambda tic: series_fu3pix(tic, "plane__circ1p5"),
    "fu3pix_prf": lambda tic: series_fu3pix(tic, "prf"),
    "tglc_aperture": lambda tic: series_tglc(tic, "cal_aper_flux"),   # independent FFI extraction (aperture)
    "tglc_psf": lambda tic: series_tglc(tic, "cal_psf_flux"),         # independent FFI extraction (PSF)
    "survey_detrended": series_survey_detrended,              # D-orig: what Stage A/C measured
    "pdc_raw": lambda tic: series_store(tic, "flux"),          # D-orig photons, no biweight
    "sap_raw": lambda tic: series_store(tic, "sap_flux"),      # same photons, pipeline SAP (no crowding corr.)
    "survey_tesscut_aperture": series_survey_aperture,         # survey Stage D 1-px TESScut aperture
    "continuation_fresh_aperture": series_cont_fresh,          # continuation's fresh TESScut aperture
}
