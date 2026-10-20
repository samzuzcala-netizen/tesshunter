"""C controls on the original recorded SPOC sectors of the 18 adversarial EBs.

Keeps the original 71-case manifest, all injection results, and the incorrect
sector-filtered EB attempts intact. New input views and 41 EB workspaces live
under P10. Both C rules use the same native 120-s inputs and unchanged science.
The explicit --stage-c-source binding also lets the existing process inspectors
recognize this controller and its case children without changing frozen code.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import run_corrected_c_controls as Q
import measure_completed_c_controls as M

ROOT = Q.ROOT
MANIFEST = ROOT / "p10/results/original_adversarial_c_manifest.json"
STATE = ROOT / "p10/results/takeover_20260908/original_adversarial_c_queue.json"
LOCK = STATE.with_suffix(".lock")
RECEIPTS = ROOT / "p10/results/original_adversarial_c_controls"
INPUT_ROOT = ROOT / "data/survey/p10/stage_c/original_adversarial_inputs"
TAG = "adv_original_spoc_native"
SOURCE = ROOT / "scripts/p10_stage_c.py"
PROFILE = "original_recorded_spoc_120s"


def select_original_products(search, index):
    """Selection depends only on the original search's author and unit IDs."""
    Q.require(search["data_source"] == "SPOC 120 s" and search["data_author"] == "SPOC",
              "Unexpected original adversarial data source")
    units = search["units_used"]
    Q.require(units and len(units) == len(set(units)) == search["n_sectors"], "Invalid original sector census")
    selected = []
    for sector in units:
        matches = [p for p in index["products"] if p["sector"] == sector and p["author"] == "SPOC"
                   and p.get("cadence_s") == 120.0 and p.get("file")]
        Q.require(len(matches) == 1, "Missing or ambiguous original SPOC sector: " + str(sector))
        selected.append(matches[0])
    return selected


def profile_config():
    from tesshunter.survey import get_config
    return get_config("survey_p8", sector_min=None, target_cadence_minutes=2.0, bin_minutes=None)


def load_manifest():
    original = Q.load_manifest()
    data = Q.read(MANIFEST)
    Q.require(data["original_manifest_sha256"] == Q.sha(Q.MANIFEST) and data["profile"] == PROFILE,
              "Original manifest/profile changed")
    expected = [i["id"] for i in original["items"] if i["set"] == "adv"]
    Q.require(len(expected) == len(data["items"]) == 41 and [i["id"] for i in data["items"]] == expected,
              "Original 41-candidate order changed")
    Q.verify_hashes(data["source_sha256"])
    Q.verify_hashes(data["input_sha256"])
    return data


def prepare():
    original = Q.load_manifest()
    Q.closed_prior_queues()
    Q.require(not LOCK.exists() and not MANIFEST.exists() and not INPUT_ROOT.exists(),
              "Existing corrected inputs/manifest require review")
    # Audit every selection before creating any input view.
    hosts, input_hashes = {}, {}
    for item in original["items"]:
        if item["set"] != "adv":
            continue
        rec = item["record"]; tic = rec["tic_id"]
        if str(tic) in hosts:
            continue
        source = ROOT / rec["source"]
        index_path = Path(rec["lc_root"]) / f"tic{tic}" / "index.json"
        search, index = Q.read(source), Q.read(index_path)
        selected = select_original_products(search, index)
        for p in selected:
            path = (index_path.parent / p["file"]).resolve()
            Q.require(path.is_relative_to(index_path.parent.resolve()) and path.is_file(), "Unsafe/missing source product")
            input_hashes[str(path.relative_to(ROOT))] = Q.sha(path)
        input_hashes[str(source.relative_to(ROOT))] = Q.sha(source)
        input_hashes[str(index_path.relative_to(ROOT))] = Q.sha(index_path)
        hosts[str(tic)] = dict(original_search=str(source.relative_to(ROOT)),
                               original_index=str(index_path.relative_to(ROOT)),
                               units_used=search["units_used"], products=selected)
    Q.require(len(hosts) == 18, "All 18 original hosts required")
    INPUT_ROOT.mkdir(parents=True)
    for tic, host in hosts.items():
        destination = INPUT_ROOT / ("tic" + tic); destination.mkdir()
        index_path = ROOT / host["original_index"]
        for product in host["products"]:
            source, target = index_path.parent / product["file"], destination / product["file"]
            shutil.copyfile(source, target)
            Q.require(Q.sha(target) == Q.sha(source), "Input view differs from original product")
            input_hashes[str(target.relative_to(ROOT))] = Q.sha(target)
        view = dict(tic_id=int(tic), profile=PROFILE, original_index=host["original_index"],
                    original_search=host["original_search"], original_units_used=host["units_used"],
                    n_products=len(host["products"]), products=host["products"])
        Q.write_new(destination / "index.json", view)
        input_hashes[str((destination / "index.json").relative_to(ROOT))] = Q.sha(destination / "index.json")
    items = []
    for original_item in original["items"]:
        if original_item["set"] != "adv":
            continue
        item = deepcopy(original_item)
        item["record"]["lc_root"] = str(INPUT_ROOT)
        item["tag"] = TAG
        item["workspace"] = str(Path("data/survey/p10/stage_c/adv") / TAG / item["id"])
        Q.require(not (ROOT / item["workspace"]).exists(), "New workspace already exists")
        items.append(item)
    injection_hashes = {}
    for item in original["items"]:
        if item["set"] != "inj":
            continue
        path = Q.RECEIPTS / (item["id"] + ".json")
        saved, fresh = Q.read(path), Q.validate_case(item)
        Q.require(all(saved[k] == v for k, v in fresh.items()), "Injection changed")
        injection_hashes[str(path.relative_to(ROOT))] = Q.sha(path)
    Q.require(len(injection_hashes) == 30, "All 30 injection controls must be complete")
    input_hashes.update(injection_hashes)
    import audit_p5 as A
    data = dict(utc=Q.utc(), profile=PROFILE, original_manifest_sha256=Q.sha(Q.MANIFEST),
                n_hosts=18, n_candidates=41, threads=8, input_config=A.input_config_for(profile_config()),
                source_sha256={str(p.relative_to(ROOT)): Q.sha(p) for p in (Path(__file__), Path(M.__file__))},
                input_sha256=input_hashes, injection_receipt_sha256=injection_hashes, hosts=hosts, items=items,
                scope="Original recorded SPOC 120-s sectors and all original survey candidates; no catalogue period enters TLS. "
                      "Earlier sector>=56 EB attempts remain diagnostic evidence and do not replace this complete control census.",
                exposure=Q.read(ROOT / "p10/results/stage_c_adversarial_input_inventory.json")["findings"][-1])
    Q.write_new(MANIFEST, data)
    load_manifest()
    print(json.dumps({k: data[k] for k in ("profile", "n_hosts", "n_candidates", "input_config")}, indent=2), flush=True)


def validate_case(item):
    manifest = load_manifest()
    fresh = Q.validate_case(item)
    ws = ROOT / item["workspace"]; key = item["record"]["key"]
    stage = Q.read(ws / "stageC" / (key + ".json"))
    prep = Q.read(ws / "prep" / (key + ".json"))
    Q.require(stage["input_config"] == manifest["input_config"] and stage["p10"]["input_profile"] == PROFILE,
              "Corrected input profile differs")
    host = manifest["hosts"][str(item["record"]["tic_id"]) ]
    Q.require(sorted(p["sector"] for p in prep["per_product"]) == sorted(host["units_used"])
              and all(p["author"] == "SPOC" for p in prep["per_product"]), "Prepared products differ from original recorded sectors")
    fresh["numerical_replay"] = M.replay_saved_decisions(Q, item)
    fresh["input_profile"] = PROFILE
    fresh["replay_helper_sha256"] = Q.sha(Path(M.__file__))
    return fresh


def validate(identifier):
    data = load_manifest(); item = next(i for i in data["items"] if i["id"] == identifier)
    Q.require(not STATE.exists() or Q.read(STATE).get("active_id") != identifier, "Active case cannot be validated")
    path = RECEIPTS / (identifier + ".json"); saved = Q.read(path); fresh = validate_case(item)
    Q.require(all(saved[k] == v for k, v in fresh.items()), "Completed result changed")
    Q.require(Q.sha(ROOT / saved["log"]) == saved["log_sha256"], "Completed log changed")
    print(json.dumps(dict(id=identifier, paired_decisions_reproduced=True, receipt_sha256=Q.sha(path))), flush=True)
    return fresh


def run_case(identifier):
    data = load_manifest()
    Q.require(LOCK.exists() and Q.read(LOCK)["pid"] in {p.pid for p in Q.psutil.Process().parents()},
              "Case requires its guarded parent")
    item = next(i for i in data["items"] if i["id"] == identifier); rec = item["record"]
    Q.require(not (ROOT / item["workspace"]).exists(), "Partial case requires review")
    # Use the original C driver and science functions, with an explicit local
    # input profile before preparation. No shared driver source is patched.
    ws = Q.T.workspace(f"adv/{TAG}", item["id"], Path(rec["source_root"]), rec["tic_id"])
    A, V, _ = Q.T.configure(ws, INPUT_ROOT, rec["stellar"], Q.T.rules_for("p10c"), "native")
    A.set_input_config(profile_config())
    Q.require(A.input_config() == data["input_config"], "Wrong original-input configuration")
    start = time.perf_counter()
    V.stagec_one(dict(tic_id=rec["tic_id"], period=rec["period"], depth_ppt=rec["depth_ppt"], rank=0),
                 threads=8, oversampling=3, force=False)
    path = ws / "stageC" / (rec["key"] + ".json")
    result = A.jload(path)
    result["p10"] = dict(set="adv", tag=TAG, rules="p10c", cadence="native", workspace=item["workspace"],
                         input_config=A.input_config(), input_profile=PROFILE, wall_s=round(time.perf_counter() - start, 1),
                         generated_utc=Q.utc(), candidate_id=identifier)
    Q.T.write(path, result)
    Q.require(result.get("decision") in ("PASS", "FAIL"), "C did not settle: " + str(result.get("reason")))
    print("CASE_DONE", identifier, result["p10"]["wall_s"], flush=True)


def write_state(data):
    temporary = STATE.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(dict(data, utc=Q.utc()), indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATE)


def run_queue():
    data = load_manifest(); Q.closed_prior_queues()
    Q.require(not LOCK.exists(), "Existing corrected queue lock requires review")
    Q.write_new(LOCK, dict(pid=os.getpid(), created=Q.psutil.Process().create_time(), manifest_sha256=Q.sha(MANIFEST)))
    state = dict(pid=os.getpid(), status="validating", n_expected=41, n_complete=0, n_injections_reused=30,
                 active_id=None, threads=8, manifest_sha256=Q.sha(MANIFEST), input_profile=PROFILE)
    try:
        for item in data["items"]:
            Q.closed_prior_queues(); load_manifest()
            path = RECEIPTS / (item["id"] + ".json")
            if path.exists():
                saved, fresh = Q.read(path), validate_case(item)
                Q.require(all(saved[k] == v for k, v in fresh.items()), "Completed EB changed")
                Q.require(Q.sha(ROOT / saved["log"]) == saved["log_sha256"], "Completed EB log changed")
            else:
                log = ROOT / "p10/logs" / ("corrected_c_original_" + item["id"] + ".log")
                Q.require(not (ROOT / item["workspace"]).exists() and not log.exists(), "Partial EB needs preservation/review")
                command = [sys.executable, "-B", str(Path(__file__)), "case", "--id", item["id"], "--stage-c-source", str(SOURCE)]
                state.update(status="running", active_id=item["id"], workspace=item["workspace"],
                             log=str(log.relative_to(ROOT)), command=command)
                write_state(state); print(Q.utc(), "START", item["id"], flush=True)
                with log.open("x", encoding="utf-8") as stream:
                    code = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT).returncode
                Q.require(code == 0, "EB failed; preserve workspace/log: " + item["id"])
                Q.closed_prior_queues(); load_manifest()
                fresh = validate_case(item)
                Q.write_new(path, dict(fresh, utc=Q.utc(), log=str(log.relative_to(ROOT)), log_sha256=Q.sha(log)))
            state["n_complete"] += 1
            state.update(status="validated", active_id=None); write_state(state)
            print(Q.utc(), "VALIDATED", item["id"], state["n_complete"], flush=True)
        state.update(status="controls_complete_review_required", active_id=None); write_state(state)
    except Exception as exc:
        state.update(status="stopped_review_required", error=f"{type(exc).__name__}: {exc}"); write_state(state)
        raise
    finally:
        if LOCK.exists() and Q.read(LOCK)["pid"] == os.getpid():
            LOCK.unlink()


def measure():
    data = load_manifest(); state = Q.read(STATE)
    Q.require(not LOCK.exists() and state["status"] == "controls_complete_review_required"
              and state["n_complete"] == state["n_expected"] == 41 and state["active_id"] is None,
              "All 41 corrected EB controls must close")
    Q.closed_prior_queues()
    Q.require({p.stem for p in RECEIPTS.glob("*.json")} == {i["id"] for i in data["items"]},
              "Corrected receipt census differs from all 41 original candidates")
    output = ROOT / "p10/results/stage_c_corrected_control_measurements.json"
    Q.require(not output.exists() and not output.with_suffix(".md").exists(), "Final control measurement exists")
    original = Q.load_manifest(); items = [i for i in original["items"] if i["set"] == "inj"] + data["items"]
    rows, hashes, replays = [], {}, []
    for item in items:
        if item["set"] == "inj":
            path = Q.RECEIPTS / (item["id"] + ".json"); saved, fresh = Q.read(path), Q.validate_case(item)
            Q.require(all(saved[k] == v for k, v in fresh.items()), "Injection changed")
            replay = M.replay_saved_decisions(Q, item)
            log = ROOT / "p10/logs" / ("corrected_c_" + item["id"] + ".log")
        else:
            path = RECEIPTS / (item["id"] + ".json"); saved = Q.read(path); fresh = validate_case(item)
            Q.require(all(saved[k] == v for k, v in fresh.items()), "Corrected EB changed")
            replay = fresh["numerical_replay"]; log = ROOT / saved["log"]
        Q.require(Q.sha(log) == saved["log_sha256"], "Completed log changed")
        rows.append(fresh); replays.append(replay)
        hashes.update(fresh["artifact_sha256"]); hashes.update({str(path.relative_to(ROOT)): Q.sha(path), str(log.relative_to(ROOT)): Q.sha(log)})
    inventory = Q.read(ROOT / "p10/results/stage_c_adversarial_input_inventory.json")
    result = M.summarize(items, rows, inventory["rows"])
    result.update(utc=Q.utc(), all_complete_and_revalidated=True, new_TLS_runs=0, replay_checks=replays,
                  input_sha256=hashes, original_control_manifest_sha256=Q.sha(Q.MANIFEST),
                  corrected_adversarial_manifest_sha256=Q.sha(MANIFEST), cadence="native", threads=8,
                  adversarial_input_profile=PROFILE, adversarial_exposure=data["exposure"],
                  adoption="not decided by this measurement command",
                  scope="Thirty unchanged original injection controls plus all 41 EBs on their original recorded SPOC 120-s sectors. "
                        "Excluded earlier sector-filtered EB attempts remain preserved. Combine with native conditions for the frozen adoption review.")
    Q.verify_hashes(hashes); Q.write_new(output, result)
    lines = ["# Part 2c: complete corrected C controls [M]", "", result["scope"], "",
             "All 71 controls independently replayed. Original walls and evidence are preserved.", "",
             "| Injection SNR bin | n | a installed | a fallback | b installed | b fallback |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for label, counts in result["injection_retention"].items():
        lines.append(f"| {label} | {counts['n']} | " + " | ".join(f"{counts[c]['pass']}/{counts['n']}" for c in M.COLUMNS) + " |")
    lines += ["", "The JSON retains every EB candidate, half/double case, flip, fallback trigger and evidence hash.", "", data["exposure"], ""]
    with output.with_suffix(".md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    print(json.dumps(dict(output=str(output.relative_to(ROOT)), n_injections=30, n_adversarial_candidates=41)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "inspect", "run", "case", "validate", "measure"))
    parser.add_argument("--id")
    parser.add_argument("--stage-c-source")
    args = parser.parse_args(); os.chdir(ROOT)
    if args.command in ("run", "case"):
        Q.require(args.stage_c_source and Path(args.stage_c_source).resolve() == SOURCE.resolve(),
                  "Explicit binding to the frozen Stage C source required")
    if args.command == "prepare": prepare()
    elif args.command == "inspect":
        data = load_manifest()
        print(json.dumps(dict(utc=Q.utc(), manifest_sha256=Q.sha(MANIFEST), profile=PROFILE,
                              state=Q.read(STATE) if STATE.exists() else None,
                              lock=Q.read(LOCK) if LOCK.exists() else None,
                              owners=Q.owners(), completed_receipts=len(list(RECEIPTS.glob("*.json")))), indent=2))
    elif args.command == "run": run_queue()
    elif args.command == "measure": measure()
    else:
        Q.require(args.id, "Case ID required")
        (run_case if args.command == "case" else validate)(args.id)


if __name__ == "__main__":
    main()
