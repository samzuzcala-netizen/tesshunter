"""Guarded continuation of the full original 2,100-job P10 injection search.

Reuse all 600 selected-e results byte for byte, retaining their original labels.
Only missing jobs run as survey_p10, whose effective configuration is identical.
No outcome-dependent sampling, rule changes, or P8/P9 output writes occur here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import psutil

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "p10/results/part2d_20260911"
RUN = REPO / "data/survey/p10/part2d/injection_search"
ORIGINAL = REPO / "data/survey/runs/p10_2b/e_inj"
SPEC = REPO / "data/survey/injections_p8.csv"
MANIFEST = OUT / "injection_search_manifest.json"
STATE = OUT / "injection_search_state.json"
LOCK = OUT / "injection_search.lock"
FROZEN_SHA = "01bd29efc1b4b57eb6fcc99f340f515c0c2cae2e0162a2e9f96beef92b678f19"
sys.path[:0] = [str(REPO / "src"), str(REPO / "scripts")]
MARKERS = ("run_survey.py", "survey_worker.py", "p10_stage_c.py", "p7_reproduce",
           "run_part2d_reproduction.py", "p8_funnel.py", "p8_completeness.py",
           "run_original_adversarial_c", "run_part2d_injection_search.py")


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
    else:
        temp = path.with_name(path.name + f".{os.getpid()}.tmp")
        temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)


def frozen_section_sha():
    content = (REPO / "HANDOFF_P10.md").read_bytes()
    frozen = content.split(b"## 0. Pre-registered decision rules", 1)[1].split(b"## 1. Part 0: housekeeping", 1)[0]
    return hashlib.sha256(frozen).hexdigest()


def process_snapshot():
    own = {os.getpid(), *(p.pid for p in psutil.Process().parents())}
    found, denied = [], []
    for p in psutil.process_iter():
        try:
            if not p.name().lower().startswith("python") or p.pid in own:
                continue
            command = p.cmdline()
            if not command:
                denied.append(p.pid)
                continue
            if any(marker in " ".join(command) for marker in MARKERS):
                cpu = p.cpu_times()
                found.append(dict(pid=p.pid, ppid=p.ppid(), created_epoch=p.create_time(),
                                  command=command, cpu_user_s=cpu.user, cpu_kernel_s=cpu.system))
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            denied.append(p.pid)
    return dict(utc=utc(), processes=found, inaccessible_pids=denied)


def require_no_workers():
    snap = process_snapshot()
    if snap["processes"] or snap["inaccessible_pids"]:
        raise RuntimeError(f"Existing computation or incomplete visibility: {snap}")
    # run_survey's PID-only orphan terminator must never see a live PID.
    for path in (RUN / "jobs").glob("*.pid"):
        pid = int(path.read_text(encoding="utf-8").strip())
        if psutil.pid_exists(pid):
            raise RuntimeError(f"Live PID file needs identity review, not termination: {path}, {pid}")
    return snap


def effective_config(config):
    result = dict(config)
    result.pop("name", None)
    return result


def expected_jobs():
    from run_survey import build_jobs
    args = SimpleNamespace(injections=str(SPEC), overrides='{"record_traces":true}',
                           config="survey_p10", offline=False, tics=None, limit=None)
    return build_jobs(args)


def check_record(rec, job, config, original):
    assert rec["job_id"] == job["job_id"] and rec["tic_id"] == job["tic_id"]
    assert rec["injection"] == job["injection"] and rec["star"] == job["star"], job["job_id"]
    assert rec["status"] == "ok" and rec.get("orchestrator_status") == "ok", job["job_id"]
    expected_name = "survey_p10_both" if original else "survey_p10"
    assert rec["config"]["name"] == expected_name, job["job_id"]
    assert effective_config(rec["config"]) == effective_config(config), job["job_id"]
    assert rec.get("injection_model") and rec.get("result") is not None, job["job_id"]


def prepare():
    from tesshunter.survey import get_config
    from tesshunter.audit_rules import P10_RULES
    require_no_workers()
    assert read(OUT / "reproduction_complete.json")["status"] == "all_checks_passed"
    assert frozen_section_sha() == FROZEN_SHA
    assert not MANIFEST.exists() and not RUN.exists(), "Preparation is exclusive; never overwrite provenance"
    assert P10_RULES.version == "p10.0" and P10_RULES.stagec_peak_rule == "strongest"
    assert P10_RULES.secondary_gate == "bound" and P10_RULES.duration_floor_cadence and P10_RULES.stagec_sde_robust_fallback
    cfg = get_config("survey_p10", record_traces=True).to_dict()
    assert effective_config(cfg) == effective_config(get_config("survey_p10_both", record_traces=True).to_dict())
    jobs = expected_jobs()
    assert len(jobs) == 2100 and len({j["job_id"] for j in jobs}) == 2100
    by_id = {j["job_id"]: j for j in jobs}
    originals = sorted((ORIGINAL / "results").glob("*.json"))
    assert len(originals) == 600
    reused = [p.stem for p in originals]
    for path in originals:
        check_record(read(path), by_id[path.stem], cfg, original=True)
    source_paths = set((REPO / "src").rglob("*.py")) | set((REPO / "scripts").glob("*.py"))
    source_paths |= {Path(__file__).resolve(), REPO / "p10/protocol/run_part2d_reproduction.py",
                     REPO / "p10/protocol/p7_reproduce_p10.py"}
    source_hashes = {str(p.relative_to(REPO)): sha(p) for p in sorted(source_paths)}
    inputs = {SPEC, REPO / "data/survey/completeness_sample_p8.csv",
              REPO / "p10/results/stage_c_adoption_20260911.json",
              REPO / "p10/results/part2c_closed_execution_seal.json",
              REPO / "p10/results/search_capacity_final.json", OUT / "reproduction_complete.json",
              OUT / "p7_verified.json", OUT / "p8_cached_verified.json", OUT / "p8_fresh_verified.json"}
    # Freeze every relevant raw product plus its complete inventory for all 300 hosts.
    tics = sorted({j["tic_id"] for j in jobs})
    assert len(tics) == 300
    for tic in tics:
        directory = REPO / "data/survey/audit_lc" / f"tic{tic}"
        index = directory / "index.json"
        inputs.add(index)
        products = read(index)["products"]
        relevant = [p for p in products if "file" in p and int(p["sector"]) >= cfg["sector_min"]
                    and p.get("author") in cfg["authors"]]
        assert relevant, tic
        for p in relevant:
            path = (directory / p["file"]).resolve()
            assert path.is_relative_to(directory.resolve()), path
            inputs.add(path)
    input_hashes = {str(p.relative_to(REPO)): sha(p) for p in sorted(inputs)}
    total_copy = sum((ORIGINAL / sub / f"{jid}{suffix}").stat().st_size for jid in reused
                     for sub, suffix in (("jobs", ".json"), ("results", ".json"), ("logs", ".log"), ("traces", ".jsonl")))
    assert shutil.disk_usage(REPO).free > total_copy + 15 * 1024**3
    RUN.mkdir(parents=True, exist_ok=False)
    copied = []
    for sub, suffix in (("jobs", ".json"), ("results", ".json"), ("logs", ".log"), ("traces", ".jsonl")):
        (RUN / sub).mkdir()
        for jid in reused:
            source, dest = ORIGINAL / sub / f"{jid}{suffix}", RUN / sub / f"{jid}{suffix}"
            shutil.copy2(source, dest)
            digest = sha(source)
            assert sha(dest) == digest
            copied.append(dict(source=str(source.relative_to(REPO)), destination=str(dest.relative_to(REPO)), sha256=digest))
    manifest = dict(created_utc=utc(), source_sha256=source_hashes, input_sha256=input_hashes,
        frozen_section_sha256=FROZEN_SHA, configuration=cfg, rules_version="p10.0",
        original_spec=str(SPEC.relative_to(REPO)), total_jobs=2100, original_stars=300,
        reused_ids=reused, pending_ids=[j["job_id"] for j in jobs if j["job_id"] not in reused],
        reused_files=copied, copied_bytes=total_copy, workers=16, hard_timeout_seconds=4500, retries=1,
        provenance="The 600 original e records, job files, logs and traces retain their exact bytes, names, paths and timers. "
                   "The remaining 1500 use survey_p10. All effective configuration fields are identical except name. "
                   "No original baseline-preset result is mixed into this run.")
    assert len(manifest["pending_ids"]) == 1500
    save(MANIFEST, manifest, exclusive=True)
    save(STATE, dict(utc=utc(), status="prepared", total=2100, complete=600, pending=1500,
                    manifest_sha256=sha(MANIFEST)))
    print(json.dumps(dict(manifest=str(MANIFEST), reused=600, pending=1500, copied_bytes=total_copy), indent=2))


def verify_manifest():
    m = read(MANIFEST)
    assert frozen_section_sha() == FROZEN_SHA
    for hashes in (m["source_sha256"], m["input_sha256"]):
        for path, digest in hashes.items():
            assert sha(REPO / path) == digest, f"Frozen source/input changed: {path}"
    for entry in m["reused_files"]:
        for key in ("source", "destination"):
            assert sha(REPO / entry[key]) == entry["sha256"], entry[key]
    return m


def census(m):
    by_id = {j["job_id"]: j for j in expected_jobs()}
    reused = set(m["reused_ids"])
    counts, invalid = Counter(), []
    seen = set()
    for path in (RUN / "results").glob("*.json"):
        try:
            rec = read(path)
            assert path.stem in by_id
            seen.add(path.stem)
            counts[rec.get("status", "missing_status")] += 1
            if rec.get("status") == "ok":
                check_record(rec, by_id[path.stem], m["configuration"], path.stem in reused)
        except (AssertionError, ValueError, KeyError, OSError) as exc:
            invalid.append(dict(path=path.name, error=repr(exc)))
    return dict(total=2100, files=len(seen), counts=dict(counts), pending=2100-len(seen),
                invalid=invalid, all_successful=len(seen)==2100 and counts=={"ok":2100} and not invalid)


def execute():
    require_no_workers()
    save(LOCK, dict(pid=os.getpid(), created_epoch=psutil.Process().create_time(), utc=utc()), exclusive=True)
    try:
        m = verify_manifest()
        initial = census(m)
        assert not initial["invalid"], initial
        if initial["all_successful"]:
            print("Already complete; no child launched")
            return
        cmd = [sys.executable, str(REPO / "scripts/run_survey.py"), "--injections", str(SPEC),
               "--out", str(RUN), "--config", "survey_p10", "--overrides", '{"record_traces":true}',
               "--concurrency", "16", "--timeout", "4500", "--retries", "1", "--resume", "--no-download"]
        save(STATE, dict(utc=utc(), status="running", owner_pid=os.getpid(),
                        owner_created_epoch=psutil.Process().create_time(), command=cmd,
                        manifest_sha256=sha(MANIFEST), initial=initial))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        with (OUT / f"injection_search_{stamp}.log").open("x", encoding="utf-8") as log:
            child = subprocess.Popen(cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
            state = read(STATE)
            state.update(child_pid=child.pid, child_created_epoch=psutil.Process(child.pid).create_time(),
                         log=f"p10/results/part2d_20260911/injection_search_{stamp}.log")
            save(STATE, state)
            code = child.wait()
        verify_manifest()
        final = census(m)
        save(STATE, dict(utc=utc(), status="search_complete_review_required" if final["all_successful"] and code==0
                        else "search_stopped_review_required", exit=code, census=final, manifest_sha256=sha(MANIFEST)))
        assert code == 0 and final["all_successful"], final
    except BaseException as exc:
        save(STATE, dict(utc=utc(), status="stopped_review_required", error=repr(exc),
                        manifest_sha256=sha(MANIFEST) if MANIFEST.exists() else None))
        raise
    finally:
        LOCK.unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("prepare", "run", "inspect"))
    args = ap.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "run":
        execute()
    else:
        m = verify_manifest()
        report = dict(utc=utc(), state=read(STATE), lock=read(LOCK) if LOCK.exists() else None,
                      census=census(m), process_snapshot=process_snapshot())
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = OUT / f"injection_inspect_{stamp}.json"
        save(path, report, exclusive=True)
        print(json.dumps(dict(receipt=str(path), census=report["census"],
                             state=report["state"]["status"], processes=len(report["process_snapshot"]["processes"]),
                             inaccessible_pids=report["process_snapshot"]["inaccessible_pids"]), indent=2))


if __name__ == "__main__":
    main()
