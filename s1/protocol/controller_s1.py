"""S1 owning controller: ``k2/protocol/controller_k2.py`` with S1 roots (prompt S1).

S1 differences: owners / STOP files under ``s1/manifests``, controllers, job lists and every worker output under
``D:/tesshunter_s1`` (``s1_common`` sets ``K1_DATA`` = ``K2_DATA`` = the S1 root before ``k2_common`` is imported);
a job script is looked up in ``s1/protocol``, then ``k2/protocol``, then ``k1/protocol``; ``s1_common.py`` is pinned;
the S1 search wrapper ``search_s1.py`` is a search job (Windows-default scheduling, as calibrated).

K2 notes follow.

K2 differences: owners / STOP files under ``k2/manifests``, controllers and job lists under
``D:/tesshunter_k2``; a job script is looked up in ``k2/protocol`` then ``k1/protocol`` and runs from its own
folder; every job gets ``K1_DATA`` = the K2 data root (``k2_common.worker_env``), so K1 workers write their
receipts, runs and caches under ``D:/tesshunter_k2``.

K1 notes follow.

Payloads are top-level subprocesses (TLS uses multiprocessing; never inside a pool worker).  The
controller enforces per-job deadlines, writes one immutable attempt receipt per job, a
``progress.json`` every few seconds, and ``closure.json`` at the end.  The session supervises only
through the registered hourly check-in (``checkin_k1.py``).

Differences from P12 (K1 is a preparation run, not a frozen survey): one owner PER PHASE
(``k1/manifests/owner_<phase>.json``) so a network-bound phase can overlap a CPU phase; every
``k1/protocol/*.py`` and every touched ``src`` module is hashed at launch and re-checked every loop
(a change stops the phase: gotcha 10); storage floors C >= 25 GB and D >= 100 GB stop new launches
(STOP-D); ``k1/manifests/STOP_<phase>`` stops new launches; an existing COMPLETE attempt receipt is
reused on resume (a job is never run twice from the same phase folder), and a retry pass is a new
phase built from the TIMEOUT/OPERATIONAL_UNKNOWN receipts of a closed phase.

CLI: ``controller_k1.py --phase P --jobs k1/manifests/P_jobs.json --workers N --deadline S``
     ``controller_k1.py --phase P_retry --retry-of P --workers N --deadline S``
Job rows: ``{"job_id", "arguments": [script, ...], "result_path", "deadline_s"?, "online"?}``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

from s1_common import REPO, K1, K2, S1 as ROOT, S1_DATA as DATA, PY, CONTROLLERS, JOBS, worker_env, read, write, sha, utc

C_FLOOR = 25_000_000_000
D_FLOOR = 100_000_000_000
SCIENCE_SCRIPTS = ("search_worker_k1.py", "funnel_k1.py", "stage_d_worker_k1.py", "inject_host_k1.py",
                   "funnel_k2.py", "p12_paired_worker_k1.py", "search_s1.py")
#: Search phases keep Windows' default scheduling, the condition the C4 pilot and Part D searches were measured
#: under (hidden background processes are power-throttled onto the 16 E-cores of the i9-13900K; the search's
#: wall-clock budget and rule E1's wall ratio depend on it).  Every other phase opts its worker process trees out
#: of execution-speed throttling (per-process ProcessPowerThrottling, not a system setting), so they may use the
#: P-cores; their results do not depend on wall-clock time (identical single-threaded numerics on both core types).
SEARCH_SCRIPTS = ("search_worker_k1.py", "search_s1.py")
RETRY_TIMEOUT_FACTOR = 4.0


def is_search_job(job) -> bool:
    a = [str(x) for x in job["arguments"]]
    return Path(a[0]).name in SEARCH_SCRIPTS or (Path(a[0]).name == "p12_paired_worker_k1.py" and len(a) > 1 and a[1] == "search")


def unthrottle(pid) -> bool:
    """Opt one process out of Windows execution-speed power throttling (EcoQoS)."""
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    class _PPT(ctypes.Structure):
        _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k32.OpenProcess(0x0200, False, int(pid))          # PROCESS_SET_INFORMATION
    if not h:
        return False
    try:
        st = _PPT(1, 0x1, 0x0)                             # EXECUTION_SPEED controlled, state off
        return bool(k32.SetProcessInformation(h, 4, ctypes.byref(st), ctypes.sizeof(st)))   # ProcessPowerThrottling
    finally:
        k32.CloseHandle(h)


TOUCHED_SRC = ("k1_rules.py", "survey.py", "survey_p8.py", "pipeline.py", "bls_search.py", "audit_rules.py", "event_vet.py",
               "star_vet.py", "secondary.py", "audit_prep.py", "verdict_tiers.py", "stage_c.py", "fpp.py")


def identity(process):
    return dict(pid=process.pid, create_time=process.create_time(), command=process.cmdline())


def identity_alive(row):
    try:
        proc = psutil.Process(row["pid"])
        return abs(proc.create_time() - row["create_time"]) < .01 and proc.cmdline() == row["command"]
    except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
        return False


def terminate_owned(row):
    if not identity_alive(row):
        return
    process = psutil.Process(row["pid"])
    try:
        children = [(child, identity(child)) for child in process.children(recursive=True)]
    except psutil.NoSuchProcess:
        return
    for child, child_id in reversed(children):
        if identity_alive(child_id):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
    if identity_alive(row):
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs([p for p, _ in children] + [process], timeout=5)


def _valid_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError("Invalid phase/job identifier")
    return value


def source_hashes(job_rows=()) -> dict:
    """The pinned sources of a phase: every job script and every file a job row lists under
    ``pins`` (relative to k1/protocol or the repo), k1_common.py, sector_policy_k1.py, the touched
    src modules and the frozen funnel scripts.  Other K1 files may change while a phase runs."""
    names = {"k1_common.py", "sector_policy_k1.py", "k2_common.py", "s1_common.py"}
    for j in job_rows:
        names.add(str(j["arguments"][0]))
        names.update(str(x) for x in j.get("pins", []))
    out = {}
    for n in sorted(names):
        p = script_path(n)
        out[p.relative_to(REPO).as_posix()] = sha(p)
    if not any(str(j["arguments"][0]) in SCIENCE_SCRIPTS for j in job_rows):
        return out        # acquisition / neighbour / injection-prep phases do not import the search or funnel code
    for name in TOUCHED_SRC:
        p = REPO / "src" / "tesshunter" / name
        out[p.relative_to(REPO).as_posix()] = sha(p)
    for name in ("audit_p5.py", "revet_p6.py"):
        p = REPO / "scripts" / name
        out[p.relative_to(REPO).as_posix()] = sha(p)
    p = REPO / "p10" / "protocol" / "p10_funnel_calibration.py"
    out[p.relative_to(REPO).as_posix()] = sha(p)
    return out


def script_path(name) -> Path:
    """A job script or pin: absolute, else s1/protocol, else k2/protocol, else k1/protocol, else repo-relative."""
    n = Path(name)
    if n.is_absolute():
        return n
    for base in (ROOT / "protocol", K2 / "protocol", K1 / "protocol"):
        if (base / n).exists():
            return base / n
    return REPO / n


def build_retry(phase, retry_of):
    folder = CONTROLLERS / retry_of
    closure = read(folder / "closure.json")
    if closure["status"] not in ("CLOSED", "STOPPED", "FAILED") or not closure["all_owned_workers_closed"]:
        raise RuntimeError("Retry requires a closed original phase")
    rows = []
    for job in read(folder / "launch.json")["frozen_jobs"]:
        receipt = folder / "attempts" / (job["job_id"] + ".json")
        prior = read(receipt) if receipt.exists() else {}
        if prior.get("status") == "COMPLETE":
            continue
        row = dict(job, attempt=int(job.get("attempt", 1)) + 1, retry_of=retry_of,
                   original_receipt_sha256=sha(receipt) if receipt.exists() else None)
        if prior.get("status") == "TIMEOUT":
            # a job that hit its deadline gets RETRY_TIMEOUT_FACTOR x that deadline on its one retry
            row["deadline_s"] = float(prior.get("deadline_s") or job.get("deadline_s") or 0) * RETRY_TIMEOUT_FACTOR or None
            row["deadline_scaled_from"] = prior.get("deadline_s")
        rows.append(row)
    out = JOBS / (phase + "_jobs.json")
    write(out, rows)
    return out


def _storage():
    c_free = shutil.disk_usage(REPO).free
    d_free = shutil.disk_usage(str(DATA)).free
    return c_free, d_free, (c_free < C_FLOOR or d_free < D_FLOOR)


def run_phase(phase, jobs_path, workers, deadline, *, retry_of=None):
    _valid_name(phase)
    if not 1 <= workers <= 30 or deadline <= 0:
        raise ValueError("Invalid workers/deadline")
    owner_path = ROOT / "manifests" / f"owner_{phase}.json"
    if owner_path.exists():
        existing = read(owner_path)
        raise RuntimeError("EXCLUSIVE_OWNER" if identity_alive(existing) else "RECYCLED_OR_LOST_OWNER: recover first")
    if retry_of:
        jobs_path = build_retry(phase, retry_of)
    jobs_path = Path(jobs_path)
    jobs_path = jobs_path if jobs_path.is_absolute() else REPO / jobs_path
    job_rows = read(jobs_path)
    if len({j["job_id"] for j in job_rows}) != len(job_rows):
        raise RuntimeError("Duplicated job ids")
    for j in job_rows:
        _valid_name(j["job_id"])
    out = CONTROLLERS / phase
    resume = out.exists()
    if resume and (out / "closure.json").exists():
        # a resumed phase must not expose its previous closure to anything waiting for this run's closure
        (out / "closure.json").rename(out / f"closure_superseded_{int(time.time())}.json")
    sources = source_hashes(job_rows)
    sources[jobs_path.as_posix()] = sha(jobs_path)
    owner = dict(**identity(psutil.Process()), phase=phase, started_utc=utc(), resume=resume)
    write(owner_path, owner)
    out.mkdir(parents=True, exist_ok=True)
    launch_name = "launch.json" if not resume else f"launch_resume_{int(time.time())}.json"
    write(out / launch_name, dict(utc=utc(), owner=owner, jobs=len(job_rows), frozen_jobs=job_rows,
                                  jobs_path=jobs_path.as_posix(), jobs_sha256=sha(jobs_path),
                                  workers=workers, deadline_s=deadline, source_hashes=sources, retry_of=retry_of))
    start = time.monotonic()
    active, completed = {}, []
    pending = []
    for j in job_rows:
        r = out / "attempts" / (j["job_id"] + ".json")
        if r.exists():
            completed.append(read(r))
        else:
            pending.append(j)
    status, error, stop_reason = "RUNNING", None, None

    unthrottled = not any(is_search_job(j) for j in job_rows)

    def sample(row):
        tree = row.setdefault("tree", {})
        done = row.setdefault("unthrottled", set())
        if identity_alive(row):
            try:
                proc = psutil.Process(row["pid"])
                for child in [proc] + proc.children(recursive=True):
                    try:
                        ident = identity(child)
                        key = f"{ident['pid']}:{ident['create_time']}"
                        if unthrottled and key not in done and unthrottle(ident["pid"]):
                            done.add(key)
                        tree[key] = dict(**ident, cpu_seconds=sum(child.cpu_times()[:2]))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except psutil.NoSuchProcess:
                pass
        return sum(p["cpu_seconds"] for p in tree.values())

    def finish(jid, row, outcome, code, reason=None):
        cpu = sample(row)
        terminate_owned(row)
        for child in reversed(list(row.get("tree", {}).values())):
            terminate_owned(child)
        row["handle"].close()
        result = REPO / row["job"]["result_path"] if not Path(row["job"]["result_path"]).is_absolute() else Path(row["job"]["result_path"])
        if outcome == "COMPLETE" and not result.is_file():
            outcome, reason = "OPERATIONAL_UNKNOWN", "Worker exited zero without its result"
        record = dict(job_id=jid, started_utc=row["started_utc"], completed_utc=utc(),
                      wall_seconds=time.monotonic() - row["timer"], cpu_seconds=cpu, pid=row["pid"],
                      create_time=row["create_time"], command=row["command"], exit_code=code, status=outcome,
                      attempt=row["job"].get("attempt", 1), deadline_s=row["deadline"],
                      result_path=row["job"]["result_path"], result_sha256=sha(result) if result.is_file() else None,
                      reason=reason, process_tree=list(row.get("tree", {}).values()))
        write(row["receipt"], record)
        completed.append(record)
        del active[jid]

    def progress():
        c_free, d_free, _ = _storage()
        rows = [dict(job_id=jid, pid=r["pid"], elapsed_seconds=round(time.monotonic() - r["timer"], 1),
                     cpu_seconds=round(sample(r), 1)) for jid, r in active.items()]
        snap = dict(utc=utc(), phase=phase, status=status, stop_reason=stop_reason, owner=owner, total=len(job_rows),
                    completed=len(completed), pending=len(pending), active=len(active),
                    complete=sum(r["status"] == "COMPLETE" for r in completed),
                    unknowns=sum(r["status"] != "COMPLETE" for r in completed), workers=rows,
                    c_free_gb=round(c_free / 1e9, 1), d_free_gb=round(d_free / 1e9, 1),
                    wall_hours=round((time.monotonic() - start) / 3600, 3), error=error,
                    power_throttling="opted_out" if unthrottled else "windows_default")
        write(out / "progress.json", snap, replace=True)

    try:
        while pending or active:
            now = source_hashes(job_rows)
            changed = [k for k, v in now.items() if sources.get(k) != v]
            if sha(jobs_path) != sources[jobs_path.as_posix()]:
                changed.append(jobs_path.name)
            if changed:
                raise RuntimeError("SOURCE_CHANGED: " + ", ".join(changed[:5]))
            _, _, low = _storage()
            if low and stop_reason is None:
                stop_reason = "STOP-D storage floor"
            if (ROOT / "manifests" / f"STOP_{phase}").exists() and stop_reason is None:
                stop_reason = "STOP file"
            while pending and len(active) < workers and stop_reason is None:
                job = pending.pop(0)
                jid = job["job_id"]
                log = out / "logs" / (jid + ".log")
                log.parent.mkdir(parents=True, exist_ok=True)
                handle = log.open("a", encoding="utf-8")
                args = [str(a) for a in job["arguments"]]
                script = script_path(args[0])
                command = [str(PY), str(script), *args[1:]]
                env = worker_env(offline=not job.get("online", False))
                proc = subprocess.Popen(command, cwd=str(script.parent), stdout=handle, stderr=subprocess.STDOUT,
                                        env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                observed = psutil.Process(proc.pid)
                row = dict(**identity(observed), job=job, proc=proc, handle=handle, timer=time.monotonic(),
                           started_utc=utc(), receipt=out / "attempts" / (jid + ".json"),
                           deadline=float(job.get("deadline_s") or deadline))
                active[jid] = row
            for jid, row in list(active.items()):
                sample(row)
                code = row["proc"].poll()
                timed_out = code is None and time.monotonic() - row["timer"] >= row["deadline"]
                if timed_out:
                    terminate_owned(row)
                    try:
                        code = row["proc"].wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        code = None
                if code is not None or timed_out:
                    finish(jid, row, "TIMEOUT" if timed_out else "COMPLETE" if code == 0 else "OPERATIONAL_UNKNOWN", code)
            progress()
            if stop_reason and not active:
                break
            if pending or active:
                time.sleep(3)
        status = "STOPPED" if (stop_reason and pending) else "CLOSED"
    except BaseException as exc:
        status, error = "FAILED", f"{type(exc).__name__}: {exc}"
        for jid, row in list(active.items()):
            finish(jid, row, "INTERRUPTED_UNKNOWN", None, error)
    finally:
        workers_closed = not active and all(not identity_alive(p) for r in completed for p in r.get("process_tree", []))
        closure = dict(utc=utc(), phase=phase, owner=owner, status=status, error=error, stop_reason=stop_reason,
                       wall_hours=(time.monotonic() - start) / 3600, completed=len(completed), pending=len(pending),
                       complete=sum(r["status"] == "COMPLETE" for r in completed),
                       unknowns=sum(r["status"] != "COMPLETE" for r in completed),
                       unknown_fraction=(sum(r["status"] != "COMPLETE" for r in completed) / max(len(completed), 1)),
                       total=len(job_rows), all_owned_workers_closed=workers_closed,
                       job_wall_hours=sum(r["wall_seconds"] for r in completed) / 3600, retry_of=retry_of,
                       power_throttling="opted_out" if unthrottled else "windows_default")
        write(out / "closure.json", closure, replace=True)
        progress()
        if owner_path.exists() and read(owner_path) == owner and workers_closed:
            owner_path.unlink()
    return closure


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True)
    ap.add_argument("--jobs")
    ap.add_argument("--workers", required=True, type=int)
    ap.add_argument("--deadline", required=True, type=float)
    ap.add_argument("--retry-of")
    a = ap.parse_args(argv)
    worker_env()
    result = run_phase(a.phase, a.jobs or JOBS / (a.phase + "_jobs.json"), a.workers, a.deadline,
                       retry_of=a.retry_of)
    print(json.dumps({k: v for k, v in result.items() if k != "owner"}), flush=True)
    return 0 if result["status"] == "CLOSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
