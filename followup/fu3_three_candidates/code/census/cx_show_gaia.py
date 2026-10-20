"""Print a compact view of the Gaia census table (read-only)."""
import json

import census_common as C

d = json.loads((C.TABLES / "gaia_dr3_census.json").read_text(encoding="utf-8"))
keys = ["source_id", "ra", "dec", "parallax", "parallax_error", "pmra", "pmdec", "phot_g_mean_mag", "bp_rp",
        "ruwe", "ipd_frac_multi_peak", "ipd_frac_odd_win", "ipd_gof_harmonic_amplitude", "phot_variable_flag",
        "has_epoch_photometry", "has_epoch_rv", "has_xp_continuous", "has_xp_sampled", "has_rvs",
        "radial_velocity", "radial_velocity_error", "rv_amplitude_robust", "rv_chisq_pvalue", "rv_nb_transits",
        "rv_renormalised_gof", "rv_method_used", "non_single_star", "duplicated_source", "visibility_periods_used",
        "astrometric_excess_noise", "astrometric_excess_noise_sig", "phot_g_n_obs", "teff_gspphot", "logg_gspphot",
        "mh_gspphot", "distance_gspphot", "classprob_dsc_combmod_star", "in_qso_candidates", "in_galaxy_candidates"]
for r in d["queries"]["gaia_source_targets"]["rows"]:
    print("---- gaia_source", r["source_id"])
    print({k: r.get(k) for k in keys})
apk = ["source_id", "teff_gspphot", "logg_gspphot", "mh_gspphot", "radius_gspphot", "radius_flame", "mass_flame",
       "lum_flame", "age_flame", "flags_gspphot", "flags_flame", "teff_gspspec", "logg_gspspec", "mh_gspspec",
       "flags_gspspec", "classlabel_espels", "spectraltype_esphs", "teff_esphs", "ruwe" ,"evolstage_flame",
       "teff_msc1", "teff_msc2", "logposterior_msc", "radius_flame_lower", "radius_flame_upper"]
for r in d["queries"]["astrophysical_parameters_targets"]["rows"]:
    print("---- AP", {k: r.get(k) for k in apk})
for tab in ("vari_summary", "vari_classifier_result"):
    for r in d["queries"][tab]["rows"]:
        print("----", tab, {k: v for k, v in r.items() if v not in ("", None)})
for tic in (270573718, 262843927, 193718989):
    q = d["queries"][f"cone90_{tic}"]
    print("==== cone90", tic, "center", q["center"])
    for r in q["rows"]:
        print(f"  {r['source_id']:>20s} sep={float(r['sep_arcsec']):6.2f} G={r['phot_g_mean_mag']:>8.8s} "
              f"BP-RP={r['bp_rp'][:6]:>6s} plx={r['parallax'][:7]:>7s} pmra={r['pmra'][:7]:>7s} "
              f"pmdec={r['pmdec'][:7]:>7s} ruwe={r['ruwe'][:5]:>5s} ipdmp={r['ipd_frac_multi_peak']:>3s} "
              f"var={r['phot_variable_flag']} ep={r['has_epoch_photometry']} nss={r['non_single_star']} "
              f"dup={r['duplicated_source']}")
print("per_target", json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'gaia_source'}
                                for k, v in d["per_target"].items()}, indent=0))
