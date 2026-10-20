"""Bounded read-only science supervision; only check-in/resume receipts are written."""
from common import REPO, ROOT, read, write, utc
import json
import shutil
import sys
import psutil


def main():
    current=read(ROOT/"progress.json")
    previous_path=ROOT/"logs/last_checkin.json"
    previous=read(previous_path) if previous_path.exists() else None
    owner=current["owner"];alive=False
    try:
        proc=psutil.Process(owner["pid"])
        alive=abs(proc.create_time()-owner["create_time"])<.01 and proc.cmdline()==owner["command"]
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    old_workers={(w["pid"],w["create_time"]):w for w in (previous or {}).get("workers",[])}
    stalled=[]
    for worker in current["workers"]:
        prior=old_workers.get((worker["pid"],worker["create_time"]))
        if prior is not None and worker["cpu_seconds"]<=prior["cpu_seconds"]:
            stalled.append(worker["job_id"])
    log=ROOT/f"logs/controller_{current['phase']}.log"
    tail=log.read_text(encoding="utf-8",errors="replace").splitlines()[-50:] if log.exists() else []
    closure=ROOT/f"results/controllers/{current['phase']}/closure.json"
    disk=shutil.disk_usage(REPO).free
    events=[]
    if not alive and not closure.exists():events.append("OWNER_GONE_WITHOUT_CLOSURE")
    if stalled:events.append("STALLED_WORKERS")
    if disk<28000000000:events.append("STORAGE_WITHIN_3GB")
    if previous and current["unknowns"]>previous["unknowns"]:events.append("RISING_ERROR_COUNT")
    if closure.exists():events.append("PHASE_CLOSED")
    result=dict(current,checkin_utc=utc(),owner_alive=alive,closure_receipt_exists=closure.exists(),
        observed_c_free_bytes=disk,stalled_job_ids=stalled,triggers=events,last_50_controller_lines=tail,
        per_case_science_opened=False,engineering_time=True)
    with (ROOT/"logs/checkins.jsonl").open("a",encoding="utf-8") as stream:
        stream.write(json.dumps(result,allow_nan=False)+"\n")
    write(previous_path,result,replace=previous_path.exists())
    with (ROOT/"RESUME_P10_3.md").open("a",encoding="utf-8") as stream:
        stream.write(f"\n{result['checkin_utc']} [M]: {current['phase']}; completed {current['completed']}, pending {current['pending']}, active {current['active']}, unknowns {current['unknowns']}; C free {disk/1e9:.3f} GB; new queue {current['new_queue_hours']:.5f} h; triggers {events}.\n")
    print(json.dumps(result,indent=2),flush=True)


if __name__=="__main__":main()
