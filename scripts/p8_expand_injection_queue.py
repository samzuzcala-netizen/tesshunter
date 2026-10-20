"""Add top-level workers to a live P8 injection queue and wait for the entire producer group.

Use only after verifying the original dispatcher's PID and retiring its old continuation
driver (leave the dispatcher and its workers running). Attach a new continuation driver
to this process with --inj-pid. It must wait for both the original dispatcher and these
helpers before validating the complete set, so no retry can race the added workers.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

from p8_finish_measurements import ExistingProcess, LOGS, REPO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--first-index", type=int, default=24)
    parser.add_argument("--wait-pid", type=int, help="wait for this verified process to release capacity before adding workers")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("this attachment helper uses Windows process handles")
    if args.workers < 1 or args.first_index < 0:
        parser.error("workers must be positive and first-index nonnegative")
    queue = args.queue.resolve(strict=True)
    queue.relative_to(LOGS.resolve())
    original = ExistingProcess(args.parent_pid)
    if original.poll() is not None:
        raise RuntimeError("original dispatcher already finished; resume normally instead")
    started = time.perf_counter()
    group = []
    run_token = f"{os.getpid()}_{time.time_ns()}"
    startup_error = None
    try:
        if args.wait_pid is not None:
            capacity = ExistingProcess(args.wait_pid)
            print(f"WAIT for capacity from PID {args.wait_pid}; original injection dispatcher remains attached", flush=True)
            while capacity.poll() is None:
                time.sleep(15)
            print("Capacity available; starting extra injection workers", flush=True)
        for index in range(args.first_index, args.first_index + args.workers):
            path = LOGS / f"inj_extra_{run_token}_{index}.log"
            with path.open("x", encoding="utf-8") as stream:
                process = subprocess.Popen([
                    sys.executable, "-u", str(REPO / "scripts/p8_completeness.py"), "slice",
                    "--index", str(index), "--nslices", str(args.first_index + args.workers),
                    "--rules", "p7.0", "--queue", str(queue),
                ], cwd=REPO, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            group.append((index, process))
            print(f"START extra injection worker {index}, PID {process.pid}, log {path.name}", flush=True)
    except Exception as exc:
        startup_error = exc
        print(f"Worker startup failed: {exc}; waiting for every live producer before returning", flush=True)
    while original.poll() is None or any(process.poll() is None for _, process in group):
        time.sleep(15)
    codes = [(index, process.wait()) for index, process in group]
    print(f"Original dispatcher and extra workers finished; exit codes {codes}; "
          f"elapsed {(time.perf_counter() - started) / 60:.1f} min", flush=True)
    if startup_error is not None:
        raise startup_error
    if any(code != 0 for _, code in codes):
        raise SystemExit("extra injection workers failed; the continuation driver's full-set check must retry")


if __name__ == "__main__":
    main()
