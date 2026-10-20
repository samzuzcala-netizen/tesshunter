"""Resume the frozen P8 real funnel after the existing search/retry launcher finishes.

This driver never starts a survey search, changes a rule, or stamps a verdict.
Each completed stage is checked against its entire eligible list before the next
stage starts. Failed/missing records get one resume pass, then stop loudly.
An operating-system lock prevents two copies of this coordinator running together.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data/survey/p8"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def stage_gaps(root, stage, jobs, cache_matches):
    """Reject missing, stale, errored and otherwise nonterminal stage records."""
    import revet_p6 as V
    folder = "secondary" if stage == "S" else f"stage{stage}"
    field = "gate" if stage == "S" else "decision"
    terminal = {"PASS", "FAIL", "HOLD"} if stage == "S" else {"PASS", "FAIL"}
    gaps = []
    for job in jobs:
        key = V.kkey(job["tic_id"], job["period"])
        path = root / folder / f"{key}.json"
        try:
            rec = read(path)
            if not cache_matches(rec) or rec.get(field) not in terminal:
                gaps.append({"key": key, "state": rec.get(field), "reason": rec.get("reason")})
        except (OSError, ValueError) as exc:
            gaps.append({"key": key, "state": "unreadable", "reason": str(exc)})
    return gaps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--search-log", type=Path, required=True)
    ap.add_argument("--slices", type=int, default=16)
    args = ap.parse_args(argv)
    os.chdir(REPO)
    os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data/cache/lightkurve"))
    os.environ["PYTHONIOENCODING"] = "utf-8"
    for name in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ[name] = "1"
    logdir = OUT / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    # The handle remains open for the whole coordinator lifetime; process exit
    # releases this lock, including after a desktop interruption.
    import msvcrt
    with (logdir / "finish_funnel.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        run(args)


def run(args):
    import audit_p5 as A
    import p8_funnel as F
    from tesshunter.audit_rules import P8_RULES
    F.set_root(OUT)
    F.set_rules("p8.0")
    if P8_RULES is None or P8_RULES.version != "p8.0":
        raise RuntimeError("P8 is not frozen")
    freeze = OUT / "freeze_p8.json"
    committed = subprocess.check_output(
        ["git", "show", "HEAD:data/survey/p8/freeze_p8.json"], cwd=REPO)
    # Git's Windows checkout may use CRLF; compare the evidence, not line endings.
    if json.loads(committed) != read(freeze):
        raise RuntimeError("Freeze evidence must match the committed file")
    state = {"started_utc": utc(), "rules_version": "p8.0", "stages": {}}

    def save(phase, **extra):
        state.update(phase=phase, updated_utc=utc(), **extra)
        A.jdump(OUT / "funnel_progress_p8.json", state)
        print(utc(), phase, flush=True)

    def command(stage, extra=()):
        save(stage)
        return subprocess.run([sys.executable, "-u", "scripts/p8_funnel.py", "--rules", "p8.0",
                               stage, *extra], cwd=REPO).returncode

    save("waiting_for_existing_search_and_retry")
    while True:
        if args.search_log.exists() and "=== DONE search ===" in args.search_log.read_text(
                encoding="utf-8", errors="replace"):
            break
        time.sleep(30)
    subprocess.run([sys.executable, "scripts/p8_per_target_log.py"], cwd=REPO, check=True)
    targets = list(csv.DictReader((REPO / "data/survey/targets_p8.csv").open(encoding="utf-8")))
    missing = [r["tic_id"] for r in targets if not (F.RUN / "results" / f"tic{r['tic_id']}.json").exists()]
    if missing:
        save("blocked_missing_search_results", missing_search_tics=missing)
        raise RuntimeError(f"Search completed without records for {len(missing)} targets")
    if command("collect"):
        raise RuntimeError("Candidate collection failed")
    for stage, cmd in (("A", "stageA"), ("S", "secondary"), ("B", "stageB"), ("C", "stageC")):
        jobs = F.eligible(stage)
        start = time.perf_counter()
        for attempt in (1, 2):
            slices = min(8 if stage == "B" else args.slices, max(1, len(jobs)))
            code = command(cmd, ["--slices", str(slices), "--threads", "1", "--shared-queue"])
            gaps = stage_gaps(OUT, stage, jobs, A.cache_matches)
            state["stages"][stage] = {"n_expected": len(jobs), "attempt": attempt,
                                      "exit_code": code, "gaps": gaps,
                                      "wall_seconds": round(time.perf_counter() - start, 1)}
            save(f"checked_{cmd}")
            if code == 0 and not gaps:
                break
        else:
            save(f"blocked_{cmd}")
            raise RuntimeError(f"{cmd} failed after its resume pass; see funnel_progress_p8.json")
    # Exercise evidence must exist before any real fit/CTOI call.
    demo = OUT / "demo_inj/stageD/tic154567574_P6.3063.json"
    save("waiting_for_injection_exercise")
    while True:
        rec = read(demo) if demo.exists() else {}
        if (A.cache_matches(rec) and rec.get("verdict") == "SUBMIT"
                and "EXERCISE" in rec.get("reason", "") and rec.get("ctoi_fields_path")):
            break
        time.sleep(30)
    if command("stageD"):
        raise RuntimeError("Stage D failed")
    errors = []
    for job in F.eligible("D"):
        key = F.V.kkey(job["tic_id"], job["period"])
        path = OUT / "stageD" / f"{key}.json"
        rec = read(path) if path.exists() else {}
        if not A.cache_matches(rec) or rec.get("verdict") == "ERROR" or not rec.get("provisional_verdict"):
            errors.append(key)
    if errors:
        save("blocked_stageD_records", stageD_errors=errors)
        raise RuntimeError(f"Stage D has {len(errors)} invalid records")
    for cmd in ("funnel", "census"):
        if command(cmd):
            raise RuntimeError(f"{cmd} failed")
    save("stageD_pixels_fpp_packets")
    subprocess.run([sys.executable, "-u", "scripts/p8_stage_d_packets.py", "--workers", "4"],
                   cwd=REPO, check=True)
    save("measurements_and_packets_complete_pending_review")


if __name__ == "__main__":
    main()
