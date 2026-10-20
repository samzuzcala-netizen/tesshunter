"""Validate the settled all-37 cadence experiment without rerunning TLS.

Reconstructs p8.0 decisions, spectrum summaries, binning and clipping from saved
artifacts. Records every disagreement and applies only the registered cadence
choice. Native p10c adoption and injection-C execution remain separate work.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
for k, v in {"LIGHTKURVE_CACHE": str(ROOT / "data/cache/lightkurve"), "TESSHUNTER_OFFLINE": "1",
             "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
             "OPENBLAS_NUM_THREADS": "1"}.items():
    os.environ.setdefault(k, v)
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from scipy.stats import chi2 as chi2_distribution
from tesshunter.audit_prep import bin_lc, clip_binned
import resume_cadence as Q

RATIOS = {"1:1": 1., "2:1": 2., "1:2": .5, "3:1": 3., "1:3": 1 / 3, "3:2": 1.5, "2:3": 2 / 3}
PREP_FIELDS = ("products", "n_unbinned", "wotan", "quality_bitmask", "upward_clip_sigma", "R_star", "M_star",
               "expected_t14_hours_b0", "mask_btjd_ranges", "n_unbinned_masked", "n_isolated_clipped",
               "reference_depth_ppt", "per_product", "transit_masked_detrend")
UNBINNED = ("time_unbinned", "flux_unbinned", "sector_unbinned", "trend_unbinned")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def close(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-10)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arrays(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def spectrum_summary(z, survey_period):
    p, w = z["periods"], z["power"]
    require(p.ndim == 1 and len(p) > 0 and p.shape == w.shape, "Malformed spectrum")
    require(all(v.shape == p.shape and np.isfinite(v).all() for v in z.values()), "Nonfinite or unmatched arrays")
    i = int(np.argmax(w)); local = np.flatnonzero(np.abs(p / survey_period - 1) < .01)
    require(len(local) > 0, "No grid point within the survey window")
    j = int(local[np.argmax(w[local])]); work = w.copy(); peaks = []
    for _ in range(10):
        k = int(np.argmax(work))
        if not np.isfinite(work[k]) or work[k] <= 0:
            break
        peaks.append({"period": float(p[k]), "SDE": float(work[k])})
        work[np.abs(p / p[k] - 1) < .02] = -np.inf
    centered_variance = (w - np.mean(w)) ** 2
    concentration = float(np.max(centered_variance) / np.sum(centered_variance))
    robust = None
    if "power_raw" in z:
        raw = z["power_raw"]; median = np.median(raw); mad = np.median(np.abs(raw - median))
        require(mad > 0, "Degenerate raw-power MAD")
        robust = float((raw[i] - median) / (1.4826 * mad))
    return {"n_periods": len(p), "period_min_grid": float(np.min(p)), "period_max_grid": float(np.max(p)),
            "strongest_period": float(p[i]), "installed_sde": float(w[i]), "local_period": float(p[j]),
            "local_sde": float(w[j]), "peaks": peaks, "installed_concentration": concentration,
            "fallback_triggered": concentration > .5, "raw_robust_at_installed_strongest": robust,
            "raw_arrays_available": "power_raw" in z}


def reconstruct_decision(record, tls, summary):
    b = tls["blind"]; period = record["survey_period"]
    require(close(summary["strongest_period"], b["period"]) and close(summary["installed_sde"], b["SDE"]), "Strongest peak mismatch")
    require(close(summary["local_sde"], b["SDE_at_survey_period_max_1pct"]), "Local peak mismatch")
    require(summary["peaks"] == b["peaks"] and record["peaks"] == b["peaks"][:5], "Peak table mismatch")
    require(all(record["blind"][k] == b[k] for k in record["blind"]), "Stage C/TLS blind summary mismatch")
    fraction = {name: abs(b["period"] / (period * ratio) - 1) for name, ratio in RATIOS.items()}
    alias = min(fraction, key=fraction.get)
    same = fraction["1:1"] < .01
    match = {"same_period_1pct": same, "closest_alias": alias, "closest_alias_frac": fraction[alias],
             "alias_1pct": fraction[alias] < .01}
    require(match == b["match"], "Stored period matching differs")
    strong = b["SDE"] >= 9
    consistent = False; alias_p = None
    if strong and not same and match["alias_1pct"] and alias in ("2:1", "1:2"):
        pairs = [(d, e) for d, e in zip(b.get("transit_depths") or [], b.get("transit_depths_uncertainties") or [])
                 if d is not None and e is not None and e > 0]
        if len(pairs) >= 3:
            depth = 1 - np.array([d for d, e in pairs]); errors = np.array([e for d, e in pairs])
            weights = 1 / errors ** 2; mean = np.sum(weights * depth) / np.sum(weights)
            statistic = float(np.sum(((depth - mean) / errors) ** 2))
            alias_p = float(chi2_distribution.sf(statistic, len(pairs) - 1)); consistent = alias_p >= .001
        stored = record["alias_depth_consistency"]
        require(stored["n"] == len(pairs) and stored["consistent"] == consistent, "Alias consistency mismatch")
        require((alias_p is None and stored["p_const"] is None) or close(alias_p, stored["p_const"]), "Alias p-value mismatch")
    decision = "PASS" if strong and (same or consistent) else "FAIL"
    require(decision == record["decision"], "p8.0 decision does not reproduce")
    return {"decision": decision, "match": match, "alias_depth_p_const": alias_p}


def main():
    out = ROOT / "p10/results/stage_c_cadence_validation.json"
    md = out.with_suffix(".md")
    require(not out.exists() and not md.exists(), "Validation exists; review before replacing")
    Q.assert_source()
    require(not Q.tls_owners() and not (Q.RECEIPTS / "cadence_queue.lock").exists(), "Cadence still has a live owner")
    state = Q.read(Q.RECEIPTS / "cadence_queue.json")
    require(state["status"] == "measurements_complete_review_required", "Cadence queue has not completed")
    manifest = Q.manifest(); table_path = ROOT / "p10/results/stage_c_cadence.json"; table = Q.read(table_path)
    table_rows = {(r["set"], r["key"]): r for r in table["rows"]}
    require(len(manifest) == table["n"] == len(table_rows) == 37, "Need the complete registered 37")
    require(set(table_rows) == {(r["set"], r["key"]) for r in manifest}, "Manifest mismatch")
    pilot = json.loads(subprocess.check_output(["git", "show", "656b838:p10/results/stage_c_cadence.json"], cwd=ROOT))
    require(len(pilot["rows"]) == 3, "Missing immutable pilot")
    pilot_walls = {r["key"]: r["wall_s"] for r in pilot["rows"]}
    projection = statistics.median(pilot_walls.values()) * 37 / 3 / 3600
    require(projection <= 12, "Registered sample should have been reduced")
    previous = Q.read(Q.RECEIPTS / "cadence_visibility_stop_20260909T0733Z/resume_preflight.json")
    require(all(digest(ROOT / f["path"]) == f["sha256"] for r in previous["settled"] for f in r["artifacts"]), "A preserved artifact changed")
    rows, all_files = [], {}
    for item in manifest:
        key = item["key"]; native_record_path = ROOT / item["native_record"]
        native_root = native_record_path.parents[1]; ws = Q.OUT / item["set"] / "cadence_600s" / key
        require(Q.complete(item["set"], "cadence_600s", key), "Incomplete case: " + key)
        native = Q.read(native_record_path); new = Q.read(ws / "stageC" / (key + ".json"))
        require(native["survey_period"] == new["survey_period"] and native["survey_depth_ppt"] == new["survey_depth_ppt"], "Candidate changed")
        require(native["rules_version"] == new["rules_version"] == new["p10"]["rules"] == "p8.0", "Rule mismatch")
        require("spectrum_fallback" not in new and "significant_peak" not in new, "Cadence used experimental rules")
        prep_a, prep_b = (Q.read(root / "prep" / (key + ".json")) for root in (native_root, ws))
        require(all(prep_a.get(f) == prep_b.get(f) for f in PREP_FIELDS), "Pre-binning preparation differs: " + key)
        require(prep_a["bin_minutes"] is None and prep_b["bin_minutes"] == 10, "Wrong native/600-s input configuration")
        config_a = prep_a["input_config"]; config_b = prep_b["input_config"]
        require(config_b == dict(config_a, bin_minutes=10.) == new["p10"]["input_config"], "Non-cadence input configuration changed")
        for name in ("candidates.csv", "survivors.csv"):
            require(csv_rows(ws / name) == [r for r in csv_rows(native_root / name) if int(r["tic_id"]) == native["tic_id"]], "Copied survey inputs differ")
        lc_a, lc_b = (arrays(root / "tls" / (key + "_lc.npz")) for root in (native_root, ws))
        require(all(np.array_equal(lc_a[f], lc_b[f], equal_nan=True) for f in UNBINNED), "Unbinned series changed: " + key)
        require(all(np.isfinite(lc_b[f]).all() for f in ("time", "flux", "flux_err")) and np.all(lc_b["flux_err"] > 0), "Invalid prepared samples")
        # Error values do not enter the time/flux bin means or the clip masks.
        tb, fb, eb = bin_lc(lc_a["time_unbinned"], lc_a["flux_unbinned"], np.ones(len(lc_a["time_unbinned"])), 10.)
        ref_depth = prep_b["transit_masked_detrend"]["ephemeris"]["ref_depth_ppt"] / 1000
        clipped = clip_binned(tb, fb, eb, ref_depth)
        require(np.array_equal(clipped["time"], lc_b["time"]) and np.array_equal(clipped["flux"], lc_b["flux"]), "Binning/clip reconstruction differs")
        require(all(clipped[f] == prep_b[f] for f in ("n_isolated_bins_clipped", "n_deep_clipped", "deep_clip_threshold_ppt")), "Clip counters differ")
        require(len(lc_a["time"]) == prep_a["n_binned"] and len(lc_b["time"]) == prep_b["n_binned"] == new["inputs"]["n_binned"], "Prepared counts differ")
        summaries, decisions = {}, {}
        for label, root, record in (("native", native_root, native), ("s600", ws, new)):
            z = arrays(root / "tls" / (key + "_spectrum.npz")); tls = Q.read(root / "tls" / (key + ".json"))
            if label == "s600":
                require(set(z) == {"periods", "power", "chi2", "SR", "power_raw"}, "Missing new raw spectrum arrays")
            require(tls["inputs"]["period_min"] == .5 and tls["inputs"]["period_max"] == 110.
                    and tls["inputs"]["oversampling_factor"] == 3, "Different TLS search domain")
            summary = spectrum_summary(z, native["survey_period"])
            decisions[label] = reconstruct_decision(record, tls, summary)
            summaries[label] = summary
        wall = float(new["p10"]["wall_s"]); tr = table_rows[item["set"], key]
        require(wall > 0 and wall == tr["wall_s"] and (key not in pilot_walls or wall == pilot_walls[key]), "Stored wall changed")
        require(tr["native"] == native["decision"] and tr["s600"] == new["decision"] and tr["agree"] == (native["decision"] == new["decision"]), "Comparison row mismatch")
        reason = None
        if not tr["agree"]:
            if native["decision"] == "PASS" and new["decision"] == "FAIL":
                reason = "survey_window_SDE_below_9" if summaries["s600"]["local_sde"] < 9 else "unrelated_stronger_peak"
                if reason == "unrelated_stronger_peak":
                    require(not decisions["s600"]["match"]["alias_1pct"], "Unexplained alias disagreement")
            elif native["decision"] == "FAIL" and new["decision"] == "PASS":
                require(decisions["s600"]["alias_depth_p_const"] is not None, "Unexplained FAIL-to-PASS")
                reason = "installed_SDE_above_9_at_depth_consistent_2_to_1_alias"
        rows.append({"set": item["set"], "key": key, "survey_period": native["survey_period"],
                     "native": native["decision"], "s600": new["decision"], "agree": tr["agree"], "mechanism": reason,
                     "spectra": summaries, "reconstructed_rules": decisions, "wall_s": wall,
                     "n_native": len(lc_a["time"]), "n_600s": len(lc_b["time"]),
                     "median_cadence_600s": float(np.median(np.diff(np.sort(lc_b["time"]))) * 86400),
                     "clipping": {f: {"native": prep_a[f], "s600": prep_b[f]} for f in
                                  ("n_isolated_bins_clipped", "n_deep_clipped", "deep_clip_threshold_ppt")},
                     "unbinned_arrays_identical": list(UNBINNED), "workspace": str(ws.relative_to(ROOT))})
        for root in (native_root, ws):
            for sub, tail in (("stageC", ".json"), ("prep", ".json"), ("tls", ".json"), ("tls", "_lc.npz"), ("tls", "_spectrum.npz")):
                path = root / sub / (key + tail); all_files[str(path.relative_to(ROOT))] = digest(path)
        for path in ws.rglob("*"):
            if path.is_file(): all_files[str(path.relative_to(ROOT))] = digest(path)
    n_agree = sum(r["agree"] for r in rows); disagreements = [r for r in rows if not r["agree"]]
    require(n_agree == table["agree"] and all(r["mechanism"] for r in disagreements), "Unexplained or miscounted disagreements")
    use_600 = n_agree >= 35
    result = {"utc": datetime.now(timezone.utc).isoformat(), "n": 37, "agree": n_agree, "disagree": len(disagreements),
              "decision_counts": dict(Counter(r["native"] + "->" + r["s600"] for r in rows)),
              "mechanism_counts": dict(Counter(r["mechanism"] for r in disagreements)),
              "pilot_projection_hours": projection, "all_37_required": True, "agreement_required": 35,
              "selected_injection_cadence": "600s" if use_600 else "native", "injection_count": 60 if use_600 else 30,
              "injections_per_bin": 20 if use_600 else 10, "sample_drawn": False,
              "median_600s_wall_s": statistics.median(r["wall_s"] for r in rows), "sum_600s_wall_h": sum(r["wall_s"] for r in rows) / 3600,
              "checks": {name: True for name in ("complete_registered_census_no_live_owner", "immutable_pilot_reused",
                  "all_147_pre_resume_artifacts_unchanged", "same_candidates_rules_and_pre_binning_inputs",
                  "all_unbinned_arrays_identical", "600s_time_flux_binning_and_clips_reproduce",
                  "all_new_raw_arrays_finite", "same_TLS_domain_and_oversampling", "both_native_and_600s_peak_tables_reproduce",
                  "both_p8_decisions_and_alias_tests_reproduce", "all_walls_positive_and_preserved", "every_disagreement_explained")},
              "scope": "Cadence validation only. Native significant-peak/fallback adoption, adversarial controls and injection-C retention remain pending.",
              "interpretation": "The existing 600-s branch changes bin averages, per-bin uncertainties and cadence-dependent clipping together. The row mechanisms identify the measured decision changes; no separate causal counterfactual was run or threshold retuned.",
              "native_raw_gap": "Legacy spectra lack power_raw; their raw robust statistic is null here, never replaced by an installed-power proxy. Native raw-array validation is separate from this cadence comparison.",
              "inputs_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (Path(__file__), table_path, Q.RECEIPTS / "cadence_queue.json")},
              "artifacts_sha256": all_files, "rows": rows}
    text = ["# P10 completed cadence comparison", "", f"{n_agree}/37 decisions agree; 35/37 were required. The registered injection-C cadence is **{result['selected_injection_cadence']}**, with **{result['injection_count']} injections ({result['injections_per_bin']} per bin)**. The sample has not been drawn.", "",
            result["interpretation"], "", "All 37 cases use the same p8.0 decision rule and identical unbinned arrays. All saved peak tables and p8.0 decisions reproduce. No new raw array is missing or nonfinite. The original three pilot timings and all 21 pre-resume workspaces are preserved.", "",
            "| Key | Change | Native SDE | 600-s strongest period / SDE | 600-s local SDE | Decision mechanism |", "|---|---|---:|---:|---:|---|"]
    for r in disagreements:
        a, b = r["spectra"]["native"], r["spectra"]["s600"]
        text.append(f"| {r['key']} | {r['native']} -> {r['s600']} | {a['installed_sde']:.4f} | {b['strongest_period']:.6f} / {b['installed_sde']:.4f} | {b['local_sde']:.4f} | {r['mechanism']} |")
    text.extend(["", result["native_raw_gap"], "", result["scope"], ""])
    with out.open("x", encoding="utf-8") as stream: stream.write(json.dumps(result, indent=2) + "\n")
    with md.open("x", encoding="utf-8") as stream: stream.write("\n".join(text))
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "artifacts_sha256")}, indent=2))


if __name__ == "__main__":
    main()
