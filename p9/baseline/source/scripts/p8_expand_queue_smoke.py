"""Check added queue workers on five settled injections and an independently held dispatcher."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "scripts")]
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data/cache/lightkurve"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def main():
    import audit_p5 as A
    import p8_completeness as C
    from p8_queue_smoke import hashes
    from p8_work_queue import create_queue

    selected = C.recovered_jobs(C._load_results(C.INJ_RUN))[:5]
    C.load_funnel_outcomes(selected, rules="p7.0")
    roots = [(C.INJ_ROOT / j["job_id"], C.kkey(j["tic_id"], j["period_days"])) for j in selected]
    before = hashes(roots)
    token = time.time_ns()
    logs = C.P8 / "logs"
    queue = logs / f"expansion_smoke_{token}.sqlite"
    release = logs / f"expansion_release_{token}"
    output = logs / f"expansion_smoke_{token}.log"
    create_queue(queue, [j["job_id"] for j in selected])
    # This owned fixture waits for release, independently of the added workers.
    parent_code = ("import sys,time; from pathlib import Path\n"
                   "deadline=time.monotonic()+180\n"
                   "while not Path(sys.argv[1]).exists() and time.monotonic()<deadline: time.sleep(0.1)\n")
    parent = subprocess.Popen([sys.executable, "-c", parent_code, str(release)],
                              creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        with output.open("x", encoding="utf-8") as stream:
            coordinator = subprocess.Popen([
                sys.executable, "-u", str(REPO / "scripts/p8_expand_injection_queue.py"),
                "--parent-pid", str(parent.pid), "--queue", str(queue), "--workers", "2",
            ], cwd=REPO, stdout=stream, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            if coordinator.poll() is not None:
                raise RuntimeError(f"coordinator exited before releasing the dispatcher: {output.read_text()}")
            worker_logs = re.findall(r"log (\S+\.log)", output.read_text(encoding="utf-8"))
            if len(worker_logs) == 2 and all(" DONE in " in (logs / name).read_text(encoding="utf-8") for name in worker_logs):
                break
            time.sleep(1)
        else:
            raise TimeoutError(f"cached expansion smoke did not finish; inspect {output}")
        assert parent.poll() is None and coordinator.poll() is None
        release.write_text("released", encoding="utf-8")
        code = coordinator.wait(timeout=45)
        if code:
            raise RuntimeError(f"coordinator failed {code}: {output.read_text()}")
        after = hashes(roots)
        changed = [path for path in before if before[path] != after.get(path)]
        result = {"generated_utc": C.utc(), "n_injections": len(selected), "n_extra_workers": 2,
                  "waited_for_original_after_helpers_finished": True, "exit_code": code,
                  "n_files_hashed": len(before), "changed": changed, "hashes": before}
        A.jdump(C.P8 / "queue_expansion_smoke_p8.json", result)
        print(json.dumps({k: v for k, v in result.items() if k != "hashes"}), flush=True)
        if changed:
            raise SystemExit("added queue workers changed scientific checkpoints")
    finally:
        release.write_text("released", encoding="utf-8")
        parent.wait(timeout=15)


if __name__ == "__main__":
    main()
