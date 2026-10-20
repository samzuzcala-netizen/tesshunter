"""Common event admission / measurement / timing machinery (PROTOCOL.md sections 3-4).

A "series" is a list of segments: dict(label, sector, t, y, cad_s, quality_ok (bool array, same length),
t_all (all cadence times incl. flagged, for edge finding), extra=dict(bkg=..., quality=...)).
y is relative flux minus 1 in ppt (negative = dimmer).
"""
from __future__ import annotations

import math

import batman
import numpy as np

from fu3_common import read, PACKET

DESAT_BIT = 32          # TESS quality value 32 = reaction-wheel desaturation (momentum dump)
STRAYLIGHT_BITS = 2048 | 4096


def adopted(tic):
    f = read(PACKET[tic] / "fit.json")
    a = f["adopted"]
    return dict(P=a["period"], T0=a["t0_btjd"], T14=a["t14_hours"] / 24.0, k=a["rp_rs"], a_rs=a["a_rs"],
                b=a["b"], inc=a["inc_deg"], u=[f["limb_darkening"]["u1"], f["limb_darkening"]["u2"]],
                depth_ppt=a["depth_max_ppt"], P_err=a.get("period_err"), T0_err=a.get("t0_err"),
                stellar=f["stellar"])


class Template:
    """Unit-depth transit shape h(dt) (h(0) = 1) for the adopted geometry, integrated over an exposure."""

    def __init__(self, eph):
        self.eph = eph
        self._cache = {}

    def __call__(self, dt, exposure_d):
        key = round(exposure_d * 86400)
        pa = batman.TransitParams()
        pa.t0, pa.per, pa.rp, pa.a = 0.0, self.eph["P"], self.eph["k"], self.eph["a_rs"]
        pa.inc, pa.ecc, pa.w, pa.u, pa.limb_dark = self.eph["inc"], 0.0, 90.0, self.eph["u"], "quadratic"
        ss = max(1, int(math.ceil(exposure_d * 1440 / 2.0)))
        if key not in self._cache:
            m0 = batman.TransitModel(pa, np.array([0.0]), supersample_factor=ss, exp_time=exposure_d)
            self._cache[key] = 1.0 - m0.light_curve(pa)[0]
        d0 = self._cache[key]
        m = batman.TransitModel(pa, np.asarray(dt, float), supersample_factor=ss, exp_time=exposure_d)
        return (1.0 - m.light_curve(pa)) / d0 if d0 > 0 else np.zeros(len(dt))


def segment_edges(t_all, gap=0.5):
    t = np.sort(np.asarray(t_all, float))
    t = t[np.isfinite(t)]
    if len(t) == 0:
        return np.array([]), np.array([])
    br = np.where(np.diff(t) > gap)[0]
    starts = np.r_[t[0], t[br + 1]]
    ends = np.r_[t[br], t[-1]]
    return starts, ends


def admit(seg, tc, eph, min_bin_min=10.0):
    """Coverage-only admission. Returns (ok, reason, idx_window)."""
    T14, P = eph["T14"], eph["P"]
    half = min(max(3 * T14, 0.2), 0.4 * P)
    t, y, good = seg["t"], seg["y"], seg["quality_ok"]
    w = (np.abs(t - tc) < half) & good & np.isfinite(y) & np.isfinite(t)
    if w.sum() < 10:
        return False, "fewer than 10 good cadences in window", w, half
    step = max(seg["cad_s"] / 86400.0, min_bin_min / 1440.0)
    tin = t[w & (np.abs(t - tc) < T14 / 2)]
    frac_in = (len(tin) * seg["cad_s"] / 86400.0) / T14
    if frac_in < 0.5:
        return False, f"in-transit coverage {frac_in:.2f} < 0.5", w, half
    bins_in = len(np.unique(np.floor((tin - tc) / step)))
    tb = t[w]
    left = len(np.unique(np.floor((tb[tb < tc - 0.6 * T14] - tc) / step)))
    right = len(np.unique(np.floor((tb[tb > tc + 0.6 * T14] - tc) / step)))
    if bins_in < 3:
        return False, f"{bins_in} in-transit bins < 3", w, half
    if left < 4 or right < 4:
        return False, f"baseline bins left {left} right {right} < 4", w, half
    return True, "ok", w, half


def _design(dt, h, half, deg):
    cols = [np.ones_like(dt)]
    if deg >= 1:
        cols.append(dt / half)
    if deg >= 2:
        cols.append((dt / half) ** 2)
    cols.append(-h)
    return np.column_stack(cols)


def _solve(X, y):
    sol, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ sol
    return sol, r


def beta_factor(dt, r, sigma, T14):
    """Time-averaging red-noise factor at the T14/3 scale (>= 1)."""
    width = T14 / 3.0
    g = np.floor((dt - dt.min()) / width).astype(int)
    means, ns = [], []
    for v in np.unique(g):
        m = g == v
        if m.sum() >= 2:
            means.append(r[m].mean())
            ns.append(m.sum())
    if len(means) < 4 or sigma <= 0:
        return 1.0
    expect = sigma / np.sqrt(np.mean(ns))
    return float(max(1.0, np.std(means, ddof=1) / expect))


def measure(seg, tc_ref, eph, tmpl: Template, deg=1, grid_half=None, step_min=2.0, use_profile=True):
    """Signed depth at the reference time, plus a profile-likelihood timing measurement."""
    ok, reason, w, half = admit(seg, tc_ref, eph)
    rec = dict(label=seg["label"], sector=seg["sector"], tc_ref=tc_ref, admitted=bool(ok), reason=reason,
               cad_s=seg["cad_s"])
    if not ok:
        return rec
    t, y = seg["t"][w], seg["y"][w]
    dt = t - tc_ref
    exp_d = seg["cad_s"] / 86400.0
    T14 = eph["T14"]
    h0 = tmpl(dt, exp_d)
    X = _design(dt, h0, half, deg)
    sol, r = _solve(X, y)
    oot = np.abs(dt) > 0.6 * T14
    sigma = float(1.4826 * np.median(np.abs(r[oot] - np.median(r[oot])))) if oot.sum() > 5 else float(np.std(r))
    sigma = max(sigma, 1e-6)
    beta = beta_factor(dt, r, sigma, T14)
    se = sigma * beta
    cov = np.linalg.pinv(X.T @ X) * se ** 2
    depth, derr = float(sol[-1]), float(np.sqrt(cov[-1, -1]))
    rec.update(depth_ppt=depth, depth_err_ppt=derr, sigma_white_ppt=sigma, beta=beta, n_points=int(w.sum()),
               n_in=int((np.abs(dt) < T14 / 2).sum()), chi2_ref=float(np.sum((r / se) ** 2)),
               baseline_deg=deg, window_half_d=half)
    if not use_profile:
        return rec
    gh = grid_half if grid_half is not None else T14
    offs = np.arange(-gh, gh + 1e-9, step_min / 1440.0)
    chi = np.empty(len(offs))
    amp = np.empty(len(offs))
    for i, o in enumerate(offs):
        h = tmpl(dt - o, exp_d)
        Xo = _design(dt, h, half, deg)
        so, ro = _solve(Xo, y)
        chi[i] = np.sum((ro / se) ** 2)
        amp[i] = so[-1]
    # only consider dimming solutions for timing
    chi_pos = np.where(amp > 0, chi, np.inf)
    if not np.isfinite(chi_pos).any():
        rec.update(timing_status="no_dimming_solution")
        return rec
    i0 = int(np.argmin(chi_pos))
    cmin = chi_pos[i0]
    inside = chi_pos <= cmin + 1.0
    idx = np.where(inside)[0]
    lo, hi = offs[idx.min()], offs[idx.max()]
    # contiguity / multimodality
    contiguous = (idx.max() - idx.min() + 1) == len(idx)
    edge = i0 in (0, len(offs) - 1) or idx.min() == 0 or idx.max() == len(offs) - 1
    # second minimum check: local minima within delta chi2 < 1 separated by > T14/4
    locmin = [j for j in range(1, len(offs) - 1) if chi_pos[j] <= chi_pos[j - 1] and chi_pos[j] <= chi_pos[j + 1]
              and chi_pos[j] < cmin + 1.0 and abs(offs[j] - offs[i0]) > T14 / 4]
    # parabolic refinement of the minimum
    if 0 < i0 < len(offs) - 1 and np.isfinite(chi_pos[i0 - 1]) and np.isfinite(chi_pos[i0 + 1]):
        c1, c0, c2 = chi_pos[i0 - 1], chi_pos[i0], chi_pos[i0 + 1]
        den = c1 - 2 * c0 + c2
        o_best = offs[i0] + (0.5 * (c1 - c2) / den * (offs[1] - offs[0]) if den > 0 else 0.0)
    else:
        o_best = offs[i0]
    status = "ok"
    if edge:
        status = "edge_truncated"
    elif not contiguous or locmin:
        status = "multimodal"
    snr_best = amp[i0] / derr if derr > 0 else 0.0
    if snr_best < 2:
        status = status + "|weak" if status != "ok" else "weak"
    rec.update(tc_fit=tc_ref + o_best, oc_d=o_best, oc_lo_d=lo, oc_hi_d=hi,
               oc_err_d=max(o_best - lo, hi - o_best, (offs[1] - offs[0]) / 2), oc_err_sym_d=(hi - lo) / 2,
               depth_at_best_ppt=float(amp[i0]), delta_chi2_ref_minus_best=float(chi[np.argmin(np.abs(offs))] - cmin),
               timing_status=status, n_secondary_minima=len(locmin))
    return rec


def context(seg, tc, eph, quality_raw=None):
    """Systematics context of an event: edges, momentum dumps, scattered-light flags, background."""
    starts, ends = segment_edges(seg["t_all"])
    dist = float(np.min(np.abs(np.r_[starts, ends] - tc))) if len(starts) else np.nan
    T14 = eph["T14"]
    out = dict(edge_distance_d=dist)
    q = seg.get("quality_all")
    ta = seg["t_all"]
    if q is not None:
        win = np.abs(ta - tc) < T14
        out["desat_within_T14"] = bool(np.any((q[win] & DESAT_BIT) > 0))
        out["straylight_frac_within_T14"] = float(np.mean((q[win] & STRAYLIGHT_BITS) > 0)) if win.any() else np.nan
        out["flagged_frac_in_transit"] = float(np.mean(q[np.abs(ta - tc) < T14 / 2] != 0)) if np.any(np.abs(ta - tc) < T14 / 2) else np.nan
    bkg = seg.get("bkg_all")
    if bkg is not None and np.isfinite(bkg).any():
        win = np.abs(ta - tc) < T14 / 2
        med = np.nanmedian(bkg)
        out["bkg_in_over_sector_median"] = float(np.nanmedian(bkg[win]) / med) if win.any() and med != 0 else np.nan
    return out


def pool(recs, key="depth_ppt", ekey="depth_err_ppt"):
    r = [x for x in recs if x.get("admitted") and x.get(key) is not None and np.isfinite(x.get(key, np.nan))]
    if not r:
        return dict(n=0)
    d = np.array([x[key] for x in r])
    e = np.array([x[ekey] for x in r])
    w = 1 / e ** 2
    mu = float((w * d).sum() / w.sum())
    chi2 = float((w * (d - mu) ** 2).sum())
    dof = max(len(r) - 1, 1)
    infl = max(1.0, math.sqrt(chi2 / dof))
    err = infl / math.sqrt(w.sum())
    from scipy.stats import chi2 as C
    snr2 = (d / e) ** 2
    return dict(n=len(r), depth_ppt=mu, err_ppt=err, snr=mu / err, err_white_ppt=1 / math.sqrt(w.sum()),
                chi2_const=chi2, dof=dof, p_const=float(C.sf(chi2, dof)), n_positive=int((d > 0).sum()),
                top_share_snr2=float(snr2.max() / snr2.sum()) if snr2.sum() > 0 else np.nan)
