"""PROTOCOL 5.2 / 7: decomposition of the continuation's retrospective early-predicts-late statistic for any target
(reproduction with the continuation's own functions, common-event-set and common-split versions, epoch-only
early fit, fixed reference ephemeris, leave-one-early-sector-out).  Output: results/s01b_decompose_<tic>.json
"""
import copy
import sys

from fu3_common import *

sys.path.insert(0, str(CONT))
import fit_recurrence_models as F   # noqa: E402


def split(ev):
    mid = np.median([e["tc"] for e in ev])
    return [e for e in ev if e["tc"] <= mid], [e for e in ev if e["tc"] > mid]


def run(tic):
    row = F.BYID[tic]
    f = F.fit(row)
    P, DUR = f["period"], f["t14_hours"] / 24
    series = {"corrected": F.windows(row, False), "aperture": F.windows(row, True)}
    out = dict(tic=tic, generated_utc=utc())
    prior = {t["series"]: t["early_predicts_late"]["snr"] for t in read(CONT / "analysis" / f"{tic}_exact_alternatives.json")["timing"]}
    for name, ev in series.items():
        early, late = split(ev)
        a = F.ephemeris_fit(early, P, DUR)
        pl = F.pool(F.predicted_depths(late, a, P, DUR))
        z = copy.deepcopy(a)
        z.update(epoch_correction_d=0.0, period_correction_d=0.0)
        fixed = F.pool(F.predicted_depths(late, z, P, DUR))
        ep = copy.deepcopy(a)
        ep.update(period_correction_d=0.0, epoch_correction_d=a["epoch_correction_d"] + a["nref"] * a["period_correction_d"])
        eponly = F.pool(F.predicted_depths(late, ep, P, DUR))
        loo = []
        for s in sorted(set(e["sector"] for e in early)):
            b = F.ephemeris_fit([e for e in early if e["sector"] != s], P, DUR)
            pp = F.pool(F.predicted_depths(late, b, P, DUR))
            loo.append(dict(omitted_early_sector=s, snr=(pp or {}).get("snr"), n_predicted=(pp or {}).get("n", 0),
                            period_correction_d=b["period_correction_d"]))
        out[name] = dict(prior_reported_snr=prior.get(name), reproduced=pl, late_at_reference=fixed,
                         early_epoch_only=eponly, early_fit=dict(depth=a["depth_ppt"], epoch_corr_d=a["epoch_correction_d"],
                                                                period_corr_d=a["period_correction_d"],
                                                                sig=np.sqrt(np.diag(np.array(a["covariance"]))).tolist()),
                         early_sectors=[e["sector"] for e in early], late_sectors=[e["sector"] for e in late],
                         late_events=[dict(sector=p["sector"], cycle=p["cycle"], depth=p["depth"], err=p["depth_err"],
                                           shift_min=p["predicted_shift_d"] * 1440)
                                      for p in F.predicted_depths(late, a, P, DUR)],
                         leave_one_early_sector_out=loo)
        log("s01b", f"{tic} {name}: prior {prior.get(name)} reproduced {pl['snr']:.2f}; late at reference "
                    f"{fixed['snr']:.2f}; epoch-only {eponly['snr']:.2f}; early sectors {out[name]['early_sectors']} "
                    f"late {out[name]['late_sectors']}; dP {a['period_correction_d']*1440:.2f} min/cycle")
    save(RES / f"s01b_decompose_{tic}.json", out)


if __name__ == "__main__":
    for t in [int(a) for a in sys.argv[1:]] or list(TICS):
        run(t)
