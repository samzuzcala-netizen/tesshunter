"""Amendment A1.2: free-shape timing cross-check.  Each admitted event is fitted with a symmetric trapezoid
(centre, depth, total duration and ingress fraction free; local linear baseline profiled), integrated over the
exposure.  The centre's 1-sigma interval comes from a profile over the centre (other parameters re-optimised) with
beta-inflated white errors.  Season offsets and the s16 coherence statistic are recomputed from these times.
Outputs: results/s19_freeshape_<tic>.json
"""
import sys

from scipy.optimize import least_squares

from fu3_common import *
from events import adopted, Template, admit, measure
from reductions import REDUCTIONS
from s16_ttv_null import coherence
from s04_oc import oc_stats


def trap(dt, depth, T, f, exp_d):
    ss = max(1, int(np.ceil(exp_d * 1440 / 2)))
    off = (np.arange(ss) + 0.5) / ss - 0.5
    x = np.abs(dt[:, None] + off[None, :] * exp_d)
    tau = max(f, 1e-3) * T / 2
    h = np.clip((T / 2 - x) / tau, 0, 1)
    return depth * h.mean(axis=1)


def fit_event(t, y, sig, tc, half, T0dur, exp_d, centre=None, dmax=50.0, tlo=0.3, thi=2.0, dmin=-20.0):
    dt = t - tc
    B = np.column_stack([np.ones_like(dt), dt / half])
    Q = np.linalg.qr(B)[0]

    def res(p):
        c = centre if centre is not None else p[0]
        q = p if centre is not None else p[1:]
        m = -trap(dt - c, q[0], q[1], q[2], exp_d)
        r = y - m
        r = r - Q @ (Q.T @ r)
        return r / sig
    best = None
    for f0 in (0.15, 0.5, 0.95):
        for T in (max(0.8, tlo) * T0dur, T0dur, min(1.2, thi) * T0dur):
            if centre is None:
                x0, lo, hi = [0.0, min(1.5, dmax / 2), T, f0], [-T0dur, dmin, tlo * T0dur, 0.02], [T0dur, dmax, thi * T0dur, 1.0]
            else:
                x0, lo, hi = [min(1.5, dmax / 2), T, f0], [dmin, tlo * T0dur, 0.02], [dmax, thi * T0dur, 1.0]
            try:
                r = least_squares(res, x0, bounds=(lo, hi), max_nfev=300)
            except Exception:   # noqa: BLE001
                continue
            if best is None or r.cost < best.cost:
                best = r
    return best


def clip_isolated(t, y, exp_d, nsig=5.0):
    """Keep mask for points within nsig robust sigma of a ~1-h running median (bounded variant only)."""
    from scipy.ndimage import median_filter
    k = max(5, int(round((1 / 24) / exp_d)) | 1)
    r = y - median_filter(y, size=k, mode="nearest")
    s = 1.4826 * mad(r)
    return np.abs(r) < nsig * s if s > 0 else np.ones_like(y, bool)


def run(tic, red="pdc_raw", bounded=False):
    """bounded=True (post-hoc sensitivity variant, A2): depth in [0, 3 x adopted], T14 in [0.6, 1.6] x adopted,
    and isolated > 5-sigma points (1-h running median) removed from each window before fitting."""
    eph = adopted(tic)
    tmpl = Template(eph)
    kw = dict(dmax=3 * eph["depth_ppt"], tlo=0.6, thi=1.6, dmin=0.0) if bounded else {}
    rows = []
    for seg in REDUCTIONS[red](tic):
        n0 = int(np.ceil((np.nanmin(seg["t"]) - eph["T0"]) / eph["P"]))
        n1 = int(np.floor((np.nanmax(seg["t"]) - eph["T0"]) / eph["P"]))
        for n in range(n0, n1 + 1):
            tc = eph["T0"] + n * eph["P"]
            ok, reason, w, half = admit(seg, tc, eph)
            if not ok:
                continue
            r0 = measure(seg, tc, eph, tmpl, use_profile=False)
            sig = r0["sigma_white_ppt"] * r0["beta"]
            t, y = seg["t"][w], seg["y"][w]
            exp_d = seg["cad_s"] / 86400
            n_clip = 0
            if bounded:
                keep = clip_isolated(t, y, exp_d)
                n_clip = int((~keep).sum())
                t, y = t[keep], y[keep]
            b = fit_event(t, y, sig, tc, half, eph["T14"], exp_d, **kw)
            if b is None or b.x[1] <= 0:
                rows.append(dict(sector=seg["sector"], cycle=n, status="no_dimming_fit", n_clipped=n_clip))
                continue
            c0 = b.x[0]
            grid = np.arange(-eph["T14"], eph["T14"] + 1e-9, 3 / 1440)
            prof = []
            for c in grid:
                bb = fit_event(t, y, sig, tc, half, eph["T14"], exp_d, centre=c, **kw)
                prof.append(2 * bb.cost if bb is not None else np.inf)
            prof = np.array(prof)
            cmin = min(prof.min(), 2 * b.cost)
            inside = grid[prof <= cmin + 1]
            lo, hi = (inside.min(), inside.max()) if len(inside) else (c0, c0)
            err = max(c0 - lo, hi - c0, 1.5 / 1440)
            rows.append(dict(sector=seg["sector"], cycle=n, oc_d=float(c0), oc_err_d=float(err), depth=float(b.x[1]),
                             T14_h=float(b.x[2] * 24), ingress_frac=float(b.x[3]), status="ok",
                             edge=bool(abs(c0) > 0.95 * eph["T14"]), n_clipped=n_clip,
                             at_bound=bool(bounded and (b.x[1] > 0.98 * kw["dmax"] or b.x[2] < 1.02 * kw["tlo"] * eph["T14"]
                                                        or b.x[2] > 0.98 * kw["thi"] * eph["T14"]))))
    good = [r for r in rows if r.get("status") == "ok"]
    st = oc_stats(good, "oc_err_d") if len(good) >= 5 else None
    coh, per = coherence(good) if good else (None, None)
    out = dict(tic=tic, reduction=red, bounded=bounded, generated_utc=utc(), events=rows, oc=st, coherence=coh, seasons=per,
               n_at_bound=sum(1 for r in good if r.get("at_bound")))
    save(RES / f"s19_freeshape_{tic}_{red}{'_bounded' if bounded else ''}.json", out)
    if st:
        log("s19", f"{tic} {red}{' BOUNDED' if bounded else ''}: n={len(good)} season offsets {[round(x, 0) for x in st['season_offsets']['params']]} "
                   f"(err {[round(x, 0) for x in st['season_offsets']['param_err']]}); lin chi2 {st['linear']['chi2']:.1f}/{st['linear']['dof']}; "
                   f"season dchi2 {st['delta_chi2_seasons_vs_linear']:.1f}; coherence {coh}; "
                   f"median T14 {np.median([r['T14_h'] for r in good]):.2f} h, ingress frac median {np.median([r['ingress_frac'] for r in good]):.2f}")
    return out


if __name__ == "__main__":
    tics = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(TICS)
    red = next((a for a in sys.argv[1:] if not a.isdigit() and not a.startswith("--")), "pdc_raw")
    for t in tics:
        run(t, red, bounded="--bounded" in sys.argv)
