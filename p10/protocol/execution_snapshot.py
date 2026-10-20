"""Read-only P10 job inventory, with a timestamped receipt under p10/results.

Does not launch, stop, retry, or change any job or scientific output. Python
launcher/interpreter pairs are recorded separately with their parent relationships.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv
import json
import psutil

ROOT = Path(__file__).resolve().parents[2]
MARKERS = ("p10_stage_c.py", "stage_c_queue1.sh", "resume_residuals.py", "resume_cadence.py",
           "resume_search_abc.ps1", "p10_search_capacity.py", "run_survey.py", "survey_worker.py", "queue_fourth_variant.py",
           "native_raw_spectra.py", "run_false_alarm_funnels.py", "p8_funnel.py", "run_corrected_c_controls.py")


def main():
    all_processes, inaccessible = {}, []
    for process in psutil.process_iter():
        try:
            name = process.name().lower()
            if not name.startswith(("python", "bash", "pwsh", "powershell")):
                continue
            command = process.cmdline()
            if not command:
                inaccessible.append(process.pid)
                continue
            cpu = process.cpu_times()
            all_processes[process.pid] = {"pid":process.pid,"ppid":process.ppid(),"name":name,
                                         "created_epoch":process.create_time(),"command":command,
                                         "cpu_user_s":cpu.user,"cpu_kernel_s":cpu.system,
                                         "rss_bytes":process.memory_info().rss}
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            inaccessible.append(process.pid)
    owners = {pid for pid,p in all_processes.items() if any(marker in " ".join(p["command"]) for marker in MARKERS)
              and not any(arg in ("-Command", "-command", "-c") for arg in p["command"])}
    while True:
        children = {pid for pid,p in all_processes.items() if p["ppid"] in owners}
        if children <= owners:
            break
        owners |= children
    searches = []
    for directory in sorted((ROOT/"data/survey/runs/p10_2b").glob("*")):
        if not directory.is_dir():
            continue
        files = list((directory/"results").glob("*.json"))
        counts, malformed = Counter(), []
        for path in files:
            try:
                r = json.loads(path.read_bytes())
                counts[r.get("status","missing_status")] += 1
            except (OSError,ValueError) as exc:
                malformed.append({"path":str(path.relative_to(ROOT)),"error":str(exc)})
        expected = 600 if directory.name.endswith("_inj") else 300
        searches.append({"run":directory.name,"expected":expected,"result_files":len(files),
                         "status_counts":dict(counts),"malformed":malformed,
                         "all_successful":counts.get("ok",0)==expected and len(files)==expected and not malformed})
    logs = []
    for pattern in ("takeover_20260908_*resume*.log", "residual_native_*.log", "cadence_600s_*.log", "stage_c_queue1.log",
                    "raw_native_*.log", "takeover_20260909_native_raw_queue*.log", "takeover_20260909_cadence_queue3*.log",
                    "takeover_20260908_fourth_queue*.log", "search_capacity_e_*.log",
                    "false_alarm_*.log", "takeover_*false_alarm_funnel*.log",
                    "corrected_c_*.log", "takeover_*corrected_c_controls*.log"):
        for path in (ROOT/"p10/logs").glob(pattern):
            stat = path.stat()
            logs.append({"path":str(path.relative_to(ROOT)),"bytes":stat.st_size,"mtime_epoch":stat.st_mtime})
    result = {"utc":datetime.now(timezone.utc).isoformat(),"visibility_inaccessible_pids":inaccessible,
              "processes":[all_processes[pid] for pid in sorted(owners)],"searches":searches,"logs":logs,
              "interpretation":"A process or directory does not establish healthy progress or completion. Compare CPU/log/artifact timestamps across receipts; preserve failed artifacts before any guarded resume."}
    output = ROOT/"p10/results/takeover_20260908/process_snapshots"
    output.mkdir(exist_ok=True)
    path = output/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".json")
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    controllers = [p for p in result["processes"] if not any("survey_worker.py" in s or "spawn_main" in s for s in p["command"])]
    print(json.dumps({"receipt":str(path.relative_to(ROOT)),"visibility_inaccessible_pids":inaccessible,
                      "controllers":[{"pid":p["pid"],"ppid":p["ppid"],"command":" ".join(p["command"])} for p in controllers],
                      "searches":searches},indent=2))


if __name__ == "__main__":
    main()
