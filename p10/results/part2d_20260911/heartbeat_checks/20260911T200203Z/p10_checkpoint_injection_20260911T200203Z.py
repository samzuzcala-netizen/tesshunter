from pathlib import Path
import hashlib,json,subprocess,shutil
from datetime import datetime,timezone
R=Path(r"C:\Users\seanj\Downloads\tess-exoplanet-candidate-hunter\tess-exoplanet-candidate-hunter")
O=R/"p10/results/part2d_20260911"
W=O/"heartbeat_checks/20260911T200203Z"
r=json.loads((W/"check.json").read_text())
art=json.loads((W/"settled_search_artifacts.json").read_text())
frozen=lambda b:b.split(b"## 0. Pre-registered decision rules",1)[1].split(b"## 1. Part 0: housekeeping",1)[0]
hp=R/"HANDOFF_P10.md";before=frozen(hp.read_bytes())
assert hashlib.sha256(before).hexdigest()=="01bd29efc1b4b57eb6fcc99f340f515c0c2cae2e0162a2e9f96beef92b678f19"
heading="### Full injection search: 806/2100 verified, 2026-09-11 20:04 UTC [M]"
body=f"""{heading}

The same guarded search owner remains healthy: **806/2,100 successful searches**, comprising the original 600 preserved selected-e cases plus 206 new cases; **1,294 remain**. No failed attempt or invalid settled result was found. All frozen source/input/copy hashes verified at the 20:02 inspection. Owner 33648 and child launcher 30412 match their original creation times; 13 continuing worker interpreters show fresh CPU progress, while other workers completed/replaced jobs. Current process/state/lock evidence and exact hashes of the 206 settled job/result/log/trace groups are under `p10/results/part2d_20260911/heartbeat_checks/20260911T200203Z/`. Never restart healthy owners or rely on these dated PIDs alone.

**Timing and schedule.** Observed overall throughput is 92.86 jobs/hour. The last 30/60/120-minute windows extrapolate 10.27/10.61/14.22 hours remaining; heterogeneous ordered host workloads make these descriptive estimates, not a firm completion time. None supports a whole-queue finish within two hours, so the existing ACTIVE heartbeat remains at its verified 120-minute interval. No schedule edit, source change, sample redraw, repeated baseline or new scientific-stage execution occurred. Continue the prescribed full A/S calibration and Stop Rule 1 when all 2,100 successful results are verified and the owner/lock close.

The preceding freeze checkpoint `7800a218` is saved. Git briefly ran automatic packing after that commit while the search was active; the operational overlap receipt retains that observation and all original job timers remain untouched. Further operational commits disable automatic maintenance for that command to avoid another overlap.

"""
t=hp.read_text(encoding="utf-8");assert heading not in t
t=t.replace("## 0. Pre-registered decision rules",body+"## 0. Pre-registered decision rules",1)
hp.write_text(t,encoding="utf-8",newline="")
assert frozen(hp.read_bytes())==before
rp=R/"RESUME_P10.md"
entry="""# P10 current check: 806/2,100 searches complete

At 2026-09-11 20:04 UTC, all 806 settled searches are successful (600 preserved e + 206 new); 1,294 remain. The original guarded owner/lock and 16-worker queue are healthy, source/input/copy hashes are unchanged, and no failed attempt was found. **Keep the two-hour cadence**: measured throughput puts the complete queue well beyond two hours. Use the current `run_part2d_injection_search.py inspect` entry point and continue full A/S calibration and Stop Rule 1 only when the full queue is verified successful and closes. Do not restart healthy workers or rerun prepare. Evidence: `p10/results/part2d_20260911/heartbeat_checks/20260911T200203Z/`. Earlier entries below describe the frozen configuration and execution contract.

---

"""
rp.write_text(entry+rp.read_text(encoding="utf-8"),encoding="utf-8",newline="")
for name in ("p10_check_injection_20260911T200203Z.py","p10_checkpoint_injection_20260911T200203Z.py"):
    shutil.copy2(Path("work")/name,W/name)
def git(*args):
    res=subprocess.run(["git","-C",str(R),"-c","maintenance.auto=false","-c","gc.auto=0",*args],capture_output=True,text=True)
    if res.returncode:raise RuntimeError(res.stderr)
    return res.stdout
assert not git("diff","--cached","--name-only").strip(),"Unexpected staged work"
paths=["HANDOFF_P10.md","RESUME_P10.md",W.relative_to(R).as_posix(),
       "p10/results/part2d_20260911/injection_inspect_20260911T200244Z.json",
       "p10/results/part2d_20260911/injection_inspect_20260911T180115Z.json",
       "p10/results/part2d_20260911/git_automatic_maintenance_overlap.json"]
for row in art["files"]:
    p=R/row["path"]
    with p.open("rb") as s:assert hashlib.file_digest(s,"sha256").hexdigest()==row["sha256"]
    paths.append(row["path"])
pathfile=Path("work/p10_check_stage_paths_200203.txt").resolve()
pathfile.write_bytes(b"\0".join(p.encode() for p in paths)+b"\0")
git("-c","core.safecrlf=false","add",f"--pathspec-from-file={pathfile}","--pathspec-file-nul")
assert frozen(hp.read_bytes())==before
staged=git("diff","--cached","--name-only").splitlines()
assert all(p in set(paths) or p.startswith(W.relative_to(R).as_posix()+"/") for p in staged)
assert not git("diff","--cached","--check").strip()
commit=git("commit","-m","Prompt 10: checkpoint 806 successful injection searches")
Path("work/p10_check_commit_200203.log").write_text(commit,encoding="utf-8")
head=git("rev-parse","HEAD").strip()
assert not git("diff","--name-only").strip()
assert frozen(hp.read_bytes())==before
print(json.dumps(dict(commit=head,staged_files=len(staged),settled_new_searches=len(art["ids"]),
                     remaining=1294,schedule_minutes=120,frozen_section_unchanged=True),indent=2))
