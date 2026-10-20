"""Load TESScut cubes with verified TESS-SPOC cadence identity.

Each TESScut frame is matched one-to-one to the TESS-SPOC light-curve cadence
with the nearest TIME (verified |dt| < 100 s; recorded). The matched TESS-SPOC
TIME (barycentric for the target position, BTJD TDB) is used as the time of
the frame: the light-curve ephemeris is defined on that time scale.

Flux convention: TESScut FLUX is calibrated e-/s per pixel and is NOT
background subtracted (FLUX_BKG is identically zero for these SPOC-FFI cubes);
no background is subtracted here. Background is modelled later.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import common as C  # noqa: F401
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

# frames are dropped if TESScut QUALITY != 0 or if the matched TESS-SPOC
# QUALITY has any of these bits (lightkurve "default" 175 + Argabrightening 16)
SPOC_BAD_BITS = 1 | 2 | 4 | 8 | 16 | 32 | 128
MOMENTUM_DUMP_BIT = 32


@dataclass
class Sector:
    sector: int
    camera: int
    ccd: int
    col0: int            # 1CRV4P: CCD column of cutout pixel [*, 0]
    row0: int            # 2CRV4P: CCD row of cutout pixel [0, *]
    wcs: WCS
    time: np.ndarray     # matched TESS-SPOC TIME (BTJD, TDB, target-barycentric)
    time_cut: np.ndarray  # original TESScut TIME
    dt_s: np.ndarray     # time_cut - time (s)
    cadenceno: np.ndarray  # matched TESS-SPOC CADENCENO
    q_cut: np.ndarray
    q_spoc: np.ndarray
    good: np.ndarray     # quality-good frames with finite flux
    dump: np.ndarray     # momentum-dump frames (either product)
    flux: np.ndarray     # (N, 21, 21) e-/s, not background subtracted
    flux_err: np.ndarray
    spoc: dict = field(default_factory=dict)   # light-curve columns on the matched frames
    meta: dict = field(default_factory=dict)


def load_sector(sector: int) -> Sector:
    path = C.TESSCUT[sector]
    with fits.open(path, memmap=True) as hd:
        h0, h1 = hd[0].header, hd[1].header
        d = hd[1].data
        t_cut = np.array(d["TIME"], float)
        flux = np.array(d["FLUX"], np.float64)
        ferr = np.array(d["FLUX_ERR"], np.float64)
        qc = np.array(d["QUALITY"], np.int64)
        wcs = WCS(hd[2].header)
        cam, ccd = int(h0["CAMERA"]), int(h0["CCD"])
        col0, row0 = int(h1["1CRV4P"]), int(h1["2CRV4P"])
    with fits.open(C.spoc_lc(sector), memmap=True) as hl:
        L = hl[1].data
        tl = np.array(L["TIME"], float)
        cols = {k: np.array(L[k], float) for k in ("SAP_FLUX", "SAP_BKG", "PDCSAP_FLUX", "PDCSAP_FLUX_ERR",
                                                    "MOM_CENTR1", "MOM_CENTR2", "POS_CORR1", "POS_CORR2")
                if k in L.columns.names}
        ql = np.array(L["QUALITY"], np.int64)
        cn = np.array(L["CADENCENO"], np.int64)
        ap = np.array(hl[2].data, np.int64)
        aph = hl[2].header
        crowd = float(hl[1].header.get("CROWDSAP", np.nan)); flfr = float(hl[1].header.get("FLFRCSAP", np.nan))
        ap_col0, ap_row0 = int(aph["CRVAL1P"]), int(aph["CRVAL2P"])
    okl = np.isfinite(tl)
    tl_f, idx_f = tl[okl], np.nonzero(okl)[0]
    j = np.searchsorted(tl_f, t_cut)
    j = np.clip(j, 1, len(tl_f) - 1)
    jl = np.where(np.abs(t_cut - tl_f[j - 1]) <= np.abs(t_cut - tl_f[j]), j - 1, j)
    dt_s = (t_cut - tl_f[jl]) * 86400.0
    if not np.all(np.abs(dt_s) < 100.0):
        raise RuntimeError(f"sector {sector}: TESScut/TESS-SPOC time match failed (max |dt| {np.max(np.abs(dt_s)):.1f} s)")
    if len(np.unique(jl)) != len(jl):
        raise RuntimeError(f"sector {sector}: non one-to-one cadence match")
    li = idx_f[jl]
    time = tl[li]
    qs = ql[li]
    finite = np.all(np.isfinite(flux), axis=(1, 2))
    good = (qc == 0) & ((qs & SPOC_BAD_BITS) == 0) & finite & np.isfinite(time)
    dump = ((qc & MOMENTUM_DUMP_BIT) != 0) | ((qs & MOMENTUM_DUMP_BIT) != 0)
    spoc = {k: v[li] for k, v in cols.items()}
    # TESS-SPOC optimal aperture (bit 2) mapped onto the TESScut pixel grid
    ap_mask = np.zeros(flux.shape[1:], bool)
    opt = (ap & 2) != 0
    for (r, c) in zip(*np.nonzero(opt)):
        rr, cc = r + ap_row0 - row0, c + ap_col0 - col0
        if 0 <= rr < flux.shape[1] and 0 <= cc < flux.shape[2]:
            ap_mask[rr, cc] = True
    meta = {"path": str(path), "spoc_path": str(C.spoc_lc(sector)), "crowdsap": crowd, "flfrcsap": flfr,
            "spoc_aperture_npix": int(opt.sum()), "spoc_aperture_npix_on_cutout": int(ap_mask.sum()),
            "spoc_aperture_origin": [ap_col0, ap_row0], "dt_s_median": float(np.median(dt_s)),
            "dt_s_min": float(dt_s.min()), "dt_s_max": float(dt_s.max()), "n_frames": int(len(time)),
            "n_good": int(good.sum()), "n_dump": int(dump.sum())}
    spoc["aperture_mask"] = ap_mask
    return Sector(sector, cam, ccd, col0, row0, wcs, time, t_cut, dt_s, cn[li], qc, qs, good, dump,
                  flux, ferr, spoc, meta)
