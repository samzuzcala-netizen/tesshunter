"""Checkpointed, resumable survey orchestrator.

One subprocess per job (``survey_worker.py``), N at a time. Every job's
result is a separate JSON file written atomically, so the results directory
IS the checkpoint: ``--resume`` rescans it and runs only what is missing or
still eligible for a retry. Killing this process (or its whole tree) at any
moment loses at most the jobs that were mid-flight, and they are rerun on
resume. Nothing else is needed for recovery.

Examples
--------
Prefetch (download + stitch + cache, no search) 300 sampled stars at 8 wide::

    python scripts/run_survey.py --sample data/survey/completeness_sample_v1.csv \
        --out data/survey/runs/prefetch_v1 --prefetch --concurrency 8

Search the same stars with no injection (false-alarm run + timing)::

    python scripts/run_survey.py --sample data/survey/completeness_sample_v1.csv \
        --out data/survey/runs/fa_v1 --concurrency 16 --resume

Injection-recovery run from a spec file (one job per row)::

    python scripts/run_survey.py --injections data/survey/injections_v1.csv \
        --out data/survey/runs/inj_v1 --concurrency 16 --resume
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "scripts" / "survey_worker.py"
PY = sys.executable

STAR_FIELDS = ("radius_rsun", "mass_msun", "teff_k", "tmag", "contamination_ratio_used")


def _float_or_none(v):
    try:
        x = float(v)
        return x if x == x else None       # NaN -> None
    except (TypeError, ValueError):
        return None


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_jobs(args) -> list[dict]:
    """Jobs from a target/sample CSV (one per star) or an injection spec."""
    overrides = json.loads(args.overrides) if args.overrides else {}
    if args.injections:
        rows = _read_csv(Path(args.injections))
        jobs = []
        for r in rows:
            star = {k: _float_or_none(r.get(k)) for k in STAR_FIELDS if k in r}
            inj = {
                "period": float(r["period"]), "rp_rs": float(r["rp_rs"]), "b": float(r["b"]),
                "t0_frac": float(r.get("t0_frac", 0.5)),
            }
            for k in ("a_rs", "u1", "u2"):
                if r.get(k) not in (None, ""):
                    inj[k] = float(r[k])
            jobs.append({
                "job_id": r["job_id"], "tic_id": int(r["tic_id"]), "config": args.config,
                "overrides": overrides, "star": star, "injection": inj,
                "offline": bool(args.offline),
            })
    else:
        src = Path(args.sample or args.targets)
        rows = _read_csv(src)
        jobs = []
        for r in rows:
            star = {k: _float_or_none(r.get(k)) for k in STAR_FIELDS if k in r}
            jobs.append({
                "job_id": f"tic{int(r['tic_id'])}", "tic_id": int(r["tic_id"]),
                "config": args.config, "overrides": overrides, "star": star,
                "prefetch_only": bool(args.prefetch), "offline": bool(args.offline),
                "refresh": bool(args.refresh),
            })
    if args.tics:
        want = {int(x) for x in args.tics.split(",") if x.strip()}
        jobs = [j for j in jobs if j["tic_id"] in want]
    if args.limit:
        jobs = jobs[: args.limit]
    return jobs


def _pid_alive(pid: int) -> bool:
    """True when a process with this id is still running (Windows and POSIX)."""
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            return bool(ok) and code.value == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _terminate(pid: int) -> None:
    if sys.platform == "win32":
        import ctypes
        PROCESS_TERMINATE = 0x0001
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
        if h:
            ctypes.windll.kernel32.TerminateProcess(h, 1)
            ctypes.windll.kernel32.CloseHandle(h)
    else:
        import signal
        os.kill(int(pid), signal.SIGKILL)


def reap_orphan(job_id: str, out_dir: Path) -> str | None:
    """A worker left running by a killed orchestrator is terminated before the
    job is rerun, so two attempts never race on the same result file."""
    pid_file = out_dir / "jobs" / f"{job_id}.pid"
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        pid_file.unlink(missing_ok=True)
        return None
    if _pid_alive(pid):
        _terminate(pid)
        pid_file.unlink(missing_ok=True)
        return f"terminated orphaned worker pid {pid}"
    pid_file.unlink(missing_ok=True)
    return None


def result_status(path: Path) -> tuple[str | None, int]:
    """(status, attempts) of an existing result file, or (None, 0)."""
    if not path.exists():
        return None, 0
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "corrupt", 0
    return d.get("status"), int(d.get("attempts", 1))


def run_one(job: dict, out_dir: Path, timeout_s: float, attempt: int, extra_args: list[str]) -> dict:
    job_dir = out_dir / "jobs"
    res_dir = out_dir / "results"
    log_dir = out_dir / "logs"
    job_path = job_dir / f"{job['job_id']}.json"
    res_path = res_dir / f"{job['job_id']}.json"
    log_path = log_dir / f"{job['job_id']}.log"
    job_path.write_text(json.dumps(job, indent=1), encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
           "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
    env.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
    cmd = [PY, str(WORKER), "--job", str(job_path), "--out", str(res_path), *extra_args]
    t0 = time.perf_counter()
    status, rc = "ok", None
    pid_file = job_dir / f"{job['job_id']}.pid"
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"\n=== attempt {attempt} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===\n")
        fh.flush()
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        try:
            rc = proc.wait(timeout=timeout_s)
            if rc != 0:
                status = "error"
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            status = "timeout"
        finally:
            pid_file.unlink(missing_ok=True)
    wall = time.perf_counter() - t0
    # Stamp attempts / timeout into the result file (or write a stub on timeout)
    rec = None
    if res_path.exists():
        try:
            rec = json.loads(res_path.read_text(encoding="utf-8"))
        except Exception:
            rec = None
    if rec is None:
        rec = {"job_id": job["job_id"], "tic_id": job["tic_id"], "status": status if status != "ok" else "error",
               "error": f"worker exited rc={rc} without a result" if status != "timeout" else f"timeout after {timeout_s:.0f} s",
               "result": None, "timings": {"total": wall}, "wall_s": wall}
    rec["attempts"] = attempt
    rec["orchestrator_status"] = status
    rec["orchestrator_wall_s"] = wall
    tmp = res_path.with_name(res_path.name + ".orch.part")
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    os.replace(tmp, res_path)
    final = rec.get("status", status)
    print(f"[{job['job_id']}] attempt {attempt}: {final} rc={rc} wall={wall:.0f}s", flush=True)
    with open(out_dir / "progress.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"job_id": job["job_id"], "status": final, "attempt": attempt,
                             "wall_s": round(wall, 1), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
    return {"job_id": job["job_id"], "status": final, "attempt": attempt, "wall_s": wall}


def summarize(out_dir: Path) -> Path:
    """Flatten every result JSON into summary.csv (one row per job)."""
    rows = []
    for p in sorted((out_dir / "results").glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            rows.append({"job_id": p.stem, "status": "corrupt"})
            continue
        res = d.get("result") or {}
        tm = res.get("timings") or {}
        cache = d.get("cache") or {}
        planets = res.get("planets") or []
        row = {
            "job_id": d.get("job_id"), "tic_id": d.get("tic_id"), "status": d.get("status"),
            "attempts": d.get("attempts"), "wall_s": round(float(d.get("wall_s") or 0.0), 1),
            "search_s": round(float((d.get("timings") or {}).get("search") or 0.0), 1),
            "preprocess_s": round(float(tm.get("preprocess") or 0.0), 1),
            "detect_s": round(float(tm.get("detect") or 0.0), 1),
            "vet_s": round(float(tm.get("vet") or 0.0), 1),
            "remeasure_s": round(float(tm.get("remeasure") or 0.0), 1),
            "cache_hit": cache.get("cache_hit"), "download_s": round(float(cache.get("download_s") or 0.0), 1),
            "stitch_s": round(float(cache.get("stitch_s") or 0.0), 1),
            "n_cadences_raw": d.get("n_cadences_raw"), "n_units": d.get("n_units"),
            "baseline_days": round(float(d.get("baseline_days") or 0.0), 1),
            "n_planets": len(planets),
            "planet_periods": ";".join(f"{p['period_days']:.5f}" for p in planets),
            "planet_snrs": ";".join(f"{p['snr']:.1f}" for p in planets),
            "planet_verdicts": ";".join(str(p.get("verdict")) for p in planets),
            "budget_stop": any("would not fit" in n for n in (res.get("notes") or [])),
            "error": (d.get("error") or "").splitlines()[0] if d.get("error") else "",
        }
        inj = d.get("injection") or {}
        model = d.get("injection_model") or {}
        if inj:
            row.update({"inj_period": inj.get("period"), "inj_rp_rs": inj.get("rp_rs"), "inj_b": inj.get("b"),
                        "inj_t0": model.get("t0"), "inj_depth_ppm": model.get("depth_mean_in_transit_ppm"),
                        "inj_t14_days": model.get("t14_days"),
                        "inj_n_transits_with_data": model.get("n_transits_with_data")})
        rows.append(row)
    path = out_dir / "summary.csv"
    if rows:
        keys = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", default=str(REPO / "data" / "survey" / "targets_v1.csv"))
    ap.add_argument("--sample", default=None, help="CSV with tic_id (+ star columns); overrides --targets")
    ap.add_argument("--injections", default=None, help="injection spec CSV: one job per row")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="survey_v1")
    ap.add_argument("--overrides", default=None, help="JSON dict of SurveyConfig overrides")
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--timeout", type=float, default=900.0, help="per-job hard timeout (s)")
    ap.add_argument("--retries", type=int, default=1, help="extra attempts for error/timeout jobs")
    ap.add_argument("--resume", action="store_true", help="skip jobs with a finished result")
    ap.add_argument("--prefetch", action="store_true", help="build the stitched cache only")
    ap.add_argument("--no-download", action="store_true", help="workers never contact MAST")
    ap.add_argument("--offline", action="store_true",
                    help="rebuild stitched curves from the local FITS cache (no MAST query)")
    ap.add_argument("--refresh", action="store_true", help="ignore existing stitched cache files")
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--tics", default=None, help="comma-separated TIC subset")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--summarize-only", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out)
    for sub in ("jobs", "results", "logs"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    if args.summarize_only:
        print(f"wrote {summarize(out_dir)}")
        return 0

    jobs = build_jobs(args)
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "argv": sys.argv, "config": args.config, "overrides": args.overrides,
        "n_jobs": len(jobs), "concurrency": args.concurrency, "timeout_s": args.timeout,
        "retries": args.retries, "python": PY,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    # Resume: decide per job from the result files (the checkpoint).
    todo: list[tuple[dict, int]] = []
    skipped = 0
    for job in jobs:
        status, attempts = result_status(out_dir / "results" / f"{job['job_id']}.json")
        if args.resume and status in ("ok", "no_data"):
            skipped += 1
            continue
        if args.resume and status in ("error", "timeout", "corrupt") and attempts > args.retries:
            skipped += 1
            continue
        todo.append((job, attempts + 1 if args.resume else 1))
    for job, _att in todo:
        msg = reap_orphan(job["job_id"], out_dir)
        if msg:
            print(f"[run_survey] {job['job_id']}: {msg}", flush=True)
    print(f"[run_survey] {len(jobs)} job(s): {len(todo)} to run, {skipped} skipped "
          f"(resume={args.resume}), concurrency {args.concurrency}, timeout {args.timeout:.0f} s", flush=True)

    extra = []
    if args.cache_dir:
        extra += ["--cache-dir", args.cache_dir]
    if args.no_download:
        extra += ["--no-download"]

    keep_awake = False
    if sys.platform == "win32":
        try:
            import ctypes
            keep_awake = bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001))
        except Exception:
            pass

    t0 = time.perf_counter()
    done = []
    try:
        pending = list(todo)
        while pending:
            batch, pending = pending, []
            with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
                futs = {ex.submit(run_one, j, out_dir, args.timeout, att, extra): (j, att) for j, att in batch}
                for fut in as_completed(futs):
                    r = fut.result()
                    done.append(r)
                    j, att = futs[fut]
                    if r["status"] in ("error", "timeout") and att <= args.retries:
                        pending.append((j, att + 1))
            if pending:
                print(f"[run_survey] retrying {len(pending)} job(s)", flush=True)
    finally:
        if keep_awake:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

    wall = time.perf_counter() - t0
    counts: dict[str, int] = {}
    for r in done:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"[run_survey] finished {len(done)} attempt(s) in {wall:.0f} s: {counts}", flush=True)
    print(f"wrote {summarize(out_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
