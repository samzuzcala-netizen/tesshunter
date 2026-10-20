"""Over-luminosity for colour (photometric binarity), added 2026-10-19 at the user's request (amendment A4).

An unresolved companion of similar brightness lifts a star above the single-star main sequence at its colour
(equal-mass pair: 0.75 mag).  Each target is placed on empirical colour-magnitude diagrams built from the Gaia DR3
solar neighbourhood (parallax > 10 mas, parallax/error > 20, 1.6 <= BP-RP <= 2.6), with 2MASS Ks (quality A)
through the Gaia DR3 best-neighbour cross-match:  M_G vs BP-RP, M_G vs G-RP, M_Ks vs BP-RP, M_Ks vs G-Ks.
Quality cut on every comparison star: corrected BP/RP flux excess |C*| < 3 sigma_C*(G) (Riello et al. 2021).
The single-star ridge is the KDE mode of absolute magnitude in 0.04-mag colour bins of a clean subsample
(RUWE < 1.2, non_single_star = 0, ipd_frac_multi_peak = 0), 3-bin running median, linearly interpolated, fitted
only inside each diagram's interior colour range (the BP-RP selection cuts G-RP and G-Ks obliquely near the
edges).  For each target: dM = M - ridge (negative = over-luminous), the fraction of neighbourhood stars (all,
and clean) within +/-0.05 mag of its colour with dM at least as negative, and the clean sample's dM quantiles there.
Extinction is neglected (d ~ 85 pc).  Metallicity spreads the single-star sequence; the clean sample's 16-84 %
range measures that spread empirically.
Outputs: results/s22_cmd.json, tables/cmd_luminosity.csv, figures/F10_cmd_luminosity.png
"""
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import median_filter
from scipy.stats import gaussian_kde

from fu3_common import *

SRC = {270573718: 4792202879700135040, 262843927: 4673750877131752832, 193718989: 1346023547769345792}
CACHEF = CACHE / "cmd" / "gaia100pc_early_m_sliced.ecsv"
CACHEF.parent.mkdir(parents=True, exist_ok=True)
COLS = ("g.source_id, g.parallax, g.parallax_over_error, g.phot_g_mean_mag, g.phot_bp_mean_mag, g.phot_rp_mean_mag, g.bp_rp, "
        "g.g_rp, g.ruwe, g.non_single_star, g.ipd_frac_multi_peak, g.astrometric_excess_noise_sig, g.phot_bp_rp_excess_factor")
# 2MASS through the documented DR3 best-neighbour path (an outer join times out on the ESA server; the inner join does not)
KS_JOIN = ("SELECT g.source_id, tm.ks_m, tm.ks_msigcom, tm.ph_qual FROM gaiadr3.gaia_source AS g "
           "INNER JOIN gaiadr3.tmass_psc_xsc_best_neighbour AS xm USING (source_id) "
           "INNER JOIN gaiadr3.tmass_psc_xsc_join AS xj USING (clean_tmass_psc_xsc_oid) "
           "INNER JOIN gaiadr1.tmass_original_valid AS tm ON xj.original_psc_source_id = tm.designation ")
BASE = "g.parallax > 10 AND g.parallax_over_error > 20 AND g.phot_bp_mean_mag IS NOT NULL AND g.phot_rp_mean_mag IS NOT NULL"
SLICES = [(1.6, 1.8), (1.8, 2.0), (2.0, 2.2), (2.2, 2.4), (2.4, 2.6001)]
CAP = 50000                         # the ESA server returned exactly 50,000 rows for an 81,447-row query; slices stay below it


def fetch():
    from astropy.table import join, unique, vstack
    from astropy.table import Table
    if CACHEF.exists():
        return Table.read(CACHEF)
    from astroquery.gaia import Gaia
    Gaia.ROW_LIMIT = -1
    ids = ",".join(str(v) for v in SRC.values())
    parts, kparts, counts = [], [], []
    for lo, hi in SLICES:
        w = f"WHERE {BASE} AND g.bp_rp >= {lo} AND g.bp_rp < {hi}"
        a = Gaia.launch_job_async(f"SELECT {COLS} FROM gaiadr3.gaia_source AS g {w}").get_results()
        b = Gaia.launch_job_async(KS_JOIN + w).get_results()
        if len(a) >= CAP or len(b) >= CAP:
            raise RuntimeError(f"slice {lo}-{hi} hit the row cap ({len(a)}, {len(b)})")
        parts.append(a)
        kparts.append(b)
        counts.append(dict(slice=[lo, hi], n_gaia=len(a), n_ks=len(b)))
    parts.append(Gaia.launch_job_async(f"SELECT {COLS} FROM gaiadr3.gaia_source AS g WHERE g.source_id IN ({ids})").get_results())
    kparts.append(Gaia.launch_job_async(KS_JOIN + f"WHERE g.source_id IN ({ids})").get_results())
    t = unique(vstack(parts), keys="source_id")
    k = unique(vstack(kparts), keys="source_id")
    t = join(t, k, keys="source_id", join_type="left")
    t.meta = dict(where=BASE, slices=counts, ks_join=KS_JOIN, retrieved_utc=utc(), n_rows=len(t))
    t.write(CACHEF, overwrite=True)
    return t


def cstar_ok(C, bprp, G, nsig=3.0):
    """Riello et al. (2021) corrected flux excess C* and its 1-sigma scatter; valid for 0.5 <= BP-RP < 4."""
    cs = C - (1.154360 + 0.033772 * bprp + 0.032277 * bprp ** 2)
    sig = 0.0059898 + 8.817481e-12 * G ** 7.618399
    return np.abs(cs) < nsig * sig, cs / sig


def ridge_fit(c, M, lo, hi, step=0.04):
    xs, ys = [], []
    for a in np.arange(lo, hi - step / 2, step):
        m = (c >= a) & (c < a + step) & np.isfinite(M)
        if m.sum() < 40:
            continue
        kde = gaussian_kde(M[m])
        grid = np.linspace(np.percentile(M[m], 1), np.percentile(M[m], 99), 800)
        xs.append(a + step / 2)
        ys.append(grid[np.argmax(kde(grid))])
    xs, ys = np.array(xs), median_filter(np.array(ys), size=3, mode="nearest")
    return (lambda x: np.interp(x, xs, ys, left=np.nan, right=np.nan)), xs, ys


def main():
    t = fetch()
    plx = np.asarray(t["parallax"], float)
    dm = 5 * np.log10(plx) - 10
    G, BP, RP = (np.asarray(t[k], float) for k in ("phot_g_mean_mag", "phot_bp_mean_mag", "phot_rp_mean_mag"))
    ks = np.asarray(np.ma.filled(t["ks_m"].astype(float), np.nan))
    q = np.asarray(np.ma.filled(t["ph_qual"].astype(str), ""))
    ks = np.where(np.array([len(s) == 3 and s[2] == "A" for s in q]) & np.isfinite(ks), ks, np.nan)
    ruwe = np.asarray(t["ruwe"], float)
    nss = np.asarray(np.ma.filled(t["non_single_star"], 0), int)
    ipd = np.asarray(np.ma.filled(t["ipd_frac_multi_peak"], 0), float)
    sid = np.asarray(t["source_id"], np.int64)
    cok, csig = cstar_ok(np.asarray(t["phot_bp_rp_excess_factor"], float), BP - RP, G)
    is_tgt = np.isin(sid, list(SRC.values()))
    pool_ = ~is_tgt & cok
    clean = pool_ & (ruwe < 1.2) & (nss == 0) & (ipd == 0)
    diagrams = {"MG_vs_BPRP": (BP - RP, G + dm, (1.62, 2.58)), "MG_vs_GRP": (G - RP, G + dm, (0.94, 1.14)),
                "MKs_vs_BPRP": (BP - RP, ks + dm, (1.62, 2.58)), "MKs_vs_GKs": (G - ks, ks + dm, (2.9, 3.45))}
    out = dict(generated_utc=utc(), n_rows=int(len(t)), n_pass_cstar=int(pool_.sum()), n_clean=int(clean.sum()),
               n_with_ks=int(np.isfinite(ks).sum()), fetch_meta=dict(t.meta), diagrams={}, targets={})
    for tic, s in SRC.items():
        i = np.where(sid == s)[0][0]
        out["targets"][str(tic)] = dict(source_id=int(s), ruwe=float(ruwe[i]), non_single_star=int(nss[i]), ipd_frac_multi_peak=float(ipd[i]),
                                        aen_sig=float(t["astrometric_excess_noise_sig"][i]), cstar_sigma=float(csig[i]), cstar_ok=bool(cok[i]))
    rows = []
    for name, (c, M, (lo, hi)) in diagrams.items():
        ok = np.isfinite(c) & np.isfinite(M)
        ridge, bx, by = ridge_fit(c[clean & ok], M[clean & ok], lo, hi)
        out["diagrams"][name] = dict(fit_range=[lo, hi], bin_centres=bx.tolist(), bin_modes=by.tolist(), n_clean=int((clean & ok).sum()))
        for tic, s in SRC.items():
            i = np.where(sid == s)[0][0]
            if not ok[i]:
                out["targets"][str(tic)][name] = dict(status="NO_DATA")
                continue
            d_t = float(M[i] - ridge(c[i]))
            win = ok & (np.abs(c - c[i]) < 0.05)
            d_all = M[win & pool_] - ridge(c[win & pool_])
            d_cl = M[win & clean] - ridge(c[win & clean])
            d_all, d_cl = d_all[np.isfinite(d_all)], d_cl[np.isfinite(d_cl)]
            r = dict(colour=float(c[i]), abs_mag=float(M[i]), ridge=float(ridge(c[i])), dM=d_t, n_window=int(len(d_all)), n_window_clean=int(len(d_cl)),
                     frac_all_as_bright=float(np.mean(d_all <= d_t)), frac_clean_as_bright=float(np.mean(d_cl <= d_t)),
                     clean_quantiles={str(p): float(np.percentile(d_cl, p)) for p in (5, 16, 50, 84, 95)},
                     frac_all_dM_lt_m0p5=float(np.mean(d_all < -0.5)),
                     frac_clean_faint_enough_for_twin=float(np.mean(d_cl >= d_t + 0.753)),
                     implied_companion_dmag=(float(-2.5 * np.log10(10 ** (-0.4 * d_t) - 1)) if d_t < 0 else None))
            out["targets"][str(tic)][name] = r
            rows.append(dict(tic=tic, diagram=name, colour=round(r["colour"], 4), abs_mag=round(r["abs_mag"], 3), ridge=round(r["ridge"], 3),
                             dM=round(d_t, 3), pct_all_as_bright=round(100 * r["frac_all_as_bright"], 1),
                             pct_clean_as_bright=round(100 * r["frac_clean_as_bright"], 1), n_window=r["n_window"],
                             clean_p5=round(r["clean_quantiles"]["5"], 3), clean_p16=round(r["clean_quantiles"]["16"], 3),
                             clean_p50=round(r["clean_quantiles"]["50"], 3), clean_p84=round(r["clean_quantiles"]["84"], 3)))
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), layout="constrained")
    for ax, name, xl, yl in ((axes[0], "MG_vs_BPRP", "BP - RP", "M_G"), (axes[1], "MKs_vs_BPRP", "BP - RP", "M_Ks")):
        c, M, (lo, hi) = diagrams[name]
        m = np.isfinite(c) & np.isfinite(M) & pool_
        ax.scatter(c[m], M[m], s=1, c="#9aa7b5", alpha=0.3, rasterized=True, label=f"Gaia DR3, d < 100 pc ({m.sum():,})")
        bx, by = np.array(out["diagrams"][name]["bin_centres"]), np.array(out["diagrams"][name]["bin_modes"])
        ax.plot(bx, by, color="#0e6a74", lw=1.8, label="single-star ridge (mode, clean subsample)")
        ax.plot(bx, by - 0.753, color="#a63737", lw=1.2, ls="--", label="equal-mass pair (ridge - 0.75 mag)")
        for (tic, s), mk in zip(SRC.items(), ("o", "s", "D")):
            i = np.where(sid == s)[0][0]
            ax.plot(c[i], M[i], mk, ms=8, mfc="#f2b134", mec="black", label=f"TIC {tic}")
        ax.set_xlim(1.85, 2.35)
        sel = m & (c > 1.85) & (c < 2.35)
        ylim = np.nanpercentile(M[sel], [0.5, 99.5])
        ax.set_ylim(ylim[1] + 0.2, ylim[0] - 0.4)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.legend(fontsize=7, loc="lower left")
    fig.savefig(FIG / "F10_cmd_luminosity.png", dpi=150)
    plt.close(fig)
    save(RES / "s22_cmd.json", out)
    with open(ROOT / "tables" / "cmd_luminosity.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log("s22", f"rows {out['n_rows']}, C* ok {out['n_pass_cstar']}, clean {out['n_clean']}, Ks {out['n_with_ks']}; slices {t.meta.get('slices')}")
    for tic, v in out["targets"].items():
        log("s22", f"{tic}: RUWE {v['ruwe']:.2f} AEN sig {v['aen_sig']:.1f} C* {v['cstar_sigma']:+.1f} sigma")
    for r in rows:
        log("s22", f"{r['tic']} {r['diagram']}: colour {r['colour']} M {r['abs_mag']} ridge {r['ridge']} dM {r['dM']:+.3f}; as bright: "
                   f"{r['pct_all_as_bright']}% all / {r['pct_clean_as_bright']}% clean of {r['n_window']}; clean p5/16/50/84 "
                   f"{r['clean_p5']:+.2f}/{r['clean_p16']:+.2f}/{r['clean_p50']:+.2f}/{r['clean_p84']:+.2f}")


if __name__ == "__main__":
    main()
