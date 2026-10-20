"""K1 hourly check-in (section 3): bounded and read-only, recomputes nothing.

Reads ``progress.json``, the owner identity, the last 50 lines of the controller log and of the
newest job log, free disk, and worker CPU growth since the previous check; appends one dated line to
``k1/RESUME_K1.md`` and one row to ``k1/logs/checkins.jsonl``.  Prints the act-early flags.
CLI: ``checkin_k1.py <phase> [<phase> ...]``.
"""
import json
import shutil
import sys
from pathlib import Path

from k1_common import REPO, ROOT, DATA, CONTROLLERS, read, utc, append_jsonl

try:
    import psutil
except ImportError:                                   # pragma: no cover
    psutil = None


def _tail(path, n=50):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


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
    state_path = REPO / "k1" / "logs" / f"checkin_state_{phase}.json"
    prev = read(state_path) if state_path.exists() else {}
    cpu_now = {w["job_id"]: w["cpu_seconds"] for w in prog.get("workers", [])}
    stalled = [j for j, c in cpu_now.items() if j in prev.get("cpu", {}) and c <= prev["cpu"][j] + 1.0]
    c_free = shutil.disk_usage(REPO).free / 1e9
    d_free = shutil.disk_usage(str(DATA)).free / 1e9
    flags = []
    if not alive and closure is None and prog:
        flags.append("OWNER_GONE_WITHOUT_CLOSURE")
    if stalled:
        flags.append("STALLED_WORKERS:" + ",".join(stalled))
    if c_free < 28 or d_free < 103:
        flags.append("DISK_WITHIN_3GB_OF_FLOOR")
    if prog.get("unknowns", 0) > prev.get("unknowns", 0):
        flags.append(f"UNKNOWNS_ROSE:{prev.get('unknowns', 0)}->{prog.get('unknowns')}")
    if prog.get("stop_reason"):
        flags.append("STOP:" + str(prog.get("stop_reason")))
    jobs = sorted((out / "logs").glob("*.log"), key=lambda p: p.stat().st_mtime) if (out / "logs").exists() else []
    row = {"utc": utc(), "phase": phase, "status": (closure or prog).get("status"), "complete": prog.get("complete"),
           "unknowns": prog.get("unknowns"), "pending": prog.get("pending"), "active": prog.get("active"),
           "total": prog.get("total"), "wall_hours": prog.get("wall_hours"), "owner_alive": alive,
           "closed": closure is not None, "c_free_gb": round(c_free, 1), "d_free_gb": round(d_free, 1), "flags": flags,
           "controller_log_tail": _tail(REPO / "k1" / "logs" / f"controller_{phase}.log")[-5:],
           "newest_job_log_tail": _tail(jobs[-1])[-5:] if jobs else []}
    state_path.write_text(json.dumps({"cpu": cpu_now, "unknowns": prog.get("unknowns", 0), "utc": row["utc"]}))
    append_jsonl(REPO / "k1" / "logs" / "checkins.jsonl", row)
    line = (f"- {row['utc'][:16]}Z check-in {phase}: {row['status']} complete {row['complete']}/{row['total']}, "
            f"unknowns {row['unknowns']}, active {row['active']}, pending {row['pending']}, owner alive {alive}, "
            f"C {row['c_free_gb']} GB / D {row['d_free_gb']} GB, flags {flags or 'none'}\n")
    with (REPO / "k1" / "RESUME_K1.md").open("a", encoding="utf-8") as fh:
        fh.write(line)
    return row


if __name__ == "__main__":
    for ph in sys.argv[1:]:
        r = check(ph)
        print(json.dumps({k: v for k, v in r.items() if not k.endswith("tail")}))
