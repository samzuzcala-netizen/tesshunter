"""Commit only a dated, already-verified P10 heartbeat and its newly settled artifacts."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,shutil,subprocess,time

R=Path(r"C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter")
ap=argparse.ArgumentParser();ap.add_argument("stamp");args=ap.parse_args()
W=R/"p10/results/part2d_20260911/heartbeat_checks"/args.stamp
assert W.resolve().is_relative_to((R/"p10/results/part2d_20260911/heartbeat_checks").resolve())
r=json.loads((W/"check.json").read_text())
art=json.loads((W/"settled_search_artifacts.json").read_text())
assert r["state"]=="healthy_search_running" and not r["failed_attempts"] and not r["invalid_results"]
assert not r["shorten_schedule"] and r["automation"]["rrule"]=="FREQ=MINUTELY;INTERVAL=120"
def git(*argv):
    p=subprocess.run(["git","-C",str(R),"-c","maintenance.auto=false","-c","gc.auto=0",*argv],capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout
assert not git("diff","--cached","--name-only").strip()
assert not git("diff","--name-only").strip(),"Review unexpected tracked changes before updating documents"
tracked=set(git("ls-files","-z","--","data/survey/p10/part2d/injection_search").strip("\0").split("\0"))
new=[row for row in art["files"] if row["path"] not in tracked]
new_results=sum("/results/" in row["path"] for row in new)
assert len(new)==4*new_results
for row in new:
    with (R/row["path"]).open("rb") as f:assert hashlib.file_digest(f,"sha256").hexdigest()==row["sha256"]
hp=R/"HANDOFF_P10.md"
frozen=lambda b:b.split(b"## 0. Pre-registered decision rules",1)[1].split(b"## 1. Part 0: housekeeping",1)[0]
before=frozen(hp.read_bytes())
assert hashlib.sha256(before).hexdigest()=="01bd29efc1b4b57eb6fcc99f340f515c0c2cae2e0162a2e9f96beef92b678f19"
when=datetime.fromisoformat(r["utc"]).strftime("%Y-%m-%d %H:%M UTC")
evidence=W.relative_to(R).as_posix()
heading=f"### Full injection search: {r['complete']}/2100 verified, {when} [M]"
body=f"""{heading}

**{r['complete']:,}/2,100 settled searches are successful**: 600 preserved selected-e cases and {r['new_successful']:,} new cases, with **{r['remaining']:,} remaining**. This checkpoint adds {new_results} newly settled job/result/log/trace groups since the previous saved checkpoint. No failed attempt or invalid settled result was found. Frozen source/input/copy hashes verified, the same owner and child creation times match the lock/state, and {r['matching_workers_with_cpu_progress']} continuing worker interpreters show fresh CPU progress. Exact case hashes, both process samples, current state/lock, and the saved automation are under `{evidence}/`. The healthy 16-worker queue continues without restart; no source, sample, threshold or scientific-stage change occurred.

**Timing and cadence.** Overall observed throughput is {r['overall_throughput_jobs_per_hour']:.2f} jobs/hour; the last 30/60/120-minute windows extrapolate {r['rolling_throughput'][0]['extrapolated_remaining_hours']:.2f}/{r['rolling_throughput'][1]['extrapolated_remaining_hours']:.2f}/{r['rolling_throughput'][2]['extrapolated_remaining_hours']:.2f} hours remaining. These are descriptive extrapolations across heterogeneous ordered host workloads, not a firm ETA. None supports a complete-queue finish within two hours. The existing heartbeat remains verified ACTIVE at 120 minutes, with its full durable continuation prompt unchanged. The full A/S calibration and Stop Rule 1 remain pending until all 2,100 searches verify successful and the owner/lock close. No unchanged-source baseline was repeated.

"""
t=hp.read_text(encoding="utf-8");assert heading not in t
hp.write_text(t.replace("## 0. Pre-registered decision rules",body+"## 0. Pre-registered decision rules",1),encoding="utf-8",newline="")
assert frozen(hp.read_bytes())==before
rp=R/"RESUME_P10.md"
entry=f"""# P10 current check: {r['complete']:,}/2,100 searches complete

At {when}, all {r['complete']:,} settled searches are successful (600 preserved e + {r['new_successful']} new); {r['remaining']:,} remain. Frozen source/input/copy hashes are unchanged, current owner/worker identities and CPU progress are healthy, and no failed attempt was found. **Keep the two-hour cadence**: every measured whole-queue throughput estimate remains beyond two hours. Continue with `p10/protocol/run_part2d_injection_search.py inspect`; never repeat prepare or restart healthy owners. Full A/S calibration and original Stop Rule 1 follow only after all 2,100 searches verify successful and the queue closes. Evidence: `{evidence}/`. Earlier entries below preserve the frozen configuration and execution contract.

---

"""
rp.write_text(entry+rp.read_text(encoding="utf-8"),encoding="utf-8",newline="")
shutil.copy2(Path("work")/f"p10_check_injection_{args.stamp}.py",W/f"p10_check_injection_{args.stamp}.py")
shutil.copy2(Path(__file__),W/"p10_checkpoint_heartbeat.py")
paths=["HANDOFF_P10.md","RESUME_P10.md",evidence,r["inspection"]]+[row["path"] for row in new]
fp=(Path("work")/f"p10_stage_paths_{args.stamp}.txt").resolve()
fp.write_bytes(b"\0".join(p.encode() for p in paths)+b"\0")
retries=[]
for attempt in range(3):
    try:
        git("-c","core.safecrlf=false","add",f"--pathspec-from-file={fp}","--pathspec-file-nul")
        break
    except RuntimeError as exc:
        if "Permission denied" not in str(exc) or attempt==2:raise
        assert not git("diff","--cached","--name-only").strip()
        retries.append(dict(utc=datetime.now(timezone.utc).isoformat(),error=str(exc)))
        time.sleep(0.5)
if retries:
    (W/"git_write_retries.json").write_text(json.dumps(dict(attempts=retries,permissions_changed=False),indent=2)+"\n",encoding="utf-8")
    git("add","--",str(W/"git_write_retries.json"))
assert frozen(hp.read_bytes())==before
staged=git("diff","--cached","--name-only").splitlines()
assert all(p in set(paths) or p.startswith(evidence+"/") for p in staged)
assert not git("diff","--cached","--check").strip()
output=git("commit","-m",f"Prompt 10: checkpoint {r['complete']} successful injection searches")
(Path("work")/f"p10_commit_{args.stamp}.log").write_text(output,encoding="utf-8")
assert not git("diff","--name-only").strip()
assert frozen(hp.read_bytes())==before
print(json.dumps(dict(commit=git("rev-parse","HEAD").strip(),files=len(staged),newly_checkpointed=new_results,
    verified_successful=r["complete"],remaining=r["remaining"],schedule_minutes=120),indent=2))
