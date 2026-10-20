"""Render ``docs/POPULATION_P8.md`` from ``data/survey/population_p8.json`` (and, when they exist,
``data/survey/p8/neighbours_p8.json``, ``completeness_p8.json`` and ``expected_yield_p8.json``).

Every number in the memo is read from those files; the memo is prose around them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POP = REPO / "data" / "survey" / "population_p8.json"
P8 = REPO / "data" / "survey" / "p8"
OUT = REPO / "docs" / "POPULATION_P8.md"


def f(v, nd=2):
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def pct(v):
    return "n/a" if v is None else f"{100 * v:.0f}%"


def main() -> None:
    m = json.loads(POP.read_text(encoding="utf-8"))
    d = m["design"]
    sel = m["selection"]
    cnt = sel["counts"]
    cov = sel["coverage_by_tmag"]
    tg = m["targets"]
    nb = json.loads((P8 / "neighbours_p8.json").read_text(encoding="utf-8")) if (P8 / "neighbours_p8.json").exists() else None
    comp = json.loads((P8 / "completeness_p8.json").read_text(encoding="utf-8")) if (P8 / "completeness_p8.json").exists() else None
    ey = json.loads((P8 / "expected_yield_p8.json").read_text(encoding="utf-8")) if (P8 / "expected_yield_p8.json").exists() else None
    L = []
    a = L.append
    a("# The prompt-8 population: mid-to-late M dwarfs at 200-second cadence\n")
    a(f"Generated {m['generated_utc']} by `scripts/build_p8_population.py all --seed {m['seed']}` (this memo: "
      "`scripts/write_population_p8_memo.py`). Population counts come from `data/survey/population_p8.json`; "
      "the later sections name their neighbour, completeness and yield records. "
      "[M] measured in prompt 8, [A] adopted, [P1] taken from prompt 1. The pipeline finds candidates; nothing "
      "here is a detection.\n")
    a("## 1. Definition [A]\n")
    a(f"* Stars: TIC Teff below {d['teff_max_k']:.0f} K, TIC radius below {d['radius_max_rsun']} Rsun, TIC luminosity "
      f"class dwarf where given, and the Gaia-based main-sequence check of section 3.")
    a(f"* Brightness: Tmag {d['tmag_range'][0]} to {sel['tmag_ceiling_used']} (ceiling extension to "
      f"{d['relax_1_tmag_ceiling']} only on the coverage measurement of section 4).")
    a(f"* Sky: |b| >= {d['min_abs_galactic_latitude_deg']:.0f} deg.")
    a(f"* Sectors: at least {d['min_sectors_200s_with_lc']} sectors at 200-s cadence (sector {d['first_200s_sector']} "
      f"onward) with a QLP or TESS-SPOC light curve; sectors {d['first_600s_sector']}-{d['first_200s_sector'] - 1} "
      "(600 s) and 1-26 (1800 s) recorded per star, not counted.")
    a(f"* FFI-only: {d['ffi_only_rule']}.")
    a("* Hard stop: CLEAN under the prompt-1 cross-match with freshly downloaded catalogs; FLAG excluded.")
    a(f"* Size: {d['size_min']} to {d['size_max']}; if more qualify, {d['ranking']}.\n")
    a("## 2. The query and the counts [M]\n")
    tq = m["tic_query"]
    a(f"The TIC was queried over the whole sky in {tq['n_strips']} declination strips of {d['dec_strip_deg']:.0f} deg on "
      f"Tmag {d['tic_query_tmag_range']}, Teff {d['tic_query_teff_range']} K, radius {d['tic_query_radius_range']} Rsun, "
      f"objType {d['tic_query_objtype']} ({tq['queried_utc']}): {tq['n_rows_all_strips']:,} rows, {tq['n_unique']:,} "
      f"unique, {tq['n_after_abs_b_cut']:,} at |b| >= {d['min_abs_galactic_latitude_deg']:.0f}. Sectors per star come from "
      f"the vendored tess-point, capped at sector {m['sectors']['latest_public_sector']} (the latest with a public QLP "
      f"target list on {m['sectors']['probed_utc'][:10]}). Light-curve presence per sector comes from the QLP and "
      f"TESS-SPOC per-sector target lists (missing lists: {m['products']['lists_missing']}); SPOC 2-minute presence "
      f"from {m['twomin']['source']} (sectors without a list: {m['twomin_sectors_missing'] or 'none'}).\n")
    a("| cut, in order | stars left |")
    a("|---|---:|")
    for k, v in cnt.items():
        if isinstance(v, dict):
            continue
        a(f"| {k} | {v:,} |")
    a("")
    a("Gaia dwarf-check outcomes on the stars reaching that cut: " + ", ".join(
        f"{k} {v:,}" for k, v in sorted(cnt["gaia_dwarf_check_reasons"].items(), key=lambda kv: -kv[1])) + ".")
    a("Hard-stop status on the stars reaching that cut: " + ", ".join(f"{k} {v:,}" for k, v in cnt["xmatch_status"].items())
      + f". Catalog stamp `{m['catalog_manifest']['stamp']}`; rows per source {m['catalog_manifest']['n_rows']}.")
    a(f"\nThe 2-minute check at zero: {cnt['zero_2min_sectors_in_search']:,} stars have no SPOC 2-minute sector among their "
      f"search sectors; at minority: {cnt['minority_2min_sectors_in_search']:,}. The definition uses minority.\n")
    a(f"Qualified: **{sel['n_qualified']:,}**. Ranked and cut at {d['size_max']}: {sel['ranked_and_cut']}. "
      f"Relaxations applied: {[r['relaxation'] for r in sel['relaxations']] or 'none'}. "
      f"Target list: **{sel['n_targets']:,} stars** (`data/survey/targets_p8.csv`).\n")
    a("## 3. The Gaia dwarf check [A, applied M]\n")
    g = d["gaia_dwarf_check"]
    a(f"From the TIC's own Gaia columns ({g['source']}): parallax signal-to-noise >= {g['plx_snr_min']}, BP-RP >= "
      f"{g['bp_rp_min']}, and |M_G - ({g['locus']})| <= {g['locus_tolerance_mag']} mag. Written before the pool was "
      "examined. Outcomes over the definition band (Teff, radius, Tmag cuts only): " + ", ".join(
          f"{k} {v:,}" for k, v in sorted(m["gaia_dwarf_check_pool_definition_band"].items(), key=lambda kv: -kv[1])) + ".\n")
    a("## 4. Light-curve coverage by Tmag, and the ceiling [M]\n")
    a("| Tmag | stars (TIC cuts, absolute latitude cut) | with >= 3 predicted 200-s sectors | with >= 3 delivered 200-s light curves | fraction |")
    a("|---|---:|---:|---:|---:|")
    for k in ("12.5-13.0", "13.0-13.5", "13.5-14.0", "14.0-14.5"):
        c = cov[k]
        a(f"| {k} | {c['n_stars']:,} | {c['n_with_3_predicted_200s']:,} | {c['n_with_3_lc_200s']:,} | {pct(c['frac_with_3_lc_200s'])} |")
    a(f"\nRatio of the 14.0-14.5 fraction to the 13.5-14.0 fraction: {f(cov['ratio_14.0-14.5_over_13.5-14.0'], 3)}; "
      f"the pre-registered condition for extending the ceiling is >= 0.8: **{'met' if cov['ceiling_extension_allowed'] else 'not met'}**. "
      f"Ceiling used: {sel['tmag_ceiling_used']}. Radius cut used: {sel['radius_max_used']} Rsun.\n")
    a("## 5. The target list [M]\n")
    a("| quantity | p10 / p25 / p50 / p75 / p90 |")
    a("|---|---|")
    for k, lab in (("tmag_quantiles", "Tmag"), ("teff_quantiles", "Teff (K)"), ("radius_quantiles", "radius (Rsun)"),
                   ("mass_quantiles", "mass (Msun)"), ("n_sectors_200s_quantiles", "200-s sectors with a light curve"),
                   ("n_sectors_600s_quantiles", "600-s sectors with a light curve"),
                   ("n_sectors_2min_in_search_quantiles", "2-minute sectors among the search sectors"),
                   ("gallat_abs_quantiles", "Absolute galactic latitude (deg)")):
        q = tg.get(k)
        a(f"| {lab} | {' / '.join(f(x, 2) for x in q) if q else 'n/a'} |")
    a(f"\n{tg['n_with_zero_2min_in_search']:,} of {tg['n']:,} stars have no 2-minute sector among their search sectors; "
      f"{tg['n_with_any_600s']:,} have at least one 600-s sector; {tg['n_with_tess_spoc']:,} have a TESS-SPOC light "
      f"curve somewhere and {tg['n_qlp_only_in_200s']:,} are QLP-only in every 200-s sector; {tg['n_north']:,} are "
      f"north of the equator. Contamination ratio missing for {pct(tg['contamination_missing_fraction'])} (median measured "
      f"{f(tg['contamination_median_measured'], 4)}; policy {sel['contamination']['policy']}, fill "
      f"{f(sel['contamination']['fills'].get('measured_median'), 4)}). A 1 R_earth planet is {f(tg['depth_1re_ppt_median'], 2)} ppt "
      f"and a 2 R_earth planet {f(tg['depth_2re_ppt_median'], 2)} ppt on the median star.\n")
    a(f"The prompt-1 model score used only for ranking (photon-noise model, adopted efficiencies, {sel['p1_model']['n_cells']} "
      f"DC15 cells over {sel['p1_model']['period_range']} d) sums to {f(sel['p1_model']['sum_expected_new_mid'], 2)} expected "
      f"new signals at mid priors ({f(sel['p1_model']['sum_expected_new_low'], 2)} low, {f(sel['p1_model']['sum_expected_new_high'], 2)} "
      "high). It is not the expectation of this prompt; section 7 is.\n")
    a("## 6. Gaia, SIMBAD and VSX for every star [M]\n")
    if nb:
        a(f"`scripts/p8_neighbours.py` ({nb['generated_utc']}): {nb['complete']:,} of {nb['n_stars']:,} stars have a complete "
          f"record (Gaia errors {nb['gaia_error']}, SIMBAD errors {nb['simbad_error']}, VSX errors {nb['vsx_error']}, missing "
          f"files {nb['missing_file']}). Target match: {nb['target_match']}. Gaia sources within 1 arcmin, p10/p50/p90: "
          f"{nb['n_gaia_within_1arcmin_quantiles']}. Target flags: {nb['target_flags']}. Stars with a neighbour within 3 px "
          f"bright enough to make a 1 ppt dip if totally eclipsed: {nb['n_neighbours_3px_1ppt_gt0']:,}; with a VSX entry within "
          f"1 arcmin: {nb['n_with_vsx_entry']:,}; with a SIMBAD entry: {nb['n_with_simbad_entry']:,}.\n")
    else:
        a("Not yet run.\n")
    a("## 7. Completeness, false alarms and the expectation [M]\n")
    if comp:
        lv = comp["levels"]

        def row(name, lab):
            x = lv[name]
            lg = x.get("logistic") or {}
            return (f"| {lab} | {x['n_through']:,} / {x['n']:,} | {pct(x['fraction'])} | {f(lg.get('snr50'), 1)} "
                    f"({f((lg.get('snr50_16_84') or [None, None])[0], 1)}-{f((lg.get('snr50_16_84') or [None, None])[1], 1)}) | "
                    f"{f(lg.get('snr90'), 1)} ({f((lg.get('snr90_16_84') or [None, None])[0], 1)}-{f((lg.get('snr90_16_84') or [None, None])[1], 1)}) |")
        a(f"`scripts/p8_completeness.py` ({comp['generated_utc']}, rules {comp['rules_version']}): {comp['n_injections']:,} "
          f"injections on {comp['n_stars']} stars, outcomes {comp['outcomes']}.\n")
        a("| level | through / injected | fraction | SNR50 (16-84%) | SNR90 (16-84%) |")
        a("|---|---:|---:|---|---|")
        a(row("search_only", "search only"))
        a(row("search_and_pregate", "search + pre-gate"))
        a(row("search_and_stageA", "search + Stage A"))
        a(row("search_and_stageA_and_secondary", "search + Stage A + secondary gate"))
        a(row("full_funnel_with_pregate", "the whole funnel (pre-gate, A, secondary)"))
        fa = comp.get("false_alarms") or {}
        if fa.get("available"):
            a(f"\nFalse alarms on the same {fa['n_stars']} stars with no injection: {fa['accepted']:,} accepted candidates "
              f"({f(fa['accepted_per_star'], 2)} per star), {fa['pregate']:,} past the pre-gate ({f(fa['pregate_per_star'], 3)} per star), "
              f"{fa['stageA_pass']:,} past Stage A ({f(fa['stageA_pass_per_star'], 4)} per star), "
              f"{fa['stageA_pass_and_secondary']:,} past the secondary gate ({f(fa['stageA_pass_and_secondary_per_star'], 4)} per star).\n")
    else:
        a("Not yet run.\n")
    if ey:
        e = ey["expected_new_signals"]
        a("### Yield model and assumptions [A, P1]\n")
        a("The central model uses the [Dressing & Charbonneau (2015) occurrence grid](https://arxiv.org/abs/1501.01623), "
          "with the adopted giant-planet component from prompt 1. The faint-M incumbent-search priors are adopted: "
          "a higher prior means that more detectable objects are already known, hence fewer expected new signals. "
          "The calibration ends after the pre-gate, Stage A and secondary scan. Later vetting can only reduce this yield.\n")
        hu = ey["occurrence"]["sensitivity_hu19"]
        a(f"The sensitivity uses [Hardegree-Ullman et al. (2019)]({hu['url']}): {hu['rate_per_star']} "
          f"(+{hu['err_plus']}/-{hu['err_minus']}) planets per star over {hu['rp_earth'][0]}-{hu['rp_earth'][1]} Earth radii "
          f"and {hu['period_days'][0]}-{hu['period_days'][1]} days. {hu['shape_assumption']}\n")
        for assumption in ey.get("model_assumptions", []):
            a(f"* {assumption}")
        a("\n### Expected signals under that model\n")
        a(f"`scripts/p8_expected_yield.py` ({ey['generated_utc']}): on {ey['n_stars_with_prepared_curve']:,} stars with a prepared "
          f"curve, detectable planets through the funnel {f(ey['detectable_planets_total']['funnel'], 2)} (search only "
          f"{f(ey['detectable_planets_total']['search_only'], 2)}).\n")
        a("| prior completeness | expected NEW signals through the funnel | with the HU19 rescaling | search only |")
        a("|---|---:|---:|---:|")
        for lvl in ("low", "mid", "high"):
            a(f"| {lvl} | {f(e['through_funnel'][lvl], 2)} | {f(e['through_funnel_hu19'][lvl], 2)} | {f(e['search_only'][lvl], 2)} |")
        a(f"\nExpected funnel-passing false alarms in the population: {f(ey['expected_funnel_passing_false_alarms'], 1)}; "
          f"ratio of expected signals to false alarms at mid priors: {f(ey['signal_to_false_alarm_ratio_mid'], 3)}.\n")
        dc = ey["decision"]
        a(f"**Stop rule** ({ey['stop_rule']['fixed']}): mid-prior expectation {f(dc['mid_prior_expectation'], 2)} against the "
          f"threshold {ey['stop_rule']['mid_prior_min_expected_through_funnel']}; high-prior {f(dc['high_prior_expectation'], 2)}. "
          f"**{dc['statement']}**\n")
    a("## 8. Files\n")
    a("* `data/survey/targets_p8.csv`, `targets_p8.meta.json`, `population_p8.json`, `catalog_versions_p8.json`.")
    a("* `data/survey/cache/p8/` (strips, pool tables), `data/survey/cache/target_lists/`, `data/survey/cache/twomin_lists/` (git-ignored).")
    a("* `data/survey/p8/neighbours/` (one JSON per star), `neighbours_p8.json`, `completeness_p8.json`, `expected_yield_p8.json`.")
    check_path = P8 / "search_validation_p8.json"
    if check_path.exists():
        check = json.loads(check_path.read_text(encoding="utf-8"))
        special = check["special_sector_1751"]
        a("\n## 9. Search input reconciliation [M]\n")
        a(f"The completed search used {check['n_products']:,} product arrays harmonised to 200 s. They cover standard sectors "
          f"{check['standard_sector_range'][0]}-{check['standard_sector_range'][1]} and include {special['n_products']} "
          "TESS-SPOC products from the special sector 1751. "
          f"[The mission release notes]({special['sources'][0]}) identify that sector as the January 2026 comet pointing. "
          "The source metadata and native timestamps agree; the existing cadence selection retained these products.\n")
        a("The special sector was not counted for the population's three-sector minimum. "
          f"It appears on {len({r['tic_id'] for r in special['products']})} selected stars and on "
          f"{len(special['calibration_sample_overlap_tics'])} injection-sample hosts. "
          "The calibration therefore does not separately measure its unusual window. "
          "[search_validation_p8.json](../data/survey/p8/search_validation_p8.json) records every affected star, "
          "its qualifying standard sectors, the source metadata and the completed search hashes.\n")
    OUT.write_text("\n".join(L).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
