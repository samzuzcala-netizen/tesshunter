"""Gaia DR3 epoch photometry (2014-2017, independent of TESS) at the predicted transit epochs.

Gaia epoch times are TCB-based BJD - 2455197.5 (Gaia DR3 data model); converted to BTJD with a TCB->TDB rate
correction (TDB - TCB ~ -L_B (JD - 2443144.5) * 86400 s, L_B = 1.550519768e-8, about -21 s at these dates).
Predicted mid-times use the FU3 frozen linear ephemeris propagated backwards with its inflated covariance (and, for
TIC 270573718, the season-offset spread as an extra +/-1 h allowance).  Reported: every epoch within the transit
window, its G-band flux relative to the median, and the transit depth the window implies.  No detection claim is
made from a handful of epochs; the point is whether any genuinely independent epoch exists.
Output: results/s20_gaia_epochs.json
"""
import pandas as pd

from fu3_common import *

DIR = RES / "census" / "gaia_epoch_photometry"
FILES = {270573718: DIR / "tic270573718_gaia4792202879700135040" / "EPOCH_PHOTOMETRY_Gaia_DR3_4792202879700135040.csv",
         193718989: DIR / "tic193718989_gaia1346023547769345792" / "EPOCH_PHOTOMETRY_Gaia_DR3_1346023547769345792.csv"}
LB = 1.550519768e-8


def load(p):
    df = pd.read_csv(p, comment="#")
    cols = {c.lower(): c for c in df.columns}
    tcol = next(c for c in df.columns if c.lower() in ("time", "g_transit_time", "obs_time"))
    fcol = next((c for c in df.columns if c.lower() in ("flux", "g_transit_flux")), None)
    bcol = next((c for c in df.columns if c.lower() in ("band",)), None)
    df["bjd_tcb"] = df[tcol] + 2455197.5
    df["bjd_tdb"] = df["bjd_tcb"] - LB * (df["bjd_tcb"] - 2443144.5003725)
    df["btjd"] = df["bjd_tdb"] - 2457000.0
    return df, fcol, bcol


def main():
    out = {}
    for tic, p in FILES.items():
        if not p.exists():
            out[str(tic)] = dict(status="NO_FILE")
            continue
        df, fcol, bcol = load(p)
        eph = read(RES / f"s03_ephemeris_{tic}.json")
        C = np.array(eph["cov_inflated_d2"])
        T14 = read(PACKET[tic] / "fit.json")["adopted"]["t14_hours"] / 24
        extra = 1.0 / 24 if tic == 270573718 else 0.0
        rows = []
        for band in sorted(df[bcol].unique()) if bcol else ["G"]:
            d = df[df[bcol] == band] if bcol else df
            d = d[np.isfinite(d[fcol])] if fcol else d
            med = np.nanmedian(d[fcol]) if fcol else np.nan
            for _, r in d.iterrows():
                n = np.round((r.btjd - eph["T_nref"]) / eph["P"]) + eph["nref"]
                tc = eph["T_nref"] + (n - eph["nref"]) * eph["P"]
                sig = float(np.sqrt(C[0, 0] + 2 * (n - eph["nref"]) * C[0, 1] + (n - eph["nref"]) ** 2 * C[1, 1])) + extra
                dt = r.btjd - tc
                if abs(dt) < T14 / 2 + 3 * sig:
                    rows.append(dict(band=band, btjd=float(r.btjd), cycle=int(n), dt_h=float(dt * 24), sigma_tc_h=sig * 24,
                                     certainly_in_transit=bool(abs(dt) < T14 / 2 - 3 * sig),
                                     flux_rel=float(r[fcol] / med) if fcol else None))
        out[str(tic)] = dict(n_epochs=int(len(df)), btjd_range=[float(df.btjd.min()), float(df.btjd.max())],
                             window_epochs=rows, n_window=len(rows),
                             n_certain=sum(r["certainly_in_transit"] for r in rows))
        log("s20", f"{tic}: {len(df)} Gaia epochs (BTJD {df.btjd.min():.1f}-{df.btjd.max():.1f}); within the +/-3 sigma window: "
                   f"{len(rows)}; certainly in transit: {out[str(tic)]['n_certain']}; "
                   + "; ".join(f"{r['band']} dt {r['dt_h']:+.1f}h (sig {r['sigma_tc_h']:.1f}h) f {r['flux_rel']}" for r in rows[:6]))
    out["262843927"] = dict(status="NO_EPOCH_PHOTOMETRY", note="Gaia DR3 has no epoch photometry for the target (only for a 54.8-arcsec AGN-class neighbour).")
    save(RES / "s20_gaia_epochs.json", out)


if __name__ == "__main__":
    main()
