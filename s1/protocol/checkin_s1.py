"""S1 check-in (``k2/protocol/checkin_k2.py`` with S1 roots and the prompt-S1 health line): bounded and read-only,
recomputes nothing.

Reads ``progress.json`` / ``closure.json``, the owner identity, the controller log tail and the newest job log tail,
free disk, and the worker CPU of the active jobs; compares with the previous check-in of the same phase (complete,
unknowns, summed worker CPU, C: free) and appends one dated line to ``s1/RESUME_S1.md`` and one row to
``s1/logs/checkins.jsonl``.  Prints the act-on flags of prompt S1 section 4.2.
CLI: ``checkin_s1.py <phase> [<phase> ...]``.
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from s1_common import REPO, S1 as ROOT, S1_DATA as DATA, CONTROLLERS, read, utc, append_jsonl

try:
    import psutil
except ImportError:                                   # pragma: no cover
    psutil = None


def _tail(path, n=50):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def _hours(a, b):
    try:
        return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def check(phase):
    out = CONTROLLERS / phase
    prog = read(out / "progress.json") if (out / "progress.json").exists() else {}
    closure = read(out / "closure.json") if (out / "closure.json").exists() else None
    owner_path = ROOT / "manifests" / f"owner_{phase}.json"
    owner = read(owner_path) if owner_path.exists() else None
    alive = False
    if owner and psutil:
        try:
            pr = psutil.Process(owner["pid"])
            alive = abs(pr.create_time() - owner["create_time"]) < .01
        except Exception:
            alive = False
    state_path = ROOT / "logs" / f"checkin_state_{phase}.json"
    prev = read(state_path) if state_path.exists() else {}
    cpu_now = {w["job_id"]: w["cpu_seconds"] for w in prog.get("workers", [])}
    stalled = [j for j, c in cpu_now.items() if j in prev.get("cpu", {}) and c <= prev["cpu"][j] + 1.0]
    cpu_gain = sum(c - prev.get("cpu", {}).get(j, 0.0) for j, c in cpu_now.items())
    c_free = shutil.disk_usage(REPO).free / 1e9
    d_free = shutil.disk_usage(str(DATA)).free / 1e9
    now = utc()
    dt = _hours(prev.get("utc"), now)
    d_complete = (prog.get("complete") or 0) - prev.get("complete", 0) if prev else None
    d_unknowns = (prog.get("unknowns") or 0) - prev.get("unknowns", 0) if prev else None
    c_trend = ((c_free - prev["c_free_gb"]) / dt) if (prev.get("c_free_gb") is not None and dt and dt > 0.05) else None
    flags = []
    if not alive and closure is None and prog:
        flags.append("OWNER_GONE_WITHOUT_CLOSURE")
    if stalled:
        flags.append("STALLED_WORKERS:" + ",".join(stalled))
    if prev and closure is None and d_complete == 0 and cpu_gain < 1.0:
        flags.append("NO_PROGRESS_SINCE_LAST_WAKE")
    if c_free < 27 or (c_trend is not None and c_trend < -1.0):
        flags.append("C_LOW_OR_FALLING")
    if c_free < 28 or d_free < 103:
        flags.append("DISK_WITHIN_3GB_OF_FLOOR")
    if (prog.get("unknowns") or 0) > prev.get("unknowns", 0):
        flags.append(f"UNKNOWNS_ROSE:{prev.get('unknowns', 0)}->{prog.get('unknowns')}")
    if prog.get("stop_reason"):
        flags.append("STOP:" + str(prog.get("stop_reason")))
    jobs = sorted((out / "logs").glob("*.log"), key=lambda p: p.stat().st_mtime) if (out / "logs").exists() else []
    row = {"utc": now, "phase": phase, "status": (closure or prog).get("status"), "complete": prog.get("complete"),
           "unknowns": prog.get("unknowns"), "pending": prog.get("pending"), "active": prog.get("active"),
           "total": prog.get("total"), "wall_hours": prog.get("wall_hours"), "owner_alive": alive,
           "closed": closure is not None, "d_complete": d_complete, "d_unknowns": d_unknowns,
           "worker_cpu_gain_s": round(cpu_gain, 1), "hours_since_last": round(dt, 3) if dt else None,
           "c_free_gb": round(c_free, 1), "d_free_gb": round(d_free, 1),
           "c_trend_gb_per_h": round(c_trend, 2) if c_trend is not None else None, "flags": flags,
           "controller_log_tail": _tail(ROOT / "logs" / f"controller_{phase}.log")[-5:],
           "newest_job_log_tail": _tail(jobs[-1])[-5:] if jobs else []}
    state_path.write_text(json.dumps({"cpu": cpu_now, "unknowns": prog.get("unknowns", 0), "complete": prog.get("complete", 0),
                                      "c_free_gb": round(c_free, 2), "utc": now}))
    append_jsonl(ROOT / "logs" / "checkins.jsonl", row)
    trend = f"{row['c_trend_gb_per_h']:+.2f} GB/h" if row["c_trend_gb_per_h"] is not None else "n/a"
    line = (f"- {now[:16]}Z check-in {phase}: {row['status']} complete {row['complete']}/{row['total']} "
            f"(+{d_complete if d_complete is not None else 'n/a'}), unknowns {row['unknowns']} "
            f"({'+' if (d_unknowns or 0) >= 0 else ''}{d_unknowns if d_unknowns is not None else 'n/a'}), "
            f"active {row['active']}, owner alive {alive}, worker CPU +{row['worker_cpu_gain_s']:.0f} s, "
            f"C {row['c_free_gb']} GB ({trend}) / D {row['d_free_gb']} GB, flags {flags or 'none'}\n")
    with (ROOT / "RESUME_S1.md").open("a", encoding="utf-8") as fh:
        fh.write(line)
    return row


if __name__ == "__main__":
    for ph in sys.argv[1:]:
        r = check(ph)
        print(json.dumps({k: v for k, v in r.items() if not k.endswith("tail")}))
