"""PROTOCOL 4 (timing claim), added test: an empirical null for season-level timing structure.

A strictly periodic copy of the adopted transit (observed pooled depth, adopted shape, same P) is injected into
the reduction at a shifted epoch T0 + phi*P (phi on a fixed grid avoiding |phi| < 0.08 and |phi - 0.5| < 0.08,
so injected windows avoid the real primary and half phase), with the real transits masked (+/- T14).  The
injected events are measured exactly like the real ones (events.measure, fixed-template profile timing) and the
same O-C models are fitted (s04.oc_stats, formal errors).  The distribution of delta chi2 (season offsets vs
linear) and of the linear chi2 under strict periodicity, compared with the observed values, gives an
empirical tail probability that includes correlated noise, detrending and the timing method itself.
Outputs: results/s16_ttv_null_<tic>.json
"""
import sys

from fu3_common import *
from events import adopted, Template, measure
from reductions import REDUCTIONS
from s03_calibrate import mask_real, inject
from s04_oc import oc_stats

PHIS = np.r_[np.linspace(0.09, 0.41, 12), np.linspace(0.59, 0.91, 12)]


def coherence(rows, min_events=4):
    """Season coherence: for seasons (s04.seasons grouping) with >= min_events timed events, the median O-C
    (minutes) and the fraction of events sharing its sign; statistic = max |median| over such seasons."""
    from s04_oc import seasons
    smap, groups = seasons([r["cycle"] for r in rows])
    best = dict(stat=0.0, season=None, n=0, frac_same_sign=None)
    per = []
    for gi, g in enumerate(groups):
        oc = np.array([r["oc_d"] * 1440 for r in rows if smap[r["cycle"]] == gi])
        if len(oc) < min_events:
            continue
        med = float(np.median(oc))
        fs = float(np.mean(np.sign(oc) == np.sign(med)))
        per.append(dict(season=gi, n=len(oc), median_min=med, frac_same_sign=fs))
        if abs(med) > best["stat"]:
            best = dict(stat=abs(med), season=gi, n=len(oc), frac_same_sign=fs)
    return best, per


def run(tic, red="pdc_raw"):
    eph = adopted(tic)
    tmpl = Template(eph)
    ev = read(RES / f"s02_events_{tic}.json")
    depth = ev["summary"][red]["pooled"]["depth_ppt"]
    real_rows = [r for r in ev["events"] if r["reduction"] == red and r.get("admitted")
                 and r.get("timing_status") in ("ok", "multimodal") and r.get("oc_err_d")]
    obs = oc_stats(real_rows, "oc_err_d")
    segs = [mask_real(s, eph) for s in REDUCTIONS[red](tic)]
    null = []
    for phi in PHIS:
        rows = []
        for seg in segs:
            n0 = int(np.ceil((np.nanmin(seg["t"]) - eph["T0"]) / eph["P"] - phi)) - 1
            n1 = int(np.floor((np.nanmax(seg["t"]) - eph["T0"]) / eph["P"] - phi)) + 1
            for n in range(n0, n1 + 1):
                tc = eph["T0"] + (n + phi) * eph["P"]
                if not (np.nanmin(seg["t"]) + 0.3 < tc < np.nanmax(seg["t"]) - 0.3):
                    continue
                s2 = inject(seg, tc, depth, tmpl, eph)
                r = measure(s2, tc, eph, tmpl, deg=1)
                if r.get("admitted") and r.get("timing_status") in ("ok", "multimodal") and r.get("oc_err_d"):
                    r.update(cycle=n, sector=seg["sector"])
                    rows.append(r)
        if len(rows) >= 5:
            st = oc_stats(rows, "oc_err_d")
            coh, per = coherence(rows)
            null.append(dict(phi=float(phi), n=len(rows), chi2_linear=st["linear"]["chi2"], dof=st["linear"]["dof"],
                             dchi2_seasons=st["delta_chi2_seasons_vs_linear"], extra=st["season_minus_linear_extra_params"],
                             season_offsets=st["season_offsets"]["params"], coherence=coh, seasons=per))
    nd = np.array([x["dchi2_seasons"] for x in null])
    nl = np.array([x["chi2_linear"] / max(x["dof"], 1) for x in null])
    nc = np.array([x["coherence"]["stat"] for x in null])
    o_d = obs["delta_chi2_seasons_vs_linear"]
    o_l = obs["linear"]["chi2"] / obs["linear"]["dof"]
    o_coh, o_per = coherence(real_rows)
    out = dict(tic=tic, reduction=red, generated_utc=utc(), injected_depth_ppt=depth,
               observed=dict(dchi2_seasons=o_d, chi2red_linear=o_l, season_offsets=obs["season_offsets"]["params"],
                             n=len(real_rows), coherence=o_coh, seasons=o_per),
               null=null, n_null=len(null),
               tail_dchi2_seasons=float((1 + np.sum(nd >= o_d)) / (1 + len(nd))) if len(nd) else None,
               tail_chi2red_linear=float((1 + np.sum(nl >= o_l)) / (1 + len(nl))) if len(nl) else None,
               tail_coherence=float((1 + np.sum(nc >= o_coh["stat"])) / (1 + len(nc))) if len(nc) else None,
               null_coherence_quantiles=dict(zip(("p50", "p90", "max"), np.percentile(nc, [50, 90, 100]).tolist())) if len(nc) else None,
               null_dchi2_quantiles=dict(zip(("p50", "p90", "max"), np.percentile(nd, [50, 90, 100]).tolist())) if len(nd) else None,
               null_chi2red_quantiles=dict(zip(("p50", "p90", "max"), np.percentile(nl, [50, 90, 100]).tolist())) if len(nl) else None)
    save(RES / f"s16_ttv_null_{tic}_{red}.json", out)
    log("s16", f"{tic} {red}: observed season dchi2 {o_d:.1f}, linear chi2red {o_l:.2f}; null (n={len(null)}) dchi2 "
               f"{out['null_dchi2_quantiles']}, chi2red {out['null_chi2red_quantiles']}; tails {out['tail_dchi2_seasons']:.3f} / {out['tail_chi2red_linear']:.3f}; "
               f"coherence obs {o_coh} null {out['null_coherence_quantiles']} tail {out['tail_coherence']}")
    return out


if __name__ == "__main__":
    tics = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(TICS)
    red = next((a for a in sys.argv[1:] if not a.isdigit()), "pdc_raw")
    for t in tics:
        run(t, red)
