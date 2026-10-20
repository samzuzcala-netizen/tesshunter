"""Assemble the census deliverables from the part files (no network):
  results/census/census_<tic>.json   (list of entries per target)
  results/census/census_table.csv    (tic, archive, outcome_code, n_rows, key_findings)
Outcome coding follows the census rules: failed endpoints / error pages are ACCESS_FAILED, account-gated
services ACCESS_RESTRICTED, survey footprints that cannot contain the star NOT_APPLICABLE; an empty result is
never turned into a scientific negative (NO_MATCH / NO_DATA mean 'nothing listed', with caveats stated)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import census_common as C
from census_common import TARGETS, entry, save_json

P = C.PARTS


def L(name):
    return json.loads((P / name).read_text(encoding="utf-8"))


def raws(receipts):
    out = []
    for r in receipts or []:
        try:
            j = json.loads(Path(r).read_text(encoding="utf-8"))
            if j.get("raw_file"):
                out.append(j["raw_file"])
        except Exception:
            pass
    return out


def fmt_secs(s):
    return ",".join(str(x) for x in sorted(s))


def main():
    c01 = {t: json.loads((C.TABLES / f"mast_tess_{t}.json").read_text(encoding="utf-8")) for t in TARGETS}
    c01c, c01d = L("c01c_sector_context.json"), L("c01d_s97_footprint.json")
    c02, c03, c03b, c03c = L("c02_tce.json"), L("c03_exofop.json"), L("c03b_exofop_documented.json"), L("c03c_nea_toi.json")
    toictl = L("cx_toi_controls.json")
    c04c = L("c04c_vizier_controls.json")
    viz = json.loads((C.TABLES / "vizier_cones.json").read_text(encoding="utf-8"))
    gaia = json.loads((C.TABLES / "gaia_dr3_census.json").read_text(encoding="utf-8"))
    c05b = L("c05b_gaia_epoch.json")
    c06, c06b = L("c06_ztf.json"), L("c06b_ztf_dr_check.json")
    c07, c08 = L("c07_asassn.json"), L("c08_eso_koa.json")
    c09, c09b = L("c09_github.json"), L("c09b_github_ephem.json")
    c12, c12b = L("c12_simbad.json"), L("c12b_cloutier2019.json")
    web = L("c14_web_search_log.json")
    ne = json.loads((C.OUT / "new_epochs.json").read_text(encoding="utf-8"))
    counts = c01c["mast_counts"]
    last = {k: max([int(s) for s, n in v["counts_per_sector"].items() if isinstance(n, int) and n > 0] or [0])
            for k, v in counts.items()}
    count_receipts = [r for v in counts.values() for r in v["receipts"]]

    all_rows = []
    for tic, t in TARGETS.items():
        E = []
        d = c01[tic]
        obs = d["observations"]
        q = d["queries"]
        rc_obs = q["target_name"]["receipts"] + q["cone15"]["receipts"]
        fams = {}
        for r in obs:
            if r["ffi_level"] or r["provenance_name"] == "ELEANOR":
                continue
            fams.setdefault(f"{r['provenance_name']}", set()).add(r["sector"])
        ffi = {}
        for r in obs:
            if r["ffi_level"]:
                ffi.setdefault(r["provenance_name"], set()).add(r["sector"])
        used = set(C.used_sectors(tic))
        fam_txt = "; ".join(f"{k}: {fmt_secs(v)}" for k, v in sorted(fams.items()))
        E.append(entry(tic, "MAST TESS+HLSP observations", "Observations.query_criteria(target_name=TIC, "
                       "obs_collection=[TESS,HLSP]) + 15\" cone restricted to TESS/HLSP; union by obsid",
                       "DATA", len(obs),
                       f"target-level families (sectors): {fam_txt}. FFI-level footprints: "
                       + "; ".join(f"{k}: {fmt_secs(v)}" for k, v in sorted(ffi.items()))
                       + ". No target-level product for any sector > 98.",
                       rc_obs, raws(rc_obs)))
        prods = d["products"]
        ver = sorted({(p["productFilename"].split("_tess_")[-1].split("_")[0] if p["productFilename"].startswith("hlsp_") else
                       p.get("prvversion")) for p in prods if p.get("productFilename")} - {None})
        dv = [p["productFilename"] for p in prods if any(s in p["productFilename"].lower() for s in ("_dvr", "_dvs", "_dvm", "_dvt"))]
        rc_p = q["product_lists"]["receipts"]
        E.append(entry(tic, "MAST product lists (target-level observations)", "Observations.get_product_list on "
                       "all non-FFI observations (chunks of 25)", "DATA", len(prods),
                       f"{len(prods)} products; version tags seen: {', '.join(str(v) for v in ver)[:400]}. "
                       f"SPOC DV products (dvr/dvs/dvm/dvt): {'none' if not dv else dv}.", rc_p, raws(rc_p)))
        tc = d["tesscut"]["SPOC"]
        rc_tc = tc["receipts"] + d["tesscut"]["TICA"]["receipts"]
        tcs = [(r["sector"], r["camera"], r["ccd"]) for r in tc["rows"] or []]
        notused = [s for s, _, _ in tcs if s not in used]
        E.append(entry(tic, "TESScut get_sectors (SPOC FFIs)", "Tesscut.get_sectors(coordinates=TIC J2000 position); "
                       "product='TICA' also tried", "DATA", len(tcs),
                       f"sectors (cam,ccd): {', '.join(f'{s}({c},{k})' for s, c, k in tcs)}. Not used by discovery: "
                       f"{notused or 'none'}. None > 98. TICA product refused by the API ('Input product must be "
                       f"SPOC'; astroquery deprecation: TESScut no longer supports TICA).", rc_tc, raws(rc_tc)))
        # sectors > 98
        w = c01c["wtv"][str(tic)]
        wtv_s = [int(r[4]) for r in (w["tables"] or [[]])[0][1:]]
        fut = [s for s in wtv_s if s > 98]
        E.append(entry(tic, "TESS sectors > 98 (any product family)", "MAST obs/product lists + TESScut + per-sector "
                       "MAST counts (SPOC FFI, TICA, QLP, TESS-SPOC) + HEASARC WTV (tess-point) pointing table",
                       "NO_DATA", 0,
                       f"No product and no TESScut sector > 98 for this star, although MAST holds SPOC FFIs through "
                       f"S{last['spoc_ffi']}, TICA through S{last['tica_ffi']}, QLP light curves through "
                       f"S{last['qlp_lc']} (TESS-SPOC: 0 light curves counted in S96-S100). WTV/tess-point (Cycle 9 to S121): "
                       f"{('next on silicon in S' + ', S'.join(map(str, fut)) + ' (2027), no data yet') if fut else 'not on silicon in any sector 99-121'}.",
                       count_receipts + w["receipts"], raws(w["receipts"])))
        # new sectors <= 98
        nt = ne["targets"][str(tic)]
        for e in nt["new_sectors"]:
            pe = e["predicted_primary_events"] or []
            se = e["predicted_phase0.5_events"] or []
            ffi_txt = "; ".join(f"{f['provenance'][:4]} {f['obs_id']} edge-dist {f['footprint_signed_edge_distance_px']} px"
                                f" ({'inside' if f['inside_footprint'] else 'outside'})" for f in e["ffi_level_footprints"])
            in_span = [x for x in pe if x["within_sector_span"]]
            code = "DATA_WITH_TRANSIT_COVERAGE" if (in_span and e["tesscut_spoc"]["listed"]) else "DATA"
            rc_ne = rc_obs + rc_tc + w["receipts"] + (c01d["receipts"] if tic == 270573718 else [])
            E.append(entry(tic, f"TESS new sector S{e['sector']} (not used by discovery)",
                           "MAST FFI-level observation footprints, TESScut, WTV; coverage PREDICTED from sector "
                           "t_min/t_max only (gaps unknown), +/-0.25 d", code, 1,
                           f"BTJD {e['t_min_btjd']:.3f}-{e['t_max_btjd']:.3f}; TESScut listed={e['tesscut_spoc']['listed']} "
                           f"{e['tesscut_spoc']['camera_ccd'] or ''}; WTV/tess-point lists it={e['wtv_tess_point'] is not None}; "
                           f"target-level pipeline products: {e['target_level_families'] or 'none'}; footprints: {ffi_txt}. "
                           f"Predicted primary in span: {[(x['n'], x['tc_btjd'], x['parity_n_mod_2']) for x in in_span]}; "
                           f"phase-0.5: {[(x['n'], x['tc_btjd']) for x in se if x['within_sector_span']]}. "
                           + ("On-silicon status unresolved by metadata (tess-point says off)." if not e['wtv_tess_point'] else ""),
                           rc_ne, raws(rc_ne), new_sector=e["sector"]))
        ups = nt["unused_products_in_used_sectors"]
        if ups:
            fam_set = {}
            for e in ups:
                for f in e["unused_families_same_sector"]:
                    fam_set.setdefault(f.split("/")[-1], []).append(e["sector"])
            E.append(entry(tic, "TESS products in used sectors not used by discovery (D-alt, same photons)",
                           "MAST product families present in discovery sectors but not used", "DATA",
                           sum(len(v) for v in fam_set.values()),
                           "; ".join(f"{k}: {fmt_secs(v)}" for k, v in sorted(fam_set.items())) +
                           ". Same photons as discovery sectors: sensitivity tests only, not independent epochs.",
                           rc_obs, raws(rc_obs)))
        # TCE / DV
        pt = c02["per_target"][str(tic)]
        rc_tce = c02["index"]["receipts"] + [r for f in c02["files"] if f["kind"] == "tce" for r in f["receipts"]]
        searched = pt["cdpp_present_in"]
        E.append(entry(tic, "SPOC TCE statistics (MAST bulk tcestats CSVs)",
                       f"index page (Last Modified {c02['index']['last_modified_text']}); {pt['n_tce_files_ok']} "
                       "single/multi-sector tcestats files covering every sector with data; exact ticid match",
                       "NO_MATCH", 0,
                       f"No TCE for this TIC in {pt['n_tce_files_ok']} files ({pt['n_tce_files_failed']} failed). "
                       + (f"SPOC TPS did search it: present in 2-min rms-CDPP tables {', '.join(s.split('-')[1] for s in searched)}."
                          if searched else
                          f"Absent from all {pt['n_cdpp_files_ok']} SPOC rms-CDPP (TPS target) tables: never a SPOC "
                          "2-min target, so TCE absence carries no information.")
                       + " Positive control: TOI-101 (TIC 231663901) found by the same code in S1.",
                       rc_tce, raws(rc_tce)))
        rc_cd = [r for f in c02["files"] if f["kind"] == "cdpp" for r in f["receipts"]]
        E.append(entry(tic, "SPOC TPS target lists (MAST rms-CDPP CSVs)", f"{pt['n_cdpp_files_ok']} CDPP files, exact ticid",
                       "DATA" if searched else "NO_MATCH", len(searched),
                       (f"in S1/S2/S3 2-min CDPP tables (rows kept in parts/c02_tce.json); not in multi-sector s1-s92/s1-s96 CDPP"
                        if searched else "not in any 2-min CDPP table (FFI-only star)"), rc_cd, raws(rc_cd)))
        E.append(entry(tic, "SPOC DV reports (MAST products)", "product lists of all TESS/SPOC observations",
                       "NO_DATA", 0, "no dvr/dvs/dvm/dvt product associated with this TIC", rc_p, raws(rc_p)))
        E.append(entry(tic, "QLP TCE list", "QLP HLSP page (archive.stsci.edu/hlsp/qlp) and MAST TCE bulk page",
                       "NOT_APPLICABLE", None,
                       "No public QLP TCE catalogue exists on either page (QLP HLSP = light curves only); QLP "
                       "signals become public as TOIs (see TOI entries).",
                       L("c11_hlsp_docs.json")["pages"]["QLP"]["receipts"], []))
        # ExoFOP
        ex = c03["exofop"]
        rc_ex = [r for k, v in ex.items() if k in ("index", "toi_csv", "ctoi_csv", f"target_{tic}", f"target_json_{tic}",
                                                   f"imaging_{tic}") for r in v["receipts"]]
        rc_ex += [r for v in c03b["per_target_calls"][str(tic)].values() for r in v["receipts"]]
        E.append(entry(tic, "ExoFOP-TESS PHP endpoints (index, target.php, &json, download_*.php)",
                       "documented calls from Introduction_to_ExoFOP_php_functions.php", "ACCESS_FAILED", None,
                       "HTTP 200 with a literal 'Array' body (5 bytes) for download_toi/ctoi.php, target.php?json, "
                       "gototicid, download_stellar/planet/uploads/filelist/imaging/spect/tseries/nearbytarget; "
                       "index, view_toi.php and target.php render 'Array' as page content. No retirement notice on "
                       "news.php (latest item 2026-09-15).", rc_ex, raws(rc_ex)))
        mt = c03b["matches"][str(tic)]
        for key, name, n in (("exofop_tois.csv", "ExoFOP TOI table (pre-built json/tois.csv)", None),
                             ("exofop_ctois.csv", "ExoFOP CTOI table (pre-built json/ctois.csv)", None),
                             ("mast_toi_csv", "MAST TOI catalogue (tois.csv)", None),
                             ("exofop_imaging.csv", "ExoFOP imaging observation summaries (json/imaging.csv)", None),
                             ("exofop_spect.csv", "ExoFOP spectroscopy summaries (json/spect.csv)", None)):
            m = mt.get(key)
            if m is None:
                continue
            nearest = toictl.get(key, {}).get("nearest_entry_to_target", {}).get(str(tic))
            pre = c03b["prebuilt"].get(key.replace("exofop_", ""), {}) if key.startswith("exofop_") else c03["toi_sources"]["mast_toi_csv"]
            rcx = pre.get("receipts", [])
            code = "DATA" if (m["exact"] or m["neighbour_tic"] or m["within_2arcmin"]) else "NO_MATCH"
            ctl = toictl.get(key, {})
            ctl_txt = (f"positive control TIC 231663901 (TOI-101) found ({ctl.get('control_TIC231663901_rows')} row(s))"
                       if ctl.get("control_TIC231663901_rows") else
                       f"TOI-101 control not applicable to this table; {ctl.get('n_radec_parsed')} of {ctl.get('n_rows')} "
                       "positions parsed")
            E.append(entry(tic, name, f"exact TIC; TIC v8 neighbours within 2' ({len(c03['tic_neighbours'][str(tic)]['rows'])}); "
                           + ("positions within 2'" if m["ra_key"] else "no RA/Dec column (TIC match only)"),
                           code, m["n_rows"],
                           f"{m['n_rows']} rows (Last-Modified {pre.get('last_modified')}); exact={len(m['exact'])}, "
                           f"neighbour-TIC={len(m['neighbour_tic'])}, within 2'={len(m['within_2arcmin'])}"
                           + (f"; nearest entry {nearest[0]}\" (TIC {nearest[1]}, {nearest[2]})" if nearest else "")
                           + f"; {ctl_txt}.", rcx, raws(rcx)))
        nq = c03c["queries"]
        rc_n = nq["exact_tic"]["receipts"] + nq["control_toi101"]["receipts"] + nq["max_rowupdate"]["receipts"]
        E.append(entry(tic, "NASA Exoplanet Archive TOI table (TAP, exact TIC)", "select ... from toi where tid in (...)",
                       "NO_MATCH", 0, f"0 rows; table has {nq['max_rowupdate']['rows'][0]['n']} rows, last rowupdate "
                       f"{nq['max_rowupdate']['rows'][0]['last_update']}; control TOI-101 returned. (First attempt at "
                       "21:44Z returned HTTP 400 'Failed to connect to cx_Oracle'.)", rc_n, raws(rc_n)))
        rcc = nq[f"cone2_{tic}"]["receipts"]
        E.append(entry(tic, "NASA Exoplanet Archive TOI table (TAP, 2' cone)", "contains(point,circle) ADQL",
                       "ACCESS_FAILED", None, "HTTP 403 Cloudflare block page ('Sorry, you have been blocked'); not "
                       "retried. Positional coverage provided instead by ExoFOP json/tois.csv (same 8151 rows).",
                       rcc, raws(rcc)))
        nb = c03["tic_neighbours"][str(tic)]
        E.append(entry(tic, "TIC v8.2 neighbours within 2' (MAST Catalogs)", "Catalogs.query_region(catalog='TIC', 2')",
                       "DATA", nb["n"], f"{nb['n']} TIC entries (incl. target); used for TOI/CTOI neighbour grep",
                       nb["receipts"], raws(nb["receipts"])))
        # VizieR
        vres = viz["results"][str(tic)]
        for cat, rec in vres.items():
            rows = [r for tb in rec["tables"].values() for r in tb["rows"]]
            group = rec["group"]
            ticq = {k: v for k, v in c04c["tic_queries"].items() if k.split("|")[0].startswith(cat + "/")
                    and k.endswith(f"|{tic}")}
            tic_exact = 0
            for k, v in ticq.items():
                col = v["tic_col"]
                tic_exact += sum(1 for r in (v["rows"] or []) if str(r.get(col)) == str(tic))
            rcv = rec["receipts"] + [r for v in ticq.values() for r in v["receipts"]]
            south_only = cat in ("J/MNRAS/506/150", "J/other/PASA/42.51", "III/283")
            north_only = cat in ("V/164", "V/162", "J/ApJS/282/29", "J/ApJS/249/18")
            if rec["error"]:
                code, kf = "ACCESS_FAILED", rec["error"]
            elif rows or tic_exact:
                code = "DATA"
                bits = []
                for tname, tb in rec["tables"].items():
                    for r in tb["rows"][:3]:
                        keep = {k: r.get(k) for k in ("Name", "Type", "ID", "ObsID", "HRV", "e_HRV", "Obs.date", "Obs.Date",
                                                       "subClass", "z", "e_z", "Teff", "logg", "Z", "Gaia", "GaiaDR3",
                                                       "SpT", "S/N", "snrr") if r.get(k) not in (None, "")}
                        bits.append(f"{tname}: sep {r.get('sep_cat_epoch')}\" {keep} periods={r.get('period_columns') or 'none'}")
                kf = " | ".join(bits)[:1500]
            else:
                if (south_only and t["dec"] > 10) or (north_only and t["dec"] < -31):
                    code = "NOT_APPLICABLE"
                    kf = "0 rows within 60\"; star outside the survey footprint (" + \
                         ("southern survey" if south_only else "northern survey") + ")"
                else:
                    code = "NO_MATCH"
                    kf = "0 rows within 60\"" + (f"; exact TIC query also 0 ({len(ticq)} TIC-keyed tables)" if ticq else "")
                    if group == "variable":
                        kf += "; survey footprint/depth coverage not verified, so this is not a non-variability result"
            E.append(entry(tic, f"VizieR {cat} ({rec['note']})", f"60\" cone at TIC J2000 position; rule={rec['rule']}; "
                           f"assumed catalogue epoch {rec['assumed_epoch']}", code, len(rows), kf, rcv, raws(rcv)))
        # Gaia
        qs = gaia["queries"]
        g = gaia["per_target"][str(tic)]["gaia_source"]
        rc_g = qs["gaia_source_targets"]["receipts"]
        fields = ("ruwe", "astrometric_excess_noise", "astrometric_excess_noise_sig", "ipd_frac_multi_peak",
                  "ipd_frac_odd_win", "ipd_gof_harmonic_amplitude", "phot_variable_flag", "has_epoch_photometry",
                  "has_epoch_rv", "has_xp_continuous", "has_rvs", "radial_velocity", "radial_velocity_error",
                  "rv_method_used", "rv_amplitude_robust", "rv_chisq_pvalue", "rv_renormalised_gof", "rv_nb_transits",
                  "non_single_star", "duplicated_source", "phot_g_mean_mag", "bp_rp", "parallax")
        E.append(entry(tic, "Gaia DR3 gaia_source (target row)", "ESA TAP sync, source_id", "DATA", 1,
                       "; ".join(f"{k}={g.get(k)}" for k in fields), rc_g, raws(rc_g)))
        ap = next((r for r in qs["astrophysical_parameters_targets"]["rows"] if int(r["source_id"]) == t["gaia"]), None)
        apk = ("teff_gspphot", "logg_gspphot", "mh_gspphot", "radius_gspphot", "radius_flame", "mass_flame", "flags_flame",
               "teff_gspspec", "logg_gspspec", "mh_gspspec", "flags_gspspec", "spectraltype_esphs",
               "classprob_dsc_combmod_star", "classprob_dsc_combmod_binarystar")
        rc_ap = qs["astrophysical_parameters_targets"]["receipts"]
        E.append(entry(tic, "Gaia DR3 astrophysical_parameters", "ESA TAP sync, source_id", "DATA" if ap else "NO_MATCH",
                       1 if ap else 0, "; ".join(f"{k}={ap.get(k)}" for k in apk if ap and ap.get(k) not in (None, ""))
                       if ap else "no row", rc_ap, raws(rc_ap)))
        cone = qs[f"cone90_{tic}"]["rows"]
        sid = str(t["gaia"])
        for tab, label in (("vari_summary", "Gaia DR3 vari_summary"), ("vari_classifier_result", "Gaia DR3 vari_classifier_result"),
                           ("vari_eclipsing_binary", "Gaia DR3 vari_eclipsing_binary"),
                           ("vari_planetary_transit", "Gaia DR3 vari_planetary_transit"),
                           ("vari_rotation_modulation", "Gaia DR3 vari_rotation_modulation"),
                           ("nss_two_body_orbit", "Gaia DR3 nss_two_body_orbit"),
                           ("nss_acceleration_astro", "Gaia DR3 nss_acceleration_astro"),
                           ("nss_non_linear_spectro", "Gaia DR3 nss_non_linear_spectro"), ("nss_vim_fl", "Gaia DR3 nss_vim_fl")):
            rows = qs[tab]["rows"] or []
            mine = [r for r in rows if r["source_id"] == sid]
            nbr = [r for r in rows if r["source_id"] != sid and r["source_id"] in {c["source_id"] for c in cone}]
            rct = qs[tab]["receipts"]
            if qs[tab]["error"]:
                code, kf = "ACCESS_FAILED", qs[tab]["error"]
            else:
                code = "DATA" if mine else "NO_MATCH"
                kf = ("target: " + ("; ".join(
                    f"{ {k: v for k, v in r.items() if k in ('best_class_name', 'best_class_score', 'in_vari_eclipsing_binary', 'in_vari_planetary_transit', 'in_vari_rotation_modulation', 'num_selected_g_fov', 'std_dev_mag_g_fov', 'range_mag_g_fov')} }"
                    for r in mine) if mine else "no row"))
                if nbr:
                    kf += "; neighbours within 90\": " + "; ".join(
                        f"{r['source_id']} ({next(float(c['sep_arcsec']) for c in cone if c['source_id'] == r['source_id']):.1f}\") "
                        f"{ {k: v for k, v in r.items() if k in ('best_class_name', 'best_class_score', 'mean_mag_g_fov')} }"
                        for r in nbr)
                else:
                    kf += "; no neighbour within 90\" in this table"
            E.append(entry(tic, label, "ESA TAP sync, target + all sources within 90\"", code, len(mine), kf, rct, raws(rct)))
        rc_c = qs[f"cone90_{tic}"]["receipts"]
        others = [c for c in cone if c["source_id"] != sid]
        brightest = sorted(others, key=lambda c: float(c["phot_g_mean_mag"] or 99))[:3]
        E.append(entry(tic, "Gaia DR3 sources within 90\"", "ESA TAP sync cone (epoch 2016.0, centred on DR3 position)",
                       "DATA", len(cone),
                       f"{len(others)} other sources; nearest: " + "; ".join(
                           f"{c['source_id']} {float(c['sep_arcsec']):.2f}\" G={float(c['phot_g_mean_mag']):.2f} "
                           f"ruwe={c['ruwe'] or 'NA'} ipd_mp={c['ipd_frac_multi_peak']}" for c in others[:3])
                       + "; brightest: " + "; ".join(f"{c['source_id']} {float(c['sep_arcsec']):.1f}\" G={float(c['phot_g_mean_mag']):.2f}"
                                                     for c in brightest), rc_c, raws(rc_c)))
        w5 = [c for c in others if float(c["sep_arcsec"]) <= 5.0]
        E.append(entry(tic, "Gaia DR3 sources within 5\" (task 11)", "subset of the 90\" cone", "DATA" if w5 else "NO_MATCH",
                       len(w5), "none besides the target" if not w5 else str(w5), rc_c, raws(rc_c)))
        ep = [r for r in c05b["requests"] if r["tic"] == tic]
        rc_e = [r for x in ep for a in x["attempts"] for r in a["receipts"]]
        tgt_ep = [x for x in ep if x["source_id"] == t["gaia"]]
        nb_ep = [x for x in ep if x["source_id"] != t["gaia"]]
        if tgt_ep:
            a = tgt_ep[0]["attempts"][-1]
            code, kf = "DATA", (f"target epoch photometry saved ({a['files'][0]['lines'] - 1} transit rows, "
                                f"{a['files'][0]['saved']}); time = TCB-based BJD - 2455197.5; not interpreted")
        else:
            code, kf = "NO_DATA", "target has_epoch_photometry = false"
        if nb_ep:
            kf += "; neighbour epoch photometry saved: " + "; ".join(
                f"{x['source_id']} ({x['sep_arcsec']:.1f}\") {x['attempts'][-1]['files'][0]['saved']}" for x in nb_ep)
        kf += ". First attempt with DATA_STRUCTURE=INDIVIDUAL returned HTTP 500 (deprecated); DATAMODEL_STANDARD used."
        E.append(entry(tic, "Gaia DR3 epoch photometry (DataLink)", "data-server RETRIEVAL_TYPE=EPOCH_PHOTOMETRY, "
                       "csv, VALID_DATA=false", code, len(tgt_ep), kf, rc_e, raws(rc_e)))
        E.append(entry(tic, "Gaia DR3 RVS / radial velocity", "gaia_source RV columns", "DATA", 1,
                       f"has_rvs={g.get('has_rvs')}, RV={g.get('radial_velocity')}+/-{g.get('radial_velocity_error')} km/s, "
                       f"rv_method_used={g.get('rv_method_used')}, rv_nb_transits={g.get('rv_nb_transits')}, "
                       f"rv_amplitude_robust={g.get('rv_amplitude_robust') or 'NA'}, rv_chisq_pvalue={g.get('rv_chisq_pvalue') or 'NA'}, "
                       f"has_epoch_rv={g.get('has_epoch_rv')} (no epoch RVs public in DR3)", rc_g, raws(rc_g)))
        # ZTF
        if t["dec"] < -31:
            E.append(entry(tic, "ZTF light curves (IRSA LC API)", "not queried", "NOT_APPLICABLE", None,
                           "Dec < -31 (outside ZTF sky)", [], []))
            E.append(entry(tic, "ZTF forced-photometry service", "not queried", "NOT_APPLICABLE", None,
                           "Dec < -31 (outside ZTF sky)", [], []))
        else:
            tq = next(x for x in c06["queries"] if x["is_target"])
            bb = tq["summary"]["by_band"]
            rc_z = [r for x in c06["queries"] for r in x["receipts"]] + c06["doc"]["receipts"] + \
                   [r for x in c06b["checks"] for r in x["receipts"]] + (c06.get("collection_check") or {}).get("receipts", [])
            nbs = [x for x in c06["queries"] if not x["is_target"]]
            E.append(entry(tic, "ZTF light curves (IRSA LC API)", "POS=CIRCLE ra dec 0.0014 (5\"), BANDNAME=g,r,i, csv; "
                           "target + 8 Gaia neighbours within 60\" with G<21 (positions at 2020.0)", "DATA",
                           sum(v["n"] for v in bb.values()),
                           "target: " + "; ".join(f"{b}: n={v['n']} (catflags=0: {v['n_catflags0']}), MJD {v['mjd_min']:.2f}-{v['mjd_max']:.2f}, "
                                                  f"{v['n_oids']} oid(s)" for b, v in bb.items())
                           + ". Default collection = ztf_dr24 (body sha256 identical to COLLECTION=ztf_dr24; ztf_dr18 named "
                             "in the API page now returns 'UsageFault'; IRSA release directory lists dr01-dr24). Neighbours: "
                           + "; ".join(f"{x['source_id']} {x['sep_arcsec_2016']:.1f}\" G={x['G']:.2f}: "
                                       + ",".join(f"{b}={v['n']}" for b, v in x['summary']['by_band'].items()) for x in nbs)
                           + ". CSVs in results/census/ztf/. Transit-phase coverage not assessed here.",
                           rc_z, raws(rc_z)))
            E.append(entry(tic, "ZTF forced-photometry service (ZFPS)", "not attempted", "ACCESS_RESTRICTED", None,
                           "requires a registered account (not created, per census rules)", [], []))
        E.append(entry(tic, "ATLAS forced photometry", "not attempted", "ACCESS_RESTRICTED", None,
                       "requires a registered account/token (not created, per census rules)", [], []))
        # ASAS-SN
        a = c07["targets"][str(tic)]
        rc_a = c07["init"]["receipts"] + a["cone_receipts"] + a.get("download_prep_receipts", [])
        idx = a.get("index") or []
        E.append(entry(tic, "ASAS-SN Sky Patrol v2 light curves (pyasassn client)",
                       "SkyPatrolClient init + cone_search(15\", master_list); block download skipped", "ACCESS_FAILED",
                       len(idx),
                       f"catalogue entry found: asas_sn_id={idx[0]['asas_sn_id'] if idx else None} "
                       f"(sources {idx[0]['catalog_sources'] if idx else None}, {idx[0]['sep_arcsec_from_2016pos'] if idx else None}\"). "
                       "Light curves not retrievable: get_block_servers returned [] and the server message (13 Oct 2026) says "
                       "'The light curve service will be down for several days while we run [maintenance] on our cluster.' "
                       "Client skypatrol 0.6.21 (pip) in D:\\tess_fu3_cache\\venv_census; no login involved.",
                       rc_a, raws(rc_a)))
        # ESO / KOA
        es = c08["eso"][str(tic)]
        rc_es = es["obscore_10arcsec"]["receipts"] + es["raw_30arcsec_box"]["receipts"]
        oc = es["obscore_10arcsec"]["rows"] or []
        kinds = {}
        for r in oc:
            kinds[(r["obs_collection"], r["dataproduct_type"])] = kinds.get((r["obs_collection"], r["dataproduct_type"]), 0) + 1
        spectra = [r for r in oc if r["dataproduct_type"] in ("spectrum", "cube", "timeseries")]
        E.append(entry(tic, "ESO archive (TAP ivoa.ObsCore 10\" + dbo.raw 30\" box)", "ADQL via archive.eso.org/tap_obs",
                       "DATA" if spectra or (es["raw_30arcsec_box"]["rows"]) else "NO_DATA", len(oc),
                       f"no spectra and no pointed raw frames; Phase-3 products whose footprints include the star: "
                       f"{ {f'{k[0]}/{k[1]}': v for k, v in kinds.items()} or 'none'} (VISTA survey imaging/catalogues)"
                       + ("; Dec +42: reachable from Paranal only below ~23 deg elevation" if t["dec"] > 30 else ""),
                       rc_es, raws(rc_es)))
        kc = c08["koa"]["cones"][str(tic)]
        rc_k = c08["koa"]["tables"]["receipts"] + [r for v in kc.values() for r in v["receipts"]]
        nk = sum(v["n_rows"] or 0 for v in kc.values())
        if t["dec"] < -60:
            kcode, knote = "NOT_APPLICABLE", "never above ~7 deg elevation from Mauna Kea; "
        else:
            kcode, knote = ("DATA" if nk else "NO_DATA"), ("max elevation ~17 deg from Mauna Kea; " if t["dec"] < -45 else "")
        E.append(entry(tic, "Keck Observatory Archive (TAP, anonymous)", "14 instrument tables, 30\" cone",
                       kcode, nk, knote + f"{nk} rows in {len(kc) - 1} instrument tables (koa_reduced_data is not "
                       "position-searchable: HTTP 400)",
                       rc_k, raws(rc_k)))
        # prior public analyses / bibliography
        sb = c12["targets"][str(tic)]
        rc_s = sb["lookup"]["receipts"] + (sb.get("refs") or {}).get("receipts", []) + sb["cone60"]["receipts"]
        look = sb["lookup"]["rows"] or []
        refs = (sb.get("refs") or {}).get("rows") or []
        E.append(entry(tic, "SIMBAD (identifiers, references, 60\" cone)", "CDS SIMBAD TAP", "DATA" if look else "NO_MATCH",
                       len(refs), (f"{look[0]['main_id']} ({look[0]['otype']}), {len(refs)} references: "
                                   + "; ".join(f"{r['bibcode']} {r['title'][:70]}" for r in refs)) if look else
                       "no SIMBAD object for TIC/Gaia ID and none within 60\"", rc_s, raws(rc_s)))
        if tic == 262843927:
            rc_cl = c12b["vizier"]["cone_receipts"] + c12b["ar5iv"]["receipts"] + c12b["arxiv_abs"]["receipts"]
            row = c12b["vizier"]["cone60"]["J/AJ/158/81/catalog"][0]
            E.append(entry(tic, "Prior public analysis: Cloutier (2019, AJ 158, 81; arXiv:1812.08145)",
                           "VizieR J/AJ/158/81 + full text (ar5iv) grep", "DATA", 1,
                           f"star is in the 1599-star low-mass sample searched with S1-S2 2-min light curves "
                           f"(Teff {row['Teff']} K, R* {row['R*']:.3f}, M* {row['M*']:.3f}, d {row['Dist']:.1f} pc); the TIC ID does not "
                           "appear in the paper text/candidate or false-positive tables (0 hits in ar5iv HTML), i.e. not "
                           "reported. Same 2-min photons as SPOC S1-S2; not independent of TESS.", rc_cl, raws(rc_cl)))
        rc_w = []
        if tic == 193718989:
            rc_w = c09["repo"]["receipts"] + c09["tree"]["receipts"] + [r for f in c09["files"] for r in f["receipts"]] + \
                   [r for f in c09b["files"].values() for r in f["receipts"]]
            eph = c09b["files"]["candidates/ephemerides.csv"]["rows_for_targets"]["193718989"][0]
            E.append(entry(tic, "Prior public analysis: github.com/eumemic/exoplanets", "GitHub API tree + raw files "
                           "(candidates/TIC193718989_P24.533/*, README, results_public/*.csv, candidates/ephemerides.csv, "
                           "predictions.csv)", "DATA", 1,
                           f"candidate TIC193718989_P24.533 (added 2026-10-08, 'faint M dwarfs' stack-slide search of "
                           f"TESS-SPOC/QLP S1-104 FFI light curves; repo created 2026-10-07, last push 2026-10-16). "
                           f"P={eph['period_d']}+/-{eph['period_err_d']} d, T0=BJD_TDB {eph['T0_BJD_TDB']} (+/-{eph['T0_err_min']} min), "
                           f"T14={eph['duration_h']} h, depth={eph['depth_ppm']} ppm (fit; BLS depth 2365+/-213 ppm, SNR 11.1, "
                           f"MES 13.5, 8 transits), Rp={eph['Rp_Re']} Re, b=0.34; data used: TESS-SPOC S25,26,40,52,53,79,80 "
                           f"(per-sector depths in vetting.json); TRICERATOPS (S40,52,53) FPP 0.029+/-0.004, NFPP 2.8e-7, "
                           f"with MOLUSC/Gaia constraints FPP 0.011; centroid offsets 1.4\" (S25), 8.8\" (S53); tier "
                           f"{eph['tier']}; planned TESS sectors listed: {eph['tess_sectors_planned']}. Same TESS photons: "
                           "not independent confirmation.", rc_w, raws(rc_w)))
        E.append(entry(tic, "Web search (TIC ID, Gaia DR3 ID)", "WebSearch tool, standard mode (no local receipts; "
                       "queries logged in parts/c14_web_search_log.json)", "NO_MATCH", 0,
                       "no indexed page mentions the TIC ID or the Gaia DR3 source_id" +
                       ("; the eumemic/exoplanets candidate page was found by direct repository inspection, not by search"
                        if tic == 193718989 else ""), [], []))
        for e in E:
            e["n_receipts"] = len(e["receipt_files"])
        save_json(C.OUT / f"census_{tic}.json", {"tic": tic, "gaia_dr3": t["gaia"], "generated_utc": C.utc(),
                                                  "n_entries": len(E), "entries": E})
        all_rows += E
    with open(C.OUT / "census_table.csv", "w", encoding="utf-8", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["tic", "archive", "outcome_code", "n_rows", "key_findings"])
        for e in all_rows:
            wr.writerow([e["tic"], e["archive"], e["outcome_code"], e["n_rows"], e["key_findings"]])
    print("entries:", len(all_rows))


if __name__ == "__main__":
    main()
