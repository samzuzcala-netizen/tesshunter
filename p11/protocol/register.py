"""Seal the initial P11 design and metadata-selected audit before measurements."""
import csv
import shutil
import subprocess
from common import REPO, P11, DATA, utc, sha, write, read, host_order, append_event


def main():
    seal = P11 / "protocol/registration_seal.json"
    if seal.exists():
        raise RuntimeError("Already registered; preserve the seal")
    attachment = r"C:\Users\seanj\.codex\attachments\198ec815-95aa-4fbc-a23f-3a45f75bb0cc\pasted-text.txt"
    shutil.copyfile(attachment, P11 / "protocol/PROMPT_P11.txt")
    hosts = list(csv.DictReader((REPO / "data/survey/completeness_sample_p8.csv").open(encoding="utf-8")))
    config = read(P11 / "protocol/config.json")
    selected = []
    for lo, hi, count in config["audit"]["magnitude_strata"]:
        eligible = [r for r in hosts if lo <= float(r["tmag"]) < hi or hi == 14 and float(r["tmag"]) == hi]
        eligible.sort(key=lambda r: host_order(r["tic_id"], "audit"))
        if len(eligible) < count:
            raise RuntimeError("Insufficient audit stratum")
        selected += [dict(r, stratum=f"{lo}-{hi}", selection_probability=count/len(eligible),
                          selection_sha256=host_order(r["tic_id"], "audit")) for r in eligible[:count]]
    write(P11 / "manifests/audit_hosts.json", selected)
    write(P11 / "manifests/development_hosts.json", [dict(r, exposure="entire original 300-star development population") for r in hosts])
    evidence = ["RESUME_P10.md", "HANDOFF_P10.md", "docs/RULES.md", "p9/protocol/PIPELINE_MAP.md",
                "p10/results/part2d_calibration_20260912/STOP_RULE_1.md",
                "p10/results/part2d_calibration_20260912/COMPLETENESS_P10.md",
                "p10/results/search_capacity_final.json", "p10/results/search_capacity_final.md",
                "p10/results/search_injections_e.json", "p10/results/secondary_modes.json", "p10/results/secondary_modes.md",
                "p10/results/stage_c_adoption_20260911.json", "p10/results/stage_c_adoption_20260911.md",
                "p10/results/stage_c_corrected_control_measurements.json", "p10/results/stage_c_native_corrected_20260910.json",
                "data/survey/completeness_sample_p8.csv", "data/survey/p10/injections_2b.csv", "data/survey/injections_p8.csv",
                "data/survey/targets_p8.csv", "data/survey/targets_p8.meta.json"]
    source = [p for folder in ["src", "scripts", "p10/protocol", "tests"] for p in (REPO/folder).rglob("*.py")]
    mapping = {name: sha(REPO/name) for name in evidence}
    mapping.update({p.relative_to(REPO).as_posix(): sha(p) for p in source})
    mapping.update({f"data/survey/audit_lc/tic{r['tic_id']}/index.json": sha(REPO/f"data/survey/audit_lc/tic{r['tic_id']}/index.json") for r in hosts})
    write(P11 / "manifests/entry_source_and_evidence_hashes.json", mapping)
    files = [P11 / "protocol/config.json", P11 / "protocol/PREREGISTRATION.md", P11 / "protocol/PROMPT_P11.txt",
             P11 / "protocol/register.py", P11 / "protocol/common.py", P11 / "manifests/audit_hosts.json",
             P11 / "manifests/development_hosts.json", P11 / "manifests/entry_source_and_evidence_hashes.json"]
    write(seal, dict(utc=utc(), phase="registered before new audit/noise/recovery scores",
                     git_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(),
                     hashes={p.relative_to(REPO).as_posix():sha(p) for p in files}))
    append_event(P11 / "manifests/exposure_ledger.jsonl", dict(event="registration", development="entire original 300 hosts, all historical P8/P9/P10 candidate outcomes, 18 EBs, 22 blends and 37 native C cases", inspected="prompt-required historical summaries, source, metadata, one source FITS header", validation_outcomes_seen=False, reserved_531_ephemerides_opened=False))
    (P11 / "RESUME_P11.md").write_text("# P11 registered; Part A input audit next\n\nInitial registration is sealed. Baseline compatibility is running; no scientific search or validation has begun. Preserve all P8/P9/P10 evidence. Read protocol/registration_seal.json and results/baseline/entry.json. No automation is authorized.\n",encoding="utf-8")
    print("Registered", len(selected), "audit hosts; preserved",len(mapping),"source/evidence/index hashes",flush=True)


if __name__ == "__main__":
    main()
