"""Section 5.1-5.2 of PROTOCOL.md: reproduce the continuation's TIC 270573718 retrospective statistics
(corrected S/N 0.29, aperture S/N 8.19) with ITS OWN code and inputs, then decompose them.

The continuation's functions are imported read-only from its bundle (windows / ephemeris_fit /
predicted_depths / pool).  Nothing is written inside the bundle.
"""
import sys
import copy

from fu3_common import *

sys.path.insert(0, str(CONT))
import fit_recurrence_models as F   # noqa: E402  (continuation code; read-only use)

TIC = 270573718
row = F.BYID[TIC]
f = F.fit(row)
P, T0, DUR = f["period"], f["t0_btjd"], f["t14_hours"] / 24


def split(ev):
    mid = np.median([e["tc"] for e in ev])
    return [e for e in ev if e["tc"] <= mid], [e for e in ev if e["tc"] > mid]


def epl(early, late):
    """early-predicts-late exactly as exact_eccentric_and_timing.py computes it."""
    a = F.ephemeris_fit(early, P, DUR)
    pred = F.predicted_depths(late, a, P, DUR)
    return a, pred, F.pool(pred)


def summarise_fit(a):
    c = np.array(a["covariance"])
    return dict(depth_ppt=a["depth_ppt"], epoch_correction_d=a["epoch_correction_d"],
                period_correction_d=a["period_correction_d"], sig=np.sqrt(np.diag(c)).tolist(), n=a["n"],
                nref=a["nref"], chi2=a["chi2"])


def shift_at(a, cycle):
    return a["epoch_correction_d"] + cycle * a["period_correction_d"]


def main():
    out = dict(tic=TIC, period=P, t0=T0, t14_d=DUR, generated_utc=utc())
    series = {"corrected": F.windows(row, False), "aperture": F.windows(row, True)}
    # ---- 1. exact reproduction ------------------------------------------------------------------------
    repro = {}
    for name, ev in series.items():
        early, late = split(ev)
        a, pred, pl = epl(early, late)
        repro[name] = dict(n_events=len(ev), early_cycles=[e["cycle"] for e in early],
                           late_cycles=[e["cycle"] for e in late],
                           early_sectors=[e["sector"] for e in early], late_sectors=[e["sector"] for e in late],
                           early_fit=summarise_fit(a), early_predicts_late=pl,
                           predicted_shift_at_late_cycles_d={e["cycle"]: shift_at(a, e["cycle"]) for e in late},
                           per_event=[dict(sector=p["sector"], cycle=p["cycle"], depth=p["depth"],
                                           depth_err=p["depth_err"], shift_d=p["predicted_shift_d"],
                                           timing_err_d=p["timing_error_d"]) for p in pred],
                           late_at_fixed_reference=F.pool(late),
                           all_events_fixed=F.pool(ev))
    out["reproduction"] = repro
    prior = read(CONT / "analysis" / f"{TIC}_exact_alternatives.json")["timing"]
    out["matches_prior"] = {t["series"]: dict(prior_snr=t["early_predicts_late"]["snr"],
                                              reproduced_snr=repro[t["series"]]["early_predicts_late"]["snr"])
                            for t in prior}
    # ---- 2. decomposition --------------------------------------------------------------------------
    dec = {}
    corr, ap = series["corrected"], series["aperture"]
    common_cycles = sorted(set(e["cycle"] for e in corr) & set(e["cycle"] for e in ap))
    dec["common_cycles"] = common_cycles
    for name, ev in series.items():
        sub = [e for e in ev if e["cycle"] in common_cycles]
        early, late = split(sub)
        a, pred, pl = epl(early, late)
        dec[f"{name}_on_common_event_set"] = dict(early_cycles=[e["cycle"] for e in early],
                                                  late_cycles=[e["cycle"] for e in late],
                                                  early_fit=summarise_fit(a), early_predicts_late=pl)
    # corrected series with the aperture series' exact early/late split membership
    ap_early, ap_late = split(ap)
    ce = [e for e in corr if e["cycle"] in {x["cycle"] for x in ap_early}]
    cl = [e for e in corr if e["cycle"] in {x["cycle"] for x in ap_late}]
    a, pred, pl = epl(ce, cl)
    dec["corrected_with_aperture_split"] = dict(early_cycles=[e["cycle"] for e in ce],
                                                late_cycles=[e["cycle"] for e in cl],
                                                early_fit=summarise_fit(a), early_predicts_late=pl)
    # corrected series without the 30-min year-1 sectors (1-11)
    ev2 = [e for e in corr if e["sector"] > 13]
    early, late = split(ev2)
    a, pred, pl = epl(early, late)
    dec["corrected_without_year1"] = dict(early_cycles=[e["cycle"] for e in early],
                                          late_cycles=[e["cycle"] for e in late], early_fit=summarise_fit(a),
                                          early_predicts_late=pl)
    # leave-one-early-sector-out (corrected)
    early, late = split(corr)
    loo = []
    for s in sorted(set(e["sector"] for e in early)):
        a, pred, pl = epl([e for e in early if e["sector"] != s], late)
        loo.append(dict(omitted_early_sector=s, early_fit=summarise_fit(a), early_predicts_late=pl))
    dec["corrected_leave_one_early_sector_out"] = loo
    # leave-one-late-sector-out (corrected) with the original early fit
    a0 = F.ephemeris_fit(early, P, DUR)
    dec["corrected_leave_one_late_sector_out"] = [
        dict(omitted_late_sector=s, early_predicts_late=F.pool(F.predicted_depths([e for e in late if e["sector"] != s], a0, P, DUR)))
        for s in sorted(set(e["sector"] for e in late))]
    # early fit with the period correction forced to zero (epoch only): same late events
    a_ep = copy.deepcopy(a0)
    a_ep["period_correction_d"] = 0.0
    a_ep["epoch_correction_d"] = a0["epoch_correction_d"] + a0["nref"] * a0["period_correction_d"]
    dec["corrected_early_epoch_only_at_nref"] = dict(
        note="early-fit shift evaluated at the early reference cycle, period correction set to 0",
        early_predicts_late=F.pool(F.predicted_depths(late, a_ep, P, DUR)))
    # the same statistic with the timing extrapolation replaced by zero shift (pure fixed ephemeris)
    a_zero = copy.deepcopy(a0)
    a_zero["period_correction_d"] = 0.0
    a_zero["epoch_correction_d"] = 0.0
    dec["corrected_late_at_reference_ephemeris"] = F.pool(F.predicted_depths(late, a_zero, P, DUR))
    # depth versus imposed timing shift for the late corrected events (how much shift kills the signal)
    grid = np.linspace(-0.25, 0.25, 51)
    dec["corrected_late_depth_vs_uniform_shift"] = [
        dict(shift_d=float(s), pool=F.pool(F.predicted_depths(late, dict(a_zero, epoch_correction_d=float(s)), P, DUR)))
        for s in grid]
    out["decomposition"] = dec
    # event tables of both series
    out["events"] = {name: [dict(sector=e["sector"], cycle=e["cycle"], tc=e["tc"], depth=e["depth"],
                                 depth_err=e["depth_err"], beta=e["beta"], exposure_min=e["exposure"] * 1440,
                                 n_bins=len(e["t"])) for e in ev] for name, ev in series.items()}
    save(RES / "s01_270_reproduce.json", out)
    for k, v in out["matches_prior"].items():
        log("s01", f"{k}: prior S/N {v['prior_snr']:.4f} reproduced {v['reproduced_snr']:.4f}")
    for k in ("corrected_on_common_event_set", "aperture_on_common_event_set", "corrected_with_aperture_split",
              "corrected_without_year1", "corrected_early_epoch_only_at_nref"):
        log("s01", f"{k}: {dec[k]['early_predicts_late']['snr']:.2f}")
    log("s01", f"corrected late at reference ephemeris: {dec['corrected_late_at_reference_ephemeris']['snr']:.2f}")
    for x in loo:
        log("s01", f"LOO early sector {x['omitted_early_sector']}: S/N {x['early_predicts_late']['snr']:.2f} "
                   f"dP {x['early_fit']['period_correction_d']:.5f}")


if __name__ == "__main__":
    main()
