"""PROTOCOL 8 (targeted, NOT part of the original survey): box searches beyond the discovery period ceiling,
and a masked-residual search for additional transiting signals.

Series: survey_detrended (the discovery's own biweight-flattened input) and the FU3 1.5-px annulus pixel series
flattened here with a wotan biweight of 1.1 d (the survey_k1 window).  BLS (astropy) with durations
0.06-0.30 d on a uniform-frequency grid:
  * long-period band: 40-100 d (TIC 262843927, 193718989), 60-130 d (TIC 270573718);
  * masked residuals: the candidate's transits (+/- 1 T14) removed, 0.5-130 d.
Peaks are listed with their power relative to the band's median absolute deviation ('SDE-like') and their
ratio to P.  Results are targeted diagnostics: they do not reproduce the survey's look-elsewhere space.
Outputs: results/s18_longp_<tic>.json
"""
import sys

from astropy.timeseries import BoxLeastSquares
from wotan import flatten

from fu3_common import *
from events import adopted
from reductions import REDUCTIONS

BANDS = {262843927: (40.0, 100.0), 193718989: (40.0, 100.0), 270573718: (60.0, 130.0)}


def series(tic, red):
    segs = REDUCTIONS[red](tic)
    t, y = [], []
    for s in segs:
        m = s["quality_ok"] & np.isfinite(s["y"])
        tt, yy = s["t"][m], 1 + s["y"][m] / 1000
        if red != "survey_detrended" and len(tt) > 50:
            yy = flatten(tt, yy, method="biweight", window_length=1.1, break_tolerance=0.5)
        ok = np.isfinite(yy)
        t.append(tt[ok])
        y.append(yy[ok])
    t, y = np.concatenate(t), np.concatenate(y)
    o = np.argsort(t)
    return t[o], y[o]


def bin30(t, y, width=30 / 1440):
    """Mean in 30-min bins within continuous segments (BLS speed; durations searched are >= 1.4 h)."""
    k = np.floor((t - t.min()) / width).astype(np.int64)
    uk, inv, cnt = np.unique(k, return_inverse=True, return_counts=True)
    tb = np.bincount(inv, weights=t) / cnt
    yb = np.bincount(inv, weights=y) / cnt
    return tb, yb


def bls(t, y, pmin, pmax, base):
    """BLS on 30-min bins over a log-period grid with dP/P = d_min / (3 * baseline)."""
    t, y = bin30(t, y)
    dy = np.full_like(y, 1.4826 * np.median(np.abs(y - np.median(y))))
    m = BoxLeastSquares(t, y, dy)
    durs = np.array([0.06, 0.09, 0.12, 0.16, 0.2, 0.25, 0.3])
    step = durs.min() / (3.0 * base)
    periods = np.exp(np.arange(np.log(pmin), np.log(pmax), step))
    freqs = 1 / periods
    res = m.power(periods, durs, objective="snr")
    p = np.asarray(res.power)
    mad_ = 1.4826 * np.median(np.abs(p - np.median(p)))
    sde = (p - np.median(p)) / max(mad_, 1e-12)
    order = np.argsort(sde)[::-1]
    peaks = []
    for i in order:
        per = 1 / freqs[i]
        if all(abs(per / q["period"] - 1) > 0.01 for q in peaks):
            peaks.append(dict(period=float(per), sde_like=float(sde[i]), depth_ppt=float(res.depth[i] * 1000),
                              duration_d=float(res.duration[i]), t0=float(res.transit_time[i]), snr=float(res.depth_snr[i])))
        if len(peaks) >= 8:
            break
    return peaks, len(freqs)


def run(tic):
    eph = adopted(tic)
    P, T0, T14 = eph["P"], eph["T0"], eph["T14"]
    out = dict(tic=tic, generated_utc=utc(), P=P, band=BANDS[tic], reductions={})
    for red in ("survey_detrended", "fu3pix_annulus_circ1p5"):
        t, y = series(tic, red)
        base = t.max() - t.min()
        lp, nf = bls(t, y, *BANDS[tic], base)
        for q in lp:
            q["ratio_to_P"] = q["period"] / P
        n = np.round((t - T0) / P)
        keep = np.abs(t - (T0 + n * P)) > T14
        rp, nf2 = bls(t[keep], y[keep], 0.5, 130.0, base)
        for q in rp:
            q["ratio_to_P"] = q["period"] / P
        out["reductions"][red] = dict(n_points=int(len(t)), baseline_d=float(base), long_band_peaks=lp, n_freq_long=nf,
                                      masked_residual_peaks=rp, n_freq_resid=nf2)
        log("s18", f"{tic} {red}: long band top {[(round(q['period'],3), round(q['sde_like'],1), round(q['ratio_to_P'],3)) for q in lp[:4]]}; "
                   f"masked residual top {[(round(q['period'],3), round(q['sde_like'],1), round(q['depth_ppt'],2)) for q in rp[:4]]}")
    save(RES / f"s18_longp_{tic}.json", out)


if __name__ == "__main__":
    for t in [int(a) for a in sys.argv[1:]] or list(TICS):
        run(t)
