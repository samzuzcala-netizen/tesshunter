"""Independent recurrence check for TIC 9066956 (Claude vetting, 2026-10-06).

Reads the archival FITS directly; does not reuse any earlier arrays.
Detrending: wotan biweight 0.5 d. Model: box of fixed duration integrated over
each cadence's exposure. Null: same estimator at random phase offsets.
"""
import json, sys, glob
import numpy as np
from astropy.io import fits
from wotan import flatten

EARLY = r"C:/Users/seanj/Documents/Codex/2026-10-05/can-you-look-at-all-the/new_data/earlier/tic9066956_p01/mast_cache/mastDownload/HLSP"
LATE = r"D:/tesshunter_surveys/20261005_survey2000/supplement/p12/lightkurve/acquisition/tic9066956/attempt1/mastDownload/HLSP"

# Ephemeris derived by the survey from sectors 69/70/92 only (prospective for 2/29/42)
P_SURV, T0_SURV = 0.7134493373386843, 3182.824017282312
# Six-sector refined ephemeris (class906)
P_REF, T0_REF = 0.7134476511671136, 3182.8243522568264
DUR = 0.723 / 24.0


def load(path, kind):
    with fits.open(path) as h:
        d = h[1].data
        hd = h[1].header
        sector = h[0].header.get("SECTOR")
        t = np.array(d["TIME"], float)
        if kind == "spoc":
            f = np.array(d["PDCSAP_FLUX"], float)
        else:
            f = np.array(d["KSPSAP_FLUX"] if "KSPSAP_FLUX" in d.names else d["SAP_FLUX"], float)
        q = np.array(d["QUALITY"], int)
        exp = float(hd.get("TIMEDEL", np.nanmedian(np.diff(t))))
    m = np.isfinite(t) & np.isfinite(f) & (q == 0)
    t, f = t[m], f[m] / np.nanmedian(f[m])
    trend = flatten(t, f, method="biweight", window_length=0.5, return_trend=True)[1]
    r = f / trend - 1.0
    ok = np.isfinite(r)
    t, r = t[ok], r[ok]
    s = 1.4826 * np.median(np.abs(r - np.median(r)))
    keep = (r < 4 * s) & (r > -6 * s)
    return dict(sector=sector, kind=kind, t=t[keep], r=r[keep], exp=exp, sig=s,
                n_clip=int((~keep).sum()))


def overlap(t, exp, P, T0, dur, phase0=0.0):
    """Fraction of each exposure inside the box."""
    ph = ((t - T0) / P - phase0 + 0.5) % 1.0 - 0.5
    dt = ph * P
    lo = np.maximum(dt - exp / 2, -dur / 2)
    hi = np.minimum(dt + exp / 2, dur / 2)
    return np.clip(hi - lo, 0, None) / exp


def depth(lc, P, T0, phase0=0.0, parity=None):
    w = overlap(lc["t"], lc["exp"], P, T0, DUR, phase0)
    if parity is not None:
        cyc = np.round((lc["t"] - T0) / P - phase0).astype(int)
        w = np.where(cyc % 2 == parity, w, 0.0)
    sel = w > 0
    if sel.sum() < 3:
        return np.nan, np.nan
    sig = lc["sig"]
    # weighted LSQ for r = -d * w (baseline already ~0 after detrending)
    d = -np.sum(w * lc["r"]) / np.sum(w * w)
    e = sig / np.sqrt(np.sum(w * w))
    return d * 1e3, e * 1e3


def nulls(lc, P, T0, n=300, seed=1):
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        ph = rng.uniform(0.08, 0.92)
        if abs(ph - 0.5) < 0.06:
            continue
        out.append(depth(lc, P, T0, ph)[0])
    return np.array(out)


def main():
    lcs = []
    for p in sorted(glob.glob(EARLY + "/*/*.fits")):
        lcs.append(load(p, "spoc"))
    for p in sorted(glob.glob(LATE + "/*/*.fits")):
        lcs.append(load(p, "qlp" if "qlp" in p else "spoc"))
    res = []
    for lc in lcs:
        for tag, P, T0 in (("survey_eph", P_SURV, T0_SURV), ("refined_eph", P_REF, T0_REF)):
            d, e = depth(lc, P, T0)
            nl = nulls(lc, P, T0)
            nstd = 1.4826 * np.median(np.abs(nl - np.median(nl)))
            do, eo = depth(lc, P, T0, parity=1)
            de, ee = depth(lc, P, T0, parity=0)
            sd, se = depth(lc, P, T0, 0.5)
            res.append(dict(sector=lc["sector"], prod=lc["kind"], eph=tag,
                            exp_s=round(lc["exp"] * 86400), npts=len(lc["t"]),
                            clip=lc["n_clip"], sig_ppt=round(lc["sig"] * 1e3, 2),
                            depth=round(d, 3), err=round(e, 3), null_std=round(nstd, 3),
                            null_med=round(float(np.median(nl)), 3),
                            snr_formal=round(d / e, 2), snr_null=round((d - np.median(nl)) / nstd, 2),
                            frac_null_ge=float(np.mean(nl >= d)),
                            odd=round(do, 2), odd_e=round(eo, 2), even=round(de, 2), even_e=round(ee, 2),
                            sec=round(sd, 2), sec_e=round(se, 2)))
    json.dump(res, open(sys.argv[1], "w"), indent=1)
    for r in res:
        print(r)


if __name__ == "__main__":
    main()
