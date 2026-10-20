"""Resume the six interrupted/queued native residual cases, then the cadence census.

Uses the inherited scientific instrument unchanged, one eight-worker TLS job at a
time. Successful records are skipped; ERROR/incomplete output stops the sequence.
The incomplete first workspace was preserved before the failed queue was stopped.
"""
from pathlib import Path
import os
import subprocess
import sys
import time
import psutil
import resume_cadence as Q


def run_checked(command, log, state, receipt):
    with log.open("a", encoding="utf-8") as fh:
        fh.write("\n=== " + Q.utc() + " " + " ".join(command) + "\n")
        fh.flush()
        child = subprocess.Popen(command, cwd=Q.REPO, stdout=fh, stderr=subprocess.STDOUT)
        state.update(child_pid=child.pid, command=command, log=str(log.relative_to(Q.REPO)))
        Q.write(receipt, state)
        while child.poll() is None:
            time.sleep(20)
        return child.returncode


def main():
    os.chdir(Q.REPO)
    os.environ.update(LIGHTKURVE_CACHE=str(Q.REPO/"data/cache/lightkurve"), PYTHONIOENCODING="utf-8",
                      TESSHUNTER_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1",
                      OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    receipt = Q.RECEIPTS/"residual_resume.json"
    lock = Q.RECEIPTS/"residual_resume.lock"
    state = {"utc":Q.utc(), "pid":os.getpid(), "status":"starting", "threads":8,
             "keys":[key for _,key in Q.ORIGINAL_KEYS], "completed":[]}
    with lock.open("x") as fh:
        fh.write(Q.json.dumps({"pid":os.getpid(), "created":psutil.Process().create_time()}))
    try:
        Q.assert_source()
        if Q.tls_owners() or (Q.RECEIPTS/"cadence_queue.lock").exists():
            raise RuntimeError("Existing TLS/cadence owner; refusing duplicate launch")
        for set_name,key in Q.ORIGINAL_KEYS:
            if Q.complete(set_name, "p10c_native", key):
                print(Q.utc(), "reuse", key, flush=True)
                state["completed"].append(key)
                continue
            Q.assert_source()
            if Q.tls_owners():
                raise RuntimeError("Unexpected live TLS owner")
            state.update(utc=Q.utc(), status="running", active=key)
            command = [str(Q.PY), "scripts/p10_stage_c.py", "run", "--set", set_name,
                       "--keys", key, "--rules", "p10c", "--cadence", "native", "--threads", "8"]
            print(Q.utc(), "start", key, flush=True)
            code = run_checked(command, Q.REPO/"p10/logs"/("residual_native_"+key+".log"), state, receipt)
            if code or Q.tls_owners() or not Q.complete(set_name,"p10c_native",key):
                raise RuntimeError("Residual execution incomplete: "+key)
            state["completed"].append(key)
            print(Q.utc(), "complete", key, flush=True)
        state.update(utc=Q.utc(), status="residual_measurements_complete_starting_cadence", active=None)
        Q.write(receipt,state)
        command = [str(Q.PY), "-B", "p10/protocol/resume_cadence.py"]
        code = run_checked(command, Q.REPO/"p10/logs/takeover_20260908_cadence_queue2.log", state, receipt)
        if code:
            raise RuntimeError("Cadence queue requires review; see its receipt")
        state.update(utc=Q.utc(), status="measurements_complete_review_required", active=None)
        Q.write(receipt,state)
    except BaseException as exc:
        state.update(utc=Q.utc(), status="needs_review", error=str(exc))
        Q.write(receipt,state)
        raise
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
