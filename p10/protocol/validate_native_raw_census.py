"""Validate the completed, permitted 37-record native raw-spectrum census.

Reads existing scientific evidence and creates new immutable validation reports.
No TLS execution, decision rewrite, cache-hit C call, or adoption is performed.
"""
from collections import Counter
from pathlib import Path
import json
import os

import native_raw_spectra as N


def main():
    os.chdir(N.Q.REPO)
    output = N.Q.REPO / "p10/results/stage_c_native_raw_validation.json"
    markdown = output.with_suffix(".md")
    N.require(not output.exists() and not markdown.exists(), "Validation report already exists")
    N.Q.assert_source()
    N.no_owners()
    N.require(not N.LOCK.exists(), "Native queue lock is still present")
    state = N.Q.read(N.STATE)
    N.require(state["status"] == "validated_spectra_complete_review_required"
              and state["n_validated"] == 37 and state["active_key"] is None,
              "Native queue has not completed")
    log = N.Q.REPO / "p10/logs/takeover_20260909_native_raw_queue.log"
    N.require("NATIVE_RAW_37_COMPLETE=1" in log.read_text(encoding="utf-8"), "Missing completion marker")
    inventory = N.Q.read(N.INVENTORY)
    measurement_bytes = N.MEASUREMENTS.read_bytes()
    measurement = json.loads(measurement_bytes)
    N.require(measurement["complete"] is True
              and measurement["n_expected"] == measurement["n_validated"] == 37,
              "Incomplete measurement census")
    N.require(measurement["inventory_sha256"] == state["inventory_sha256"] == N.sha(N.INVENTORY),
              "Inventory hash differs")
    expected = {r["key"]: r for r in inventory["rows"]}
    rows = {r["key"]: r for r in measurement["rows"]}
    N.require(len(expected) == len(inventory["rows"]) == len(rows) == len(measurement["rows"]) == 37
              and set(expected) == set(rows), "Missing, extra, or repeated key")
    N.require(Counter(r["set"] for r in rows.values()) == {"p8": 19, "p9": 18}, "Wrong permitted sets")
    N.require(sum(r["reused"] is not None for r in expected.values()) == inventory["reused"] == 8,
              "Initial reused census changed")
    revalidated = []
    for key, item in expected.items():
        row = rows[key]
        N.verify_hashes(item["original_sha256"])
        N.verify_hashes(row["artifacts_sha256"])
        current = N.validate(item, N.Q.REPO / row["workspace"])
        N.require({k: v for k, v in current.items() if k != "utc"}
                  == {k: v for k, v in row.items() if k != "utc"},
                  "Reproduction validation differs: " + key)
        if item["reused"] is None:
            N.require(row["workspace"] == item["new_workspace"] and row["record_rules"] == "p8.0",
                      "Wrong new reproduction workspace/rule: " + key)
        else:
            N.require(row == item["reused"], "Original reused validation differs: " + key)
        revalidated.append(dict(key=key, set=row["set"], reused=item["reused"] is not None,
                                native_decision=row["native_decision"], record_rules=row["record_rules"],
                                workspace=row["workspace"], wall_s=row["wall_s"],
                                statistics=current["statistics"], checks=current["checks"],
                                artifacts_sha256=row["artifacts_sha256"]))
        print("validated", row["set"], key, "reused" if item["reused"] else "new p8.0", flush=True)
    N.Q.assert_source()
    N.no_owners()
    N.require(N.MEASUREMENTS.read_bytes() == measurement_bytes, "Measurement changed during validation")
    triggered = [r for r in revalidated if r["statistics"]["fallback_triggered"]]
    checks = {name: True for name in (
        "native_queue_complete_and_lock_closed", "exact_unique_37_record_census",
        "permitted_19_P8_and_18_P9_records", "eight_original_reuses_and_29_new_reproductions",
        "all_original_and_output_hashes_verified", "all_five_finite_spectrum_arrays",
        "native_grids_and_installed_powers_exact", "all_seven_prepared_arrays_exact",
        "native_input_configuration_and_candidates_exact", "new_p8_rules_and_original_decisions_exact",
        "raw_statistics_recomputed_without_proxy", "saved_measurements_and_timings_unchanged",
        "protected_scientific_source_unchanged", "no_live_native_output_owner")}
    result = dict(
        utc=N.Q.utc(), scope="Only the already-permitted 19 P8 and 18 post-lock P9 Stage C records; raw-spectrum validation, not C adoption.",
        n_expected=37, n_validated=37, n_reused=8, n_new_p8_reproductions=29,
        new_reproduction_wall_sum_s=sum(r["wall_s"] for r in revalidated if not r["reused"]),
        n_installed_concentration_triggers=len(triggered),
        installed_concentration_trigger_keys=[r["key"] for r in triggered],
        checks=checks, rows=revalidated,
        inputs_sha256={str(p.relative_to(N.Q.REPO)): N.sha(p) for p in (
            N.INVENTORY, N.MEASUREMENTS, N.STATE, log,
            Path(N.__file__).resolve(), Path(__file__).resolve())},
        interpretation="The frozen trigger uses installed-power concentration > 0.5; the robust statistic uses power_raw at that same installed strongest peak. Existing experimental C decisions and all control/adoption requirements remain separate. The eight reused walls can include residual work and must not be combined with the 29 new reproduction walls as a paired timing benchmark.")
    lines = ["# P10 completed native raw-spectrum validation [M]", "", result["scope"], "",
             "All 37 records pass the 14 validation groups: eight original reproductions reused and 29 new p8.0 reproductions. Original/native inputs, grids and installed powers reproduce exactly; all five spectrum arrays are finite. Existing records and measured timings were not rewritten.", "",
             f"Installed-concentration triggers: **{len(triggered)}/37**. Trigger keys: " + ", ".join("`" + r["key"] + "`" for r in triggered) + ".", "",
             result["interpretation"], "",
             "| Set | Key | Source | Original native decision | Installed strongest period (d) | Installed SDE | Installed concentration | Raw robust at the same peak | Trigger |",
             "|---|---|---|---|---:|---:|---:|---:|---|"]
    for r in revalidated:
        s = r["statistics"]
        lines.append(f"| {r['set']} | `{r['key']}` | {'Reused' if r['reused'] else 'New p8.0'} | {r['native_decision']} | {s['strongest_period']:.10f} | {s['installed_SDE']:.6f} | {s['installed_concentration']:.10f} | {s['raw_robust_at_installed_strongest']:.6f} | {'Yes' if s['fallback_triggered'] else 'No'} |")
    lines += ["", "Full measurements, validation groups and input/artifact hashes: `stage_c_native_raw_validation.json`. Robust fallback retention and significant-peak adoption still require the documented implementation corrections, fixed injection sample and adversarial/negative/alias controls.", ""]
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    with markdown.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "inputs_sha256")}, indent=2))


if __name__ == "__main__":
    main()
