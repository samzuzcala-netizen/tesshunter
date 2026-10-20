"""Measure the complete frozen C-control census without TLS or rule adoption.

The command refuses live, interrupted or incomplete queues. It revalidates every
receipt and replays decisions from saved spectra/ephemerides before reporting
the four paired columns. The final C adoption review also needs the separately
validated native cases; this report does not freeze p10.0 or write old evidence.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = ("a_installed", "a_with_fallback", "b_installed", "b_with_fallback")
BINS = {"7_12": (7, 12), "12_20": (12, 20), "20_50": (20, 50)}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def require_complete_queue(state, has_lock):
    require(not has_lock and state.get("status") == "controls_complete_review_required"
            and state.get("n_expected") == state.get("n_complete") == 71
            and state.get("active_id") is None, "All 71 controls must finish and the queue must close")


def summarize(items, receipts, adversarial):
    """Counts use unique original candidate IDs, including rounded-key collisions."""
    require(len(items) == len(receipts) == 71, "Complete 71-case census required")
    expected = {r["id"]: r for r in items}
    actual = {r["id"]: r for r in receipts}
    require(len(expected) == len(actual) == 71 and set(expected) == set(actual),
            "Missing, duplicate or extra control identity")
    require(Counter(r["set"] for r in items) == {"inj": 30, "adv": 41}, "Wrong control populations")
    adv = {r["candidate_id"]: r for r in adversarial}
    require(len(adv) == len(adversarial) == 41
            and set(adv) == {r["id"] for r in items if r["set"] == "adv"}
            and len({r["tic_id"] for r in adversarial}) == 18, "Original 18-EB/41-candidate census required")
    rows = []
    for item in items:
        r = actual[item["id"]]
        rec = item["record"]
        require(r["set"] == item["set"] and r["key"] == rec["key"]
                and r["workspace"] == item["workspace"], "Unpaired control metadata")
        require(all(r[c] in ("PASS", "FAIL") for c in COLUMNS), "Unsettled paired C decision")
        require(math.isfinite(r["wall_s"]) and r["wall_s"] > 0, "Original positive wall required")
        row = {k: r[k] for k in ("id", "set", "key", "workspace", "wall_s", "fallback", *COLUMNS)}
        if item["set"] == "inj":
            label, snr = r["bin"], r["snr_expected"]
            require(label in BINS and label == rec["bin"] and snr == rec["snr_expected"]
                    and math.isfinite(snr) and BINS[label][0] <= snr < BINS[label][1], "Changed injection bin/SNR")
            row.update(bin=label, snr_expected=snr)
        else:
            original = adv[item["id"]]
            require(original["key"] == r["key"] and original["tic_id"] == rec["tic_id"], "EB identity changed")
            row.update(tic_id=original["tic_id"], survey_to_catalogue_alias=original["survey_to_catalogue_alias"])
        rows.append(row)
    injections = [r for r in rows if r["set"] == "inj"]
    ebs = [r for r in rows if r["set"] == "adv"]
    require(Counter(r["bin"] for r in injections) == {b: 10 for b in BINS}, "Exactly ten original injections per bin required")
    half_double = [r for r in ebs if r["survey_to_catalogue_alias"] in ("1:2", "2:1")]
    require(len(half_double) == 7, "The seven original half/double candidates must be retained")

    def counts(group):
        return {"n": len(group), **{c: {"pass": sum(r[c] == "PASS" for r in group),
                "fail": sum(r[c] == "FAIL" for r in group),
                "retention": sum(r[c] == "PASS" for r in group) / len(group)} for c in COLUMNS}}

    def flips(group, before, after):
        return [r["id"] for r in group if r[before] == "FAIL" and r[after] == "PASS"]

    retention = {b: counts([r for r in injections if r["bin"] == b]) for b in BINS}
    retention["all"] = counts(injections)
    return {"n_injections": 30, "n_adversarial_hosts": 18, "n_adversarial_candidates": 41,
            "injection_retention": retention,
            "injection_b_pass_rate_at_least_a": {s: retention["all"]["b_" + s]["pass"] >= retention["all"]["a_" + s]["pass"]
                                                   for s in ("installed", "with_fallback")},
            "adversarial_counts": counts(ebs),
            "adversarial_a_to_b_flips": {s: flips(ebs, "a_" + s, "b_" + s) for s in ("installed", "with_fallback")},
            "adversarial_fallback_fail_to_pass": {r: flips(ebs, r + "_installed", r + "_with_fallback") for r in ("a", "b")},
            "half_double_case_ids": [r["id"] for r in half_double],
            "half_double_passes": {c: [r["id"] for r in half_double if r[c] == "PASS"] for c in COLUMNS},
            "fallback_trigger_ids": [r["id"] for r in rows if r["fallback"]["triggered"]],
            "rows": rows}


def verify_saved_spectrum_peak(arrays, blind, oversampling_factor):
    """Reproduce TLS normalization exactly without fitting or changing arrays."""
    import numpy as np
    from transitleastsquares.stats import spectra

    p, w = arrays["periods"], arrays["power"]
    strongest = {"period": blind["period"], "SDE": blind["SDE"], "index": int(np.argmax(w))}
    require(float(p[strongest["index"]]) == blind["period"],
            "Saved strongest period differs from the full spectrum")
    # TLS computes scalar SDE before a final multiply rescales power. The
    # rescaled maximum can differ by a rounding bit; it is not the scalar's
    # definition. Reproduce both outputs from the saved chi2, using the saved
    # oversampling factor, rather than weakening the check with a tolerance.
    sr, power_raw, power, _, sde = spectra(arrays["chi2"], oversampling_factor)
    require(np.array_equal(sr, arrays["SR"]) and np.array_equal(power_raw, arrays["power_raw"])
            and np.array_equal(power, w), "Saved TLS normalization arrays differ from chi2")
    require(float(sde) == blind["SDE"], "Saved strongest SDE differs from TLS normalization")
    return strongest


def replay_saved_decisions(q, item):
    """Only saved arrays, masks and ephemerides; never call a TLS/cache writer."""
    import numpy as np
    import audit_p5 as a
    import revet_p6 as v
    c = q.C
    ws, rec = q.ROOT / item["workspace"], item["record"]
    key, period = rec["key"], rec["period"]
    saved = q.read(ws / "stageC" / (key + ".json"))
    tls = q.read(ws / "tls" / (key + ".json")); blind = tls["blind"]
    with np.load(ws / "tls" / (key + "_spectrum.npz"), allow_pickle=False) as z:
        p, w = z["periods"], z["power"]
        strongest = verify_saved_spectrum_peak(z, blind, tls["inputs"]["oversampling_factor"])
    with np.load(ws / "tls" / (key + "_lc.npz"), allow_pickle=False) as z:
        times = z["time"]
    cadence_s = float(np.median(np.diff(np.sort(times)))) * 86400
    local = c.local_peak(p, w, period)
    peaks = a._peak_table(p, w, n=len(p), min_power=local["sde"]) if local["sde"] is not None else []
    match = a._match(blind["period"], period)
    require(match == blind["match"], "Saved period match differs")
    fallback = v.spectrum_fallback(SimpleNamespace(OUT=ws), rec["tic_id"], period)
    require(fallback == saved["spectrum_fallback"], "Raw robust/installed concentration measurement differs")
    sp = saved["significant_peak"]
    require(local == sp["local"] and peaks == sp["stronger_peak_census"], "Local/stronger-peak census differs")
    indices = {f"{r['period']:.6f}": i for i, r in enumerate(peaks)}

    def ephemeris(peak):
        if abs(peak / blind["period"] - 1) < 1e-6:
            return blind
        narrow = q.read(ws / "tls" / f"{key}_peak{indices[f'{peak:.6f}']}.json")
        require(narrow["peak_period"] == peak and narrow["input_config"] == tls["input_config"], "Narrow ephemeris input differs")
        summary = narrow["narrow"]
        require(c.duration_summary(summary, cadence_s) == summary, "Narrow duration floor missing")
        return summary

    adc, transits, residual = {}, {}, {}
    for peak_key, measurement in sp["alias_depth_measurements"].items():
        peak = blind["period"] if peak_key == f"{blind['period']:.6f}" else peaks[indices[peak_key]]["period"]
        fresh = v.alias_depths_consistent(ephemeris(peak))
        require(all(measurement[k] == value for k, value in fresh.items()), "Per-peak alias depths differ")
        adc[peak_key] = fresh["consistent"]
    for run in sp["runs"]:
        peak, peak_key = run["period"], f"{run['period']:.6f}"
        eph = ephemeris(peak)
        require(run["t0"] == eph["T0_btjd"] and run["duration_days"] == eph["duration_raw_days"], "Stronger-peak ephemeris differs")
        duration = c.floor_duration(run["duration_days"], cadence_s)["floored_days"] or cadence_s / 86400
        require(duration == run["duration_used_days"], "Mask duration differs from the registered floor")
        n = c.covered_transits(times, peak, run["t0"], duration, cadence_days=cadence_s / 86400) if run["t0"] is not None else 0
        require(n == run["covered_transits"], "Covered-transit census differs")
        transits[peak_key] = n
        if run.get("residual_suffix"):
            require(n >= 3, "Residual search without three covered transits")
            stem = key + run["residual_suffix"]
            res = q.read(ws / "tls" / (stem + ".json"))
            mask = a.transit_mask(times, peak, run["t0"], duration, n_durations=1.0)
            require(int(mask.sum()) == run["n_cadences_masked"] == res["blind"]["residual_mask"]["n_cadences_masked"], "Residual mask differs")
            with np.load(ws / "tls" / (stem + "_spectrum.npz"), allow_pickle=False) as z:
                residual[peak_key] = c.local_peak(z["periods"], z["power"], period)
            require(residual[peak_key] == run["residual_local"], "Residual local spectrum differs")
    period_ok = match["same_period_1pct"] or (match["alias_1pct"] and match["closest_alias"] in ("2:1", "1:2")
                                             and v.alias_depths_consistent(blind)["consistent"])
    a0 = "PASS" if period_ok and blind["SDE"] >= 9 else "FAIL"
    a1 = "PASS" if period_ok and (blind["SDE"] >= 9 or fallback["passes_on_robust"]) else "FAIL"
    b0 = c.significant_peak(period, strongest, peaks, local, transits, residual, adc)
    b1 = c.significant_peak(period, strongest, peaks, local, transits, residual, adc, fallback)
    require(a0 == saved["decision_strongest_installed"] and a1 == saved["decision_strongest"]
            and b0["decision"] == saved["decision_significant_installed"] and b1["decision"] == saved["decision"],
            "Replayed paired decisions differ")
    require(all(sp["installed_only"][k] == value for k, value in b0.items())
            and all(sp[k] == value for k, value in b1.items()), "Replayed blocking analysis differs")
    return {"id": item["id"], "paired_decisions_reproduced": True, "stronger_peaks": len(peaks),
            "alias_measurements": len(adc), "coverage_measurements": len(transits), "residual_measurements": len(residual)}


def main():
    output = ROOT / "p10/results/stage_c_corrected_control_measurements.json"
    markdown = output.with_suffix(".md")
    require(not output.exists() and not markdown.exists(), "Completed control measurement already exists; preserve it")
    sys.path.insert(0, str(ROOT / "p10/protocol"))
    import run_corrected_c_controls as q
    manifest = q.load_manifest()
    require_complete_queue(q.read(q.STATE), q.LOCK.exists())
    q.closed_prior_queues()
    expected = {r["id"] for r in manifest["items"]}
    require({p.stem for p in q.RECEIPTS.glob("*.json")} == expected, "Receipt identities do not match the frozen census")
    inventory_path = ROOT / "p10/results/stage_c_adversarial_input_inventory.json"
    inventory = q.read(inventory_path)
    hashes = {str(p.relative_to(ROOT)): q.sha(p) for p in (q.MANIFEST, q.STATE, inventory_path, Path(__file__))}
    receipts, replay = [], []
    for item in manifest["items"]:
        path = q.RECEIPTS / (item["id"] + ".json")
        saved, fresh = q.read(path), q.validate_case(item)
        require(all(saved[k] == value for k, value in fresh.items()), "Completed evidence changed: " + item["id"])
        log = ROOT / "p10/logs" / ("corrected_c_" + item["id"] + ".log")
        require(q.sha(log) == saved["log_sha256"], "Completed case log changed")
        hashes.update({str(path.relative_to(ROOT)): q.sha(path), str(log.relative_to(ROOT)): q.sha(log), **fresh["artifact_sha256"]})
        replay.append(replay_saved_decisions(q, item))
        receipts.append(fresh)
    result = summarize(manifest["items"], receipts, inventory["rows"])
    result.update(utc=datetime.now(timezone.utc).isoformat(), cadence="native", threads=8,
                  all_complete_and_revalidated=True, new_TLS_runs=0, replay_checks=replay,
                  input_sha256=hashes, scope="Complete paired C-control measurement only; combine with the 37 native cases for the frozen adoption/withdrawal review.",
                  adversarial_exposure=inventory["findings"][-1], adoption="not decided by this measurement command")
    lines = ["# Part 2c: completed corrected native controls [M]", "", result["scope"], "",
             "30 frozen S-passing injections; 41 survey candidates from the original 18 EBs. All saved paired decisions reproduce without TLS. Original measured walls are preserved.", "",
             "| Injection SNR bin | n | a installed | a fallback | b installed | b fallback |", "|---|---:|---:|---:|---:|---:|"]
    for label, counts in result["injection_retention"].items():
        lines.append(f"| {label} | {counts['n']} | " + " | ".join(f"{counts[c]['pass']}/{counts['n']} ({counts[c]['retention']:.1%})" for c in COLUMNS) + " |")
    lines += ["", "| EB candidate | Key | Survey/catalogue alias | a installed | a fallback | b installed | b fallback |", "|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        if r["set"] == "adv":
            lines.append(f"| {r['id']} | {r['key']} | {r['survey_to_catalogue_alias']} | " + " | ".join(r[c] for c in COLUMNS) + " |")
    lines += ["", "The JSON records all triggers, half/double passes, adversarial flips, exact injection counts and evidence hashes. These are inputs to the frozen adoption/withdrawal rule, not permission to inspect later-stage outcomes.", "", result["adversarial_exposure"], ""]
    q.write_new(output, result)
    with markdown.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "input_sha256", "replay_checks")}, indent=2))


if __name__ == "__main__":
    main()
