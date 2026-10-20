"""PRF fits of difference images: D = A * PRF(x, y) + plane (signed A, plane profiled).

For a template t and data d with weights w and plane design Q:
  t_perp = t - Q (Q^T W Q)^-1 Q^T W t,  d_perp likewise,
  A = (t_perp^T W d_perp) / (t_perp^T W t_perp),  sigma_A = (t_perp^T W t_perp)^-1/2,
  chi2 = chi2_0 - (t_perp^T W d_perp)^2 / (t_perp^T W t_perp).
chi2_0 is the null model M0 (plane only). Every model has the same plane freedom.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import map_coordinates


class EventFitter:
    def __init__(self, prf, centre_xy, shape, half=5, grid_half=4.5, grid_step=0.05, width_scale=1.0):
        self.prf = prf
        self.shape = shape
        cx, cy = int(round(centre_xy[0])), int(round(centre_xy[1]))
        self.cx, self.cy = cx, cy
        r0, r1 = max(0, cy - half), min(shape[0] - 1, cy + half)
        c0, c1 = max(0, cx - half), min(shape[1] - 1, cx + half)
        ii, jj = np.mgrid[r0:r1 + 1, c0:c1 + 1]
        self.rows, self.cols = ii.ravel(), jj.ravel()
        self.box = (r0, r1, c0, c1)
        self.ref_xy = (float(centre_xy[0]), float(centre_xy[1]))
        self.Q = np.vstack([np.ones(self.rows.size), self.cols - centre_xy[0], self.rows - centre_xy[1]]).T
        g = np.arange(-grid_half, grid_half + 1e-9, grid_step)
        self.goff = g
        gx, gy = np.meshgrid(centre_xy[0] + g, centre_xy[1] + g)  # [iy, ix]
        self.grid_x, self.grid_y = gx, gy
        self.width_scale = width_scale
        self.T = prf.render_many(gx.ravel(), gy.ravel(), self.rows.astype(float), self.cols.astype(float), width_scale)

    def _prep(self, D, sigma, kappa):
        d = D[self.rows, self.cols].astype(float)
        s = sigma[self.rows, self.cols].astype(float) * kappa
        ok = np.isfinite(d) & np.isfinite(s) & (s > 0)
        w = np.where(ok, 1.0 / np.where(ok, s, 1.0) ** 2, 0.0)
        d = np.where(ok, d, 0.0)
        WQ = self.Q * w[:, None]
        Minv = np.linalg.inv(self.Q.T @ WQ)
        dp = d - self.Q @ (Minv @ (WQ.T @ d))
        chi2_0 = float(np.sum(w * dp * dp))
        return d, w, WQ, Minv, dp, chi2_0, int(ok.sum())

    def _profile(self, T, w, WQ, Minv, dp, chi2_0):
        Tp = T - (T @ WQ) @ Minv.T @ self.Q.T
        num = Tp @ (w * dp)
        den = (Tp * Tp) @ w
        A = num / den
        return A, 1.0 / np.sqrt(den), chi2_0 - num * num / den

    def fit_map(self, D, sigma, kappa=1.0):
        """Signed map ('chi2') and, revision R2, the dimming-only map with the
        zero-amplitude boundary A >= 0 ('chi2p' = chi2_0 - max(num,0)^2/den)."""
        d, w, WQ, Minv, dp, chi2_0, npix = self._prep(D, sigma, kappa)
        A, sA, chi2 = self._profile(self.T, w, WQ, Minv, dp, chi2_0)
        chi2p = np.where(A > 0, chi2, chi2_0)
        n = self.grid_x.shape
        k = int(np.argmin(chi2))
        kp = int(np.argmin(chi2p))
        return {"chi2_0": chi2_0, "npix": npix, "dof0": npix - 3, "A": A.reshape(n), "sA": sA.reshape(n),
                "chi2": chi2.reshape(n), "best_x": float(self.grid_x.ravel()[k]), "best_y": float(self.grid_y.ravel()[k]),
                "best_A": float(A[k]), "best_sA": float(sA[k]), "best_chi2": float(chi2[k]),
                "chi2p": chi2p.reshape(n), "bestp_x": float(self.grid_x.ravel()[kp]), "bestp_y": float(self.grid_y.ravel()[kp]),
                "bestp_A": float(A[kp]), "bestp_sA": float(sA[kp]), "bestp_chi2": float(chi2p[kp])}

    def fit_at(self, D, sigma, xs, ys, kappa=1.0, prf=None, width_scale=None):
        d, w, WQ, Minv, dp, chi2_0, npix = self._prep(D, sigma, kappa)
        p = self.prf if prf is None else prf
        ws = self.width_scale if width_scale is None else width_scale
        T = p.render_many(np.atleast_1d(xs), np.atleast_1d(ys), self.rows.astype(float), self.cols.astype(float), ws)
        A, sA, chi2 = self._profile(T, w, WQ, Minv, dp, chi2_0)
        return A, sA, chi2, chi2_0

    def model_image(self, D, sigma, xs, ys, kappa=1.0):
        """Best-fit model (PRF + plane) and residual images on the fit box."""
        d, w, WQ, Minv, dp, chi2_0, npix = self._prep(D, sigma, kappa)
        t = self.prf.render_many(np.atleast_1d(xs), np.atleast_1d(ys), self.rows.astype(float),
                                 self.cols.astype(float), self.width_scale)[0]
        X = np.vstack([t, self.Q.T]).T
        sw = np.sqrt(w)
        coef, *_ = np.linalg.lstsq(X * sw[:, None], d * sw, rcond=None)
        model = np.full(self.shape, np.nan); resid = np.full(self.shape, np.nan)
        model[self.rows, self.cols] = X @ coef
        resid[self.rows, self.cols] = d - X @ coef
        return model, resid, coef

    def interp_chi2(self, chi2_map, xs, ys):
        """Bilinear interpolation of a chi2 map at pixel positions (NaN outside)."""
        step = self.goff[1] - self.goff[0]
        fx = (np.asarray(xs) - self.grid_x[0, 0]) / step
        fy = (np.asarray(ys) - self.grid_y[0, 0]) / step
        n = chi2_map.shape
        out = map_coordinates(chi2_map, [fy.ravel(), fx.ravel()], order=1, mode="constant", cval=np.nan)
        out = out.reshape(np.shape(xs))
        outside = (fx < 0) | (fy < 0) | (fx > n[1] - 1) | (fy > n[0] - 1)
        return np.where(outside, np.nan, out)


def sky_grid(ra0, dec0, half_arcsec=85.0, step_arcsec=1.0):
    g = np.arange(-half_arcsec, half_arcsec + 1e-9, step_arcsec)
    xi, eta = np.meshgrid(g, g)  # xi east (+RA), eta north
    ra = ra0 + xi / 3600.0 / np.cos(np.radians(dec0))
    dec = dec0 + eta / 3600.0
    return xi, eta, ra, dec


DCHI2_2DOF = {"68.27": 2.30, "95.45": 6.18, "99.73": 11.83}
