"""Version 2: verify the adopted amendment chain; original controller preserved.

One bounded owning controller; durable progress, exact process identities.

Payloads are top-level subprocesses, never nested multiprocessing pool workers.
The controller's internal event loop enforces deadlines and resource limits;
the Codex session supervises through the registered hourly check-in only.
"""
from common import REPO, ROOT, environment, read, write, sha, utc
environment()
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import psutil


def safe_write(path,value,replace=False):
    for attempt in range(10):
        try:return write(path,value,replace=replace)
        except PermissionError:
            if attempt==9:raise
            time.sleep(.1*(attempt+1))


def identity(process):
    return dict(pid=process.pid,create_time=process.create_time(),command=process.cmdline())


def terminate_owned(row):
    try:
        process=psutil.Process(row["pid"])
        if abs(process.create_time()-row["create_time"])>0.01:return
        children=process.children(recursive=True)
        for child in reversed(children):
            try:child.kill()
            except psutil.NoSuchProcess:pass
        process.kill()
        psutil.wait_procs(children+[process],timeout=5)
    except psutil.NoSuchProcess:pass


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--phase",required=True);ap.add_argument("--jobs",required=True)
    ap.add_argument("--workers",type=int,required=True);ap.add_argument("--deadline",type=int,required=True)
    args=ap.parse_args()
    if not 1<=args.workers<=24:raise ValueError("Core/worker cap")
    me=psutil.Process();cpus=[0,2,4,6,8,10,12,14]+list(range(16,32)) if psutil.cpu_count()==32 else me.cpu_affinity()[:24]
    me.cpu_affinity(cpus)
    # Retain P11.5's explicit execution QoS without calling its historical writer.
    import importlib.util
    spec=importlib.util.spec_from_file_location("p10_3_cpu",REPO/"p11/p11_5/protocol/cpu_allocation.py")
    allocation=importlib.util.module_from_spec(spec);spec.loader.exec_module(allocation)
    qos=allocation.apply_current(cpus)
    config=read(ROOT/"protocol/config.json")
    from registration_chain import verify
    registration_verification = verify()
    owner_path=ROOT/"manifests/controller_owner.json"
    owner=dict(**identity(me),phase=args.phase,started_utc=utc(),cpus=cpus,qos=qos)
    # Exclusive create: even simultaneous launch attempts cannot both become owner.
    with owner_path.open("x",encoding="utf-8") as handle:json.dump(owner,handle,indent=2)
    out=ROOT/f"results/controllers/{args.phase}";out.mkdir(parents=True,exist_ok=False)
    jobs=read(REPO/args.jobs)
    sources={p.relative_to(REPO).as_posix():sha(p) for p in (ROOT/"protocol").glob("*.py")}
    sources.update({p:sha(REPO/p) for p in [args.jobs,"scripts/audit_p5.py","scripts/p8_download.py"]})
    safe_write(out/"launch.json",dict(owner=owner,jobs=len(jobs),workers=args.workers,deadline=args.deadline,
        source_hashes=sources,config_sha256=sha(ROOT/"protocol/config.json")))
    # Only this controller changes aggregate progress; original records are immutable.
    start=time.monotonic();active={};completed=[];pending=list(jobs);status="RUNNING";error=None
    ledger=read(ROOT/"manifests/resource_ledger.json")
    prior=float(ledger["new_queue_hours"])
    def progress():
        workers=[]
        for jid,r in active.items():
            cpu=0.;tree=[]
            try:
                parent=psutil.Process(r["pid"])
                for proc in [parent]+parent.children(recursive=True):
                    try:
                        value=sum(proc.cpu_times()[:2]);cpu+=value
                        tree.append(dict(**identity(proc),cpu_seconds=value))
                    except psutil.NoSuchProcess:pass
            except psutil.NoSuchProcess:pass
            workers.append(dict(job_id=jid,pid=r["pid"],create_time=r["create_time"],
                elapsed_seconds=time.monotonic()-r["timer"],cpu_seconds=cpu,process_tree=tree))
        snapshot=dict(utc=utc(),phase=args.phase,status=status,owner=owner,total=len(jobs),
            completed=len(completed),pending=len(pending),active=len(active),
            unknowns=sum(r["status"]!="COMPLETE" for r in completed),workers=workers,
            c_free_bytes=shutil.disk_usage(REPO).free,
            new_queue_hours=prior+(time.monotonic()-start)/3600,error=error)
        safe_write(out/"progress.json",snapshot,replace=(out/"progress.json").exists())
        safe_write(ROOT/"progress.json",snapshot,replace=(ROOT/"progress.json").exists())
    try:
        while pending or active:
            if shutil.disk_usage(REPO).free<config["budget"]["c_free_floor_bytes"]+1000000000:
                raise RuntimeError("STORAGE_ACTION_REQUIRED: disk within 1 GB of floor")
            if prior+(time.monotonic()-start)/3600>=config["budget"]["new_queue_hours_max"]:
                raise RuntimeError("QUEUE_BUDGET_CAP")
            while pending and len(active)<args.workers:
                job=pending.pop(0);jid=job["job_id"]
                receipt=out/f"attempts/{jid}.json"
                if receipt.exists():raise RuntimeError("Attempt already exists: "+jid)
                log=out/f"logs/{jid}.log";log.parent.mkdir(parents=True,exist_ok=True)
                handle=log.open("x",encoding="utf-8")
                command=[sys.executable,*job["arguments"]]
                proc=subprocess.Popen(command,cwd=REPO,stdout=handle,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                observed=psutil.Process(proc.pid)
                active[jid]=dict(**identity(observed),job=job,proc=proc,handle=handle,
                    timer=time.monotonic(),started_utc=utc(),receipt=receipt)
                print("started",jid,proc.pid,flush=True)
            for jid,r in list(active.items()):
                code=r["proc"].poll();elapsed=time.monotonic()-r["timer"]
                timed_out=code is None and elapsed>=args.deadline
                if timed_out:terminate_owned(r);code=r["proc"].wait(timeout=10)
                if code is None:continue
                r["handle"].close()
                record=dict(job_id=jid,started_utc=r["started_utc"],completed_utc=utc(),
                    wall_seconds=elapsed,pid=r["pid"],create_time=r["create_time"],command=r["command"],
                    exit_code=code,status="TIMEOUT" if timed_out else "COMPLETE" if code==0 else "OPERATIONAL_UNKNOWN",
                    attempt=1,result_path=r["job"].get("result_path"))
                safe_write(r["receipt"],record);completed.append(record);active.pop(jid)
                print("closed",jid,record["status"],round(elapsed,1),flush=True)
            progress()
            if pending or active:time.sleep(3)
        status="CLOSED"
    except BaseException as exc:
        status="FAILED";error=f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        for jid,r in list(active.items()):
            terminate_owned(r);r["handle"].close()
            record=dict(job_id=jid,started_utc=r["started_utc"],completed_utc=utc(),
                status="INTERRUPTED_UNKNOWN",reason=error,wall_seconds=time.monotonic()-r["timer"],
                pid=r["pid"],create_time=r["create_time"],command=r["command"],attempt=1)
            safe_write(r["receipt"],record);completed.append(record);active.pop(jid)
    finally:
        elapsed=time.monotonic()-start
        closure=dict(utc=utc(),owner=owner,status=status,error=error,queue_hours=elapsed/3600,
            completed=len(completed),pending=len(pending),unknowns=sum(r["status"]!="COMPLETE" for r in completed),
            all_owned_workers_closed=not active,source_hashes_unchanged=all(sha(REPO/p)==h for p,h in sources.items()))
        safe_write(out/"closure.json",closure)
        ledger["new_queue_hours"]=prior+elapsed/3600
        ledger["intervals"].append(dict(phase=args.phase,start=owner["started_utc"],end=closure["utc"],hours=elapsed/3600))
        safe_write(ROOT/"manifests/resource_ledger.json",ledger,replace=True)
        progress()
        current=read(owner_path)
        if current["pid"]==owner["pid"] and current["create_time"]==owner["create_time"]:
            owner_path.unlink()
        print("PHASE",status,closure,flush=True)
    if status!="CLOSED":raise SystemExit(1)


if __name__=="__main__":main()
