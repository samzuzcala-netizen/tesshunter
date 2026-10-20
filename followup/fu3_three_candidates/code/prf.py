"""Mission PRF models (MAST prf_fitsfiles: start_s0001 for sectors 1-3, start_s0004 for sectors >= 4).

A PRF at CCD (row, col) is the bilinear interpolation of the four nearest grid models (117 x 117 samples at
1/9 pixel, centre index 58); it is integrated onto the pixel grid of a cutout by sampling at pixel centres and
normalising to unit sum over a 17 x 17 pixel box.  Optional broadening (Gaussian, sigma in pixels) gives the
deliberately mis-specified PRF used in the misspecification injections.
"""
from __future__ import annotations

import re

import numpy as np
import requests
from astropy.io import fits
from scipy.ndimage import gaussian_filter, map_coordinates

from fu3_common import CACHE

BASE = "https://archive.stsci.edu/missions/tess/models/prf_fitsfiles/"
DIR = CACHE / "prf"
DIR.mkdir(parents=True, exist_ok=True)


def _index(epoch, cam, ccd):
    p = DIR / f"{epoch}_cam{cam}_ccd{ccd}_index.html"
    if not p.exists():
        r = requests.get(f"{BASE}{epoch}/cam{cam}_ccd{ccd}/", timeout=60)
        r.raise_for_status()
        p.write_text(r.text, encoding="utf-8")
    names = [n for n in re.findall(r'href="([^"]+\.fits)"', p.read_text(encoding="utf-8"))
             if re.fullmatch(r"tess\d+-prf-\d-\d-row\d+-col\d+\.fits", n)]   # 117x117 grid models only
    return [(n, *map(int, re.search(r"row(\d+)-col(\d+)", n).groups())) for n in names]


def _file(epoch, cam, ccd, name):
    p = DIR / f"{epoch}_cam{cam}_ccd{ccd}_{name}"
    if not p.exists():
        r = requests.get(f"{BASE}{epoch}/cam{cam}_ccd{ccd}/{name}", timeout=60)
        r.raise_for_status()
        p.write_bytes(r.content)
    return p


class PRF:
    def __init__(self, sector, cam, ccd, row, col, broaden_px=0.0):
        epoch = "start_s0001" if sector <= 3 else "start_s0004"
        parsed = _index(epoch, cam, ccd)
        rs = sorted({r for _, r, c in parsed})
        cs = sorted({c for _, r, c in parsed})
        rl = max([r for r in rs if r <= row] or [rs[0]])
        rh = min([r for r in rs if r >= row] or [rs[-1]])
        cl = max([c for c in cs if c <= col] or [cs[0]])
        ch = min([c for c in cs if c >= col] or [cs[-1]])
        z = np.zeros((117, 117))
        self.files = []
        for name, r, c in parsed:
            if r not in (rl, rh) or c not in (cl, ch):
                continue
            wx = 1.0 if cl == ch else ((ch - col) / (ch - cl) if c == cl else (col - cl) / (ch - cl))
            wy = 1.0 if rl == rh else ((rh - row) / (rh - rl) if r == rl else (row - rl) / (rh - rl))
            p = _file(epoch, cam, ccd, name)
            z += fits.getdata(p).astype(float) * wx * wy
            self.files.append(p.name)
        if broaden_px > 0:
            z = gaussian_filter(z, broaden_px * 9.0)
        self.z = z
        self.meta = dict(epoch=epoch, camera=cam, ccd=ccd, row=row, col=col, files=self.files, broaden_px=broaden_px)

    def image(self, x, y, shape):
        """Unit-sum PRF of a source at cutout pixel coordinates (x = column, y = row) on a grid of ``shape``."""
        ny, nx = shape
        yy, xx = np.indices((ny, nx))
        cy, cx = int(np.floor(y)), int(np.floor(x))
        g = np.arange(-8, 9)
        gy, gx = np.meshgrid(58 + 9 * (g + cy - y), 58 + 9 * (g + cx - x), indexing="ij")
        full = map_coordinates(self.z, [gy, gx], order=1, mode="constant", cval=0.0).sum()
        img = map_coordinates(self.z, [58 + 9 * (yy - y), 58 + 9 * (xx - x)], order=1, mode="constant", cval=0.0)
        return img / max(full, 1e-12)
