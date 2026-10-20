"""PROTOCOL 4-5.5: empirical calibration of per-event depth and timing errors, and single-event null
(negative-control) distributions, in each reduction of each target.

* Real transits (+/- T14 around every predicted epoch, all cycles) are masked first.
* Injections: the adopted unit template times the reduction's pooled depth is multiplied into the flux at
  tc_event + s*T14, s in {-7,-5,-3,+3,+5,+7} for every admitted real event (plus +/-9,+/-11,+/-13 when a
  sector has a single event, giving 12 per sector), and measured with the same profile method.
* Shape-mismatch check: the same injections with a grazing template (b and a/R* of the packet free fit)
  measured with the adopted template.
* Nulls: >= 200 random epochs per reduction (uniform over admitted out-of-transit times), no injection.

Outputs: results/s03_calibration_<tic>.json
"""
import sys

from fu3_common import *
from events import adopted, Template, measure
from reductions import REDUCTIONS
import s02_events as S2

RNG_SEED = 20261018
SHIFTS = (-7, -5, -3, 3, 5, 7)
EXTRA = (-13, -11, -9, 9, 11, 13)


def mask_real(seg, eph):
    t = seg["t"]
    n = np.round((t - eph["T0"]) / eph["P"])
    near = np.abs(t - (eph["T0"] + n * eph["P"])) < eph["T14"]
    s = dict(seg)
    s["quality_ok"] = seg["quality_ok"] & ~near
    return s


def inject(seg, tc, depth_ppt, tmpl, eph):
    s = dict(seg)
    h = tmpl(seg["t"] - tc, seg["cad_s"] / 86400.0)
    s["y"] = seg["y"] - depth_ppt * h * (1 + seg["y"] / 1000.0)   # multiplicative injection
    return s


def grazing_template(tic):
    f = read(PACKET[tic] / "fit.json")
    ff = f["free_fit"]
    eph = adopted(tic)
    g = dict(eph)
    g.update(k=ff["rp_rs"], a_rs=ff["a_rs"], b=ff["b"],
             inc=float(np.degrees(np.arccos(min(ff["b"] / ff["a_rs"], 0.999999)))))
    return Template(g), g


def run(tic, reductions=("pdc_raw", "sap_raw", "survey_tesscut_aperture", "survey_detrended")):
    rng = np.random.default_rng(RNG_SEED + tic % 1000)
    eph = adopted(tic)
    tmpl = Template(eph)
    gtmpl, geph = grazing_template(tic)
    ev = read(RES / f"s02_events_{tic}.json")
    out = dict(tic=tic, generated_utc=utc(), seed=RNG_SEED + tic % 1000, shifts_T14=SHIFTS, extra_shifts=EXTRA,
               grazing_geometry=dict(k=geph["k"], a_rs=geph["a_rs"], b=geph["b"]), reductions={})
    for name in reductions:
        segs = REDUCTIONS[name](tic)
        if not segs:
            continue
        summ = ev["summary"].get(name, {})
        depth = summ.get("pooled", {}).get("depth_ppt")
        if not depth or depth <= 0:
            continue
        real = [r for r in ev["events"] if r["reduction"] == name and r["admitted"]]
        by_sector = {}
        for r in real:
            by_sector.setdefault(r["sector"], []).append(r)
        inj, injg, nulls = [], [], []
        for seg in segs:
            ms = mask_real(seg, eph)
            evs = by_sector.get(seg["sector"], [])
            shifts = list(SHIFTS) + (list(EXTRA) if len(evs) == 1 else [])
            for r in evs:
                for s in shifts:
                    tc = r["tc_ref"] + s * eph["T14"]
                    for templ, store in ((tmpl, inj), (gtmpl, injg)):
                        x = measure(inject(ms, tc, depth, templ, eph), tc, eph, tmpl, deg=1)
                        if x["admitted"]:
                            store.append(dict(sector=seg["sector"], cad_s=seg["cad_s"], shift_T14=s,
                                              depth_in=depth, depth_out=x["depth_ppt"], depth_err=x["depth_err_ppt"],
                                              oc_d=x.get("oc_d"), oc_err_d=x.get("oc_err_d"),
                                              timing_status=x.get("timing_status")))
            # nulls: random out-of-transit epochs in this segment (proportional to its length)
            good_t = ms["t"][ms["quality_ok"]]
            if len(good_t) < 50:
                continue
            k = max(8, int(round(250 * (np.ptp(good_t) / 27.0) / max(len(segs), 1))))
            for tc in rng.uniform(good_t.min() + 0.5, good_t.max() - 0.5, size=k):
                x = measure(ms, tc, eph, tmpl, deg=1)
                if x["admitted"]:
                    nulls.append(dict(sector=seg["sector"], cad_s=seg["cad_s"], tc=tc, depth=x["depth_ppt"],
                                      depth_err=x["depth_err_ppt"], oc_d=x.get("oc_d"),
                                      timing_status=x.get("timing_status")))

        def timing_stats(rows):
            rows = [r for r in rows if r["oc_d"] is not None and r["timing_status"] in ("ok", "multimodal")]
            if len(rows) < 5:
                return dict(n=len(rows))
            oc = np.array([r["oc_d"] for r in rows]) * 1440
            er = np.array([r["oc_err_d"] for r in rows]) * 1440
            z = oc / er
            return dict(n=len(rows), median_formal_err_min=float(np.median(er)), robust_std_min=float(mad(oc)),
                        std_min=float(np.std(oc)), frac_within_1sigma=float(np.mean(np.abs(z) <= 1)),
                        robust_std_of_z=float(mad(z)), mean_bias_min=float(np.mean(oc)))

        def by_cad(rows):
            res = {}
            for c in sorted(set(r["cad_s"] for r in rows)):
                rr = [r for r in rows if r["cad_s"] == c]
                dep = np.array([r["depth_out"] for r in rr])
                res[str(int(c))] = dict(timing=timing_stats(rr), n=len(rr),
                                        depth_ratio_median=float(np.median(dep) / rr[0]["depth_in"]),
                                        depth_z_robust_std=float(mad((dep - rr[0]["depth_in"]) / np.array([r["depth_err"] for r in rr]))))
            return res

        nd = np.array([r["depth"] for r in nulls])
        ne = np.array([r["depth_err"] for r in nulls])
        real_depths = np.array([r["depth_ppt"] for r in real])
        med_real = float(np.median(real_depths)) if len(real_depths) else np.nan
        out["reductions"][name] = dict(
            pooled_depth_used=depth, n_inj=len(inj), n_inj_grazing=len(injg), n_null=len(nulls),
            injection_adopted_shape=dict(all=timing_stats(inj), by_cadence=by_cad(inj),
                                         depth_ratio_median=float(np.median([r["depth_out"] for r in inj]) / depth) if inj else None),
            injection_grazing_shape=dict(all=timing_stats(injg), by_cadence=by_cad(injg),
                                         depth_ratio_median=float(np.median([r["depth_out"] for r in injg]) / depth) if injg else None),
            null=dict(n=len(nulls), depth_mean=float(nd.mean()) if len(nd) else None,
                      depth_robust_std=float(mad(nd)) if len(nd) else None,
                      z_robust_std=float(mad(nd / ne)) if len(nd) else None,
                      frac_depth_ge_median_real=float(np.mean(nd >= med_real)) if len(nd) else None,
                      frac_z_ge_3=float(np.mean(nd / ne >= 3)) if len(nd) else None,
                      median_real_event_depth=med_real,
                      by_cadence={str(int(c)): dict(n=int(np.sum([r["cad_s"] == c for r in nulls])),
                                                     depth_robust_std=float(mad(nd[[r["cad_s"] == c for r in nulls]])),
                                                     z_robust_std=float(mad((nd / ne)[[r["cad_s"] == c for r in nulls]])),
                                                     frac_ge_median_real=float(np.mean(nd[[r["cad_s"] == c for r in nulls]] >= med_real)))
                                  for c in sorted(set(r["cad_s"] for r in nulls))}),
            injections=inj, injections_grazing=injg, nulls=nulls)
        a = out["reductions"][name]
        log("s03cal", f"{tic} {name}: inj {len(inj)} timing robust std {a['injection_adopted_shape']['all'].get('robust_std_min')} "
                      f"(formal median {a['injection_adopted_shape']['all'].get('median_formal_err_min')}) z_std "
                      f"{a['injection_adopted_shape']['all'].get('robust_std_of_z')}; grazing z_std "
                      f"{a['injection_grazing_shape']['all'].get('robust_std_of_z')}; null n {len(nulls)} z_std {a['null']['z_robust_std']}"
                      f" frac>=median real {a['null']['frac_depth_ge_median_real']}")
    save(RES / f"s03_calibration_{tic}.json", out)
    return out


if __name__ == "__main__":
    tics = [int(a) for a in sys.argv[1:]] or list(TICS)
    for t in tics:
        run(t)
