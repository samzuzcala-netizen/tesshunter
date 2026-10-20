"""Event-level signed difference images.

D = (per-pixel baseline model at the in-event times) - (observed in-event image),
averaged over good in-event frames, in e-/s per pixel. Positive D = flux lost
during the event. No clipping, no division by total flux, no alignment on a
centroid. The baseline is a per-pixel polynomial in time fitted to the two
reference sides only (degree 1 primary, 2 sensitivity).

Uncertainty per pixel (formal): s_p^2 (1/N_in + xbar^T (X^T X)^-1 xbar), with
s_p the robust (1.4826 MAD) scatter of the reference residuals.
"""
from __future__ import annotations

import numpy as np

import windows as W


def basis(dt_d, deg):
    x = dt_d / 0.25  # scale to O(1)
    return np.vstack([x ** k for k in range(deg + 1)]).T


def frame_background(frames):
    """Per-frame background level: mean of the 20% faintest cutout pixels."""
    flat = frames.reshape(frames.shape[0], -1)
    k = max(5, int(0.2 * flat.shape[1]))
    return np.sort(flat, axis=1)[:, :k].mean(axis=1)


def trapezoid_shape(t, tc, duration_d, ingress_d=10.0 / 1440.0, cadence_d=200.0 / 86400.0, nsub=10):
    """Fractional depth shape (0..1) integrated over each 200-s cadence."""
    off = (np.arange(nsub) + 0.5) / nsub - 0.5
    tt = t[:, None] + off[None, :] * cadence_d
    s = np.clip((duration_d / 2.0 - np.abs(tt - tc)) / ingress_d, 0.0, 1.0)
    return s.mean(axis=1)


def difference_image(S, tc, duration_d, deg=1, cube=None, role=None, noise="mad", bkg_regressor=False, inject=None):
    """cube: optional (N, ny, nx) replacement flux (used for injections).

    noise: 'mad' = robust scatter of reference residuals (original choice);
           'p2p' = 1.4826 MAD of consecutive reference-residual differences / sqrt(2)
                   (insensitive to smooth trend residuals).
    bkg_regressor: add the per-frame background level B(t) (faintest 20% of
           the cutout, measured on each frame) as a baseline regressor with a
           per-pixel coefficient fitted on the reference frames only.
    """
    if role is None:
        role, st = W.select(S.time, S.good, S.dump, tc, duration_d)
    else:
        st = {}
    F = S.flux if cube is None else cube
    iin = np.nonzero(role == W.ROLE_IN)[0]
    iref = np.nonzero((role == W.ROLE_REF_L) | (role == W.ROLE_REF_R))[0]
    ny, nx = F.shape[1:]
    if iin.size < 3 or iref.size < 10:
        return None
    Xr = basis(S.time[iref] - tc, deg)
    Xi = basis(S.time[iin] - tc, deg)
    Fr, Fi = F[iref], F[iin]
    if inject is not None:
        # pixel-level injection: subtract only the host's modelled PRF contribution,
        # A x trapezoid(t) x unit-flux PRF image, on every frame used (identical to
        # editing the cube; frames outside the event shape get zero).
        img = inject["img"]
        sr = trapezoid_shape(S.time[iref], inject["tc"], inject["dur"])
        si = trapezoid_shape(S.time[iin], inject["tc"], inject["dur"])
        Fr = Fr - (inject["A"] * sr)[:, None, None] * img[None]
        Fi = Fi - (inject["A"] * si)[:, None, None] * img[None]
    if bkg_regressor:
        br = frame_background(Fr); bi = frame_background(Fi)
        b0 = np.median(br)
        Xr = np.hstack([Xr, (br - b0)[:, None] / 10.0])
        Xi = np.hstack([Xi, (bi - b0)[:, None] / 10.0])
    Yr = Fr.reshape(iref.size, -1)
    Yi = Fi.reshape(iin.size, -1)
    coef, *_ = np.linalg.lstsq(Xr, Yr, rcond=None)
    pred_r = Xr @ coef
    resid_r = Yr - pred_r
    if noise == "p2p":
        # consecutive differences within each reference side only
        side = role[iref]
        dd = np.diff(resid_r, axis=0)
        same = side[1:] == side[:-1]
        dd = dd[same]
        s = 1.4826 * np.median(np.abs(dd - np.median(dd, axis=0)), axis=0) / np.sqrt(2.0)
    else:
        med = np.median(resid_r, axis=0)
        s = 1.4826 * np.median(np.abs(resid_r - med), axis=0)
    XtX_inv = np.linalg.inv(Xr.T @ Xr)
    xbar = Xi.mean(axis=0)
    var_fac = 1.0 / iin.size + float(xbar @ XtX_inv @ xbar)
    pred_i = Xi @ coef
    D = (pred_i - Yi).mean(axis=0)
    sig = s * np.sqrt(var_fac)
    out_img = pred_i.mean(axis=0)
    in_img = Yi.mean(axis=0)
    # pointing / motion diagnostic: least-squares shift template fit on the baseline image
    oot = out_img.reshape(ny, nx)
    gy, gx = np.gradient(oot)
    return {"D": D.reshape(ny, nx), "sigma": sig.reshape(ny, nx), "out": oot, "in": in_img.reshape(ny, nx),
            "n_in": int(iin.size), "n_ref": int(iref.size), "n_ref_left": int((role == W.ROLE_REF_L).sum()),
            "n_ref_right": int((role == W.ROLE_REF_R).sum()), "var_fac": var_fac,
            "ref_scatter": s.reshape(ny, nx), "grad_x": gx, "grad_y": gy, "role": role, "status": st,
            "deg": deg, "tc": float(tc), "duration_d": float(duration_d), "noise": noise,
            "bkg_regressor": bool(bkg_regressor)}


def series(S, role, tc, ap_mask, box_xy, cube=None):
    """Local light curves around one window: SPOC-aperture sum, 3x3 box sum,
    background (median of the 20% faintest cutout pixels), flux-weighted
    centroid of the 5x5 box, plus TESS-SPOC SAP/PDCSAP and MOM_CENTR."""
    F = S.flux if cube is None else cube
    sel = np.nonzero(role > 0)[0]
    cx, cy = int(round(box_xy[0])), int(round(box_xy[1]))
    out = {"time": S.time[sel], "role": role[sel], "dt_h": (S.time[sel] - tc) * 24.0}
    frames = F[sel]
    out["ap_sum"] = np.array([f[ap_mask].sum() for f in frames]) if ap_mask.any() else np.full(sel.size, np.nan)
    out["box3_sum"] = frames[:, cy - 1:cy + 2, cx - 1:cx + 2].sum(axis=(1, 2))
    flat = frames.reshape(sel.size, -1)
    k = max(5, int(0.2 * flat.shape[1]))
    out["bkg_med"] = np.sort(flat, axis=1)[:, :k].mean(axis=1)
    b5 = frames[:, cy - 2:cy + 3, cx - 2:cx + 3] - out["bkg_med"][:, None, None]
    yy, xx = np.mgrid[cy - 2:cy + 3, cx - 2:cx + 3]
    tot = b5.sum(axis=(1, 2))
    out["cen_x"] = (b5 * xx).sum(axis=(1, 2)) / tot
    out["cen_y"] = (b5 * yy).sum(axis=(1, 2)) / tot
    for k2 in ("SAP_FLUX", "PDCSAP_FLUX", "SAP_BKG", "MOM_CENTR1", "MOM_CENTR2"):
        if k2 in S.spoc:
            out[k2.lower()] = S.spoc[k2][sel]
    return out
