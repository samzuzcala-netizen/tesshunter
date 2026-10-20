"""PROTOCOL 7: ZTF (IRSA light-curve API, DR24 detections only) constraints on TIC 193718989 neighbours as the
eclipsing host.

* Times: ZTF 'mjd' (UTC, exposure start) + exptime/2 -> BJD_TDB at Palomar (astropy), then BTJD.
* Cleaning: catflags == 0, magerr < 0.3, one row per (expid, oid); per-oid median magnitude baseline.
* Ephemeris: the frozen FU3 linear ephemeris (results/s03_ephemeris_193718989.json, errors inflated by
  sqrt(chi2_red)); sigma_tc(n) propagated with its covariance.  Sensitivity: the packet ephemeris.
* Windows: nominal in-eclipse |dt| < T14/2; robust core |dt| < T14/2 - 3 sigma_tc(n); out-of-eclipse
  |dt| > T14 + 3 sigma_tc(n).
* Each neighbour's required eclipse fraction comes from s13 (TESS band, mission-PRF aperture shares).  The
  constraint is from DETECTIONS ONLY: an epoch at which a deep eclipse would push the star below the
  single-epoch limit is absent from the table if eclipsed, so (a) in-core detections at normal brightness
  directly exclude a deep eclipse at those epochs, and (b) the in-window detection rate is compared with the
  duty-cycle expectation from the out-of-eclipse detection rate (censoring test).  No forced photometry
  (account-gated) is used, so no stronger claim is made.
* Grid: for eclipse fraction f in [0.3, 1.0] and duration scale s in {0.8, 1.0, 1.2} x T14 and timing shifts
  within +/-3 sigma, a model is 'excluded' if >= 1 robust in-core detection has a measured flux ratio
  (vs its oid baseline) above 1 - f/2 at > 3 sigma.  The excluded fraction of the grid is reported.
Outputs: results/s14_ztf_193718989.json
"""
import glob

import pandas as pd
from astropy.coordinates import EarthLocation, SkyCoord
from astropy.time import Time
import astropy.units as u

from fu3_common import *

TIC = 193718989
ZDIR = RES / "census" / "ztf"
COORD = (267.554464, 42.109629)


def load(path, ra, dec):
    df = pd.read_csv(path)
    df = df[(df.catflags == 0) & (df.magerr < 0.3)].drop_duplicates(["expid", "oid"]).copy()
    loc = EarthLocation.of_site("Palomar")
    t = Time(df.mjd.values + df.exptime.values / 2 / 86400.0, format="mjd", scale="utc", location=loc)
    sc = SkyCoord(ra, dec, unit="deg")
    bjd = t.tdb + t.light_travel_time(sc, "barycentric")
    df["btjd"] = bjd.jd - 2457000.0
    df["dm"] = df.mag - df.groupby("oid").mag.transform("median")
    df["flux_ratio"] = 10 ** (-0.4 * df.dm)
    df["flux_err"] = df.flux_ratio * df.magerr * np.log(10) / 2.5
    return df


def main():
    eph = read(RES / f"s03_ephemeris_{TIC}.json")
    P, Tn, nref = eph["P"], eph["T_nref"], eph["nref"]
    C = np.array(eph["cov_inflated_d2"])
    T14 = read(PACKET[TIC] / "fit.json")["adopted"]["t14_hours"] / 24
    fb = read(RES / f"s13_fluxbudget_{TIC}.json")
    need = {r["id"]: r for r in fb["neighbours_ranked"]}
    gaia = {Path(p).stem.split("gaia")[1]: p for p in glob.glob(str(ZDIR / "ztf_lc_gaia*.csv"))}
    cone = read(RES / "census" / "tables" / "gaia_dr3_census.json")
    out = dict(tic=TIC, generated_utc=utc(), ephemeris=dict(P=P, T_nref=Tn, nref=nref, cov=C.tolist()), T14_d=T14,
               neighbours={}, note=__doc__)
    for gid, path in sorted(gaia.items()):
        df = load(path, *COORD)
        n = np.round((df.btjd.values - (Tn - nref * P)) / P)
        tc = Tn + (n - nref) * P
        sig = np.sqrt(C[0, 0] + 2 * (n - nref) * C[0, 1] + (n - nref) ** 2 * C[1, 1])
        dt = df.btjd.values - tc
        df["dt_h"] = dt * 24
        df["sig_tc_h"] = sig * 24
        core = np.abs(dt) < T14 / 2 - 3 * sig
        nominal = np.abs(dt) < T14 / 2
        oot = np.abs(dt) > T14 + 3 * sig
        rec = dict(n_clean=int(len(df)), bands={b: int((df.filtercode == b).sum()) for b in ("zg", "zr", "zi")},
                   mjd_range=[float(df.mjd.min()), float(df.mjd.max())],
                   median_mag={b: float(df[df.filtercode == b].mag.median()) for b in ("zg", "zr", "zi") if (df.filtercode == b).any()},
                   median_limitmag={b: float(df[df.filtercode == b].limitmag.median()) for b in ("zg", "zr", "zi") if (df.filtercode == b).any()},
                   n_nominal_in_window=int(nominal.sum()), n_core=int(core.sum()), n_oot=int(oot.sum()),
                   required_eclipse_fraction_TESS=need.get(gid, {}).get("eclipse_needed"),
                   sep_arcsec=need.get(gid, {}).get("sep_arcsec"))
        # censoring test: expected in-window detections from the out-of-eclipse rate x duty cycle
        duty = T14 / P
        rec["censoring"] = dict(duty_cycle=duty, expected_in_window_if_no_eclipse=float(len(df) * duty),
                                observed_in_window=int(nominal.sum()))
        rows = []
        for i in np.where(core)[0]:
            r = df.iloc[i]
            rows.append(dict(btjd=float(r.btjd), band=r.filtercode, mag=float(r.mag), magerr=float(r.magerr),
                             dm=float(r.dm), flux_ratio=float(r.flux_ratio), flux_err=float(r.flux_err),
                             dt_h=float(r.dt_h), sig_tc_h=float(r.sig_tc_h), limitmag=float(r.limitmag), cycle=int(n[i])))
        rec["core_detections"] = rows
        if rows:
            fr = np.array([x["flux_ratio"] for x in rows])
            fe = np.array([x["flux_err"] for x in rows])
            w = 1 / fe ** 2
            mu = float(np.sum(w * fr) / np.sum(w))
            er = float(1 / np.sqrt(np.sum(w)))
            rec["core_weighted_flux_ratio"] = dict(mean=mu, err=er, depth_upper95=float(max(0.0, 1 - mu + 1.645 * er)),
                                                   n_nights=len({int(x["btjd"]) for x in rows}))
        # model grid exclusion (robust core detections only)
        grid = []
        for f in np.round(np.arange(0.3, 1.0001, 0.05), 3):
            for s in (0.8, 1.0, 1.2):
                for shift in (-3, 0, 3):
                    dt_m = dt - shift * sig
                    incore = np.abs(dt_m) < s * T14 / 2 - 3 * sig
                    hit = incore & (df.flux_ratio.values - (1 - f / 2) > 3 * df.flux_err.values)
                    grid.append(dict(f=float(f), dur_scale=s, shift_sigma=shift, n_incore=int(incore.sum()),
                                     excluded=bool(hit.any()), n_excluding=int(hit.sum())))
        g = pd.DataFrame(grid)
        rec["grid_excluded_fraction_all"] = float(g.excluded.mean())
        rec["grid_excluded_fraction_f_ge_0p5"] = float(g[g.f >= 0.5].excluded.mean())
        req = rec["required_eclipse_fraction_TESS"]
        if req is not None and np.isfinite(req):
            sub = g[(g.f >= min(1.0, req - 0.15)) & (g.f <= min(1.0, req + 0.15))]
            rec["grid_excluded_fraction_near_required"] = float(sub.excluded.mean()) if len(sub) else None
        rec["grid"] = grid
        out["neighbours"][gid] = rec
        log("s14", f"ZTF gaia {gid}: clean {len(df)} bands {rec['bands']} sep {rec['sep_arcsec']} need {req}; window {rec['n_nominal_in_window']} "
                   f"(expected {rec['censoring']['expected_in_window_if_no_eclipse']:.1f}) core {rec['n_core']} "
                   f"core flux ratio {rec.get('core_weighted_flux_ratio')} grid excl (f>=0.5) {rec['grid_excluded_fraction_f_ge_0p5']:.2f}")
    save(RES / f"s14_ztf_{TIC}.json", out)


if __name__ == "__main__":
    main()
