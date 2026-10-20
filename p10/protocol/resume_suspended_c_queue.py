"""Inspect or resume the user-paused C queue without starting another job.

Only an explicit `resume` command mutates process state. All identities, the
Windows boot, frozen scientific inputs and paused files must still match.
An interrupted resume journal requires manual review; never blindly retry it.
"""
from pathlib import Path
import argparse
import json
import os
import time

import psutil
import run_corrected_c_controls as Q


def check_identity(process, saved):
    Q.require(process.pid == saved["pid"]
              and process.create_time() == saved["created_epoch"]
              and process.ppid() == saved["ppid"]
              and process.cmdline() == saved["command"],
              "Process identity changed; do not resume PID " + str(saved["pid"]))
    Q.require(process.status() == psutil.STATUS_STOPPED,
              "Process is not suspended; do not resume PID " + str(saved["pid"]))


def inspect_pause(receipt_path):
    Q.load_manifest()
    saved = Q.read(receipt_path)
    Q.require(saved["status"] == "suspended_in_memory", "Not a verified pause receipt")
    Q.require(abs(psutil.boot_time() - saved["boot_time_epoch"]) < 2,
              "Windows restarted. In-memory progress is unavailable; review ownership and partial files.")
    Q.require(Q.sha(Q.MANIFEST) == saved["manifest_sha256"], "Manifest changed")
    Q.require(Q.sha(Q.STATE) == saved["queue_state_sha256"]
              and Q.sha(Q.LOCK) == saved["queue_lock_sha256"], "Queue state/lock changed")
    Q.verify_hashes(saved["active_artifact_sha256"])
    Q.verify_hashes(saved["paused_log_sha256"])
    Q.require(len(list(Q.RECEIPTS.glob("*.json"))) == saved["completed_receipt_count"],
              "Completed receipt census changed")
    rows = {row["pid"]: row for row in saved["processes"]}
    Q.require(len(rows) == len(saved["processes"])
              and set(saved["suspend_order"]) == set(rows)
              and saved["resume_order"] == list(reversed(saved["suspend_order"])),
              "Pause process census/order is inconsistent")
    processes = {}
    for pid, row in rows.items():
        process = psutil.Process(pid)
        check_identity(process, row)
        processes[pid] = process
    owner_pid = saved["queue_lock"]["pid"]
    root_pid = rows[owner_pid]["ppid"]
    descendants = {p.pid for p in processes[root_pid].children(recursive=True)} | {root_pid}
    Q.require(descendants == set(rows), "Live descendant tree changed")
    expected_owners = {pid for pid, row in rows.items()
                       if any(Path(arg).name == Path(Q.__file__).name for arg in row["command"])}
    Q.require({row["pid"] for row in Q.owners()} == expected_owners,
              "Unexpected scientific owner or incomplete visibility")
    return saved, rows, processes


def resume(receipt_path):
    journal = receipt_path.with_name(receipt_path.stem + ".resume.events.jsonl")
    output = receipt_path.with_name(receipt_path.stem + ".resume.json")
    Q.require(not journal.exists() and not output.exists(),
              "A resume was already attempted. Inspect its journal and live ownership; never retry blindly.")
    saved, rows, processes = inspect_pause(receipt_path)
    pause_events = [json.loads(line) for line in (Q.ROOT / saved["events_path"]).read_text().splitlines()]
    paused_at = {event["pid"]: event["epoch"] for event in pause_events
                 if event["event"] == "suspend_returned"}
    Q.require(set(paused_at) == set(rows), "Missing original suspension timestamps")
    intervals = []
    with journal.open("x", encoding="utf-8") as stream:
        def record(event):
            stream.write(json.dumps(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

        record({"event": "resume_started", "utc": Q.utc(), "pause_receipt_sha256": Q.sha(receipt_path)})
        # Console host and workers first, queue controller last. No new process
        # is launched here, and each process is resumed exactly once.
        for pid in saved["resume_order"]:
            process = processes[pid]
            check_identity(process, rows[pid])
            epoch = time.time()
            record({"event": "resume_requested", "pid": pid, "utc": Q.utc(), "epoch": epoch})
            process.resume()
            record({"event": "resume_returned", "pid": pid, "utc": Q.utc(), "epoch": time.time()})
            intervals.append({"pid": pid, "paused_at_epoch": paused_at[pid],
                              "resume_requested_epoch": epoch, "pause_seconds": epoch - paused_at[pid]})
    result = {"utc": Q.utc(), "status": "resume_calls_completed", "pause_receipt": str(receipt_path.relative_to(Q.ROOT)),
              "pause_receipt_sha256": Q.sha(receipt_path), "events_path": str(journal.relative_to(Q.ROOT)),
              "per_process_pause_intervals": intervals, "active_id": saved["queue_state"]["active_id"],
              "timing_caveat": saved["timing_caveat"],
              "next": "Take a fresh process snapshot and verify CPU progress and ownership. Preserve raw wall fields and this pause interval. The Codex automation remains paused."}
    Q.write_new(output, result)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "resume"))
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    os.chdir(Q.ROOT)
    path = Path(args.receipt).resolve()
    Q.require(path.parent == Q.STATE.parent and path.name.startswith("suspended_c_queue_"),
              "Use the saved P10 pause receipt under takeover_20260908")
    if args.command == "resume":
        resume(path)
    else:
        saved, _, processes = inspect_pause(path)
        print(json.dumps({"utc": Q.utc(), "status": "verified_suspended_in_memory", "n_suspended": len(processes),
                          "active_id": saved["queue_state"]["active_id"],
                          "n_complete": saved["completed_receipt_count"],
                          "pause_started_utc": saved["pause_started_utc"],
                          "timing_caveat": saved["timing_caveat"]}, indent=2))


if __name__ == "__main__":
    main()
