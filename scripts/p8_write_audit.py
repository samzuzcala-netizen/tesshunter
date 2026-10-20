"""Write the final P8 audit only after the real funnel and candidate reviews settle."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data/survey/p8"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    f = read(OUT / "funnel_p8.json")
    run = read(OUT / "run_summary_p8.json")
    census = read(OUT / "census_p8.json")
    old = read(REPO / "data/survey/p6/census_p6.json")
    comp = read(OUT / "completeness_p8.json")
    expectation = read(OUT / "expected_yield_p8.json")
    ranks = read(OUT / "ranking_p8.json")
    progress = read(OUT / "funnel_progress_p8.json")
    search_check = read(OUT / "search_validation_p8.json")
    if not search_check.get("verified") or search_check["n_results"] != run["n_targets"]:
        raise RuntimeError("The completed search input validation is missing or inconsistent")
    from p8_neighbour_depths import ensure_context
    depth_context = ensure_context(check_only=True)
    if run["n_missing"] or f["rules_version"] != "p8.0":
        raise RuntimeError("Missing search results or incorrect rules")
    for stage in ("A", "S", "B", "C"):
        check = progress["stages"][stage]
        if check["gaps"] or check["exit_code"]:
            raise RuntimeError(f"Stage {stage} has unfinished records")
    review_path = OUT / "review_p8.json"
    reviews = read(review_path) if review_path.exists() else {}
    records = []
    for row in ranks["candidates"]:
        key = row["key"]
        d = read(OUT / "stageD" / f"{key}.json")
        if d.get("verdict") not in ("SUBMIT", "HOLD", "KILL"):
            raise RuntimeError(f"{key}: final verdict has not been reviewed")
        if key not in reviews or not reviews[key].get("what_would_change"):
            raise RuntimeError(f"{key}: review needs an explicit follow-up assessment")
        extra = read(OUT / "expensive" / f"{key}.json")
        packet = REPO / "docs/packets/audit_p8" / key
        if not all((packet / name).exists() for name in ("packet.md", "summary.png", "ctoi_fields.json")):
            raise RuntimeError(f"{key}: review packet missing")
        records.append((row, d, extra, reviews[key]))
    if len(records) != f["stageC"]["PASS"]:
        raise RuntimeError("The reviewed list does not equal the Stage C survivors")
    if records:
        refetch = read(OUT / "catalog_refetch_p8.json")
        snapshot = read(OUT / "crossmatch_p8.json")["manifest"]
        if refetch["status"] != "complete" or not snapshot.get("refreshed"):
            raise RuntimeError("Stage D needs a completed fresh catalogue download")
        expected = {item["filename"]: item["sha256"] for item in snapshot["sources"]["spoc_tce"]["files"]}
        received = {item["filename"]: item["sha256"] for item in refetch["files"]}
        if not received or expected != received:
            raise RuntimeError("The SPOC TCE download receipt does not match the hard-stop snapshot")
    submits = [r for r in records if r[1]["verdict"] == "SUBMIT"]
    counts = {v: sum(d["verdict"] == v for _, d, _, _ in records) for v in ("SUBMIT", "HOLD", "KILL")}
    lines = ["# Prompt 8: native-cadence small-star audit", "",
             f"**{counts['SUBMIT']} SUBMIT, {counts['HOLD']} HOLD, {counts['KILL']} KILL** among "
             f"{len(records)} Stage C survivors [M]. " + (
                 "The ordered submission list is empty." if not submits else "The ordered local review list is below."), "",
             "The pipeline finds candidates. Nothing was submitted to an external service.", "",
             "Evidence: [M] measured during P8; [Pn] inherited from prompt n; [A] adopted assumption. "
             "The rule choices were committed before any real P8 candidate entered Stage A.", "",
             "## Population and search", "",
             f"{run['n_targets']:,} targets; search states {run['status_counts']} [M]. Every target has a result record. "
             f"{run['n_budget_stops']} jobs stopped accepting additional sub-searches when their search budget was exhausted [M]. "
             "[Per-target log](../data/survey/p8/per_target_log.csv) records products, sectors, timing, fallbacks and errors.", "",
             f"{ranks['n_population_gaia_record_files']:,} of {ranks['n_population_targets']:,} population stars have "
             "cached Gaia/SIMBAD/VSX record files [M]. V2 ordering uses the Gaia target record; no verdict depends on rank.", ""]
    if run["wall_s_median_p90_max"]:
        med, p90, maximum = run["wall_s_median_p90_max"]
        lines += [f"Per-job wall time: median {med:.1f} s, 90th percentile {p90:.1f} s, maximum {maximum:.1f} s [M]. "
                  "[Population memo](POPULATION_P8.md) documents each cut and the selected cadence.", ""]
    special = search_check["special_sector_1751"]
    lines += [f"The input reconciliation verified {search_check['n_products']:,} products at a common 200 s cadence [M]. "
              f"{special['n_products']} are from the special sector 1751, whose "
              f"[mission release notes]({special['sources'][0]}) describe the January 2026 pointing. "
              "Those products were retained by the existing selection and were not used for the population's minimum "
              f"sector count. The injection sample contains {len(special['calibration_sample_overlap_tics'])} hosts "
              "with this extra sector [M], so its unusual window "
              "is not separately calibrated. "
              "[Input validation and source hashes](../data/survey/p8/search_validation_p8.json).", ""]
    lines += [f"The pre-search Gaia cache acquired the completed survivor-depth context for "
              f"{depth_context['n_stars_with_survivors']:,} hosts before Stage B [M]. "
              f"{depth_context['n_stars_with_depth_capable_neighbour']:,} hosts have at least one neighbour within "
              "63 arcsec able to produce a survivor's depth under the inherited total-eclipse dilution calculation [M]. "
              "This is the existing per-star test against any pre-gate survivor depth, using full saved magnitudes; "
              "it is a HOLD flag, not a source-location measurement. "
              "[Depth-context evidence](../data/survey/p8/neighbour_depth_context_p8.json) records source hashes "
              "and every flag change. The earlier VSX display-separation repair changed no vetting flags.", ""]
    errors = [r for r in csv.DictReader((OUT / "per_target_log.csv").open(encoding="utf-8")) if r["status"] != "ok"]
    if errors:
        lines += ["Searches that did not finish successfully after the retry pass [M]:", "", "| TIC | Status | Reason |", "|---|---|---|"]
        for r in errors:
            lines.append(f"| {r['tic_id']} | {r['status']} | {str(r.get('error', '')).replace('|', '/')} |")
        lines += [""]
    lines += ["## Funnel", "", "| Stage | Entered [M] | Passed / disposition [M] |", "|---|---:|---:|",
              f"| Accepted by search | {f['n_accepted_candidates']:,} | {f['n_accepted_candidates']:,} |",
              f"| Pre-gate | {f['n_accepted_candidates']:,} | {f['n_pass_pregate']:,} |",
              f"| A: event rules | {f['stageA']['n_in']:,} | {f['stageA']['PASS']:,} |",
              f"| Full-phase secondary | {f['secondary']['n_in_passers']:,} | "
              f"{f['secondary']['passers_PASS']} PASS + {f['secondary']['passers_HOLD']} HOLD |",
              f"| B: star and independent-window tests | {f['stageB']['n_in']:,} | {f['stageB']['PASS']:,} |",
              f"| C: blind TLS | {f['stageC']['n_in']:,} | {f['stageC']['PASS']:,} |",
              f"| D: full audit | {len(records)} | {counts} |", "",
              f"The seeded Stage A failure sample contains {f['secondary']['stageA_failure_sample_n']} candidates; "
              f"secondary outcomes are {f['secondary']['stageA_failure_sample_gate']} [M].", ""]
    sa = [read(p) for p in (OUT / "stageA").glob("*.json")]
    if sa:
        seconds = [r["seconds"] for r in sa]
        lines += [f"Native-cadence Stage A measured {np.median(seconds):.1f} s per candidate at the median and "
                  f"{np.percentile(seconds, 90):.1f} s at the 90th percentile, across {len(sa):,} records [M].", ""]
    c_records = sorted((read(p) for p in (OUT / "stageC").glob("tic*.json")), key=lambda r: r["rank"])
    if len(c_records) != f["stageC"]["n_in"]:
        raise RuntimeError("The blind-check records do not equal the Stage C input count")
    if c_records:
        lines += ["### Blind-period verification", "",
                  "The verification search spans 0.5 to 110 d [A]. The population search remains the "
                  "pre-registered 0.5 to 30 d band [A]; an unrelated strongest peak is not a new accepted candidate. "
                  "The frozen C gate requires the strongest peak at SDE >= 9 to match the survey period "
                  "within 1%, or a 2:1/1:2 alias with consistent transit depths [A]. The table retains "
                  "near-survey significance even when the strongest-period requirement fails. "
                  "The linked records contain the exact period/alias comparison.", "",
                  "| TIC | Survey P (d) [M] | Strongest blind P (d) [M] | Blind SDE [M] | SDE within 1% of survey P [M] | Transits at strongest peak [M] | C result [M] |",
                  "|---|---:|---:|---:|---:|---:|---|"]
        def value(number, decimals=3):
            return "unavailable" if number is None else f"{number:.{decimals}f}"
        for rec in c_records:
            blind = rec.get("blind") or {}
            lines.append(f"| [TIC {rec['tic_id']}](../data/survey/p8/stageC/{rec['key']}.json) | "
                         f"{rec['survey_period']:.6f} | {value(blind.get('period'), 6)} | "
                         f"{value(blind.get('SDE'))} | {value(blind.get('SDE_at_survey_period_max_1pct'))} | "
                         f"{blind.get('distinct_transit_count', 'unavailable')} | {rec['decision']} |")
        lines += [""]
    lines += ["## Calibration carried into the search", "",
              f"{comp['n_injections']:,} injections on {comp['n_stars']} stars [M]. "
              "Calibration used p7.0; the selected p8.0 A/secondary choices are the same, with exact Stage B window metadata added. "
              "[The complete map and bootstrap intervals](COMPLETENESS_P8.md) retain every denominator.", "",
              "| Calibration level | Through [M] | SNR50 [M] | SNR90 [M] |", "|---|---:|---:|---:|"]
    for name, rec in comp["levels"].items():
        curve = rec["logistic"]
        lines.append(f"| {name} | {rec['n_through']:,}/{rec['n']:,} | {curve['snr50']:.2f} | {curve['snr90']:.2f} |")
    y = expectation["expected_new_signals"]["through_funnel"]
    lines += ["", f"Expected new signals through the early funnel were {y['low']:.3f}, {y['mid']:.3f}, "
              f"{y['high']:.3f} under low, mid and high incumbent-search completeness priors [M under adopted model assumptions]. "
              "Higher incumbent completeness leaves fewer new signals. The mid value passed the pre-registered 3.0 stop threshold [A]. "
              f"Uninjected controls projected {expectation['expected_funnel_passing_false_alarms']:.2f} early-funnel survivors "
              "over the population [M]. B/C/D efficiency was not calibrated, so these expectations do not predict the final SUBMIT count.", "",
              "## Artefact census", "",
              "A candidate is carried by a class when its strongest observed event is removed by that rule. "
              "The classes overlap; counts must not be summed as independent candidates. The comparison also changes population, "
              "cadence and rule version, so it does not isolate the effect of a single change.", "",
              "| Class | P8 candidates [M] | P6 candidates [P6] | P8 removed events [M] | P6 removed events [P6] |",
              "|---|---:|---:|---:|---:|"]
    for name in old["artefact_classes"]:
        lines.append(f"| {name} | {census['chosen']['carried_by'].get(name, 0)} | {old['chosen']['carried_by'].get(name, 0)} | "
                     f"{census['chosen']['events']['n_excluded_per_class'].get(name, 0)} | {old['chosen']['events']['n_excluded_per_class'].get(name, 0)} |")
    for label, obj, tag in [("P8", census, "M"), ("P6", old, "P6")]:
        chosen = obj["chosen"]
        lines += ["", f"{label}: {chosen['n_carried_by_an_artefact_class']:,}/{obj['n_candidates']:,} candidates "
                  f"are carried by at least one class; {chosen['events']['n_excluded']:,}/{chosen['events']['n_observed']:,} "
                  f"observed epochs were removed [{tag}]."]
        detector_groups = list(chosen["pdc_made_dips_by_sector_camera_ccd"].values())
        pdc_events = sum(group["n_events"] for group in detector_groups)
        camera34 = sum(group["n_events"] for group in detector_groups if group["camera"] in (3, 4))
        ordinary_late = sum(group["n_events"] for group in detector_groups if 56 <= group["sector"] <= 105)
        sector1751 = sum(group["n_events"] for group in detector_groups if group["sector"] == 1751)
        lines += ["", f"{label}: {pdc_events:,} correction-made events in {len(detector_groups):,} "
                  f"sector/camera/CCD/product groups, including {camera34:,} "
                  f"({100 * camera34 / pdc_events:.1f}%) on cameras 3 and 4 [{tag}]. "
                  f"Ordinary sectors 56-105 account for {ordinary_late:,}; special sector 1751 accounts for "
                  f"{sector1751} more [{tag}]."]
    lines += ["", "Flares, fast rotation and noisy faint-star QLP data were anticipated [A]. The upward clipping and measured "
              "rotation proxy were already in the search. The historical P6 count of 291 late-sector correction-made events "
              "covers ordinary sectors 56-105; the stored census also contains two from special sector 1751 [P6]. "
              "The full P8 detector/sector counts are retained in [census_p8.json](../data/survey/p8/census_p8.json).", "",
              "## Individual Stage C survivors", ""]
    if not records:
        lines += ["No candidate survived Stage C. Stage D, the candidate packet list and the submission list are empty [M].", ""]
    for row, d, extra, review in records:
        key = row["key"]
        fitted_period = d["fit"]["adopted"]["period"]
        lines += [f"### Rank {row['rank_v2']}: TIC {row['tic_id']}, fitted P = {fitted_period:.7f} d [M]", "",
                  f"Original survey period: {row['period']:.7f} d [M].", "",
                  f"**{d['verdict']}**: {d['reason']}", "", f"What would change this: {review['what_would_change']}", "",
                  f"[Review packet](packets/audit_p8/{key}/packet.md). "
                  f"FPP {(extra.get('fpp') or {}).get('fpp')}; NFPP {(extra.get('fpp') or {}).get('nfpp')}; "
                  f"fpp_uniform {extra.get('fpp_uniform')} [M].", ""]
    lines += ["## Ordered local submission list", ""]
    if not submits:
        lines += ["Empty. Nothing is ready for external submission under the frozen rules.", ""]
    for i, (row, d, extra, review) in enumerate(submits, 1):
        fields = read(REPO / "docs/packets/audit_p8" / row["key"] / "ctoi_fields.json")
        lines += [f"{i}. TIC {row['tic_id']}, P = {fields['form_fields']['period_days']:.7f} d [M]. "
                  f"[Packet](packets/audit_p8/{row['key']}/packet.md). " + fields["form_fields"]["notes"], ""]
    eb_path = OUT / "eb_review_p8.json"
    if not eb_path.exists():
        raise RuntimeError("The rejected-candidate EB assessment has not been recorded")
    eb = read(eb_path)
    lines += ["## Eclipsing-binary assessment", "", eb["statement"], "", "## Assumptions and limitations [A]", "",
              "The yield model uses DC15 plus the inherited giant occurrence allowance, adopted incumbent-search priors, "
              "representative cells and phase-averaged coverage. The SNR-only logistic fit approaches unit completeness even "
              "though strong signals can still fail event vetoes; the individual-injection bootstrap omits correlation within a host. "
              "The HU19 calculation is a sensitivity proxy. No threshold was retuned on the real candidates.", "",
              "TRICERATOPS uses a binned fold, the inherited circular aperture, its TIC scene and a separately cached wide Gaia "
              "background population. The P8 Gaia cone supports resolved-neighbour assessment and ranking. Uniform scenario "
              "probabilities are labelled as a failed likelihood calculation. Missing pixel/FPP information remains explicit.", "",
              "The non-candidate fit exercises, including TOI-270 c and the recovered P8 injection, are preserved in "
              "[fit_exercises_p8.json](../data/survey/p8/fit_exercises_p8.json). The injection's EXERCISE verdict is never part "
              "of this survey's candidate counts. P8 physical fits start at the ephemeris accepted by Stage C and "
              "record its source hash. A regression test covers survey periods outside the local fit bounds and "
              "factor-two aliases. The first survey-seeded real fit was superseded after this mismatch was found; "
              "[the preserved diagnostic history](../data/survey/p8/fit_seed_repair/first_candidate_before/manifest.json) "
              "and the repeated injection exercise document the correction before the real refit. The frozen gates "
              "and P6/P7 fit behavior were unchanged.", ""]
    path = REPO / "docs/AUDIT_P8.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
