"""Apply the complete Part 2c conditions, including the prompt's absolute alias check."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[2]


def choose(controls, native):
    assert controls["n_injections"]==30 and controls["n_adversarial_candidates"]==41 and controls["n_adversarial_hosts"]==18
    assert native["n"]==37 and len(controls["half_double_case_ids"])==7
    comparative=dict(TOI_1470_c_flips=native["TOI_1470_c_flips"],
        no_native_alias_flip=native["n_alias_case_flips_among_all_37"]==0,
        no_adversarial_flip=not controls["adversarial_a_to_b_flips"]["installed"]
                            and not controls["adversarial_a_to_b_flips"]["with_fallback"],
        injection_retention_at_least_a=all(controls["injection_b_pass_rate_at_least_a"].values()))
    half_double_fail=not controls["half_double_passes"]["b_installed"] and not controls["half_double_passes"]["b_with_fallback"]
    native_negative_fallback=set(native["fallback_flip_keys"])-{"tic237222864_P10.2888"}
    withdraw=bool(native_negative_fallback or any(controls["adversarial_fallback_fail_to_pass"].values()))
    adopt_b=all(comparative.values()) and half_double_fail
    return dict(comparative_conditions=comparative,comparative_conditions_met=all(comparative.values()),
        prompt_required_all_half_double_cases_fail=half_double_fail,
        significant_peak_adopted=adopt_b,selected_peak_rule="significant_peak" if adopt_b else "strongest",
        robust_fallback_withdrawn=withdraw,robust_fallback_enabled=not withdraw,
        duration_floor_cadence=True,
        selected_injection_column=("b" if adopt_b else "a")+("_installed" if withdraw else "_with_fallback"))


def main():
    sys.path.insert(0,str(ROOT/"p10/protocol"))
    import run_original_adversarial_c_checked as V
    R,Q=V.R,V.Q
    V.load_contract(); Q.closed_prior_queues()
    assert not R.LOCK.exists() and Q.read(R.STATE)["n_complete"]==41
    control_path=ROOT/"p10/results/stage_c_corrected_control_measurements.json"
    native_path=ROOT/"p10/results/stage_c_native_conditions_20260910.json"
    corrected_native_path=ROOT/"p10/results/stage_c_native_corrected_20260910.json"
    controls,native=Q.read(control_path),Q.read(native_path)
    assert controls["all_complete_and_revalidated"] and len(controls["rows"])==71
    Q.verify_hashes(controls["input_sha256"]); Q.verify_hashes(native["input_sha256"])
    Q.verify_hashes(Q.read(corrected_native_path)["input_sha256"])
    decision=choose(controls,native)
    byid={r["id"]:r for r in controls["rows"]}
    alias_rows=[]
    for identifier in controls["half_double_case_ids"]:
        row=byid[identifier]; result=Q.read(ROOT/row["workspace"]/"stageC"/(row["key"]+".json"))
        alias_rows.append(dict(id=identifier,tic_id=row["tic_id"],survey_period=result["survey_period"],
            catalogue_alias=row["survey_to_catalogue_alias"],blind_period=result["blind"]["period"],
            installed_SDE=result["blind"]["SDE"],blind_match=result["blind"]["match"],
            decisions={k:row[k] for k in R.M.COLUMNS},reason=result["reason"],
            no_new_b_or_fallback_pass=len(set(row[k] for k in R.M.COLUMNS))==1))
    hashes={str(p.relative_to(ROOT)):Q.sha(p) for p in
            (control_path,native_path,corrected_native_path,ROOT/"PROMPT_P10.md",Path(__file__),R.MANIFEST,V.CONTRACT,Q.MANIFEST)}
    result=dict(utc=Q.utc(),**decision,controls_complete=71,native_development_complete=37,
        injection_retention=controls["injection_retention"],adversarial_counts=controls["adversarial_counts"],
        half_double_cases=alias_rows,fallback_native=native["fallback_native_interpretation"],
        fallback_EB_triggers=controls["fallback_trigger_ids"],
        interpretation="The comparative adoption conditions in frozen section 0.4 all pass. PROMPT_P10.md 2c(ii) additionally requires the alias rule to fail every half/double-period case; section 0.11 does not waive it. Three of seven pass both (a) and (b), so that required check fails. Retain (a) under the stated otherwise-keep-(a) fallback rather than claim the absolute alias requirement passed. This records the literal pre-existing requirement after its result was measured; it changes no threshold, input, decision or frozen-section text. The baseline also has these three passes, which remain a demonstrated C limitation.",
        coverage_limitation="Both TIC 92743594 candidates lie below their inherited blind grid (R_star=M_star=30.2557). Their FAILs are missing local-period coverage, not demonstrated alias rejection. Original stellar inputs and all +inf empty-duration chi2 values are preserved with exact proofs.",
        exposure=controls["adversarial_exposure"],timing_caveat="The thirteenth injection's original raw wall includes its recorded suspension; no timing is rewritten.",
        source_inputs_sha256=hashes,scientific_worker_source_unchanged_at_decision=True,
        next_stage="Part 2d: freeze p10.0/survey_p10, reproduction and complete 2100-injection calibration; original stop rules still bind.")
    output=ROOT/"p10/results/stage_c_adoption_20260911.json"
    Q.write_new(output,result)
    lines=["# Part 2c: complete C decision [M, A]","", "**Retain strongest-peak (a); retain the conditional robust fallback and cadence duration floor.**","",result["interpretation"],"",
        "| Injection expected-SNR bin | n | a installed/fallback passes | b installed/fallback passes |",
        "|---|---:|---:|---:|"]
    for label,row in controls["injection_retention"].items():
        lines.append(f"| {label} | {row['n']} | {row['a_installed']['pass']} / {row['a_with_fallback']['pass']} | {row['b_installed']['pass']} / {row['b_with_fallback']['pass']} |")
    lines += ["", "No adversarial FAIL-to-PASS change occurs under (b) or fallback. Every paired EB column has 16 PASS and 25 FAIL. Only the named positive HIP 97166 b flips under fallback among the 37 native cases.","",
        "| Half/double EB candidate | Catalogue alias | a | b |","|---|---|---|---|"]
    for row in alias_rows:lines.append(f"| {row['id']} | {row['catalogue_alias']} | {row['decisions']['a_with_fallback']} | {row['decisions']['b_with_fallback']} |")
    lines += ["",result["coverage_limitation"],"",result["exposure"],"",result["timing_caveat"],""]
    with output.with_suffix(".md").open("x",encoding="utf-8") as stream:stream.write("\n".join(lines))
    artifacts=dict(controls["input_sha256"],**Q.read(corrected_native_path)["input_sha256"],**hashes)
    artifacts[str(output.relative_to(ROOT))]=Q.sha(output)
    artifacts[str(output.with_suffix(".md").relative_to(ROOT))]=Q.sha(output.with_suffix(".md"))
    Q.write_new(ROOT/"p10/results/part2c_closed_execution_seal.json",dict(utc=Q.utc(),
        complete=True,queue_closed=True,n_controls=71,n_native_development=37,frozen_section_sha256=Q.FROZEN_SHA,
        artifact_and_original_source_sha256=artifacts,
        transition="Both C manifests describe the completed historical execution. Part 2d may now change shared rule/configuration source to freeze the measured choices; do not invoke an old C controller or treat those documented source changes as evidence corruption. Preserve all recorded artifact hashes and original source provenance.",
        scientific_source_at_seal=Q.read(Q.MANIFEST)["source_sha256"]))
    print(json.dumps(decision,indent=2))


if __name__=="__main__":main()
