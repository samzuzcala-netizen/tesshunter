"""Apply the predeclared decision criteria (config.json) to the real joint fit,
using the null/injection calibrations, and assess every host hypothesis.

Writes results/decision.json, results/host_assessment.json and neighbours.csv
(regenerated with assessment columns).
"""
from __future__ import annotations

import csv
import json

import common as C
import numpy as np

import core
import scene as Sc

R = C.RESULTS
CFG = json.load(open(C.WS / "config.json"))
REAL = json.load(open(R / "real_events.json"))
JOINT = json.load(open(R / "joint.json"))
CTRL = json.load(open(R / "controls_full_summary.json"))
SCENE = json.load(open(R / "scene.json"))
STAGEA = json.load(open(C.PACKET / "stageA.json"))
D95, D997 = 6.18, 11.83


def lc_depths():
    ev = {e["n"]: e for e in STAGEA["per_ephemeris"]["survey"]["events"]}
    k = STAGEA["per_ephemeris"]["survey"]
    return {"PDCSAP_kept": (k["det_kept"]["weighted_mean_depth_ppt"], k["det_kept"]["err_ppt"]),
            "SAP_kept": (k["sap_kept"]["weighted_mean_depth_ppt"], k["sap_kept"]["err_ppt"]),
            "per_event": {f"E{n:02d}": {"pdc": (ev[n]["det_depth_ppt"], ev[n]["det_depth_err_ppt"]),
                                         "sap": (ev[n]["sap_depth_ppt"], ev[n]["sap_depth_err_ppt"])} for n in (0, 32, 33, 39)}}


def main():
    jd = JOINT["dimming"]["primary"]
    js = JOINT["signed"]["primary"]
    nulls = [json.loads(l) for l in open(R / "controls_full" / "null_joint.jsonl")]
    nsing = [json.loads(l) for l in open(R / "controls_full" / "null_single.jsonl")]
    lam = np.array([r["Lambda_dimming"] for r in nulls]); Q = np.array([r["Q_dimming"] for r in nulls])
    tsn = np.array([r["target_snr_joint"] for r in nulls])
    lam99 = CTRL["null_joint_Lambda_dimming_p99"]
    tgt = jd["hosts"][C.GAIA_TARGET]
    real_lam = jd["free_improvement"]
    det = {"target_snr_joint": tgt["snr_weighted"], "target_snr_ge_3": tgt["snr_weighted"] >= 3,
           "null_frac_target_snr_ge_real": float(np.mean(tsn >= tgt["snr_weighted"])), "n_null": int(tsn.size),
           "Lambda_real": real_lam, "Lambda_null_p99": lam99, "Lambda_gt_p99": real_lam > lam99,
           "null_frac_Lambda_ge_real": float(np.mean(lam >= real_lam))}
    det["pixel_detection"] = bool(det["target_snr_ge_3"] and det["Lambda_gt_p99"])
    # per-event look-elsewhere-calibrated detection p-values
    ev_det = {}
    for e, sec in (("E00", 57), ("E32", 79), ("E33", 80)):
        b = np.array([r["bestp_snr"] for r in nsing if r["sector"] == sec])
        s = REAL[e]["dimming_best"]["snr"]
        ev_det[e] = {"dimming_best_snr": s, "offset_from_target_px": REAL[e]["dimming_best"]["offset_px"],
                     "descriptive_detected_snr_ge_3": bool(s >= 3),
                     "null_frac_ge": float(np.mean(b >= s)), "n_null": int(b.size),
                     "calibrated_detected_p_lt_0.01": bool(np.mean(b >= s) < 0.01),
                     "target_snr": REAL[e]["target"]["snr"]}
    q_real = jd["Q_consistency"]
    incons = {"Q_real": q_real, "Q_dof": jd["Q_dof"], "Q_p_formal_chi2": jd["Q_p"],
              "Q_null_frac_ge_real": float(np.mean(Q >= q_real)), "Q_null_median": float(np.median(Q)),
              "n_descriptively_detected": sum(v["descriptive_detected_snr_ge_3"] for v in ev_det.values()),
              "n_calibrated_detected": sum(v["calibrated_detected_p_lt_0.01"] for v in ev_det.values())}
    incons["fires_formal"] = bool(incons["n_descriptively_detected"] >= 2 and (incons["Q_p_formal_chi2"] or 1) < 0.01)
    incons["fires_calibrated"] = bool(incons["n_calibrated_detected"] >= 2 and incons["Q_null_frac_ge_real"] < 0.01)
    inj = CTRL["injections"]
    calib = {"target_LC": {k: inj["target_LC"][k] for k in ("coverage", "assigned_to_true_host", "all_other_hosts_excluded_dchi2_ge_9", "pixel_detected")},
             "target_PIX": {k: inj["target_PIX"][k] for k in ("coverage", "assigned_to_true_host", "all_other_hosts_excluded_dchi2_ge_9", "pixel_detected")}}
    calib["coverage95_target_PIX"] = inj["target_PIX"]["coverage"]["95.45"]["frac"]
    calib["confusion_target_PIX_to_neighbour"] = 1 - inj["target_PIX"]["assigned_to_true_host"]["frac"]
    calib["coverage95_target_LC"] = inj["target_LC"]["coverage"]["95.45"]["frac"]
    calib["confusion_target_LC_to_neighbour"] = 1 - inj["target_LC"]["assigned_to_true_host"]["frac"]
    calib["adequate_at_observed_amplitude"] = bool(calib["coverage95_target_PIX"] >= 0.85 and calib["confusion_target_PIX_to_neighbour"] <= 0.05)
    calib["adequate_at_LC_amplitude"] = bool(calib["coverage95_target_LC"] >= 0.85 and calib["confusion_target_LC_to_neighbour"] <= 0.05)
    # --------------------------------------------------------- host assessment
    depths = lc_depths()
    cat = Sc.load_catalogue()
    by_id = {c["source_id"]: c for c in cat}
    loo = JOINT["dimming"]["leave_one_out"]
    rows = []
    for sid in core.HOSTS:
        h = jd["hosts"][sid]
        c = by_id[sid]
        # spatial: joint dchi2 relative to best catalogue host, and LOO
        loo_d = {k: v["hosts"][sid]["dchi2_vs_best_catalogue"] for k, v in loo.items()}
        spatial_excluded = bool(h["dchi2_vs_best_catalogue"] >= 9 and sum(d >= 4 for d in loo_d.values()) >= 2)
        # flux (predeclared): pixel-fit amplitude vs host flux, per event then weighted
        f_ev, eps_ev, A_req = {}, {}, {"pdc": {}, "sap": {}}
        for e in core.PRIMARY:
            rh = REAL[e]["hosts"][sid]
            f_ev[e] = rh["flux_e_s"]; eps_ev[e] = rh["aperture_fraction"]
            ft = REAL[e]["hosts"][C.GAIA_TARGET]["flux_e_s"]; et = REAL[e]["hosts"][C.GAIA_TARGET]["aperture_fraction"]
            for kind, key in (("pdc", "PDCSAP_kept"), ("sap", "SAP_kept")):
                d, de = depths[key]
                A_req[kind][e] = (d / 1000.0 * ft * et / max(rh["aperture_fraction"], 1e-6),
                                  de / 1000.0 * ft * et / max(rh["aperture_fraction"], 1e-6))
        f_mean = float(np.mean(list(f_ev.values())))
        e_tmag = c["e_tmag"] if sid != C.GAIA_TARGET else 0.05
        sig_ln_f = 0.921 * e_tmag
        frac = h["A_weighted"] / f_mean
        frac_err = np.hypot(h["sA_weighted"] / f_mean, frac * sig_ln_f)
        flux_infeasible_pixel = bool(frac - 2 * frac_err > 1)
        # light-curve-matched requirement (inverse-variance mean over the 3 events) and consistency with the pixels
        lc = {}
        for kind in ("pdc", "sap"):
            a = np.array([A_req[kind][e][0] for e in core.PRIMARY]); ae = np.array([A_req[kind][e][1] for e in core.PRIMARY])
            # 15% PRF-wing / aperture-throughput systematic on eps added in quadrature
            ae = np.hypot(ae, 0.15 * a)
            w = 1 / ae ** 2
            am, sm = float(np.sum(a * w) / np.sum(w)), float(1 / np.sqrt(np.sum(w)))
            req_frac = am / f_mean
            req_frac_err = float(np.hypot(sm / f_mean, req_frac * sig_ln_f))
            tension = (am - h["A_weighted"]) / np.hypot(sm, h["sA_weighted"])
            lc[kind] = {"A_required_e_s": am, "A_required_err": sm, "required_eclipse_fraction": req_frac,
                        "required_eclipse_fraction_err": req_frac_err,
                        "infeasible_2sigma": bool(req_frac - 2 * req_frac_err > 1),
                        "pixel_vs_required_tension_sigma": float(tension)}
        rows.append({"gaia_dr3_source_id": sid, "role": "target" if sid == C.GAIA_TARGET else
                     ("listed neighbour" if sid in C.LISTED_NEIGHBOURS else "additional catalogue source (<=3.6 px)"),
                     "tic_id": c["tic_id"], "G": c["G"], "tmag": c["tmag"], "tmag_source": c["tmag_src"], "e_tmag": e_tmag,
                     "sep_arcsec_epoch2024": float(Sc.sep_arcsec(by_id[C.GAIA_TARGET]["ra"], by_id[C.GAIA_TARGET]["dec"], c["ra"], c["dec"])),
                     "sep_px": {e: REAL[e]["hosts"][sid]["sep_px"] for e in core.PRIMARY},
                     "flux_e_s_mean": f_mean, "aperture_fraction": eps_ev,
                     "astrometric_params_solved": c["astrometric_params_solved"], "ruwe": c["ruwe"], "parallax_mas": c["parallax"],
                     "joint_dchi2_vs_free": h["dchi2_vs_free"], "joint_dchi2_vs_best_catalogue": h["dchi2_vs_best_catalogue"],
                     "loo_dchi2_vs_best_catalogue": loo_d, "inside_joint_95": h["inside"]["95.45"],
                     "per_event_dchi2p_vs_free": {e: REAL[e]["hosts"][sid]["dchi2p_vs_free"] for e in ("E00", "E32", "E33", "E39")},
                     "per_event_A": {e: [REAL[e]["hosts"][sid]["A"], REAL[e]["hosts"][sid]["sA"]] for e in ("E00", "E32", "E33", "E39")},
                     "pixel_A_joint": [h["A_weighted"], h["sA_weighted"]], "pixel_required_eclipse_fraction": [frac, float(frac_err)],
                     "spatially_excluded": spatial_excluded, "flux_infeasible_pixel_amplitude": flux_infeasible_pixel,
                     "lc_matched": lc,
                     "injection_same_missing_flux_target_excluded_frac": (inj.get(f"nb{sid[-6:]}_PIX", {}).get("all_other_hosts_excluded_dchi2_ge_9", {}) or {}).get("frac"),
                     })
    # --------------------------------------------------------- status
    crit = CFG["decision_criteria"]
    reasons = []
    status = None
    if not det["pixel_detection"]:
        reasons.append(f"no pixel detection under the predeclared rule: joint target S/N {det['target_snr_joint']:.2f} (>= 3, null fraction "
                       f"{det['null_frac_target_snr_ge_real']:.3f} of {det['n_null']}) but joint free-position improvement "
                       f"{real_lam:.1f} < null p99 {lam99:.1f} (null fraction >= real: {det['null_frac_Lambda_ge_real']:.3f})")
    t_in95 = jd["hosts"][C.GAIA_TARGET]["inside"]["95.45"]
    unsep = [r["gaia_dr3_source_id"] for r in rows if r["role"] != "target" and not r["spatially_excluded"]
             and not r["flux_infeasible_pixel_amplitude"] and min(r["sep_px"].values()) <= 3.0]
    if unsep:
        reasons.append(f"{len(unsep)} catalogue source(s) within 3 px neither spatially excluded (joint dchi2 >= 9 and >= 2/3 LOO >= 4) "
                       f"nor flux-infeasible on the pixel amplitude: {unsep}")
    if not t_in95:
        reasons.append(f"target outside the joint 95.45% dimming region (dchi2 vs free {jd['hosts'][C.GAIA_TARGET]['dchi2_vs_free']:.2f}); "
                       f"the free best ({jd['best']['xi']:.0f}\", {jd['best']['eta']:.0f}\") is driven by E32 (LOO without E32 moves it to "
                       f"({loo['without_E32']['best']['xi']:.0f}\", {loo['without_E32']['best']['eta']:.0f}\"))")
    if not calib["adequate_at_observed_amplitude"]:
        reasons.append(f"localisation calibration inadequate at the observed amplitude: target-hosted joint injections (A = pixel-matched) "
                       f"coverage95 {calib['coverage95_target_PIX']:.2f} (< 0.85), confusion {calib['confusion_target_PIX_to_neighbour']:.2f} (> 0.05)")
    if incons["fires_formal"] and not incons["fires_calibrated"]:
        reasons.append(f"INCONSISTENT_EVENTS not adopted: the formal chi2({incons['Q_dof']}) p = {incons['Q_p_formal_chi2']:.1e} is not valid for the "
                       f"look-elsewhere free fits (null Q median {incons['Q_null_median']:.1f}); calibrated null fraction with Q >= {q_real:.1f} is "
                       f"{incons['Q_null_frac_ge_real']:.3f}; only {incons['n_calibrated_detected']} event(s) individually detected at a calibrated p < 0.01")
    if det["pixel_detection"] and t_in95 and not unsep and calib["adequate_at_LC_amplitude"]:
        status = "TARGET_LOCALISED"
    elif incons["fires_calibrated"]:
        status = "INCONSISTENT_EVENTS"
    else:
        status = "UNRESOLVED"
    out = {"status": status, "status_reasons": reasons, "pixel_detection": det, "per_event_detection": ev_det,
           "inconsistency": incons, "calibration": calib, "criteria_text": crit,
           "answer": None}
    C.write_json(R / "decision.json", C.clean(out))
    C.write_json(R / "host_assessment.json", C.clean({"lc_depths_ppt": depths, "hosts": rows}))
    # neighbours.csv regenerated with the assessment columns
    keys = ["gaia_dr3_source_id", "role", "tic_id", "G", "tmag", "tmag_source", "e_tmag", "sep_arcsec_epoch2024", "sep_px_E00",
            "sep_px_E32", "sep_px_E33", "flux_e_s_mean", "astrometric_params_solved", "ruwe", "parallax_mas",
            "joint_dchi2_vs_best_catalogue", "joint_dchi2_vs_free", "loo_dchi2_without_E00", "loo_dchi2_without_E32",
            "loo_dchi2_without_E33", "spatially_excluded", "pixel_A_joint_e_s", "pixel_A_err", "pixel_required_eclipse_fraction",
            "flux_infeasible_pixel_amplitude", "lc_pdc_required_eclipse_fraction", "lc_pdc_infeasible_2sigma",
            "lc_pdc_pixel_tension_sigma", "lc_sap_required_eclipse_fraction", "lc_sap_infeasible_2sigma", "lc_sap_pixel_tension_sigma",
            "injection_same_missing_flux_target_excluded_frac"]
    with open(C.WS / "neighbours.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys)
        wr.writeheader()
        for r in rows:
            wr.writerow({"gaia_dr3_source_id": r["gaia_dr3_source_id"], "role": r["role"], "tic_id": r["tic_id"],
                         "G": round(r["G"], 3), "tmag": round(r["tmag"], 3), "tmag_source": r["tmag_source"], "e_tmag": r["e_tmag"],
                         "sep_arcsec_epoch2024": round(r["sep_arcsec_epoch2024"], 2),
                         "sep_px_E00": round(r["sep_px"]["E00"], 3), "sep_px_E32": round(r["sep_px"]["E32"], 3), "sep_px_E33": round(r["sep_px"]["E33"], 3),
                         "flux_e_s_mean": round(r["flux_e_s_mean"], 3), "astrometric_params_solved": r["astrometric_params_solved"],
                         "ruwe": r["ruwe"], "parallax_mas": r["parallax_mas"],
                         "joint_dchi2_vs_best_catalogue": round(r["joint_dchi2_vs_best_catalogue"], 2),
                         "joint_dchi2_vs_free": round(r["joint_dchi2_vs_free"], 2),
                         "loo_dchi2_without_E00": round(r["loo_dchi2_vs_best_catalogue"]["without_E00"], 2),
                         "loo_dchi2_without_E32": round(r["loo_dchi2_vs_best_catalogue"]["without_E32"], 2),
                         "loo_dchi2_without_E33": round(r["loo_dchi2_vs_best_catalogue"]["without_E33"], 2),
                         "spatially_excluded": r["spatially_excluded"], "pixel_A_joint_e_s": round(r["pixel_A_joint"][0], 3),
                         "pixel_A_err": round(r["pixel_A_joint"][1], 3),
                         "pixel_required_eclipse_fraction": round(r["pixel_required_eclipse_fraction"][0], 4),
                         "flux_infeasible_pixel_amplitude": r["flux_infeasible_pixel_amplitude"],
                         "lc_pdc_required_eclipse_fraction": round(r["lc_matched"]["pdc"]["required_eclipse_fraction"], 3),
                         "lc_pdc_infeasible_2sigma": r["lc_matched"]["pdc"]["infeasible_2sigma"],
                         "lc_pdc_pixel_tension_sigma": round(r["lc_matched"]["pdc"]["pixel_vs_required_tension_sigma"], 2),
                         "lc_sap_required_eclipse_fraction": round(r["lc_matched"]["sap"]["required_eclipse_fraction"], 3),
                         "lc_sap_infeasible_2sigma": r["lc_matched"]["sap"]["infeasible_2sigma"],
                         "lc_sap_pixel_tension_sigma": round(r["lc_matched"]["sap"]["pixel_vs_required_tension_sigma"], 2),
                         "injection_same_missing_flux_target_excluded_frac": r["injection_same_missing_flux_target_excluded_frac"]})
    print("STATUS", status)
    for r in reasons:
        print(" -", r)
    print(json.dumps(det)); print(json.dumps(ev_det)); print(json.dumps(incons)); print(json.dumps({k: v for k, v in calib.items() if not isinstance(v, dict)}))
    for r in rows:
        print(r["gaia_dr3_source_id"], r["role"][:6], "sep %.1f\"" % r["sep_arcsec_epoch2024"], "T %.2f f %.1f" % (r["tmag"], r["flux_e_s_mean"]),
              "| dchi2_bestcat %.2f LOO %s spat_excl %s" % (r["joint_dchi2_vs_best_catalogue"], {k[-3:]: round(v, 1) for k, v in r["loo_dchi2_vs_best_catalogue"].items()}, r["spatially_excluded"]),
              "| pixA %.2f+-%.2f frac %.3f infeas %s" % (r["pixel_A_joint"][0], r["pixel_A_joint"][1], r["pixel_required_eclipse_fraction"][0], r["flux_infeasible_pixel_amplitude"]),
              "| LC pdc frac %.2f+-%.2f inf %s tens %.1f | sap frac %.2f+-%.2f inf %s tens %.1f" % (
                  r["lc_matched"]["pdc"]["required_eclipse_fraction"], r["lc_matched"]["pdc"]["required_eclipse_fraction_err"],
                  r["lc_matched"]["pdc"]["infeasible_2sigma"], r["lc_matched"]["pdc"]["pixel_vs_required_tension_sigma"],
                  r["lc_matched"]["sap"]["required_eclipse_fraction"], r["lc_matched"]["sap"]["required_eclipse_fraction_err"],
                  r["lc_matched"]["sap"]["infeasible_2sigma"], r["lc_matched"]["sap"]["pixel_vs_required_tension_sigma"]))


if __name__ == "__main__":
    main()
