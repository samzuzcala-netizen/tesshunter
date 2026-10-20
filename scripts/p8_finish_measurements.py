"""Resume P8's measurement sequence; never start the full-population search or choose rules in code.

When attaching to existing Windows launcher processes, pass --inj-pid and --fa-pid.
Otherwise starts the checkpointed funnels. All logs and the ready marker live under p8/.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
P8 = REPO / "data" / "survey" / "p8"
LOGS = P8 / "logs"
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("LIGHTKURVE_CACHE", str(REPO / "data" / "cache" / "lightkurve"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(variable, "1")


class ExistingProcess:
    """Keep an OS handle to this particular process, so PID reuse cannot confuse a wait."""
    def __init__(self, pid: int):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.OpenProcess(0x00100000, False, pid)
        if not self.handle:
            raise RuntimeError(f"cannot attach to process {pid}; inspect the existing workers before resuming")

    def poll(self):
        if not self.handle:
            return 0
        status = self.api.WaitForSingleObject(self.handle, 0)
        if status == 258:
            return None
        if status != 0:
            raise RuntimeError(f"process wait failed: {status}")
        self.api.CloseHandle(self.handle)
        self.handle = None
        return 0  # correctness is checked from the full set of output records, not this code


def start(name: str, arguments: list[str]):
    print(f"START {name}: {' '.join(arguments)}", flush=True)
    log = open(LOGS / f"finish_{name}.log", "w", encoding="utf-8")
    process = subprocess.Popen([sys.executable, "-u", *arguments], cwd=REPO, stdout=log,
                               stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    log.close()
    return process


def finish(name, process):
    while process.poll() is None:
        time.sleep(20)
    if process.returncode:
        raise RuntimeError(f"{name} exited {process.returncode}; see finish_{name}.log")
    print(f"DONE {name}", flush=True)


def run(name, arguments):
    finish(name, start(name, arguments))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inj-pid", type=int)
    parser.add_argument("--fa-pid", type=int)
    parser.add_argument("--inj-slices", type=int, default=16)
    parser.add_argument("--fa-slices", type=int, default=8)
    parser.add_argument("--decision-slices", type=int, default=16)
    parser.add_argument("--shared-queues", action="store_true", help="distribute unfinished cases across available top-level workers")
    args = parser.parse_args()
    if min(args.inj_slices, args.fa_slices, args.decision_slices) < 1:
        parser.error("slice counts must be positive")
    LOGS.mkdir(parents=True, exist_ok=True)
    import p8_completeness as C
    import p8_funnel as F
    jobs = C.recovered_jobs(C._load_results(C.INJ_RUN))
    F.set_root(C.FA_ROOT)
    F.set_rules("p7.0")
    fa_jobs = F.V.jobs()
    inj_command = ["scripts/p8_completeness.py", "funnel", "--slices", str(args.inj_slices), "--rules", "p7.0"]
    fa_command = ["scripts/p8_funnel.py", "--root", "data/survey/p8/fa_funnel", "--rules", "p7.0", "stageA", "--slices", str(args.fa_slices)]
    if args.shared_queues:
        inj_command.append("--shared-queue")
        fa_command.append("--shared-queue")
    inj = ExistingProcess(args.inj_pid) if args.inj_pid else start("injection_funnel", inj_command)
    fa = ExistingProcess(args.fa_pid) if args.fa_pid else start("fa_stageA", fa_command)
    ready = {"inj": False, "fa": False}
    retries = {"inj": 0, "fa": 0}
    dec_process = sec_process = None
    while not all(ready.values()):
        for name, process in (("inj", inj), ("fa", fa)):
            if ready[name] or process.poll() is None:
                continue
            try:
                if name == "inj":
                    C.load_funnel_outcomes(jobs, rules="p7.0")
                else:
                    for job in fa_jobs:
                        key = F.V.kkey(job["tic_id"], job["period"])
                        C.require_settled_record(C.FA_ROOT / "stageA" / f"{key}.json", "p7.0", "decision", ("PASS", "FAIL"))
            except (ValueError, OSError) as exc:
                if retries[name] >= 1:
                    raise RuntimeError(f"{name} remains incomplete after retry: {exc}") from exc
                retries[name] += 1
                print(f"RETRY {name}: {exc}", flush=True)
                if name == "inj":
                    inj = start("injection_funnel_retry", inj_command)
                else:
                    fa = start("fa_stageA_retry", fa_command)
                continue
            ready[name] = True
            if name == "inj":
                dec_process = start("decisions_inj", ["scripts/p8_decisions.py", "run", "--sets", "inj", "--slices", str(args.decision_slices)])
            else:
                sec_process = start("fa_secondary", ["scripts/p8_funnel.py", "--root", "data/survey/p8/fa_funnel", "--rules", "p7.0", "secondary", "--slices", str(args.fa_slices)])
        print(f"CHECKPOINT injection Stage A files {len(list(C.INJ_ROOT.glob('*/stageA/*.json')))}/{len(jobs)}, "
              f"false-alarm Stage A files {len(list((C.FA_ROOT / 'stageA').glob('*.json')))}/{len(fa_jobs)}; "
              f"completed producers {ready}", flush=True)
        if not all(ready.values()):
            time.sleep(30)
    finish("fa_secondary", sec_process)
    run("completeness", ["scripts/p8_completeness.py", "analyze", "--rules", "p7.0"])
    run("expected_yield", ["scripts/p8_expected_yield.py", "--workers", "4"])
    run("population_memo", ["scripts/write_population_p8_memo.py"])
    finish("decisions_inj", dec_process)
    run("decisions_tables", ["scripts/p8_decisions.py", "tables"])
    result = {"generated_utc": C.utc(), "status": "measurement tables ready for review",
              "retries": retries, "real_search_started": False, "p8_rules_committed": False}
    (P8 / "measurements_ready_p8.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
