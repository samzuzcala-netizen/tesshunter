"""Let existing Windows P8 slices settle before constructing a new stage queue.

The main driver cannot own helpers launched after it started. Identify those
processes by their explicit output root, or by a registered launcher and queue
for older relative command lines. This only waits; it never changes measurements
or terminates a worker. Simultaneous new stage coordinators are not supported.
"""
from __future__ import annotations

import json
import ntpath
import os
from pathlib import Path
import shlex
import subprocess
import time


def _path(value: str, repo: Path) -> str:
    return ntpath.normcase(ntpath.normpath(ntpath.join(str(repo), value)))


def registrations(root: Path) -> dict[int, str]:
    """Recorded launcher PIDs and their queues, including completed launchers.

    A reused PID alone cannot match: the script, stage and queue must also agree.
    """
    registered = {}
    for pattern in ("bounded_workers_batch*.json", "C_ready_batch*.json"):
        for path in root.glob(pattern):
            record = json.loads(path.read_text(encoding="utf-8-sig"))
            queue = record.get("queue")
            if queue:
                for worker in record.get("workers", [record]):
                    if worker.get("launcher_pid"):
                        registered[int(worker["launcher_pid"])] = queue
    return registered


def matching_workers(processes, stage: str, repo: Path, root: Path, registered):
    matches = []
    script = _path("scripts/p8_funnel.py", repo)
    for process in processes:
        try:
            args = [s.strip('"') for s in shlex.split(process.get("CommandLine") or "", posix=False)]
        except ValueError:
            continue
        script_positions = [i for i, a in enumerate(args) if ntpath.basename(a) == "p8_funnel.py"]
        if len(script_positions) != 1:
            continue
        index = script_positions[0]
        if _path(args[index], repo) != script:
            continue
        args = args[index + 1:]
        if "slice" not in args:
            continue

        def option(name):
            try:
                return args[args.index(name) + 1]
            except (ValueError, IndexError):
                return None

        if option("--stage") != stage:
            continue
        output = option("--root")
        if output is not None:
            # Relative roots alone do not identify the other process's cwd.
            if not ntpath.isabs(output) or _path(output, repo) != _path(str(root), repo):
                continue
        if output is None:
            queue = option("--queue")
            identities = (process["ProcessId"], process.get("ParentProcessId"))
            if not queue or not any(
                pid in registered and _path(registered[pid], repo) == _path(queue, repo)
                for pid in identities
            ):
                continue
        matches.append(process)
    return matches


def windows_processes():
    script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
        "$p=@(Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -match '^python' -and $_.CommandLine -like '*p8_funnel.py*' "
        "} | Select-Object ProcessId,ParentProcessId,CommandLine); "
        "ConvertTo-Json -InputObject $p -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True, capture_output=True, text=True, encoding="utf-8", timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    records = json.loads(result.stdout.lstrip("\ufeff"))
    if not isinstance(records, list):
        raise ValueError("P8 worker enumeration did not return a process list")
    return records


def wait_for_existing_workers(stage: str, repo: Path, root: Path, *,
                              process_source=None, sleep=time.sleep, poll_seconds=15):
    """Wait before reading eligibility or creating a fresh shared queue.

    Enumeration errors propagate so the caller cannot silently duplicate work.
    The live P8 helper launches covered here are Windows-only.
    """
    if stage not in ("A", "C") or root.resolve() != (repo / "data/survey/p8").resolve():
        return
    if process_source is None:
        if os.name != "nt":
            return
        process_source = windows_processes
    previous = None
    while True:
        workers = matching_workers(process_source(), stage, repo, root, registrations(root))
        pids = sorted(p["ProcessId"] for p in workers)
        if not pids:
            if previous:
                print(f"stage {stage}: earlier workers have finished", flush=True)
            return
        if pids != previous:
            print(f"stage {stage}: waiting for earlier Python processes {pids}", flush=True)
            previous = pids
        sleep(poll_seconds)
