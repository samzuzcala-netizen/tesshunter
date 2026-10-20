"""Per-event signed depths and profile-likelihood mid-times in every D-orig/D-alt reduction (PROTOCOL 3-4),
for all three targets, plus the O-C analysis on each reduction.

Outputs: results/s02_events_<tic>.json (event x reduction table + pooled stats + O-C fits),
results/s02_events_<tic>.csv
"""
import csv
import sys

from fu3_common import *
from events import adopted, Template, measure, context, pool
from reductions import REDUCTIONS


def predicted_events(eph, segs):
    tmin = min(np.nanmin(s["t"]) for s in segs)
    tmax = max(np.nanmax(s["t"]) for s in segs)
    n0 = int(np.ceil((tmin - eph["T0"]) / eph["P"]))
    n1 = int(np.floor((tmax - eph["T0"]) / eph["P"]))
    return [(n, eph["T0"] + n * eph["P"]) for n in range(n0, n1 + 1)]


def oc_fit(times, errs, cycles, nref=None):
    """Weighted linear ephemeris fit to measured times. Returns T_ref, P, covariance, chi2 and inflation."""
    n = np.asarray(cycles, float)
    t = np.asarray(times, float)
    e = np.asarray(errs, float)
    if nref is None:
        nref = float(np.round(np.average(n, weights=1 / e ** 2)))
    X = np.column_stack([np.ones_like(n), n - nref])
    W = np.diag(1 / e ** 2)
    cov = np.linalg.inv(X.T @ W @ X)
    sol = cov @ X.T @ W @ t
    r = t - X @ sol
    chi2 = float(np.sum((r / e) ** 2))
    dof = max(len(t) - 2, 1)
    infl = max(1.0, np.sqrt(chi2 / dof))
    return dict(nref=nref, T_ref=float(sol[0]), P=float(sol[1]), cov=(cov * infl ** 2).tolist(),
                cov_uninflated=cov.tolist(), chi2=chi2, dof=dof, inflation=float(infl),
                residuals_min=(r * 1440).tolist())


def oc_models(rows):
    """Linear vs quadratic vs per-season-offset models of O-C (times in days)."""
    n = np.array([r["cycle"] for r in rows], float)
    oc = np.array([r["oc_d"] for r in rows], float)
    e = np.array([r["oc_err_d"] for r in rows], float)
    w = 1 / e ** 2
    out = {}

    def wls(X):
        W = np.diag(w)
        cov = np.linalg.pinv(X.T @ W @ X)
        sol = cov @ X.T @ W @ oc
        r = oc - X @ sol
        return sol, float(np.sum(w * r ** 2)), cov

    nc = n - np.average(n, weights=w)
    X0 = np.column_stack([np.ones_like(nc)])
    X1 = np.column_stack([np.ones_like(nc), nc])
    X2 = np.column_stack([np.ones_like(nc), nc, nc ** 2])
    for name, X in (("constant", X0), ("linear", X1), ("quadratic", X2)):
        sol, chi2, cov = wls(X)
        out[name] = dict(params=sol.tolist(), chi2=chi2, k=X.shape[1], n=len(oc),
                         p_value=float(__import__("scipy.stats", fromlist=["chi2"]).chi2.sf(chi2, max(len(oc) - X.shape[1], 1))))
    out["delta_chi2_quadratic_vs_linear"] = out["linear"]["chi2"] - out["quadratic"]["chi2"]
    # leave-one-sector-out on the quadratic improvement
    loo = []
    for s in sorted(set(r["sector"] for r in rows)):
        keep = np.array([r["sector"] != s for r in rows])
        if keep.sum() < 5:
            continue
        nn, oo, ww = nc[keep], oc[keep], w[keep]
        res = []
        for X in (np.column_stack([np.ones_like(nn), nn]), np.column_stack([np.ones_like(nn), nn, nn ** 2])):
            W = np.diag(ww)
            cov = np.linalg.pinv(X.T @ W @ X)
            sol = cov @ X.T @ W @ oo
            res.append(float(np.sum(ww * (oo - X @ sol) ** 2)))
        loo.append(dict(omitted_sector=s, delta_chi2_quad_vs_lin=res[0] - res[1]))
    out["loo_quadratic"] = loo
    return out


def run(tic):
    eph = adopted(tic)
    tmpl = Template(eph)
    table = []
    summary = {}
    for name, loader in REDUCTIONS.items():
        try:
            segs = loader(tic)
        except Exception as exc:   # noqa: BLE001
            summary[name] = dict(status="LOAD_FAILED", error=repr(exc))
            continue
        if not segs:
            summary[name] = dict(status="NO_DATA")
            continue
        recs = []
        for seg in segs:
            for n, tc in predicted_events(eph, [seg]):
                r = measure(seg, tc, eph, tmpl, deg=1)
                r.update(cycle=n, reduction=name)
                if r["admitted"]:
                    r2 = measure(seg, tc, eph, tmpl, deg=2, use_profile=False)
                    r["depth_deg2_ppt"] = r2.get("depth_ppt")
                    r["depth_deg2_err_ppt"] = r2.get("depth_err_ppt")
                    r.update(context(seg, tc, eph))
                recs.append(r)
        adm = [r for r in recs if r["admitted"]]
        timed = [r for r in adm if r.get("timing_status") in ("ok", "multimodal") and r.get("oc_err_d")]
        oc = None
        if len(timed) >= 4:
            lin = oc_fit([r["tc_fit"] for r in timed], [r["oc_err_d"] for r in timed], [r["cycle"] for r in timed])
            oc = dict(linear_ephemeris=lin, models=oc_models(timed), n_timed=len(timed),
                      excluded_from_timing=[(r["sector"], r["cycle"], r.get("timing_status")) for r in adm if r not in timed])
        summary[name] = dict(status="OK", n_predicted=len(recs), n_admitted=len(adm), pooled=pool(adm),
                             pooled_deg2=pool(adm, "depth_deg2_ppt", "depth_deg2_err_ppt"),
                             sectors=sorted(set(r["sector"] for r in adm)), oc=oc,
                             rejected=[(r["sector"], r["cycle"], r["reason"]) for r in recs if not r["admitted"]])
        table.extend(recs)
        log("s02", f"{tic} {name}: admitted {len(adm)}/{len(recs)} pooled {summary[name]['pooled'].get('depth_ppt', float('nan')):.3f}"
                   f" +- {summary[name]['pooled'].get('err_ppt', float('nan')):.3f} timed {len(timed)}")
    out = dict(tic=tic, ephemeris=eph, generated_utc=utc(), summary=summary, events=table)
    save(RES / f"s02_events_{tic}.json", out)
    keys = ["reduction", "sector", "cycle", "tc_ref", "admitted", "reason", "cad_s", "depth_ppt", "depth_err_ppt",
            "depth_deg2_ppt", "depth_deg2_err_ppt", "beta", "sigma_white_ppt", "n_in", "oc_d", "oc_err_d",
            "oc_lo_d", "oc_hi_d", "timing_status", "depth_at_best_ppt", "edge_distance_d", "desat_within_T14",
            "straylight_frac_within_T14", "flagged_frac_in_transit", "bkg_in_over_sector_median"]
    with open(RES / f"s02_events_{tic}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in table:
            w.writerow({k: r.get(k) for k in keys})
    return out


if __name__ == "__main__":
    tics = [int(a) for a in sys.argv[1:]] or list(TICS)
    for t in tics:
        run(t)
