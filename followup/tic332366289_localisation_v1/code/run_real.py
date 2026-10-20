"""Real-event difference images, per-event / joint / leave-one-out fits,
registration Monte Carlo and the predeclared sensitivity runs.

Both localisation modes are reported: 'dimming' (R2: A >= 0, decision mode) and
'signed' (original, diagnostic). Writes results/real_events.json,
results/joint.json, results/sensitivity.json and arrays to D:.
"""
from __future__ import annotations

import json

import common as C
import numpy as np

import core
import diffimg
import fitting
import jointfit as JF
import scene as Sc

KAPPA = {int(k): v["kappa"] for k, v in json.load(open(C.RESULTS / "kappa.json")).items()}
SCENE = json.load(open(C.RESULTS / "scene.json"))
ARR = C.ARRAYS / "real"
ARR.mkdir(parents=True, exist_ok=True)
D2 = fitting.DCHI2_2DOF


def event_summary(ctx, res):
    S = ctx.S
    out = {k: v for k, v in res.items() if not k.startswith("_") and k != "hosts"}
    for tag, bx, by, A, sA in (("signed", res["best_x"], res["best_y"], res["best_A"], res["best_sA"]),
                               ("dimming", res["bestp_x"], res["bestp_y"], res["bestp_A"], res["bestp_sA"])):
        ra_b, dec_b = S.wcs.all_pix2world(bx - ctx.dx, by - ctx.dy, 0)
        out[f"{tag}_best"] = {"x": bx, "y": by, "A": A, "sA": sA, "snr": A / sA, "radec": [float(ra_b), float(dec_b)],
                              "offset_px": float(np.hypot(bx - ctx.xt, by - ctx.yt)),
                              "offset_arcsec": float(Sc.sep_arcsec(ctx.ra[ctx.kt], ctx.dec[ctx.kt], ra_b, dec_b))}
    out["target"] = res["hosts"][C.GAIA_TARGET]
    out["event_detected_dimming_snr_ge_3"] = bool(res["bestp_A"] / res["bestp_sA"] >= 3)
    for mode, mk in (("signed", "chi2"), ("dimming", "chi2p")):
        dmap = res["_maps"][mk] - np.nanmin(res["_maps"][mk])
        step = ctx.fitter.goff[1] - ctx.fitter.goff[0]
        reg = {}
        for lvl, thr in D2.items():
            sel = dmap <= thr
            reg[lvl] = {"area_px2": float(sel.sum() * step * step),
                        "touches_grid_edge": bool(sel[0, :].any() or sel[-1, :].any() or sel[:, 0].any() or sel[:, -1].any())}
        out[f"{mode}_regions"] = reg
    hs = {}
    for sid, h in res["hosts"].items():
        hh = dict(h)
        hh["inside_dimming"] = {lvl: bool(h["dchi2p_vs_free"] <= thr) for lvl, thr in D2.items()}
        hh["inside_signed"] = {lvl: bool(h["dchi2_vs_free"] <= thr) for lvl, thr in D2.items()}
        k = ctx.ids.index(sid)
        hh["flux_e_s"] = float(ctx.flux_of(k))
        hh["sep_px"] = float(np.hypot(ctx.x[k] - ctx.xt, ctx.y[k] - ctx.yt))
        hh["tmag"] = ctx.cat[k]["tmag"]
        hh["aperture_fraction"] = ctx.aperture_fraction(ctx.x[k], ctx.y[k])
        hs[sid] = hh
    out["hosts"] = hs
    return out


def run_event(eid, cat, recipe=None, eph=None, prf_kind="tess", gauss_sigma=None, save=True, tag="primary"):
    ctx = core.EventContext(eid, cat=cat, scene_json=SCENE, prf_kind=prf_kind, gauss_sigma=gauss_sigma)
    eph = core.EA if eph is None else eph
    tc = core.tc_of(eph, ctx.n)
    hosts = ctx.fixed_host_indices()
    rec = dict(core.PRIMARY_RECIPE) if recipe is None else recipe
    res = core.analyse(ctx, tc, eph["duration_d"], kappa=KAPPA[ctx.sector], host_idx=hosts, keep_maps=True, **rec)
    summ = event_summary(ctx, res)
    summ.update({"eid": eid, "sector": ctx.sector, "tag": tag, "recipe": rec, "ephemeris": eph.get("name"),
                 "prf": prf_kind if prf_kind == "tess" else f"gauss_sigma_{gauss_sigma}",
                 "target_xy": [float(ctx.xt), float(ctx.yt)], "fit_box": list(ctx.fitter.box)})
    if save:
        di = res["_di"]
        sig = di["sigma"] * KAPPA[ctx.sector]
        f = ctx.fitter
        model_b, resid_b, _ = f.model_image(di["D"], sig, res["bestp_x"], res["bestp_y"])
        model_t, resid_t, _ = f.model_image(di["D"], sig, ctx.xt, ctx.yt)
        ser = diffimg.series(ctx.S, di["role"], tc, ctx.ap, (ctx.xt, ctx.yt))
        X = np.vstack([di["grad_x"][f.rows, f.cols], di["grad_y"][f.rows, f.cols], f.Q.T]).T
        w = 1.0 / sig[f.rows, f.cols] ** 2
        sw = np.sqrt(w)
        coef, *_ = np.linalg.lstsq(X * sw[:, None], di["D"][f.rows, f.cols] * sw, rcond=None)
        cov = np.linalg.inv((X * w[:, None]).T @ X)
        summ["motion_diagnostic"] = {"shift_col_px": float(-coef[0]), "shift_row_px": float(-coef[1]),
                                     "err_col_px": float(np.sqrt(cov[0, 0])), "err_row_px": float(np.sqrt(cov[1, 1])),
                                     "note": "apparent in-minus-out pointing shift that would mimic D through the scene gradient"}
        np.savez_compressed(ARR / f"{eid}_{tag}.npz", D=di["D"], sigma=sig, out=di["out"], inn=di["in"],
                            chi2=res["_maps"]["chi2"], chi2p=res["_maps"]["chi2p"], A=res["_maps"]["A"], sA=res["_maps"]["sA"],
                            grid_x=f.grid_x, grid_y=f.grid_y, model_best=model_b, resid_best=resid_b,
                            model_target=model_t, resid_target=resid_t, role=di["role"],
                            ser_time=ser["time"], ser_role=ser["role"], ser_dt_h=ser["dt_h"], ser_ap=ser["ap_sum"],
                            ser_box3=ser["box3_sum"], ser_bkg=ser["bkg_med"], ser_cx=ser["cen_x"], ser_cy=ser["cen_y"],
                            ser_sap=ser.get("sap_flux", np.array([])), ser_pdc=ser.get("pdcsap_flux", np.array([])),
                            ser_sapbkg=ser.get("sap_bkg", np.array([])), ap=ctx.ap, box=np.array(f.box),
                            xs=ctx.x, ys=ctx.y)
    return ctx, res, summ


def main():
    cat = Sc.load_catalogue()
    ctxs, ress, summ = {}, {}, {}
    for eid in ("E00", "E32", "E33", "E39"):
        ctx, res, s = run_event(eid, cat)
        ctxs[eid], ress[eid], summ[eid] = ctx, res, s
        t, b, bs = s["target"], s["dimming_best"], s["signed_best"]
        print(eid, "target A=%.2f+-%.2f S/N %.2f | dimming best off %.2f px A=%.2f S/N %.2f impr %.2f | signed best off %.2f A=%.2f S/N %.2f" %
              (t["A"], t["sA"], t["snr"], b["offset_px"], b["A"], b["snr"], s["freep_improvement"], bs["offset_px"], bs["A"], bs["snr"]))
        for sid, h in s["hosts"].items():
            print("    host %s sep %.2f px T=%.2f f=%.1f eps_ap=%.3f A=%.2f+-%.2f dchi2p %.2f in95 %s" %
                  (sid, h["sep_px"], h["tmag"], h["flux_e_s"], h["aperture_fraction"], h["A"], h["sA"],
                   h["dchi2p_vs_free"], h["inside_dimming"]["95.45"]))
    ra0 = float(np.mean([ctxs[e].ra[ctxs[e].kt] for e in core.PRIMARY]))
    dec0 = float(np.mean([ctxs[e].dec[ctxs[e].kt] for e in core.PRIMARY]))
    sky = JF.sky_setup(ctxs, ra0, dec0)
    rng = np.random.default_rng(core.CFG["controls"]["seed"])
    jout = {"origin": {"ra0": ra0, "dec0": dec0, "grid_half_arcsec": 85.0, "grid_step_arcsec": 1.0}}
    arrays = {}
    for mode in ("dimming", "signed"):
        J = JF.joint(ctxs, ress, core.PRIMARY, sky, mode=mode, reg_draws=200, rng=rng, keep_maps=True)
        loo = {f"without_{d}": JF.joint(ctxs, ress, [e for e in core.PRIMARY if e != d], sky, mode=mode, keep_maps=True)
               for d in core.PRIMARY}
        single = {e: JF.joint(ctxs, ress, [e], sky, mode=mode, keep_maps=True) for e in ("E00", "E32", "E33", "E39")}
        jout[mode] = {"primary": JF.strip(J), "leave_one_out": {k: JF.strip(v) for k, v in loo.items()},
                      "single_event": {k: JF.strip(v) for k, v in single.items()}}
        arrays[f"{mode}_tot"] = J["_tot"]; arrays[f"{mode}_marg"] = J["_marg"]
        for k, v in loo.items():
            arrays[f"{mode}_{k}"] = v["_tot"]
        for k, v in single.items():
            arrays[f"{mode}_single_{k}"] = v["_tot"]
        b = J["best"]
        print("JOINT[%s] best xi,eta = %.1f, %.1f arcsec  impr vs null %.2f  Q=%.2f (p=%.3g) edge %s" %
              (mode, b["xi"], b["eta"], J["free_improvement"], J["Q_consistency"], J["Q_p"], J["best_on_grid_edge"]))
        print("   areas", J["region_area_arcsec2"], "marg", J["registration_mc"]["marginal_region_area_arcsec2"])
        for sid, h in J["hosts"].items():
            print("   host %s dchi2_free %.2f dchi2_bestcat %.2f A=%.2f+-%.2f S/N %.2f in95 %s regMC med %.2f p05 %.2f" %
                  (sid, h["dchi2_vs_free"], h["dchi2_vs_best_catalogue"], h["A_weighted"], h["sA_weighted"],
                   h["snr_weighted"], h["inside"]["95.45"], J["registration_mc"]["host_dchi2_vs_free_median"][sid],
                   J["registration_mc"]["host_dchi2_vs_free_p05"][sid]))
        for k, v in loo.items():
            print("   ", k, "best %.1f,%.1f impr %.2f" % (v["best"]["xi"], v["best"]["eta"], v["free_improvement"]),
                  {s[-6:]: round(h["dchi2_vs_best_catalogue"], 2) for s, h in v["hosts"].items()})
    np.savez_compressed(ARR / "joint_maps.npz", xi=sky["xi"], eta=sky["eta"], **arrays)
    C.write_json(C.RESULTS / "joint.json", C.clean(jout))
    C.write_json(C.RESULTS / "real_events.json", C.clean(summ))
    # ------------------------------------------------ predeclared sensitivity runs
    sens = {}
    gs = {e: SCENE["events"][e]["gauss_best_sigma"] for e in core.EVENTS}
    variants = {
        "S_EF_windows": dict(eph=core.EF),
        "S_quadratic_baseline": dict(recipe={"deg": 2, "noise": "p2p", "bkg_regressor": True}),
        "S_V0_original_recipe": dict(recipe={"deg": 1, "noise": "mad", "bkg_regressor": False}),
        "S_gaussian_prf": dict(prf_kind="gauss"),
    }
    for name, kw in variants.items():
        cx, rx, sx = {}, {}, {}
        for eid in ("E00", "E32", "E33", "E39"):
            kk = dict(kw)
            if kk.get("prf_kind") == "gauss":
                kk["gauss_sigma"] = gs[eid]
            ctx, res, s = run_event(eid, cat, save=False, tag=name, **kk)
            cx[eid], rx[eid], sx[eid] = ctx, res, s
        skys = JF.sky_setup(cx, ra0, dec0)
        sens[name] = {"events": {e: {"target_A": sx[e]["target"]["A"], "target_sA": sx[e]["target"]["sA"],
                                     "target_snr": sx[e]["target"]["snr"], "dimming_best": sx[e]["dimming_best"],
                                     "signed_best": sx[e]["signed_best"], "freep_improvement": sx[e]["freep_improvement"],
                                     "host_dchi2p_vs_free": {sid: h["dchi2p_vs_free"] for sid, h in sx[e]["hosts"].items()}}
                                 for e in sx}}
        for mode in ("dimming", "signed"):
            Js = JF.joint(cx, rx, core.PRIMARY, skys, mode=mode)
            sens[name][f"joint_{mode}"] = JF.strip(Js)
        Jd = sens[name]["joint_dimming"]
        print("SENS", name, "dimming joint best %.1f,%.1f impr %.2f" % (Jd["best"]["xi"], Jd["best"]["eta"], Jd["free_improvement"]),
              {s[-6:]: (round(h["dchi2_vs_best_catalogue"], 2), round(h["snr_weighted"], 2)) for s, h in Jd["hosts"].items()})
    C.write_json(C.RESULTS / "sensitivity.json", C.clean(sens))


if __name__ == "__main__":
    main()
