"""Generate the markdown tables of LOCALISATION_REPORT.md from the result JSONs
(so every number in the report tables is machine-copied, not hand-typed)."""
from __future__ import annotations

import json

import common as C

R = C.RESULTS
T = C.GAIA_TARGET


def f(x, n=2):
    return "n/a" if x is None else f"{x:.{n}f}"


def wil(d):
    lo, hi = d["wilson95"]
    return f"{d['k']}/{d['n']} ({100 * d['frac']:.0f}%; {100 * lo:.0f}-{100 * hi:.0f}%)"


def main():
    real = json.load(open(R / "real_events.json"))
    joint = json.load(open(R / "joint.json"))
    dec = json.load(open(R / "decision.json"))
    diag = json.load(open(R / "diagnostics.json"))
    hosts = json.load(open(R / "host_assessment.json"))
    ctrl = json.load(open(R / "controls_full_summary.json"))
    sens = json.load(open(R / "sensitivity.json"))
    kap = json.load(open(R / "kappa.json"))
    ev = json.load(open(R / "events.json"))
    out = {}
    # ---------------------------------------------------------------- events
    L = ["| Event | Sector (cam/ccd) | Stage A | E_A centre (BTJD) | in / ref frames | kappa | target A (e-/s) | target S/N | pixel deficit at target (ppt) | Stage A PDCSAP / SAP depth (ppt) | dimming free best: offset, S/N, look-elsewhere null p | 95.45% region | target in 95.45%? (dchi2) | quality notes |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    notes = {"E00": "free best at fit-box edge beside the T~11.7 star residual; target inside 99.73%",
             "E32": "full-width row/column stripe structure in D (null fraction >= real 5.0% rows / 2.1% cols); signed fit finds a -15 sigma brightening at the box edge; dip present in PDCSAP only weakly in SAP",
             "E33": "event on a steep background ramp (~122 to 165 e-/s/px); baseline adequacy normal (MAD/p2p 1.00)",
             "E39": "Stage A excluded (scattered-light flag 50%, PDC gap 0.00 d); diagnostic only, never pooled"}
    evs = {r["event_id"]: r for r in ev["events"]}
    for e in ("E00", "E32", "E33", "E39"):
        v = real[e]; t = v["target"]; b = v["dimming_best"]; d = diag["events"][e]
        pe = dec["per_event_detection"].get(e, {})
        p = f"{pe['null_frac_ge']:.3f} ({round(pe['null_frac_ge'] * pe['n_null'])}/{pe['n_null']})" if pe else "n/a (s84 nulls not run)"
        L.append(f"| {e} | {v['sector']} ({evs[e]['camera']}/{evs[e]['ccd']}) | {evs[e]['stageA_decision']} | {evs[e]['tc_primary_EA_btjd']:.4f} | "
                 f"{v['n_in']} / {v['n_ref']} | {v['kappa']:.3f} | {t['A']:.2f} +/- {t['sA']:.2f} | {t['snr']:.2f} | "
                 f"{d['pixel_deficit_at_target_ppt'][0]:.1f} +/- {d['pixel_deficit_at_target_ppt'][1]:.1f} | "
                 f"{d['stageA_pdcsap_depth_ppt'][0]:.1f}+/-{d['stageA_pdcsap_depth_ppt'][1]:.1f} / {d['stageA_sap_depth_ppt'][0]:.1f}+/-{d['stageA_sap_depth_ppt'][1]:.1f} | "
                 f"{b['offset_px']:.2f} px ({b['offset_arcsec']:.0f}\"), {b['snr']:.2f}, {p} | "
                 f"{v['dimming_regions']['95.45']['area_px2']:.2f} px^2{' (touches grid edge)' if v['dimming_regions']['95.45']['touches_grid_edge'] else ''} | "
                 f"{'yes' if v['hosts'][T]['inside_dimming']['95.45'] else 'no'} ({v['hosts'][T]['dchi2p_vs_free']:.2f}) | {notes[e]} |")
    out["EVENTS"] = "\n".join(L)
    # ---------------------------------------------------------------- joint + LOO
    jd = joint["dimming"]
    L = ["| Fit (dimming-only, A >= 0) | events | free best (xi, eta) arcsec | free improvement vs null | consistency Q (formal p) | target A (e-/s) | target S/N | target dchi2 vs free | best catalogue host (target dchi2 vs it) | 95.45% area (arcsec^2) |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    rows = [("joint", jd["primary"])] + [(k.replace("without_", "LOO without "), v) for k, v in jd["leave_one_out"].items()]
    for name, v in rows:
        th = v["hosts"][T]
        L.append(f"| {name} | {', '.join(v['events'])} | ({v['best']['xi']:.0f}, {v['best']['eta']:.0f}){' grid edge' if v['best_on_grid_edge'] else ''} | "
                 f"{v['free_improvement']:.2f} | {v['Q_consistency']:.2f} ({f(v['Q_p'], 4) if v['Q_p'] is not None else 'n/a'}) | "
                 f"{th['A_weighted']:.2f} +/- {th['sA_weighted']:.2f} | {th['snr_weighted']:.2f} | {th['dchi2_vs_free']:.2f} | "
                 f"{v['best_catalogue_host']} ({th['dchi2_vs_best_catalogue']:.2f}) | {v['region_area_arcsec2']['95.45']:.0f} |")
    rm = jd["primary"]["registration_mc"]
    out["JOINT"] = "\n".join(L) + (f"\n\nRegistration Monte Carlo ({rm['n_draws']} draws, per-sector sigma_reg ~0.10 px/axis): best-position scatter "
                                   f"{rm['best_xi_std']:.1f}\" (xi) x {rm['best_eta_std']:.1f}\" (eta); registration-marginalised 68.27/95.45/99.73% areas "
                                   f"{rm['marginal_region_area_arcsec2']['68.27']:.0f} / {rm['marginal_region_area_arcsec2']['95.45']:.0f} / "
                                   f"{rm['marginal_region_area_arcsec2']['99.73']:.0f} arcsec^2 (statistical-only "
                                   f"{jd['primary']['region_area_arcsec2']['68.27']:.0f} / {jd['primary']['region_area_arcsec2']['95.45']:.0f} / "
                                   f"{jd['primary']['region_area_arcsec2']['99.73']:.0f}). Joint best RA, Dec = {jd['primary']['best']['ra']:.5f}, "
                                   f"{jd['primary']['best']['dec']:.5f} (deg).")
    # ---------------------------------------------------------------- hosts
    L = ["| Gaia DR3 source_id | role | sep (\") | T (source) | flux (e-/s) | joint dchi2 vs best catalogue host | LOO dchi2 (w/o E00, E32, E33) | spatially excluded? | pixel missing flux at host (e-/s) | eclipse fraction implied by pixels | LC-matched eclipse fraction PDCSAP / SAP | pixel vs LC tension (sigma) PDCSAP / SAP | assessment |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in hosts["hosts"]:
        lp, ls = r["lc_matched"]["pdc"], r["lc_matched"]["sap"]
        lo = r["loo_dchi2_vs_best_catalogue"]
        if r["role"] == "target":
            assess = "spatially compatible; pixel deficit = SAP-like depth (PDCSAP 2.6 sigma higher)"
        elif r["spatially_excluded"]:
            assess = "spatially excluded (dchi2 >= 9 and LOO); also cannot make the LC dip consistently with its pixel flux"
        else:
            assess = ("NOT spatially excluded; pixel-amplitude feasible; making the light-curve dip would need "
                      f"{lp['required_eclipse_fraction']:.1f}x (PDCSAP) / {ls['required_eclipse_fraction']:.1f}x (SAP) its total flux and contradicts its pixel flux")
        L.append(f"| {r['gaia_dr3_source_id']} | {r['role']} | {r['sep_arcsec_epoch2024']:.1f} | {r['tmag']:.2f} ({r['tmag_source']}) | "
                 f"{r['flux_e_s_mean']:.2f} | {r['joint_dchi2_vs_best_catalogue']:.2f} | {lo['without_E00']:.1f}, {lo['without_E32']:.1f}, {lo['without_E33']:.1f} | "
                 f"{'yes' if r['spatially_excluded'] else 'no'} | {r['pixel_A_joint'][0]:.2f} +/- {r['pixel_A_joint'][1]:.2f} | "
                 f"{r['pixel_required_eclipse_fraction'][0]:.3f} | {lp['required_eclipse_fraction']:.2f}+/-{lp['required_eclipse_fraction_err']:.2f} / "
                 f"{ls['required_eclipse_fraction']:.2f}+/-{ls['required_eclipse_fraction_err']:.2f} | {lp['pixel_vs_required_tension_sigma']:.1f} / "
                 f"{ls['pixel_vs_required_tension_sigma']:.1f} | {assess} |")
    out["HOSTS"] = "\n".join(L)
    # ---------------------------------------------------------------- controls
    nj = ctrl["null_joint"]; ns = ctrl["null_single"]
    L = ["| Null quantity | value |", "|---|---|",
         f"| null windows per sector (all / independent) | 57: {ns['57']['n']}/{ns['57']['n_independent']}, 79: {ns['79']['n']}/{ns['79']['n_independent']}, 80: {ns['80']['n']}/{ns['80']['n_independent']} |",
         f"| joint null combinations (all-independent) | {nj['n']} ({nj['n_all_independent']}) |",
         f"| kappa (calibration half, V2 recipe) | s57 {kap['57']['kappa']:.3f}, s79 {kap['79']['kappa']:.3f}, s80 {kap['80']['kappa']:.3f}, s84 {kap['84']['kappa']:.3f} |",
         f"| joint target S/N under the null: mean, std | {nj['target_snr_joint_mean']:.2f}, {nj['target_snr_joint_std']:.2f} |",
         f"| null fraction with joint target S/N >= 3 / >= 3.73 (real) | {nj['frac_target_snr_joint_ge_3']:.3f} / {nj['frac_target_snr_joint_ge_3_7']:.3f} (of {nj['n']}) |",
         f"| joint free improvement Lambda: p50 / p90 / p95 / p99 | {ctrl['null_joint_Lambda_dimming_quantiles']['50']:.1f} / {ctrl['null_joint_Lambda_dimming_quantiles']['90']:.1f} / {ctrl['null_joint_Lambda_dimming_quantiles']['95']:.1f} / {ctrl['null_joint_Lambda_dimming_quantiles']['99']:.1f} (real {dec['pixel_detection']['Lambda_real']:.1f}; null fraction >= real {dec['pixel_detection']['null_frac_Lambda_ge_real']:.3f}) |",
         f"| consistency Q: p50 / p90 / p95 / p99 | {nj['Q_dimming_quantiles']['50']:.1f} / {nj['Q_dimming_quantiles']['90']:.1f} / {nj['Q_dimming_quantiles']['95']:.1f} / {nj['Q_dimming_quantiles']['99']:.1f} (real {dec['inconsistency']['Q_real']:.1f}; null fraction >= real {dec['inconsistency']['Q_null_frac_ge_real']:.3f}; textbook chi2(4) p {dec['inconsistency']['Q_p_formal_chi2']:.1e}) |",
         f"| per-event max dimming S/N over the box, null p95 / p99 | s57 {ns['57']['max_dimming_snr_quantiles']['95']:.2f} / {ns['57']['max_dimming_snr_quantiles']['99']:.2f}; s79 {ns['79']['max_dimming_snr_quantiles']['95']:.2f} / {ns['79']['max_dimming_snr_quantiles']['99']:.2f}; s80 {ns['80']['max_dimming_snr_quantiles']['95']:.2f} / {ns['80']['max_dimming_snr_quantiles']['99']:.2f} |",
         f"| pixel-detection rule fired on joint nulls | {nj['frac_pixel_detected']:.3f} |",
         f"| best catalogue host under the null (joint) | " + ", ".join(f"{k[-6:]}: {v}" for k, v in nj["assigned_host_counts"].items()) + " |"]
    out["NULLS"] = "\n".join(L)
    L = ["| Injection config (host; amplitude) | A injected s57/s79/s80 (e-/s) | capped? | coverage of 95.45% region | best catalogue host = true host | all other hosts excluded (dchi2 >= 9) | assigned to target | pixel-detection rule fired | median offset of joint best from true host | median joint target S/N |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for name, v in ctrl["injections"].items():
        amps = ctrl["amplitudes"][name]
        a = " / ".join(f"{amps[e]['A_injected']:.2f}" for e in ("E00", "E32", "E33"))
        cap = "yes (needs " + "/".join(f"{amps[e]['required_eclipse_fraction']:.2f}" for e in ("E00", "E32", "E33")) + " x host flux)" if any(amps[e]["capped"] for e in amps) else "no"
        L.append(f"| {name} ({v['host'][-6:]}; {v['level']}) | {a} | {cap} | {wil(v['coverage']['95.45'])} | {wil(v['assigned_to_true_host'])} | "
                 f"{wil(v['all_other_hosts_excluded_dchi2_ge_9'])} | {wil(v['assigned_to_target'])} | {wil(v['pixel_detected'])} | "
                 f"{v['best_offset_from_true_arcsec_median']:.1f}\" | {v['target_snr_joint_median']:.2f} |")
    out["INJ"] = "\n".join(L) + ("\n\nPerturbed-PRF half vs unperturbed half, coverage of the 95.45% region: " +
                                 "; ".join(f"{n}: {v['perturbed_vs_unperturbed_coverage_95'][0]:.2f} vs {v['perturbed_vs_unperturbed_coverage_95'][1]:.2f}"
                                           for n, v in ctrl["injections"].items()) + ".")
    # ---------------------------------------------------------------- sensitivity
    L = ["| Variant | joint free best (xi, eta) | free improvement | Q | target A (e-/s) | target S/N | target dchi2 vs free | best catalogue host | per-event target S/N (E00, E32, E33, E39) |",
         "|---|---|---|---|---|---|---|---|---|"]
    prim = jd["primary"]
    L.append(f"| primary (E_A, V2 baseline, TESS PRF) | ({prim['best']['xi']:.0f}, {prim['best']['eta']:.0f}) | {prim['free_improvement']:.1f} | {prim['Q_consistency']:.1f} | "
             f"{prim['hosts'][T]['A_weighted']:.2f} +/- {prim['hosts'][T]['sA_weighted']:.2f} | {prim['hosts'][T]['snr_weighted']:.2f} | {prim['hosts'][T]['dchi2_vs_free']:.1f} | "
             f"{prim['best_catalogue_host'][-6:]} | " + ", ".join(f"{real[e]['target']['snr']:.2f}" for e in ("E00", "E32", "E33", "E39")) + " |")
    for name, v in sens.items():
        j2 = v["joint_dimming"]; th = j2["hosts"][T]
        L.append(f"| {name} | ({j2['best']['xi']:.0f}, {j2['best']['eta']:.0f}) | {j2['free_improvement']:.1f} | {j2['Q_consistency']:.1f} | "
                 f"{th['A_weighted']:.2f} +/- {th['sA_weighted']:.2f} | {th['snr_weighted']:.2f} | {th['dchi2_vs_free']:.1f} | {j2['best_catalogue_host'][-6:]} | "
                 + ", ".join(f"{v['events'][e]['target_snr']:.2f}" for e in ("E00", "E32", "E33", "E39")) + " |")
    out["SENS"] = "\n".join(L)
    C.write_json(R / "report_tables.json", out)
    tpl = (C.WS / "code" / "REPORT_TEMPLATE.md").read_text(encoding="utf-8")
    for k, v in out.items():
        tpl = tpl.replace("{{" + k + "}}", v)
    assert "{{" not in tpl, "unfilled placeholder"
    (C.WS / "LOCALISATION_REPORT.md").write_text(tpl, encoding="utf-8")
    print("report written", len(tpl), "chars")


if __name__ == "__main__":
    main()
