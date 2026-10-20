from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,importlib.util,json,statistics,tomllib,subprocess
import psutil

R=Path(r"C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter")
O=R/"p10/results/part2d_20260911"
W=O/"heartbeat_checks/20260912T001037Z"
W.mkdir(parents=True,exist_ok=False)
module_spec=importlib.util.spec_from_file_location("p10_guard",R/"p10/protocol/run_part2d_injection_search.py")
Q=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(Q)
manifest=Q.read(Q.MANIFEST)
first=Q.read(O/"injection_inspect_20260912T001215Z.json")
now=datetime.now(timezone.utc)
automation=tomllib.loads(Path(r"C:\Users\seanj\.codex\automations\continue-local-p10-execution\automation.toml").read_text(encoding="utf-8"))
assert automation["id"]=="continue-local-p10-execution" and automation["status"]=="ACTIVE"
assert automation["rrule"]=="FREQ=MINUTELY;INTERVAL=120"
assert automation["target_thread_id"]=="01a08dce-53a4-79a1-9b18-0929d292b272"
state=Q.read(Q.STATE);lock=Q.read(Q.LOCK)
assert state["status"]=="running" and lock["pid"]==state["owner_pid"]
for pid,created in ((lock["pid"],lock["created_epoch"]),(state["child_pid"],state["child_created_epoch"])):
    p=psutil.Process(pid)
    assert p.create_time()==created and p.is_running()
second=Q.process_snapshot()
assert not second["inaccessible_pids"]
previous={r["pid"]:r for r in first["process_snapshot"]["processes"]}
deltas=[]
for row in second["processes"]:
    old=previous.get(row["pid"])
    if old and old["created_epoch"]==row["created_epoch"] and old["command"]==row["command"]:
        delta=row["cpu_user_s"]+row["cpu_kernel_s"]-old["cpu_user_s"]-old["cpu_kernel_s"]
        deltas.append(dict(pid=row["pid"],cpu_delta_s=delta,worker=any("survey_worker.py" in x for x in row["command"])))
assert any(r["worker"] and r["cpu_delta_s"]>0 for r in deltas)
run=Q.RUN
progress=[json.loads(line) for line in (run/"progress.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
assert all(row["status"]=="ok" for row in progress),"A failed attempt needs review"
assert len({row["job_id"] for row in progress})==len(progress),"Repeated attempts need review"
jobs={j["job_id"]:j for j in Q.expected_jobs()}
reused=set(manifest["reused_ids"])
new_ids=sorted(row["job_id"] for row in progress)
assert not reused.intersection(new_ids)
files=[]
for jid in new_ids:
    assert not (run/"jobs"/f"{jid}.pid").exists(),jid
    Q.check_record(Q.read(run/"results"/f"{jid}.json"),jobs[jid],manifest["configuration"],False)
    for sub,suffix in (("jobs",".json"),("results",".json"),("logs",".log"),("traces",".jsonl")):
        p=run/sub/f"{jid}{suffix}"
        files.append(dict(path=p.relative_to(R).as_posix(),sha256=Q.sha(p),bytes=p.stat().st_size))
started=datetime.fromisoformat(state["utc"])
elapsed=(now-started).total_seconds()
remaining=2100-600-len(new_ids)
windows=[]
for minutes in (30,60,120):
    start=max(started,now-timedelta(minutes=minutes))
    n=sum(datetime.fromisoformat(row["utc"].replace("Z","+00:00"))>=start for row in progress)
    duration=(now-start).total_seconds()
    windows.append(dict(window_minutes=minutes,observed_seconds=duration,completed=n,
       jobs_per_hour=n/duration*3600,extrapolated_remaining_hours=remaining*duration/n/3600 if n else None))
overall_remaining_hours=remaining*elapsed/len(new_ids)/3600
assert overall_remaining_hours>2 and all(w["extrapolated_remaining_hours"] is None or w["extrapolated_remaining_hours"]>2 for w in windows)
report=dict(utc=now.isoformat(),state="healthy_search_running",inspection="p10/results/part2d_20260911/injection_inspect_20260912T001215Z.json",
    total=2100,reused=600,new_successful=len(new_ids),complete=600+len(new_ids),remaining=remaining,
    invalid_results=[],failed_attempts=0,all_frozen_source_input_and_copies_verified_at_inspection=True,
    owner_pid=state["owner_pid"],owner_created_epoch=state["owner_created_epoch"],child_pid=state["child_pid"],
    matching_workers_with_cpu_progress=sum(r["worker"] and r["cpu_delta_s"]>0 for r in deltas),
    elapsed_hours=elapsed/3600,completed_wall_median_seconds=statistics.median(r["wall_s"] for r in progress),
    overall_throughput_jobs_per_hour=len(new_ids)/elapsed*3600,
    overall_extrapolated_remaining_hours=overall_remaining_hours,rolling_throughput=windows,
    expected_finish_utc=None,credible_finish_within_two_hours=False,shorten_schedule=False,
    uncertainty="Throughput extrapolations are descriptive, not a firm ETA: host workloads vary and the remaining ordered hosts differ. Every measured window puts the whole queue beyond two hours. No CPU/one-case ETA is substituted.",
    automation=dict(id=automation["id"],status=automation["status"],rrule=automation["rrule"],
        target_thread_id=automation["target_thread_id"],prompt_sha256=hashlib.sha256(automation["prompt"].encode()).hexdigest()),
    scientific_changes=False,baseline_repeated=False,reason="Frozen source unchanged; full queue not complete; preserve healthy owners and continue Part 2d only when ready.")
Q.save(W/"check.json",report,exclusive=True)
Q.save(W/"settled_search_artifacts.json",dict(utc=now.isoformat(),ids=new_ids,files=files),exclusive=True)
Q.save(W/"process_health.json",dict(first_utc=first["utc"],second=second,cpu_deltas=deltas),exclusive=True)
Q.save(W/"state_and_lock.json",dict(state=state,lock=lock),exclusive=True)
Q.save(W/"saved_automation.json",automation,exclusive=True)
print(json.dumps({k:v for k,v in report.items() if k not in ("automation",)},indent=2))
