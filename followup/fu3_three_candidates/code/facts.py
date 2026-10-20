"""Collect the key numbers for the report into results/facts.json (and print a compact digest)."""
from fu3_common import *


def g(d, *ks, default=None):
    for k in ks:
        if isinstance(d, dict) and k in d:
            d = d[k]
        elif isinstance(d, list) and isinstance(k, int) and k < len(d):
            d = d[k]
        else:
            return default
    return d


def main():
    F = {}
    for tic in TICS:
        f = {}
        prov = read(RES / f"s00_provenance_{tic}.json")
        a = prov["ephemerides"]["fit_adopted"]
        f["adopted"] = {k: a.get(k) for k in ("period", "period_err", "t0_btjd", "t0_err", "t14_hours", "b", "rp_rs", "rp_rearth", "rp_rearth_err")}
        f["stellar"] = prov["ephemerides"]["fit_stellar"]
        f["free_fit"] = prov["ephemerides"]["fit_free"]
        f["sectors_used"] = [(p["sector"], p["author"], int(p["cadence_s"])) for p in prov["products_used"]]
        f["stageA"] = prov["stageA_n"]
        eph = read(RES / f"s03_ephemeris_{tic}.json")
        f["frozen_ephemeris"] = {k: eph[k] for k in ("P", "T_nref", "nref", "inflation", "chi2", "dof", "n_events")}
        f["frozen_ephemeris"]["sig_P"] = float(np.sqrt(eph["cov_inflated_d2"][1][1]))
        f["frozen_ephemeris"]["sig_T_min"] = float(np.sqrt(eph["cov_inflated_d2"][0][0]) * 1440)
        dec = read(RES / f"s01b_decompose_{tic}.json")
        f["decomposition"] = {k: dict(prior=v["prior_reported_snr"], reproduced=v["reproduced"]["snr"],
                                      late_at_reference=v["late_at_reference"]["snr"], epoch_only=v["early_epoch_only"]["snr"],
                                      early_dP_min_per_cycle=v["early_fit"]["period_corr_d"] * 1440,
                                      early_sectors=v["early_sectors"], late_sectors=v["late_sectors"])
                              for k, v in dec.items() if k in ("corrected", "aperture")}
        ev = read(RES / f"s02_events_{tic}.json")
        f["pooled"] = {red: {k: g(s, "pooled", k) for k in ("n", "depth_ppt", "err_ppt", "snr", "p_const", "n_positive")}
                       for red, s in ev["summary"].items() if s.get("status") == "OK"}
        px = read(RES / f"s07b_summary_{tic}.json")
        f["fu3pix"] = {red: {k: g(v, "pooled", k) for k in ("n", "depth_ppt", "err_ppt", "snr", "p_const", "n_positive")} for red, v in px.items()}
        pxs = read(RES / f"s07b_pixels_{tic}.json")
        f["pixel_sectors"] = [(s["sector"], s.get("status"), round(g(s, "scene", "frac_rms", default=float("nan")) or float("nan"), 4)) for s in pxs["sectors"]]
        cal = read(RES / f"s03_calibration_{tic}.json")
        f["null_single_event"] = {red: dict(frac_ge_median_real=v["null"]["frac_depth_ge_median_real"], z_std=v["null"]["z_robust_std"], n=v["null"]["n"])
                                  for red, v in cal["reductions"].items()}
        f["timing_cal_z"] = {red: {c: g(x, "timing", "robust_std_of_z") for c, x in v["injection_adopted_shape"]["by_cadence"].items()}
                             for red, v in cal["reductions"].items()}
        f["timing_cal_z_grazing"] = {red: {c: g(x, "timing", "robust_std_of_z") for c, x in v["injection_grazing_shape"]["by_cadence"].items()}
                                     for red, v in cal["reductions"].items()}
        oc = read(RES / f"s04_oc_{tic}.json")
        f["oc"] = {red: dict(n=v["n"], formal_lin=(v["formal"]["linear"]["chi2"], v["formal"]["linear"]["dof"]),
                             formal_season_dchi2=v["formal"]["delta_chi2_seasons_vs_linear"],
                             cal_adopted_lin=v["calibrated_adopted"]["linear"]["chi2"],
                             cal_adopted_season_dchi2=v["calibrated_adopted"]["delta_chi2_seasons_vs_linear"],
                             cal_grazing_lin=v["calibrated_grazing"]["linear"]["chi2"],
                             cal_grazing_season_dchi2=v["calibrated_grazing"]["delta_chi2_seasons_vs_linear"],
                             loo_min_grazing=min([x["delta_chi2_seasons"] for x in v["calibrated_grazing"]["leave_one_sector_out"]] or [None], key=lambda z: (z is None, z)),
                             loo_min_adopted=min([x["delta_chi2_seasons"] for x in v["calibrated_adopted"]["leave_one_sector_out"]] or [None], key=lambda z: (z is None, z)),
                             season_offsets=v["formal"]["season_offsets"]["params"],
                             season_offset_err_cal=v["calibrated_adopted"]["season_offsets"]["param_err"])
                   for red, v in oc["reductions"].items()}
        f["ttv_null"] = {}
        for p in sorted(RES.glob(f"s16_ttv_null_{tic}_*.json")):
            if "STALE" in p.name:
                continue
            d = read(p)
            f["ttv_null"][d["reduction"]] = dict(n_null=d["n_null"], obs_dchi2=d["observed"]["dchi2_seasons"], tail_dchi2=d["tail_dchi2_seasons"],
                                                 obs_coh=d["observed"]["coherence"]["stat"], tail_coh=d["tail_coherence"],
                                                 null_coh_max=g(d, "null_coherence_quantiles", "max"),
                                                 null_dchi2=d["null_dchi2_quantiles"], obs_chi2red=d["observed"]["chi2red_linear"],
                                                 null_chi2red=d["null_chi2red_quantiles"])
        sec = read(RES / f"s10_secondary_2p_{tic}.json")
        f["secondary"] = {red: dict(odd=g(v, "odd", "depth_ppt"), even=g(v, "even", "depth_ppt"), oe_sig=v.get("odd_even_sigma"),
                                    half=g(v, "half_phase", "depth_ppt"), half_err=g(v, "half_phase", "err_ppt"), half_n=g(v, "half_phase", "n"),
                                    p_half=g(v, "null", "p_half_depth"), null_p95=g(v, "null", "depth_p95"))
                          for red, v in sec["reductions"].items() if "primary" in v}
        sh = read(RES / f"s11_shape_{tic}_pdc_raw.json")
        f["shape"] = {}
        for mode in ("linear", "season"):
            a2 = sh[mode]["A_planet_free"]
            c2 = sh[mode]["A_planet_rho_cat"]
            big = [p for p in sh[mode]["B_k_profile_diluted"] if p["k"] >= 0.3]
            occ = sh[mode]["C_large_occultor_undiluted"]
            f["shape"][mode] = dict(k=a2["k"], b=a2["b"], rho_eff=a2["rho_eff"], e_min=a2["e_min"], chi2=a2["chi2"],
                                    dchi2_rho_cat=c2["chi2"] - a2["chi2"], dchi2_k_ge_0p3=min(p["delta_chi2"] for p in big),
                                    dchi2_occultor=min(o["delta_chi2"] for o in occ), e_min_occultor=min(o["e_min"] for o in occ),
                                    offsets=a2.get("offsets_min"))
        if tic == 270573718:
            shp = read(RES / f"s11_shape_{tic}_fu3pix_annulus_circ1p5.json")
            f["shape_pixel"] = {}
            for mode in ("linear", "season"):
                a2 = shp[mode]["A_planet_free"]
                c2 = shp[mode]["A_planet_rho_cat"]
                big = [p for p in shp[mode]["B_k_profile_diluted"] if p["k"] >= 0.3]
                occ = shp[mode]["C_large_occultor_undiluted"]
                f["shape_pixel"][mode] = dict(k=a2["k"], b=a2["b"], rho_eff=a2["rho_eff"], chi2=a2["chi2"],
                                              dchi2_rho_cat=c2["chi2"] - a2["chi2"], dchi2_k_ge_0p3=min(p["delta_chi2"] for p in big),
                                              dchi2_occultor=min(o["delta_chi2"] for o in occ), offsets=a2.get("offsets_min"))
        mc = read(RES / f"s17_mcmc_{tic}.json")
        f["mcmc"] = {pr: dict(rp=r["rp_rearth"], b=r["b"], k=r["k"], rho=r["rho_eff"], e_min=r["e_min"], P_b_gt_0p8=r["frac_b_gt_0p8"])
                     for pr, r in mc["runs"].items()}
        loc = read(RES / f"s07c_localize_{tic}.json")
        f["localization"] = {gid: dict(obs=v["observed_sum_delta_chi2_diag"], n_sectors=v["n_sectors"],
                                       tgt=g(v, "injection_distributions", "true_target_mission"),
                                       nb=g(v, "injection_distributions", "true_neighbour_mission"),
                                       nb_broad=g(v, "injection_distributions", "true_neighbour_broadened"))
                             for gid, v in loc["combined"].items()}
        f["free_fit_offsets_arcsec"] = [(s["sector"], round(s["free_fit_offset_arcsec"], 1)) for s in loc["sectors"]]
        fb = read(RES / f"s13_fluxbudget_{tic}.json")
        f["flux_budget"] = dict(depth=fb["depth_obs_raw_ppt"], unresolved=fb["unresolved_contaminant_max_dT"],
                                ranked=[{k: r.get(k) for k in ("id", "sep_arcsec", "dT", "eclipse_needed", "verdict")} for r in fb["neighbours_ranked"][:8]])
        F[str(tic)] = f
    F["fpp"] = read(RES / "s12_fpp_audit.json")
    F["rv"] = read(RES / "s15_rv_limits.json")
    z = read(RES / "s14_ztf_193718989.json")
    F["ztf"] = {gid: {k: v.get(k) for k in ("sep_arcsec", "n_clean", "bands", "required_eclipse_fraction_TESS", "n_nominal_in_window",
                                             "n_core", "core_weighted_flux_ratio", "grid_excluded_fraction_f_ge_0p5", "censoring")}
                for gid, v in z["neighbours"].items()}
    F["timestamp_control"] = {s: g(v, "ffi_minus_2min") and {k: v["ffi_minus_2min"][k] for k in ("n", "weighted_mean_min", "err_min")}
                              for s, v in read(RES / "s06_timestamp_control.json")["sectors"].items()}
    F["s262_offsilicon"] = read(RES / "s09_262_s31_s88.json")
    save(RES / "facts.json", F)
    print("facts written", len(json.dumps(clean(F))))


if __name__ == "__main__":
    main()

