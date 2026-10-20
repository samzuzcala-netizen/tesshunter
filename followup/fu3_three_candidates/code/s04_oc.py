"""PROTOCOL 4 + A1.3: O-C analysis with formal and injection-calibrated timing errors, per reduction, plus
per-season joint shift fits and the frozen reference ephemeris/covariance for new-epoch predictions.

Outputs: results/s04_oc_<tic>.json, figures/oc_<tic>.png, results/s03_ephemeris_<tic>.json (frozen
prediction ephemeris from D-orig products, PROTOCOL 1)
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import chi2 as CHI2

from fu3_common import *
from events import adopted, Template, measure
from reductions import REDUCTIONS

SEASON_GAP_CYCLES = 6       # events closer than this many cycles belong to the same observing season


def seasons(cycles):
    cs = sorted(set(cycles))
    groups, cur = [], [cs[0]]
    for c in cs[1:]:
        if c - cur[-1] <= SEASON_GAP_CYCLES:
            cur.append(c)
        else:
            groups.append(cur)
            cur = [c]
    groups.append(cur)
    return {c: i for i, g in enumerate(groups) for c in g}, groups


def wls(X, y, w):
    W = w[:, None]
    cov = np.linalg.pinv(X.T @ (W * X))
    sol = cov @ (X.T @ (w * y))
    r = y - X @ sol
    return sol, float(np.sum(w * r * r)), cov


def oc_stats(rows, err_key):
    n = np.array([r["cycle"] for r in rows], float)
    y = np.array([r["oc_d"] for r in rows]) * 1440.0
    e = np.array([r[err_key] for r in rows]) * 1440.0
    w = 1 / e ** 2
    nc = n - np.average(n, weights=w)
    smap, groups = seasons(n.astype(int).tolist())
    S = np.zeros((len(n), len(groups)))
    for i, c in enumerate(n.astype(int)):
        S[i, smap[c]] = 1
    models = {"linear": np.column_stack([np.ones_like(nc), nc]),
              "quadratic": np.column_stack([np.ones_like(nc), nc, nc ** 2]),
              "season_offsets": S}
    out = {}
    for k, X in models.items():
        sol, c2, cov = wls(X, y, w)
        dof = len(y) - X.shape[1]
        out[k] = dict(chi2=c2, dof=dof, p=float(CHI2.sf(c2, max(dof, 1))), params=sol.tolist(),
                      param_err=np.sqrt(np.diag(cov)).tolist())
    out["season_groups_cycles"] = groups
    out["delta_chi2_quadratic_vs_linear"] = out["linear"]["chi2"] - out["quadratic"]["chi2"]
    out["delta_chi2_seasons_vs_linear"] = out["linear"]["chi2"] - out["season_offsets"]["chi2"]
    out["season_minus_linear_extra_params"] = len(groups) - 2
    # leave-one-sector-out of the linear chi2 and of the season improvement
    loo = []
    for s in sorted(set(r["sector"] for r in rows)):
        keep = np.array([r["sector"] != s for r in rows])
        if keep.sum() < 5:
            continue
        sol, c2l, _ = wls(models["linear"][keep], y[keep], w[keep])
        Sk = S[keep][:, S[keep].sum(0) > 0]
        sol, c2s, _ = wls(Sk, y[keep], w[keep])
        loo.append(dict(omitted_sector=s, chi2_linear=c2l, dof_linear=int(keep.sum() - 2),
                        p_linear=float(CHI2.sf(c2l, max(keep.sum() - 2, 1))), delta_chi2_seasons=c2l - c2s,
                        extra_params=Sk.shape[1] - 2))
    out["leave_one_sector_out"] = loo
    return out


def calibration_factors(tic, red):
    p = RES / f"s03_calibration_{tic}.json"
    if not p.exists():
        return {}, {}
    cal = read(p)["reductions"].get(red)
    if not cal:
        return {}, {}
    fa = {int(k): max(1.0, v["timing"].get("robust_std_of_z") or 1.0)
          for k, v in cal["injection_adopted_shape"]["by_cadence"].items() if v["timing"].get("n", 0) >= 8}
    fg = {int(k): max(1.0, v["timing"].get("robust_std_of_z") or 1.0)
          for k, v in cal["injection_grazing_shape"]["by_cadence"].items() if v["timing"].get("n", 0) >= 8}
    return fa, fg


def season_joint_shift(tic, red, groups, eph, tmpl):
    """For each season: one common time shift for all its admitted events (depth and baselines free per
    event); profile chi2 over shifts; 1-sigma from delta chi2 = 1 (per-event beta-inflated errors)."""
    segs = REDUCTIONS[red](tic)
    res = []
    offs = np.arange(-eph["T14"], eph["T14"] + 1e-9, 2 / 1440)
    for g in groups:
        tot = np.zeros(len(offs))
        nev = 0
        for seg in segs:
            for c in g:
                tc = eph["T0"] + c * eph["P"]
                if not (seg["t"].min() - 1 < tc < seg["t"].max() + 1):
                    continue
                r0 = measure(seg, tc, eph, tmpl, use_profile=False)
                if not r0["admitted"]:
                    continue
                nev += 1
                se = r0["sigma_white_ppt"] * r0["beta"]
                w = (np.abs(seg["t"] - tc) < r0["window_half_d"]) & seg["quality_ok"] & np.isfinite(seg["y"])
                t, y = seg["t"][w], seg["y"][w]
                dt = t - tc
                for i, o in enumerate(offs):
                    h = tmpl(dt - o, seg["cad_s"] / 86400)
                    X = np.column_stack([np.ones_like(dt), dt / r0["window_half_d"], -h])
                    sol, *_ = np.linalg.lstsq(X, y, rcond=None)
                    if sol[-1] <= 0:
                        tot[i] += np.sum(((y - X @ np.r_[sol[:-1], 0]) / se) ** 2)   # no dimming allowed
                    else:
                        tot[i] += np.sum(((y - X @ sol) / se) ** 2)
        if nev == 0:
            continue
        i0 = int(np.argmin(tot))
        inside = np.where(tot <= tot[i0] + 1)[0]
        res.append(dict(cycles=g, n_events=nev, shift_min=float(offs[i0] * 1440),
                        lo_min=float(offs[inside.min()] * 1440), hi_min=float(offs[inside.max()] * 1440),
                        edge=bool(i0 in (0, len(offs) - 1))))
    return res


def run(tic):
    eph = adopted(tic)
    tmpl = Template(eph)
    ev = read(RES / f"s02_events_{tic}.json")
    out = dict(tic=tic, generated_utc=utc(), reference=dict(P=eph["P"], T0=eph["T0"]), reductions={})
    fig, ax = plt.subplots(figsize=(9, 4.8))
    colors = {"pdc_raw": "C0", "sap_raw": "C1", "survey_detrended": "C2", "survey_tesscut_aperture": "C3",
              "continuation_fresh_aperture": "C4", "tglc_aperture": "C5", "tglc_psf": "C6", "fu3_pixel": "C7"}
    k = 0
    for red in ev["summary"]:
        rows = [r for r in ev["events"] if r["reduction"] == red and r.get("admitted")
                and r.get("timing_status") in ("ok", "multimodal") and r.get("oc_err_d")]
        if len(rows) < 4:
            continue
        fa, fg = calibration_factors(tic, red)
        for r in rows:
            c = int(r["cad_s"])
            r["oc_err_cal_adopted_d"] = r["oc_err_d"] * fa.get(c, max(fa.values()) if fa else 1.0)
            r["oc_err_cal_grazing_d"] = r["oc_err_d"] * fg.get(c, max(fg.values()) if fg else 1.0)
        res = dict(n=len(rows), factors_adopted=fa, factors_grazing=fg,
                   formal=oc_stats(rows, "oc_err_d"), calibrated_adopted=oc_stats(rows, "oc_err_cal_adopted_d"),
                   calibrated_grazing=oc_stats(rows, "oc_err_cal_grazing_d"),
                   events=[dict(sector=r["sector"], cycle=r["cycle"], cad_s=r["cad_s"], oc_min=r["oc_d"] * 1440,
                                err_formal_min=r["oc_err_d"] * 1440,
                                err_cal_adopted_min=r["oc_err_cal_adopted_d"] * 1440,
                                err_cal_grazing_min=r["oc_err_cal_grazing_d"] * 1440,
                                status=r["timing_status"]) for r in rows])
        if red in ("pdc_raw", "survey_tesscut_aperture"):
            res["season_joint_shift"] = season_joint_shift(tic, red, res["formal"]["season_groups_cycles"], eph, tmpl)
        out["reductions"][red] = res
        x = np.array([r["cycle"] for r in rows]) + (k - 2) * 0.25
        ax.errorbar(x, [r["oc_d"] * 1440 for r in rows], yerr=[r["oc_err_cal_adopted_d"] * 1440 for r in rows],
                    fmt="o", ms=4, capsize=2, color=colors.get(red, None), label=f"{red} (cal. errors)")
        k += 1
        f, ca, cg = res["formal"], res["calibrated_adopted"], res["calibrated_grazing"]
        log("s04", f"{tic} {red}: n={len(rows)} linear chi2 formal {f['linear']['chi2']:.1f}/{f['linear']['dof']} "
                   f"(p={f['linear']['p']:.2g}); cal-adopted {ca['linear']['chi2']:.1f} (p={ca['linear']['p']:.2g}); "
                   f"cal-grazing {cg['linear']['chi2']:.1f} (p={cg['linear']['p']:.2g}); seasons dchi2 (cal-ad) "
                   f"{ca['delta_chi2_seasons_vs_linear']:.1f} for {ca['season_minus_linear_extra_params']} extra")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("cycle (reference ephemeris)")
    ax.set_ylabel("O - C (min)")
    ax.set_title(f"TIC {tic}: transit timing vs. reference ephemeris (injection-calibrated errors)")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(FIG / f"oc_{tic}.png", dpi=130)
    plt.close(fig)
    save(RES / f"s04_oc_{tic}.json", out)
    return out


def frozen_ephemeris(tic):
    """PROTOCOL 1: linear ephemeris from D-orig (pdc_raw) per-event times, errors inflated by
    sqrt(max(1, chi2_red)); predictions with +/-3 sigma envelopes for sectors 99-140 time range."""
    ev = read(RES / f"s02_events_{tic}.json")
    rows = [r for r in ev["events"] if r["reduction"] == "pdc_raw" and r.get("admitted")
            and r.get("timing_status") in ("ok", "multimodal") and r.get("oc_err_d")]
    n = np.array([r["cycle"] for r in rows], float)
    t = np.array([r["tc_fit"] for r in rows])
    e = np.array([r["oc_err_d"] for r in rows])
    w = 1 / e ** 2
    nref = float(np.round(np.average(n, weights=w)))
    X = np.column_stack([np.ones_like(n), n - nref])
    sol, c2, cov = wls(X, t, w)
    dof = len(t) - 2
    infl = max(1.0, np.sqrt(c2 / max(dof, 1)))
    covi = cov * infl ** 2
    eph = adopted(tic)
    preds = []
    for cyc in range(int(n.max()) + 1, int(n.max()) + 80):
        tc = sol[0] + (cyc - nref) * sol[1]
        v = np.array([1, cyc - nref])
        sig = float(np.sqrt(v @ covi @ v))
        preds.append(dict(cycle=cyc, tc_btjd=float(tc), sigma_d=sig, sigma_min=sig * 1440,
                          tc_reference_ephemeris=eph["T0"] + cyc * eph["P"]))
    out = dict(tic=tic, generated_utc=utc(), source="pdc_raw (D-orig TESS-SPOC PDCSAP / QLP det_flux, sectors <= 98)",
               n_events=len(rows), nref=nref, T_nref=float(sol[0]), P=float(sol[1]),
               cov_inflated_d2=covi.tolist(), cov_formal_d2=cov.tolist(), chi2=c2, dof=dof, inflation=float(infl),
               T0_equivalent_cycle0=float(sol[0] - nref * sol[1]),
               note="Conditional linear-ephemeris reconstruction (PROTOCOL 1). Errors inflated by sqrt(chi2_red). "
                    "Not a recovered original posterior; non-linear timing (if any) is not modelled.",
               predictions=preds)
    save(RES / f"s03_ephemeris_{tic}.json", out)
    log("s04", f"{tic} frozen ephemeris: P {sol[1]:.6f} +- {np.sqrt(covi[1,1]):.6f} T(n={nref:.0f}) {sol[0]:.5f} "
               f"+- {np.sqrt(covi[0,0])*1440:.1f} min; inflation {infl:.2f}")
    return out


if __name__ == "__main__":
    tics = [int(a) for a in sys.argv[1:]] or list(TICS)
    for t in tics:
        frozen_ephemeris(t)
        run(t)
