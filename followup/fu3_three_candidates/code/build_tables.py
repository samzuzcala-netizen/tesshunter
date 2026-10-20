"""Machine-readable deliverable tables (CSV) assembled from the FU3 result files.  No new measurement."""
import csv

import pandas as pd

from fu3_common import *

TAB = ROOT / "tables"
TAB.mkdir(exist_ok=True)


def w(name, rows):
    if not rows:
        return
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(TAB / name, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: r.get(k) for k in keys})


def events():
    rows = []
    for tic in TICS:
        for src in ("s02_events", "s07b_pixels"):
            d = read(RES / f"{src}_{tic}.json")
            for r in d["events"]:
                rows.append(dict(tic=tic, source=src, reduction=r.get("reduction"), sector=r.get("sector"), cycle=r.get("cycle"),
                                 tc_ref_btjd=r.get("tc_ref"), admitted=r.get("admitted"), reason=r.get("reason"),
                                 cadence_s=r.get("cad_s"), depth_ppt=r.get("depth_ppt"), depth_err_ppt=r.get("depth_err_ppt"),
                                 depth_deg2_ppt=r.get("depth_deg2_ppt"), beta=r.get("beta"),
                                 oc_min=(r["oc_d"] * 1440 if r.get("oc_d") is not None else None),
                                 oc_err_min=(r["oc_err_d"] * 1440 if r.get("oc_err_d") else None),
                                 timing_status=r.get("timing_status"), edge_distance_d=r.get("edge_distance_d"),
                                 desat_within_T14=r.get("desat_within_T14"), scene_pass=r.get("scene_pass")))
    w("event_table_all_reductions.csv", rows)
    return len(rows)


def pooled():
    rows = []
    for tic in TICS:
        d = read(RES / f"s02_events_{tic}.json")
        for red, s in d["summary"].items():
            p = s.get("pooled") or {}
            rows.append(dict(tic=tic, reduction=red, status=s.get("status"), n_admitted=s.get("n_admitted"),
                             **{k: p.get(k) for k in ("depth_ppt", "err_ppt", "snr", "p_const", "n_positive", "top_share_snr2")}))
        px = read(RES / f"s07b_pixels_{tic}.json")
        for red, s in px["summary"].items():
            p = s.get("pooled") or {}
            rows.append(dict(tic=tic, reduction=red, status="FU3_PIXEL", n_admitted=p.get("n"),
                             **{k: p.get(k) for k in ("depth_ppt", "err_ppt", "snr", "p_const", "n_positive", "top_share_snr2")}))
    w("pooled_depths.csv", rows)


def null_and_calibration():
    rows = []
    for tic in TICS:
        c = read(RES / f"s03_calibration_{tic}.json")
        for red, v in c["reductions"].items():
            for shape in ("injection_adopted_shape", "injection_grazing_shape"):
                for cad, x in v[shape]["by_cadence"].items():
                    t = x["timing"]
                    rows.append(dict(tic=tic, reduction=red, injected_shape=shape, cadence_s=cad, n=x["n"],
                                     timing_formal_median_min=t.get("median_formal_err_min"),
                                     timing_robust_std_min=t.get("robust_std_min"), timing_z_robust_std=t.get("robust_std_of_z"),
                                     depth_ratio_median=x["depth_ratio_median"]))
            n = v["null"]
            rows.append(dict(tic=tic, reduction=red, injected_shape="NULL_random_epochs", n=n["n"],
                             null_z_robust_std=n["z_robust_std"], null_frac_ge_median_real=n["frac_depth_ge_median_real"],
                             null_frac_z_ge_3=n["frac_z_ge_3"]))
    w("injection_null_calibration.csv", rows)
    rows = []
    for tic in TICS:
        for red in ("pdc_raw", "sap_raw", "fu3pix_annulus_circ1p5", "tglc_aperture"):
            p = RES / f"s16_ttv_null_{tic}.json"
        # s16 keeps only the last reduction per tic in one file; read every reduction's log line instead is fragile,
        # so s16 is re-read per file name convention below
    for p in sorted(RES.glob("s16_ttv_null_*.json")):
        if "STALE" in p.name:
            continue
        d = read(p)
        rows.append(dict(tic=d["tic"], reduction=d["reduction"], n_null=d["n_null"],
                         observed_dchi2_seasons=d["observed"]["dchi2_seasons"], tail_dchi2=d["tail_dchi2_seasons"],
                         observed_chi2red_linear=d["observed"]["chi2red_linear"], tail_chi2red=d["tail_chi2red_linear"],
                         observed_coherence_min=d["observed"]["coherence"]["stat"], tail_coherence=d.get("tail_coherence"),
                         null_coherence_max_min=(d.get("null_coherence_quantiles") or {}).get("max")))
    w("timing_null_tests.csv", rows)


def models():
    rows = []
    for tic in TICS:
        s = read(RES / f"s11_shape_{tic}_pdc_raw.json")
        for mode in ("linear", "season"):
            a = s[mode]["A_planet_free"]
            c = s[mode]["A_planet_rho_cat"]
            big = [p for p in s[mode]["B_k_profile_diluted"] if p["k"] >= 0.3]
            occ = s[mode]["C_large_occultor_undiluted"]
            rows.append(dict(tic=tic, mode=mode, chi2_planet_free=a["chi2"], k=a["k"], b=a["b"], rho_eff=a["rho_eff"],
                             rho_cat=s["stellar"]["rho_cgs"], e_min=a["e_min"], dchi2_rho_cat=c["chi2"] - a["chi2"],
                             dchi2_k_ge_0p3_min=min(p["delta_chi2"] for p in big) if big else None,
                             dchi2_undiluted_occultor_min=min(o["delta_chi2"] for o in occ) if occ else None,
                             e_min_undiluted_occultor=min(o["e_min"] for o in occ) if occ else None,
                             season_offsets_min=json.dumps(a.get("offsets_min"))))
        m = read(RES / f"s17_mcmc_{tic}.json")
        for prior, r in m["runs"].items():
            rows.append(dict(tic=tic, mode=f"mcmc_{prior}", k=r["k"]["p50"], k_p16=r["k"]["p16"], k_p84=r["k"]["p84"],
                             b=r["b"]["p50"], b_p16=r["b"]["p16"], b_p84=r["b"]["p84"], rho_eff=r["rho_eff"]["p50"],
                             rp_rearth=r["rp_rearth"]["p50"], rp_p16=r["rp_rearth"]["p16"], rp_p84=r["rp_rearth"]["p84"],
                             rp_p2_5=r["rp_rearth"]["p02.5"], rp_p97_5=r["rp_rearth"]["p97.5"], e_min=r["e_min"]["p50"],
                             frac_b_gt_0p8=r["frac_b_gt_0p8"], acceptance=r["acceptance"]))
    w("model_comparison.csv", rows)


def host():
    rows = []
    for tic in TICS:
        d = read(RES / f"s07c_localize_{tic}.json")
        fb = {r["id"]: r for r in read(RES / f"s13_fluxbudget_{tic}.json")["neighbours_ranked"]}
        for gid, v in d["combined"].items():
            dist = v["injection_distributions"]
            g = lambda k, f: dist.get(k, {}).get(f)  # noqa: E731
            rows.append(dict(tic=tic, gaia_id=gid, n_sectors=v["n_sectors"], observed_dchi2=v["observed_sum_delta_chi2_diag"],
                             observed_dchi2_cov=v["observed_sum_delta_chi2_cov"],
                             target_inj_median=g("true_target_mission", "median"), target_inj_p05=g("true_target_mission", "p05"),
                             target_inj_p95=g("true_target_mission", "p95"),
                             neighbour_inj_median=g("true_neighbour_mission", "median"), neighbour_inj_p95=g("true_neighbour_mission", "p95"),
                             neighbour_inj_broadened_p95=g("true_neighbour_broadened", "p95"),
                             sep_arcsec=fb.get(gid, {}).get("sep_arcsec"), dT=fb.get(gid, {}).get("dT"),
                             eclipse_needed=fb.get(gid, {}).get("eclipse_needed"), flux_verdict=fb.get(gid, {}).get("verdict")))
    w("host_localization.csv", rows)
    rows = []
    for tic in TICS:
        d = read(RES / f"s13_fluxbudget_{tic}.json")
        for r in d["neighbours_ranked"]:
            rows.append(dict(tic=tic, **{k: r.get(k) for k in ("id", "sep_arcsec", "G", "T", "T_method", "dT", "frac_psf_in_aperture",
                                                                 "aperture_flux_share", "eclipse_needed", "verdict", "sector")}))
        rows.append(dict(tic=tic, id="UNRESOLVED_CONTAMINANT", dT=d["unresolved_contaminant_max_dT"]["f_max_1"],
                         verdict=f"needs dT <= {d['unresolved_contaminant_max_dT']['f_max_1']:.2f} (100% eclipse) / "
                                 f"{d['unresolved_contaminant_max_dT']['f_max_0p5']:.2f} (50%)"))
    w("flux_budget.csv", rows)


def fpp():
    d = read(RES / "s12_fpp_audit.json")
    rows = []
    for tic, v in d.items():
        for run, x in v["runs"].items():
            f, ic = x["families"], x["image_conditioned"]
            rows.append(dict(tic=tic, run=run, package_fpp=x["package_fpp"], package_nfpp=x["package_nfpp"],
                             target_host_planet=f["target_planet"], STP=f["other_planets"]["STP"], BTP=f["other_planets"]["BTP"],
                             NTP=f["other_planets"]["NTP"], any_host_planet=f["any_host_planet"], stellar_eclipse=f["stellar_eclipse"],
                             image_conditioned_fpp=ic["fpp"], image_conditioned_nfpp=ic["nfpp"],
                             image_conditioned_target_planet=ic["target_planet"],
                             prior_reweight_fpp_min=(x["prior_sensitivity_fpp_range"] or [None, None])[0],
                             prior_reweight_fpp_max=(x["prior_sensitivity_fpp_range"] or [None, None])[1],
                             image_excluded_neighbour_tics=";".join(map(str, v["image_excluded_neighbour_tics"]))))
    w("fpp_scenario_audit.csv", rows)


def misc():
    rows = []
    for tic in TICS:
        d = read(RES / f"s10_secondary_2p_{tic}.json")
        for red, v in d["reductions"].items():
            if "primary" not in v:
                continue
            rows.append(dict(tic=tic, reduction=red, primary=v["primary"].get("depth_ppt"), odd=v["odd"].get("depth_ppt"),
                             even=v["even"].get("depth_ppt"), odd_even_sigma=v["odd_even_sigma"],
                             half_phase=v["half_phase"].get("depth_ppt"), half_phase_err=v["half_phase"].get("err_ppt"),
                             half_phase_n=v["half_phase"].get("n"), null_p_half=v["null"]["p_half_depth"],
                             null_p95=v["null"]["depth_p95"]))
    w("secondary_odd_even.csv", rows)
    r = read(RES / "s15_rv_limits.json")
    rows = []
    for tic, v in r.items():
        for case, c in (v.get("cases") or {}).items():
            rows.append(dict(tic=tic, case=case, sigma_epoch_kms=v.get("sigma_epoch_kms"), K95_kms=c["K95_kms"], Msini95_mjup=c["Mmin95_mjup"]))
        if v.get("status"):
            rows.append(dict(tic=tic, case=v["status"]))
    w("gaia_rv_limits.csv", rows)
    z = read(RES / "s14_ztf_193718989.json")
    rows = []
    for gid, v in z["neighbours"].items():
        rows.append(dict(gaia_id=gid, sep_arcsec=v["sep_arcsec"], n_clean=v["n_clean"], bands=json.dumps(v["bands"]),
                         required_eclipse=v["required_eclipse_fraction_TESS"], n_window=v["n_nominal_in_window"],
                         expected_window_if_no_eclipse=v["censoring"]["expected_in_window_if_no_eclipse"], n_core=v["n_core"],
                         core_flux_ratio=(v.get("core_weighted_flux_ratio") or {}).get("mean"),
                         core_flux_err=(v.get("core_weighted_flux_ratio") or {}).get("err"),
                         depth_upper95=(v.get("core_weighted_flux_ratio") or {}).get("depth_upper95"),
                         grid_excluded_f_ge_0p5=v["grid_excluded_fraction_f_ge_0p5"]))
    w("ztf_193718989.csv", rows)


def freeshape():
    """Per-event free-shape (trapezoid) times for TIC 270573718, unbounded (A1) and bounded (A3)."""
    rows = []
    for p in sorted(RES.glob("s19_freeshape_*.json")):
        d = read(p)
        for e in d["events"]:
            rows.append(dict(tic=d["tic"], reduction=d["reduction"], bounded=bool(d.get("bounded")), sector=e["sector"], cycle=e["cycle"],
                             status=e["status"], oc_min=(e["oc_d"] * 1440 if e.get("oc_d") is not None else None),
                             oc_err_min=(e["oc_err_d"] * 1440 if e.get("oc_err_d") is not None else None), depth_ppt=e.get("depth"),
                             t14_h=e.get("T14_h"), ingress_frac=e.get("ingress_frac"), edge=e.get("edge"), at_bound=e.get("at_bound"),
                             n_clipped=e.get("n_clipped")))
    if rows:
        w("freeshape_timing.csv", rows)


if __name__ == "__main__":
    n = events()
    pooled()
    null_and_calibration()
    models()
    host()
    fpp()
    misc()
    freeshape()
    log("tables", f"tables written; events rows {n}")
