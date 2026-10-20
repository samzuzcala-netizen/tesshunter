"""Standalone TESS PRF renderer (official MAST start_s0004 models) + Gaussian alternative.

Conventions (verified on the FITS headers, 2026-10-01):
  * PRF image array is [row, col] (NAXIS1 = RAWX = CCD column = numpy axis 1).
  * 117 x 117 samples, CDELT = 1/9 px, reference sample CRPIX = 59 (1-based) ->
    0-based index 58 is the star position; sum of samples = 81 (unit flux).
  * The PRF image is the pixel response map: the value at CCD offset
    (d_col, d_row) from the star is the fraction of the star's flux collected
    by a pixel CENTRED at that offset. So, for a pixel centred at (j, i) and a
    star at (xs, ys): response = PRF[58 + 9 (i - ys), 58 + 9 (j - xs)].
  * Grid file columns 45..2092 are in FFI/TPF column numbering (science pixels).

Cutout pixel convention: pixel centres at integer 0-based (col, row); the
cutout pixel [i, j] has CCD column col0 + j and CCD row row0 + i.
"""
from __future__ import annotations

import glob
import os

import common as C
import numpy as np
from astropy.io import fits
from scipy.special import erf

ROWS = [1, 513, 1025, 1536, 2048]
COLS = [45, 557, 1069, 1580, 2092]
NS = 9
CEN = 58
HALF = 58 / 9.0  # 6.444 px: model support


def _bracket(v, grid):
    for a, b in zip(grid[:-1], grid[1:]):
        if a <= v <= b:
            return a, b
    return (grid[0], grid[1]) if v < grid[0] else (grid[-2], grid[-1])


def _grid_file(cam, ccd, r, c):
    pat = os.path.join(str(C.PRF_DIR), "start_s0004", f"cam{cam}_ccd{ccd}", f"*-prf-{cam}-{ccd}-row{r:04d}-col{c:04d}.fits")
    hits = glob.glob(pat)
    if len(hits) != 1:
        raise FileNotFoundError(pat)
    return hits[0]


def load_grid_prf(cam, ccd, r, c):
    with fits.open(_grid_file(cam, ccd, r, c)) as h:
        img = np.array(h[0].data, float)
        hd = h[0].header
        assert int(round(hd["CRPIX1P"])) == 59 and int(round(hd["CRPIX2P"])) == 59
        assert abs(hd["CDELT1P"] - 1 / 9) < 1e-9 and abs(hd["CDELT2P"] - 1 / 9) < 1e-9
        assert int(round(hd["CCD_RREF"])) == r and int(round(hd["CCD_CREF"])) == c
    return img


class TessPRF:
    """Bilinear interpolation of the 4 bracketing grid PRFs at a CCD position."""

    def __init__(self, cam: int, ccd: int, ccd_col: float, ccd_row: float):
        self.cam, self.ccd, self.ccd_col, self.ccd_row = cam, ccd, ccd_col, ccd_row
        c0, c1 = _bracket(ccd_col, COLS)
        r0, r1 = _bracket(ccd_row, ROWS)
        fc = (ccd_col - c0) / (c1 - c0)
        fr = (ccd_row - r0) / (r1 - r0)
        fc, fr = min(max(fc, 0.0), 1.0), min(max(fr, 0.0), 1.0)
        img = ((1 - fr) * (1 - fc) * load_grid_prf(cam, ccd, r0, c0) + (1 - fr) * fc * load_grid_prf(cam, ccd, r0, c1)
               + fr * (1 - fc) * load_grid_prf(cam, ccd, r1, c0) + fr * fc * load_grid_prf(cam, ccd, r1, c1))
        img = np.clip(img, 0.0, None)
        self.img = img * (81.0 / img.sum())
        self.weights = {"cols": (c0, c1), "rows": (r0, r1), "f_col": fc, "f_row": fr}

    def sample(self, d_row, d_col, width_scale=1.0):
        """PRF value at offsets (arrays, px). width_scale > 1 broadens (flux-conserving)."""
        w = float(width_scale)
        u = CEN + NS * np.asarray(d_row, float) / w
        v = CEN + NS * np.asarray(d_col, float) / w
        ok = (u >= 0) & (u <= 116) & (v >= 0) & (v <= 116)
        u = np.clip(u, 0, 116 - 1e-9); v = np.clip(v, 0, 116 - 1e-9)
        i0 = np.floor(u).astype(int); j0 = np.floor(v).astype(int)
        fu = u - i0; fv = v - j0
        im = self.img
        val = ((1 - fu) * (1 - fv) * im[i0, j0] + (1 - fu) * fv * im[i0, j0 + 1]
               + fu * (1 - fv) * im[i0 + 1, j0] + fu * fv * im[i0 + 1, j0 + 1])
        return np.where(ok, val, 0.0) / (w * w)

    def render(self, xs, ys, shape, width_scale=1.0):
        """Image (shape) of a unit-flux source at cutout position (xs=col, ys=row)."""
        ii, jj = np.mgrid[0:shape[0], 0:shape[1]]
        return self.sample(ii - ys, jj - xs, width_scale)

    def render_many(self, xs, ys, pix_rows, pix_cols, width_scale=1.0):
        """(K, P) responses of K unit sources at (xs, ys) on P pixels (rows, cols)."""
        xs = np.asarray(xs, float)[:, None]; ys = np.asarray(ys, float)[:, None]
        return self.sample(pix_rows[None, :] - ys, pix_cols[None, :] - xs, width_scale)


class GaussPRF:
    """Circular Gaussian integrated over square pixels (exploratory alternative)."""

    def __init__(self, sigma_px: float):
        self.sigma = float(sigma_px)

    def _f(self, d):
        s = self.sigma * np.sqrt(2.0)
        return 0.5 * (erf((d + 0.5) / s) - erf((d - 0.5) / s))

    def sample(self, d_row, d_col, width_scale=1.0):
        g = GaussPRF(self.sigma * width_scale)
        return g._f(np.asarray(d_row, float)) * g._f(np.asarray(d_col, float))

    def render(self, xs, ys, shape, width_scale=1.0):
        ii, jj = np.mgrid[0:shape[0], 0:shape[1]]
        return self.sample(ii - ys, jj - xs, width_scale)

    def render_many(self, xs, ys, pix_rows, pix_cols, width_scale=1.0):
        xs = np.asarray(xs, float)[:, None]; ys = np.asarray(ys, float)[:, None]
        return self.sample(pix_rows[None, :] - ys, pix_cols[None, :] - xs, width_scale)


def prf_for_sector(S, target_xy):
    """Primary PRF at the target's CCD position for Sector S (cutout col/row -> CCD)."""
    ccd_col = S.col0 + target_xy[0]
    ccd_row = S.row0 + target_xy[1]
    return TessPRF(S.camera, S.ccd, ccd_col, ccd_row)
